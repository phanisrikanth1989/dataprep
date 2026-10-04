"""Tests for Talend trigger connection mapping to V2 triggers."""
from __future__ import annotations

from pathlib import Path

from src.converters.talend_to_v2.components.base import TalendConnection
from src.converters.talend_to_v2.trigger_mapper import TriggerMapperResult, map_triggers
from src.converters.talend_to_v2.xml_parser import XmlParser


def _make_xml(content: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<talendfile:ProcessType xmi:version="2.0"
  xmlns:xmi="http://www.omg.org/XMI"
  xmlns:talendfile="platform:/resource/org.talend.model/model/TalendFile.xsd"
  defaultContext="Default" jobType="Standard">
{content}
</talendfile:ProcessType>"""


def _write_xml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "TestJob_0.1.item"
    p.write_text(_make_xml(content), encoding="utf-8")
    return p


class TestTalendConnectionCondition:
    """Tests for optional condition field on TalendConnection."""

    def test_connection_without_condition(self):
        conn = TalendConnection(
            name="row1", source="A", target="B", connector_type="FLOW"
        )
        assert conn.condition is None

    def test_connection_with_condition(self):
        conn = TalendConnection(
            name="if1", source="A", target="B",
            connector_type="RUN_IF",
            condition='context.env.equals("PROD")',
        )
        assert conn.condition == 'context.env.equals("PROD")'

    def test_existing_connections_unaffected(self):
        """Existing code that creates TalendConnection without condition still works."""
        conn = TalendConnection(
            name="row1", source="A", target="B", connector_type="MAIN"
        )
        assert conn.name == "row1"
        assert conn.source == "A"
        assert conn.target == "B"
        assert conn.connector_type == "MAIN"
        assert conn.condition is None


class TestXmlParserTriggerCondition:
    """Tests for extracting CONDITION from RUN_IF connections."""

    def test_run_if_connection_has_condition(self, tmp_path: Path):
        xml_path = _write_xml(tmp_path, """
            <node componentName="tFileInputDelimited">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="comp_A" />
            </node>
            <node componentName="tFileInputDelimited">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="comp_B" />
            </node>
            <connection connectorName="RUN_IF" label="If" source="comp_A" target="comp_B">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="if1" />
              <elementParameter field="TEXT" name="CONDITION" value="context.env.equals(&quot;PROD&quot;)" />
            </connection>
        """)
        job = XmlParser().parse(str(xml_path))

        run_if_conns = [c for c in job.connections if c.connector_type == "RUN_IF"]
        assert len(run_if_conns) == 1
        assert run_if_conns[0].condition == 'context.env.equals("PROD")'

    def test_flow_connection_has_no_condition(self, tmp_path: Path):
        xml_path = _write_xml(tmp_path, """
            <node componentName="tFileInputDelimited">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="comp_A" />
            </node>
            <node componentName="tFileOutputDelimited">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="comp_B" />
            </node>
            <connection connectorName="FLOW" label="row1" source="comp_A" target="comp_B">
              <elementParameter name="UNIQUE_NAME" value="row1" />
            </connection>
        """)
        job = XmlParser().parse(str(xml_path))

        flow_conns = [c for c in job.connections if c.connector_type == "FLOW"]
        assert len(flow_conns) == 1
        assert flow_conns[0].condition is None

    def test_subjob_ok_connection_has_no_condition(self, tmp_path: Path):
        xml_path = _write_xml(tmp_path, """
            <node componentName="tFileInputDelimited">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="comp_A" />
            </node>
            <node componentName="tFileInputDelimited">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="comp_B" />
            </node>
            <connection connectorName="SUBJOB_OK" label="OnSubjobOk" source="comp_A" target="comp_B">
              <elementParameter name="UNIQUE_NAME" value="trigger1" />
            </connection>
        """)
        job = XmlParser().parse(str(xml_path))

        trigger_conns = [c for c in job.connections if c.connector_type == "SUBJOB_OK"]
        assert len(trigger_conns) == 1
        assert trigger_conns[0].condition is None

    def test_run_if_without_condition_param(self, tmp_path: Path):
        """RUN_IF connection missing CONDITION elementParameter -> condition is None."""
        xml_path = _write_xml(tmp_path, """
            <node componentName="tFileInputDelimited">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="comp_A" />
            </node>
            <node componentName="tFileInputDelimited">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="comp_B" />
            </node>
            <connection connectorName="RUN_IF" label="If" source="comp_A" target="comp_B">
              <elementParameter field="TEXT" name="UNIQUE_NAME" value="if1" />
            </connection>
        """)
        job = XmlParser().parse(str(xml_path))

        run_if_conns = [c for c in job.connections if c.connector_type == "RUN_IF"]
        assert len(run_if_conns) == 1
        assert run_if_conns[0].condition is None


class TestTriggerMapper:
    """Tests for map_triggers function."""

    def test_subjob_ok_maps_to_on_success(self):
        conns = [
            TalendConnection(name="t1", source="A", target="B", connector_type="SUBJOB_OK"),
        ]
        result = map_triggers(conns)
        assert len(result.triggers) == 1
        assert result.triggers[0] == {
            "source": "A", "target": "B", "type": "on_success",
        }

    def test_subjob_error_maps_to_on_failure(self):
        conns = [
            TalendConnection(name="t1", source="A", target="B", connector_type="SUBJOB_ERROR"),
        ]
        result = map_triggers(conns)
        assert len(result.triggers) == 1
        assert result.triggers[0] == {
            "source": "A", "target": "B", "type": "on_failure",
        }

    def test_component_ok_maps_to_on_success(self):
        conns = [
            TalendConnection(name="t1", source="A", target="B", connector_type="COMPONENT_OK"),
        ]
        result = map_triggers(conns)
        assert len(result.triggers) == 1
        assert result.triggers[0] == {
            "source": "A", "target": "B", "type": "on_success",
        }

    def test_component_error_maps_to_on_failure(self):
        conns = [
            TalendConnection(name="t1", source="A", target="B", connector_type="COMPONENT_ERROR"),
        ]
        result = map_triggers(conns)
        assert len(result.triggers) == 1
        assert result.triggers[0] == {
            "source": "A", "target": "B", "type": "on_failure",
        }

    def test_run_if_maps_to_conditional_with_needs_review(self):
        conns = [
            TalendConnection(
                name="if1", source="A", target="B",
                connector_type="RUN_IF",
                condition='context.env.equals("PROD")',
            ),
        ]
        result = map_triggers(conns)
        assert len(result.triggers) == 1
        assert result.triggers[0] == {
            "source": "A", "target": "B", "type": "conditional",
            "condition": 'context.env.equals("PROD")',
        }
        # RunIf conditions must be flagged for review
        assert len(result.needs_review) == 1
        assert result.needs_review[0]["source"] == "A"
        assert result.needs_review[0]["target"] == "B"
        assert "RunIf" in result.needs_review[0]["reason"] or "review" in result.needs_review[0]["reason"].lower()
        assert result.needs_review[0]["raw_condition"] == 'context.env.equals("PROD")'

    def test_run_if_without_condition_warns(self):
        """RUN_IF with no condition -> still emit trigger but warn."""
        conns = [
            TalendConnection(
                name="if1", source="A", target="B",
                connector_type="RUN_IF",
                condition=None,
            ),
        ]
        result = map_triggers(conns)
        assert len(result.triggers) == 1
        assert result.triggers[0]["type"] == "conditional"
        assert result.triggers[0].get("condition") is None
        assert len(result.warnings) >= 1

    def test_data_connections_ignored(self):
        """FLOW, MAIN, REJECT, LOOKUP, FILTER, ITERATE are not triggers."""
        conns = [
            TalendConnection(name="r1", source="A", target="B", connector_type="FLOW"),
            TalendConnection(name="r2", source="A", target="B", connector_type="MAIN"),
            TalendConnection(name="r3", source="A", target="B", connector_type="REJECT"),
            TalendConnection(name="r4", source="A", target="B", connector_type="LOOKUP"),
            TalendConnection(name="r5", source="A", target="B", connector_type="FILTER"),
            TalendConnection(name="r6", source="A", target="B", connector_type="ITERATE"),
        ]
        result = map_triggers(conns)
        assert len(result.triggers) == 0
        assert len(result.warnings) == 0
        assert len(result.needs_review) == 0

    def test_mixed_connections(self):
        """Only trigger connections are extracted; data connections are ignored."""
        conns = [
            TalendConnection(name="r1", source="A", target="B", connector_type="FLOW"),
            TalendConnection(name="t1", source="A", target="C", connector_type="SUBJOB_OK"),
            TalendConnection(name="r2", source="B", target="D", connector_type="MAIN"),
            TalendConnection(name="t2", source="C", target="D", connector_type="SUBJOB_ERROR"),
        ]
        result = map_triggers(conns)
        assert len(result.triggers) == 2
        assert result.triggers[0]["type"] == "on_success"
        assert result.triggers[1]["type"] == "on_failure"

    def test_empty_connections(self):
        result = map_triggers([])
        assert len(result.triggers) == 0
        assert len(result.warnings) == 0
        assert len(result.needs_review) == 0

    def test_result_dataclass(self):
        result = TriggerMapperResult(
            triggers=[{"source": "A", "target": "B", "type": "on_success"}],
            warnings=["w1"],
            needs_review=[{"item": "r1"}],
        )
        assert len(result.triggers) == 1
        assert len(result.warnings) == 1
        assert len(result.needs_review) == 1


# ---------------------------------------------------------------------------
# Validator: trigger reference validation
# ---------------------------------------------------------------------------

from src.converters.talend_to_v2.validator import validate_v2_config


class TestValidatorTriggers:
    """Tests for trigger reference validation."""

    def test_valid_trigger_references(self):
        config = {
            "components": [
                {"id": "A", "type": "file_input_delimited", "config": {}},
                {"id": "B", "type": "file_input_delimited", "config": {}},
            ],
            "flows": [],
            "triggers": [
                {"source": "A", "target": "B", "type": "on_success"},
            ],
        }
        report = validate_v2_config(config)
        trigger_errors = [
            i for i in report.issues
            if i.field == "triggers" and i.severity == "error"
        ]
        assert len(trigger_errors) == 0

    def test_trigger_with_invalid_source(self):
        config = {
            "components": [
                {"id": "B", "type": "file_input_delimited", "config": {}},
            ],
            "flows": [],
            "triggers": [
                {"source": "MISSING", "target": "B", "type": "on_success"},
            ],
        }
        report = validate_v2_config(config)
        trigger_errors = [
            i for i in report.issues
            if i.field == "triggers" and i.severity == "error"
        ]
        assert len(trigger_errors) == 1
        assert "MISSING" in trigger_errors[0].message

    def test_trigger_with_invalid_target(self):
        config = {
            "components": [
                {"id": "A", "type": "file_input_delimited", "config": {}},
            ],
            "flows": [],
            "triggers": [
                {"source": "A", "target": "MISSING", "type": "on_success"},
            ],
        }
        report = validate_v2_config(config)
        trigger_errors = [
            i for i in report.issues
            if i.field == "triggers" and i.severity == "error"
        ]
        assert len(trigger_errors) == 1
        assert "MISSING" in trigger_errors[0].message

    def test_no_triggers_no_errors(self):
        config = {
            "components": [
                {"id": "A", "type": "file_input_delimited", "config": {}},
            ],
            "flows": [],
            "triggers": [],
        }
        report = validate_v2_config(config)
        trigger_errors = [
            i for i in report.issues
            if i.field == "triggers" and i.severity == "error"
        ]
        assert len(trigger_errors) == 0

    def test_config_without_triggers_key(self):
        """Configs without a triggers key (pre-existing) don't error."""
        config = {
            "components": [
                {"id": "A", "type": "file_input_delimited", "config": {}},
            ],
            "flows": [],
        }
        report = validate_v2_config(config)
        trigger_errors = [
            i for i in report.issues
            if i.field == "triggers" and i.severity == "error"
        ]
        assert len(trigger_errors) == 0

    def test_orphan_check_considers_triggers(self):
        """Components referenced only by triggers should NOT be flagged as orphans."""
        config = {
            "components": [
                {"id": "A", "type": "file_input_delimited", "config": {}},
                {"id": "B", "type": "file_input_delimited", "config": {}},
            ],
            "flows": [],
            "triggers": [
                {"source": "A", "target": "B", "type": "on_success"},
            ],
        }
        report = validate_v2_config(config)
        orphan_warnings = [
            i for i in report.issues
            if "Orphan" in i.message
        ]
        assert len(orphan_warnings) == 0
