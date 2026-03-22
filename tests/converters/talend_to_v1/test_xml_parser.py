"""Tests for talend_to_v1.xml_parser — XmlParser and TalendJob."""
from __future__ import annotations

import os
import tempfile
import textwrap
import xml.etree.ElementTree as ET

import pytest

from src.converters.talend_to_v1.xml_parser import TalendJob, XmlParser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_item(xml_text: str) -> str:
    """Write *xml_text* to a temp .item file and return the path."""
    fd, path = tempfile.mkstemp(suffix=".item")
    os.write(fd, textwrap.dedent(xml_text).encode("utf-8"))
    os.close(fd)
    return path


# Minimal job wrapper that many tests reuse.
_JOB_WRAP = (
    '<ProcessType xmlns:xmi="http://www.omg.org/XMI" '
    'jobType="Standard" defaultContext="Default">'
    "{body}"
    "</ProcessType>"
)


def _job_xml(body: str) -> str:
    return _JOB_WRAP.format(body=body)


# ---------------------------------------------------------------------------
# 1. Context parsing
# ---------------------------------------------------------------------------

class TestContextParsing:
    def test_parse_context_with_type_conversion(self):
        xml = _job_xml(
            '<context name="Default">'
            '  <contextParameter name="db_host" type="id_String" value="&quot;localhost&quot;" />'
            '  <contextParameter name="db_port" type="id_Integer" value="5432" />'
            '  <contextParameter name="is_prod" type="id_Boolean" value="false" />'
            '  <contextParameter name="threshold" type="id_Double" value="0.95" />'
            "</context>"
        )
        path = _write_item(xml)
        try:
            job = XmlParser().parse(path)
            ctx = job.context["Default"]

            assert ctx["db_host"]["type"] == "str"
            assert ctx["db_host"]["value"] == "localhost"  # quotes stripped

            assert ctx["db_port"]["type"] == "int"
            assert ctx["db_port"]["value"] == "5432"

            assert ctx["is_prod"]["type"] == "bool"
            assert ctx["threshold"]["type"] == "float"
        finally:
            os.unlink(path)

    def test_multiple_context_groups(self):
        xml = _job_xml(
            '<context name="Default">'
            '  <contextParameter name="env" type="id_String" value="dev" />'
            "</context>"
            '<context name="Production">'
            '  <contextParameter name="env" type="id_String" value="prod" />'
            "</context>"
        )
        path = _write_item(xml)
        try:
            job = XmlParser().parse(path)
            assert "Default" in job.context
            assert "Production" in job.context
            assert job.context["Default"]["env"]["value"] == "dev"
            assert job.context["Production"]["env"]["value"] == "prod"
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# 2. Node parsing — basic
# ---------------------------------------------------------------------------

class TestNodeParsing:
    def test_parse_node_with_params_and_schema(self):
        xml = _job_xml(
            '<node componentName="tFileInputDelimited" posX="100" posY="200">'
            '  <elementParameter name="UNIQUE_NAME" value="tFileInputDelimited_1" field="TEXT" />'
            '  <elementParameter name="FILENAME" value="&quot;/data/input.csv&quot;" field="FILE" />'
            '  <elementParameter name="HEADER" value="1" field="TEXT" />'
            '  <metadata connector="FLOW">'
            '    <column name="id" type="id_Integer" nullable="false" key="true" length="10" precision="0" />'
            '    <column name="name" type="id_String" nullable="true" length="50" precision="-1" />'
            "  </metadata>"
            "</node>"
        )
        path = _write_item(xml)
        try:
            job = XmlParser().parse(path)
            assert len(job.nodes) == 1
            node = job.nodes[0]

            assert node.component_id == "tFileInputDelimited_1"
            assert node.component_type == "tFileInputDelimited"
            assert "UNIQUE_NAME" not in node.params  # should be removed
            assert node.params["FILENAME"] == "/data/input.csv"  # quotes stripped
            assert node.params["HEADER"] == "1"

            # Schema
            assert "FLOW" in node.schema
            cols = node.schema["FLOW"]
            assert len(cols) == 2
            assert cols[0].name == "id"
            assert cols[0].type == "id_Integer"
            assert cols[0].nullable is False
            assert cols[0].key is True
            assert cols[0].length == 10
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# 3. UNIQUE_NAME extraction
# ---------------------------------------------------------------------------

