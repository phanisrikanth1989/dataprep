"""Tests for tXMLMap -> XMLMap converter."""
from xml.etree.ElementTree import Element, SubElement

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.xml_map import (
    XMLMapConverter,
    _build_expressions,
    _build_input_tree_node_map,
    _detect_looping_element,
    _parse_connections,
    _parse_input_trees,
    _parse_nested_children,
    _parse_output_schema_from_xml,
    _parse_output_trees,
    _rewrite_expressions_for_loop,
)


# ---------------------------------------------------------------------------
# XML builder helpers
# ---------------------------------------------------------------------------

def _make_raw_xml(
    *,
    die_on_error: str = "true",
    keep_order: str = "false",
    connection_format: str = "row",
    input_trees_xml: str = "",
    output_trees_xml: str = "",
    connections_xml: str = "",
    metadata_xml: str = "",
) -> Element:
    """Build a minimal raw_xml Element that mimics a Talend tXMLMap node."""
    root = Element("node", attrib={
        "componentName": "tXMLMap",
        "componentVersion": "0.1",
    })
    # elementParameters
    ep1 = SubElement(root, "elementParameter", attrib={
        "name": "DIE_ON_ERROR", "value": die_on_error,
    })
    ep2 = SubElement(root, "elementParameter", attrib={
        "name": "KEEP_ORDER_FOR_DOCUMENT", "value": keep_order,
    })
    ep3 = SubElement(root, "elementParameter", attrib={
        "name": "CONNECTION_FORMAT", "value": connection_format,
    })

    # nodeData
    node_data_str = (
        f"<nodeData>"
        f"  {input_trees_xml}"
        f"  {output_trees_xml}"
        f"  {connections_xml}"
        f"</nodeData>"
    )
    # Parse nodeData as XML and append to root
    import xml.etree.ElementTree as ET
    node_data_elem = ET.fromstring(node_data_str)
    root.append(node_data_elem)

    # metadata
    if metadata_xml:
        metadata_elem = ET.fromstring(metadata_xml)
        root.append(metadata_elem)

    return root


def _make_node(params=None, schema=None, raw_xml=None):
    """Build a TalendNode for tXMLMap tests."""
    return TalendNode(
        component_id="tXMLMap_1",
        component_type="tXMLMap",
        params=params or {},
        schema=schema or {},
        position={"x": 300, "y": 150},
        raw_xml=raw_xml,
    )


