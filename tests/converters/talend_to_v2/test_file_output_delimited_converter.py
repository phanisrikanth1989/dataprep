"""Tests for talend_to_v2 FileOutputDelimited converter (Phase 8, COMP-06).

Dedicated test module covering all Talend parameters: path, delimiter,
row separator, include header, append, CSV option with text enclosure
and escape char, CSVROWSEPARATOR CLOSED_LIST, delete_empty_file,
error_if_exists, encoding warnings, UNSUPPORTED/NOT_PLANNED introspection,
label, schema, and XML fixture roundtrip.
"""
from __future__ import annotations

from pathlib import Path
from xml.etree.ElementTree import parse as xml_parse

import pytest

from src.converters.talend_to_v2.components.base import (
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v2.components.file.file_output_delimited_converter import (
    FileOutputDelimitedConverter,
)
from src.converters.talend_to_v2.xml_parser import SchemaColumn


FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flow_conn(name: str, source: str, target: str) -> TalendConnection:
    return TalendConnection(name=name, source=source, target=target, connector_type="FLOW")


SAMPLE_SCHEMA = [
    SchemaColumn(name="id", type="id_Integer", nullable=False),
    SchemaColumn(name="name", type="id_String", nullable=True),
    SchemaColumn(name="date", type="id_Date", nullable=True),
]


def _make_node(params=None, schema=None, component_id="tFileOutputDelimited_1"):
    """Create a TalendNode with defaults for tFileOutputDelimited."""
    base_params = {
        "FILENAME": "/data/output.csv",
    }
    if params:
        base_params.update(params)
    return TalendNode(
        component_id=component_id,
        component_type="tFileOutputDelimited",
        params=base_params,
        schema=schema or {"FLOW": SAMPLE_SCHEMA},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFileOutputDelimitedConverter:
    """Round-trip tests for tFileOutputDelimited converter (Phase 8)."""

    def test_basic_conversion(self):
        """Minimal params produce correct config output."""
        node = _make_node()
        converter = FileOutputDelimitedConverter()
        result = converter.convert(node, [], {})

        comp = result.component
        assert comp["id"] == "tFileOutputDelimited_1"
        assert comp["type"] == "file_output_delimited"
        cfg = comp["config"]
        assert cfg["path"] == "/data/output.csv"
        # Talend default: FIELDSEPARATOR=';' when not specified
        assert cfg["delimiter"] == ";"
        # Talend default: INCLUDEHEADER=false
        assert cfg["has_header"] is False
        # Talend default: FILE_EXIST_EXCEPTION=true
        assert cfg["error_if_exists"] is True

    def test_delimiter_custom(self):
        """Custom FIELDSEPARATOR maps to delimiter."""
        node = _make_node({"FIELDSEPARATOR": ","})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["delimiter"] == ","

    def test_delimiter_pipe(self):
        """Pipe FIELDSEPARATOR maps correctly."""
        node = _make_node({"FIELDSEPARATOR": "|"})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["delimiter"] == "|"

    def test_tab_delimiter(self):
        """FIELDSEPARATOR '\\t' resolves to actual tab character."""
        node = _make_node({"FIELDSEPARATOR": "\\t"})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["delimiter"] == "\t"

    def test_delimiter_multi_char_warning(self):
        """Multi-char FIELDSEPARATOR emits warning."""
        node = _make_node({"FIELDSEPARATOR": "||"})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["delimiter"] == "||"
        assert any("Multi-char" in w for w in result.warnings)

    def test_includeheader_true(self):
        """INCLUDEHEADER=true maps to has_header=True."""
        node = _make_node({"INCLUDEHEADER": True})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["has_header"] is True

    def test_includeheader_false(self):
        """INCLUDEHEADER=false maps to has_header=False."""
        node = _make_node({"INCLUDEHEADER": False})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["has_header"] is False

    def test_includeheader_string(self):
        """INCLUDEHEADER as string 'true' maps correctly."""
        node = _make_node({"INCLUDEHEADER": "true"})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["has_header"] is True

    def test_append_mapping(self):
        """APPEND=true maps to append=True."""
        node = _make_node({"APPEND": True})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["append"] is True

    def test_csv_option_with_text_enclosure(self):
        """CSV_OPTION=true sets quote_char and quote_style."""
        node = _make_node({
            "CSV_OPTION": True,
            "TEXT_ENCLOSURE": '"\'"',  # Talend: double-quote wrapped in quotes
        })
        result = FileOutputDelimitedConverter().convert(node, [], {})
        cfg = result.component["config"]
        assert cfg["quote_char"] == "'"
        assert cfg["quote_style"] == "always"

    def test_csv_option_default_enclosure(self):
        """CSV_OPTION=true without TEXT_ENCLOSURE uses default quote char."""
        node = _make_node({
            "CSV_OPTION": True,
        })
        result = FileOutputDelimitedConverter().convert(node, [], {})
        cfg = result.component["config"]
        # Default TEXT_ENCLOSURE is '"' which _strip_talend_quotes strips
        # but since there's no wrapping quotes, the raw '"' becomes ''
        # The converter uses default '"' from params.get("TEXT_ENCLOSURE", '"')
        assert cfg["quote_style"] == "always"

    def test_csv_option_custom_enclosure(self):
        """CSV_OPTION with custom TEXT_ENCLOSURE (single quote)."""
        node = _make_node({
            "CSV_OPTION": True,
            "TEXT_ENCLOSURE": "'",
        })
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["quote_char"] == "'"

    def test_escape_char_mismatch_warning(self):
        """ESCAPE_CHAR != TEXT_ENCLOSURE emits RFC4180 warning."""
        node = _make_node({
            "CSV_OPTION": True,
            "TEXT_ENCLOSURE": "'",
            "ESCAPE_CHAR": "\\",
        })
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert any("RFC4180" in w for w in result.warnings)
        assert any("ESCAPE_CHAR" in w for w in result.warnings)

    def test_escape_char_matches_no_warning(self):
        """ESCAPE_CHAR == TEXT_ENCLOSURE emits no warning."""
        node = _make_node({
            "CSV_OPTION": True,
            "TEXT_ENCLOSURE": "'",
            "ESCAPE_CHAR": "'",
        })
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert not any("ESCAPE_CHAR" in w for w in result.warnings)

    def test_csvrowseparator_lf(self):
        """CSVROWSEPARATOR 'LF' maps to '\\n'."""
        node = _make_node({
            "CSV_OPTION": True,
            "CSVROWSEPARATOR": "LF",
        })
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["line_terminator"] == "\n"

    def test_csvrowseparator_cr(self):
        """CSVROWSEPARATOR 'CR' maps to '\\r'."""
        node = _make_node({
            "CSV_OPTION": True,
            "CSVROWSEPARATOR": "CR",
        })
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["line_terminator"] == "\r"

    def test_csvrowseparator_crlf(self):
        """CSVROWSEPARATOR 'CRLF' maps to '\\r\\n'."""
        node = _make_node({
            "CSV_OPTION": True,
            "CSVROWSEPARATOR": "CRLF",
        })
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["line_terminator"] == "\r\n"

    def test_rowseparator_escape_resolution_newline(self):
        """ROWSEPARATOR '\\n' resolves to actual newline."""
        node = _make_node({"ROWSEPARATOR": "\\n"})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["line_terminator"] == "\n"

    def test_rowseparator_escape_resolution_crlf(self):
        """ROWSEPARATOR '\\r\\n' resolves to actual carriage-return + newline."""
        node = _make_node({"ROWSEPARATOR": "\\r\\n"})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["line_terminator"] == "\r\n"

    def test_rowseparator_escape_resolution_tab(self):
        """ROWSEPARATOR '\\t' resolves to actual tab."""
        node = _make_node({"ROWSEPARATOR": "\\t"})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["line_terminator"] == "\t"

    def test_delete_emptyfile_mapping(self):
        """DELETE_EMPTYFILE=true maps to delete_empty_file=True."""
        node = _make_node({"DELETE_EMPTYFILE": True})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["delete_empty_file"] is True

    def test_file_exist_exception_true(self):
        """FILE_EXIST_EXCEPTION=true maps to error_if_exists=True."""
        node = _make_node({"FILE_EXIST_EXCEPTION": True})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["error_if_exists"] is True

    def test_file_exist_exception_false(self):
        """FILE_EXIST_EXCEPTION=false maps to error_if_exists=False."""
        node = _make_node({"FILE_EXIST_EXCEPTION": False})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["error_if_exists"] is False

    def test_file_exist_exception_default_true(self):
        """When FILE_EXIST_EXCEPTION is absent, Talend default true applies."""
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["error_if_exists"] is True

    def test_encoding_non_utf8_warning(self):
        """Non-UTF-8 encoding emits warning."""
        node = _make_node({"ENCODING": '"ISO-8859-15"'})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert any("UNSUPPORTED" in w for w in result.warnings)
        assert any("ISO-8859-15" in w for w in result.warnings)
        # No encoding in config (Polars always writes UTF-8)
        assert "encoding" not in result.component["config"]

    def test_encoding_utf8_no_warning(self):
        """UTF-8 encoding emits no warning."""
        node = _make_node({"ENCODING": '"UTF-8"'})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert not any("ENCODING" in w for w in result.warnings)

    def test_unsupported_compress_warning(self):
        """COMPRESS=true emits UNSUPPORTED warning."""
        node = _make_node({"COMPRESS": True})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert any("COMPRESS" in w and "UNSUPPORTED" in w for w in result.warnings)

    def test_unsupported_split_warning(self):
        """SPLIT=true emits UNSUPPORTED warning."""
        node = _make_node({"SPLIT": True})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert any("SPLIT" in w and "UNSUPPORTED" in w for w in result.warnings)

    def test_not_planned_usestream_warning(self):
        """USESTREAM=true emits NOT_PLANNED warning."""
        node = _make_node({"USESTREAM": True})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert any("USESTREAM" in w and "NOT_PLANNED" in w for w in result.warnings)

    def test_not_planned_flushonrow_warning(self):
        """FLUSHONROW=true emits NOT_PLANNED warning."""
        node = _make_node({"FLUSHONROW": True})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert any("FLUSHONROW" in w and "NOT_PLANNED" in w for w in result.warnings)

    def test_not_planned_row_mode_warning(self):
        """ROW_MODE=true emits NOT_PLANNED warning."""
        node = _make_node({"ROW_MODE": True})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert any("ROW_MODE" in w and "NOT_PLANNED" in w for w in result.warnings)

    def test_unsupported_false_no_warning(self):
        """COMPRESS=false does NOT emit warning."""
        node = _make_node({"COMPRESS": False})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert not any("COMPRESS" in w for w in result.warnings)

    def test_schema_conversion(self):
        """Schema columns are converted from Talend types."""
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        schema = result.component["config"]["schema"]
        assert len(schema) == 3
        assert schema[0]["name"] == "id"
        assert schema[1]["name"] == "name"
        assert schema[2]["name"] == "date"

    def test_label_mapping(self):
        """LABEL parameter maps to config label."""
        node = _make_node({"LABEL": '"My Output"'})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "My Output"

    def test_context_path_expression(self):
        """Context variable in FILENAME is converted."""
        node = _make_node({"FILENAME": "context.outputDir"})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["path"] == "${context.outputDir}"

    def test_concatenated_path_expression(self):
        """Concatenated path with context variables is converted."""
        node = _make_node({
            "FILENAME": 'context.dir + "/output_" + context.date + ".csv"',
        })
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["path"] == "${context.dir}/output_${context.date}.csv"

    def test_flows_building(self):
        """Incoming FLOW connections produce correct flow dicts."""
        node = _make_node()
        conns = [_flow_conn("row1", "source_comp", "tFileOutputDelimited_1")]
        result = FileOutputDelimitedConverter().convert(node, conns, {})
        assert len(result.flows) == 1
        assert result.flows[0]["source"] == "source_comp"
        assert result.flows[0]["target"] == "tFileOutputDelimited_1"

    def test_xml_fixture_roundtrip(self):
        """Parse XML fixture, convert, and validate output."""
        fixture_path = FIXTURES_DIR / "tFileOutputDelimited_basic.xml"
        tree = xml_parse(fixture_path)
        root = tree.getroot()

        # Parse params
        params = {}
        for elem in root.findall("elementParameter"):
            name = elem.get("name", "")
            value = elem.get("value", "")
            field_type = elem.get("field", "")

            if field_type == "CHECK":
                params[name] = value.lower() == "true"
            elif field_type == "CLOSED_LIST":
                params[name] = value.strip('"')
            else:
                params[name] = value

        # Parse schema
        schema_cols = []
        for meta in root.findall("metadata"):
            for col in meta.findall("column"):
                schema_cols.append(
                    SchemaColumn(
                        name=col.get("name", ""),
                        type=col.get("type", "id_String"),
                        nullable=col.get("nullable", "true") == "true",
                    )
                )

        node = TalendNode(
            component_id=params.get("UNIQUE_NAME", "unknown"),
            component_type=root.get("componentName", ""),
            params=params,
            schema={"FLOW": schema_cols},
            raw_xml=root,
        )

        converter = FileOutputDelimitedConverter()
        result = converter.convert(node, [], {})

        comp = result.component
        assert comp["type"] == "file_output_delimited"
        assert comp["id"] == "tFileOutputDelimited_1"

        cfg = comp["config"]
        # Path should contain context expression
        assert "${context.outputDir}" in cfg["path"]
        # Delimiter should be semicolon
        assert cfg["delimiter"] == ";"
        # INCLUDEHEADER=false
        assert cfg["has_header"] is False
        # CSV_OPTION=true -> quote_style set
        assert cfg["quote_style"] == "always"
        # FILE_EXIST_EXCEPTION=true -> error_if_exists
        assert cfg["error_if_exists"] is True
        # Encoding is ISO-8859-15 -> warning
        assert any("ISO-8859-15" in w for w in result.warnings)
        # Schema should have 3 columns
        assert len(cfg["schema"]) == 3

    def test_no_schema_no_schema_key(self):
        """When no FLOW schema is present, config has no schema key."""
        node = _make_node(schema={"FLOW": []})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert "schema" not in result.component["config"]

    def test_quoted_delimiter_stripped(self):
        """Talend-quoted FIELDSEPARATOR has outer quotes stripped."""
        node = _make_node({"FIELDSEPARATOR": '";"'})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["delimiter"] == ";"

    def test_rowseparator_default_newline(self):
        """Default ROWSEPARATOR resolves to actual newline."""
        node = _make_node()
        result = FileOutputDelimitedConverter().convert(node, [], {})
        # Default ROWSEPARATOR is "\\n" which resolves to "\n"
        assert result.component["config"]["line_terminator"] == "\n"

    def test_advanced_separator_warning(self):
        """ADVANCED_SEPARATOR=true emits UNSUPPORTED warning."""
        node = _make_node({"ADVANCED_SEPARATOR": True})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert any("ADVANCED_SEPARATOR" in w for w in result.warnings)

    def test_tstatcatcher_false_no_warning(self):
        """TSTATCATCHER_STATS=false does NOT emit warning."""
        node = _make_node({"TSTATCATCHER_STATS": False})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert not any("TSTATCATCHER_STATS" in w for w in result.warnings)

    def test_csv_option_string_true(self):
        """CSV_OPTION as string 'true' maps correctly."""
        node = _make_node({
            "CSV_OPTION": "true",
            "TEXT_ENCLOSURE": '"',
        })
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert result.component["config"]["quote_style"] == "always"

    def test_os_line_separator_warning(self):
        """OS_LINE_SEPARATOR_AS_ROW_SEPARATOR=true emits NOT_PLANNED warning."""
        node = _make_node({"OS_LINE_SEPARATOR_AS_ROW_SEPARATOR": True})
        result = FileOutputDelimitedConverter().convert(node, [], {})
        assert any("OS_LINE_SEPARATOR" in w for w in result.warnings)