class TestUniqueNameExtraction:
    def test_unique_name_becomes_component_id(self):
        xml = _job_xml(
            '<node componentName="tLogRow" posX="0" posY="0">'
            '  <elementParameter name="UNIQUE_NAME" value="tLogRow_1" field="TEXT" />'
            "</node>"
        )
        path = _write_item(xml)
        try:
            job = XmlParser().parse(path)
            assert job.nodes[0].component_id == "tLogRow_1"
            assert "UNIQUE_NAME" not in job.nodes[0].params
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# 4. Quote stripping
# ---------------------------------------------------------------------------

class TestQuoteStripping:
    def test_quotes_stripped_from_string_values(self):
        xml = _job_xml(
            '<node componentName="tLogRow" posX="0" posY="0">'
            '  <elementParameter name="UNIQUE_NAME" value="tLogRow_1" field="TEXT" />'
            '  <elementParameter name="FILENAME" value="&quot;output.csv&quot;" field="FILE" />'
            '  <elementParameter name="ENCODING" value="&quot;UTF-8&quot;" field="ENCODING_TYPE" />'
            "</node>"
        )
        path = _write_item(xml)
        try:
            job = XmlParser().parse(path)
            node = job.nodes[0]
            assert node.params["FILENAME"] == "output.csv"
            assert node.params["ENCODING"] == "UTF-8"
        finally:
            os.unlink(path)

    def test_non_quoted_values_untouched(self):
        xml = _job_xml(
            '<node componentName="tLogRow" posX="0" posY="0">'
            '  <elementParameter name="UNIQUE_NAME" value="tLogRow_1" field="TEXT" />'
            '  <elementParameter name="NB_ROWS" value="100" field="TEXT" />'
            "</node>"
        )
        path = _write_item(xml)
        try:
            node = XmlParser().parse(path).nodes[0]
            assert node.params["NB_ROWS"] == "100"
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# 5. Boolean resolution (field="CHECK")
# ---------------------------------------------------------------------------

class TestBooleanResolution:
    def test_check_field_true(self):
        xml = _job_xml(
            '<node componentName="tLogRow" posX="0" posY="0">'
            '  <elementParameter name="UNIQUE_NAME" value="tLogRow_1" field="TEXT" />'
            '  <elementParameter name="PRINT_HEADER" value="true" field="CHECK" />'
            "</node>"
        )
        path = _write_item(xml)
        try:
            node = XmlParser().parse(path).nodes[0]
            assert node.params["PRINT_HEADER"] is True
        finally:
            os.unlink(path)

    def test_check_field_false(self):
        xml = _job_xml(
            '<node componentName="tLogRow" posX="0" posY="0">'
            '  <elementParameter name="UNIQUE_NAME" value="tLogRow_1" field="TEXT" />'
            '  <elementParameter name="PRINT_HEADER" value="false" field="CHECK" />'
            "</node>"
        )
        path = _write_item(xml)
        try:
            node = XmlParser().parse(path).nodes[0]
            assert node.params["PRINT_HEADER"] is False
        finally:
            os.unlink(path)

    def test_check_field_missing_defaults_false(self):
        xml = _job_xml(
            '<node componentName="tLogRow" posX="0" posY="0">'
            '  <elementParameter name="UNIQUE_NAME" value="tLogRow_1" field="TEXT" />'
            '  <elementParameter name="USE_HEADER" field="CHECK" />'
            "</node>"
        )
        path = _write_item(xml)
        try:
            node = XmlParser().parse(path).nodes[0]
            assert node.params["USE_HEADER"] is False
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# 6. Schema column parsing with date patterns
# ---------------------------------------------------------------------------

