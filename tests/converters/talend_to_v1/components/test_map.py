"""Tests for tMap -> Map converter — the most complex Talend component.

Covers: basic main-only input, lookups with join keys, variables, outputs
with columns, filters, join modes, reject outputs, empty mapper data,
registry integration, and DIE_ON_ERROR handling.
"""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.map import MapConverter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mapper_xml(
    input_tables_xml: str = "",
    var_tables_xml: str = "",
    output_tables_xml: str = "",
) -> ET.Element:
    """Build a minimal <node> element containing MapperData nodeData."""
    xml_str = (
        '<node componentName="tMap" posX="100" posY="200">'
        '  <nodeData xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
        '            xsi:type="pipeline:MapperData">'
        f"    {input_tables_xml}"
        f"    {var_tables_xml}"
        f"    {output_tables_xml}"
        "  </nodeData>"
        "</node>"
    )
    return ET.fromstring(xml_str)


def _make_node(
    raw_xml: ET.Element = None,
    params: dict = None,
    component_id: str = "tMap_1",
) -> TalendNode:
    return TalendNode(
        component_id=component_id,
        component_type="tMap",
        params=params or {},
        schema={},
        position={"x": 100, "y": 200},
        raw_xml=raw_xml,
    )


# ---------------------------------------------------------------------------
# Test: registry
# ---------------------------------------------------------------------------

class TestMapConverterRegistry:
    def test_registered_as_tmap(self):
        from src.converters.talend_to_v1.components.registry import REGISTRY
        assert REGISTRY.get("tMap") is MapConverter


# ---------------------------------------------------------------------------
# Test: basic main-only input
# ---------------------------------------------------------------------------

