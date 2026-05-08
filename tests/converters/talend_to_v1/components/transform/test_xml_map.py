"""Tests for XMLMapConverter (tXMLMap -> v1 XMLMap config)."""
import inspect
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.registry import REGISTRY
from src.converters.talend_to_v1.components.transform.xml_map import XMLMapConverter


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_raw_xml(
    *,
    input_trees_xml: str = "",
    output_trees_xml: str = "",
    connections_xml: str = "",
    var_tables_xml: str = "",
    metadata_xml: str = "",
) -> ET.Element:
    """Build a minimal raw_xml Element that mimics a Talend tXMLMap node.

    The nodeData block is assembled from the XML snippet parameters.
    Metadata (for output schema) is appended separately.
    """
    root = ET.Element("node", attrib={
        "componentName": "tXMLMap",
        "componentVersion": "0.1",
    })

    # nodeData
    node_data_str = (
        f"<nodeData>"
        f"  {input_trees_xml}"
        f"  {output_trees_xml}"
        f"  {connections_xml}"
        f"  {var_tables_xml}"
        f"</nodeData>"
    )
    node_data_elem = ET.fromstring(node_data_str)
    root.append(node_data_elem)

    # metadata (FLOW connector for output schema)
    if metadata_xml:
        metadata_elem = ET.fromstring(metadata_xml)
        root.append(metadata_elem)

    return root


def _make_node(params=None, schema=None, component_id="xm_1",
               component_type="tXMLMap", raw_xml=None):
    """Create a TalendNode for tXMLMap testing."""
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 100, "y": 200},
        raw_xml=raw_xml,
    )


def _make_schema_columns():
    """Return a sample FLOW schema for testing."""
    return {
        "FLOW": [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True, length=10),
            SchemaColumn(name="name", type="id_String", nullable=True, length=50),
        ]
    }


def _convert(params=None, schema=None, raw_xml=None, connections=None):
    """Shortcut: build node + convert in one call."""
    node = _make_node(params=params, schema=schema, raw_xml=raw_xml)
    return XMLMapConverter().convert(node, connections or [], {})


# ------------------------------------------------------------------
# Standard XML snippets for reuse
# ------------------------------------------------------------------

_SIMPLE_INPUT_TREE = (
    '<inputTrees name="row1" matchingMode="ALL_ROWS" lookupMode="LOAD_ONCE" lookup="false">'
    '  <nodes name="doc" expression="row1.payload" type="id_Document" xpath="/">'
    '    <children name="root" type="id_String" xpath="root" nodeType="ELEMENT" loop="false" main="false">'
    '      <children name="item" type="id_String" xpath="item" nodeType="ELEMENT" loop="true" main="false">'
    '        <children name="id" type="id_String" xpath="id" nodeType="ELEMENT" loop="false" main="false" />'
    '        <children name="name" type="id_String" xpath="name" nodeType="ELEMENT" loop="false" main="false" />'
    '      </children>'
    '    </children>'
    '  </nodes>'
    '</inputTrees>'
)

_LOOKUP_INPUT_TREE = (
    '<inputTrees name="lookup1" matchingMode="ALL_ROWS" lookupMode="LOAD_ONCE" lookup="true">'
    '  <nodes name="ref_doc" expression="lookup1.ref" type="id_Document" xpath="/">'
    '    <children name="ref_root" type="id_String" xpath="ref_root" nodeType="ELEMENT" loop="false" main="false">'
    '      <children name="ref_item" type="id_String" xpath="ref_item" nodeType="ELEMENT" loop="true" main="false">'
    '        <children name="ref_id" type="id_String" xpath="ref_id" nodeType="ELEMENT" loop="false" main="false" />'
    '      </children>'
    '    </children>'
    '  </nodes>'
    '</inputTrees>'
)

_SIMPLE_OUTPUT_TREE = (
    '<outputTrees name="out1" expressionFilter="row1.status == 1" activateExpressionFilter="true">'
    '  <nodes name="id" expression="" type="id_String" xpath="id" />'
    '  <nodes name="name" expression="" type="id_String" xpath="name" />'
    '</outputTrees>'
)

_SIMPLE_CONNECTIONS = (
    '<connections source="inputTrees.0/@nodes.0/@children.0/@children.0/@children.0" '
    '            target="outputTrees.0/@nodes.0" sourceExpression="" />'
    '<connections source="inputTrees.0/@nodes.0/@children.0/@children.0/@children.1" '
    '            target="outputTrees.0/@nodes.1" sourceExpression="" />'
)

