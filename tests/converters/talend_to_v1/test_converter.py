"""Tests for talend_to_v1.converter — TalendToV1Converter orchestrator."""
from __future__ import annotations

import json
import os
import tempfile
import textwrap
from typing import Any, Dict, List
from unittest.mock import patch, MagicMock

import pytest

from src.converters.talend_to_v1.components.base import (
    ComponentConverter,
    ComponentResult,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.registry import REGISTRY
from src.converters.talend_to_v1.converter import (
    TalendToV1Converter,
    convert_job,
)
from src.converters.talend_to_v1.xml_parser import TalendJob


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_node(
    component_id: str,
    component_type: str = "tLogRow",
    params: Dict[str, Any] | None = None,
) -> TalendNode:
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema={},
        position={"x": 0, "y": 0},
        raw_xml=None,
    )


def _make_connection(
    name: str,
    source: str,
    target: str,
    connector_type: str = "FLOW",
    condition: str | None = None,
) -> TalendConnection:
    return TalendConnection(
        name=name,
        source=source,
        target=target,
        connector_type=connector_type,
        condition=condition,
    )


def _make_job(
    job_name: str = "TestJob",
    nodes: List[TalendNode] | None = None,
    connections: List[TalendConnection] | None = None,
    context: Dict[str, Dict[str, Any]] | None = None,
    routines: List[str] | None = None,
    libraries: List[str] | None = None,
) -> TalendJob:
    return TalendJob(
        job_name=job_name,
        job_type="Standard",
        default_context="Default",
        context=context or {"Default": {}},
        nodes=nodes or [],
        connections=connections or [],
        routines=routines or [],
        libraries=libraries or [],
    )


def _write_item(xml_text: str) -> str:
    """Write XML to a temp .item file and return the path."""
    fd, path = tempfile.mkstemp(suffix=".item")
    os.write(fd, textwrap.dedent(xml_text).encode("utf-8"))
    os.close(fd)
    return path


_JOB_WRAP = (
    '<ProcessType xmlns:xmi="http://www.omg.org/XMI" '
    'jobType="Standard" defaultContext="Default">'
    "{body}"
    "</ProcessType>"
)


def _job_xml(body: str) -> str:
    return _JOB_WRAP.format(body=body)


# ---------------------------------------------------------------------------
# 1. Zero registered converters -> all components get _unsupported: true
# ---------------------------------------------------------------------------

class TestUnsupportedFallback:
    def test_unknown_component_gets_unsupported_placeholder(self):
        """When no converter is registered, the component gets _unsupported."""
        job = _make_job(nodes=[
            _make_node("comp_1", "tUnknownComponent"),
            _make_node("comp_2", "tAnotherUnknown"),
        ])

        converter = TalendToV1Converter()

        with patch.object(converter, "_parser") as mock_parser:
            mock_parser.parse.return_value = job

            config = converter.convert_file("dummy.item")

        assert len(config["components"]) == 2
        for comp in config["components"]:
            assert comp["_unsupported"] is True
            assert comp["inputs"] == []
            assert comp["outputs"] == []

    def test_converter_error_produces_unsupported_placeholder(self):
        """When a converter raises, the component becomes an unsupported placeholder."""
        node = _make_node("err_comp", "tBrokenComponent")
        job = _make_job(nodes=[node])

        # Register a converter that will raise
        class _BrokenConverter(ComponentConverter):
            def convert(self, node, connections, context):
                raise RuntimeError("boom")

        converter = TalendToV1Converter()

        with patch.object(converter, "_parser") as mock_parser, \
             patch.object(REGISTRY, "get", return_value=_BrokenConverter):
            mock_parser.parse.return_value = job
            config = converter.convert_file("dummy.item")

        comp = config["components"][0]
        assert comp["_unsupported"] is True
        assert comp["id"] == "err_comp"


# ---------------------------------------------------------------------------
# 2. Flow parsing from connections (FLOW, REJECT types)
# ---------------------------------------------------------------------------

