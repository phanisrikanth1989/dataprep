"""Tests for JavaFlexConverter -- parses the real Job_tJavaFlex_0.1.item fixture."""
from src.converters.talend_to_v1.xml_parser import XmlParser
from src.converters.talend_to_v1.components.transform.java_flex import JavaFlexConverter
from src.converters.talend_to_v1.components.base import TalendNode, TalendConnection


def _node_and_conns():
    job = XmlParser().parse("tests/talend_xml_samples/Job_tJavaFlex_0.1.item")
    node = next(n for n in job.nodes if n.component_type == "tJavaFlex")
    return node, job.connections


def _make_node(params=None):
    """Return a minimal TalendNode with no schema columns."""
    return TalendNode(
        component_id="tJavaFlex_1",
        component_type="tJavaFlex",
        params=params or {},
        schema={},
    )


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


# ---------------------------------------------------------------------------
# Task-8: synthetic-node tests covering lines 65-66, 68, 83
# ---------------------------------------------------------------------------

def test_propagate_timing_v3_2_true_sets_after():
    """Lines 65-66: Version_V3_2=true (and V4.0 false) -> propagate_timing='after'."""
    node = _make_node({"Version_V4.0": "false", "Version_V3_2": "true"})
    result = JavaFlexConverter().convert(node, [], {})
    assert result.component["config"]["propagate_timing"] == "after"


def test_propagate_timing_neither_flag_sets_before():
    """Line 68: neither V4.0 nor V3_2 -> propagate_timing defaults to 'before'."""
    node = _make_node({"Version_V4.0": "false", "Version_V3_2": "false"})
    result = JavaFlexConverter().convert(node, [], {})
    assert result.component["config"]["propagate_timing"] == "before"


def test_multiple_output_flows_adds_needs_review():
    """Line 83: >1 outgoing FLOW connections -> needs_review entry with severity='multi_output'."""
    node = _make_node()
    conns = [
        TalendConnection(name="row2", source="tJavaFlex_1", target="tLogRow_1", connector_type="FLOW"),
        TalendConnection(name="row3", source="tJavaFlex_1", target="tLogRow_2", connector_type="FLOW"),
    ]
    result = JavaFlexConverter().convert(node, conns, {})
    review_entries = result.needs_review
    assert any(e.get("severity") == "multi_output" for e in review_entries)
