"""Tests for ExtractJSONFields engine component (tExtractJSONFields).

Test classes:
    TestRegistry        -- @REGISTRY.register, BaseComponent inheritance
    TestValidateConfig  -- _validate_config() structural checks (Rule 12)
    TestProcessEmpty    -- None / empty DataFrame input
    TestProcessJSONPath -- happy-path JSONPATH mode extraction
    TestProcessXPathMode -- read_by=XPATH dispatch
    TestProcessReject   -- reject flow (NO_JSON, PARSE_ERROR, die_on_error)
    TestLoopQuery       -- loop query zero-match Talend parity
    TestUseLoopAsRoot   -- use_loop_as_root=True/False semantics
    TestJsonFieldColumn -- jsonfield column selection
    TestStats           -- NB_LINE / NB_LINE_OK / NB_LINE_REJECT tracking
"""
import json
import math

import pytest
import pandas as pd

from src.v1.engine.components.transform.extract_json_fields import ExtractJSONFields
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ComponentExecutionError, ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Sample data
# ------------------------------------------------------------------

_SIMPLE_JSON = json.dumps({
    "records": [
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25},
    ]
})

_NESTED_JSON = json.dumps({
    "person": {
        "name": "Alice",
        "address": {"city": "London", "zip": "EC1A"},
    }
})

_ARRAY_ROOT_JSON = json.dumps([
    {"name": "Alice", "score": 10},
    {"name": "Bob", "score": 20},
])


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_component(config=None, global_map=None):
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    cfg = config or {}
    comp = ExtractJSONFields(
        component_id="tEJF_1",
        config=cfg,
        global_map=gm,
        context_manager=cm,
    )
    comp.config = dict(cfg)
    return comp


def _set_schema(comp, col_names, col_type="id_String"):
    comp.output_schema = [{"name": c, "type": col_type} for c in col_names]


# ------------------------------------------------------------------
# TestRegistry
# ------------------------------------------------------------------

@pytest.mark.unit
class TestRegistry:
    def test_v1_name_registered(self):
        assert REGISTRY.get("ExtractJSONFields") is ExtractJSONFields

    def test_talend_alias_registered(self):
        assert REGISTRY.get("tExtractJSONFields") is ExtractJSONFields

    def test_inherits_base_component(self):
        from src.v1.engine.base_component import BaseComponent
        assert issubclass(ExtractJSONFields, BaseComponent)


# ------------------------------------------------------------------
# TestValidateConfig
# ------------------------------------------------------------------

@pytest.mark.unit
class TestValidateConfig:
    def test_mapping_not_list_raises(self):
        comp = _make_component(config={"mapping": "not-a-list"})
        with pytest.raises(ConfigurationError, match="mapping"):
            comp._validate_config()

    def test_mapping_4_jsonpath_not_list_raises(self):
        comp = _make_component(config={"mapping_4_jsonpath": 42})
        with pytest.raises(ConfigurationError, match="mapping_4_jsonpath"):
            comp._validate_config()

    def test_die_on_error_not_bool_raises(self):
        comp = _make_component(config={"die_on_error": "yes"})
        with pytest.raises(ConfigurationError, match="die_on_error"):
            comp._validate_config()

    def test_valid_config_passes(self):
        comp = _make_component(config={
            "mapping_4_jsonpath": [],
            "mapping": [],
            "die_on_error": False,
        })
        comp._validate_config()  # must not raise


# ------------------------------------------------------------------
# TestProcessEmpty
# ------------------------------------------------------------------

@pytest.mark.unit
class TestProcessEmpty:
    def test_none_input_returns_empty(self):
        comp = _make_component(config={
            "json_loop_query": "$.records[*]",
            "mapping_4_jsonpath": [],
        })
        result = comp.execute(None)
        assert result["main"].empty

    def test_empty_df_returns_empty(self):
        comp = _make_component(config={
            "json_loop_query": "$.records[*]",
            "mapping_4_jsonpath": [],
        })
        result = comp.execute(pd.DataFrame())
        assert result["main"].empty


# ------------------------------------------------------------------
# TestProcessJSONPath
# ------------------------------------------------------------------

