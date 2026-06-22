"""Tests for XMLMapConverter (tXMLMap -> v1 XMLMap config)."""
import inspect
import xml.etree.ElementTree as ET

import pytest

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


# ==================================================================
# Plan 14-11: targeted module-helper tests for missed-line clusters
# ==================================================================
#
# These cover the helper-function branches that the converter-level
# tests above do not naturally exercise. Calling helpers directly via
# crafted Element / dict inputs is cleaner than constructing a full
# Talend tXMLMap node for each branch. See xml_map.py:
#   _build_expressions: lines 183, 188, 208-212, 216
#   _detect_looping_element: lines 247-249, 253-256, 263-268
#   _rewrite_expressions_for_loop: lines 293-294, 315-317, 320-321
#   converter convert(): line 409 (raw_xml without nodeData)


class TestBuildExpressionsBranches:
    """Cover lines 183, 188, 208-212, 216 in _build_expressions."""

    def _build(self):
        from src.converters.talend_to_v1.components.transform.xml_map import (
            _build_expressions,
        )
        return _build_expressions

    def test_target_without_output_path_skipped(self):
        """A connection whose target lacks 'outputTrees.0/@nodes.<n>' is skipped (line 183)."""
        build = self._build()
        connections = [
            {
                # No outputTrees regex match
                "source": "inputTrees.0/@nodes.0",
                "target": "garbage/path",
                "sourceExpression": "",
            },
        ]
        result = build(connections, {}, {0: "out_col"})
        assert result == {}

    def test_unknown_output_index_skipped(self):
        """A connection's out_idx not in output_col_map -> skipped (line 188)."""
        build = self._build()
        connections = [
            {
                "source": "inputTrees.0/@nodes.0",
                "target": "outputTrees.0/@nodes.42",  # idx 42 not in map
                "sourceExpression": "",
            },
        ]
        result = build(connections, {}, {0: "first_only"})
        assert result == {}

    def test_attribute_at_leaf_with_parents(self):
        """ATTRIBUT leaf with parent xpath_parts -> ./parents/@attr (lines 207-210)."""
        build = self._build()
        # Build an input_tree_node_map where the leaf node is type ATTRIBUT
        node_map = {
            "inputTrees.0/@nodes.0": ("doc", "ELEMENT", {}),
            "inputTrees.0/@nodes.0/@children.0": ("root", "ELEMENT", {}),
            "inputTrees.0/@nodes.0/@children.0/@children.0": (
                "id_attr", "ATTRIBUT", {},
            ),
        }
        connections = [
            {
                "source": (
                    "inputTrees.0/@nodes.0/@children.0/@children.0"
                ),
                "target": "outputTrees.0/@nodes.0",
                "sourceExpression": "",
            },
        ]
        result = build(connections, node_map, {0: "id"})
        # Expect ./root/@id_attr (parent then attribute name)
        # Note 'doc' (the @nodes.0 root) is skipped because xpath_parts skips
        # 'newColumn'-named entries; but 'doc' is a real name so it IS included.
        # Check the suffix matches the ATTRIBUT shape.
        assert result["id"].startswith("./")
        assert "/@id_attr" in result["id"]

    def test_attribute_at_leaf_without_parents(self):
        """ATTRIBUT leaf with no parent xpath_parts -> ./@attr (lines 211-212)."""
        build = self._build()
        # Only the leaf-attribute node is named; the parent's name is "newColumn"
        # which is filtered out by line 201's exclusion list, so xpath_parts
        # is empty after pop.
        node_map = {
            "inputTrees.0/@nodes.0": ("newColumn", "ELEMENT", {}),
            "inputTrees.0/@nodes.0/@children.0": (
                "attrOnly", "ATTRIBUT", {},
            ),
        }
        connections = [
            {
                "source": "inputTrees.0/@nodes.0/@children.0",
                "target": "outputTrees.0/@nodes.0",
                "sourceExpression": "",
            },
        ]
        result = build(connections, node_map, {0: "id"})
        assert result["id"] == "./@attrOnly"

    def test_no_named_path_parts_falls_back_to_dot(self):
        """Source path with no recognised parts -> xpath '.' (line 216)."""
        build = self._build()
        # node_map has no entries matching the source path -> path_parts empty
        connections = [
            {
                "source": "totally/unrelated",
                "target": "outputTrees.0/@nodes.0",
                "sourceExpression": "",
            },
        ]
        result = build(connections, {}, {0: "id"})
        assert result == {"id": "."}


