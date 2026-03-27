"""Tests for tFileInputDelimited -> FileInputDelimited converter."""
import pytest
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_input_delimited import (
    FileInputDelimitedConverter,
)


def _make_node(params=None, schema=None):
    return TalendNode(
        component_id="tFileInputDelimited_1",
        component_type="tFileInputDelimited",
        params=params or {},
        schema=schema or {},
        position={"x": 100, "y": 200},
    )


def _convert(node=None):
    """Shorthand: convert a node (or default empty node)."""
    return FileInputDelimitedConverter().convert(node or _make_node(), [], {})


class TestFileInputDelimitedConverter:
    """Tests for FileInputDelimitedConverter."""

    def test_basic_config(self):
        """Config params are extracted and quote-stripped correctly."""
        node = _make_node(params={
            "FILENAME": '"/data/input.csv"',
            "FIELDSEPARATOR": '","',
            "ROWSEPARATOR": '"\\n"',
            "HEADER": "1",
            "FOOTER": "0",
            "LIMIT": "1000",
            "ENCODING": '"UTF-8"',
            "TEXT_ENCLOSURE": '"\\""',
            "ESCAPE_CHAR": '"\\\\"',
            "REMOVE_EMPTY_ROW": "true",
            "TRIMALL": "false",
            "DIE_ON_ERROR": True,
        })
        result = FileInputDelimitedConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "FileInputDelimited"
        assert comp["original_type"] == "tFileInputDelimited"
        assert comp["id"] == "tFileInputDelimited_1"
        assert comp["position"] == {"x": 100, "y": 200}

        cfg = comp["config"]
        assert cfg["filepath"] == "/data/input.csv"
        assert cfg["delimiter"] == ","
        assert cfg["row_separator"] == "\\n"
        assert cfg["header_rows"] == 1
        assert cfg["footer_rows"] == 0
        assert cfg["limit"] == 1000
        assert cfg["encoding"] == "UTF-8"
        assert cfg["text_enclosure"] == '\\"'
        assert cfg["escape_char"] == "\\\\"
        assert cfg["remove_empty_rows"] is True
        assert cfg["trim_all"] is False
        assert cfg["die_on_error"] is True

    def test_defaults_when_params_missing(self):
        """Missing params fall back to sensible defaults."""
        node = _make_node(params={"FILENAME": '"/data/file.csv"'})
        result = FileInputDelimitedConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["filepath"] == "/data/file.csv"
        assert cfg["delimiter"] == ";"
        assert cfg["row_separator"] == "\\n"
        assert cfg["header_rows"] == 0
        assert cfg["footer_rows"] == 0
        assert cfg["limit"] == 0
        assert cfg["encoding"] == "ISO-8859-15"
        assert cfg["text_enclosure"] == ""
        assert cfg["escape_char"] == ""
        assert cfg["remove_empty_rows"] is False
        assert cfg["trim_all"] is False
        assert cfg["die_on_error"] is False

    def test_empty_filename_produces_warning(self):
        """An empty FILENAME triggers a warning."""
        node = _make_node(params={})
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert any("FILENAME" in w for w in result.warnings)

    def test_schema_parsed(self):
        """Schema columns are parsed into output schema dicts."""
        node = _make_node(
            params={"FILENAME": '"test.csv"'},
            schema={
                "FLOW": [
                    SchemaColumn(name="id", type="id_Integer", key=True, nullable=False),
                    SchemaColumn(name="name", type="id_String", key=False, length=100),
                    SchemaColumn(
                        name="created",
                        type="id_Date",
                        date_pattern="yyyy-MM-dd",
                    ),
                ]
            },
        )
        result = FileInputDelimitedConverter().convert(node, [], {})
        output_schema = result.component["schema"]["output"]

        assert len(output_schema) == 3
        assert output_schema[0]["name"] == "id"
        assert output_schema[0]["key"] is True
        assert output_schema[0]["nullable"] is False
        assert output_schema[1]["name"] == "name"
        assert output_schema[1]["length"] == 100
        assert output_schema[2]["name"] == "created"
        # date_pattern should be converted from Java to Python format
        assert output_schema[2]["date_pattern"] == "%Y-%m-%d"

    def test_input_schema_always_empty(self):
        """FileInputDelimited is a source — input schema must be empty."""
        node = _make_node(params={"FILENAME": '"x.csv"'})
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []

    def test_boolean_params_from_strings(self):
        """Boolean params accept string representations."""
        node = _make_node(params={
            "FILENAME": '"data.csv"',
            "REMOVE_EMPTY_ROW": "true",
            "TRIMALL": "1",
            "DIE_ON_ERROR": "false",
        })
        result = FileInputDelimitedConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["remove_empty_rows"] is True
        assert cfg["trim_all"] is True
        assert cfg["die_on_error"] is False

    def test_int_params_from_quoted_strings(self):
        """Integer params handle quoted string values."""
        node = _make_node(params={
            "FILENAME": '"data.csv"',
            "HEADER": '"5"',
            "FOOTER": '"2"',
            "LIMIT": '"500"',
        })
        result = FileInputDelimitedConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["header_rows"] == 5
        assert cfg["footer_rows"] == 2
        assert cfg["limit"] == 500

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params={"FILENAME": '"f.csv"'})
        result = FileInputDelimitedConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={"FILENAME": '"f.csv"'})
        result = FileInputDelimitedConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_registry_lookup(self):
        """The converter is registered under 'tFileInputDelimited'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tFileInputDelimited")
        assert cls is FileInputDelimitedConverter


# ---------------------------------------------------------------------------
# New boolean parameters
# ---------------------------------------------------------------------------

class TestNewBooleanParams:
    """Verify all new boolean parameters are extracted."""

    @pytest.mark.parametrize("xml_name,config_key", [
        ("CSV_OPTION", "csv_option"),
        ("SPLITRECORD", "split_record"),
        ("UNCOMPRESS", "uncompress"),
        ("CHECK_FIELDS_NUM", "check_fields_num"),
        ("CHECK_DATE", "check_date"),
        ("ADVANCED_SEPARATOR", "advanced_separator"),
        ("RANDOM", "random"),
        ("ENABLE_DECODE", "enable_decode"),
        ("TSTATCATCHER_STATS", "tstatcatcher_stats"),
    ])
    def test_bool_param_defaults_to_false(self, xml_name, config_key):
        result = _convert(_make_node())
        assert result.component["config"][config_key] is False

    @pytest.mark.parametrize("xml_name,config_key", [
        ("CSV_OPTION", "csv_option"),
        ("SPLITRECORD", "split_record"),
        ("UNCOMPRESS", "uncompress"),
        ("CHECK_FIELDS_NUM", "check_fields_num"),
        ("CHECK_DATE", "check_date"),
        ("ADVANCED_SEPARATOR", "advanced_separator"),
        ("RANDOM", "random"),
        ("ENABLE_DECODE", "enable_decode"),
        ("TSTATCATCHER_STATS", "tstatcatcher_stats"),
    ])
    def test_bool_param_extracted_when_true(self, xml_name, config_key):
        result = _convert(_make_node(params={xml_name: True}))
        assert result.component["config"][config_key] is True


# ---------------------------------------------------------------------------
# New string and int parameters
# ---------------------------------------------------------------------------

class TestNewStringIntParams:

    def test_thousands_separator_default(self):
        result = _convert(_make_node())
        assert result.component["config"]["thousands_separator"] == ","

    def test_thousands_separator_extracted(self):
        result = _convert(_make_node(params={"THOUSANDS_SEPARATOR": '"."'}))
        assert result.component["config"]["thousands_separator"] == "."

    def test_decimal_separator_default(self):
        result = _convert(_make_node())
        assert result.component["config"]["decimal_separator"] == "."

    def test_decimal_separator_extracted(self):
        result = _convert(_make_node(params={"DECIMAL_SEPARATOR": '","'}))
        assert result.component["config"]["decimal_separator"] == ","

    def test_nb_random_default(self):
        result = _convert(_make_node())
        assert result.component["config"]["nb_random"] == 10

    def test_nb_random_extracted(self):
        result = _convert(_make_node(params={"NB_RANDOM": "50"}))
        assert result.component["config"]["nb_random"] == 50

    def test_csv_row_separator_default(self):
        result = _convert(_make_node())
        assert result.component["config"]["csv_row_separator"] == "\\n"

    def test_csv_row_separator_extracted(self):
        result = _convert(_make_node(params={"CSVROWSEPARATOR": '"\\r\\n"'}))
        assert result.component["config"]["csv_row_separator"] == "\\r\\n"

    def test_label_default(self):
        result = _convert(_make_node())
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        result = _convert(_make_node(params={"LABEL": '"My Component"'}))
        assert result.component["config"]["label"] == "My Component"


# ---------------------------------------------------------------------------
# Table parameters (TRIMSELECT, DECODE_COLS)
# ---------------------------------------------------------------------------

class TestTableParams:

    def test_trim_select_default_empty(self):
        result = _convert(_make_node())
        assert result.component["config"]["trim_select"] == []

    def test_trim_select_parsed(self):
        raw_trimselect = [
            {"elementRef": "SCHEMA_COLUMN", "value": "name"},
            {"elementRef": "TRIM", "value": "true"},
            {"elementRef": "SCHEMA_COLUMN", "value": "age"},
            {"elementRef": "TRIM", "value": "false"},
            {"elementRef": "SCHEMA_COLUMN", "value": "city"},
            {"elementRef": "TRIM", "value": "true"},
        ]
        result = _convert(_make_node(params={"TRIMSELECT": raw_trimselect}))
        expected = [
            {"column": "name", "trim": True},
            {"column": "age", "trim": False},
            {"column": "city", "trim": True},
        ]
        assert result.component["config"]["trim_select"] == expected

    def test_decode_cols_default_empty(self):
        result = _convert(_make_node())
        assert result.component["config"]["decode_cols"] == []

    def test_decode_cols_parsed(self):
        raw_decode = [
            {"elementRef": "SCHEMA_COLUMN", "value": "hex_field"},
            {"elementRef": "DECODE", "value": "true"},
            {"elementRef": "SCHEMA_COLUMN", "value": "normal_field"},
            {"elementRef": "DECODE", "value": "false"},
        ]
        result = _convert(_make_node(params={"DECODE_COLS": raw_decode}))
        expected = [
            {"column": "hex_field", "decode": True},
            {"column": "normal_field", "decode": False},
        ]
        assert result.component["config"]["decode_cols"] == expected

    def test_trim_select_empty_table(self):
        """Empty TABLE parameter (no elementValue entries)."""
        result = _convert(_make_node(params={"TRIMSELECT": []}))
        assert result.component["config"]["trim_select"] == []


# ---------------------------------------------------------------------------
# Engine-gap warnings
# ---------------------------------------------------------------------------

class TestEngineGapWarnings:

    def test_no_warnings_for_defaults(self):
        """Default values should not produce engine-gap warnings."""
        result = _convert(_make_node(params={"FILENAME": '"/data/test.csv"'}))
        engine_warnings = [w for w in result.warnings if "engine" in w.lower()]
        assert engine_warnings == []

    @pytest.mark.parametrize("xml_name,expected_substring", [
        ("UNCOMPRESS", "UNCOMPRESS"),
        ("CSV_OPTION", "CSV_OPTION"),
        ("RANDOM", "RANDOM"),
        ("CHECK_FIELDS_NUM", "CHECK_FIELDS_NUM"),
        ("CHECK_DATE", "CHECK_DATE"),
        ("ENABLE_DECODE", "ENABLE_DECODE"),
        ("SPLITRECORD", "SPLITRECORD"),
        ("ADVANCED_SEPARATOR", "ADVANCED_SEPARATOR"),
    ])
    def test_warning_when_unsupported_param_enabled(self, xml_name, expected_substring):
        result = _convert(_make_node(params={"FILENAME": '"/data/test.csv"', xml_name: True}))
        assert any(expected_substring in w for w in result.warnings)

    @pytest.mark.parametrize("xml_name", [
        "UNCOMPRESS", "CSV_OPTION", "RANDOM",
        "CHECK_FIELDS_NUM", "CHECK_DATE", "ENABLE_DECODE", "SPLITRECORD",
        "ADVANCED_SEPARATOR",
    ])
    def test_no_warning_when_unsupported_param_disabled(self, xml_name):
        result = _convert(_make_node(params={"FILENAME": '"/data/test.csv"', xml_name: False}))
        engine_warnings = [w for w in result.warnings if "engine" in w.lower()]
        assert engine_warnings == []

    def test_warning_when_trimselect_has_true_entries(self):
        raw = [
            {"elementRef": "SCHEMA_COLUMN", "value": "name"},
            {"elementRef": "TRIM", "value": "true"},
        ]
        result = _convert(_make_node(params={"FILENAME": '"/data/test.csv"', "TRIMSELECT": raw}))
        assert any("TRIMSELECT" in w for w in result.warnings)

    def test_no_warning_when_trimselect_all_false(self):
        raw = [
            {"elementRef": "SCHEMA_COLUMN", "value": "name"},
            {"elementRef": "TRIM", "value": "false"},
        ]
        result = _convert(_make_node(params={"FILENAME": '"/data/test.csv"', "TRIMSELECT": raw}))
        assert not any("TRIMSELECT" in w for w in result.warnings)

    def test_warning_when_csv_row_separator_differs(self):
        result = _convert(_make_node(params={
            "FILENAME": '"/data/test.csv"',
            "CSVROWSEPARATOR": '"\\r\\n"',
            "ROWSEPARATOR": '"\\n"',
        }))
        assert any("CSVROWSEPARATOR" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Component output structure completeness
# ---------------------------------------------------------------------------

class TestComponentCompleteness:

    def test_all_28_config_keys_present(self):
        """Verify all 28 parameters are in the config dict."""
        result = _convert(_make_node())
        cfg = result.component["config"]
        expected_keys = {
            "filepath", "delimiter", "row_separator", "header_rows", "footer_rows",
            "limit", "encoding", "text_enclosure", "escape_char", "remove_empty_rows",
            "trim_all", "die_on_error",
            "csv_option", "split_record", "csv_row_separator",
            "uncompress", "check_fields_num", "check_date",
            "advanced_separator", "thousands_separator", "decimal_separator",
            "random", "nb_random", "enable_decode",
            "trim_select", "decode_cols",
            "tstatcatcher_stats", "label",
        }
        assert set(cfg.keys()) == expected_keys