@pytest.mark.unit
class TestProcessJSONPath:
    def test_basic_extraction_multiple_items(self):
        """Loop over array, extract two fields per item."""
        comp = _make_component(config={
            "read_by": "JSONPATH",
            "jsonfield": "json_data",
            "json_loop_query": "$.records[*]",
            "mapping_4_jsonpath": [
                {"schema_column": "name", "query": "$.name"},
                {"schema_column": "age", "query": "$.age"},
            ],
            "die_on_error": False,
        })
        _set_schema(comp, ["name", "age"])
        df = pd.DataFrame([{"json_data": _SIMPLE_JSON}])
        result = comp.execute(df)
        assert len(result["main"]) == 2
        assert result["main"].iloc[0]["name"] == "Alice"
        assert result["main"].iloc[1]["name"] == "Bob"

    def test_nested_path_extraction(self):
        """Deep nested JSONPath query."""
        comp = _make_component(config={
            "read_by": "JSONPATH",
            "jsonfield": "json_data",
            "json_loop_query": "$.person",
            "mapping_4_jsonpath": [
                {"schema_column": "name", "query": "$.name"},
                {"schema_column": "city", "query": "$.address.city"},
                {"schema_column": "zip", "query": "$.address.zip"},
            ],
            "die_on_error": False,
        })
        _set_schema(comp, ["name", "city", "zip"])
        df = pd.DataFrame([{"json_data": _NESTED_JSON}])
        result = comp.execute(df)
        assert len(result["main"]) == 1
        assert result["main"].iloc[0]["name"] == "Alice"
        assert result["main"].iloc[0]["city"] == "London"
        assert result["main"].iloc[0]["zip"] == "EC1A"

    def test_multiple_input_rows(self):
        """Each input row is processed independently."""
        comp = _make_component(config={
            "read_by": "JSONPATH",
            "jsonfield": "json_data",
            "json_loop_query": "$.records[*]",
            "mapping_4_jsonpath": [
                {"schema_column": "name", "query": "$.name"},
            ],
            "die_on_error": False,
        })
        _set_schema(comp, ["name"])
        row1 = json.dumps({"records": [{"name": "Alice"}]})
        row2 = json.dumps({"records": [{"name": "Bob"}, {"name": "Carol"}]})
        df = pd.DataFrame([{"json_data": row1}, {"json_data": row2}])
        result = comp.execute(df)
        # row1 → 1 output, row2 → 2 outputs
        assert len(result["main"]) == 3

    def test_missing_field_returns_empty_string(self):
        """Query that matches nothing produces empty string for that column."""
        comp = _make_component(config={
            "read_by": "JSONPATH",
            "jsonfield": "json_data",
            "json_loop_query": "$.records[*]",
            "mapping_4_jsonpath": [
                {"schema_column": "name", "query": "$.name"},
                {"schema_column": "missing", "query": "$.nonexistent"},
            ],
            "die_on_error": False,
        })
        # No output schema set: skip schema validation so we can inspect the raw
        # empty-string value the component produces for a non-matching path.
        df = pd.DataFrame([{"json_data": json.dumps({"records": [{"name": "Alice"}]})}])
        result = comp._process(df)
        assert result["main"].iloc[0]["missing"] == ""

    def test_passthrough_empty_query_copies_input_column(self):
        """Empty query in mapping_4_jsonpath copies value from input row column."""
        comp = _make_component(config={
            "read_by": "JSONPATH",
            "jsonfield": "json_data",
            "json_loop_query": "$.records[*]",
            "mapping_4_jsonpath": [
                {"schema_column": "row_id", "query": ""},  # passthrough
                {"schema_column": "name", "query": "$.name"},
            ],
            "die_on_error": False,
        })
        _set_schema(comp, ["row_id", "name"])
        doc = json.dumps({"records": [{"name": "Alice"}]})
        df = pd.DataFrame([{"row_id": 99, "json_data": doc}])
        result = comp.execute(df)
        assert len(result["main"]) == 1
        assert result["main"].iloc[0]["row_id"] == 99     # from input row
        assert result["main"].iloc[0]["name"] == "Alice"  # from JSONPath

    def test_array_root_iteration(self):
        """Loop over JSON array root."""
        comp = _make_component(config={
            "read_by": "JSONPATH",
            "jsonfield": "json_data",
            "json_loop_query": "$[*]",
            "mapping_4_jsonpath": [
                {"schema_column": "name", "query": "$.name"},
                {"schema_column": "score", "query": "$.score"},
            ],
            "die_on_error": False,
        })
        _set_schema(comp, ["name", "score"])
        df = pd.DataFrame([{"json_data": _ARRAY_ROOT_JSON}])
        result = comp.execute(df)
        assert len(result["main"]) == 2
        assert result["main"].iloc[0]["score"] == 10
        assert result["main"].iloc[1]["score"] == 20


