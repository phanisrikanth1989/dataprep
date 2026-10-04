"""Tests for V1-to-V2 component type mapping."""
import pytest
from src.converters.v1_to_v2.component_mapper import (
    map_component,
    _map_aggregate_row,
)


class TestFileInputDelimited:
    def test_basic(self):
        v1 = {
            "id": "read",
            "type": "tFileInputDelimited",
            "config": {
                "filepath": "/data/orders.csv",
                "delimiter": ",",
                "encoding": "UTF-8",
                "header_rows": 1,
                "die_on_error": True,
            },
            "schema": {
                "output": [
                    {"name": "id", "type": "id_Integer"},
                    {"name": "name", "type": "id_String"},
                ]
            },
        }
        result = map_component(v1)
        assert result.component["id"] == "read"
        assert result.component["type"] == "file_input_delimited"
        assert result.component["config"]["path"] == "/data/orders.csv"
        assert result.component["config"]["delimiter"] == ","
        assert result.component["config"]["has_header"] is True
        assert result.component["config"]["schema"] == [
            {"name": "id", "type": "integer"},
            {"name": "name", "type": "string"},
        ]
        assert not result.warnings

    def test_date_schema_with_pattern(self):
        v1 = {
            "id": "read",
            "type": "tFileInputDelimited",
            "config": {"filepath": "/data/f.csv"},
            "schema": {
                "output": [
                    {"name": "d", "type": "id_Date", "date_pattern": "yyyy-MM-dd"},
                ]
            },
        }
        result = map_component(v1)
        schema = result.component["config"]["schema"]
        assert schema[0]["type"] == "date"
        assert schema[0]["date_pattern"] == "%Y-%m-%d"

    def test_header_rows_0_means_no_header(self):
        v1 = {
            "id": "r",
            "type": "tFileInputDelimited",
            "config": {"filepath": "f.csv", "header_rows": 0},
        }
        result = map_component(v1)
        assert result.component["config"]["has_header"] is False

    def test_text_enclosure_maps_to_quote_char(self):
        v1 = {
            "id": "read",
            "type": "tFileInputDelimited",
            "config": {
                "filepath": "/data/orders.csv",
                "text_enclosure": "'",
            },
            "schema": {"output": [{"name": "a", "type": "id_String"}]},
        }
        result = map_component(v1)
        assert result.component["config"]["quote_char"] == "'"

    def test_footer_limit_skip_empty_trim(self):
        v1 = {
            "id": "read",
            "type": "tFileInputDelimited",
            "config": {
                "filepath": "/data/orders.csv",
                "footer_rows": 2,
                "limit": 100,
                "remove_empty_rows": True,
                "trim_all": True,
            },
            "schema": {"output": [{"name": "a", "type": "id_String"}]},
        }
        result = map_component(v1)
        cfg = result.component["config"]
        assert cfg["footer_rows"] == 2
        assert cfg["limit"] == 100
        assert cfg["skip_empty_rows"] is True
        assert cfg["trim_all"] is True

    def test_escape_char_differs_from_enclosure_warns(self):
        v1 = {
            "id": "read",
            "type": "tFileInputDelimited",
            "config": {
                "filepath": "/data/orders.csv",
                "text_enclosure": '"',
                "escape_char": "\\",
            },
            "schema": {"output": [{"name": "a", "type": "id_String"}]},
        }
        result = map_component(v1)
        assert result.component["config"]["quote_char"] == '"'
        assert any("escape_char" in w for w in result.warnings)