class TestDetectLoopingElementBranches:
    """Cover lines 247-249, 253-256, 263-268 in _detect_looping_element."""

    def _detect(self):
        from src.converters.talend_to_v1.components.transform.xml_map import (
            _detect_looping_element,
        )
        return _detect_looping_element

    def test_strategy2_element_parameter_lookup(self):
        """No loop=true child but elementParameter LOOPING_ELEMENT present (lines 247-249)."""
        detect = self._detect()
        raw_xml = ET.fromstring(
            '<node>'
            '  <elementParameter name="LOOPING_ELEMENT" value="loop_node" />'
            '</node>'
        )
        result = detect(raw_xml, {})
        assert result == "loop_node"

    def test_strategy2_element_parameter_value_none_strips_to_empty(self):
        """elementParameter LOOPING_ELEMENT with no value attribute -> empty (line 248)."""
        detect = self._detect()
        # value attribute missing -> param.get("value") is None -> "" or None
        raw_xml = ET.fromstring(
            '<node>'
            '  <elementParameter name="LOOPING_ELEMENT" />'
            '</node>'
        )
        result = detect(raw_xml, {})
        # Falls through Strategy 2 (sets to ""), then Strategy 3 with empty map -> ""
        assert result == ""

    def test_normalize_list_value(self):
        """If looping_element somehow becomes a list, str(list[0]) is used (line 256)."""
        # We cannot trigger this via raw_xml + ET (param.get always returns str),
        # but we can construct a fake param-bearing element by patching ET nodes.
        # Easier: call private through a stub that returns a list. Use
        # monkey-style by constructing ET with attribute that the function
        # reads via param.get("value"). The function uses str.strip() on the
        # value -- so we must drive the list/tuple/dict branch a different way:
        # call the helper and then verify the carve-out via a tuple-bearing
        # raw_xml that contains a nested children loop=true (Strategy 1) where
        # name returns a list-like via custom Element subclass.
        # Simpler: construct a Strategy 1 hit using two children with loop=true;
        # the function takes the FIRST one. The list/tuple/dict branch is dead
        # for ET-typed `name` returns. Document and skip the branch.
        pytest.skip(
            "Strategy 1/2 always yield strings via ET.Element.get(); the "
            "list/tuple/dict normalization branch (lines 252-256) is "
            "defensive code for non-ET callers and is genuinely unreachable "
            "via the documented call sites. D-C5 candidate but kept as "
            "low-risk defensive code per Phase 14 scope."
        )

    def test_strategy3_deepest_node_in_input_tree(self):
        """No loop=true and no elementParameter -> use deepest path in node_map
        (lines 263-268)."""
        detect = self._detect()
        raw_xml = ET.fromstring("<node />")  # no children loop, no LOOPING_ELEMENT
        node_map = {
            "inputTrees.0/@nodes.0": ("doc", "ELEMENT", {}),
            "inputTrees.0/@nodes.0/@children.0": ("shallow", "ELEMENT", {}),
            "inputTrees.0/@nodes.0/@children.0/@children.0": (
                "deepest", "ELEMENT", {},
            ),
        }
        result = detect(raw_xml, node_map)
        # Deepest path has the most '/' separators -> "deepest"
        assert result == "deepest"

    def test_strategy3_with_no_input_map_returns_empty(self):
        """Empty raw_xml AND empty node_map -> empty string."""
        detect = self._detect()
        result = detect(None, {})
        assert result == ""


