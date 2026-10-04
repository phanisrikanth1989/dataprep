"""Tests for simple component converters (file I/O, sort, aggregate, context_load, java_row)."""
from __future__ import annotations

import pytest

from src.converters.talend_to_v2.components.base import (
    ComponentResult,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v2.xml_parser import SchemaColumn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flow_conn(name: str, source: str, target: str) -> TalendConnection:
    return TalendConnection(name=name, source=source, target=target, connector_type="FLOW")


def _reject_conn(name: str, source: str, target: str) -> TalendConnection:
    return TalendConnection(name=name, source=source, target=target, connector_type="REJECT")


SAMPLE_SCHEMA = [
    SchemaColumn(name="id", type="id_Integer", nullable=False),
    SchemaColumn(name="name", type="id_String", nullable=True),
    SchemaColumn(name="created", type="id_Date", nullable=True, date_pattern="yyyy-MM-dd"),
]


# ===========================================================================
# tFileInputDelimited
# ===========================================================================

class TestFileInputDelimitedConverter:
    """Tests for the tFileInputDelimited converter."""

    def _make_converter(self):
        from src.converters.talend_to_v2.components.file.file_input_delimited_converter import FileInputDelimitedConverter
        return FileInputDelimitedConverter()

    def test_basic_happy_path(self) -> None:
        node = TalendNode(
            component_id="tFileInputDelimited_1",
            component_type="tFileInputDelimited",
            params={
                "FILENAME": "data.csv",
                "FIELDSEPARATOR": ",",
                "CSV_OPTION": True,
                "TEXT_ENCLOSURE": "'",
                "ESCAPE_CHAR": "'",
                "HEADER": "1",
                "FOOTER": "0",
                "LIMIT": "",
                "ENCODING": "UTF-8",
                "REMOVE_EMPTY_ROW": True,
                "TRIMALL": False,
                "DIE_ON_ERROR": True,
            },
            schema={"FLOW": SAMPLE_SCHEMA},
        )
        result = self._make_converter().convert(node, [], {})
        comp = result.component
        assert comp["id"] == "tFileInputDelimited_1"
        assert comp["type"] == "file_input_delimited"
        cfg = comp["config"]
        assert cfg["path"] == "data.csv"
        assert cfg["delimiter"] == ","
        assert cfg["quote_char"] == "'"
        assert cfg["has_header"] is True
        assert cfg["encoding"] == "utf8"
        assert cfg["skip_empty_rows"] is True
        assert cfg["trim_all"] is False
        assert cfg["die_on_error"] is True
        # footer_rows=0 should be omitted
        assert "footer_rows" not in cfg
        # limit="" should be omitted
        assert "limit" not in cfg

    def test_schema_conversion(self) -> None:
        node = TalendNode(
            component_id="tFileInputDelimited_1",
            component_type="tFileInputDelimited",
            params={"FILENAME": "f.csv", "FIELDSEPARATOR": ";", "HEADER": "0"},
            schema={"FLOW": SAMPLE_SCHEMA},
        )
        result = self._make_converter().convert(node, [], {})
        schema = result.component["config"]["schema"]
        assert len(schema) == 3
        assert schema[0] == {"name": "id", "type": "integer"}
        assert schema[1] == {"name": "name", "type": "string"}
        assert schema[2] == {"name": "created", "type": "date", "date_pattern": "%Y-%m-%d"}

    def test_footer_and_limit(self) -> None:
        node = TalendNode(
            component_id="tFileInputDelimited_1",
            component_type="tFileInputDelimited",
            params={"FILENAME": "f.csv", "FIELDSEPARATOR": ",", "HEADER": "1", "FOOTER": "2", "LIMIT": "100"},
            schema={"FLOW": []},
        )
        result = self._make_converter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["footer_rows"] == 2
        assert cfg["limit"] == 100

    def test_escape_char_warning(self) -> None:
        node = TalendNode(
            component_id="tFileInputDelimited_1",
            component_type="tFileInputDelimited",
            params={
                "FILENAME": "f.csv",
                "FIELDSEPARATOR": ",",
                "HEADER": "1",
                "CSV_OPTION": True,
                "TEXT_ENCLOSURE": '"',
                "ESCAPE_CHAR": "\\",
            },
            schema={"FLOW": []},
        )
        result = self._make_converter().convert(node, [], {})
        assert any("ESCAPE_CHAR" in w for w in result.warnings)

    def test_missing_optional_params(self) -> None:
        """Converter should not crash when optional params are absent."""
        node = TalendNode(
            component_id="tFileInputDelimited_1",
            component_type="tFileInputDelimited",
            params={"FILENAME": "f.csv", "FIELDSEPARATOR": ",", "HEADER": "0"},
            schema={},
        )
        result = self._make_converter().convert(node, [], {})
        assert result.component["type"] == "file_input_delimited"

    def test_flow_generation(self) -> None:
        node = TalendNode(
            component_id="tFileInputDelimited_1",
            component_type="tFileInputDelimited",
            params={"FILENAME": "f.csv", "FIELDSEPARATOR": ",", "HEADER": "0"},
            schema={"FLOW": []},
        )
        connections = [
            _flow_conn("row1", "tFileInputDelimited_1", "tMap_1"),
            _reject_conn("row2", "tFileInputDelimited_1", "tLogRow_1"),
        ]
        result = self._make_converter().convert(node, connections, {})
        assert len(result.flows) == 2
        assert result.flows[0]["source"] == "tFileInputDelimited_1"
        assert result.flows[1].get("output") == "reject"

    def test_registry_lookup(self) -> None:
        from src.converters.talend_to_v2.components.registry import REGISTRY
        # Force import of the module to trigger registration
        import src.converters.talend_to_v2.components.file  # noqa: F401
        assert REGISTRY.get("tFileInputDelimited") is not None


# ===========================================================================
# tFileInputFullRow
# ===========================================================================

class TestFileInputFullRowConverter:
    """Tests for the tFileInputFullRow converter."""

    def _make_converter(self):
        from src.converters.talend_to_v2.components.file_input import FileInputFullRowConverter
        return FileInputFullRowConverter()

    def test_basic_happy_path(self) -> None:
        node = TalendNode(
            component_id="tFileInputFullRow_1",
            component_type="tFileInputFullRow",
            params={
                "FILENAME": "data.txt",
                "HEADER": "2",
                "FOOTER": "1",
                "LIMIT": "50",
                "ENCODING": "ISO-8859-1",
            },
            schema={"FLOW": [SchemaColumn(name="line", type="id_String")]},
        )
        result = self._make_converter().convert(node, [], {})
        comp = result.component
        assert comp["type"] == "file_input_full_row"
        cfg = comp["config"]
        assert cfg["path"] == "data.txt"
        assert cfg["header_rows"] == 2
        assert cfg["footer_rows"] == 1
        assert cfg["limit"] == 50
        assert cfg["encoding"] == "ISO-8859-1"

    def test_missing_optional_params(self) -> None:
        node = TalendNode(
            component_id="tFileInputFullRow_1",
            component_type="tFileInputFullRow",
            params={"FILENAME": "data.txt"},
            schema={},
        )
        result = self._make_converter().convert(node, [], {})
        assert result.component["type"] == "file_input_full_row"

    def test_registry_lookup(self) -> None:
        from src.converters.talend_to_v2.components.registry import REGISTRY
        import src.converters.talend_to_v2.components.file_input  # noqa: F401
        assert REGISTRY.get("tFileInputFullRow") is not None


# ===========================================================================
# tFileOutputDelimited
# ===========================================================================

class TestFileOutputDelimitedConverter:
    """Tests for the tFileOutputDelimited converter."""

    def _make_converter(self):
        from src.converters.talend_to_v2.components.file_output import FileOutputDelimitedConverter
        return FileOutputDelimitedConverter()

    def test_basic_happy_path(self) -> None:
        node = TalendNode(
            component_id="tFileOutputDelimited_1",
            component_type="tFileOutputDelimited",
            params={
                "FILENAME": "out.csv",
                "FIELDSEPARATOR": ",",
                "ROWSEPARATOR": "\\n",
                "INCLUDEHEADER": True,
                "APPEND": False,
                "TEXT_ENCLOSURE": '"',
                "CSV_OPTION": True,
                "DELETE_EMPTYFILE": False,
            },
            schema={"FLOW": SAMPLE_SCHEMA},
        )
        connections = [_flow_conn("row1", "tMap_1", "tFileOutputDelimited_1")]
        result = self._make_converter().convert(node, connections, {})
        comp = result.component
        assert comp["id"] == "tFileOutputDelimited_1"
        assert comp["type"] == "file_output_delimited"
        cfg = comp["config"]
        assert cfg["path"] == "out.csv"
        assert cfg["delimiter"] == ","
        assert cfg["line_terminator"] == "\\n"
        assert cfg["has_header"] is True
        assert cfg["append"] is False
        assert cfg["quote_char"] == '"'
        assert cfg["quote_style"] == "always"
        assert cfg["delete_empty_file"] is False

    def test_csv_option_false_omits_quote_style(self) -> None:
        node = TalendNode(
            component_id="tFileOutputDelimited_1",
            component_type="tFileOutputDelimited",
            params={
                "FILENAME": "out.csv",
                "FIELDSEPARATOR": ",",
                "ROWSEPARATOR": "\\n",
                "INCLUDEHEADER": True,
                "CSV_OPTION": False,
            },
            schema={"FLOW": []},
        )
        result = self._make_converter().convert(node, [], {})
        assert "quote_style" not in result.component["config"]

    def test_missing_optional_params(self) -> None:
        node = TalendNode(
            component_id="tFileOutputDelimited_1",
            component_type="tFileOutputDelimited",
            params={"FILENAME": "out.csv", "FIELDSEPARATOR": ",", "ROWSEPARATOR": "\\n"},
            schema={},
        )
        result = self._make_converter().convert(node, [], {})
        assert result.component["type"] == "file_output_delimited"

    def test_flow_generation_with_incoming(self) -> None:
        node = TalendNode(
            component_id="tFileOutputDelimited_1",
            component_type="tFileOutputDelimited",
            params={"FILENAME": "out.csv", "FIELDSEPARATOR": ",", "ROWSEPARATOR": "\\n"},
            schema={"FLOW": []},
        )
        connections = [_flow_conn("row1", "tMap_1", "tFileOutputDelimited_1")]
        result = self._make_converter().convert(node, connections, {})
        assert len(result.flows) == 1
        assert result.flows[0]["target"] == "tFileOutputDelimited_1"

    def test_schema_conversion(self) -> None:
        node = TalendNode(
            component_id="tFileOutputDelimited_1",
            component_type="tFileOutputDelimited",
            params={"FILENAME": "out.csv", "FIELDSEPARATOR": ",", "ROWSEPARATOR": "\\n"},
            schema={"FLOW": SAMPLE_SCHEMA},
        )
        result = self._make_converter().convert(node, [], {})
        schema = result.component["config"]["schema"]
        assert len(schema) == 3

    def test_registry_lookup(self) -> None:
        from src.converters.talend_to_v2.components.registry import REGISTRY
        import src.converters.talend_to_v2.components.file_output  # noqa: F401
        assert REGISTRY.get("tFileOutputDelimited") is not None


# ===========================================================================
# tSortRow -- converter tests moved to test_sort_row_converter.py
# ===========================================================================


# ===========================================================================
# tAggregateRow
# ===========================================================================

class TestAggregateRowConverter:
    """Tests for the tAggregateRow converter."""

    def _make_converter(self):
        from src.converters.talend_to_v2.components.aggregate import AggregateRowConverter
        return AggregateRowConverter()

    def test_groupby_and_operations(self) -> None:
        node = TalendNode(
            component_id="tAggregateRow_1",
            component_type="tAggregateRow",
            params={
                "GROUPBYS": [
                    {"elementRef": "OUTPUT_COLUMN", "value": "region"},
                    {"elementRef": "OUTPUT_COLUMN", "value": "category"},
                ],
                "OPERATIONS": [
                    {"elementRef": "OUTPUT_COLUMN", "value": "total"},
                    {"elementRef": "FUNCTION", "value": "sum"},
                    {"elementRef": "INPUT_COLUMN", "value": "revenue"},
                    {"elementRef": "IGNORE_NULL", "value": True},
                    {"elementRef": "OUTPUT_COLUMN", "value": "cnt"},
                    {"elementRef": "FUNCTION", "value": "count"},
                    {"elementRef": "INPUT_COLUMN", "value": "id"},
                    {"elementRef": "IGNORE_NULL", "value": False},
                ],
            },
            schema={"FLOW": []},
        )
        result = self._make_converter().convert(node, [], {})
        comp = result.component
        assert comp["type"] == "aggregate"
        cfg = comp["config"]
        assert cfg["group_by"] == ["region", "category"]
        ops = cfg["operations"]
        assert len(ops) == 2
        assert ops[0] == {"name": "total", "function": "sum", "column": "revenue", "ignore_nulls": True}
        assert ops[1] == {"name": "cnt", "function": "count", "column": "id", "ignore_nulls": False}

    def test_empty_groupby(self) -> None:
        node = TalendNode(
            component_id="tAggregateRow_1",
            component_type="tAggregateRow",
            params={
                "GROUPBYS": [],
                "OPERATIONS": [
                    {"elementRef": "OUTPUT_COLUMN", "value": "total"},
                    {"elementRef": "FUNCTION", "value": "sum"},
                    {"elementRef": "INPUT_COLUMN", "value": "amount"},
                    {"elementRef": "IGNORE_NULL", "value": True},
                ],
            },
            schema={"FLOW": []},
        )
        result = self._make_converter().convert(node, [], {})
        assert result.component["config"]["group_by"] == []
        assert len(result.component["config"]["operations"]) == 1

    def test_missing_params(self) -> None:
        node = TalendNode(
            component_id="tAggregateRow_1",
            component_type="tAggregateRow",
            params={},
            schema={},
        )
        result = self._make_converter().convert(node, [], {})
        assert result.component["config"]["group_by"] == []
        assert result.component["config"]["operations"] == []

    def test_flow_generation(self) -> None:
        node = TalendNode(
            component_id="tAggregateRow_1",
            component_type="tAggregateRow",
            params={},
            schema={},
        )
        connections = [
            _flow_conn("row1", "tMap_1", "tAggregateRow_1"),
            _flow_conn("row2", "tAggregateRow_1", "tLogRow_1"),
        ]
        result = self._make_converter().convert(node, connections, {})
        assert len(result.flows) == 2

    def test_registry_lookup(self) -> None:
        from src.converters.talend_to_v2.components.registry import REGISTRY
        import src.converters.talend_to_v2.components.aggregate  # noqa: F401
        assert REGISTRY.get("tAggregateRow") is not None


# ===========================================================================
# tContextLoad
# ===========================================================================

class TestContextLoadConverter:
    """Tests for the tContextLoad converter."""

    def _make_converter(self):
        from src.converters.talend_to_v2.components.context_load import ContextLoadConverter
        return ContextLoadConverter()

    def test_properties_format(self) -> None:
        node = TalendNode(
            component_id="tContextLoad_1",
            component_type="tContextLoad",
            params={
                "CONTEXTFILE": "ctx.properties",
                "FORMAT": "properties",
                "FIELDSEPARATOR": "=",
                "PRINT_OPERATIONS": True,
                "ERROR_IF_NOT_EXISTS": False,
            },
            schema={},
        )
        result = self._make_converter().convert(node, [], {})
        comp = result.component
        assert comp["type"] == "context_load"
        cfg = comp["config"]
        assert cfg["path"] == "ctx.properties"
        assert cfg["format"] == "properties"
        assert cfg["delimiter"] == "="
        assert cfg["print_operations"] is True
        assert cfg["die_on_error"] is False

    def test_csv_format(self) -> None:
        node = TalendNode(
            component_id="tContextLoad_1",
            component_type="tContextLoad",
            params={
                "CONTEXTFILE": "ctx.csv",
                "FORMAT": "csv",
                "CSV_SEPARATOR": ",",
                "PRINT_OPERATIONS": False,
                "ERROR_IF_NOT_EXISTS": True,
            },
            schema={},
        )
        result = self._make_converter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["format"] == "delimited"
        assert cfg["delimiter"] == ","

    def test_missing_optional_params(self) -> None:
        node = TalendNode(
            component_id="tContextLoad_1",
            component_type="tContextLoad",
            params={"CONTEXTFILE": "ctx.properties"},
            schema={},
        )
        result = self._make_converter().convert(node, [], {})
        assert result.component["type"] == "context_load"

    def test_flow_generation(self) -> None:
        node = TalendNode(
            component_id="tContextLoad_1",
            component_type="tContextLoad",
            params={"CONTEXTFILE": "ctx.properties"},
            schema={},
        )
        connections = [_flow_conn("row1", "tFileInputDelimited_1", "tContextLoad_1")]
        result = self._make_converter().convert(node, connections, {})
        assert len(result.flows) == 1

    def test_registry_lookup(self) -> None:
        from src.converters.talend_to_v2.components.registry import REGISTRY
        import src.converters.talend_to_v2.components.context_load  # noqa: F401
        assert REGISTRY.get("tContextLoad") is not None


# ===========================================================================
# tJavaRow
# ===========================================================================

class TestJavaRowConverter:
    """Tests for the tJavaRow converter."""

    def _make_converter(self):
        from src.converters.talend_to_v2.components.java_row import JavaRowConverter
        return JavaRowConverter()

    def test_placeholder_output(self) -> None:
        node = TalendNode(
            component_id="tJavaRow_1",
            component_type="tJavaRow",
            params={
                "CODE": 'output_row.name = input_row.name.toUpperCase();',
                "IMPORT": 'import java.util.HashMap;',
            },
            schema={"FLOW": []},
        )
        result = self._make_converter().convert(node, [], {})
        comp = result.component
        assert comp["id"] == "tJavaRow_1"
        assert comp["type"] == "python_row"
        cfg = comp["config"]
        assert cfg["code"] == "# TODO: Manually rewrite from Java"
        assert cfg["_original_java_code"] == 'output_row.name = input_row.name.toUpperCase();'
        assert cfg["_needs_rewrite"] is True

    def test_needs_review_flag(self) -> None:
        node = TalendNode(
            component_id="tJavaRow_1",
            component_type="tJavaRow",
            params={"CODE": "// java code"},
            schema={},
        )
        result = self._make_converter().convert(node, [], {})
        assert len(result.needs_review) == 1
        assert result.needs_review[0]["component"] == "tJavaRow_1"
        assert "manual" in result.needs_review[0]["reason"].lower() or "rewrite" in result.needs_review[0]["reason"].lower()

    def test_warning_message(self) -> None:
        node = TalendNode(
            component_id="tJavaRow_1",
            component_type="tJavaRow",
            params={"CODE": "// java code"},
            schema={},
        )
        result = self._make_converter().convert(node, [], {})
        assert len(result.warnings) == 1
        assert "tJavaRow_1" in result.warnings[0]
        assert "manual" in result.warnings[0].lower() or "rewrite" in result.warnings[0].lower()

    def test_missing_code_param(self) -> None:
        node = TalendNode(
            component_id="tJavaRow_1",
            component_type="tJavaRow",
            params={},
            schema={},
        )
        result = self._make_converter().convert(node, [], {})
        assert result.component["type"] == "python_row"
        assert result.component["config"]["_needs_rewrite"] is True

    def test_flow_generation(self) -> None:
        node = TalendNode(
            component_id="tJavaRow_1",
            component_type="tJavaRow",
            params={"CODE": "// code"},
            schema={},
        )
        connections = [
            _flow_conn("row1", "tMap_1", "tJavaRow_1"),
            _flow_conn("row2", "tJavaRow_1", "tLogRow_1"),
        ]
        result = self._make_converter().convert(node, connections, {})
        assert len(result.flows) == 2

    def test_registry_lookup(self) -> None:
        from src.converters.talend_to_v2.components.registry import REGISTRY
        import src.converters.talend_to_v2.components.java_row  # noqa: F401
        assert REGISTRY.get("tJavaRow") is not None


# ===========================================================================
# tFileInputExcel
# ===========================================================================

class TestFileInputExcelConverter:
    """Tests for the tFileInputExcel converter."""

    def _make_converter(self):
        from src.converters.talend_to_v2.components.file_input_excel import FileInputExcelConverter
        return FileInputExcelConverter()

    def test_basic_conversion(self) -> None:
        """Minimal config: path + schema."""
        node = TalendNode(
            component_id="tFileInputExcel_1",
            component_type="tFileInputExcel",
            params={"FILENAME": "data.xlsx"},
            schema={"FLOW": SAMPLE_SCHEMA},
        )
        result = self._make_converter().convert(node, [], {})
        comp = result.component
        assert comp["id"] == "tFileInputExcel_1"
        assert comp["type"] == "file_input_excel"
        cfg = comp["config"]
        assert cfg["path"] == "data.xlsx"
        assert "schema" in cfg
        assert len(cfg["schema"]) == 3

    def test_all_sheets(self) -> None:
        """ALL_SHEETS=true produces all_sheets: true."""
        node = TalendNode(
            component_id="tFileInputExcel_1",
            component_type="tFileInputExcel",
            params={"FILENAME": "data.xlsx", "ALL_SHEETS": True},
            schema={"FLOW": SAMPLE_SCHEMA},
        )
        result = self._make_converter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["all_sheets"] is True
        assert "sheet" not in cfg
        assert "sheets" not in cfg

    def test_sheet_list(self) -> None:
        """SHEETLIST TABLE param produces sheets array with names."""
        node = TalendNode(
            component_id="tFileInputExcel_1",
            component_type="tFileInputExcel",
            params={
                "FILENAME": "data.xlsx",
                "SHEETLIST": [
                    {"elementRef": "SHEETNAME", "value": "Sheet1"},
                    {"elementRef": "USE_REGEX", "value": "false"},
                    {"elementRef": "SHEETNAME", "value": "Sheet2"},
                    {"elementRef": "USE_REGEX", "value": "false"},
                ],
            },
            schema={"FLOW": SAMPLE_SCHEMA},
        )
        result = self._make_converter().convert(node, [], {})
        cfg = result.component["config"]
        assert "sheets" in cfg
        assert len(cfg["sheets"]) == 2
        assert cfg["sheets"][0] == {"name": "Sheet1"}
        assert cfg["sheets"][1] == {"name": "Sheet2"}
        assert "all_sheets" not in cfg
        assert "sheet" not in cfg

    def test_sheet_list_with_regex(self) -> None:
        """SHEETLIST with USE_REGEX=true adds regex flag."""
        node = TalendNode(
            component_id="tFileInputExcel_1",
            component_type="tFileInputExcel",
            params={
                "FILENAME": "data.xlsx",
                "SHEETLIST": [
                    {"elementRef": "SHEETNAME", "value": "Sales_.*"},
                    {"elementRef": "USE_REGEX", "value": "true"},
                ],
            },
            schema={"FLOW": SAMPLE_SCHEMA},
        )
        result = self._make_converter().convert(node, [], {})
        sheets = result.component["config"]["sheets"]
        assert len(sheets) == 1
        assert sheets[0] == {"name": "Sales_.*", "regex": True}

    def test_sheet_name(self) -> None:
        """SHEETNAME produces sheet: name when no ALL_SHEETS or SHEETLIST."""
        node = TalendNode(
            component_id="tFileInputExcel_1",
            component_type="tFileInputExcel",
            params={"FILENAME": "data.xlsx", "SHEETNAME": "Report"},
            schema={"FLOW": SAMPLE_SCHEMA},
        )
        result = self._make_converter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["sheet"] == "Report"
        assert "all_sheets" not in cfg
        assert "sheets" not in cfg

    def test_sheet_name_numeric(self) -> None:
        """SHEETNAME with numeric string converts to int for index-based lookup."""
        node = TalendNode(
            component_id="tFileInputExcel_1",
            component_type="tFileInputExcel",
            params={"FILENAME": "data.xlsx", "SHEETNAME": "2"},
            schema={"FLOW": SAMPLE_SCHEMA},
        )
        result = self._make_converter().convert(node, [], {})
        assert result.component["config"]["sheet"] == 2

    def test_header_footer_limit(self) -> None:
        """HEADER, FOOTER, LIMIT numeric param mapping."""
        node = TalendNode(
            component_id="tFileInputExcel_1",
            component_type="tFileInputExcel",
            params={
                "FILENAME": "data.xlsx",
                "HEADER": "1",
                "FOOTER": "3",
                "LIMIT": "500",
            },
            schema={"FLOW": SAMPLE_SCHEMA},
        )
        result = self._make_converter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["has_header"] is True
        assert cfg["footer_rows"] == 3
        assert cfg["limit"] == 500

    def test_header_zero_means_no_header(self) -> None:
        """HEADER=0 means has_header=False."""
        node = TalendNode(
            component_id="tFileInputExcel_1",
            component_type="tFileInputExcel",
            params={"FILENAME": "data.xlsx", "HEADER": "0"},
            schema={"FLOW": SAMPLE_SCHEMA},
        )
        result = self._make_converter().convert(node, [], {})
        assert result.component["config"]["has_header"] is False

    def test_column_range(self) -> None:
        """FIRST_COLUMN and LAST_COLUMN mapping."""
        node = TalendNode(
            component_id="tFileInputExcel_1",
            component_type="tFileInputExcel",
            params={
                "FILENAME": "data.xlsx",
                "FIRST_COLUMN": "2",
                "LAST_COLUMN": "5",
            },
            schema={"FLOW": SAMPLE_SCHEMA},
        )
        result = self._make_converter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["first_column"] == 2
        assert cfg["last_column"] == 5

    def test_column_range_zero_omitted(self) -> None:
        """FIRST_COLUMN=0 and LAST_COLUMN=0 are omitted."""
        node = TalendNode(
            component_id="tFileInputExcel_1",
            component_type="tFileInputExcel",
            params={
                "FILENAME": "data.xlsx",
                "FIRST_COLUMN": "0",
                "LAST_COLUMN": "0",
            },
            schema={"FLOW": SAMPLE_SCHEMA},
        )
        result = self._make_converter().convert(node, [], {})
        cfg = result.component["config"]
        assert "first_column" not in cfg
        assert "last_column" not in cfg

    def test_trim_and_skip_empty(self) -> None:
        """TRIMALL and STOPREAD_ON_EMPTYROW boolean mapping."""
        node = TalendNode(
            component_id="tFileInputExcel_1",
            component_type="tFileInputExcel",
            params={
                "FILENAME": "data.xlsx",
                "TRIMALL": True,
                "STOPREAD_ON_EMPTYROW": True,
            },
            schema={"FLOW": SAMPLE_SCHEMA},
        )
        result = self._make_converter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["trim_all"] is True
        assert cfg["skip_empty_rows"] is True

    def test_die_on_error(self) -> None:
        """DIE_ON_ERROR boolean passthrough."""
        node = TalendNode(
            component_id="tFileInputExcel_1",
            component_type="tFileInputExcel",
            params={"FILENAME": "data.xlsx", "DIE_ON_ERROR": True},
            schema={"FLOW": SAMPLE_SCHEMA},
        )
        result = self._make_converter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is True

    def test_unsupported_params_warn(self) -> None:
        """Unsupported params emit warnings."""
        node = TalendNode(
            component_id="tFileInputExcel_1",
            component_type="tFileInputExcel",
            params={
                "FILENAME": "data.xlsx",
                "PASSWORD": "secret",
                "GENERATION_MODE": "User",
                "READ_REAL_VALUE": True,
            },
            schema={"FLOW": SAMPLE_SCHEMA},
        )
        result = self._make_converter().convert(node, [], {})
        assert len(result.warnings) >= 3
        warning_text = " ".join(result.warnings)
        assert "PASSWORD" in warning_text
        assert "GENERATION_MODE" in warning_text
        assert "READ_REAL_VALUE" in warning_text

    def test_path_with_context(self) -> None:
        """Context variable interpolation in FILENAME."""
        node = TalendNode(
            component_id="tFileInputExcel_1",
            component_type="tFileInputExcel",
            params={"FILENAME": 'context.dir + "/data.xlsx"'},
            schema={"FLOW": SAMPLE_SCHEMA},
        )
        result = self._make_converter().convert(node, [], {})
        assert result.component["config"]["path"] == "${context.dir}/data.xlsx"

    def test_registry_lookup(self) -> None:
        """REGISTRY.get returns the converter class."""
        from src.converters.talend_to_v2.components.registry import REGISTRY
        import src.converters.talend_to_v2.components.file_input_excel  # noqa: F401
        assert REGISTRY.get("tFileInputExcel") is not None

    def test_flow_generation(self) -> None:
        """Incoming FLOW and outgoing REJECT produce correct flows."""
        node = TalendNode(
            component_id="tFileInputExcel_1",
            component_type="tFileInputExcel",
            params={"FILENAME": "data.xlsx"},
            schema={"FLOW": SAMPLE_SCHEMA},
        )
        connections = [
            _flow_conn("row1", "tFileInputExcel_1", "tMap_1"),
            _reject_conn("row2", "tFileInputExcel_1", "tLogRow_1"),
        ]
        result = self._make_converter().convert(node, connections, {})
        assert len(result.flows) == 2
        flow_names = {f["name"] for f in result.flows}
        assert "row1" in flow_names
        assert "row2" in flow_names
        reject_flow = [f for f in result.flows if f["name"] == "row2"][0]
        assert reject_flow.get("output") == "reject"

    def test_schema_conversion(self) -> None:
        """FLOW schema columns pass through convert_schema() correctly."""
        node = TalendNode(
            component_id="tFileInputExcel_1",
            component_type="tFileInputExcel",
            params={"FILENAME": "data.xlsx"},
            schema={"FLOW": SAMPLE_SCHEMA},
        )
        result = self._make_converter().convert(node, [], {})
        schema = result.component["config"]["schema"]
        assert schema[0] == {"name": "id", "type": "integer"}
        assert schema[1] == {"name": "name", "type": "string"}
        assert schema[2] == {"name": "created", "type": "date", "date_pattern": "%Y-%m-%d"}

    def test_stopread_warning(self) -> None:
        """STOPREAD_ON_EMPTYROW=true emits semantic difference warning."""
        node = TalendNode(
            component_id="tFileInputExcel_1",
            component_type="tFileInputExcel",
            params={"FILENAME": "data.xlsx", "STOPREAD_ON_EMPTYROW": True},
            schema={"FLOW": SAMPLE_SCHEMA},
        )
        result = self._make_converter().convert(node, [], {})
        assert any("STOPREAD" in w or "empty row" in w.lower() for w in result.warnings)

    def test_header_multi_row_warning(self) -> None:
        """HEADER > 1 emits warning about V2 single-row limitation."""
        node = TalendNode(
            component_id="tFileInputExcel_1",
            component_type="tFileInputExcel",
            params={"FILENAME": "data.xlsx", "HEADER": "3"},
            schema={"FLOW": SAMPLE_SCHEMA},
        )
        result = self._make_converter().convert(node, [], {})
        assert result.component["config"]["has_header"] is True
        assert any("header" in w.lower() and ("multi" in w.lower() or "single" in w.lower() or "1" in w) for w in result.warnings)

    def test_sheet_priority_all_sheets_wins(self) -> None:
        """ALL_SHEETS takes priority over SHEETNAME and SHEETLIST."""
        node = TalendNode(
            component_id="tFileInputExcel_1",
            component_type="tFileInputExcel",
            params={
                "FILENAME": "data.xlsx",
                "ALL_SHEETS": True,
                "SHEETNAME": "Sheet1",
                "SHEETLIST": [
                    {"elementRef": "SHEETNAME", "value": "Sheet2"},
                    {"elementRef": "USE_REGEX", "value": "false"},
                ],
            },
            schema={"FLOW": SAMPLE_SCHEMA},
        )
        result = self._make_converter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["all_sheets"] is True
        assert "sheet" not in cfg
        assert "sheets" not in cfg

    def test_empty_sheetlist_falls_through_to_sheetname(self) -> None:
        """Empty SHEETLIST (present but zero entries) falls through to SHEETNAME."""
        node = TalendNode(
            component_id="tFileInputExcel_1",
            component_type="tFileInputExcel",
            params={
                "FILENAME": "data.xlsx",
                "SHEETLIST": [],
                "SHEETNAME": "Report",
            },
            schema={"FLOW": SAMPLE_SCHEMA},
        )
        result = self._make_converter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["sheet"] == "Report"
        assert "sheets" not in cfg

    def test_missing_optional_params(self) -> None:
        """Converter should not crash when optional params are absent."""
        node = TalendNode(
            component_id="tFileInputExcel_1",
            component_type="tFileInputExcel",
            params={"FILENAME": "data.xlsx"},
            schema={},
        )
        result = self._make_converter().convert(node, [], {})
        assert result.component["type"] == "file_input_excel"
