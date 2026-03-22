"""Tests for post-conversion validator (v1 format)."""
from __future__ import annotations

from typing import Any, Dict

import pytest

from src.converters.talend_to_v1.validator import (
    ValidationIssue,
    ValidationReport,
    validate_config,
)


def _make_config(**overrides: Any) -> Dict[str, Any]:
    """Build a minimal valid V1 config for testing.

    V1 uses "from"/"to" keys in flows and triggers (not "source"/"target").
    """
    config: Dict[str, Any] = {
        "name": "test_job",
        "version": "1.0",
        "context": {},
        "components": [
            {
                "id": "src_1",
                "type": "FileInputDelimited",
                "config": {"path": "a.csv"},
                "schema": [{"name": "col1", "type": "string"}],
            },
            {
                "id": "sink_1",
                "type": "FileOutputDelimited",
                "config": {"path": "b.csv"},
                "schema": [{"name": "col1", "type": "string"}],
            },
        ],
        "flows": [
            {"name": "row1", "from": "src_1", "to": "sink_1"},
        ],
    }
    config.update(overrides)
    return config


# ---------------------------------------------------------------------------
# Reference Integrity
# ---------------------------------------------------------------------------
class TestValidateReferenceIntegrity:
    def test_valid_config_passes(self) -> None:
        """Config with matching components and flows has no errors."""
        report = validate_config(_make_config())
        errors = [i for i in report.issues if i.severity == "error"]
        assert not errors
        assert report.valid

    def test_missing_flow_target(self) -> None:
        """Flow referencing non-existent target component = error."""
        config = _make_config(
            flows=[{"name": "row1", "from": "src_1", "to": "nonexistent"}],
        )
        report = validate_config(config)
        errors = [i for i in report.issues if i.severity == "error"]
        assert any("nonexistent" in e.message for e in errors)
        assert not report.valid

    def test_missing_flow_source(self) -> None:
        """Flow referencing non-existent source component = error."""
        config = _make_config(
            flows=[{"name": "row1", "from": "ghost", "to": "sink_1"}],
        )
        report = validate_config(config)
        errors = [i for i in report.issues if i.severity == "error"]
        assert any("ghost" in e.message for e in errors)
        assert not report.valid

    def test_orphan_component_warning(self) -> None:
        """A component with no flows or triggers = warning."""
        config = _make_config()
        config["components"].append(
            {
                "id": "orphan_1",
                "type": "Sort",
                "config": {"criteria": "col1"},
                "schema": [{"name": "col1", "type": "string"}],
            }
        )
        report = validate_config(config)
        warnings = [i for i in report.issues if i.severity == "warning"]
        assert any("orphan_1" in w.message for w in warnings)

    def test_source_component_no_incoming_ok(self) -> None:
        """A source component (has outgoing but no incoming flows) is NOT orphan."""
        config = _make_config()
        # src_1 has outgoing flow but no incoming -- that's fine
        report = validate_config(config)
        warnings = [
            i for i in report.issues
            if i.severity == "warning" and "orphan" in i.message.lower()
        ]
        assert not warnings

    def test_trigger_missing_source(self) -> None:
        """Trigger referencing non-existent source = error."""
        config = _make_config(
            triggers=[{"type": "onSubjobOk", "from": "ghost", "to": "sink_1"}],
        )
        report = validate_config(config)
        errors = [i for i in report.issues if i.severity == "error"]
        assert any("ghost" in e.message for e in errors)

    def test_trigger_missing_target(self) -> None:
        """Trigger referencing non-existent target = error."""
        config = _make_config(
            triggers=[{"type": "onSubjobOk", "from": "src_1", "to": "missing"}],
        )
        report = validate_config(config)
        errors = [i for i in report.issues if i.severity == "error"]
        assert any("missing" in e.message for e in errors)