class TestMapConverterMainOnly:
    def test_basic_main_input(self):
        """Single main input with no lookups, variables, or output columns."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1" matchingMode="UNIQUE_MATCH" lookupMode="LOAD_ONCE"/>',
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["type"] == "Map"
        assert comp["original_type"] == "tMap"
        assert comp["id"] == "tMap_1"

        cfg = comp["config"]
        assert cfg["inputs"]["main"]["name"] == "row1"
        assert cfg["inputs"]["main"]["filter"] == ""
        assert cfg["inputs"]["main"]["activate_filter"] is False
        assert cfg["inputs"]["main"]["matching_mode"] == "UNIQUE_MATCH"
        assert cfg["inputs"]["main"]["lookup_mode"] == "LOAD_ONCE"
        assert cfg["inputs"]["lookups"] == []

    def test_main_with_active_filter(self):
        """Main input with an active expression filter."""
        raw_xml = _make_mapper_xml(
            input_tables_xml=(
                '<inputTables name="row1"'
                '  activateExpressionFilter="true"'
                '  expressionFilter="row1.status != null"/>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        main = result.component["config"]["inputs"]["main"]

        assert main["activate_filter"] is True
        assert main["filter"] == "{{java}}row1.status != null"

    def test_main_filter_inactive_not_prefixed(self):
        """When activateExpressionFilter is false, filter stays empty."""
        raw_xml = _make_mapper_xml(
            input_tables_xml=(
                '<inputTables name="row1"'
                '  activateExpressionFilter="false"'
                '  expressionFilter="row1.id > 0"/>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        main = result.component["config"]["inputs"]["main"]

        assert main["activate_filter"] is False
        assert main["filter"] == ""


# ---------------------------------------------------------------------------
# Test: lookups
# ---------------------------------------------------------------------------

class TestMapConverterLookups:
    def test_single_lookup_with_join_key(self):
        """A lookup table with one join key and inner join."""
        raw_xml = _make_mapper_xml(
            input_tables_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lookup1" innerJoin="true"'
                '  matchingMode="ALL_MATCHES" lookupMode="RELOAD">'
                '  <mapperTableEntries name="id" expression="row1.id"/>'
                "</inputTables>"
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})

        lookups = result.component["config"]["inputs"]["lookups"]
        assert len(lookups) == 1

        lk = lookups[0]
        assert lk["name"] == "lookup1"
        assert lk["matching_mode"] == "ALL_MATCHES"
        assert lk["lookup_mode"] == "RELOAD"
        assert lk["join_mode"] == "INNER_JOIN"
        assert len(lk["join_keys"]) == 1
        assert lk["join_keys"][0] == {
            "lookup_column": "id",
            "expression": "{{java}}row1.id",
        }

    def test_lookup_left_outer_join(self):
        """innerJoin=false (default) produces LEFT_OUTER_JOIN."""
        raw_xml = _make_mapper_xml(
            input_tables_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lookup1">'
                '  <mapperTableEntries name="key" expression="row1.key"/>'
                "</inputTables>"
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})

        lk = result.component["config"]["inputs"]["lookups"][0]
        assert lk["join_mode"] == "LEFT_OUTER_JOIN"

    def test_multiple_lookups(self):
        """Multiple lookup tables are all parsed."""
        raw_xml = _make_mapper_xml(
            input_tables_xml=(
                '<inputTables name="main_row"/>'
                '<inputTables name="lk1" innerJoin="true">'
                '  <mapperTableEntries name="a" expression="main_row.a"/>'
                "</inputTables>"
                '<inputTables name="lk2" innerJoin="false">'
                '  <mapperTableEntries name="b" expression="main_row.b"/>'
                "</inputTables>"
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})

        lookups = result.component["config"]["inputs"]["lookups"]
        assert len(lookups) == 2
        assert lookups[0]["name"] == "lk1"
        assert lookups[0]["join_mode"] == "INNER_JOIN"
        assert lookups[1]["name"] == "lk2"
        assert lookups[1]["join_mode"] == "LEFT_OUTER_JOIN"

    def test_lookup_with_filter(self):
        """A lookup with an active filter gets the {{java}} prefix."""
        raw_xml = _make_mapper_xml(
            input_tables_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lk1"'
                '  activateExpressionFilter="true"'
                '  expressionFilter="lk1.active == true">'
                '  <mapperTableEntries name="id" expression="row1.id"/>'
                "</inputTables>"
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})

        lk = result.component["config"]["inputs"]["lookups"][0]
        assert lk["activate_filter"] is True
        assert lk["filter"] == "{{java}}lk1.active == true"

    def test_lookup_no_expression_entries_skipped(self):
        """mapperTableEntries without expressions are not treated as join keys."""
        raw_xml = _make_mapper_xml(
            input_tables_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lk1">'
                '  <mapperTableEntries name="col_a"/>'
                '  <mapperTableEntries name="col_b" expression="row1.b"/>'
                "</inputTables>"
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})

        lk = result.component["config"]["inputs"]["lookups"][0]
        assert len(lk["join_keys"]) == 1
        assert lk["join_keys"][0]["lookup_column"] == "col_b"


# ---------------------------------------------------------------------------
# Test: variables
# ---------------------------------------------------------------------------

class TestMapConverterVariables:
    def test_variables_parsed(self):
        """Variable table entries with name+expression are captured."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            var_tables_xml=(
                "<varTables>"
                '  <mapperTableEntries name="v_name"'
                '    expression="row1.first + row1.last"'
                '    type="id_String"/>'
                '  <mapperTableEntries name="v_total"'
                '    expression="row1.qty * row1.price"'
                '    type="id_Double"/>'
                "</varTables>"
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})

        variables = result.component["config"]["variables"]
        assert len(variables) == 2
        assert variables[0] == {
            "name": "v_name",
            "expression": "{{java}}row1.first + row1.last",
            "type": "id_String",
        }
        assert variables[1] == {
            "name": "v_total",
            "expression": "{{java}}row1.qty * row1.price",
            "type": "id_Double",
        }

    def test_variables_skip_empty_expression(self):
        """Variables with empty expressions are skipped."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            var_tables_xml=(
                "<varTables>"
                '  <mapperTableEntries name="v_good" expression="row1.x" type="id_Integer"/>'
                '  <mapperTableEntries name="v_empty" expression="" type="id_String"/>'
                "</varTables>"
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})

        variables = result.component["config"]["variables"]
        assert len(variables) == 1
        assert variables[0]["name"] == "v_good"

    def test_variables_skip_empty_name(self):
        """Variables with empty names are skipped."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            var_tables_xml=(
                "<varTables>"
                '  <mapperTableEntries name="" expression="row1.x" type="id_Integer"/>'
                '  <mapperTableEntries name="v_ok" expression="row1.y" type="id_String"/>'
                "</varTables>"
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})

        variables = result.component["config"]["variables"]
        assert len(variables) == 1
        assert variables[0]["name"] == "v_ok"

    def test_default_type_is_id_string(self):
        """Missing type attribute defaults to id_String."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            var_tables_xml=(
                "<varTables>"
                '  <mapperTableEntries name="v1" expression="row1.x"/>'
                "</varTables>"
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})

        assert result.component["config"]["variables"][0]["type"] == "id_String"


# ---------------------------------------------------------------------------
# Test: outputs
# ---------------------------------------------------------------------------

class TestMapConverterOutputs:
    def test_output_with_columns(self):
        """Output table columns are parsed with expression, type, nullable."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml=(
                '<outputTables name="out1">'
                '  <mapperTableEntries name="id"'
                '    expression="row1.id"'
                '    type="id_Integer"'
                '    nullable="false"/>'
                '  <mapperTableEntries name="full_name"'
                '    expression="row1.first + row1.last"'
                '    type="id_String"'
                '    nullable="true"/>'
                "</outputTables>"
            ),
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})

        outputs = result.component["config"]["outputs"]
        assert len(outputs) == 1

        out = outputs[0]
        assert out["name"] == "out1"
        assert out["is_reject"] is False
        assert out["inner_join_reject"] is False
        assert len(out["columns"]) == 2

        assert out["columns"][0] == {
            "name": "id",
            "expression": "{{java}}row1.id",
            "type": "id_Integer",
            "nullable": False,
        }
        assert out["columns"][1] == {
            "name": "full_name",
            "expression": "{{java}}row1.first + row1.last",
            "type": "id_String",
            "nullable": True,
        }

    def test_output_filter(self):
        """Active output filter gets the {{java}} prefix."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml=(
                '<outputTables name="out1"'
                '  activateExpressionFilter="true"'
                '  expressionFilter="row1.amount > 0"/>'
            ),
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})

        out = result.component["config"]["outputs"][0]
        assert out["activate_filter"] is True
        assert out["filter"] == "{{java}}row1.amount > 0"

    def test_output_filter_inactive(self):
        """Inactive output filter stays empty."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml=(
                '<outputTables name="out1"'
                '  activateExpressionFilter="false"'
                '  expressionFilter="row1.x > 0"/>'
            ),
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})

        out = result.component["config"]["outputs"][0]
        assert out["activate_filter"] is False
        assert out["filter"] == ""

    def test_reject_output(self):
        """reject=true produces is_reject=True."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml='<outputTables name="reject_out" reject="true"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})

        out = result.component["config"]["outputs"][0]
        assert out["is_reject"] is True
        assert out["name"] == "reject_out"

    def test_inner_join_reject(self):
        """rejectInnerJoin=true produces inner_join_reject=True."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml=(
                '<outputTables name="ij_reject" reject="true" rejectInnerJoin="true"/>'
            ),
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})

        out = result.component["config"]["outputs"][0]
        assert out["is_reject"] is True
        assert out["inner_join_reject"] is True

    def test_multiple_outputs(self):
        """Multiple output tables are all captured."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml=(
                '<outputTables name="out1"/>'
                '<outputTables name="out2"/>'
                '<outputTables name="reject" reject="true"/>'
            ),
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})

        outputs = result.component["config"]["outputs"]
        assert len(outputs) == 3
        assert outputs[0]["name"] == "out1"
        assert outputs[1]["name"] == "out2"
        assert outputs[2]["name"] == "reject"
        assert outputs[2]["is_reject"] is True

    def test_column_empty_expression(self):
        """A column with no expression produces empty string (no {{java}} prefix)."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml=(
                '<outputTables name="out1">'
                '  <mapperTableEntries name="col1" expression="" type="id_String"/>'
                "</outputTables>"
            ),
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})

        col = result.component["config"]["outputs"][0]["columns"][0]
        assert col["expression"] == ""


