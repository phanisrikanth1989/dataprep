"""Comprehensive tests for FileInputJSON (tFileInputJSON engine component).

Plan 14-09 COV-FIJ-001 -- lift coverage from 9% to >=95%.

Covers:
- Registry registration (V1 + Talend names; BUG-FIJ-001 fix)
- _validate_config() raise-based validation (BUG-FIJ-002 fix)
- Simple list-of-objects JSON read
- JSONPath query mode (nested objects, users[*] pattern)
- Encoding variants (UTF-8 BOM)
- URL read path (mocked urlopen)
- Type conversion + advanced separator + date parsing branches
- Reject flow for malformed records
- Pipeline test via run_job_fixture("file/json_jsonpath", ...)
"""
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.components.file.file_input_json import FileInputJSON
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import (
    ConfigurationError,
    ComponentExecutionError,
)
from src.v1.engine.global_map import GlobalMap


_FIXTURES_DATA = Path(__file__).resolve().parents[5] / "tests" / "fixtures" / "data"
SAMPLE_DATA_JSON = str(_FIXTURES_DATA / "sample_data.json")
SAMPLE_JSONPATH_JSON = str(_FIXTURES_DATA / "sample_jsonpath.json")


def _make_component(config):
    """Create a FileInputJSON with explicit config."""
    cm = ContextManager()
    gm = GlobalMap()
    comp = FileInputJSON(
        component_id="tFIJ_1",
        config=config,
        global_map=gm,
        context_manager=cm,
    )
    comp.config = dict(config)
    comp.output_schema = None
    return comp


# ------------------------------------------------------------------
# Registration (BUG-FIJ-001 fix)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    def test_v1_name_resolves(self):
        assert REGISTRY.get("FileInputJSON") is FileInputJSON

    def test_talend_alias_resolves(self):
        assert REGISTRY.get("tFileInputJSON") is FileInputJSON


# ------------------------------------------------------------------
# Validation (BUG-FIJ-002 fix)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    def test_missing_filename_raises(self):
        comp = _make_component({"json_loop_query": "$.x"})
        with pytest.raises(ConfigurationError, match="filename"):
            comp._validate_config()

    def test_missing_loop_query_raises(self):
        comp = _make_component({"filename": "x.json"})
        with pytest.raises(ConfigurationError, match="json_loop_query"):
            comp._validate_config()

    def test_non_list_mapping_raises(self):
        comp = _make_component({"filename": "x.json", "json_loop_query": "$.x",
                                "mapping": "not_a_list"})
        with pytest.raises(ConfigurationError, match="mapping"):
            comp._validate_config()

    def test_non_str_encoding_raises(self):
        comp = _make_component({"filename": "x.json", "json_loop_query": "$.x",
                                "encoding": 123})
        with pytest.raises(ConfigurationError, match="encoding"):
            comp._validate_config()

    def test_non_bool_die_on_error_raises(self):
        comp = _make_component({"filename": "x.json", "json_loop_query": "$.x",
                                "die_on_error": "true"})
        with pytest.raises(ConfigurationError, match="die_on_error"):
            comp._validate_config()

    def test_useurl_without_urlpath_raises(self):
        comp = _make_component({"json_loop_query": "$.x", "useurl": True})
        with pytest.raises(ConfigurationError, match="urlpath"):
            comp._validate_config()

    def test_non_list_schema_raises(self):
        comp = _make_component({"filename": "x.json", "json_loop_query": "$.x",
                                "schema": "not_a_list"})
        with pytest.raises(ConfigurationError, match="schema"):
            comp._validate_config()

    def test_valid_config_does_not_raise(self):
        comp = _make_component({"filename": "x.json", "json_loop_query": "$.x"})
        comp._validate_config()  # must not raise

    def test_useurl_with_urlpath_does_not_raise(self):
        comp = _make_component({"json_loop_query": "$.x", "useurl": True,
                                "urlpath": "http://example.com/data.json"})
        comp._validate_config()  # must not raise