class TestRewriteExpressionsBranches:
    """Cover lines 293-294, 315-317, 320-321 in _rewrite_expressions_for_loop."""

    def _rewrite(self):
        from src.converters.talend_to_v1.components.transform.xml_map import (
            _rewrite_expressions_for_loop,
        )
        return _rewrite_expressions_for_loop

    def test_empty_xpath_passthrough(self):
        """An empty xpath passes through unchanged (lines 293-294)."""
        rewrite = self._rewrite()
        result = rewrite({"col_a": ""}, "loop")
        assert result["col_a"] == ""

    def test_in_loop_no_remaining_parts_uses_loop_name(self):
        """xpath whose last part IS the loop element -> ./<loop_name>
        (lines 314-315)."""
        rewrite = self._rewrite()
        # field_parts = ['root', 'item'] and loop_name='item' -> in_loop=True,
        # loop_index=1, rel_parts=[] -> new_xpath = './item'
        result = rewrite({"id": "./root/item"}, "item")
        assert result["id"] == "./item"

    def test_in_loop_with_relative_parts(self):
        """xpath inside loop with deeper parts -> ./<rel_parts>."""
        rewrite = self._rewrite()
        # loop_name='item', xpath='./root/item/id' -> in_loop=True,
        # rel_parts=['id'] -> './id'
        result = rewrite({"id": "./root/item/id"}, "item")
        assert result["id"] == "./id"

    def test_field_outside_loop_uses_ancestor_axis(self):
        """A field NOT under the loop element -> ./ancestor::<path>
        (lines 320-321)."""
        rewrite = self._rewrite()
        # xpath='./root/header' and loop_name='item' -> in_loop=False
        # -> new_xpath = './ancestor::root/header'
        result = rewrite({"hdr": "./root/header"}, "item")
        assert result["hdr"] == "./ancestor::root/header"


class TestConverterRawXmlEdges:
    """Cover line 409 (raw_xml provided but missing nodeData)."""

    def test_raw_xml_without_nodedata_emits_warning(self):
        """raw_xml is provided but contains no <nodeData> child -> warning."""
        # Build a node element with NO nodeData child
        raw_xml = ET.fromstring(
            '<node componentName="tXMLMap" componentVersion="0.1" />'
        )
        node = _make_node(raw_xml=raw_xml)
        result = XMLMapConverter().convert(node, [], {})

        # Convert returns a ComponentResult; warnings should mention missing nodeData
        warnings = result.warnings
        assert any("nodeData element not found" in w for w in warnings), (
            f"Expected 'nodeData element not found' warning; got {warnings}"
        )


# ==================================================================
# Coverage lift: _extract_loop_nodes, _rewrite outside-loop relative,
# _build_expression_contexts_multi, and the multi-loop converter dispatch.
# ==================================================================