# ---------------------------------------------------------------------------
# tMap-Specific (v1 type is "Map")
# ---------------------------------------------------------------------------
class TestValidateTMap:
    @staticmethod
    def _tmap_config() -> Dict[str, Any]:
        return {
            "name": "test_job",
            "version": "1.0",
            "context": {},
            "components": [
                {
                    "id": "src_1",
                    "type": "FileInputDelimited",
                    "config": {"path": "in.csv"},
                    "schema": [{"name": "id", "type": "string"}],
                },
                {
                    "id": "lookup_src",
                    "type": "FileInputDelimited",
                    "config": {"path": "lookup.csv"},
                    "schema": [{"name": "id", "type": "string"}],
                },
                {
                    "id": "map_1",
                    "type": "Map",
                    "config": {
                        "lookups": [
                            {
                                "name": "lookup_input",
                                "join_type": "left",
                                "keys": [{"main": "id", "lookup": "id"}],
                            }
                        ],
                        "variables": [],
                        "outputs": [{"name": "out1", "columns": []}],
                    },
                    "schema": [{"name": "id", "type": "string"}],
                },
                {
                    "id": "sink_1",
                    "type": "FileOutputDelimited",
                    "config": {"path": "out.csv"},
                    "schema": [{"name": "id", "type": "string"}],
                },
            ],
            "flows": [
                {"name": "main", "from": "src_1", "to": "map_1", "input": "main"},
                {"name": "lookup_input", "from": "lookup_src", "to": "map_1", "input": "lookup_input"},
                {"name": "out1", "from": "map_1", "to": "sink_1", "output": "out1"},
            ],
        }

    def test_valid_tmap_passes(self) -> None:
        """A correctly configured Map component has no Map-specific errors."""
        report = validate_config(self._tmap_config())
        tmap_issues = [
            i for i in report.issues
            if i.component_id == "map_1" and i.severity == "error"
        ]
        assert not tmap_issues

    def test_empty_join_key_main(self) -> None:
        """Map lookup with empty main join key = error."""
        config = self._tmap_config()
        config["components"][2]["config"]["lookups"][0]["keys"] = [
            {"main": "", "lookup": "id"}
        ]
        report = validate_config(config)
        errors = [i for i in report.issues if i.severity == "error"]
        assert any("join key" in e.message.lower() for e in errors)

    def test_empty_join_key_lookup(self) -> None:
        """Map lookup with empty lookup join key = error."""
        config = self._tmap_config()
        config["components"][2]["config"]["lookups"][0]["keys"] = [
            {"main": "id", "lookup": ""}
        ]
        report = validate_config(config)
        errors = [i for i in report.issues if i.severity == "error"]
        assert any("join key" in e.message.lower() for e in errors)

    def test_missing_lookup_input_flow(self) -> None:
        """Map lookup with no matching input flow = warning."""
        config = self._tmap_config()
        # Remove the lookup flow
        config["flows"] = [f for f in config["flows"] if f.get("input") != "lookup_input"]
        report = validate_config(config)
        warnings = [i for i in report.issues if i.severity == "warning"]
        assert any("lookup_input" in w.message for w in warnings)


