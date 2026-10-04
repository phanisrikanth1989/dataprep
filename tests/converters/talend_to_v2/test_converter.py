"""Tests for the TalendToV2Converter orchestrator."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.converters.talend_to_v2.converter import ConversionResult, TalendToV2Converter


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
# Helpers
# ---------------------------------------------------------------------------

_FILE_INPUT_NODE = """
<node componentName="tFileInputDelimited">
  <elementParameter field="TEXT" name="UNIQUE_NAME" value="tFileInputDelimited_1" />
  <elementParameter field="TEXT" name="FILENAME" value="&quot;input.csv&quot;" />
  <elementParameter field="TEXT" name="FIELDSEPARATOR" value="&quot;,&quot;" />
  <elementParameter field="TEXT" name="HEADER" value="1" />
  <metadata connector="FLOW">
    <column name="id" type="id_Integer" nullable="true" />
    <column name="name" type="id_String" nullable="true" />
  </metadata>
</node>
"""

_FILE_OUTPUT_NODE = """
<node componentName="tFileOutputDelimited">
  <elementParameter field="TEXT" name="UNIQUE_NAME" value="tFileOutputDelimited_1" />
  <elementParameter field="TEXT" name="FILENAME" value="&quot;output.csv&quot;" />
  <elementParameter field="TEXT" name="FIELDSEPARATOR" value="&quot;,&quot;" />
</node>
"""

_CONNECTION = """
<connection connectorName="FLOW" label="row1" source="tFileInputDelimited_1" target="tFileOutputDelimited_1">
  <elementParameter name="UNIQUE_NAME" value="row1" />
</connection>
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTalendToV2Converter:
    def test_converts_simple_job(self, tmp_path: Path) -> None:
        """A minimal job with one file input -> one file output."""
        xml_path = _write_xml(
            tmp_path,
            _FILE_INPUT_NODE + _FILE_OUTPUT_NODE + _CONNECTION,
        )
        result = TalendToV2Converter(str(xml_path)).convert()

        assert isinstance(result, ConversionResult)
        cfg = result.config

        assert cfg["name"] == "TestJob"
        assert cfg["version"] == "2.0"
        assert len(cfg["components"]) == 2
        assert len(cfg["flows"]) >= 1

        # Verify component types were translated
        comp_types = {c["type"] for c in cfg["components"]}
        assert "file_input_delimited" in comp_types
        assert "file_output_delimited" in comp_types

        # Verify flow connects the two components
        flow = cfg["flows"][0]
        assert flow["source"] == "tFileInputDelimited_1"
        assert flow["target"] == "tFileOutputDelimited_1"

    def test_unknown_component_placeholder(self, tmp_path: Path) -> None:
        """Unknown component types get _unsupported=True and warning."""
        xml_path = _write_xml(
            tmp_path,
            """
            <node componentName="tSomeWeirdComponent">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="tSomeWeirdComponent_1" />
            </node>
            """,
        )
        result = TalendToV2Converter(str(xml_path)).convert()

        # Should have one component with _unsupported flag
        assert len(result.config["components"]) == 1
        comp = result.config["components"][0]
        assert comp["_unsupported"] is True
        assert comp["id"] == "tSomeWeirdComponent_1"
        assert comp["type"] == "tSomeWeirdComponent"

        # Should have a warning
        assert len(result.warnings) >= 1
        assert any("tSomeWeirdComponent" in w for w in result.warnings)

    def test_context_variables_typed(self, tmp_path: Path) -> None:
        """Context variables get proper V2 types."""
        xml_path = _write_xml(
            tmp_path,
            """
            <context confirmationNeeded="false" name="Default">
              <contextParameter name="INPUT_DIR" value="/data/in" type="id_String" />
              <contextParameter name="MAX_ROWS" value="1000" type="id_Integer" />
              <contextParameter name="ENABLED" value="true" type="id_Boolean" />
            </context>
            """
            + _FILE_INPUT_NODE,
        )
        result = TalendToV2Converter(str(xml_path)).convert()
        ctx = result.config["context"]

        assert ctx["INPUT_DIR"]["type"] == "str"
        assert ctx["INPUT_DIR"]["value"] == "/data/in"
        assert ctx["MAX_ROWS"]["type"] == "int"
        assert ctx["MAX_ROWS"]["value"] == "1000"
        assert ctx["ENABLED"]["type"] == "bool"
        assert ctx["ENABLED"]["value"] == "true"

    def test_flow_deduplication(self, tmp_path: Path) -> None:
        """Same flow from two converters should appear once."""
        # Both input and output converters will emit the same flow for row1
        xml_path = _write_xml(
            tmp_path,
            _FILE_INPUT_NODE + _FILE_OUTPUT_NODE + _CONNECTION,
        )
        result = TalendToV2Converter(str(xml_path)).convert()

        # Count flows between the two components
        matching_flows = [
            f
            for f in result.config["flows"]
            if f["source"] == "tFileInputDelimited_1"
            and f["target"] == "tFileOutputDelimited_1"
        ]
        assert len(matching_flows) == 1

    def test_metadata_includes_warnings(self, tmp_path: Path) -> None:
        """Conversion metadata includes warnings and review items."""
        xml_path = _write_xml(
            tmp_path,
            """
            <node componentName="tUnknownThing">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="tUnknownThing_1" />
            </node>
            """,
        )
        result = TalendToV2Converter(str(xml_path)).convert()

        meta = result.config["_conversion_metadata"]
        assert meta["source"] == "talend_xml"
        assert isinstance(meta["warnings"], list)
        assert len(meta["warnings"]) >= 1
        assert isinstance(meta["needs_review"], list)

    def test_empty_job(self, tmp_path: Path) -> None:
        """A job with no nodes produces valid but empty config."""
        xml_path = _write_xml(tmp_path, "")
        result = TalendToV2Converter(str(xml_path)).convert()

        assert result.config["name"] == "TestJob"
        assert result.config["components"] == []
        assert result.config["flows"] == []

    def test_conversion_result_dataclass(self) -> None:
        """ConversionResult holds config, warnings, and needs_review."""
        cr = ConversionResult(
            config={"name": "test"},
            warnings=["w1"],
            needs_review=[{"item": "r1"}],
        )
        assert cr.config == {"name": "test"}
        assert cr.warnings == ["w1"]
        assert cr.needs_review == [{"item": "r1"}]