class TestFileOutputDelimited:
    def test_basic(self):
        v1 = {
            "id": "write",
            "type": "tFileOutputDelimited",
            "config": {
                "filepath": "/out/result.csv",
                "delimiter": ";",
                "include_header": True,
            },
        }
        result = map_component(v1)
        assert result.component["type"] == "file_output_delimited"
        assert result.component["config"]["path"] == "/out/result.csv"
        assert result.component["config"]["delimiter"] == ";"
        assert result.component["config"]["has_header"] is True

    def test_include_header_false(self):
        v1 = {
            "id": "w",
            "type": "tFileOutputDelimited",
            "config": {"filepath": "f.csv", "include_header": False},
        }
        result = map_component(v1)
        assert result.component["config"]["has_header"] is False

    def test_row_separator_maps_to_line_terminator(self):
        v1 = {
            "id": "w",
            "type": "tFileOutputDelimited",
            "config": {"filepath": "f.csv", "row_separator": "\r\n"},
        }
        result = map_component(v1)
        assert result.component["config"]["line_terminator"] == "\r\n"

    def test_text_enclosure_maps_to_quote_char(self):
        v1 = {
            "id": "w",
            "type": "tFileOutputDelimited",
            "config": {"filepath": "f.csv", "text_enclosure": "'"},
        }
        result = map_component(v1)
        assert result.component["config"]["quote_char"] == "'"

    def test_csv_option_maps_to_quote_style_always(self):
        v1 = {
            "id": "w",
            "type": "tFileOutputDelimited",
            "config": {"filepath": "f.csv", "csv_option": True},
        }
        result = map_component(v1)
        assert result.component["config"]["quote_style"] == "always"

    def test_delete_empty_file_passthrough(self):
        v1 = {
            "id": "w",
            "type": "tFileOutputDelimited",
            "config": {"filepath": "f.csv", "delete_empty_file": True},
        }
        result = map_component(v1)
        assert result.component["config"]["delete_empty_file"] is True

    def test_unsupported_keys_warn(self):
        v1 = {
            "id": "w",
            "type": "tFileOutputDelimited",
            "config": {
                "filepath": "f.csv",
                "encoding": "ISO-8859-15",
                "split": True,
                "split_every": 1000,
            },
        }
        result = map_component(v1)
        assert len(result.warnings) == 3
        warning_text = " ".join(result.warnings)
        assert "encoding" in warning_text
        assert "split" in warning_text
        assert "split_every" in warning_text


class TestFileInputExcel:
    def test_basic(self):
        v1 = {
            "id": "read_xl",
            "type": "tFileInputExcel",
            "config": {"filepath": "/data/book.xlsx", "sheet_name": "Sheet1"},
        }
        result = map_component(v1)
        assert result.component["type"] == "file_input_excel"
        assert result.component["config"]["path"] == "/data/book.xlsx"
        assert result.component["config"]["sheet"] == "Sheet1"

    def test_multi_sheet_mapping(self):
        """V1 all_sheets should map to V2 config."""
        v1 = {
            "id": "read_xl",
            "type": "tFileInputExcel",
            "config": {
                "filepath": "/data/book.xlsx",
                "all_sheets": True,
            },
        }
        result = map_component(v1)
        assert result.component["config"]["all_sheets"] is True

    def test_sheet_list_mapping(self):
        """V1 sheetlist should map to V2 sheets list."""
        v1 = {
            "id": "read_xl",
            "type": "tFileInputExcel",
            "config": {
                "filepath": "/data/book.xlsx",
                "sheetlist": [
                    {"sheetname": "Sales", "use_regex": False},
                    {"sheetname": "Data_.*", "use_regex": True},
                ],
            },
        }
        result = map_component(v1)
        sheets = result.component["config"]["sheets"]
        assert len(sheets) == 2
        assert sheets[0] == {"name": "Sales"}
        assert sheets[1] == {"name": "Data_.*", "regex": True}

    def test_footer_limit_column_range(self):
        """V1 footer, limit, first/last column should map."""
        v1 = {
            "id": "read_xl",
            "type": "tFileInputExcel",
            "config": {
                "filepath": "/data/book.xlsx",
                "footer": 3,
                "limit": 100,
                "first_column": 2,
                "last_column": 5,
            },
        }
        result = map_component(v1)
        cfg = result.component["config"]
        assert cfg["footer_rows"] == 3
        assert cfg["limit"] == 100
        assert cfg["first_column"] == 2
        assert cfg["last_column"] == 5

    def test_trim_and_skip_empty(self):
        """V1 trimall and stopread_on_emptyrow should map."""
        v1 = {
            "id": "read_xl",
            "type": "tFileInputExcel",
            "config": {
                "filepath": "/data/book.xlsx",
                "trimall": True,
                "stopread_on_emptyrow": True,
            },
        }
        result = map_component(v1)
        cfg = result.component["config"]
        assert cfg["trim_all"] is True
        assert cfg["skip_empty_rows"] is True

    def test_unsupported_features_warn(self):
        """Unsupported V1 features should produce warnings."""
        v1 = {
            "id": "read_xl",
            "type": "tFileInputExcel",
            "config": {
                "filepath": "/data/book.xlsx",
                "password": "secret",
                "generation_mode": "EVENT_MODE",
                "advanced_separator": True,
            },
        }
        result = map_component(v1)
        assert len(result.warnings) == 3


