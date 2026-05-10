"""Tests for ParseRecordSet engine component (tParseRecordSet).

Test classes:
    TestRegistration         -- registry decorator, BaseComponent inheritance
    TestValidation           -- _validate_config structural checks (Rule 12)
    TestEmptyInput           -- empty DataFrame returns empty without error
    TestDictExpansion        -- single-dict recordset column expands to 1 row
    TestListOfDictsExpansion -- list-of-dicts column expands to N rows
    TestAttributeTable       -- attribute_table controls which keys are extracted
    TestMissingKeys          -- dict missing a key produces pd.NA in that column
    TestNullRecordset        -- null/None recordset entries are skipped
    TestJsonStringParsing    -- JSON string in column is parsed
    TestMissingColumn        -- recordset_field not in DataFrame raises
    TestNoAttributeTable     -- empty attribute_table extracts all keys
    TestStatistics           -- NB_LINE / NB_LINE_OK match output row count
"""
import json

import pytest
import pandas as pd

from src.v1.engine.components.transform.parse_record_set import ParseRecordSet
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError, ComponentExecutionError, DataValidationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_component(config=None, global_map=None):
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    cfg = config or {}
    comp = ParseRecordSet(
        component_id="tParseRecordSet_1",
        config=cfg,
        global_map=gm,
        context_manager=cm,
    )
    comp.config = dict(cfg)
    return comp


def _df(*rows, columns):
    return pd.DataFrame(rows, columns=columns)


# ------------------------------------------------------------------
# TestRegistration
# ------------------------------------------------------------------

@pytest.mark.unit
class TestRegistration:
    """Registry decorator, BaseComponent inheritance."""

    def test_v1_name_registered(self):
        assert REGISTRY.get("ParseRecordSet") is ParseRecordSet

    def test_talend_alias_registered(self):
        assert REGISTRY.get("tParseRecordSet") is ParseRecordSet

    def test_inherits_base_component(self):
        from src.v1.engine.base_component import BaseComponent
        assert issubclass(ParseRecordSet, BaseComponent)


# ------------------------------------------------------------------
# TestValidation
# ------------------------------------------------------------------

@pytest.mark.unit
class TestValidation:
    """_validate_config() -- structural checks, raises ConfigurationError."""

    def test_missing_recordset_field_raises(self):
        comp = _make_component({"attribute_table": ["a"]})
        with pytest.raises(ConfigurationError, match="recordset_field"):
            comp._validate_config()

    def test_empty_recordset_field_raises(self):
        comp = _make_component({"recordset_field": "", "attribute_table": []})
        with pytest.raises(ConfigurationError, match="recordset_field"):
            comp._validate_config()

    def test_attribute_table_not_list_raises(self):
        comp = _make_component({"recordset_field": "rs", "attribute_table": "bad"})
        with pytest.raises(ConfigurationError, match="attribute_table"):
            comp._validate_config()

    def test_valid_config_does_not_raise(self):
        comp = _make_component({"recordset_field": "rs", "attribute_table": ["a", "b"]})
        comp._validate_config()  # must not raise


# ------------------------------------------------------------------
# TestEmptyInput
# ------------------------------------------------------------------

@pytest.mark.unit
class TestEmptyInput:
    """Empty DataFrame returns empty without error."""

    def test_empty_df_returns_empty(self):
        comp = _make_component({"recordset_field": "rs", "attribute_table": []})
        result = comp.execute(pd.DataFrame())
        assert isinstance(result["main"], pd.DataFrame)

    def test_none_input_returns_empty(self):
        comp = _make_component({"recordset_field": "rs"})
        result = comp.execute(None)
        assert isinstance(result["main"], pd.DataFrame)


# ------------------------------------------------------------------
# TestDictExpansion
# ------------------------------------------------------------------