# ------------------------------------------------------------------
# TestProcessXPathMode
# ------------------------------------------------------------------

@pytest.mark.unit
class TestProcessXPathMode:
    def test_xpath_mode_uses_loop_query_and_mapping(self):
        """read_by=XPATH dispatches to loop_query + mapping."""
        doc = json.dumps({"items": [{"val": "A"}, {"val": "B"}]})
        comp = _make_component(config={
            "read_by": "XPATH",
            "jsonfield": "json_data",
            "loop_query": "$.items[*]",
            "mapping": [
                {"schema_column": "val", "query": "$.val", "nodecheck": False, "isarray": False},
            ],
            "die_on_error": False,
        })
        _set_schema(comp, ["val"])
        df = pd.DataFrame([{"json_data": doc}])
        result = comp.execute(df)
        assert len(result["main"]) == 2
        assert result["main"].iloc[0]["val"] == "A"

    def test_xpath_mode_ignores_mapping_4_jsonpath(self):
        """XPATH mode must not use mapping_4_jsonpath even if it is populated."""
        doc = json.dumps({"records": [{"name": "Alice"}]})
        comp = _make_component(config={
            "read_by": "XPATH",
            "jsonfield": "json_data",
            "loop_query": "$.records[*]",
            "mapping": [
                {"schema_column": "name", "query": "$.name", "nodecheck": False, "isarray": False},
            ],
            "mapping_4_jsonpath": [
                {"schema_column": "SHOULD_NOT_APPEAR", "query": "$.name"},
            ],
            "die_on_error": False,
        })
        _set_schema(comp, ["name"])
        df = pd.DataFrame([{"json_data": doc}])
        result = comp.execute(df)
        assert "SHOULD_NOT_APPEAR" not in result["main"].columns


# ------------------------------------------------------------------
# TestProcessReject
# ------------------------------------------------------------------