class TestFilterRows:
    def test_simple_condition(self):
        v1 = {
            "id": "filt",
            "type": "tFilterRows",
            "config": {
                "conditions": [
                    {"column": "amount", "operator": ">=", "value": 100}
                ],
                "logical_operator": "AND",
            },
        }
        result = map_component(v1)
        assert result.component["type"] == "filter"
        assert result.component["config"]["condition"] == "amount >= 100"

    def test_multiple_conditions_and(self):
        v1 = {
            "id": "filt",
            "type": "tFilterRows",
            "config": {
                "conditions": [
                    {"column": "status", "operator": "==", "value": "ACTIVE"},
                    {"column": "amount", "operator": ">", "value": 0},
                ],
                "logical_operator": "AND",
            },
        }
        result = map_component(v1)
        assert result.component["config"]["condition"] == "status == 'ACTIVE' AND amount > 0"

    def test_multiple_conditions_or(self):
        v1 = {
            "id": "filt",
            "type": "tFilterRows",
            "config": {
                "conditions": [
                    {"column": "tier", "operator": "==", "value": "GOLD"},
                    {"column": "tier", "operator": "==", "value": "PLATINUM"},
                ],
                "logical_operator": "OR",
            },
        }
        result = map_component(v1)
        assert result.component["config"]["condition"] == "tier == 'GOLD' OR tier == 'PLATINUM'"

    def test_null_check(self):
        v1 = {
            "id": "filt",
            "type": "tFilterRows",
            "config": {
                "conditions": [
                    {"column": "email", "operator": "is_not_null"}
                ],
            },
        }
        result = map_component(v1)
        assert result.component["config"]["condition"] == "email != null"

    def test_reject_output(self):
        """tFilterRows always has a reject, so V2 gets reject_output=true."""
        v1 = {
            "id": "filt",
            "type": "tFilterRows",
            "config": {
                "conditions": [{"column": "x", "operator": ">", "value": 0}],
            },
        }
        result = map_component(v1)
        assert result.component["config"].get("reject_output") is True


class TestSortRow:
    def test_ascending(self):
        v1 = {
            "id": "sort",
            "type": "tSortRow",
            "config": {
                "sort_keys": [
                    {"column": "amount", "ascending": True},
                    {"column": "name", "ascending": False},
                ]
            },
        }
        result = map_component(v1)
        assert result.component["type"] == "sort_row"
        cols = result.component["config"]["columns"]
        assert cols[0] == {"name": "amount", "order": "asc"}
        assert cols[1] == {"name": "name", "order": "desc"}


class TestAggregateRow:
    def test_basic(self):
        v1 = {
            "id": "agg",
            "type": "tAggregateRow",
            "config": {
                "group_by": ["region"],
                "operations": [
                    {"input_column": "amount", "output_column": "total", "function": "sum"},
                    {"input_column": "id", "output_column": "cnt", "function": "count"},
                ],
            },
        }
        result = map_component(v1)
        assert result.component["type"] == "aggregate"
        assert result.component["config"]["group_by"] == ["region"]
        aggs = result.component["config"]["aggregations"]
        assert aggs[0] == {"name": "total", "column": "amount", "function": "sum"}
        assert aggs[1] == {"name": "cnt", "column": "id", "function": "count"}

    def test_map_aggregate_row_with_ignore_null(self):
        """Test that ignore_null from V1 maps to ignore_nulls in V2."""
        v1 = {
            "id": "agg1",
            "type": "tAggregateRow",
            "config": {
                "group_by": ["dept"],
                "operations": [
                    {"input_column": "salary", "output_column": "total_salary", "function": "sum", "ignore_null": True},
                    {"input_column": "name", "output_column": "first_name", "function": "first", "ignore_null": False},
                ],
            },
        }
        result = _map_aggregate_row(v1)
        aggs = result.component["config"]["aggregations"]
        assert aggs[0]["ignore_nulls"] is True
        assert aggs[1]["ignore_nulls"] is False