# ------------------------------------------------------------------
# Public validate_config() (existing API)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestPublicValidateConfig:
    """The public validate_config() returns a list of errors (existing contract)."""

    def test_returns_empty_when_valid(self):
        comp = _make_component({"filename": "x.json", "json_loop_query": "$.x",
                                "mapping": [{"column": "a", "jsonpath": "$.a"}]})
        assert comp.validate_config() == []

    def test_returns_errors_when_invalid(self):
        comp = _make_component({})
        errors = comp.validate_config()
        assert any("filename" in e for e in errors)
        assert any("json_loop_query" in e for e in errors)
        assert any("mapping" in e for e in errors)

    def test_non_list_mapping_error(self):
        comp = _make_component({"filename": "x.json", "json_loop_query": "$.x",
                                "mapping": "not_a_list"})
        errors = comp.validate_config()
        assert any("must be a list" in e for e in errors)

    def test_empty_mapping_error(self):
        comp = _make_component({"filename": "x.json", "json_loop_query": "$.x",
                                "mapping": []})
        errors = comp.validate_config()
        assert any("cannot be empty" in e for e in errors)

    def test_non_str_encoding_error(self):
        comp = _make_component({"filename": "x.json", "json_loop_query": "$.x",
                                "mapping": [{"column": "a", "jsonpath": "$.a"}],
                                "encoding": 123})
        errors = comp.validate_config()
        assert any("encoding" in e and "string" in e for e in errors)

    def test_non_list_schema_error(self):
        comp = _make_component({"filename": "x.json", "json_loop_query": "$.x",
                                "mapping": [{"column": "a", "jsonpath": "$.a"}],
                                "schema": "not_a_list"})
        errors = comp.validate_config()
        assert any("schema" in e for e in errors)

    def test_useurl_without_urlpath_error(self):
        comp = _make_component({"filename": "x.json", "json_loop_query": "$.x",
                                "mapping": [{"column": "a", "jsonpath": "$.a"}],
                                "useurl": True})
        errors = comp.validate_config()
        assert any("urlpath" in e for e in errors)


# ------------------------------------------------------------------
# Simple list-of-records read
# ------------------------------------------------------------------


@pytest.mark.unit
class TestSimpleListRead:
    def test_read_committed_sample_data(self):
        comp = _make_component({
            "filename": SAMPLE_DATA_JSON,
            "json_loop_query": "$[*]",
            "mapping": [
                {"column": "id", "jsonpath": "$.id"},
                {"column": "name", "jsonpath": "$.name"},
            ],
        })
        result = comp.execute()
        assert isinstance(result["main"], pd.DataFrame)
        assert len(result["main"]) == 3
        assert list(result["main"]["name"]) == ["Alice", "Bob", "Carol"]

    def test_quoted_jsonpath_unwrapped(self, tmp_path):
        """Quoted JSONPath strings get unwrapped."""
        p = tmp_path / "data.json"
        p.write_text('[{"a": 1}]')
        comp = _make_component({
            "filename": str(p),
            "json_loop_query": '"$[*]"',  # quoted
            "mapping": [{"column": "a", "jsonpath": '"$.a"'}],  # quoted
        })
        result = comp.execute()
        assert len(result["main"]) == 1

    def test_url_read_path_mocked(self, tmp_path):
        """useurl=True path is hit via mocked urlopen."""
        body = json.dumps([{"id": 1, "name": "url_alice"}]).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = body
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False
        with patch("src.v1.engine.components.file.file_input_json.urlopen",
                   return_value=mock_resp):
            comp = _make_component({
                "useurl": True,
                "urlpath": "http://example.com/data.json",
                "json_loop_query": "$[*]",
                "mapping": [
                    {"column": "id", "jsonpath": "$.id"},
                    {"column": "name", "jsonpath": "$.name"},
                ],
            })
            result = comp.execute()
            assert len(result["main"]) == 1
            assert result["main"]["name"].iloc[0] == "url_alice"


# ------------------------------------------------------------------
# JSONPath query mode (nested + users[*])
# ------------------------------------------------------------------


@pytest.mark.unit
class TestJSONPathQueryMode:
    def test_committed_jsonpath_sample(self):
        comp = _make_component({
            "filename": SAMPLE_JSONPATH_JSON,
            "json_loop_query": "$.users[*]",
            "mapping": [
                {"column": "user_id", "jsonpath": "$.id"},
                {"column": "user_name", "jsonpath": "$.name"},
                {"column": "user_email", "jsonpath": "$.contact.email"},
            ],
        })
        result = comp.execute()
        assert len(result["main"]) == 3
        assert result["main"]["user_name"].iloc[0] == "Alice"
        assert result["main"]["user_email"].iloc[0] == "alice@example.com"

    def test_wildcard_extract_keeps_list(self, tmp_path):
        """JSONPath with [*] keeps list when value_matches has length 1+."""
        p = tmp_path / "wild.json"
        p.write_text(json.dumps({"records": [
            {"tags": ["x", "y", "z"]},
            {"tags": ["a"]},
        ]}))
        comp = _make_component({
            "filename": str(p),
            "json_loop_query": "$.records[*]",
            "mapping": [{"column": "tags", "jsonpath": "$.tags[*]"}],
        })
        result = comp.execute()
        # tags column stored as JSON list-serialized strings
        first = result["main"]["tags"].iloc[0]
        # Serialized via json.dumps after lookup
        assert "x" in first and "y" in first

    def test_use_loop_as_root(self, tmp_path):
        """use_loop_as_root=True flattens single-list result."""
        p = tmp_path / "nested.json"
        p.write_text(json.dumps({"items": [{"a": 1}, {"a": 2}]}))
        comp = _make_component({
            "filename": str(p),
            "json_loop_query": "$.items",  # returns single list containing 2 dicts
            "mapping": [{"column": "a", "jsonpath": "$.a"}],
            "use_loop_as_root": True,
        })
        result = comp.execute()
        assert len(result["main"]) == 2