class TestTriggerConversion:
    """Tests for trigger extraction in the full conversion pipeline."""

    def test_subjob_ok_trigger_in_output(self, tmp_path: Path) -> None:
        """SUBJOB_OK connection becomes an on_success trigger."""
        xml_path = _write_xml(tmp_path, """
            <node componentName="tFileInputDelimited">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="comp_A" />
              <elementParameter field="TEXT" name="FILENAME" value="&quot;a.csv&quot;" />
              <elementParameter field="TEXT" name="FIELDSEPARATOR" value="&quot;,&quot;" />
              <elementParameter field="TEXT" name="HEADER" value="1" />
              <metadata connector="FLOW">
                <column name="id" type="id_Integer" />
              </metadata>
            </node>
            <node componentName="tFileInputDelimited">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="comp_B" />
              <elementParameter field="TEXT" name="FILENAME" value="&quot;b.csv&quot;" />
              <elementParameter field="TEXT" name="FIELDSEPARATOR" value="&quot;,&quot;" />
              <elementParameter field="TEXT" name="HEADER" value="1" />
              <metadata connector="FLOW">
                <column name="id" type="id_Integer" />
              </metadata>
            </node>
            <connection connectorName="SUBJOB_OK" label="OnSubjobOk" source="comp_A" target="comp_B">
              <elementParameter name="UNIQUE_NAME" value="trigger1" />
            </connection>
        """)
        result = TalendToV2Converter(str(xml_path)).convert()
        triggers = result.config.get("triggers", [])

        assert len(triggers) == 1
        assert triggers[0]["source"] == "comp_A"
        assert triggers[0]["target"] == "comp_B"
        assert triggers[0]["type"] == "on_success"

    def test_run_if_trigger_flagged_for_review(self, tmp_path: Path) -> None:
        """RUN_IF connection becomes conditional trigger with needs_review."""
        xml_path = _write_xml(tmp_path, """
            <node componentName="tFileInputDelimited">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="comp_A" />
              <elementParameter field="TEXT" name="FILENAME" value="&quot;a.csv&quot;" />
              <elementParameter field="TEXT" name="FIELDSEPARATOR" value="&quot;,&quot;" />
              <elementParameter field="TEXT" name="HEADER" value="1" />
              <metadata connector="FLOW">
                <column name="id" type="id_Integer" />
              </metadata>
            </node>
            <node componentName="tFileInputDelimited">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="comp_B" />
              <elementParameter field="TEXT" name="FILENAME" value="&quot;b.csv&quot;" />
              <elementParameter field="TEXT" name="FIELDSEPARATOR" value="&quot;,&quot;" />
              <elementParameter field="TEXT" name="HEADER" value="1" />
              <metadata connector="FLOW">
                <column name="id" type="id_Integer" />
              </metadata>
            </node>
            <connection connectorName="RUN_IF" label="If" source="comp_A" target="comp_B">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="if1" />
              <elementParameter field="TEXT" name="CONDITION" value="context.env.equals(&quot;PROD&quot;)" />
            </connection>
        """)
        result = TalendToV2Converter(str(xml_path)).convert()
        triggers = result.config.get("triggers", [])

        assert len(triggers) == 1
        assert triggers[0]["type"] == "conditional"
        assert triggers[0]["condition"] == 'context.env.equals("PROD")'

        # Must be flagged for review
        assert any(
            nr.get("raw_condition") == 'context.env.equals("PROD")'
            for nr in result.needs_review
        )

    def test_no_triggers_produces_empty_list(self, tmp_path: Path) -> None:
        """Job with only data flows has triggers: []."""
        xml_path = _write_xml(
            tmp_path,
            _FILE_INPUT_NODE + _FILE_OUTPUT_NODE + _CONNECTION,
        )
        result = TalendToV2Converter(str(xml_path)).convert()
        assert result.config.get("triggers") == []

    def test_mixed_flows_and_triggers(self, tmp_path: Path) -> None:
        """Data flows go to flows, trigger connections go to triggers."""
        xml_path = _write_xml(tmp_path, """
            <node componentName="tFileInputDelimited">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="input1" />
              <elementParameter field="TEXT" name="FILENAME" value="&quot;a.csv&quot;" />
              <elementParameter field="TEXT" name="FIELDSEPARATOR" value="&quot;,&quot;" />
              <elementParameter field="TEXT" name="HEADER" value="1" />
              <metadata connector="FLOW">
                <column name="id" type="id_Integer" />
              </metadata>
            </node>
            <node componentName="tFileOutputDelimited">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="output1" />
              <elementParameter field="TEXT" name="FILENAME" value="&quot;out.csv&quot;" />
              <elementParameter field="TEXT" name="FIELDSEPARATOR" value="&quot;,&quot;" />
            </node>
            <node componentName="tFileInputDelimited">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="input2" />
              <elementParameter field="TEXT" name="FILENAME" value="&quot;b.csv&quot;" />
              <elementParameter field="TEXT" name="FIELDSEPARATOR" value="&quot;,&quot;" />
              <elementParameter field="TEXT" name="HEADER" value="1" />
              <metadata connector="FLOW">
                <column name="id" type="id_Integer" />
              </metadata>
            </node>
            <connection connectorName="FLOW" label="row1" source="input1" target="output1">
              <elementParameter name="UNIQUE_NAME" value="row1" />
            </connection>
            <connection connectorName="SUBJOB_OK" label="OnSubjobOk" source="output1" target="input2">
              <elementParameter name="UNIQUE_NAME" value="trigger1" />
            </connection>
        """)
        result = TalendToV2Converter(str(xml_path)).convert()

        # Data flow exists
        assert any(
            f["source"] == "input1" and f["target"] == "output1"
            for f in result.config["flows"]
        )
        # Trigger exists
        triggers = result.config["triggers"]
        assert len(triggers) == 1
        assert triggers[0]["source"] == "output1"
        assert triggers[0]["target"] == "input2"
        assert triggers[0]["type"] == "on_success"

        # Trigger should NOT appear in flows
        assert not any(
            f["source"] == "output1" and f["target"] == "input2"
            for f in result.config["flows"]
        )
