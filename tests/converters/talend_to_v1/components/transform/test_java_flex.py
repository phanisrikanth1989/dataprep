"""Tests for JavaFlexConverter -- parses the real Job_tJavaFlex_0.1.item fixture."""
from src.converters.talend_to_v1.xml_parser import XmlParser
from src.converters.talend_to_v1.components.transform.java_flex import JavaFlexConverter


def _node_and_conns():
    job = XmlParser().parse("tests/talend_xml_samples/Job_tJavaFlex_0.1.item")
    node = next(n for n in job.nodes if n.component_type == "tJavaFlex")
    return node, job.connections


def test_extracts_code_sections_and_flags():
    node, conns = _node_and_conns()
    cfg = JavaFlexConverter().convert(node, conns, {}).component["config"]
    assert "int totalCount = 0;" in cfg["code_start"]
    assert "row2.customer_id = customerId;" in cfg["code_main"]
    assert "Total records" in cfg["code_end"]
    assert cfg["auto_propagate"] is True
    assert cfg["propagate_timing"] == "before"      # Version_V4.0 true
    assert cfg["imports"].startswith("//import")


def test_derives_row_names_from_connections():        # the NEW, untested logic
    node, conns = _node_and_conns()
    cfg = JavaFlexConverter().convert(node, conns, {}).component["config"]
    assert cfg["input_row_name"] == "row1"            # incoming FLOW .name
    assert cfg["output_row_name"] == "row2"           # outgoing FLOW .name


def test_output_schema_adds_columns_and_input_key_present():
    node, conns = _node_and_conns()
    comp = JavaFlexConverter().convert(node, conns, {}).component
    out_names = [c["name"] for c in comp["schema"]["output"]]
    for added in ("status", "processed_time", "error_reason", "is_valid"):
        assert added in out_names
    assert "input" in comp["schema"]                  # MUST exist for propagation