_SIMPLE_METADATA = (
    '<metadata connector="FLOW" name="out1">'
    '  <column name="id" type="id_String" nullable="true" key="false" length="50" precision="-1" />'
    '  <column name="name" type="id_String" nullable="true" key="false" length="100" precision="-1" />'
    '</metadata>'
)

_VAR_TABLES = (
    '<varTables name="Var" minimized="false" />'
)


# ==================================================================
# Test Classes
# ==================================================================


class TestRegistration:
    """Verify tXMLMap is registered in the converter registry."""

    def test_registered_in_registry(self):
        """REGISTRY.get('tXMLMap') returns XMLMapConverter."""
        assert REGISTRY.get("tXMLMap") is XMLMapConverter


class TestDefaults:
    """Verify default values for flat params and framework params."""

    def test_die_on_error_default_true(self):
        """DIE_ON_ERROR defaults to True when absent."""
        raw_xml = _make_raw_xml()
        result = _convert(raw_xml=raw_xml)
        assert result.component["config"]["die_on_error"] is True

    def test_keep_order_for_document_default_false(self):
        """KEEP_ORDER_FOR_DOCUMENT defaults to False when absent."""
        raw_xml = _make_raw_xml()
        result = _convert(raw_xml=raw_xml)
        assert result.component["config"]["keep_order_for_document"] is False

    def test_tstatcatcher_stats_default_false(self):
        """TSTATCATCHER_STATS defaults to False when absent."""
        raw_xml = _make_raw_xml()
        result = _convert(raw_xml=raw_xml)
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        """LABEL defaults to empty string when absent."""
        raw_xml = _make_raw_xml()
        result = _convert(raw_xml=raw_xml)
        assert result.component["config"]["label"] == ""


class TestParameterExtraction:
    """Verify parameter extraction from explicit param values."""

    def test_die_on_error_false(self):
        """DIE_ON_ERROR='false' -> die_on_error=False."""
        raw_xml = _make_raw_xml()
        result = _convert(params={"DIE_ON_ERROR": "false"}, raw_xml=raw_xml)
        assert result.component["config"]["die_on_error"] is False

    def test_keep_order_true(self):
        """KEEP_ORDER_FOR_DOCUMENT='true' -> keep_order_for_document=True."""
        raw_xml = _make_raw_xml()
        result = _convert(params={"KEEP_ORDER_FOR_DOCUMENT": "true"}, raw_xml=raw_xml)
        assert result.component["config"]["keep_order_for_document"] is True