class TestSchemaColumnParsing:
    def test_date_pattern_stripped(self):
        xml = _job_xml(
            '<node componentName="tMap" posX="0" posY="0">'
            '  <elementParameter name="UNIQUE_NAME" value="tMap_1" field="TEXT" />'
            '  <metadata connector="FLOW">'
            '    <column name="created" type="id_Date" pattern="&quot;yyyy-MM-dd&quot;" '
            '            nullable="true" key="false" length="-1" precision="-1" />'
            "  </metadata>"
            "</node>"
        )
        path = _write_item(xml)
        try:
            node = XmlParser().parse(path).nodes[0]
            col = node.schema["FLOW"][0]
            assert col.name == "created"
            assert col.type == "id_Date"
            assert col.date_pattern == "yyyy-MM-dd"  # quotes stripped
            assert col.nullable is True
        finally:
            os.unlink(path)

    def test_multiple_connectors(self):
        xml = _job_xml(
            '<node componentName="tMap" posX="0" posY="0">'
            '  <elementParameter name="UNIQUE_NAME" value="tMap_1" field="TEXT" />'
            '  <metadata connector="FLOW">'
            '    <column name="id" type="id_Integer" />'
            "  </metadata>"
            '  <metadata connector="REJECT">'
            '    <column name="err_msg" type="id_String" />'
            "  </metadata>"
            "</node>"
        )
        path = _write_item(xml)
        try:
            node = XmlParser().parse(path).nodes[0]
            assert "FLOW" in node.schema
            assert "REJECT" in node.schema
            assert node.schema["FLOW"][0].name == "id"
            assert node.schema["REJECT"][0].name == "err_msg"
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# 7. tLibraryLoad skipping
# ---------------------------------------------------------------------------

class TestLibraryLoadSkipping:
    def test_tlibraryload_excluded_from_nodes(self):
        xml = _job_xml(
            '<node componentName="tLibraryLoad" posX="0" posY="0">'
            '  <elementParameter name="UNIQUE_NAME" value="tLibraryLoad_1" field="TEXT" />'
            '  <elementParameter name="LIBRARY" value="&quot;commons-lang3.jar&quot;" field="TEXT" />'
            "</node>"
            '<node componentName="tLogRow" posX="50" posY="50">'
            '  <elementParameter name="UNIQUE_NAME" value="tLogRow_1" field="TEXT" />'
            "</node>"
        )
        path = _write_item(xml)
        try:
            job = XmlParser().parse(path)
            assert len(job.nodes) == 1
            assert job.nodes[0].component_type == "tLogRow"
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# 8. Connection parsing
# ---------------------------------------------------------------------------

class TestConnectionParsing:
    def test_flow_connection(self):
        xml = _job_xml(
            '<connection source="tInput_1" target="tMap_1" '
            'connectorName="FLOW" label="row1">'
            '  <elementParameter name="UNIQUE_NAME" value="row1" />'
            "</connection>"
        )
        path = _write_item(xml)
        try:
            job = XmlParser().parse(path)
            assert len(job.connections) == 1
            conn = job.connections[0]
            assert conn.source == "tInput_1"
            assert conn.target == "tMap_1"
            assert conn.connector_type == "FLOW"
            assert conn.name == "row1"
            assert conn.condition is None
        finally:
            os.unlink(path)

    def test_reject_connection(self):
        xml = _job_xml(
            '<connection source="tMap_1" target="tLogRow_1" '
            'connectorName="REJECT" label="reject1">'
            '  <elementParameter name="UNIQUE_NAME" value="reject1" />'
            "</connection>"
        )
        path = _write_item(xml)
        try:
            conn = XmlParser().parse(path).connections[0]
            assert conn.connector_type == "REJECT"
        finally:
            os.unlink(path)

    def test_subjob_ok_connection(self):
        xml = _job_xml(
            '<connection source="tInput_1" target="tLogRow_1" '
            'connectorName="SUBJOB_OK" label="OnSubjobOk">'
            '  <elementParameter name="UNIQUE_NAME" value="OnSubjobOk" />'
            "</connection>"
        )
        path = _write_item(xml)
        try:
            conn = XmlParser().parse(path).connections[0]
            assert conn.connector_type == "SUBJOB_OK"
            assert conn.name == "OnSubjobOk"
        finally:
            os.unlink(path)

    def test_connection_with_condition(self):
        xml = _job_xml(
            '<connection source="tInput_1" target="tLogRow_1" '
            'connectorName="RUN_IF" label="If">'
            '  <elementParameter name="UNIQUE_NAME" value="If1" />'
            '  <elementParameter name="CONDITION" value="context.enabled == true" />'
            "</connection>"
        )
        path = _write_item(xml)
        try:
            conn = XmlParser().parse(path).connections[0]
            assert conn.connector_type == "RUN_IF"
            assert conn.condition == "context.enabled == true"
        finally:
            os.unlink(path)

    def test_connection_missing_source_skipped(self):
        xml = _job_xml(
            '<connection target="tLogRow_1" connectorName="FLOW" label="bad" />'
        )
        path = _write_item(xml)
        try:
            job = XmlParser().parse(path)
            assert len(job.connections) == 0
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# 9. Routine parsing
# ---------------------------------------------------------------------------