# ---------------------------------------------------------------------------
# Test: component.inputs / component.outputs arrays (engine routing)
# ---------------------------------------------------------------------------

class TestMapConverterRoutingArrays:
    def test_inputs_array(self):
        """component['inputs'] lists main name + lookup names."""
        raw_xml = _make_mapper_xml(
            input_tables_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lk1"><mapperTableEntries name="k" expression="row1.k"/></inputTables>'
                '<inputTables name="lk2"><mapperTableEntries name="k" expression="row1.k"/></inputTables>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})

        assert result.component["inputs"] == ["row1", "lk1", "lk2"]

    def test_outputs_array(self):
        """component['outputs'] lists all output table names."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml=(
                '<outputTables name="out1"/>'
                '<outputTables name="out2"/>'
            ),
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})

        assert result.component["outputs"] == ["out1", "out2"]


# ---------------------------------------------------------------------------
# Test: empty / missing mapper data
# ---------------------------------------------------------------------------

class TestMapConverterEmptyMapper:
    def test_no_raw_xml(self):
        """Node with raw_xml=None produces empty config + warning."""
        node = _make_node(raw_xml=None)
        result = MapConverter().convert(node, [], {})

        assert result.component["config"] == {}
        assert any("No MapperData" in w for w in result.warnings)

    def test_no_mapper_data_element(self):
        """Node XML with no nodeData/MapperData produces empty config."""
        raw_xml = ET.fromstring('<node componentName="tMap"/>')
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})

        assert result.component["config"] == {}
        assert any("No MapperData" in w for w in result.warnings)

    def test_mapper_data_without_input_tables(self):
        """MapperData with no inputTables produces empty config + warning."""
        raw_xml = _make_mapper_xml(
            input_tables_xml="",
            output_tables_xml="",
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})

        assert result.component["config"] == {}
        assert any("No inputTables" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Test: DIE_ON_ERROR (audit CONV-MAP-001)
# ---------------------------------------------------------------------------

class TestMapConverterDieOnError:
    def test_die_on_error_default_true(self):
        """DIE_ON_ERROR defaults to True when not in params."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml, params={})
        result = MapConverter().convert(node, [], {})

        assert result.component["config"]["die_on_error"] is True

    def test_die_on_error_false(self):
        """DIE_ON_ERROR=false is captured."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml, params={"DIE_ON_ERROR": "false"})
        result = MapConverter().convert(node, [], {})

        assert result.component["config"]["die_on_error"] is False


# ---------------------------------------------------------------------------
# Test: full complex scenario
# ---------------------------------------------------------------------------

class TestMapConverterFullScenario:
    def test_full_tmap(self):
        """Full tMap with main, lookup, variables, and multiple outputs."""
        raw_xml = _make_mapper_xml(
            input_tables_xml=(
                '<inputTables name="customers"'
                '  activateExpressionFilter="true"'
                '  expressionFilter="customers.active == true"'
                '  matchingMode="UNIQUE_MATCH" lookupMode="LOAD_ONCE"/>'
                '<inputTables name="orders" innerJoin="true"'
                '  matchingMode="ALL_MATCHES" lookupMode="RELOAD"'
                '  activateExpressionFilter="true"'
                '  expressionFilter="orders.amount > 0">'
                '  <mapperTableEntries name="customer_id" expression="customers.id"/>'
                '  <mapperTableEntries name="region" expression="customers.region"/>'
                "</inputTables>"
            ),
            var_tables_xml=(
                "<varTables>"
                '  <mapperTableEntries name="full_name"'
                '    expression="customers.first + &quot; &quot; + customers.last"'
                '    type="id_String"/>'
                "</varTables>"
            ),
            output_tables_xml=(
                '<outputTables name="enriched"'
                '  activateExpressionFilter="true"'
                '  expressionFilter="Var.full_name != null">'
                '  <mapperTableEntries name="name" expression="Var.full_name"'
                '    type="id_String" nullable="true"/>'
                '  <mapperTableEntries name="total" expression="orders.amount"'
                '    type="id_Double" nullable="false"/>'
                "</outputTables>"
                '<outputTables name="rejects" reject="true" rejectInnerJoin="true"/>'
            ),
        )
        node = _make_node(raw_xml=raw_xml, params={"DIE_ON_ERROR": "true"})
        result = MapConverter().convert(node, [], {})
        comp = result.component
        cfg = comp["config"]

        # ── Inputs ──
        main = cfg["inputs"]["main"]
        assert main["name"] == "customers"
        assert main["activate_filter"] is True
        assert main["filter"] == "{{java}}customers.active == true"

        lookups = cfg["inputs"]["lookups"]
        assert len(lookups) == 1
        lk = lookups[0]
        assert lk["name"] == "orders"
        assert lk["join_mode"] == "INNER_JOIN"
        assert lk["matching_mode"] == "ALL_MATCHES"
        assert lk["lookup_mode"] == "RELOAD"
        assert lk["activate_filter"] is True
        assert lk["filter"] == "{{java}}orders.amount > 0"
        assert len(lk["join_keys"]) == 2
        assert lk["join_keys"][0] == {
            "lookup_column": "customer_id",
            "expression": "{{java}}customers.id",
        }
        assert lk["join_keys"][1] == {
            "lookup_column": "region",
            "expression": "{{java}}customers.region",
        }

        # ── Variables ──
        variables = cfg["variables"]
        assert len(variables) == 1
        assert variables[0]["name"] == "full_name"
        assert variables[0]["type"] == "id_String"
        # Expression contains XML-decoded quote entities
        assert variables[0]["expression"].startswith("{{java}}")

        # ── Outputs ──
        outputs = cfg["outputs"]
        assert len(outputs) == 2

        enriched = outputs[0]
        assert enriched["name"] == "enriched"
        assert enriched["is_reject"] is False
        assert enriched["activate_filter"] is True
        assert enriched["filter"] == "{{java}}Var.full_name != null"
        assert len(enriched["columns"]) == 2
        assert enriched["columns"][0]["name"] == "name"
        assert enriched["columns"][0]["nullable"] is True
        assert enriched["columns"][1]["name"] == "total"
        assert enriched["columns"][1]["nullable"] is False

        rejects = outputs[1]
        assert rejects["name"] == "rejects"
        assert rejects["is_reject"] is True
        assert rejects["inner_join_reject"] is True

        # ── Routing arrays ──
        assert comp["inputs"] == ["customers", "orders"]
        assert comp["outputs"] == ["enriched", "rejects"]

        # ── DIE_ON_ERROR ──
        assert cfg["die_on_error"] is True

    def test_component_structure_keys(self):
        """Output dict has all required top-level keys."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        comp = result.component

        expected_keys = {
            "id", "type", "original_type", "position",
            "config", "schema", "inputs", "outputs",
        }
        assert set(comp.keys()) == expected_keys