class TestMultiFlow:
    """Multi-flow nodeData parsing scenarios per D-75."""

    def test_main_input_tree(self):
        """Single main inputTree with nested children is parsed correctly."""
        raw_xml = _make_raw_xml(
            input_trees_xml=_SIMPLE_INPUT_TREE,
            metadata_xml=_SIMPLE_METADATA,
        )
        result = _convert(raw_xml=raw_xml)
        cfg = result.component["config"]

        assert len(cfg["input_trees"]) == 1
        tree = cfg["input_trees"][0]
        assert tree["name"] == "row1"
        assert tree["lookup"] is False
        assert tree["matchingMode"] == "ALL_ROWS"
        assert len(tree["nodes"]) == 1
        # Recursive children parsed
        doc_node = tree["nodes"][0]
        assert doc_node["name"] == "doc"
        root_child = doc_node["children"][0]
        assert root_child["name"] == "root"
        item_child = root_child["children"][0]
        assert item_child["name"] == "item"
        assert item_child["loop"] is True
        assert len(item_child["children"]) == 2

    def test_main_plus_lookup(self):
        """Main + lookup inputTree (lookup='true') -> both parsed."""
        raw_xml = _make_raw_xml(
            input_trees_xml=_SIMPLE_INPUT_TREE + _LOOKUP_INPUT_TREE,
            metadata_xml=_SIMPLE_METADATA,
        )
        result = _convert(raw_xml=raw_xml)
        cfg = result.component["config"]

        assert len(cfg["input_trees"]) == 2
        main_tree = cfg["input_trees"][0]
        lookup_tree = cfg["input_trees"][1]
        assert main_tree["lookup"] is False
        assert lookup_tree["lookup"] is True
        assert lookup_tree["name"] == "lookup1"

    def test_output_tree_parsing(self):
        """OutputTree with nodes -> output_trees populated with expression filter."""
        raw_xml = _make_raw_xml(
            output_trees_xml=_SIMPLE_OUTPUT_TREE,
            metadata_xml=_SIMPLE_METADATA,
        )
        result = _convert(raw_xml=raw_xml)
        cfg = result.component["config"]

        assert len(cfg["output_trees"]) == 1
        tree = cfg["output_trees"][0]
        assert tree["name"] == "out1"
        assert tree["expressionFilter"] == "row1.status == 1"
        assert tree["activateExpressionFilter"] is True
        assert len(tree["nodes"]) == 2

    def test_connections_parsing(self):
        """Connections with source/target paths -> expressions list."""
        raw_xml = _make_raw_xml(
            input_trees_xml=_SIMPLE_INPUT_TREE,
            output_trees_xml=_SIMPLE_OUTPUT_TREE,
            connections_xml=_SIMPLE_CONNECTIONS,
            metadata_xml=_SIMPLE_METADATA,
        )
        result = _convert(raw_xml=raw_xml)
        cfg = result.component["config"]

        assert len(cfg["connections"]) == 2
        conn = cfg["connections"][0]
        assert "source" in conn
        assert "target" in conn
        # expressions derived from connections
        assert isinstance(cfg["expressions"], dict)
        assert len(cfg["expressions"]) > 0

    def test_looping_element(self):
        """InputTree with loop='true' on a child node -> looping_element detected."""
        raw_xml = _make_raw_xml(
            input_trees_xml=_SIMPLE_INPUT_TREE,
            metadata_xml=_SIMPLE_METADATA,
        )
        result = _convert(raw_xml=raw_xml)
        cfg = result.component["config"]

        assert cfg["looping_element"] == "item"

    def test_all_combined(self):
        """Full nodeData with input, lookup, output, connections, var -> all populated."""
        raw_xml = _make_raw_xml(
            input_trees_xml=_SIMPLE_INPUT_TREE + _LOOKUP_INPUT_TREE,
            output_trees_xml=_SIMPLE_OUTPUT_TREE,
            connections_xml=_SIMPLE_CONNECTIONS,
            var_tables_xml=_VAR_TABLES,
            metadata_xml=_SIMPLE_METADATA,
        )
        result = _convert(raw_xml=raw_xml)
        cfg = result.component["config"]

        # All tree structures populated
        assert len(cfg["input_trees"]) == 2
        assert len(cfg["output_trees"]) == 1
        assert len(cfg["connections"]) == 2
        assert len(cfg["var_tables"]) == 1
        assert cfg["var_tables"][0]["name"] == "Var"

        # Derived fields populated
        assert cfg["looping_element"] == "item"
        assert isinstance(cfg["expressions"], dict)
        assert len(cfg["output_schema"]) == 2

        # Framework params present
        assert "tstatcatcher_stats" in cfg
        assert "label" in cfg


class TestSchema:
    """Verify schema structure."""

    def test_schema_has_input_output(self):
        """Schema dict has 'input' and 'output' keys."""
        raw_xml = _make_raw_xml(metadata_xml=_SIMPLE_METADATA)
        result = _convert(schema=_make_schema_columns(), raw_xml=raw_xml)
        schema = result.component["schema"]
        assert "input" in schema
        assert "output" in schema


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_has_entries(self):
        """Per-feature needs_review entries exist for engine gaps."""
        raw_xml = _make_raw_xml(
            input_trees_xml=_SIMPLE_INPUT_TREE,
            output_trees_xml=_SIMPLE_OUTPUT_TREE,
            connections_xml=_SIMPLE_CONNECTIONS,
            metadata_xml=_SIMPLE_METADATA,
        )
        result = _convert(raw_xml=raw_xml)
        assert len(result.needs_review) > 0

    def test_needs_review_engine_gap_severity(self):
        """All needs_review entries have engine_gap or output_shape_change severity."""
        raw_xml = _make_raw_xml(
            input_trees_xml=_SIMPLE_INPUT_TREE,
            output_trees_xml=_SIMPLE_OUTPUT_TREE,
            connections_xml=_SIMPLE_CONNECTIONS,
            metadata_xml=_SIMPLE_METADATA,
        )
        result = _convert(raw_xml=raw_xml)
        valid_severities = {"engine_gap", "output_shape_change"}
        for entry in result.needs_review:
            assert entry["severity"] in valid_severities, (
                f"Unexpected severity: {entry['severity']} in {entry}"
            )