@pytest.mark.unit
class TestProcessReject:
    def test_null_json_goes_to_reject(self):
        comp = _make_component(config={
            "read_by": "JSONPATH",
            "jsonfield": "json_data",
            "json_loop_query": "$.records[*]",
            "mapping_4_jsonpath": [],
            "die_on_error": False,
        })
        df = pd.DataFrame([{"json_data": None}])
        result = comp.execute(df)
        assert result["main"].empty
        assert len(result["reject"]) == 1
        assert result["reject"].iloc[0]["errorCode"] == "NO_JSON"

    def test_nan_json_goes_to_reject(self):
        """NaN (pandas representation of missing value) also routes to reject."""
        comp = _make_component(config={
            "read_by": "JSONPATH",
            "jsonfield": "json_data",
            "json_loop_query": "$.records[*]",
            "mapping_4_jsonpath": [],
            "die_on_error": False,
        })
        df = pd.DataFrame([{"json_data": float("nan")}])
        result = comp.execute(df)
        assert result["main"].empty
        assert len(result["reject"]) == 1
        assert result["reject"].iloc[0]["errorCode"] == "NO_JSON"

    def test_malformed_json_goes_to_reject(self):
        comp = _make_component(config={
            "read_by": "JSONPATH",
            "jsonfield": "json_data",
            "json_loop_query": "$.records[*]",
            "mapping_4_jsonpath": [],
            "die_on_error": False,
        })
        df = pd.DataFrame([{"json_data": "{not valid json"}])
        result = comp.execute(df)
        assert result["main"].empty
        assert len(result["reject"]) == 1
        assert result["reject"].iloc[0]["errorCode"] == "PARSE_ERROR"

    def test_die_on_error_true_raises_on_null(self):
        comp = _make_component(config={
            "read_by": "JSONPATH",
            "jsonfield": "json_data",
            "json_loop_query": "$.records[*]",
            "mapping_4_jsonpath": [],
            "die_on_error": True,
        })
        df = pd.DataFrame([{"json_data": None}])
        with pytest.raises((ComponentExecutionError, Exception)):
            comp.execute(df)

    def test_die_on_error_true_raises_on_bad_json(self):
        comp = _make_component(config={
            "read_by": "JSONPATH",
            "jsonfield": "json_data",
            "json_loop_query": "$.records[*]",
            "mapping_4_jsonpath": [],
            "die_on_error": True,
        })
        df = pd.DataFrame([{"json_data": "<<bad>>"}])
        with pytest.raises((ComponentExecutionError, Exception)):
            comp.execute(df)

    def test_reject_row_has_error_columns(self):
        """REJECT row must have errorCode, errorMessage, errorJSONField."""
        comp = _make_component(config={
            "read_by": "JSONPATH",
            "jsonfield": "json_data",
            "json_loop_query": "$.records[*]",
            "mapping_4_jsonpath": [],
            "die_on_error": False,
        })
        df = pd.DataFrame([{"json_data": None}])
        result = comp.execute(df)
        reject_cols = set(result["reject"].columns)
        assert "errorCode" in reject_cols
        assert "errorMessage" in reject_cols


# ------------------------------------------------------------------
# TestLoopQuery
# ------------------------------------------------------------------

@pytest.mark.unit
class TestLoopQuery:
    def test_no_loop_matches_produces_zero_rows(self):
        """Talend parity: when loop query matches nothing, produce 0 output rows."""
        doc = json.dumps({"other": "data"})
        comp = _make_component(config={
            "read_by": "JSONPATH",
            "jsonfield": "json_data",
            "json_loop_query": "$.records[*]",  # path does not exist
            "mapping_4_jsonpath": [{"schema_column": "name", "query": "$.name"}],
            "die_on_error": False,
        })
        _set_schema(comp, ["name"])
        df = pd.DataFrame([{"json_data": doc}])
        result = comp.execute(df)
        assert result["main"].empty, "No loop matches must produce 0 rows (Talend parity)"

    def test_empty_loop_query_processes_full_document(self):
        """Empty loop_query (no iteration) processes the whole document once."""
        doc = json.dumps({"name": "Alice"})
        comp = _make_component(config={
            "read_by": "JSONPATH",
            "jsonfield": "json_data",
            "json_loop_query": "",  # no loop
            "mapping_4_jsonpath": [{"schema_column": "name", "query": "$.name"}],
            "die_on_error": False,
        })
        _set_schema(comp, ["name"])
        df = pd.DataFrame([{"json_data": doc}])
        result = comp.execute(df)
        assert len(result["main"]) == 1
        assert result["main"].iloc[0]["name"] == "Alice"


# ------------------------------------------------------------------
# TestUseLoopAsRoot
# ------------------------------------------------------------------