class TestRoutineParsing:
    def test_routines_extracted_and_prefixed(self):
        xml = _job_xml(
            "<parameters>"
            '  <routinesParameter name="DataOperation" />'
            '  <routinesParameter name="routines.StringHandling" />'
            '  <routinesParameter name="Numeric" />'
            "</parameters>"
        )
        path = _write_item(xml)
        try:
            job = XmlParser().parse(path)
            assert "routines.DataOperation" in job.routines
            assert "routines.StringHandling" in job.routines
            assert "routines.Numeric" in job.routines
        finally:
            os.unlink(path)

    def test_routines_deduplicated(self):
        xml = _job_xml(
            "<parameters>"
            '  <routinesParameter name="Foo" />'
            '  <routinesParameter name="Foo" />'
            '  <routinesParameter name="routines.Foo" />'
            "</parameters>"
        )
        path = _write_item(xml)
        try:
            job = XmlParser().parse(path)
            assert job.routines.count("routines.Foo") == 1
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# 10. Library parsing
# ---------------------------------------------------------------------------

class TestLibraryParsing:
    def test_libraries_from_tlibraryload(self):
        xml = _job_xml(
            '<node componentName="tLibraryLoad" posX="0" posY="0">'
            '  <elementParameter name="UNIQUE_NAME" value="tLibraryLoad_1" field="TEXT" />'
            '  <elementParameter name="LIBRARY" value="&quot;commons-lang3-3.14.0.jar&quot;" field="TEXT" />'
            "</node>"
            '<node componentName="tLibraryLoad" posX="0" posY="0">'
            '  <elementParameter name="UNIQUE_NAME" value="tLibraryLoad_2" field="TEXT" />'
            '  <elementParameter name="LIBRARY" value="&quot;gson-2.8.9.jar&quot;" field="TEXT" />'
            "</node>"
        )
        path = _write_item(xml)
        try:
            job = XmlParser().parse(path)
            assert "commons-lang3-3.14.0.jar" in job.libraries
            assert "gson-2.8.9.jar" in job.libraries
            assert len(job.libraries) == 2
        finally:
            os.unlink(path)

    def test_libraries_deduplicated(self):
        xml = _job_xml(
            '<node componentName="tLibraryLoad" posX="0" posY="0">'
            '  <elementParameter name="UNIQUE_NAME" value="tLibraryLoad_1" field="TEXT" />'
            '  <elementParameter name="LIBRARY" value="&quot;same.jar&quot;" field="TEXT" />'
            "</node>"
            '<node componentName="tLibraryLoad" posX="0" posY="0">'
            '  <elementParameter name="UNIQUE_NAME" value="tLibraryLoad_2" field="TEXT" />'
            '  <elementParameter name="LIBRARY" value="&quot;same.jar&quot;" field="TEXT" />'
            "</node>"
        )
        path = _write_item(xml)
        try:
            job = XmlParser().parse(path)
            assert len(job.libraries) == 1
            assert job.libraries[0] == "same.jar"
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# 11. Position extraction
# ---------------------------------------------------------------------------

class TestPositionExtraction:
    def test_position_from_node_attributes(self):
        xml = _job_xml(
            '<node componentName="tLogRow" posX="320" posY="180">'
            '  <elementParameter name="UNIQUE_NAME" value="tLogRow_1" field="TEXT" />'
            "</node>"
        )
        path = _write_item(xml)
        try:
            node = XmlParser().parse(path).nodes[0]
            assert node.position == {"x": 320, "y": 180}
        finally:
            os.unlink(path)

    def test_position_defaults_to_zero(self):
        xml = _job_xml(
            '<node componentName="tLogRow">'
            '  <elementParameter name="UNIQUE_NAME" value="tLogRow_1" field="TEXT" />'
            "</node>"
        )
        path = _write_item(xml)
        try:
            node = XmlParser().parse(path).nodes[0]
            assert node.position == {"x": 0, "y": 0}
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# 12. Full parse round-trip (TalendJob structure)
# ---------------------------------------------------------------------------