class TestFlowParsing:
    def test_flow_connections_parsed(self):
        """FLOW connections produce flow entries."""
        connections = [
            _make_connection("row1", "A", "B", "FLOW"),
            _make_connection("row2", "B", "C", "REJECT"),
        ]
        flows = TalendToV1Converter._parse_flows(connections)

        assert len(flows) == 2
        assert flows[0] == {"name": "row1", "from": "A", "to": "B", "type": "flow"}
        assert flows[1] == {"name": "row2", "from": "B", "to": "C", "type": "reject"}

    def test_trigger_connections_excluded_from_flows(self):
        """Trigger connections (SUBJOB_OK, etc.) are NOT included in flows."""
        connections = [
            _make_connection("row1", "A", "B", "FLOW"),
            _make_connection("trigger1", "A", "C", "SUBJOB_OK"),
            _make_connection("trigger2", "A", "D", "COMPONENT_OK"),
        ]
        flows = TalendToV1Converter._parse_flows(connections)

        assert len(flows) == 1
        assert flows[0]["name"] == "row1"

    def test_all_flow_connector_types(self):
        """All recognized flow connector types produce flows."""
        flow_types = ["FLOW", "MAIN", "REJECT", "FILTER", "UNIQUE", "DUPLICATE", "ITERATE"]
        connections = [
            _make_connection(f"row_{ct.lower()}", "A", "B", ct)
            for ct in flow_types
        ]
        flows = TalendToV1Converter._parse_flows(connections)
        assert len(flows) == len(flow_types)
        for i, ct in enumerate(flow_types):
            assert flows[i]["type"] == ct.lower()

    def test_empty_source_or_target_skipped(self):
        """Connections with empty source or target are skipped."""
        connections = [
            _make_connection("row1", "", "B", "FLOW"),
            _make_connection("row2", "A", "", "FLOW"),
        ]
        flows = TalendToV1Converter._parse_flows(connections)
        assert len(flows) == 0


# ---------------------------------------------------------------------------
# 3. Component inputs/outputs populated from flows
# ---------------------------------------------------------------------------

class TestComponentConnectionsUpdate:
    def test_inputs_outputs_populated(self):
        """Flow adds flow name to source outputs and target inputs."""
        comp_a = {"id": "A", "inputs": [], "outputs": []}
        comp_b = {"id": "B", "inputs": [], "outputs": []}
        components_map = {"A": comp_a, "B": comp_b}
        flow = {"name": "row1", "from": "A", "to": "B", "type": "flow"}

        TalendToV1Converter._update_component_connections(components_map, flow)

        assert "row1" in comp_a["outputs"]
        assert "row1" in comp_b["inputs"]

    def test_no_duplicate_entries(self):
        """Calling update twice with the same flow doesn't duplicate entries."""
        comp_a = {"id": "A", "inputs": [], "outputs": []}
        comp_b = {"id": "B", "inputs": [], "outputs": []}
        components_map = {"A": comp_a, "B": comp_b}
        flow = {"name": "row1", "from": "A", "to": "B", "type": "flow"}

        TalendToV1Converter._update_component_connections(components_map, flow)
        TalendToV1Converter._update_component_connections(components_map, flow)

        assert comp_a["outputs"].count("row1") == 1
        assert comp_b["inputs"].count("row1") == 1

    def test_missing_component_ignored(self):
        """References to components not in the map are silently ignored."""
        components_map = {"A": {"id": "A", "inputs": [], "outputs": []}}
        flow = {"name": "row1", "from": "A", "to": "MISSING", "type": "flow"}

        # Should not raise
        TalendToV1Converter._update_component_connections(components_map, flow)
        assert "row1" in components_map["A"]["outputs"]

    def test_end_to_end_inputs_outputs(self):
        """Full pipeline populates inputs/outputs from parsed flows."""
        nodes = [
            _make_node("A", "tLogRow"),
            _make_node("B", "tLogRow"),
        ]
        connections = [
            _make_connection("row1", "A", "B", "FLOW"),
        ]
        job = _make_job(nodes=nodes, connections=connections)

        converter = TalendToV1Converter()
        with patch.object(converter, "_parser") as mock_parser:
            mock_parser.parse.return_value = job
            config = converter.convert_file("dummy.item")

        comp_a = next(c for c in config["components"] if c["id"] == "A")
        comp_b = next(c for c in config["components"] if c["id"] == "B")

        assert "row1" in comp_a["outputs"]
        assert "row1" in comp_b["inputs"]


# ---------------------------------------------------------------------------
# 4. Subjob detection (2 connected components = 1 subjob)
# ---------------------------------------------------------------------------