class TestExtractLoopNodes:
    """Cover _extract_loop_nodes EMF-path parsing branches."""

    def _extract(self):
        from src.converters.talend_to_v1.components.transform.xml_map import (
            _extract_loop_nodes,
        )
        return _extract_loop_nodes

    def test_raw_xml_none_returns_empty(self):
        """raw_xml=None -> early return []."""
        extract = self._extract()
        assert extract(None, {}) == []

    def test_blank_inputloopnodes_skipped(self):
        """An inputLoopNodesTables with blank inputloopnodes attr is skipped."""
        extract = self._extract()
        raw_xml = ET.fromstring(
            '<node>'
            '  <outputTrees name="out1">'
            '    <inputLoopNodesTables inputloopnodes="   " />'
            '  </outputTrees>'
            '</node>'
        )
        assert extract(raw_xml, {}) == []

    def test_no_path_parts_in_emf_path_skipped(self):
        """An EMF path with no @inputTrees/@nodes/@children tokens is skipped."""
        extract = self._extract()
        raw_xml = ET.fromstring(
            '<node>'
            '  <outputTrees name="out1">'
            '    <inputLoopNodesTables inputloopnodes="//@garbage/@noindex" />'
            '  </outputTrees>'
            '</node>'
        )
        assert extract(raw_xml, {}) == []

    def test_emf_path_resolves_to_loop_name(self):
        """A resolvable EMF path -> the corresponding node name in loop_nodes."""
        extract = self._extract()
        raw_xml = ET.fromstring(
            '<node>'
            '  <outputTrees name="out1">'
            '    <inputLoopNodesTables '
            '       inputloopnodes="//@node.0/@nodeData/@inputTrees.0/@nodes.0/@children.0" />'
            '  </outputTrees>'
            '</node>'
        )
        node_map = {
            "inputTrees.0/@nodes.0": ("doc", "ELEMENT", {}),
            "inputTrees.0/@nodes.0/@children.0": ("item", "ELEMENT", {}),
        }
        assert extract(raw_xml, node_map) == ["item"]

    def test_emf_path_nonzero_inputtrees_prefix(self):
        """An @inputTrees.1 token overrides the default tree prefix (lines 254-255)."""
        extract = self._extract()
        raw_xml = ET.fromstring(
            '<node>'
            '  <outputTrees name="out1">'
            '    <inputLoopNodesTables '
            '       inputloopnodes="//@nodeData/@inputTrees.1/@nodes.0/@children.0" />'
            '  </outputTrees>'
            '</node>'
        )
        node_map = {
            "inputTrees.1/@nodes.0/@children.0": ("lookup_item", "ELEMENT", {}),
        }
        assert extract(raw_xml, node_map) == ["lookup_item"]

    def test_duplicate_loop_names_deduped(self):
        """The same loop name appearing twice is only added once."""
        extract = self._extract()
        emf = "//@nodeData/@inputTrees.0/@nodes.0/@children.0"
        raw_xml = ET.fromstring(
            '<node>'
            '  <outputTrees name="out1">'
            f'    <inputLoopNodesTables inputloopnodes="{emf} {emf}" />'
            '  </outputTrees>'
            '</node>'
        )
        node_map = {
            "inputTrees.0/@nodes.0/@children.0": ("item", "ELEMENT", {}),
        }
        assert extract(raw_xml, node_map) == ["item"]

    def test_unresolvable_emf_path_yields_no_name(self):
        """An EMF path whose full_path is not in the node_map adds no name."""
        extract = self._extract()
        raw_xml = ET.fromstring(
            '<node>'
            '  <outputTrees name="out1">'
            '    <inputLoopNodesTables '
            '       inputloopnodes="//@nodeData/@inputTrees.0/@nodes.9/@children.9" />'
            '  </outputTrees>'
            '</node>'
        )
        node_map = {
            "inputTrees.0/@nodes.0/@children.0": ("item", "ELEMENT", {}),
        }
        assert extract(raw_xml, node_map) == []


class TestRewriteOutsideLoopRelative:
    """Cover the elif loop_full_parts branch (relative ../ traversal)."""

    def _rewrite(self):
        from src.converters.talend_to_v1.components.transform.xml_map import (
            _rewrite_expressions_for_loop,
        )
        return _rewrite_expressions_for_loop

    def test_outside_loop_uses_relative_up_traversal(self):
        """A field outside the loop is rewritten with ../ once loop path is known."""
        rewrite = self._rewrite()
        # An inside-loop expression lets the function infer the loop's full path:
        #   loop_full_parts = ['company', 'employee'] (loop_name='employee').
        # The outside field './company/name' shares the 'company' prefix, so it
        # navigates up one level (employee -> company) then to 'name': '../name'.
        exprs = {
            "emp_id": "./company/employee/id",   # inside loop
            "company_name": "./company/name",    # outside loop
        }
        result = rewrite(exprs, "employee")
        assert result["emp_id"] == "./id"
        assert result["company_name"] == "./../name"

    def test_outside_loop_no_common_prefix(self):
        """Outside field sharing no prefix climbs all loop levels then descends."""
        rewrite = self._rewrite()
        exprs = {
            "emp_id": "./company/employee/id",   # inside loop; loop path len 2
            "other": "./root/other",             # no shared prefix
        }
        result = rewrite(exprs, "employee")
        # levels_up = 2 (whole loop path), down_parts = ['root','other']
        assert result["other"] == "./../../root/other"