@pytest.mark.unit
class TestDictExpansion:
    """Single-dict recordset column expands to one output row."""

    def test_dict_produces_one_row(self):
        df = pd.DataFrame([{"rs": {"name": "Alice", "age": 30}}])
        comp = _make_component({
            "recordset_field": "rs",
            "attribute_table": ["name", "age"],
        })
        result = comp.execute(df)
        assert len(result["main"]) == 1
        assert result["main"].iloc[0]["name"] == "Alice"
        assert result["main"].iloc[0]["age"] == 30

    def test_returns_only_requested_attributes(self):
        df = pd.DataFrame([{"rs": {"a": 1, "b": 2, "c": 3}}])
        comp = _make_component({
            "recordset_field": "rs",
            "attribute_table": ["a", "c"],
        })
        result = comp.execute(df)
        assert list(result["main"].columns) == ["a", "c"]
        assert "b" not in result["main"].columns


# ------------------------------------------------------------------
# TestListOfDictsExpansion
# ------------------------------------------------------------------

@pytest.mark.unit
class TestListOfDictsExpansion:
    """List-of-dicts column expands to N output rows."""

    def test_list_of_two_dicts_gives_two_rows(self):
        df = pd.DataFrame([{
            "rs": [{"x": 1}, {"x": 2}]
        }])
        comp = _make_component({
            "recordset_field": "rs",
            "attribute_table": ["x"],
        })
        result = comp.execute(df)
        assert len(result["main"]) == 2

    def test_multiple_input_rows_each_expanded(self):
        df = pd.DataFrame([
            {"rs": [{"v": "a"}, {"v": "b"}]},
            {"rs": [{"v": "c"}]},
        ])
        comp = _make_component({"recordset_field": "rs", "attribute_table": ["v"]})
        result = comp.execute(df)
        assert len(result["main"]) == 3
        assert list(result["main"]["v"]) == ["a", "b", "c"]


# ------------------------------------------------------------------
# TestAttributeTable
# ------------------------------------------------------------------

@pytest.mark.unit
class TestAttributeTable:
    """attribute_table controls which attributes are extracted and in what order."""

    def test_order_follows_attribute_table(self):
        df = pd.DataFrame([{"rs": {"z": 3, "a": 1, "m": 2}}])
        comp = _make_component({
            "recordset_field": "rs",
            "attribute_table": ["a", "m", "z"],
        })
        result = comp.execute(df)
        assert list(result["main"].columns) == ["a", "m", "z"]


# ------------------------------------------------------------------
# TestMissingKeys
# ------------------------------------------------------------------

@pytest.mark.unit
class TestMissingKeys:
    """Dict missing an attribute_table key produces pd.NA."""

    def test_missing_key_is_na(self):
        df = pd.DataFrame([{"rs": {"a": 1}}])  # "b" is missing
        comp = _make_component({
            "recordset_field": "rs",
            "attribute_table": ["a", "b"],
        })
        result = comp.execute(df)
        assert result["main"].iloc[0]["a"] == 1
        assert pd.isna(result["main"].iloc[0]["b"])


# ------------------------------------------------------------------
# TestNullRecordset
# ------------------------------------------------------------------

@pytest.mark.unit
class TestNullRecordset:
    """Null/None recordset entries are silently skipped."""

    def test_null_entry_skipped(self):
        df = pd.DataFrame([{"rs": None}, {"rs": {"v": 42}}])
        comp = _make_component({"recordset_field": "rs", "attribute_table": ["v"]})
        result = comp.execute(df)
        assert len(result["main"]) == 1
        assert result["main"].iloc[0]["v"] == 42

    def test_all_null_returns_empty(self):
        df = pd.DataFrame([{"rs": None}, {"rs": None}])
        comp = _make_component({"recordset_field": "rs", "attribute_table": ["v"]})
        result = comp.execute(df)
        assert result["main"].empty


# ------------------------------------------------------------------
# TestJsonStringParsing
# ------------------------------------------------------------------

@pytest.mark.unit
class TestJsonStringParsing:
    """JSON string in column is parsed into dict."""

    def test_json_string_expanded(self):
        df = pd.DataFrame([{"rs": json.dumps({"k": "val"})}])
        comp = _make_component({"recordset_field": "rs", "attribute_table": ["k"]})
        result = comp.execute(df)
        assert result["main"].iloc[0]["k"] == "val"

    def test_json_array_string_expanded(self):
        df = pd.DataFrame([{"rs": json.dumps([{"n": 1}, {"n": 2}])}])
        comp = _make_component({"recordset_field": "rs", "attribute_table": ["n"]})
        result = comp.execute(df)
        assert len(result["main"]) == 2