# ---------------------------------------------------------------------------
# Expression Validation
# ---------------------------------------------------------------------------
class TestValidateExpressions:
    def test_java_method_substring_detected(self) -> None:
        """Expression with .substring() = warning."""
        config = _make_config()
        config["components"] = [
            {
                "id": "src_1",
                "type": "FileInputDelimited",
                "config": {"path": "a.csv"},
                "schema": [{"name": "col1", "type": "string"}],
            },
            {
                "id": "map_1",
                "type": "Map",
                "config": {
                    "lookups": [],
                    "variables": [],
                    "outputs": [
                        {
                            "name": "out1",
                            "columns": [
                                {"name": "col1", "expression": 'col("x").substring(0, 5)'},
                            ],
                        }
                    ],
                },
                "schema": [{"name": "col1", "type": "string"}],
            },
        ]
        config["flows"] = [{"name": "row1", "from": "src_1", "to": "map_1"}]
        report = validate_config(config)
        warnings = [
            i for i in report.issues
            if i.severity == "warning" and "java" in i.message.lower()
        ]
        assert len(warnings) >= 1

    def test_java_method_equals_detected(self) -> None:
        """Expression with .equals() = warning."""
        config = _make_config()
        config["components"] = [
            {
                "id": "src_1",
                "type": "FileInputDelimited",
                "config": {"path": "a.csv"},
                "schema": [{"name": "col1", "type": "string"}],
            },
            {
                "id": "map_1",
                "type": "Map",
                "config": {
                    "lookups": [],
                    "variables": [],
                    "outputs": [
                        {
                            "name": "out1",
                            "columns": [
                                {"name": "col1", "expression": 'row1.name.equals("test")'},
                            ],
                        }
                    ],
                },
                "schema": [{"name": "col1", "type": "string"}],
            },
        ]
        config["flows"] = [{"name": "row1", "from": "src_1", "to": "map_1"}]
        report = validate_config(config)
        warnings = [
            i for i in report.issues
            if i.severity == "warning" and "java" in i.message.lower()
        ]
        assert len(warnings) >= 1

    def test_clean_expression_ok(self) -> None:
        """Clean expression has no expression warnings."""
        config = _make_config()
        config["components"] = [
            {
                "id": "src_1",
                "type": "FileInputDelimited",
                "config": {"path": "a.csv"},
                "schema": [{"name": "col1", "type": "string"}],
            },
            {
                "id": "map_1",
                "type": "Map",
                "config": {
                    "lookups": [],
                    "variables": [{"name": "x", "expression": "col('amount') * 2"}],
                    "outputs": [
                        {
                            "name": "out1",
                            "columns": [
                                {"name": "col1", "expression": "var.x + 1"},
                            ],
                        }
                    ],
                },
                "schema": [{"name": "col1", "type": "string"}],
            },
        ]
        config["flows"] = [{"name": "row1", "from": "src_1", "to": "map_1"}]
        report = validate_config(config)
        expr_warnings = [
            i for i in report.issues
            if i.severity == "warning" and "java" in i.message.lower()
        ]
        assert not expr_warnings


# ---------------------------------------------------------------------------
# Conversion Quality
# ---------------------------------------------------------------------------
class TestValidateConversionQuality:
    def test_unsupported_component_flagged(self) -> None:
        """Component with _unsupported=True = info."""
        config = _make_config()
        config["components"].append(
            {"id": "unsup_1", "type": "tSomeWeirdComp", "_unsupported": True, "schema": []}
        )
        report = validate_config(config)
        infos = [i for i in report.issues if i.severity == "info"]
        assert any("unsup_1" in i.message for i in infos)

    def test_empty_config_flagged(self) -> None:
        """Component with empty/missing config = warning."""
        config = _make_config()
        config["components"][0]["config"] = {}
        report = validate_config(config)
        warnings = [
            i for i in report.issues
            if i.severity == "warning" and "config" in i.field
        ]
        assert any("src_1" in w.message for w in warnings)

    def test_missing_schema_flagged(self) -> None:
        """Component with missing schema = warning."""
        config = _make_config()
        del config["components"][0]["schema"]
        report = validate_config(config)
        warnings = [
            i for i in report.issues
            if i.severity == "warning" and "schema" in i.field
        ]
        assert any("src_1" in w.message for w in warnings)


# ---------------------------------------------------------------------------
# Overall Report
# ---------------------------------------------------------------------------
class TestValidateOverall:
    def test_clean_config_valid(self) -> None:
        """Clean config returns valid=True and no issues."""
        report = validate_config(_make_config())
        assert report.valid
        assert isinstance(report.summary, str)

    def test_errors_make_invalid(self) -> None:
        """Errors make valid=False, warnings alone don't."""
        # Config with only warnings (orphan) should still be valid
        config = _make_config()
        config["components"].append(
            {
                "id": "orphan",
                "type": "Sort",
                "config": {"criteria": "col1"},
                "schema": [{"name": "col1", "type": "string"}],
            }
        )
        report = validate_config(config)
        # orphan is a warning, not an error
        assert report.valid

        # Config with errors should be invalid
        config2 = _make_config(
            flows=[{"name": "row1", "from": "src_1", "to": "missing"}],
        )
        report2 = validate_config(config2)
        assert not report2.valid

    def test_summary_includes_counts(self) -> None:
        """Summary string includes issue counts."""
        config = _make_config(
            flows=[{"name": "row1", "from": "src_1", "to": "missing"}],
        )
        report = validate_config(config)
        assert "error" in report.summary.lower()

    def test_summary_no_issues(self) -> None:
        """Clean config summary says 'passed'."""
        report = validate_config(_make_config())
        assert "passed" in report.summary.lower() or "no issues" in report.summary.lower()
