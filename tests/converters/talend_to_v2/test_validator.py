"""Tests for post-conversion validator."""
from __future__ import annotations

import copy
from typing import Any, Dict

import pytest

from src.converters.talend_to_v2.validator import (
    ValidationIssue,
    ValidationReport,
    validate_v2_config,
)


def _make_config(**overrides: Any) -> Dict[str, Any]:
    """Build a minimal valid V2 config for testing."""
    config: Dict[str, Any] = {
        "name": "test_job",
        "version": "2.0",
        "context": {},
        "components": [
            {"id": "src_1", "type": "file_input_delimited", "config": {"path": "a.csv"}},
            {"id": "sink_1", "type": "file_output_delimited", "config": {"path": "b.csv"}},
        ],
        "flows": [
            {"name": "row1", "source": "src_1", "target": "sink_1"},
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
        report = validate_v2_config(_make_config())
        errors = [i for i in report.issues if i.severity == "error"]
        assert not errors
        assert report.valid

    def test_missing_flow_target(self) -> None:
        """Flow referencing non-existent target component = error."""
        config = _make_config(
            flows=[{"name": "row1", "source": "src_1", "target": "nonexistent"}],
        )
        report = validate_v2_config(config)
        errors = [i for i in report.issues if i.severity == "error"]
        assert any("nonexistent" in e.message for e in errors)
        assert not report.valid

    def test_missing_flow_source(self) -> None:
        """Flow referencing non-existent source component = error."""
        config = _make_config(
            flows=[{"name": "row1", "source": "ghost", "target": "sink_1"}],
        )
        report = validate_v2_config(config)
        errors = [i for i in report.issues if i.severity == "error"]
        assert any("ghost" in e.message for e in errors)
        assert not report.valid

    def test_orphan_component_warning(self) -> None:
        """A component with no flows at all (not a source) = warning."""
        config = _make_config()
        config["components"].append(
            {"id": "orphan_1", "type": "sort_row", "config": {}}
        )
        report = validate_v2_config(config)
        warnings = [i for i in report.issues if i.severity == "warning"]
        assert any("orphan_1" in w.message for w in warnings)

    def test_source_component_no_incoming_ok(self) -> None:
        """A source component (has outgoing but no incoming flows) is NOT orphan."""
        config = _make_config()
        # src_1 has outgoing flow but no incoming — that's fine
        report = validate_v2_config(config)
        warnings = [
            i for i in report.issues
            if i.severity == "warning" and "orphan" in i.message.lower()
        ]
        assert not warnings


# ---------------------------------------------------------------------------
# tMap-Specific
# ---------------------------------------------------------------------------
class TestValidateTMap:
    @staticmethod
    def _tmap_config() -> Dict[str, Any]:
        return {
            "name": "test_job",
            "version": "2.0",
            "context": {},
            "components": [
                {"id": "src_1", "type": "file_input_delimited", "config": {}},
                {"id": "lookup_src", "type": "file_input_delimited", "config": {}},
                {
                    "id": "map_1",
                    "type": "map",
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
                },
                {"id": "sink_1", "type": "file_output_delimited", "config": {}},
            ],
            "flows": [
                {"name": "main", "source": "src_1", "target": "map_1", "input": "main"},
                {"name": "lookup_input", "source": "lookup_src", "target": "map_1", "input": "lookup_input"},
                {"name": "out1", "source": "map_1", "target": "sink_1", "output": "out1"},
            ],
        }

    def test_valid_tmap_passes(self) -> None:
        """A correctly configured tMap has no tMap-specific errors."""
        report = validate_v2_config(self._tmap_config())
        tmap_issues = [i for i in report.issues if i.component_id == "map_1" and i.severity == "error"]
        assert not tmap_issues

    def test_empty_join_key_main(self) -> None:
        """tMap lookup with empty main join key = error."""
        config = self._tmap_config()
        config["components"][2]["config"]["lookups"][0]["keys"] = [
            {"main": "", "lookup": "id"}
        ]
        report = validate_v2_config(config)
        errors = [i for i in report.issues if i.severity == "error"]
        assert any("join key" in e.message.lower() for e in errors)

    def test_empty_join_key_lookup(self) -> None:
        """tMap lookup with empty lookup join key = error."""
        config = self._tmap_config()
        config["components"][2]["config"]["lookups"][0]["keys"] = [
            {"main": "id", "lookup": ""}
        ]
        report = validate_v2_config(config)
        errors = [i for i in report.issues if i.severity == "error"]
        assert any("join key" in e.message.lower() for e in errors)

    def test_missing_lookup_input_flow(self) -> None:
        """tMap lookup with no matching input flow = warning."""
        config = self._tmap_config()
        # Remove the lookup flow
        config["flows"] = [f for f in config["flows"] if f.get("input") != "lookup_input"]
        report = validate_v2_config(config)
        warnings = [i for i in report.issues if i.severity == "warning"]
        assert any("lookup_input" in w.message for w in warnings)


# ---------------------------------------------------------------------------
# Expression Validation
# ---------------------------------------------------------------------------
class TestValidateExpressions:
    def test_java_method_detected(self) -> None:
        """Expression with .equals() or .substring() = warning."""
        config = _make_config()
        config["components"] = [
            {"id": "src_1", "type": "file_input_delimited", "config": {}},
            {
                "id": "map_1",
                "type": "map",
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
            },
        ]
        config["flows"] = [{"name": "row1", "source": "src_1", "target": "map_1"}]
        report = validate_v2_config(config)
        warnings = [i for i in report.issues if i.severity == "warning" and "java" in i.message.lower()]
        assert len(warnings) >= 1

    def test_equals_detected(self) -> None:
        """Expression with .equals() = warning."""
        config = _make_config()
        config["components"] = [
            {"id": "src_1", "type": "file_input_delimited", "config": {}},
            {
                "id": "map_1",
                "type": "map",
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
            },
        ]
        config["flows"] = [{"name": "row1", "source": "src_1", "target": "map_1"}]
        report = validate_v2_config(config)
        warnings = [i for i in report.issues if i.severity == "warning" and "java" in i.message.lower()]
        assert len(warnings) >= 1

    def test_uppercase_var_detected(self) -> None:
        """Expression with Var. (uppercase) = warning."""
        config = _make_config()
        config["components"] = [
            {"id": "src_1", "type": "file_input_delimited", "config": {}},
            {
                "id": "map_1",
                "type": "map",
                "config": {
                    "lookups": [],
                    "variables": [{"name": "x", "expression": "Var.something + 1"}],
                    "outputs": [{"name": "out1", "columns": []}],
                },
            },
        ]
        config["flows"] = [{"name": "row1", "source": "src_1", "target": "map_1"}]
        report = validate_v2_config(config)
        warnings = [i for i in report.issues if i.severity == "warning" and "var" in i.message.lower()]
        assert len(warnings) >= 1

    def test_clean_expression_ok(self) -> None:
        """Clean V2 expression has no expression warnings."""
        config = _make_config()
        config["components"] = [
            {"id": "src_1", "type": "file_input_delimited", "config": {}},
            {
                "id": "map_1",
                "type": "map",
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
            },
        ]
        config["flows"] = [{"name": "row1", "source": "src_1", "target": "map_1"}]
        report = validate_v2_config(config)
        expr_warnings = [
            i for i in report.issues
            if i.severity == "warning" and ("java" in i.message.lower() or "var" in i.message.lower())
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
            {"id": "unsup_1", "type": "tSomeWeirdComp", "_unsupported": True}
        )
        report = validate_v2_config(config)
        infos = [i for i in report.issues if i.severity == "info"]
        assert any("unsup_1" in i.message for i in infos)

    def test_needs_rewrite_flagged(self) -> None:
        """Component with _needs_rewrite=True in config = info."""
        config = _make_config()
        config["components"][0]["config"]["_needs_rewrite"] = True
        report = validate_v2_config(config)
        infos = [i for i in report.issues if i.severity == "info"]
        assert any("rewrite" in i.message.lower() for i in infos)

    def test_review_marker_flagged(self) -> None:
        """Component with _review marker in config = info."""
        config = _make_config()
        config["components"][0]["config"]["_review"] = "check expression"
        report = validate_v2_config(config)
        infos = [i for i in report.issues if i.severity == "info"]
        assert any("review" in i.message.lower() for i in infos)


# ---------------------------------------------------------------------------
# Overall Report
# ---------------------------------------------------------------------------
class TestValidateOverall:
    def test_valid_report(self) -> None:
        """Clean config returns valid=True."""
        report = validate_v2_config(_make_config())
        assert report.valid
        assert isinstance(report.summary, str)

    def test_errors_make_invalid(self) -> None:
        """Errors make valid=False, warnings don't."""
        # Config with only warnings (orphan) should still be valid
        config = _make_config()
        config["components"].append({"id": "orphan", "type": "sort_row", "config": {}})
        report = validate_v2_config(config)
        # orphan is a warning, not an error
        assert report.valid

        # Config with errors should be invalid
        config2 = _make_config(
            flows=[{"name": "row1", "source": "src_1", "target": "missing"}],
        )
        report2 = validate_v2_config(config2)
        assert not report2.valid

    def test_summary_includes_counts(self) -> None:
        """Summary string includes issue counts."""
        config = _make_config(
            flows=[{"name": "row1", "source": "src_1", "target": "missing"}],
        )
        report = validate_v2_config(config)
        assert "error" in report.summary.lower()
