from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.converters.talend_to_v2.xml_parser import (
    ContextParam,
    SchemaColumn,
    TalendJob,
    XmlParser,
)


def _make_xml(content: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<talendfile:ProcessType xmi:version="2.0"
  xmlns:xmi="http://www.omg.org/XMI"
  xmlns:talendfile="platform:/resource/org.talend.model/model/TalendFile.xsd"
  defaultContext="Default" jobType="Standard">
{content}
</talendfile:ProcessType>"""


def _write_xml(tmp_path: Path, content: str, filename: str = "TestJob_0.1.item") -> Path:
    p = tmp_path / filename
    p.write_text(_make_xml(content), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# TestParseContext
# ---------------------------------------------------------------------------


class TestParseContext:
    def test_parses_context_variables(self, tmp_path: Path) -> None:
        xml_path = _write_xml(
            tmp_path,
            """
            <context confirmationNeeded="false" name="Default">
              <contextParameter name="INPUT_DIR" value="/data/in" type="id_String" />
              <contextParameter name="MAX_ROWS" value="1000" type="id_Integer" />
            </context>
            """,
        )
        job = XmlParser().parse(str(xml_path))
        assert len(job.context) == 2
        assert job.context["INPUT_DIR"] == ContextParam(
            name="INPUT_DIR", value="/data/in", type="id_String"
        )
        assert job.context["MAX_ROWS"] == ContextParam(
            name="MAX_ROWS", value="1000", type="id_Integer"
        )

    def test_uses_default_context_group(self, tmp_path: Path) -> None:
        xml_path = _write_xml(
            tmp_path,
            """
            <context confirmationNeeded="false" name="Default">
              <contextParameter name="ENV" value="dev" type="id_String" />
            </context>
            <context confirmationNeeded="false" name="Production">
              <contextParameter name="ENV" value="prod" type="id_String" />
            </context>
            """,
        )
        job = XmlParser().parse(str(xml_path))
        assert job.context["ENV"].value == "dev"

    def test_empty_context(self, tmp_path: Path) -> None:
        xml_path = _write_xml(tmp_path, "")
        job = XmlParser().parse(str(xml_path))
        assert job.context == {}


# ---------------------------------------------------------------------------
# TestParseNodes
# ---------------------------------------------------------------------------


class TestParseNodes:
    def test_parses_component_with_params(self, tmp_path: Path) -> None:
        xml_path = _write_xml(
            tmp_path,
            """
            <node componentName="tFileInputDelimited" offsetLabelX="0" offsetLabelY="0" posX="100" posY="100">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="tFileInputDelimited_1" />
              <elementParameter field="FILE" name="FILENAME" value="&quot;data.csv&quot;" />
              <elementParameter field="CHECK" name="CSV_OPTION" value="true" />
              <elementParameter field="TEXT" name="HEADER" value="1" />
            </node>
            """,
        )
        job = XmlParser().parse(str(xml_path))
        assert len(job.nodes) == 1
        node = job.nodes[0]
        assert node.component_id == "tFileInputDelimited_1"
        assert node.component_type == "tFileInputDelimited"
        assert node.params["FILENAME"] == "data.csv"
        assert node.params["CSV_OPTION"] is True
        assert node.params["HEADER"] == "1"
        # UNIQUE_NAME should NOT be in params
        assert "UNIQUE_NAME" not in node.params

    def test_parses_schema_columns(self, tmp_path: Path) -> None:
        xml_path = _write_xml(
            tmp_path,
            """
            <node componentName="tFileInputDelimited" offsetLabelX="0" offsetLabelY="0" posX="100" posY="100">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="tFileInputDelimited_1" />
              <metadata connector="FLOW" name="tFileInputDelimited_1">
                <column comment="" key="false" name="id" nullable="true" pattern="" type="id_Integer" />
                <column comment="" key="false" name="name" nullable="false" pattern="" type="id_String" />
                <column comment="" key="false" name="created" nullable="true" pattern="&quot;yyyy-MM-dd&quot;" type="id_Date" />
              </metadata>
            </node>
            """,
        )
        job = XmlParser().parse(str(xml_path))
        node = job.nodes[0]
        assert "FLOW" in node.schema
        columns = node.schema["FLOW"]
        assert len(columns) == 3
        assert columns[0] == SchemaColumn(name="id", type="id_Integer", nullable=True)
        assert columns[1] == SchemaColumn(name="name", type="id_String", nullable=False)
        assert columns[2] == SchemaColumn(
            name="created", type="id_Date", nullable=True, date_pattern="yyyy-MM-dd"
        )

    def test_parses_table_parameters(self, tmp_path: Path) -> None:
        xml_path = _write_xml(
            tmp_path,
            """
            <node componentName="tJavaRow" offsetLabelX="0" offsetLabelY="0" posX="100" posY="100">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="tJavaRow_1" />
              <elementParameter field="TABLE" name="JAVA_EXPRESSIONS">
                <elementValue elementRef="OUTPUT_COLUMN" value="col_a" />
                <elementValue elementRef="EXPRESSION" value="input_row.col_a" />
              </elementParameter>
            </node>
            """,
        )
        job = XmlParser().parse(str(xml_path))
        node = job.nodes[0]
        table = node.params["JAVA_EXPRESSIONS"]
        assert isinstance(table, list)
        assert len(table) == 2
        assert table[0] == {"elementRef": "OUTPUT_COLUMN", "value": "col_a"}
        assert table[1] == {"elementRef": "EXPRESSION", "value": "input_row.col_a"}

    def test_preserves_raw_xml(self, tmp_path: Path) -> None:
        xml_path = _write_xml(
            tmp_path,
            """
            <node componentName="tLogRow" offsetLabelX="0" offsetLabelY="0" posX="100" posY="100">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="tLogRow_1" />
            </node>
            """,
        )
        job = XmlParser().parse(str(xml_path))
        node = job.nodes[0]
        assert node.raw_xml is not None
        assert node.raw_xml.attrib["componentName"] == "tLogRow"

    def test_skips_external_field(self, tmp_path: Path) -> None:
        xml_path = _write_xml(
            tmp_path,
            """
            <node componentName="tMap" offsetLabelX="0" offsetLabelY="0" posX="100" posY="100">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="tMap_1" />
              <elementParameter field="EXTERNAL" name="MAP" />
              <elementParameter field="TEXT" name="SOME_PARAM" value="hello" />
            </node>
            """,
        )
        job = XmlParser().parse(str(xml_path))
        node = job.nodes[0]
        assert "MAP" not in node.params
        assert node.params["SOME_PARAM"] == "hello"

    def test_parses_reject_schema(self, tmp_path: Path) -> None:
        xml_path = _write_xml(
            tmp_path,
            """
            <node componentName="tFileInputDelimited" offsetLabelX="0" offsetLabelY="0" posX="100" posY="100">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="tFileInputDelimited_1" />
              <metadata connector="FLOW" name="main">
                <column name="id" type="id_Integer" nullable="true" />
              </metadata>
              <metadata connector="REJECT" name="reject">
                <column name="errorMessage" type="id_String" nullable="true" />
              </metadata>
            </node>
            """,
        )
        job = XmlParser().parse(str(xml_path))
        node = job.nodes[0]
        assert "FLOW" in node.schema
        assert "REJECT" in node.schema
        assert node.schema["REJECT"][0].name == "errorMessage"


# ---------------------------------------------------------------------------
# TestParseConnections
# ---------------------------------------------------------------------------


class TestParseConnections:
    def test_parses_flow_connections(self, tmp_path: Path) -> None:
        xml_path = _write_xml(
            tmp_path,
            """
            <connection connectorName="FLOW" label="row1" lineStyle="0"
              metaname="tFileInputDelimited_1" offsetLabelX="0" offsetLabelY="0"
              source="tFileInputDelimited_1" target="tLogRow_1">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="row1" />
            </connection>
            """,
        )
        job = XmlParser().parse(str(xml_path))
        assert len(job.connections) == 1
        conn = job.connections[0]
        assert conn.source == "tFileInputDelimited_1"
        assert conn.target == "tLogRow_1"
        assert conn.connector_type == "FLOW"
        assert conn.name == "row1"

    def test_parses_reject_connections(self, tmp_path: Path) -> None:
        xml_path = _write_xml(
            tmp_path,
            """
            <connection connectorName="REJECT" label="row2" lineStyle="0"
              source="tMap_1" target="tLogRow_1">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="reject1" />
            </connection>
            """,
        )
        job = XmlParser().parse(str(xml_path))
        conn = job.connections[0]
        assert conn.connector_type == "REJECT"
        assert conn.name == "reject1"

    def test_prefers_unique_name_over_label(self, tmp_path: Path) -> None:
        xml_path = _write_xml(
            tmp_path,
            """
            <connection connectorName="FLOW" label="row1" lineStyle="0"
              source="comp_1" target="comp_2">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="actual_name" />
            </connection>
            """,
        )
        job = XmlParser().parse(str(xml_path))
        assert job.connections[0].name == "actual_name"

    def test_falls_back_to_label(self, tmp_path: Path) -> None:
        xml_path = _write_xml(
            tmp_path,
            """
            <connection connectorName="FLOW" label="fallback_label" lineStyle="0"
              source="comp_1" target="comp_2">
            </connection>
            """,
        )
        job = XmlParser().parse(str(xml_path))
        assert job.connections[0].name == "fallback_label"

    def test_skips_connections_without_source_or_target(self, tmp_path: Path) -> None:
        xml_path = _write_xml(
            tmp_path,
            """
            <connection connectorName="FLOW" label="row1" lineStyle="0"
              source="comp_1">
            </connection>
            <connection connectorName="FLOW" label="row2" lineStyle="0"
              target="comp_2">
            </connection>
            <connection connectorName="FLOW" label="row3" lineStyle="0"
              source="comp_1" target="comp_2">
            </connection>
            """,
        )
        job = XmlParser().parse(str(xml_path))
        assert len(job.connections) == 1
        assert job.connections[0].name == "row3"


# ---------------------------------------------------------------------------
# TestParseJobName
# ---------------------------------------------------------------------------


class TestParseJobName:
    def test_extracts_from_filename(self, tmp_path: Path) -> None:
        xml_path = _write_xml(tmp_path, "", filename="SimpleJob_0.1.item")
        job = XmlParser().parse(str(xml_path))
        assert job.job_name == "SimpleJob"

    def test_handles_versioned_names(self, tmp_path: Path) -> None:
        xml_path = _write_xml(tmp_path, "", filename="My_Complex_Job_1.2.item")
        job = XmlParser().parse(str(xml_path))
        assert job.job_name == "My_Complex_Job"

    def test_no_version_suffix(self, tmp_path: Path) -> None:
        xml_path = _write_xml(tmp_path, "", filename="PlainJob.item")
        job = XmlParser().parse(str(xml_path))
        assert job.job_name == "PlainJob"


# ---------------------------------------------------------------------------
# TestQuoteStripping
# ---------------------------------------------------------------------------


class TestQuoteStripping:
    def test_strips_surrounding_quotes(self) -> None:
        parser = XmlParser()
        assert parser._strip_quotes('"data.csv"') == "data.csv"

    def test_preserves_context_refs(self) -> None:
        parser = XmlParser()
        assert parser._strip_quotes("context.INPUT_DIR") == "context.INPUT_DIR"

    def test_preserves_unquoted_values(self) -> None:
        parser = XmlParser()
        assert parser._strip_quotes("plain_value") == "plain_value"

    def test_preserves_empty_string(self) -> None:
        parser = XmlParser()
        assert parser._strip_quotes("") == ""

    def test_strips_empty_quoted_string(self) -> None:
        parser = XmlParser()
        assert parser._strip_quotes('""') == ""