class TestUniqueRow:
    def test_basic(self):
        v1 = {
            "id": "dedup",
            "type": "tUniqueRow",
            "config": {"distinct_key": ["email"], "duplicate_action": "first"},
        }
        result = map_component(v1)
        assert result.component["type"] == "unique"
        assert result.component["config"]["columns"] == ["email"]
        assert result.component["config"]["keep"] == "first"


class TestFilterColumns:
    def test_basic(self):
        v1 = {
            "id": "sel",
            "type": "tFilterColumns",
            "config": {"columns": ["id", "name", "email"]},
        }
        result = map_component(v1)
        assert result.component["type"] == "select"
        assert result.component["config"]["columns"] == ["id", "name", "email"]


class TestPythonComponents:
    def test_python_row(self):
        v1 = {
            "id": "py",
            "type": "tPythonRow",
            "config": {"python_code": "output_row['x'] = input_row['a'] + 1"},
        }
        result = map_component(v1)
        assert result.component["type"] == "python_row"
        assert result.component["config"]["code"] == "output_row['x'] = input_row['a'] + 1"

    def test_python_dataframe(self):
        v1 = {
            "id": "pydf",
            "type": "tPythonDataFrame",
            "config": {"python_code": "output_df = input_df"},
        }
        result = map_component(v1)
        assert result.component["type"] == "python_dataframe"
        assert result.component["config"]["code"] == "output_df = input_df"

    def test_python_code(self):
        v1 = {
            "id": "pyc",
            "type": "tPython",
            "config": {"python_code": "print('hello')"},
        }
        result = map_component(v1)
        assert result.component["type"] == "python_code"
        assert result.component["config"]["code"] == "print('hello')"


class TestUnion:
    def test_basic(self):
        v1 = {"id": "u", "type": "tUnite", "config": {}}
        result = map_component(v1)
        assert result.component["type"] == "unite"