# ------------------------------------------------------------------
# TestMissingColumn
# ------------------------------------------------------------------

@pytest.mark.unit
class TestMissingColumn:
    """recordset_field column not in DataFrame raises DataValidationError."""

    def test_missing_column_raises(self):
        df = pd.DataFrame([{"other_col": 1}])
        comp = _make_component({"recordset_field": "rs", "attribute_table": ["a"]})
        with pytest.raises((ComponentExecutionError, DataValidationError), match="rs"):
            comp.execute(df)


# ------------------------------------------------------------------
# TestNoAttributeTable
# ------------------------------------------------------------------

@pytest.mark.unit
class TestNoAttributeTable:
    """Empty attribute_table extracts all keys from the dict."""

    def test_all_keys_extracted_when_no_attribute_table(self):
        df = pd.DataFrame([{"rs": {"x": 10, "y": 20}}])
        comp = _make_component({"recordset_field": "rs", "attribute_table": []})
        result = comp.execute(df)
        assert "x" in result["main"].columns
        assert "y" in result["main"].columns


# ------------------------------------------------------------------
# TestStatistics
# ------------------------------------------------------------------

@pytest.mark.unit
class TestStatistics:
    """NB_LINE / NB_LINE_OK match the number of output rows produced."""

    def test_nb_line_equals_output_rows(self):
        df = pd.DataFrame([{"rs": [{"v": 1}, {"v": 2}]}])
        gm = GlobalMap()
        comp = _make_component({"recordset_field": "rs", "attribute_table": ["v"]}, global_map=gm)
        comp.execute(df)
        assert gm.get("tParseRecordSet_1_NB_LINE") == 2
        assert gm.get("tParseRecordSet_1_NB_LINE_OK") == 2
        assert gm.get("tParseRecordSet_1_NB_LINE_REJECT") == 0


# ------------------------------------------------------------------
# TestCoverageLift_14_05 (COV-PRS-001)
#
# Target missed lines from Phase 14 baseline:
#   - 127-133 (JSON parse failure -> skip row, log warning)
#   - 137-142 (record entry is not a dict -> skip, log warning)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestCoverageLift1405:
    """Targeted coverage for residual missed branches in parse_record_set.py."""

    def test_unparseable_string_cell_is_skipped(self, caplog):
        # Hits lines 127-133. Non-dict, non-list cell that cannot be
        # JSON-parsed. The row is skipped and a warning is logged.
        df = pd.DataFrame([
            {"rs": "this is not json", "id": 1},
            {"rs": [{"v": 99}], "id": 2},  # one valid row
        ])
        comp = _make_component({"recordset_field": "rs", "attribute_table": ["v"]})
        with caplog.at_level("WARNING"):
            result = comp.execute(df)
        # Only the valid row produces output.
        assert len(result["main"]) == 1
        assert int(result["main"].iloc[0]["v"]) == 99
        # Warning emitted for the unparseable cell.
        assert any("Cannot parse recordset value" in rec.message for rec in caplog.records)

    def test_non_dict_record_entry_is_skipped(self, caplog):
        # Hits lines 137-142. Cell is a list with non-dict entries mixed in.
        df = pd.DataFrame([
            {"rs": [{"v": 1}, "not a dict", {"v": 2}, 42], "id": 1},
        ])
        comp = _make_component({"recordset_field": "rs", "attribute_table": ["v"]})
        with caplog.at_level("WARNING"):
            result = comp.execute(df)
        # Only the two valid dict entries become output rows.
        assert len(result["main"]) == 2
        assert sorted(int(v) for v in result["main"]["v"].tolist()) == [1, 2]
        # Warning logged for each non-dict entry.
        non_dict_warnings = [
            rec for rec in caplog.records
            if "Record entry is not a dict" in rec.message
        ]
        assert len(non_dict_warnings) >= 2