@pytest.mark.unit
class TestUseLoopAsRoot:
    def test_use_loop_as_root_true_queries_loop_item(self):
        """use_loop_as_root=True: mapping queries run against each loop item."""
        doc = json.dumps({"records": [{"name": "Alice"}, {"name": "Bob"}]})
        comp = _make_component(config={
            "read_by": "JSONPATH",
            "jsonfield": "json_data",
            "json_loop_query": "$.records[*]",
            "mapping_4_jsonpath": [{"schema_column": "name", "query": "$.name"}],
            "use_loop_as_root": True,
            "die_on_error": False,
        })
        _set_schema(comp, ["name"])
        df = pd.DataFrame([{"json_data": doc}])
        result = comp.execute(df)
        assert len(result["main"]) == 2
        assert result["main"].iloc[0]["name"] == "Alice"

    def test_use_loop_as_root_false_queries_full_doc(self):
        """use_loop_as_root=False: mapping queries run against the full document."""
        doc = json.dumps({
            "meta": {"source": "test"},
            "records": [{"name": "Alice"}, {"name": "Bob"}],
        })
        comp = _make_component(config={
            "read_by": "JSONPATH",
            "jsonfield": "json_data",
            "json_loop_query": "$.records[*]",
            "mapping_4_jsonpath": [{"schema_column": "source", "query": "$.meta.source"}],
            "use_loop_as_root": False,
            "die_on_error": False,
        })
        _set_schema(comp, ["source"])
        df = pd.DataFrame([{"json_data": doc}])
        result = comp.execute(df)
        # 2 loop items, each querying full doc → "test" repeated twice
        assert len(result["main"]) == 2
        assert result["main"].iloc[0]["source"] == "test"
        assert result["main"].iloc[1]["source"] == "test"


# ------------------------------------------------------------------
# TestJsonFieldColumn
# ------------------------------------------------------------------

@pytest.mark.unit
class TestJsonFieldColumn:
    def test_jsonfield_selects_named_column(self):
        """jsonfield config picks the correct source column."""
        comp = _make_component(config={
            "read_by": "JSONPATH",
            "jsonfield": "payload",
            "json_loop_query": "$[*]",
            "mapping_4_jsonpath": [{"schema_column": "val", "query": "$.val"}],
            "die_on_error": False,
        })
        _set_schema(comp, ["val"])
        doc = json.dumps([{"val": 42}])
        df = pd.DataFrame([{"payload": doc, "other_col": "ignore"}])
        result = comp.execute(df)
        assert len(result["main"]) == 1
        assert result["main"].iloc[0]["val"] == 42

    def test_jsonfield_missing_falls_back_to_first_column(self):
        """When jsonfield names a column not in the DataFrame, fall back to first column."""
        comp = _make_component(config={
            "read_by": "JSONPATH",
            "jsonfield": "nonexistent_col",
            "json_loop_query": "$[*]",
            "mapping_4_jsonpath": [{"schema_column": "val", "query": "$.val"}],
            "die_on_error": False,
        })
        _set_schema(comp, ["val"])
        doc = json.dumps([{"val": 7}])
        df = pd.DataFrame([{"actual_first_col": doc}])
        result = comp.execute(df)
        assert len(result["main"]) == 1
        assert result["main"].iloc[0]["val"] == 7

    def test_jsonfield_empty_falls_back_to_first_column(self):
        """When jsonfield is empty string, fall back to first column."""
        comp = _make_component(config={
            "read_by": "JSONPATH",
            "jsonfield": "",
            "json_loop_query": "$[*]",
            "mapping_4_jsonpath": [{"schema_column": "val", "query": "$.val"}],
            "die_on_error": False,
        })
        _set_schema(comp, ["val"])
        doc = json.dumps([{"val": 5}])
        df = pd.DataFrame([{"first_col": doc, "second_col": "other"}])
        result = comp.execute(df)
        assert len(result["main"]) == 1


# ------------------------------------------------------------------
# TestStats
# ------------------------------------------------------------------

@pytest.mark.unit
class TestStats:
    def test_stats_updated_after_execution(self):
        gm = GlobalMap()
        comp = _make_component(config={
            "read_by": "JSONPATH",
            "jsonfield": "json_data",
            "json_loop_query": "$.records[*]",
            "mapping_4_jsonpath": [{"schema_column": "name", "query": "$.name"}],
            "die_on_error": False,
        }, global_map=gm)
        _set_schema(comp, ["name"])
        df = pd.DataFrame([{"json_data": _SIMPLE_JSON}])
        comp.execute(df)
        assert gm.get_nb_line(comp.id) >= 1

    def test_stats_zero_on_empty_input(self):
        gm = GlobalMap()
        comp = _make_component(config={
            "read_by": "JSONPATH",
            "json_loop_query": "$.records[*]",
            "mapping_4_jsonpath": [],
        }, global_map=gm)
        comp.execute(None)
        assert gm.get_nb_line(comp.id) == 0