class TestNoLstripBug:
    """Verify D-76 compliance: no lstrip() usage in converter source."""

    def test_no_lstrip_in_converter(self):
        """Source code of xml_map.py does NOT contain '.lstrip(' -- uses removeprefix instead."""
        source = inspect.getsource(XMLMapConverter)
        assert ".lstrip(" not in source, (
            "Converter source contains .lstrip() -- use str.removeprefix() per D-76"
        )

    def test_no_lstrip_in_module(self):
        """Entire xml_map module has no .lstrip( calls."""
        import src.converters.talend_to_v1.components.transform.xml_map as mod
        source = inspect.getsource(mod)
        assert ".lstrip(" not in source, (
            "Module source contains .lstrip() -- use str.removeprefix() per D-76"
        )


class TestCompleteness:
    """Verify all config keys are present."""

    def test_all_config_keys_present(self):
        """Config has flat params + tree structures + framework."""
        raw_xml = _make_raw_xml(
            input_trees_xml=_SIMPLE_INPUT_TREE,
            output_trees_xml=_SIMPLE_OUTPUT_TREE,
            connections_xml=_SIMPLE_CONNECTIONS,
            var_tables_xml=_VAR_TABLES,
            metadata_xml=_SIMPLE_METADATA,
        )
        result = _convert(raw_xml=raw_xml)
        cfg = result.component["config"]

        expected_keys = {
            # Flat params
            "die_on_error",
            "keep_order_for_document",
            # nodeData tree structures
            "input_trees",
            "output_trees",
            "connections",
            "var_tables",
            # Derived from tree structures
            "output_schema",
            "expressions",
            "looping_element",
            "expression_filter",
            "activate_expression_filter",
            # Framework
            "tstatcatcher_stats",
            "label",
        }
        assert expected_keys.issubset(set(cfg.keys())), (
            f"Missing keys: {expected_keys - set(cfg.keys())}"
        )


class TestComponentStructure:
    """Verify component dict structure."""

    def test_has_type(self):
        """Component type is 'XMLMap'."""
        raw_xml = _make_raw_xml()
        result = _convert(raw_xml=raw_xml)
        assert result.component["type"] == "XMLMap"

    def test_has_original_type(self):
        """Component original_type is 'tXMLMap'."""
        raw_xml = _make_raw_xml()
        result = _convert(raw_xml=raw_xml)
        assert result.component["original_type"] == "tXMLMap"

    def test_has_standard_keys(self):
        """Component has all standard top-level keys from _build_component_dict."""
        raw_xml = _make_raw_xml()
        result = _convert(raw_xml=raw_xml)
        comp = result.component
        expected_keys = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(comp.keys()) == expected_keys

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        raw_xml = _make_raw_xml()
        result = _convert(raw_xml=raw_xml)
        assert isinstance(result, ComponentResult)

    def test_raw_xml_none_produces_warning(self):
        """When raw_xml is None, a warning about missing nodeData is emitted."""
        result = _convert(raw_xml=None)
        assert any("raw_xml is None" in w for w in result.warnings)
        cfg = result.component["config"]
        assert cfg["input_trees"] == []
        assert cfg["output_trees"] == []
        assert cfg["connections"] == []