class TestSubjobDetection:
    def test_two_connected_components_one_subjob(self):
        """Two components linked by a flow form one subjob."""
        components_map = {
            "A": {"id": "A"},
            "B": {"id": "B"},
        }
        flows = [{"name": "row1", "from": "A", "to": "B", "type": "flow"}]

        subjobs = TalendToV1Converter._detect_subjobs(components_map, flows)

        assert len(subjobs) == 1
        members = list(subjobs.values())[0]
        assert set(members) == {"A", "B"}

    def test_isolated_components_separate_subjobs(self):
        """Disconnected components each become their own subjob."""
        components_map = {
            "A": {"id": "A"},
            "B": {"id": "B"},
            "C": {"id": "C"},
        }
        flows: List[Dict[str, Any]] = []

        subjobs = TalendToV1Converter._detect_subjobs(components_map, flows)

        assert len(subjobs) == 3

    def test_chain_of_three_one_subjob(self):
        """A -> B -> C all belong to one subjob."""
        components_map = {
            "A": {"id": "A"},
            "B": {"id": "B"},
            "C": {"id": "C"},
        }
        flows = [
            {"name": "row1", "from": "A", "to": "B", "type": "flow"},
            {"name": "row2", "from": "B", "to": "C", "type": "flow"},
        ]

        subjobs = TalendToV1Converter._detect_subjobs(components_map, flows)

        assert len(subjobs) == 1
        members = list(subjobs.values())[0]
        assert set(members) == {"A", "B", "C"}

    def test_two_separate_chains(self):
        """Two disjoint chains produce two subjobs."""
        components_map = {
            "A": {"id": "A"},
            "B": {"id": "B"},
            "C": {"id": "C"},
            "D": {"id": "D"},
        }
        flows = [
            {"name": "row1", "from": "A", "to": "B", "type": "flow"},
            {"name": "row2", "from": "C", "to": "D", "type": "flow"},
        ]

        subjobs = TalendToV1Converter._detect_subjobs(components_map, flows)

        assert len(subjobs) == 2


# ---------------------------------------------------------------------------
# 5. Java detection (JavaRowComponent type -> enabled=True)
# ---------------------------------------------------------------------------

class TestJavaDetectionByType:
    @pytest.mark.parametrize("java_type", [
        "tJavaRow", "tJava", "JavaRowComponent",
        "JavaComponent", "JavaRow", "Java",
    ])
    def test_java_component_type_detected(self, java_type: str):
        """Components with Java types are detected."""
        components = [
            {"id": "comp1", "type": java_type, "config": {}},
        ]
        assert TalendToV1Converter._detect_java_requirement(components) is True

    def test_non_java_type_not_detected(self):
        """Standard component types do NOT require Java."""
        components = [
            {"id": "comp1", "type": "tLogRow", "config": {}},
            {"id": "comp2", "type": "tFileInputDelimited", "config": {}},
        ]
        assert TalendToV1Converter._detect_java_requirement(components) is False


# ---------------------------------------------------------------------------
# 6. Java detection (config with {{java}} marker -> enabled=True)
# ---------------------------------------------------------------------------

class TestJavaDetectionByMarker:
    def test_java_marker_in_config_string(self):
        """A {{java}} marker in config triggers Java requirement."""
        components = [
            {
                "id": "comp1",
                "type": "tLogRow",
                "config": {"expression": "{{java}}some.method()"},
            },
        ]
        assert TalendToV1Converter._detect_java_requirement(components) is True

    def test_java_marker_in_nested_config(self):
        """A {{java}} marker nested deep in config is found."""
        components = [
            {
                "id": "comp1",
                "type": "tLogRow",
                "config": {
                    "level1": {
                        "level2": ["{{java}}routine.call()"]
                    }
                },
            },
        ]
        assert TalendToV1Converter._detect_java_requirement(components) is True

    def test_no_java_marker_not_detected(self):
        """Config without {{java}} markers does not require Java."""
        components = [
            {
                "id": "comp1",
                "type": "tLogRow",
                "config": {"expression": "plain value"},
            },
        ]
        assert TalendToV1Converter._detect_java_requirement(components) is False

    def test_has_java_expressions_recursive(self):
        """_has_java_expressions scans dicts, lists, and strings."""
        assert TalendToV1Converter._has_java_expressions("{{java}}x") is True
        assert TalendToV1Converter._has_java_expressions("plain") is False
        assert TalendToV1Converter._has_java_expressions({"k": "{{java}}x"}) is True
        assert TalendToV1Converter._has_java_expressions(["{{java}}x"]) is True
        assert TalendToV1Converter._has_java_expressions(42) is False
        assert TalendToV1Converter._has_java_expressions(None) is False


# ---------------------------------------------------------------------------
# 7. Context conversion (type mapping applied)
# ---------------------------------------------------------------------------