# Standard XML snippets for reuse
_SIMPLE_INPUT_TREE = (
    '<inputTrees name="row1" matchingMode="ALL_ROWS" lookupMode="LOAD_ONCE">'
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


class TestXMLMapConverter:
    """Tests for the XMLMapConverter."""

    def test_type_name_is_xml_map(self):
        """CONV-XMP-001: type must be 'XMLMap', not 'TXMLMap'."""
        raw_xml = _make_raw_xml(
            input_trees_xml=_SIMPLE_INPUT_TREE,
            output_trees_xml=_SIMPLE_OUTPUT_TREE,
            connections_xml=_SIMPLE_CONNECTIONS,
            metadata_xml=_SIMPLE_METADATA,
        )
        node = _make_node(
            params={
                "DIE_ON_ERROR": "true",
                "KEEP_ORDER_FOR_DOCUMENT": "false",
                "CONNECTION_FORMAT": "row",
            },
            raw_xml=raw_xml,
        )
        result = XMLMapConverter().convert(node, [], {})
        assert result.component["type"] == "XMLMap"
        assert result.component["original_type"] == "tXMLMap"

    def test_basic_params_extraction(self):
        """die_on_error, keep_order, connection_format are extracted."""
        raw_xml = _make_raw_xml(
            die_on_error="false",
            keep_order="true",
            connection_format="document",
        )
        node = _make_node(
            params={
                "DIE_ON_ERROR": "false",
                "KEEP_ORDER_FOR_DOCUMENT": "true",
                "CONNECTION_FORMAT": "document",
            },
            raw_xml=raw_xml,
        )
        result = XMLMapConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["die_on_error"] is False
        assert cfg["keep_order"] is True
        assert cfg["connection_format"] == "document"

    def test_input_trees_parsed(self):
        """Input trees with nested children are parsed correctly."""
        raw_xml = _make_raw_xml(input_trees_xml=_SIMPLE_INPUT_TREE)
        node = _make_node(raw_xml=raw_xml)
        result = XMLMapConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert len(cfg["INPUT_TREES"]) == 1
        tree = cfg["INPUT_TREES"][0]
        assert tree["name"] == "row1"
        assert tree["matchingMode"] == "ALL_ROWS"
        assert tree["lookupMode"] == "LOAD_ONCE"
        assert len(tree["nodes"]) == 1

        doc_node = tree["nodes"][0]
        assert doc_node["name"] == "doc"
        assert doc_node["type"] == "id_Document"

        root_child = doc_node["children"][0]
        assert root_child["name"] == "root"
        assert root_child["loop"] is False

        item_child = root_child["children"][0]
        assert item_child["name"] == "item"
        assert item_child["loop"] is True
        assert len(item_child["children"]) == 2

    def test_output_trees_parsed(self):
        """Output trees with expression filter are parsed."""
        raw_xml = _make_raw_xml(output_trees_xml=_SIMPLE_OUTPUT_TREE)
        node = _make_node(raw_xml=raw_xml)
        result = XMLMapConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert len(cfg["OUTPUT_TREES"]) == 1
        tree = cfg["OUTPUT_TREES"][0]
        assert tree["name"] == "out1"
        assert tree["expressionFilter"] == "row1.status == 1"
        assert tree["activateExpressionFilter"] is True
        assert len(tree["nodes"]) == 2

    def test_connections_parsed(self):
        """Connections are parsed into source/target/sourceExpression dicts."""
        raw_xml = _make_raw_xml(connections_xml=_SIMPLE_CONNECTIONS)
        node = _make_node(raw_xml=raw_xml)
        result = XMLMapConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert len(cfg["CONNECTIONS"]) == 2
        conn = cfg["CONNECTIONS"][0]
        assert "inputTrees.0/@nodes.0" in conn["source"]
        assert "outputTrees.0/@nodes.0" in conn["target"]

    def test_output_schema_from_metadata(self):
        """Output schema is parsed from FLOW metadata in raw_xml."""
        raw_xml = _make_raw_xml(metadata_xml=_SIMPLE_METADATA)
        node = _make_node(raw_xml=raw_xml)
        result = XMLMapConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert len(cfg["output_schema"]) == 2
        assert cfg["output_schema"][0]["name"] == "id"
        assert cfg["output_schema"][0]["type"] == "id_String"
        assert cfg["output_schema"][0]["nullable"] is True
        assert cfg["output_schema"][0]["length"] == 50
        assert cfg["output_schema"][1]["name"] == "name"

    def test_expression_filter_extraction(self):
        """Expression filter and activation flag come from first output tree."""
        raw_xml = _make_raw_xml(output_trees_xml=_SIMPLE_OUTPUT_TREE)
        node = _make_node(raw_xml=raw_xml)
        result = XMLMapConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["expression_filter"] == "{{java}}row1.status == 1"
        assert cfg["activate_expression_filter"] is True

    def test_no_expression_filter_defaults(self):
        """When no output trees exist, expression filter is None."""
        raw_xml = _make_raw_xml()
        node = _make_node(raw_xml=raw_xml)
        result = XMLMapConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["expression_filter"] is None
        assert cfg["activate_expression_filter"] is False

    def test_looping_element_detection(self):
        """Looping element is detected from children with loop=true."""
        raw_xml = _make_raw_xml(input_trees_xml=_SIMPLE_INPUT_TREE)
        node = _make_node(raw_xml=raw_xml)
        result = XMLMapConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["looping_element"] == "item"

    def test_expressions_with_loop_rewrite(self):
        """Expressions inside the loop are rewritten to relative paths."""
        raw_xml = _make_raw_xml(
            input_trees_xml=_SIMPLE_INPUT_TREE,
            output_trees_xml=_SIMPLE_OUTPUT_TREE,
            connections_xml=_SIMPLE_CONNECTIONS,
            metadata_xml=_SIMPLE_METADATA,
        )
        node = _make_node(raw_xml=raw_xml)
        result = XMLMapConverter().convert(node, [], {})
        cfg = result.component["config"]

        # "id" and "name" are children of "item" (the loop element)
        # so after rewrite they should be relative to the loop: ./id, ./name
        assert "id" in cfg["expressions"]
        assert "name" in cfg["expressions"]
        # Both should be relative paths (inside the loop)
        for col in ("id", "name"):
            xpath = cfg["expressions"][col]
            assert xpath.startswith("./"), f"Expected relative path for {col}, got {xpath}"
            assert "ancestor::" not in xpath

    def test_raw_xml_none_produces_warning(self):
        """When raw_xml is None, a warning about missing nodeData is emitted."""
        node = _make_node(raw_xml=None)
        result = XMLMapConverter().convert(node, [], {})

        assert any("raw_xml is None" in w for w in result.warnings)
        cfg = result.component["config"]
        assert cfg["INPUT_TREES"] == []
        assert cfg["OUTPUT_TREES"] == []
        assert cfg["CONNECTIONS"] == []

    def test_component_dict_structure(self):
        """Output dict has all required top-level keys."""
        raw_xml = _make_raw_xml()
        node = _make_node(raw_xml=raw_xml)
        result = XMLMapConverter().convert(node, [], {})
        comp = result.component

        expected_keys = {
            "id", "type", "original_type", "position",
            "config", "schema", "inputs", "outputs",
        }
        assert set(comp.keys()) == expected_keys
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_result_type(self):
        """convert() returns a ComponentResult."""
        raw_xml = _make_raw_xml()
        node = _make_node(raw_xml=raw_xml)
        result = XMLMapConverter().convert(node, [], {})
        assert isinstance(result, ComponentResult)

    def test_registration(self):
        """The converter is registered under 'tXMLMap'."""
        from src.converters.talend_to_v1.components.registry import REGISTRY
        cls = REGISTRY.get("tXMLMap")
        assert cls is XMLMapConverter

    def test_config_keys_complete(self):
        """Config contains all expected keys from the old converter."""
        raw_xml = _make_raw_xml(
            input_trees_xml=_SIMPLE_INPUT_TREE,
            output_trees_xml=_SIMPLE_OUTPUT_TREE,
            connections_xml=_SIMPLE_CONNECTIONS,
            metadata_xml=_SIMPLE_METADATA,
        )
        node = _make_node(raw_xml=raw_xml)
        result = XMLMapConverter().convert(node, [], {})
        cfg = result.component["config"]

        expected_keys = {
            "die_on_error", "keep_order", "connection_format",
            "INPUT_TREES", "OUTPUT_TREES", "CONNECTIONS",
            "output_schema", "expression_filter",
            "activate_expression_filter", "expressions",
            "looping_element",
        }
        assert expected_keys.issubset(set(cfg.keys()))

    def test_defaults_when_params_missing(self):
        """Missing params fall back to sensible defaults."""
        raw_xml = _make_raw_xml()
        node = _make_node(params={}, raw_xml=raw_xml)
        result = XMLMapConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["die_on_error"] is True  # default for XMLMap
        assert cfg["keep_order"] is False
        assert cfg["connection_format"] == "row"


class TestParseNestedChildren:
    """Tests for the _parse_nested_children helper."""

    def test_empty_element(self):
        """Element with no children returns empty list."""
        elem = Element("node")
        assert _parse_nested_children(elem) == []

    def test_single_child(self):
        """Single child is parsed with all attributes."""
        parent = Element("node")
        SubElement(parent, "children", attrib={
            "name": "field1",
            "type": "id_Integer",
            "xpath": "field1",
            "nodeType": "ELEMENT",
            "loop": "true",
            "main": "false",
            "outgoingConnections": "conn1",
        })
        result = _parse_nested_children(parent)
        assert len(result) == 1
        assert result[0]["name"] == "field1"
        assert result[0]["type"] == "id_Integer"
        assert result[0]["loop"] is True
        assert result[0]["main"] is False

    def test_nested_children_recursive(self):
        """Deeply nested children are parsed recursively."""
        parent = Element("node")
        child1 = SubElement(parent, "children", attrib={"name": "level1"})
        child2 = SubElement(child1, "children", attrib={"name": "level2"})
        SubElement(child2, "children", attrib={"name": "level3"})

        result = _parse_nested_children(parent)
        assert len(result) == 1
        assert result[0]["name"] == "level1"
        assert len(result[0]["children"]) == 1
        assert result[0]["children"][0]["name"] == "level2"
        assert len(result[0]["children"][0]["children"]) == 1
        assert result[0]["children"][0]["children"][0]["name"] == "level3"


class TestBuildInputTreeNodeMap:
    """Tests for the _build_input_tree_node_map helper."""

    def test_empty_trees(self):
        assert _build_input_tree_node_map([]) == {}

    def test_basic_tree(self):
        input_trees = [{
            "name": "row1",
            "nodes": [{
                "name": "doc",
                "type": "id_Document",
                "children": [{
                    "name": "root",
                    "nodeType": "ELEMENT",
                    "children": [{
                        "name": "item",
                        "nodeType": "ELEMENT",
                        "children": [],
                    }],
                }],
            }],
        }]
        result = _build_input_tree_node_map(input_trees)

        assert "inputTrees.0/@nodes.0" in result
        assert result["inputTrees.0/@nodes.0"][0] == "doc"
        assert "inputTrees.0/@nodes.0/@children.0" in result
        assert result["inputTrees.0/@nodes.0/@children.0"][0] == "root"
        assert "inputTrees.0/@nodes.0/@children.0/@children.0" in result
        assert result["inputTrees.0/@nodes.0/@children.0/@children.0"][0] == "item"


class TestRewriteExpressionsForLoop:
    """Tests for the _rewrite_expressions_for_loop helper."""

    def test_no_looping_element(self):
        """No rewrite when looping_element is empty."""
        expressions = {"col1": "./root/item/name"}
        result = _rewrite_expressions_for_loop(expressions, "")
        assert result == expressions

    def test_inside_loop(self):
        """Fields inside the loop become relative paths."""
        expressions = {"name": "./item/name"}
        result = _rewrite_expressions_for_loop(expressions, "item")
        assert result["name"] == "./name"

    def test_outside_loop(self):
        """Fields outside the loop use ancestor:: axis."""
        expressions = {"header": "./header_field"}
        result = _rewrite_expressions_for_loop(expressions, "item")
        assert result["header"] == "./ancestor::header_field"

    def test_loop_element_itself(self):
        """When field path ends at the loop element, uses ./loop_name."""
        expressions = {"item_col": "./item"}
        result = _rewrite_expressions_for_loop(expressions, "item")
        assert result["item_col"] == "./item"

    def test_empty_expression_preserved(self):
        """Empty expressions are preserved as-is."""
        expressions = {"col": ""}
        result = _rewrite_expressions_for_loop(expressions, "item")
        assert result["col"] == ""


class TestDetectLoopingElement:
    """Tests for the _detect_looping_element helper."""

    def test_from_children_loop_true(self):
        """Detects loop from children element with loop=true."""
        root = Element("node")
        node_data = SubElement(root, "nodeData")
        input_tree = SubElement(node_data, "inputTrees", attrib={"name": "row1"})
        nodes = SubElement(input_tree, "nodes", attrib={"name": "doc"})
        child = SubElement(nodes, "children", attrib={"name": "item", "loop": "true"})

        result = _detect_looping_element(root, {})
        assert result == "item"

    def test_from_element_parameter(self):
        """Falls back to elementParameter LOOPING_ELEMENT."""
        root = Element("node")
        SubElement(root, "elementParameter", attrib={
            "name": "LOOPING_ELEMENT", "value": "record",
        })
        result = _detect_looping_element(root, {})
        assert result == "record"

    def test_auto_detect_deepest_node(self):
        """Falls back to deepest node in input tree map."""
        root = Element("node")
        node_map = {
            "inputTrees.0/@nodes.0": ("doc", "id_Document", {}),
            "inputTrees.0/@nodes.0/@children.0": ("root", "ELEMENT", {}),
            "inputTrees.0/@nodes.0/@children.0/@children.0": ("deepest", "ELEMENT", {}),
        }
        result = _detect_looping_element(root, node_map)
        assert result == "deepest"

    def test_none_raw_xml(self):
        """When raw_xml is None, returns empty string."""
        result = _detect_looping_element(None, {})
        assert result == ""


class TestBuildExpressions:
    """Tests for the _build_expressions helper."""

    def test_empty_connections(self):
        assert _build_expressions([], {}, {}) == {}

    def test_basic_mapping(self):
        """Connection maps source input node to output column."""
        node_map = {
            "inputTrees.0/@nodes.0": ("doc", "id_Document", {}),
            "inputTrees.0/@nodes.0/@children.0": ("root", "ELEMENT", {}),
            "inputTrees.0/@nodes.0/@children.0/@children.0": ("item", "ELEMENT", {}),
            "inputTrees.0/@nodes.0/@children.0/@children.0/@children.0": ("name", "ELEMENT", {}),
        }
        connections = [{
            "source": "inputTrees.0/@nodes.0/@children.0/@children.0/@children.0",
            "target": "outputTrees.0/@nodes.0",
            "sourceExpression": "",
        }]
        output_col_map = {0: "name_col"}

        result = _build_expressions(connections, node_map, output_col_map)
        assert "name_col" in result
        # Full path from doc node: doc/root/item/name
        assert result["name_col"] == "./doc/root/item/name"

    def test_root_stripping(self):
        """When first xpath element is 'root', it is stripped."""
        node_map = {
            "inputTrees.0/@nodes.0": ("root", "id_Document", {}),
            "inputTrees.0/@nodes.0/@children.0": ("item", "ELEMENT", {}),
            "inputTrees.0/@nodes.0/@children.0/@children.0": ("name", "ELEMENT", {}),
        }
        connections = [{
            "source": "inputTrees.0/@nodes.0/@children.0/@children.0",
            "target": "outputTrees.0/@nodes.0",
            "sourceExpression": "",
        }]
        output_col_map = {0: "name_col"}

        result = _build_expressions(connections, node_map, output_col_map)
        assert result["name_col"] == "./item/name"

    def test_attribute_node_type(self):
        """ATTRIBUT nodeType generates @attribute XPath syntax."""
        node_map = {
            "inputTrees.0/@nodes.0": ("doc", "id_Document", {}),
            "inputTrees.0/@nodes.0/@children.0": ("element", "ELEMENT", {}),
            "inputTrees.0/@nodes.0/@children.0/@children.0": ("attr_name", "ATTRIBUT", {}),
        }
        connections = [{
            "source": "inputTrees.0/@nodes.0/@children.0/@children.0",
            "target": "outputTrees.0/@nodes.0",
            "sourceExpression": "",
        }]
        output_col_map = {0: "attr_col"}

        result = _build_expressions(connections, node_map, output_col_map)
        assert "attr_col" in result
        assert "@attr_name" in result["attr_col"]