class TestConditionalNeedsReview:
    """D-E1 lock-in: expression_filter / lookup / allInOne emit conditional needs_review.

    Each sub-feature emits a needs_review entry ONLY when its trigger flag is
    active in the Talend node (conditional). Absence of the flag means NO entry.
    """

    # ---- expression_filter ----

    def test_expression_filter_true_emits_needs_review(self):
        """activateExpressionFilter='true' on outputTree -> needs_review entry with feature='expression_filter'."""
        raw_xml = _make_raw_xml(
            output_trees_xml=(
                '<outputTrees name="out1" expressionFilter="row1.status == 1" '
                'activateExpressionFilter="true">'
                '  <nodes name="id" expression="" type="id_String" xpath="id" />'
                '</outputTrees>'
            ),
            metadata_xml=_SIMPLE_METADATA,
        )
        result = _convert(raw_xml=raw_xml)
        ef_entries = [e for e in result.needs_review if e.get("feature") == "expression_filter"]
        assert len(ef_entries) == 1, (
            f"Expected exactly 1 expression_filter needs_review entry; got {len(ef_entries)}"
        )

    def test_expression_filter_false_no_needs_review(self):
        """activateExpressionFilter='false' -> NO expression_filter needs_review entry."""
        raw_xml = _make_raw_xml(
            output_trees_xml=(
                '<outputTrees name="out1" expressionFilter="" activateExpressionFilter="false">'
                '  <nodes name="id" expression="" type="id_String" xpath="id" />'
                '</outputTrees>'
            ),
            metadata_xml=_SIMPLE_METADATA,
        )
        result = _convert(raw_xml=raw_xml)
        ef_entries = [e for e in result.needs_review if e.get("feature") == "expression_filter"]
        assert len(ef_entries) == 0, (
            "expression_filter needs_review emitted when flag is False"
        )

    def test_expression_filter_absent_no_needs_review(self):
        """No activateExpressionFilter attribute -> NO expression_filter needs_review entry."""
        raw_xml = _make_raw_xml(metadata_xml=_SIMPLE_METADATA)
        result = _convert(raw_xml=raw_xml)
        ef_entries = [e for e in result.needs_review if e.get("feature") == "expression_filter"]
        assert len(ef_entries) == 0

    # ---- lookup_join ----

    def test_lookup_input_tree_emits_needs_review(self):
        """inputTree with lookup='true' -> needs_review entry with feature='lookup_join'."""
        raw_xml = _make_raw_xml(
            input_trees_xml=_SIMPLE_INPUT_TREE + _LOOKUP_INPUT_TREE,
            metadata_xml=_SIMPLE_METADATA,
        )
        result = _convert(raw_xml=raw_xml)
        lj_entries = [e for e in result.needs_review if e.get("feature") == "lookup_join"]
        assert len(lj_entries) == 1, (
            f"Expected exactly 1 lookup_join needs_review entry; got {len(lj_entries)}"
        )

    def test_no_lookup_input_tree_no_needs_review(self):
        """All inputTrees have lookup='false' -> NO lookup_join needs_review entry."""
        raw_xml = _make_raw_xml(
            input_trees_xml=_SIMPLE_INPUT_TREE,  # lookup='false'
            metadata_xml=_SIMPLE_METADATA,
        )
        result = _convert(raw_xml=raw_xml)
        lj_entries = [e for e in result.needs_review if e.get("feature") == "lookup_join"]
        assert len(lj_entries) == 0, (
            "lookup_join needs_review emitted when no lookup tree present"
        )

    # ---- all_in_one_document_output ----

    def test_all_in_one_output_tree_emits_needs_review(self):
        """outputTree with allInOne='true' -> needs_review entry with feature='all_in_one_document_output'."""
        raw_xml = _make_raw_xml(
            output_trees_xml=(
                '<outputTrees name="out1" allInOne="true">'
                '  <nodes name="id" expression="" type="id_String" xpath="id" />'
                '</outputTrees>'
            ),
            metadata_xml=_SIMPLE_METADATA,
        )
        result = _convert(raw_xml=raw_xml)
        aio_entries = [e for e in result.needs_review if e.get("feature") == "all_in_one_document_output"]
        assert len(aio_entries) == 1, (
            f"Expected exactly 1 all_in_one needs_review entry; got {len(aio_entries)}"
        )

    def test_all_in_one_false_no_needs_review(self):
        """outputTree with allInOne='false' -> NO all_in_one needs_review entry."""
        raw_xml = _make_raw_xml(
            output_trees_xml=(
                '<outputTrees name="out1" allInOne="false">'
                '  <nodes name="id" expression="" type="id_String" xpath="id" />'
                '</outputTrees>'
            ),
            metadata_xml=_SIMPLE_METADATA,
        )
        result = _convert(raw_xml=raw_xml)
        aio_entries = [e for e in result.needs_review if e.get("feature") == "all_in_one_document_output"]
        assert len(aio_entries) == 0

    # ---- combined ----

    def test_all_three_triggers_active_emits_three_entries(self):
        """All three D-E1 flags active simultaneously -> 3 separate needs_review entries."""
        raw_xml = _make_raw_xml(
            input_trees_xml=_SIMPLE_INPUT_TREE + _LOOKUP_INPUT_TREE,
            output_trees_xml=(
                '<outputTrees name="out1" expressionFilter="x==1" '
                'activateExpressionFilter="true" allInOne="true">'
                '  <nodes name="id" expression="" type="id_String" xpath="id" />'
                '</outputTrees>'
            ),
            metadata_xml=_SIMPLE_METADATA,
        )
        result = _convert(raw_xml=raw_xml)
        ef = [e for e in result.needs_review if e.get("feature") == "expression_filter"]
        lj = [e for e in result.needs_review if e.get("feature") == "lookup_join"]
        aio = [e for e in result.needs_review if e.get("feature") == "all_in_one_document_output"]
        assert len(ef) == 1, f"Expected 1 expression_filter entry, got {len(ef)}"
        assert len(lj) == 1, f"Expected 1 lookup_join entry, got {len(lj)}"
        assert len(aio) == 1, f"Expected 1 all_in_one entry, got {len(aio)}"