class TestFullParse:
    def test_talend_job_fields(self):
        xml = _job_xml(
            '<context name="Default">'
            '  <contextParameter name="env" type="id_String" value="dev" />'
            "</context>"
            "<parameters>"
            '  <routinesParameter name="DataOp" />'
            "</parameters>"
            '<node componentName="tLogRow" posX="10" posY="20">'
            '  <elementParameter name="UNIQUE_NAME" value="tLogRow_1" field="TEXT" />'
            "</node>"
            '<node componentName="tLibraryLoad" posX="0" posY="0">'
            '  <elementParameter name="UNIQUE_NAME" value="tLibraryLoad_1" field="TEXT" />'
            '  <elementParameter name="LIBRARY" value="&quot;foo.jar&quot;" field="TEXT" />'
            "</node>"
            '<connection source="tLogRow_1" target="tLogRow_1" '
            'connectorName="FLOW" label="row1">'
            '  <elementParameter name="UNIQUE_NAME" value="row1" />'
            "</connection>"
        )
        path = _write_item(xml)
        try:
            job = XmlParser().parse(path)
            assert isinstance(job, TalendJob)
            assert job.job_type == "Standard"
            assert job.default_context == "Default"
            assert "Default" in job.context
            assert len(job.nodes) == 1  # tLibraryLoad excluded
            assert len(job.connections) == 1
            assert "routines.DataOp" in job.routines
            assert "foo.jar" in job.libraries
        finally:
            os.unlink(path)

    def test_job_name_from_filename(self):
        xml = _job_xml("")
        path = _write_item(xml)
        try:
            job = XmlParser().parse(path)
            # job_name is the stem of the temp file
            assert job.job_name  # non-empty
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# 13. EXTERNAL field skipped
# ---------------------------------------------------------------------------

class TestExternalFieldSkipped:
    def test_external_field_not_in_params(self):
        xml = _job_xml(
            '<node componentName="tMap" posX="0" posY="0">'
            '  <elementParameter name="UNIQUE_NAME" value="tMap_1" field="TEXT" />'
            '  <elementParameter name="MAP" field="EXTERNAL" value="some_big_blob" />'
            '  <elementParameter name="LABEL" value="&quot;myLabel&quot;" field="LABEL" />'
            "</node>"
        )
        path = _write_item(xml)
        try:
            node = XmlParser().parse(path).nodes[0]
            assert "MAP" not in node.params
            assert node.params["LABEL"] == "myLabel"
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# 14. TABLE field parsing
# ---------------------------------------------------------------------------

class TestTableFieldParsing:
    def test_table_field_parsed_as_list(self):
        xml = _job_xml(
            '<node componentName="tRowGenerator" posX="0" posY="0">'
            '  <elementParameter name="UNIQUE_NAME" value="tRowGenerator_1" field="TEXT" />'
            '  <elementParameter name="VALUES" field="TABLE">'
            '    <elementValue elementRef="SCHEMA_COLUMN" value="col1" />'
            '    <elementValue elementRef="ARRAY" value="sequence(1,10,1)" />'
            "  </elementParameter>"
            "</node>"
        )
        path = _write_item(xml)
        try:
            node = XmlParser().parse(path).nodes[0]
            values = node.params["VALUES"]
            assert isinstance(values, list)
            assert len(values) == 2
            assert values[0]["elementRef"] == "SCHEMA_COLUMN"
            assert values[0]["value"] == "col1"
            assert values[1]["elementRef"] == "ARRAY"
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# 15. raw_xml reference
# ---------------------------------------------------------------------------

class TestRawXmlReference:
    def test_raw_xml_attached(self):
        xml = _job_xml(
            '<node componentName="tLogRow" posX="0" posY="0">'
            '  <elementParameter name="UNIQUE_NAME" value="tLogRow_1" field="TEXT" />'
            "</node>"
        )
        path = _write_item(xml)
        try:
            node = XmlParser().parse(path).nodes[0]
            assert node.raw_xml is not None
            assert node.raw_xml.get("componentName") == "tLogRow"
        finally:
            os.unlink(path)
