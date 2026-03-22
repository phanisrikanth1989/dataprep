"""Tests for tFileInputExcel -> FileInputExcel converter."""
from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.file.file_input_excel import (
    FileInputExcelConverter,
)


def _make_node(params=None, schema=None):
    return TalendNode(
        component_id="tFileInputExcel_1",
        component_type="tFileInputExcel",
        params=params or {},
        schema=schema or {},
        position={"x": 256, "y": 128},
    )


class TestFileInputExcelConverter:
    """Tests for FileInputExcelConverter."""

    # ------------------------------------------------------------------ #
    # 1. Basic config extraction
    # ------------------------------------------------------------------ #

    def test_basic_config(self):
        """All basic config params are extracted and quote-stripped correctly."""
        node = _make_node(params={
            "FILENAME": '"/data/report.xlsx"',
            "PASSWORD": '"secret"',
            "VERSION_2007": "true",
            "ALL_SHEETS": "true",
            "HEADER": "2",
            "FOOTER": "1",
            "LIMIT": '"500"',
            "AFFECT_EACH_SHEET": "true",
            "FIRST_COLUMN": "3",
            "LAST_COLUMN": '"10"',
            "DIE_ON_ERROR": "true",
            "SUPPRESS_WARN": "true",
            "NOVALIDATE_ON_CELL": "true",
            "ADVANCED_SEPARATOR": "true",
            "THOUSANDS_SEPARATOR": '"."',
            "DECIMAL_SEPARATOR": '","',
            "TRIMALL": "true",
            "CONVERTDATETOSTRING": "true",
            "READ_REAL_VALUE": "true",
            "STOPREAD_ON_EMPTYROW": "true",
            "GENERATION_MODE": '"STREAM_MODE"',
            "ENCODING": '"ISO-8859-1"',
            "SHEET_NAME": '"Sheet1"',
            "EXECUTION_MODE": '"PARALLEL"',
            "CHUNK_SIZE": '"1000"',
        })
        result = FileInputExcelConverter().convert(node, [], {})
        comp = result.component

        assert comp["type"] == "FileInputExcel"
        assert comp["original_type"] == "tFileInputExcel"
        assert comp["id"] == "tFileInputExcel_1"
        assert comp["position"] == {"x": 256, "y": 128}

        cfg = comp["config"]
        assert cfg["filepath"] == "/data/report.xlsx"
        assert cfg["password"] == "secret"
        assert cfg["version_2007"] is True
        assert cfg["all_sheets"] is True
        assert cfg["header"] == 2
        assert cfg["footer"] == 1
        assert cfg["limit"] == "500"
        assert cfg["affect_each_sheet"] is True
        assert cfg["first_column"] == 3
        assert cfg["last_column"] == "10"
        assert cfg["die_on_error"] is True
        assert cfg["suppress_warn"] is True
        assert cfg["novalidate_on_cell"] is True
        assert cfg["advanced_separator"] is True
        assert cfg["thousands_separator"] == "."
        assert cfg["decimal_separator"] == ","
        assert cfg["trimall"] is True
        assert cfg["convertdatetostring"] is True
        assert cfg["read_real_value"] is True
        assert cfg["stopread_on_emptyrow"] is True
        assert cfg["generation_mode"] == "STREAM_MODE"
        assert cfg["encoding"] == "ISO-8859-1"
        assert cfg["sheet_name"] == "Sheet1"
        assert cfg["execution_mode"] == "PARALLEL"
        assert cfg["chunk_size"] == "1000"

    # ------------------------------------------------------------------ #
    # 2. Defaults when params are missing
    # ------------------------------------------------------------------ #

    def test_defaults_when_params_missing(self):
        """Missing params fall back to sensible defaults."""
        node = _make_node(params={"FILENAME": '"/data/file.xlsx"'})
        result = FileInputExcelConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["filepath"] == "/data/file.xlsx"
        assert cfg["password"] == ""
        assert cfg["version_2007"] is True
        assert cfg["all_sheets"] is False
        assert cfg["sheetlist"] == []
        assert cfg["header"] == 1
        assert cfg["footer"] == 0
        assert cfg["limit"] == ""
        assert cfg["affect_each_sheet"] is False
        assert cfg["first_column"] == 1
        assert cfg["last_column"] == ""
        assert cfg["die_on_error"] is False
        assert cfg["suppress_warn"] is False
        assert cfg["novalidate_on_cell"] is False
        assert cfg["advanced_separator"] is False
        assert cfg["thousands_separator"] == ","
        assert cfg["decimal_separator"] == "."
        assert cfg["trimall"] is False
        assert cfg["trim_select"] == []
        assert cfg["convertdatetostring"] is False
        assert cfg["date_select"] == []
        assert cfg["read_real_value"] is False
        assert cfg["stopread_on_emptyrow"] is False
        assert cfg["generation_mode"] == "EVENT_MODE"
        assert cfg["encoding"] == "UTF-8"
        assert cfg["sheet_name"] == ""
        assert cfg["execution_mode"] == ""
        assert cfg["chunk_size"] == ""

    # ------------------------------------------------------------------ #
    # 3. Empty filename warning
    # ------------------------------------------------------------------ #

    def test_empty_filename_produces_warning(self):
        """An empty FILENAME triggers a warning."""
        node = _make_node(params={})
        result = FileInputExcelConverter().convert(node, [], {})
        assert any("FILENAME" in w for w in result.warnings)

    # ------------------------------------------------------------------ #
    # 4. SHEETLIST TABLE param parsing
    # ------------------------------------------------------------------ #

    def test_sheetlist_table_parsing_pre_grouped(self):
        """SHEETLIST table entries as pre-grouped dicts are parsed correctly."""
        node = _make_node(params={
            "FILENAME": '"/data/report.xlsx"',
            "SHEETLIST": [
                {"sheetname": "Sales", "use_regex": "false"},
                {"sheetname": "Inventory.*", "use_regex": "true"},
            ],
        })
        result = FileInputExcelConverter().convert(node, [], {})
        sheets = result.component["config"]["sheetlist"]

        assert len(sheets) == 2
        assert sheets[0] == {"sheetname": "Sales", "use_regex": False}
        assert sheets[1] == {"sheetname": "Inventory.*", "use_regex": True}

    def test_sheetlist_table_parsing_flat(self):
        """SHEETLIST table entries as flat elementRef/value pairs are parsed."""
        node = _make_node(params={
            "FILENAME": '"/data/report.xlsx"',
            "SHEETLIST": [
                {"elementRef": "SHEETNAME", "value": '"Sheet1"'},
                {"elementRef": "USE_REGEX", "value": "false"},
                {"elementRef": "SHEETNAME", "value": '"Data.*"'},
                {"elementRef": "USE_REGEX", "value": "true"},
            ],
        })
        result = FileInputExcelConverter().convert(node, [], {})
        sheets = result.component["config"]["sheetlist"]

        assert len(sheets) == 2
        assert sheets[0] == {"sheetname": "Sheet1", "use_regex": False}
        assert sheets[1] == {"sheetname": "Data.*", "use_regex": True}

    # ------------------------------------------------------------------ #
    # 5. TRIMSELECT TABLE param parsing
    # ------------------------------------------------------------------ #

    def test_trim_select_table_parsing(self):
        """TRIMSELECT table entries are parsed into column/trim dicts."""
        node = _make_node(params={
            "FILENAME": '"/data/report.xlsx"',
            "TRIMSELECT": [
                {"column": "name", "trim": "true"},
                {"column": "address", "trim": "false"},
            ],
        })
        result = FileInputExcelConverter().convert(node, [], {})
        trims = result.component["config"]["trim_select"]

        assert len(trims) == 2
        assert trims[0] == {"column": "name", "trim": True}
        assert trims[1] == {"column": "address", "trim": False}

    def test_trim_select_flat_elementref(self):
        """TRIMSELECT flat elementRef/value pairs are parsed."""
        node = _make_node(params={
            "FILENAME": '"/data/report.xlsx"',
            "TRIMSELECT": [
                {"elementRef": "SCHEMA_COLUMN", "value": "col_a"},
                {"elementRef": "TRIM", "value": "true"},
                {"elementRef": "SCHEMA_COLUMN", "value": "col_b"},
                {"elementRef": "TRIM", "value": "false"},
            ],
        })
        result = FileInputExcelConverter().convert(node, [], {})
        trims = result.component["config"]["trim_select"]

        assert len(trims) == 2
        assert trims[0] == {"column": "col_a", "trim": True}
        assert trims[1] == {"column": "col_b", "trim": False}

    # ------------------------------------------------------------------ #
    # 6. DATESELECT TABLE param parsing
    # ------------------------------------------------------------------ #

    def test_date_select_table_parsing(self):
        """DATESELECT table entries are parsed into column/convert_date/pattern dicts."""
        node = _make_node(params={
            "FILENAME": '"/data/report.xlsx"',
            "DATESELECT": [
                {"column": "created_at", "convert_date": "true", "pattern": '"yyyy-MM-dd"'},
                {"column": "updated_at", "convert_date": "false", "pattern": '"MM/dd/yyyy"'},
            ],
        })
        result = FileInputExcelConverter().convert(node, [], {})
        dates = result.component["config"]["date_select"]

        assert len(dates) == 2
        assert dates[0] == {
            "column": "created_at",
            "convert_date": True,
            "pattern": "yyyy-MM-dd",
        }
        assert dates[1] == {
            "column": "updated_at",
            "convert_date": False,
            "pattern": "MM/dd/yyyy",
        }

    def test_date_select_flat_elementref(self):
        """DATESELECT flat elementRef/value pairs are parsed."""
        node = _make_node(params={
            "FILENAME": '"/data/report.xlsx"',
            "DATESELECT": [
                {"elementRef": "SCHEMA_COLUMN", "value": "dt"},
                {"elementRef": "CONVERTDATE", "value": "true"},
                {"elementRef": "PATTERN", "value": '"dd-MM-yyyy"'},
            ],
        })
        result = FileInputExcelConverter().convert(node, [], {})
        dates = result.component["config"]["date_select"]

        assert len(dates) == 1
        assert dates[0] == {
            "column": "dt",
            "convert_date": True,
            "pattern": "dd-MM-yyyy",
        }

    # ------------------------------------------------------------------ #
    # 7. Schema parsing (source component)
    # ------------------------------------------------------------------ #

    def test_schema_parsed(self):
        """Schema columns are parsed into output schema dicts."""
        node = _make_node(
            params={"FILENAME": '"report.xlsx"'},
            schema={
                "FLOW": [
                    SchemaColumn(name="id", type="id_Integer", key=True, nullable=False),
                    SchemaColumn(name="name", type="id_String", key=False, length=200),
                    SchemaColumn(
                        name="sale_date",
                        type="id_Date",
                        date_pattern="yyyy-MM-dd",
                    ),
                ]
            },
        )
        result = FileInputExcelConverter().convert(node, [], {})
        output_schema = result.component["schema"]["output"]

        assert len(output_schema) == 3
        assert output_schema[0]["name"] == "id"
        assert output_schema[0]["key"] is True
        assert output_schema[0]["nullable"] is False
        assert output_schema[1]["name"] == "name"
        assert output_schema[1]["length"] == 200
        assert output_schema[2]["name"] == "sale_date"
        assert output_schema[2]["date_pattern"] == "%Y-%m-%d"

    def test_input_schema_always_empty(self):
        """FileInputExcel is a source — input schema must be empty."""
        node = _make_node(params={"FILENAME": '"x.xlsx"'})
        result = FileInputExcelConverter().convert(node, [], {})
        assert result.component["schema"]["input"] == []

    # ------------------------------------------------------------------ #
    # 8. Boolean params from string representations
    # ------------------------------------------------------------------ #

    def test_boolean_params_from_strings(self):
        """Boolean params accept string representations."""
        node = _make_node(params={
            "FILENAME": '"data.xlsx"',
            "VERSION_2007": "false",
            "ALL_SHEETS": "1",
            "DIE_ON_ERROR": "true",
            "SUPPRESS_WARN": "false",
            "TRIMALL": "1",
            "CONVERTDATETOSTRING": "true",
        })
        result = FileInputExcelConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["version_2007"] is False
        assert cfg["all_sheets"] is True
        assert cfg["die_on_error"] is True
        assert cfg["suppress_warn"] is False
        assert cfg["trimall"] is True
        assert cfg["convertdatetostring"] is True

    # ------------------------------------------------------------------ #
    # 9. Component dict structure
    # ------------------------------------------------------------------ #

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        node = _make_node(params={"FILENAME": '"f.xlsx"'})
        result = FileInputExcelConverter().convert(node, [], {})
        comp = result.component
        expected_keys = {
            "id", "type", "original_type", "position",
            "config", "schema", "inputs", "outputs",
        }
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        node = _make_node(params={"FILENAME": '"f.xlsx"'})
        result = FileInputExcelConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    # ------------------------------------------------------------------ #
    # 10. Registry lookup
    # ------------------------------------------------------------------ #

    def test_registry_lookup(self):
        """The converter is registered under 'tFileInputExcel'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tFileInputExcel")
        assert cls is FileInputExcelConverter

    # ------------------------------------------------------------------ #
    # 11. Integer params from quoted strings
    # ------------------------------------------------------------------ #

    def test_int_params_from_quoted_strings(self):
        """Integer params handle quoted string values."""
        node = _make_node(params={
            "FILENAME": '"data.xlsx"',
            "HEADER": '"5"',
            "FOOTER": '"2"',
            "FIRST_COLUMN": '"3"',
        })
        result = FileInputExcelConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["header"] == 5
        assert cfg["footer"] == 2
        assert cfg["first_column"] == 3

    # ------------------------------------------------------------------ #
    # 12. Empty TABLE params
    # ------------------------------------------------------------------ #

    def test_empty_table_params(self):
        """Empty or missing TABLE params produce empty lists."""
        node = _make_node(params={
            "FILENAME": '"data.xlsx"',
            "SHEETLIST": [],
            "TRIMSELECT": [],
            "DATESELECT": [],
        })
        result = FileInputExcelConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["sheetlist"] == []
        assert cfg["trim_select"] == []
        assert cfg["date_select"] == []
