"""Tests for talend_to_v2 FileInputDelimited converter (Phase 7, COMP-05).

Dedicated test module covering all 33 Talend parameters, encoding warnings,
UNSUPPORTED/NOT_PLANNED introspection, TRIMSELECT parsing, CSV_OPTION mapping,
NaN-to-null, and non-standard eol_char warnings.
"""
from __future__ import annotations

from pathlib import Path
from xml.etree.ElementTree import parse as xml_parse

import pytest

from src.converters.talend_to_v2.components.base import (
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v2.components.file.file_input_delimited_converter import (
    FileInputDelimitedConverter,
)
from src.converters.talend_to_v2.xml_parser import SchemaColumn


FIXTURES_DIR = Path(__file__).parent / "fixtures"


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
    SchemaColumn(name="amount", type="id_Double", nullable=True),
]


def _make_node(params=None, schema=None, component_id="tFileInputDelimited_1"):
    """Create a TalendNode with defaults for tFileInputDelimited."""
    base_params = {
        "FILENAME": "/data/input.csv",
        "FIELDSEPARATOR": ",",
        "HEADER": "1",
    }
    if params:
        base_params.update(params)
    return TalendNode(
        component_id=component_id,
        component_type="tFileInputDelimited",
        params=base_params,
        schema=schema or {"FLOW": SAMPLE_SCHEMA},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFileInputDelimitedConverter:
    """Round-trip tests for tFileInputDelimited converter (Phase 7)."""

    def test_basic_conversion(self):
        """Minimal params produce correct config output."""
        node = _make_node()
        converter = FileInputDelimitedConverter()
        result = converter.convert(node, [], {})

        comp = result.component
        assert comp["id"] == "tFileInputDelimited_1"
        assert comp["type"] == "file_input_delimited"
        cfg = comp["config"]
        assert cfg["path"] == "/data/input.csv"
        assert cfg["delimiter"] == ","
        assert cfg["has_header"] is True
        assert cfg["nan_is_null"] is True
        assert "schema" in cfg
        assert len(cfg["schema"]) == 3

    def test_encoding_utf8_passthrough(self):
        """UTF-8 encoding passes without warning."""
        node = _make_node({"ENCODING": "UTF-8"})
        converter = FileInputDelimitedConverter()
        result = converter.convert(node, [], {})

        assert result.component["config"]["encoding"] == "utf8"
        assert not any("ENCODING" in w for w in result.warnings)

    def test_encoding_non_utf8_warns(self):
        """ISO-8859-15 triggers warning with advice text."""
        node = _make_node({"ENCODING": "ISO-8859-15"})
        converter = FileInputDelimitedConverter()
        result = converter.convert(node, [], {})

        assert result.component["config"]["encoding"] == "utf8"
        assert any("UNSUPPORTED" in w and "ISO-8859-15" in w for w in result.warnings)
        assert any("Pre-convert" in w for w in result.warnings)

    def test_delimiter_mapping(self):
        """Semicolon delimiter passes through."""
        node = _make_node({"FIELDSEPARATOR": ";"})
        converter = FileInputDelimitedConverter()
        result = converter.convert(node, [], {})

        assert result.component["config"]["delimiter"] == ";"

    def test_multi_char_separator_warns(self):
        """Multi-char separator triggers warning."""
        node = _make_node({"FIELDSEPARATOR": "||"})
        converter = FileInputDelimitedConverter()
        result = converter.convert(node, [], {})

        assert result.component["config"]["delimiter"] == "||"
        assert any("Multi-char" in w for w in result.warnings)
        assert any("single-byte" in w for w in result.warnings)

    def test_header_skip_rows(self):
        """HEADER=3 produces has_header=True, skip_rows=2."""
        node = _make_node({"HEADER": "3"})
        converter = FileInputDelimitedConverter()
        result = converter.convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["has_header"] is True
        assert cfg["skip_rows"] == 2

    def test_footer_and_limit(self):
        """FOOTER=5 and LIMIT=100 produce correct config."""
        node = _make_node({"FOOTER": "5", "LIMIT": "100"})
        converter = FileInputDelimitedConverter()
        result = converter.convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["footer_rows"] == 5
        assert cfg["limit"] == 100

    def test_csv_option_quote_char(self):
        """CSV_OPTION=true + TEXT_ENCLOSURE="'" produces quote_char="'"."""
        node = _make_node({
            "CSV_OPTION": True,
            "TEXT_ENCLOSURE": "'",
            "ESCAPE_CHAR": "'",
        })
        converter = FileInputDelimitedConverter()
        result = converter.convert(node, [], {})

        assert result.component["config"]["quote_char"] == "'"
        # No warning when escape == enclosure
        assert not any("ESCAPE_CHAR" in w for w in result.warnings)

    def test_escape_char_mismatch_warns(self):
        """ESCAPE_CHAR differs from TEXT_ENCLOSURE produces warning."""
        node = _make_node({
            "CSV_OPTION": True,
            "TEXT_ENCLOSURE": '"',
            "ESCAPE_CHAR": "\\",
        })
        converter = FileInputDelimitedConverter()
        result = converter.convert(node, [], {})

        assert any("ESCAPE_CHAR" in w for w in result.warnings)
        assert any("does not support a separate escape character" in w for w in result.warnings)

    def test_trimall_and_trimselect(self):
        """Both TRIMALL and TRIMSELECT produce correct config."""
        node = _make_node({
            "TRIMALL": True,
            "TRIMSELECT": [
                {"elementRef": "SCHEMA_COLUMN", "value": '"name"'},
                {"elementRef": "TRIM", "value": '"LEFT"'},
                {"elementRef": "SCHEMA_COLUMN", "value": '"amount"'},
                {"elementRef": "TRIM", "value": '"RIGHT"'},
            ],
        })
        converter = FileInputDelimitedConverter()
        result = converter.convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["trim_all"] is True
        assert len(cfg["trim_columns"]) == 2
        assert cfg["trim_columns"][0] == {"column": "name", "trim": "left"}
        assert cfg["trim_columns"][1] == {"column": "amount", "trim": "right"}

    def test_reject_connection_sets_die_on_error_false(self):
        """REJECT connector wired produces die_on_error=False."""
        node = _make_node({"DIE_ON_ERROR": True})
        connections = [
            _flow_conn("row1", "tFileInputDelimited_1", "tMap_1"),
            _reject_conn("reject1", "tFileInputDelimited_1", "tLogRow_1"),
        ]
        converter = FileInputDelimitedConverter()
        result = converter.convert(node, connections, {})

        assert result.component["config"]["die_on_error"] is False

    def test_uncompress_warning(self):
        """UNCOMPRESS=true produces warning about gzip/ZIP."""
        node = _make_node({"UNCOMPRESS": True})
        converter = FileInputDelimitedConverter()
        result = converter.convert(node, [], {})

        assert any("UNCOMPRESS" in w for w in result.warnings)
        assert any("gzip" in w for w in result.warnings)
        assert any("ZIP" in w for w in result.warnings)

    def test_nan_is_null_always_set(self):
        """Converted config always has nan_is_null=True."""
        node = _make_node()
        converter = FileInputDelimitedConverter()
        result = converter.convert(node, [], {})

        assert result.component["config"]["nan_is_null"] is True

    def test_unsupported_params_warn(self):
        """ADVANCED_SEPARATOR=true triggers UNSUPPORTED warning."""
        node = _make_node({"ADVANCED_SEPARATOR": True})
        converter = FileInputDelimitedConverter()
        result = converter.convert(node, [], {})

        assert any("ADVANCED_SEPARATOR" in w and "UNSUPPORTED" in w for w in result.warnings)

    def test_not_planned_params_warn(self):
        """RANDOM=true triggers NOT_PLANNED warning."""
        node = _make_node({"RANDOM": True})
        converter = FileInputDelimitedConverter()
        result = converter.convert(node, [], {})

        assert any("RANDOM" in w and "NOT_PLANNED" in w for w in result.warnings)

    def test_schema_conversion(self):
        """FLOW schema converted correctly."""
        node = _make_node()
        converter = FileInputDelimitedConverter()
        result = converter.convert(node, [], {})

        schema = result.component["config"]["schema"]
        assert len(schema) == 3
        assert schema[0] == {"name": "id", "type": "integer"}
        assert schema[1] == {"name": "name", "type": "string"}
        assert schema[2] == {"name": "amount", "type": "float"}

    def test_xml_fixture_roundtrip(self):
        """Parse XML fixture, convert, and validate output."""
        fixture_path = FIXTURES_DIR / "tFileInputDelimited_basic.xml"
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

        converter = FileInputDelimitedConverter()
        result = converter.convert(node, [], {})

        comp = result.component
        assert comp["type"] == "file_input_delimited"
        assert comp["id"] == "tFileInputDelimited_1"

        cfg = comp["config"]
        # Path should have quotes stripped
        assert "/data/input.csv" in cfg["path"]
        # Delimiter should be semicolon (from fixture)
        assert cfg["delimiter"] == ";"
        assert cfg["has_header"] is True
        assert cfg["nan_is_null"] is True
        # Schema should have 3 columns
        assert len(cfg["schema"]) == 3
        assert cfg["schema"][0]["name"] == "id"
        assert cfg["schema"][0]["type"] == "integer"

    def test_non_standard_rowseparator_warns(self):
        """ROWSEPARATOR="|" produces eol_char="|" + warning about non-standard."""
        node = _make_node({"ROWSEPARATOR": "|"})
        converter = FileInputDelimitedConverter()
        result = converter.convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["eol_char"] == "|"
        assert any("non-standard" in w for w in result.warnings)
        assert any("optimized for" in w.lower() or "optimized for" in w for w in result.warnings)

    def test_standard_rowseparator_no_warning(self):
        """Standard newline ROWSEPARATOR does not produce warning."""
        node = _make_node({"ROWSEPARATOR": "\\n"})
        converter = FileInputDelimitedConverter()
        result = converter.convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["eol_char"] == "\\n"
        assert not any("non-standard" in w for w in result.warnings)

    def test_label_passthrough(self):
        """LABEL param is passed through to config."""
        node = _make_node({"LABEL": '"Read CSV"'})
        converter = FileInputDelimitedConverter()
        result = converter.convert(node, [], {})

        assert result.component["config"]["label"] == "Read CSV"

    def test_skip_empty_rows(self):
        """REMOVE_EMPTY_ROW=true sets skip_empty_rows=True."""
        node = _make_node({"REMOVE_EMPTY_ROW": True})
        converter = FileInputDelimitedConverter()
        result = converter.convert(node, [], {})

        assert result.component["config"]["skip_empty_rows"] is True

    def test_flows_passthrough(self):
        """Converter builds simple flows from connections."""
        node = _make_node()
        connections = [
            _flow_conn("row1", "tInput_1", "tFileInputDelimited_1"),
            _flow_conn("row2", "tFileInputDelimited_1", "tOutput_1"),
        ]
        converter = FileInputDelimitedConverter()
        result = converter.convert(node, connections, {})

        assert len(result.flows) == 2
        sources = [f["source"] for f in result.flows]
        assert "tInput_1" in sources
        assert "tFileInputDelimited_1" in sources

    def test_context_path_expression(self):
        """Context expression in FILENAME is converted to ${context.var} format."""
        node = _make_node({"FILENAME": 'context.inputDir + "/data.csv"'})
        converter = FileInputDelimitedConverter()
        result = converter.convert(node, [], {})

        assert result.component["config"]["path"] == "${context.inputDir}/data.csv"