class TestMapComponent:
    def test_simple_columns(self):
        v1 = {
            "id": "m",
            "type": "tMap",
            "config": {
                "outputs": [
                    {
                        "name": "main",
                        "columns": [
                            {"name": "order_id", "expression": "main.order_id"},
                            {"name": "total", "expression": "main.qty * main.price"},
                        ],
                    }
                ],
            },
        }
        result = map_component(v1)
        assert result.component["type"] == "map"
        outputs = result.component["config"]["outputs"]
        assert outputs[0]["columns"][0]["expression"] == "order_id"
        assert outputs[0]["columns"][1]["expression"] == "qty * price"

    def test_lookup(self):
        v1 = {
            "id": "m",
            "type": "tMap",
            "config": {
                "inputs": {
                    "main": {"name": "main_input"},
                    "lookups": [
                        {
                            "name": "cust",
                            "join_keys": [
                                {"main_column": "customer_id", "lookup_column": "id"}
                            ],
                            "join_type": "LEFT",
                        }
                    ],
                },
                "outputs": [
                    {
                        "name": "main",
                        "columns": [
                            {"name": "order_id", "expression": "main.order_id"},
                            {"name": "cust_name", "expression": "cust.name"},
                        ],
                    }
                ],
            },
        }
        result = map_component(v1)
        lookups = result.component["config"]["lookups"]
        assert len(lookups) == 1
        assert lookups[0]["name"] == "cust"
        assert lookups[0]["keys"] == [{"main": "customer_id", "lookup": "id"}]
        assert lookups[0]["join_type"] == "left"

    def test_java_expression_flagged(self):
        v1 = {
            "id": "m",
            "type": "tMap",
            "config": {
                "outputs": [
                    {
                        "name": "main",
                        "columns": [
                            {
                                "name": "full",
                                "expression": "{{java}} row.get('first') + ' ' + row.get('last')",
                            }
                        ],
                    }
                ],
            },
        }
        result = map_component(v1)
        col = result.component["config"]["outputs"][0]["columns"][0]
        assert col.get("_review") is True
        assert len(result.expressions_needing_review) == 1

    def test_variables(self):
        v1 = {
            "id": "m",
            "type": "tMap",
            "config": {
                "variables": [
                    {"name": "subtotal", "expression": "main.qty * main.price"}
                ],
                "outputs": [
                    {
                        "name": "main",
                        "columns": [
                            {"name": "subtotal", "expression": "var.subtotal"},
                        ],
                    }
                ],
            },
        }
        result = map_component(v1)
        variables = result.component["config"]["variables"]
        assert variables[0]["expression"] == "qty * price"
        # Verify var. prefix is preserved in output column expressions
        cols = result.component["config"]["outputs"][0]["columns"]
        assert cols[0]["expression"] == "var.subtotal"

    def test_output_filter(self):
        v1 = {
            "id": "m",
            "type": "tMap",
            "config": {
                "outputs": [
                    {
                        "name": "main",
                        "activate_filter": True,
                        "filter": "main.amount > 0",
                        "columns": [
                            {"name": "amount", "expression": "main.amount"},
                        ],
                    }
                ],
            },
        }
        result = map_component(v1)
        assert result.component["config"]["outputs"][0]["filter"] == "amount > 0"

    def test_match_mode_mapped(self):
        v1 = {
            "id": "m",
            "type": "tMap",
            "config": {
                "inputs": {
                    "lookups": [{
                        "name": "ref",
                        "join_keys": [{"main_column": "id", "lookup_column": "id"}],
                        "join_type": "LEFT",
                        "match_mode": "FIRST_MATCH",
                    }]
                },
                "outputs": [{"name": "main", "columns": []}],
            },
        }
        result = map_component(v1)
        lookups = result.component["config"]["lookups"]
        assert lookups[0]["match_mode"] == "first"

    def test_match_mode_defaults_to_unique(self):
        v1 = {
            "id": "m",
            "type": "tMap",
            "config": {
                "inputs": {
                    "lookups": [{
                        "name": "ref",
                        "join_keys": [{"main_column": "id", "lookup_column": "id"}],
                        "join_type": "LEFT",
                    }]
                },
                "outputs": [{"name": "main", "columns": []}],
            },
        }
        result = map_component(v1)
        lookups = result.component["config"]["lookups"]
        assert lookups[0]["match_mode"] == "unique"

    def test_die_on_error_mapped(self):
        v1 = {
            "id": "m",
            "type": "tMap",
            "config": {
                "die_on_error": False,
                "outputs": [{"name": "main", "columns": []}],
            },
        }
        result = map_component(v1)
        assert result.component["config"]["die_on_error"] is False


class TestUnsupportedComponents:
    @pytest.mark.parametrize(
        "v1_type,suggestion",
        [
            ("tJavaRow", "python_row"),
            ("tJava", "python_code"),
            ("tDie", None),
            ("tWarn", None),
            ("tOracleInput", None),
            ("tFileInputPositional", None),
        ],
    )
    def test_unsupported_marked(self, v1_type, suggestion):
        v1 = {"id": "x", "type": v1_type, "config": {}}
        result = map_component(v1)
        assert result.component["config"].get("_unsupported") is True
        assert len(result.warnings) >= 1
        if suggestion:
            assert any(suggestion in w for w in result.warnings)

    def test_unknown_type(self):
        v1 = {"id": "x", "type": "tSomethingNew", "config": {}}
        result = map_component(v1)
        assert result.component["config"].get("_unsupported") is True