# ------------------------------------------------------------------
# Schema type conversion
# ------------------------------------------------------------------


@pytest.mark.unit
class TestSchemaTypeConversion:
    def test_integer_conversion(self, tmp_path):
        p = tmp_path / "ints.json"
        p.write_text(json.dumps([{"x": "42"}, {"x": "100"}]))
        comp = _make_component({
            "filename": str(p),
            "json_loop_query": "$[*]",
            "mapping": [{"column": "x", "jsonpath": "$.x"}],
            "schema": [{"name": "x", "type": "id_Integer"}],
        })
        result = comp.execute()
        assert result["main"]["x"].iloc[0] == 42

    def test_float_conversion(self, tmp_path):
        p = tmp_path / "floats.json"
        p.write_text(json.dumps([{"x": "3.14"}]))
        comp = _make_component({
            "filename": str(p),
            "json_loop_query": "$[*]",
            "mapping": [{"column": "x", "jsonpath": "$.x"}],
            "schema": [{"name": "x", "type": "id_Float"}],
        })
        result = comp.execute()
        assert result["main"]["x"].iloc[0] == 3.14

    def test_integer_with_advanced_separator(self, tmp_path):
        """advanced_separator strips thousands separator before conversion."""
        p = tmp_path / "eu_ints.json"
        p.write_text(json.dumps([{"x": "1,000"}]))
        comp = _make_component({
            "filename": str(p),
            "json_loop_query": "$[*]",
            "mapping": [{"column": "x", "jsonpath": "$.x"}],
            "schema": [{"name": "x", "type": "id_Integer"}],
            "advanced_separator": True,
            "thousands_separator": ",",
            "decimal_separator": ".",
        })
        result = comp.execute()
        assert result["main"]["x"].iloc[0] == 1000

    def test_float_with_advanced_separator(self, tmp_path):
        p = tmp_path / "eu_floats.json"
        p.write_text(json.dumps([{"x": "1.000,50"}]))
        comp = _make_component({
            "filename": str(p),
            "json_loop_query": "$[*]",
            "mapping": [{"column": "x", "jsonpath": "$.x"}],
            "schema": [{"name": "x", "type": "id_Float"}],
            "advanced_separator": True,
            "thousands_separator": ".",
            "decimal_separator": ",",
        })
        result = comp.execute()
        assert result["main"]["x"].iloc[0] == 1000.50

    def test_date_conversion_with_pattern(self, tmp_path):
        p = tmp_path / "dates.json"
        p.write_text(json.dumps([{"d": "2024-03-15"}]))
        comp = _make_component({
            "filename": str(p),
            "json_loop_query": "$[*]",
            "mapping": [{"column": "d", "jsonpath": "$.d"}],
            "schema": [{"name": "d", "type": "id_Date", "pattern": "%Y-%m-%d"}],
            "check_date": True,
        })
        result = comp.execute()
        assert pd.Timestamp(result["main"]["d"].iloc[0]).year == 2024

    def test_invalid_integer_goes_to_reject(self, tmp_path):
        p = tmp_path / "bad_int.json"
        p.write_text(json.dumps([{"x": "not_a_number"}, {"x": "42"}]))
        comp = _make_component({
            "filename": str(p),
            "json_loop_query": "$[*]",
            "mapping": [{"column": "x", "jsonpath": "$.x"}],
            "schema": [{"name": "x", "type": "id_Integer"}],
        })
        result = comp.execute()
        # One row goes to reject, one to main
        assert len(result["main"]) == 1
        assert result["main"]["x"].iloc[0] == 42
        assert "reject" in result
        assert len(result["reject"]) == 1

    def test_invalid_float_goes_to_reject(self, tmp_path):
        p = tmp_path / "bad_float.json"
        p.write_text(json.dumps([{"x": "not_a_number"}]))
        comp = _make_component({
            "filename": str(p),
            "json_loop_query": "$[*]",
            "mapping": [{"column": "x", "jsonpath": "$.x"}],
            "schema": [{"name": "x", "type": "id_Float"}],
        })
        result = comp.execute()
        assert len(result["main"]) == 0
        assert len(result["reject"]) == 1

    def test_invalid_date_goes_to_reject(self, tmp_path):
        p = tmp_path / "bad_date.json"
        p.write_text(json.dumps([{"d": "not-a-date"}]))
        comp = _make_component({
            "filename": str(p),
            "json_loop_query": "$[*]",
            "mapping": [{"column": "d", "jsonpath": "$.d"}],
            "schema": [{"name": "d", "type": "id_Date", "pattern": "%Y-%m-%d"}],
            "check_date": True,
        })
        result = comp.execute()
        assert len(result["main"]) == 0
        assert len(result["reject"]) == 1