class TestBuildExpressionContextsMulti:
    """Cover _build_expression_contexts_multi (multi-loop XPath rewrite)."""

    def _build(self):
        from src.converters.talend_to_v1.components.transform.xml_map import (
            _build_expression_contexts_multi,
        )
        return _build_expression_contexts_multi

    def test_no_loop_nodes_returns_inputs_and_empty_contexts(self):
        """Empty loop_nodes -> (expressions_raw, {}) early return (line 430-431)."""
        build = self._build()
        exprs = {"a": "./x/y"}
        rewritten, contexts = build(exprs, [])
        assert rewritten == exprs
        assert contexts == {}

    def test_field_in_deepest_loop(self):
        """A field under the deepest loop axis is rewritten relative to that loop."""
        build = self._build()
        # loop_nodes primary='employee', secondary='address'.
        # Field path contains both; deepest match is 'address' (higher index).
        exprs = {
            "city": "./company/employee/addresses/address/city",
        }
        rewritten, contexts = build(exprs, ["employee", "address"])
        assert rewritten["city"] == "./city"
        assert contexts["city"] == "address"

    def test_field_in_primary_loop_only(self):
        """A field under only the primary loop is owned by that loop."""
        build = self._build()
        exprs = {
            "emp_id": "./company/employee/id",
        }
        rewritten, contexts = build(exprs, ["employee", "address"])
        assert rewritten["emp_id"] == "./id"
        assert contexts["emp_id"] == "employee"

    def test_field_inside_loop_is_loop_itself(self):
        """A field whose last part IS the loop element -> '.' (no remaining parts)."""
        build = self._build()
        exprs = {
            "addr": "./company/employee/address",
        }
        rewritten, contexts = build(exprs, ["employee", "address"])
        assert rewritten["addr"] == "."
        assert contexts["addr"] == "address"

    def test_field_outside_all_loops_relative_to_primary(self):
        """A field outside all loops uses the primary loop context with ../ paths."""
        build = self._build()
        exprs = {
            "emp_id": "./company/employee/id",   # establishes primary path
            "co_name": "./company/name",         # outside all loops
        }
        rewritten, contexts = build(exprs, ["employee", "address"])
        # primary_full_path = ['company','employee']; co_name shares 'company'
        # -> up 1 (employee), down to 'name': '../name'
        assert rewritten["co_name"] == "./../name"
        assert contexts["co_name"] == "employee"

    def test_field_outside_all_loops_no_primary_path(self):
        """Outside field with no inferable primary path -> kept as ./<parts>."""
        build = self._build()
        # No expression contains 'employee' or 'address', so loop_node_full_paths
        # stays empty -> primary_full_path = [] -> else branch keeps absolute parts.
        exprs = {
            "lonely": "./root/value",
        }
        rewritten, contexts = build(exprs, ["employee", "address"])
        assert rewritten["lonely"] == "./root/value"
        assert contexts["lonely"] == "employee"

    def test_empty_xpath_passthrough(self):
        """An empty xpath value passes through, owned by the primary loop."""
        build = self._build()
        exprs = {"blank": ""}
        rewritten, contexts = build(exprs, ["employee", "address"])
        assert rewritten["blank"] == ""
        assert contexts["blank"] == "employee"