class TestSchemaConversion:
    def test_type_id_conversion(self):
        v1 = {
            "id": "r",
            "type": "tFileInputDelimited",
            "config": {"filepath": "f.csv"},
            "schema": {
                "output": [
                    {"name": "a", "type": "id_Integer"},
                    {"name": "b", "type": "id_Double"},
                    {"name": "c", "type": "id_Boolean"},
                    {"name": "d", "type": "id_BigDecimal"},
                    {"name": "e", "type": "id_String"},
                    {"name": "f", "type": "id_Long"},
                    {"name": "g", "type": "id_Float"},
                ]
            },
        }
        result = map_component(v1)
        schema = result.component["config"]["schema"]
        types = {s["name"]: s["type"] for s in schema}
        assert types == {
            "a": "integer",
            "b": "float",
            "c": "boolean",
            "d": "str",
            "e": "string",
            "f": "integer",
            "g": "float",
        }

    def test_drops_nullable_precision_scale(self):
        v1 = {
            "id": "r",
            "type": "tFileInputDelimited",
            "config": {"filepath": "f.csv"},
            "schema": {
                "output": [
                    {
                        "name": "a",
                        "type": "id_Integer",
                        "nullable": True,
                        "precision": 10,
                        "scale": 2,
                    }
                ]
            },
        }
        result = map_component(v1)
        col = result.component["config"]["schema"][0]
        assert "nullable" not in col
        assert "precision" not in col
        assert "scale" not in col


class TestFileInputFullRow:
    """Tests for tFileInputFullRow mapping."""

    def test_basic_mapping(self):
        v1 = {
            "id": "full_reader",
            "type": "tFileInputFullRow",
            "config": {
                "filepath": "/data/input.txt",
                "header": 1,
                "footer": 0,
                "limit": 0,
                "encoding": "UTF-8",
            },
            "schema": {
                "input": [
                    {"name": "line", "type": "id_String"},
                ]
            },
        }
        result = map_component(v1)
        comp = result.component
        assert comp["type"] == "file_input_full_row"
        assert comp["config"]["path"] == "/data/input.txt"
        assert comp["config"]["header_rows"] == 1
        assert comp["config"]["footer_rows"] == 0
        assert comp["config"]["schema"] == [{"name": "line", "type": "string"}]

    def test_encoding_mapping(self):
        v1 = {
            "id": "reader",
            "type": "tFileInputFullRow",
            "config": {"filepath": "/data/file.txt", "encoding": "ISO-8859-1"},
            "schema": {"input": [{"name": "line", "type": "id_String"}]},
        }
        result = map_component(v1)
        assert result.component["config"]["encoding"] == "ISO-8859-1"

    def test_limit_zero_becomes_none(self):
        v1 = {
            "id": "reader",
            "type": "tFileInputFullRow",
            "config": {"filepath": "/data/file.txt", "limit": 0},
            "schema": {"input": [{"name": "line", "type": "id_String"}]},
        }
        result = map_component(v1)
        assert result.component["config"].get("limit") is None


class TestContextLoadMapper:
    def test_basic_context_load(self):
        v1 = {
            "id": "ctx_load",
            "type": "tContextLoad",
            "config": {
                "filepath": "/data/context.properties",
                "delimiter": "=",
                "print_operations": True,
            },
        }
        result = map_component(v1)
        comp = result.component
        assert comp["type"] == "context_load"
        assert comp["config"]["path"] == "/data/context.properties"
        assert comp["config"]["delimiter"] == "="
        assert comp["config"]["print_operations"] is True

    def test_context_load_csv_format(self):
        v1 = {
            "id": "ctx_load",
            "type": "tContextLoad",
            "config": {
                "filepath": "/data/ctx.csv",
                "format": "csv",
                "csv_separator": ";",
            },
        }
        result = map_component(v1)
        comp = result.component
        assert comp["config"]["format"] == "delimited"
        assert comp["config"]["delimiter"] == ";"

    def test_context_load_default_delimiter(self):
        v1 = {
            "id": "ctx_load",
            "type": "tContextLoad",
            "config": {"filepath": "/data/ctx.properties"},
        }
        result = map_component(v1)
        assert result.component["config"]["delimiter"] == "="

    def test_context_load_error_mapping(self):
        v1 = {
            "id": "ctx_load",
            "type": "tContextLoad",
            "config": {
                "filepath": "/data/ctx.properties",
                "error_if_not_exists": False,
            },
        }
        result = map_component(v1)
        assert result.component["config"]["die_on_error"] is False