class TestContextConversion:
    def test_context_passthrough(self):
        """Context conversion returns the same structure (already mapped)."""
        context = {
            "Default": {
                "db_host": {"value": "localhost", "type": "str"},
                "db_port": {"value": "5432", "type": "int"},
            }
        }
        result = TalendToV1Converter._convert_context(context)
        assert result == context

    def test_context_in_full_pipeline(self):
        """Context variables appear in the output config."""
        job = _make_job(
            context={
                "Default": {
                    "host": {"value": "localhost", "type": "str"},
                    "port": {"value": "5432", "type": "int"},
                }
            },
        )

        converter = TalendToV1Converter()
        with patch.object(converter, "_parser") as mock_parser:
            mock_parser.parse.return_value = job
            config = converter.convert_file("dummy.item")

        assert "Default" in config["context"]
        assert config["context"]["Default"]["host"]["type"] == "str"
        assert config["context"]["Default"]["port"]["type"] == "int"


# ---------------------------------------------------------------------------
# 8. Trigger integration (triggers present in output)
# ---------------------------------------------------------------------------

class TestTriggerIntegration:
    def test_triggers_in_output(self):
        """Trigger connections appear in the output config."""
        nodes = [
            _make_node("A", "tLogRow"),
            _make_node("B", "tLogRow"),
        ]
        connections = [
            _make_connection("trigger1", "A", "B", "SUBJOB_OK"),
        ]
        job = _make_job(nodes=nodes, connections=connections)

        converter = TalendToV1Converter()
        with patch.object(converter, "_parser") as mock_parser:
            mock_parser.parse.return_value = job
            config = converter.convert_file("dummy.item")

        assert len(config["triggers"]) == 1
        trigger = config["triggers"][0]
        assert trigger["type"] == "OnSubjobOk"
        assert trigger["from"] == "A"
        assert trigger["to"] == "B"

    def test_trigger_for_missing_component_filtered(self):
        """Triggers referencing non-existent components are filtered out."""
        nodes = [_make_node("A", "tLogRow")]
        connections = [
            _make_connection("trigger1", "A", "NONEXISTENT", "SUBJOB_OK"),
        ]
        job = _make_job(nodes=nodes, connections=connections)

        converter = TalendToV1Converter()
        with patch.object(converter, "_parser") as mock_parser:
            mock_parser.parse.return_value = job
            config = converter.convert_file("dummy.item")

        assert len(config["triggers"]) == 0


# ---------------------------------------------------------------------------
# 9. Validation report attached
# ---------------------------------------------------------------------------

class TestValidationReport:
    def test_validation_report_present(self):
        """Output config has a _validation key with valid/summary/issues."""
        job = _make_job(nodes=[_make_node("A", "tLogRow")])

        converter = TalendToV1Converter()
        with patch.object(converter, "_parser") as mock_parser:
            mock_parser.parse.return_value = job
            config = converter.convert_file("dummy.item")

        assert "_validation" in config
        assert "valid" in config["_validation"]
        assert "summary" in config["_validation"]
        assert "issues" in config["_validation"]

    def test_validation_issues_contain_fields(self):
        """Each issue dict has severity, component_id, field, message."""
        job = _make_job(nodes=[_make_node("A", "tLogRow")])

        converter = TalendToV1Converter()
        with patch.object(converter, "_parser") as mock_parser:
            mock_parser.parse.return_value = job
            config = converter.convert_file("dummy.item")

        for issue in config["_validation"]["issues"]:
            assert "severity" in issue
            assert "component_id" in issue
            assert "field" in issue
            assert "message" in issue


# ---------------------------------------------------------------------------
# 10. convert_job convenience function
# ---------------------------------------------------------------------------

class TestConvertJobConvenience:
    def test_convert_job_returns_config(self):
        """convert_job returns a valid config dict."""
        xml = _job_xml(
            '<node componentName="tLogRow" posX="100" posY="200">'
            '  <elementParameter name="UNIQUE_NAME" value="tLogRow_1" field="TEXT"/>'
            "</node>"
        )
        path = _write_item(xml)
        try:
            config = convert_job(path)
            assert config["job_name"] is not None
            assert "components" in config
            assert "flows" in config
            assert "triggers" in config
        finally:
            os.unlink(path)

    def test_convert_job_writes_output_file(self):
        """convert_job with output_path writes JSON to disk."""
        xml = _job_xml(
            '<node componentName="tLogRow" posX="100" posY="200">'
            '  <elementParameter name="UNIQUE_NAME" value="tLogRow_1" field="TEXT"/>'
            "</node>"
        )
        path = _write_item(xml)
        fd, out_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            config = convert_job(path, output_path=out_path)
            assert os.path.exists(out_path)
            with open(out_path) as f:
                loaded = json.load(f)
            assert loaded["job_name"] is not None
            assert loaded["components"] == config["components"]
        finally:
            os.unlink(path)
            os.unlink(out_path)