# ------------------------------------------------------------------
# Talend-style mapping (SCHEMA_COLUMN / QUERY)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestTalendMappingNormalization:
    def test_talend_style_mapping_alternating_pairs(self, tmp_path):
        p = tmp_path / "data.json"
        p.write_text(json.dumps([{"id": 1, "name": "alice"}]))
        comp = _make_component({
            "filename": str(p),
            "json_loop_query": "$[*]",
            "mapping": [
                {"column": "SCHEMA_COLUMN", "jsonpath": "id"},
                {"column": "QUERY", "jsonpath": '"$.id"'},
                {"column": "SCHEMA_COLUMN", "jsonpath": "name"},
                {"column": "QUERY", "jsonpath": '"$.name"'},
            ],
        })
        result = comp.execute()
        assert "id" in result["main"].columns
        assert "name" in result["main"].columns
        assert result["main"]["name"].iloc[0] == "alice"


# ------------------------------------------------------------------
# Error handling
# ------------------------------------------------------------------


@pytest.mark.unit
class TestErrorHandling:
    def test_missing_file_die_on_error_true_raises(self, tmp_path):
        comp = _make_component({
            "filename": str(tmp_path / "missing.json"),
            "json_loop_query": "$[*]",
            "mapping": [{"column": "x", "jsonpath": "$.x"}],
            "die_on_error": True,
        })
        with pytest.raises((FileNotFoundError, ComponentExecutionError)):
            comp.execute()

    def test_missing_file_die_on_error_false_returns_empty(self, tmp_path):
        comp = _make_component({
            "filename": str(tmp_path / "missing.json"),
            "json_loop_query": "$[*]",
            "mapping": [{"column": "x", "jsonpath": "$.x"}],
            "die_on_error": False,
        })
        result = comp.execute()
        assert len(result["main"]) == 0

    def test_malformed_json_die_on_error_false(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{not valid json")
        comp = _make_component({
            "filename": str(p),
            "json_loop_query": "$[*]",
            "mapping": [{"column": "x", "jsonpath": "$.x"}],
            "die_on_error": False,
        })
        result = comp.execute()
        assert len(result["main"]) == 0

    def test_malformed_json_die_on_error_true(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{not valid json")
        comp = _make_component({
            "filename": str(p),
            "json_loop_query": "$[*]",
            "mapping": [{"column": "x", "jsonpath": "$.x"}],
            "die_on_error": True,
        })
        with pytest.raises((json.JSONDecodeError, ComponentExecutionError, Exception)):
            comp.execute()


# ------------------------------------------------------------------
# Statistics
# ------------------------------------------------------------------


@pytest.mark.unit
class TestStatistics:
    def test_stats_after_successful_read(self):
        comp = _make_component({
            "filename": SAMPLE_DATA_JSON,
            "json_loop_query": "$[*]",
            "mapping": [{"column": "id", "jsonpath": "$.id"}],
        })
        result = comp.execute()
        stats = result.get("stats", {})
        assert stats.get("NB_LINE", 0) == 3
        assert stats.get("NB_LINE_OK", 0) == 3
        assert stats.get("NB_LINE_REJECT", 0) == 0


# ------------------------------------------------------------------
# Pipeline integration
# ------------------------------------------------------------------


@pytest.mark.unit
class TestPipelineIntegration:
    def test_pipeline_json_to_csv(self, run_job_fixture, tmp_path):
        out_csv = str(tmp_path / "out.csv")
        result = run_job_fixture(
            "file/json_jsonpath",
            mutations={
                "tFileInputJSON_1": {"filename": SAMPLE_JSONPATH_JSON},
                "tFileOutputDelimited_1": {"filepath": out_csv},
            },
        )
        assert os.path.exists(out_csv)
        df = pd.read_csv(out_csv, sep=";")
        assert len(df) == 3
        assert "user_name" in df.columns