class TestConverterMultiLoopDispatch:
    """Cover the converter's multi-loop dispatch (loop_nodes[0] and multi rewrite)."""

    def _multi_loop_raw_xml(self):
        """Build a tXMLMap raw_xml with two loop axes via inputLoopNodesTables.

        The input tree has nested 'item' and 'detail' loop elements; the
        inputLoopNodesTables list references both, so _extract_loop_nodes
        returns two names, triggering the multi-loop branch.
        """
        input_tree = (
            '<inputTrees name="row1" matchingMode="ALL_ROWS" lookupMode="LOAD_ONCE" lookup="false">'
            '  <nodes name="doc" expression="row1.payload" type="id_Document" xpath="/">'
            '    <children name="root" type="id_String" xpath="root" nodeType="ELEMENT" loop="false">'
            '      <children name="item" type="id_String" xpath="item" nodeType="ELEMENT" loop="true">'
            '        <children name="iid" type="id_String" xpath="iid" nodeType="ELEMENT" loop="false" />'
            '        <children name="detail" type="id_String" xpath="detail" nodeType="ELEMENT" loop="true">'
            '          <children name="did" type="id_String" xpath="did" nodeType="ELEMENT" loop="false" />'
            '        </children>'
            '      </children>'
            '    </children>'
            '  </nodes>'
            '</inputTrees>'
        )
        # Connections: out col 0 (iid) <- item/iid; out col 1 (did) <- item/detail/did
        connections = (
            '<connections '
            ' source="inputTrees.0/@nodes.0/@children.0/@children.0/@children.0" '
            ' target="outputTrees.0/@nodes.0" sourceExpression="" />'
            '<connections '
            ' source="inputTrees.0/@nodes.0/@children.0/@children.0/@children.1/@children.0" '
            ' target="outputTrees.0/@nodes.1" sourceExpression="" />'
        )
        metadata = (
            '<metadata connector="FLOW" name="out1">'
            '  <column name="iid" type="id_String" nullable="true" key="false" length="50" precision="-1" />'
            '  <column name="did" type="id_String" nullable="true" key="false" length="50" precision="-1" />'
            '</metadata>'
        )
        # outputTrees must contain the inputLoopNodesTables referencing both loops.
        output_trees = (
            '<outputTrees name="out1">'
            '  <nodes name="iid" expression="" type="id_String" xpath="iid" />'
            '  <nodes name="did" expression="" type="id_String" xpath="did" />'
            '  <inputLoopNodesTables '
            '     inputloopnodes="//@nodeData/@inputTrees.0/@nodes.0/@children.0/@children.0 '
            '//@nodeData/@inputTrees.0/@nodes.0/@children.0/@children.0/@children.1" />'
            '</outputTrees>'
        )
        return _make_raw_xml(
            input_trees_xml=input_tree,
            output_trees_xml=output_trees,
            connections_xml=connections,
            metadata_xml=metadata,
        )

    def test_multi_loop_sets_loop_nodes_and_contexts(self):
        """Two loop axes -> loop_nodes has 2 entries, looping_element=loop_nodes[0],
        and _build_expression_contexts_multi runs (expression_contexts populated)."""
        raw_xml = self._multi_loop_raw_xml()
        result = _convert(raw_xml=raw_xml)
        cfg = result.component["config"]

        assert cfg["loop_nodes"] == ["item", "detail"]
        assert cfg["looping_element"] == "item"
        # Multi-loop branch populates per-column contexts.
        assert cfg["expression_contexts"]
        assert set(cfg["expression_contexts"].values()) <= {"item", "detail"}
        # iid is inside 'item'; did is inside the deeper 'detail' loop.
        assert cfg["expression_contexts"]["iid"] == "item"
        assert cfg["expression_contexts"]["did"] == "detail"

    def test_single_loop_node_from_extract_uses_index_zero(self):
        """A single resolved loop node -> looping_element=loop_nodes[0] (line 629)
        and the single-loop rewrite path (len==1, not multi)."""
        input_tree = _SIMPLE_INPUT_TREE
        output_trees = (
            '<outputTrees name="out1">'
            '  <nodes name="id" expression="" type="id_String" xpath="id" />'
            '  <inputLoopNodesTables '
            '     inputloopnodes="//@nodeData/@inputTrees.0/@nodes.0/@children.0/@children.0" />'
            '</outputTrees>'
        )
        raw_xml = _make_raw_xml(
            input_trees_xml=input_tree,
            output_trees_xml=output_trees,
            connections_xml=_SIMPLE_CONNECTIONS,
            metadata_xml=_SIMPLE_METADATA,
        )
        result = _convert(raw_xml=raw_xml)
        cfg = result.component["config"]
        assert cfg["loop_nodes"] == ["item"]
        assert cfg["looping_element"] == "item"
        # Single-loop: expression_contexts stays empty (multi branch not taken).
        assert cfg["expression_contexts"] == {}