# ---------------------------------------------------------------------------
# Full pipeline integration tests
# ---------------------------------------------------------------------------

class TestFullPipeline:
    def test_output_shape(self):
        """Output config has all required top-level keys."""
        job = _make_job(
            nodes=[_make_node("A", "tLogRow")],
        )

        converter = TalendToV1Converter()
        with patch.object(converter, "_parser") as mock_parser:
            mock_parser.parse.return_value = job
            config = converter.convert_file("dummy.item")

        expected_keys = {
            "job_name", "job_type", "default_context", "context",
            "components", "flows", "triggers", "subjobs", "java_config",
            "_validation",
        }
        assert expected_keys.issubset(set(config.keys()))

    def test_java_config_structure(self):
        """java_config has enabled, routines, and libraries keys."""
        job = _make_job(
            routines=["routines.DataOperation"],
            libraries=["mysql-connector.jar"],
        )

        converter = TalendToV1Converter()
        with patch.object(converter, "_parser") as mock_parser:
            mock_parser.parse.return_value = job
            config = converter.convert_file("dummy.item")

        jc = config["java_config"]
        assert jc["enabled"] is False
        assert jc["routines"] == ["routines.DataOperation"]
        assert jc["libraries"] == ["mysql-connector.jar"]

    def test_java_enabled_for_java_component(self):
        """java_config.enabled is True when a Java component is present."""
        job = _make_job(
            nodes=[_make_node("java_1", "JavaRowComponent")],
        )

        converter = TalendToV1Converter()
        with patch.object(converter, "_parser") as mock_parser:
            mock_parser.parse.return_value = job
            config = converter.convert_file("dummy.item")

        assert config["java_config"]["enabled"] is True

    def test_multiple_flows_and_subjobs(self):
        """Multiple flows produce correct subjob groupings."""
        nodes = [
            _make_node("A"), _make_node("B"),
            _make_node("C"), _make_node("D"),
        ]
        connections = [
            _make_connection("row1", "A", "B", "FLOW"),
            _make_connection("row2", "C", "D", "MAIN"),
        ]
        job = _make_job(nodes=nodes, connections=connections)

        converter = TalendToV1Converter()
        with patch.object(converter, "_parser") as mock_parser:
            mock_parser.parse.return_value = job
            config = converter.convert_file("dummy.item")

        assert len(config["flows"]) == 2
        assert len(config["subjobs"]) == 2

    def test_end_to_end_xml_parse(self):
        """Full end-to-end: XML file -> parsed -> converted."""
        xml = _job_xml(
            '<context name="Default">'
            '  <contextParameter name="host" type="id_String" value="&quot;localhost&quot;" />'
            "</context>"
            '<node componentName="tFileInputDelimited" posX="100" posY="100">'
            '  <elementParameter name="UNIQUE_NAME" value="tFileInputDelimited_1" field="TEXT"/>'
            '  <elementParameter name="FILENAME" value="&quot;data.csv&quot;" field="TEXT"/>'
            "</node>"
            '<node componentName="tLogRow" posX="300" posY="100">'
            '  <elementParameter name="UNIQUE_NAME" value="tLogRow_1" field="TEXT"/>'
            "</node>"
            '<connection source="tFileInputDelimited_1" target="tLogRow_1" '
            '  connectorName="FLOW" label="row1">'
            '  <elementParameter name="UNIQUE_NAME" value="row1" field="TEXT"/>'
            "</connection>"
        )
        path = _write_item(xml)
        try:
            config = convert_job(path)

            # Check components
            assert len(config["components"]) == 2
            ids = {c["id"] for c in config["components"]}
            assert ids == {"tFileInputDelimited_1", "tLogRow_1"}

            # Check flows
            assert len(config["flows"]) == 1
            assert config["flows"][0]["from"] == "tFileInputDelimited_1"
            assert config["flows"][0]["to"] == "tLogRow_1"

            # Check inputs/outputs
            src = next(c for c in config["components"] if c["id"] == "tFileInputDelimited_1")
            tgt = next(c for c in config["components"] if c["id"] == "tLogRow_1")
            assert "row1" in src["outputs"]
            assert "row1" in tgt["inputs"]

            # Check subjobs
            assert len(config["subjobs"]) == 1

            # Check context
            assert config["context"]["Default"]["host"]["value"] == "localhost"
            assert config["context"]["Default"]["host"]["type"] == "str"

        finally:
            os.unlink(path)
