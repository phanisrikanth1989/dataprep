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
            "type": "id_String",
            "nullable": True,
            "operator": "",
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
            "nullable": True,
        }
        assert variables[1] == {
            "name": "v_total",
            "expression": "{{java}}row1.qty * row1.price",
            "type": "id_Double",
            "nullable": True,
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
            "operator": "",
            "length": -1,
            "precision": -1,
            "pattern": "",
        }
        assert out["columns"][1] == {
            "name": "full_name",
            "expression": "{{java}}row1.first + row1.last",
            "type": "id_String",
            "nullable": True,
            "operator": "",
            "length": -1,
            "precision": -1,
            "pattern": "",
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
            "type": "id_String",
            "nullable": True,
            "operator": "",
        }
        assert lk["join_keys"][1] == {
            "lookup_column": "region",
            "expression": "{{java}}customers.region",
            "type": "id_String",
            "nullable": True,
            "operator": "",
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


# ---------------------------------------------------------------------------
# Test: top-level elementParameter params (Task 1)
# ---------------------------------------------------------------------------

class TestMapConverterTopLevelParams:
    """Verify all 9 new top-level params are extracted from elementParameters."""

    def _convert_with_params(self, params: dict):
        """Helper: create a minimal tMap node with given params and convert."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml, params=params)
        return MapConverter().convert(node, [], {})

    # --- Defaults (no params provided) ---

    def test_tstatcatcher_stats_default_false(self):
        result = self._convert_with_params({})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        result = self._convert_with_params({})
        assert result.component["config"]["label"] == ""

    def test_lkup_parallelize_default_false(self):
        result = self._convert_with_params({})
        assert result.component["config"]["lkup_parallelize"] is False

    def test_enable_auto_convert_type_default_false(self):
        result = self._convert_with_params({})
        assert result.component["config"]["enable_auto_convert_type"] is False

    def test_store_on_disk_default_false(self):
        result = self._convert_with_params({})
        assert result.component["config"]["store_on_disk"] is False

    def test_temp_data_directory_default_empty(self):
        result = self._convert_with_params({})
        assert result.component["config"]["temp_data_directory"] == ""

    def test_rows_buffer_size_default(self):
        result = self._convert_with_params({})
        assert result.component["config"]["rows_buffer_size"] == 2000000

    def test_change_hash_and_equals_for_bigdecimal_default_false(self):
        result = self._convert_with_params({})
        assert result.component["config"]["change_hash_and_equals_for_bigdecimal"] is False

    def test_link_style_default_empty(self):
        result = self._convert_with_params({})
        assert result.component["config"]["link_style"] == ""

    # --- Extraction (params provided) ---

    def test_tstatcatcher_stats_extracted(self):
        result = self._convert_with_params({"TSTATCATCHER_STATS": "true"})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        result = self._convert_with_params({"LABEL": '"My tMap"'})
        assert result.component["config"]["label"] == "My tMap"

    def test_lkup_parallelize_extracted(self):
        result = self._convert_with_params({"LKUP_PARALLELIZE": "true"})
        assert result.component["config"]["lkup_parallelize"] is True

    def test_enable_auto_convert_type_extracted(self):
        result = self._convert_with_params({"ENABLE_AUTO_CONVERT_TYPE": "true"})
        assert result.component["config"]["enable_auto_convert_type"] is True

    def test_store_on_disk_extracted(self):
        result = self._convert_with_params({"STORE_ON_DISK": "true"})
        assert result.component["config"]["store_on_disk"] is True

    def test_temp_data_directory_extracted(self):
        result = self._convert_with_params({"TEMPORARY_DATA_DIRECTORY": '"/tmp/tmap"'})
        assert result.component["config"]["temp_data_directory"] == "/tmp/tmap"

    def test_rows_buffer_size_extracted(self):
        result = self._convert_with_params({"ROWS_BUFFER_SIZE": "5000000"})
        assert result.component["config"]["rows_buffer_size"] == 5000000

    def test_change_hash_bigdecimal_extracted(self):
        result = self._convert_with_params({"CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL": "true"})
        assert result.component["config"]["change_hash_and_equals_for_bigdecimal"] is True

    def test_link_style_extracted(self):
        result = self._convert_with_params({"LINK_STYLE": '"AUTO"'})
        assert result.component["config"]["link_style"] == "AUTO"


# ---------------------------------------------------------------------------
# Test: input table enhancements (Task 2)
# ---------------------------------------------------------------------------

class TestMapConverterInputEnhancements:
    """Verify new attributes on main input, lookup tables, and join key entries."""

    # --- Main input new attributes ---

    def test_main_size_state_default(self):
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        main = result.component["config"]["inputs"]["main"]
        assert main["size_state"] == ""

    def test_main_size_state_extracted(self):
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1" sizeState="INTERMEDIATE"/>',
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        main = result.component["config"]["inputs"]["main"]
        assert main["size_state"] == "INTERMEDIATE"

    def test_main_activate_condensed_tool_default(self):
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        main = result.component["config"]["inputs"]["main"]
        assert main["activate_condensed_tool"] is False

    def test_main_activate_global_map_default(self):
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        main = result.component["config"]["inputs"]["main"]
        assert main["activate_global_map"] is False

    # --- Lookup new table-level attributes ---

    def test_lookup_size_state_extracted(self):
        raw_xml = _make_mapper_xml(
            input_tables_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lk1" sizeState="MAXIMIZED">'
                '  <mapperTableEntries name="id" expression="row1.id"/>'
                '</inputTables>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        lk = result.component["config"]["inputs"]["lookups"][0]
        assert lk["size_state"] == "MAXIMIZED"

    def test_lookup_persistent_default_false(self):
        raw_xml = _make_mapper_xml(
            input_tables_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lk1">'
                '  <mapperTableEntries name="id" expression="row1.id"/>'
                '</inputTables>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        lk = result.component["config"]["inputs"]["lookups"][0]
        assert lk["persistent"] is False

    def test_lookup_persistent_true(self):
        raw_xml = _make_mapper_xml(
            input_tables_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lk1" persistent="true">'
                '  <mapperTableEntries name="id" expression="row1.id"/>'
                '</inputTables>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        lk = result.component["config"]["inputs"]["lookups"][0]
        assert lk["persistent"] is True

    def test_lookup_activate_global_map_true(self):
        raw_xml = _make_mapper_xml(
            input_tables_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lk1" activateGlobalMap="true">'
                '  <mapperTableEntries name="id" expression="row1.id"/>'
                '</inputTables>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        lk = result.component["config"]["inputs"]["lookups"][0]
        assert lk["activate_global_map"] is True

    # --- Join key entry enhancements ---

    def test_join_key_type_extracted(self):
        raw_xml = _make_mapper_xml(
            input_tables_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lk1">'
                '  <mapperTableEntries name="id" expression="row1.id" type="id_Integer"/>'
                '</inputTables>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        jk = result.component["config"]["inputs"]["lookups"][0]["join_keys"][0]
        assert jk["type"] == "id_Integer"

    def test_join_key_nullable_false(self):
        raw_xml = _make_mapper_xml(
            input_tables_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lk1">'
                '  <mapperTableEntries name="id" expression="row1.id" nullable="false"/>'
                '</inputTables>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        jk = result.component["config"]["inputs"]["lookups"][0]["join_keys"][0]
        assert jk["nullable"] is False

    def test_join_key_operator_extracted(self):
        """Join key with operator='=' should be detected and operator captured."""
        raw_xml = _make_mapper_xml(
            input_tables_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lk1">'
                '  <mapperTableEntries name="id" expression="row1.id" operator="="/>'
                '</inputTables>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        jk = result.component["config"]["inputs"]["lookups"][0]["join_keys"][0]
        assert jk["operator"] == "="

    # --- Correctness fix: operator-only join key detection ---

    def test_join_key_detected_by_operator_only(self):
        """Entry with operator='=' but NO expression should still be a join key."""
        raw_xml = _make_mapper_xml(
            input_tables_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lk1">'
                '  <mapperTableEntries name="id" operator="="/>'
                '</inputTables>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        lk = result.component["config"]["inputs"]["lookups"][0]
        assert len(lk["join_keys"]) == 1
        assert lk["join_keys"][0]["lookup_column"] == "id"
        assert lk["join_keys"][0]["operator"] == "="
        assert lk["join_keys"][0]["expression"] == ""

    def test_non_join_entry_still_skipped(self):
        """Entry with no expression AND no operator is NOT a join key."""
        raw_xml = _make_mapper_xml(
            input_tables_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lk1">'
                '  <mapperTableEntries name="col_a"/>'
                '  <mapperTableEntries name="col_b" expression="row1.b"/>'
                '</inputTables>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        lk = result.component["config"]["inputs"]["lookups"][0]
        assert len(lk["join_keys"]) == 1
        assert lk["join_keys"][0]["lookup_column"] == "col_b"


# ---------------------------------------------------------------------------
# Test: variable table enhancements (Task 3)
# ---------------------------------------------------------------------------

class TestMapConverterVariableEnhancements:
    """Verify table-level name/size_state and per-entry nullable on variables."""

    # --- Table-level attributes (stored at config root) ---

    def test_var_table_name_default(self):
        """Default var table name is 'Var' when varTables has no name attr."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            var_tables_xml=(
                '<varTables>'
                '  <mapperTableEntries name="v1" expression="row1.x" type="id_String"/>'
                '</varTables>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        assert result.component["config"]["var_table_name"] == "Var"

    def test_var_table_name_extracted(self):
        """Custom var table name is captured."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            var_tables_xml=(
                '<varTables name="MyVars">'
                '  <mapperTableEntries name="v1" expression="row1.x" type="id_String"/>'
                '</varTables>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        assert result.component["config"]["var_table_name"] == "MyVars"

    def test_var_table_name_empty_when_no_var_table(self):
        """When there is no varTables element, var_table_name defaults to empty."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        assert result.component["config"]["var_table_name"] == ""

    def test_var_table_size_state_default(self):
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            var_tables_xml=(
                '<varTables>'
                '  <mapperTableEntries name="v1" expression="row1.x" type="id_String"/>'
                '</varTables>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        assert result.component["config"]["var_table_size_state"] == ""

    def test_var_table_size_state_extracted(self):
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            var_tables_xml=(
                '<varTables sizeState="MINIMIZED">'
                '  <mapperTableEntries name="v1" expression="row1.x" type="id_String"/>'
                '</varTables>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        assert result.component["config"]["var_table_size_state"] == "MINIMIZED"

    # --- Per-entry nullable ---

    def test_variable_nullable_default_true(self):
        """Variables default to nullable=True when not specified."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            var_tables_xml=(
                '<varTables>'
                '  <mapperTableEntries name="v1" expression="row1.x" type="id_String"/>'
                '</varTables>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        assert result.component["config"]["variables"][0]["nullable"] is True

    def test_variable_nullable_false(self):
        """Variable with nullable='false' is captured."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            var_tables_xml=(
                '<varTables>'
                '  <mapperTableEntries name="v1" expression="row1.x"'
                '    type="id_Integer" nullable="false"/>'
                '</varTables>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        assert result.component["config"]["variables"][0]["nullable"] is False


# ---------------------------------------------------------------------------
# Test: output table enhancements (Task 4)
# ---------------------------------------------------------------------------

class TestMapConverterOutputEnhancements:
    """Verify new table-level and per-column attributes on outputs."""

    # --- Table-level attributes ---

    def test_output_size_state_default(self):
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        assert result.component["config"]["outputs"][0]["size_state"] == ""

    def test_output_size_state_extracted(self):
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml='<outputTables name="out1" sizeState="MAXIMIZED"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        assert result.component["config"]["outputs"][0]["size_state"] == "MAXIMIZED"

    def test_output_catch_output_reject_default_false(self):
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        assert result.component["config"]["outputs"][0]["catch_output_reject"] is False

    def test_output_catch_output_reject_true(self):
        """activateCondensedTool on OUTPUT means 'Catch Output Reject'."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml=(
                '<outputTables name="out1"'
                '  activateExpressionFilter="true"'
                '  expressionFilter="row1.x > 0"/>'
                '<outputTables name="out2" activateCondensedTool="true"/>'
            ),
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        outputs = result.component["config"]["outputs"]
        assert outputs[0]["catch_output_reject"] is False
        assert outputs[1]["catch_output_reject"] is True

    def test_output_activate_global_map_default_false(self):
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        assert result.component["config"]["outputs"][0]["activate_global_map"] is False

    def test_output_activate_global_map_true(self):
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml='<outputTables name="out1" activateGlobalMap="true"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        assert result.component["config"]["outputs"][0]["activate_global_map"] is True

    # --- Per-column attributes ---

    def test_output_column_operator_default(self):
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml=(
                '<outputTables name="out1">'
                '  <mapperTableEntries name="col1" expression="row1.x" type="id_String"/>'
                '</outputTables>'
            ),
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        col = result.component["config"]["outputs"][0]["columns"][0]
        assert col["operator"] == ""

    def test_output_column_operator_extracted(self):
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml=(
                '<outputTables name="out1">'
                '  <mapperTableEntries name="col1" expression="row1.x"'
                '    type="id_String" operator="="/>'
                '</outputTables>'
            ),
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        col = result.component["config"]["outputs"][0]["columns"][0]
        assert col["operator"] == "="

    def test_output_column_length_default(self):
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml=(
                '<outputTables name="out1">'
                '  <mapperTableEntries name="col1" expression="row1.x" type="id_String"/>'
                '</outputTables>'
            ),
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        col = result.component["config"]["outputs"][0]["columns"][0]
        assert col["length"] == -1

    def test_output_column_length_extracted(self):
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml=(
                '<outputTables name="out1">'
                '  <mapperTableEntries name="col1" expression="row1.x"'
                '    type="id_String" length="50"/>'
                '</outputTables>'
            ),
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        col = result.component["config"]["outputs"][0]["columns"][0]
        assert col["length"] == 50

    def test_output_column_precision_default(self):
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml=(
                '<outputTables name="out1">'
                '  <mapperTableEntries name="col1" expression="row1.x" type="id_Double"/>'
                '</outputTables>'
            ),
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        col = result.component["config"]["outputs"][0]["columns"][0]
        assert col["precision"] == -1

    def test_output_column_precision_extracted(self):
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml=(
                '<outputTables name="out1">'
                '  <mapperTableEntries name="col1" expression="row1.x"'
                '    type="id_Double" precision="4"/>'
                '</outputTables>'
            ),
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        col = result.component["config"]["outputs"][0]["columns"][0]
        assert col["precision"] == 4

    def test_output_column_pattern_default(self):
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml=(
                '<outputTables name="out1">'
                '  <mapperTableEntries name="col1" expression="row1.x" type="id_Date"/>'
                '</outputTables>'
            ),
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        col = result.component["config"]["outputs"][0]["columns"][0]
        assert col["pattern"] == ""

    def test_output_column_pattern_extracted(self):
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml=(
                '<outputTables name="out1">'
                '  <mapperTableEntries name="col1" expression="row1.date"'
                '    type="id_Date" pattern="&quot;yyyy-MM-dd&quot;"/>'
                '</outputTables>'
            ),
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        col = result.component["config"]["outputs"][0]["columns"][0]
        assert col["pattern"] == '"yyyy-MM-dd"'

    def test_output_column_all_new_attrs_together(self):
        """A single column with all new attributes set."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml=(
                '<outputTables name="out1">'
                '  <mapperTableEntries name="amount" expression="row1.amount"'
                '    type="id_BigDecimal" nullable="false" operator=""'
                '    length="10" precision="2" pattern=""/>'
                '</outputTables>'
            ),
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        col = result.component["config"]["outputs"][0]["columns"][0]
        assert col == {
            "name": "amount",
            "expression": "{{java}}row1.amount",
            "type": "id_BigDecimal",
            "nullable": False,
            "operator": "",
            "length": 10,
            "precision": 2,
            "pattern": "",
        }


# ---------------------------------------------------------------------------
# Test: engine-gap warnings (Task 5)
# ---------------------------------------------------------------------------

class TestMapConverterEngineGapWarnings:
    """Verify engine-gap warnings are emitted for unsupported features."""

    def _convert_with_params(self, params=None, input_xml=None, output_xml=None):
        """Helper: build a tMap node and convert it."""
        raw_xml = _make_mapper_xml(
            input_tables_xml=input_xml or '<inputTables name="row1"/>',
            output_tables_xml=output_xml or '<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml, params=params or {})
        return MapConverter().convert(node, [], {})

    # --- No warnings on defaults ---

    def test_no_engine_gap_warnings_on_defaults(self):
        """Default config should produce zero engine-gap warnings."""
        result = self._convert_with_params()
        engine_warnings = [w for w in result.warnings if "engine" in w.lower()]
        assert engine_warnings == []

    # --- Top-level warnings ---

    def test_warning_lkup_parallelize(self):
        result = self._convert_with_params(params={"LKUP_PARALLELIZE": "true"})
        assert any("LKUP_PARALLELIZE" in w for w in result.warnings)

    def test_warning_store_on_disk(self):
        result = self._convert_with_params(params={"STORE_ON_DISK": "true"})
        assert any("STORE_ON_DISK" in w for w in result.warnings)

    def test_warning_enable_auto_convert_type(self):
        result = self._convert_with_params(params={"ENABLE_AUTO_CONVERT_TYPE": "true"})
        assert any("ENABLE_AUTO_CONVERT_TYPE" in w for w in result.warnings)

    def test_warning_change_hash_bigdecimal(self):
        result = self._convert_with_params(
            params={"CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL": "true"}
        )
        assert any("CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL" in w for w in result.warnings)

    def test_no_warning_lkup_parallelize_false(self):
        result = self._convert_with_params(params={"LKUP_PARALLELIZE": "false"})
        assert not any("LKUP_PARALLELIZE" in w for w in result.warnings)

    # --- Per-lookup warnings ---

    def test_warning_reload_at_each_row(self):
        result = self._convert_with_params(
            input_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lk1" lookupMode="RELOAD_AT_EACH_ROW">'
                '  <mapperTableEntries name="id" expression="row1.id"/>'
                '</inputTables>'
            ),
        )
        assert any("RELOAD_AT_EACH_ROW" in w and "lk1" in w for w in result.warnings)

    def test_warning_reload_at_each_row_cache(self):
        result = self._convert_with_params(
            input_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lk1" lookupMode="RELOAD_AT_EACH_ROW_CACHE">'
                '  <mapperTableEntries name="id" expression="row1.id"/>'
                '</inputTables>'
            ),
        )
        assert any("RELOAD_AT_EACH_ROW_CACHE" in w and "lk1" in w for w in result.warnings)

    def test_no_warning_load_once(self):
        """LOAD_ONCE is supported -- no warning."""
        result = self._convert_with_params(
            input_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lk1" lookupMode="LOAD_ONCE">'
                '  <mapperTableEntries name="id" expression="row1.id"/>'
                '</inputTables>'
            ),
        )
        assert not any("RELOAD" in w for w in result.warnings)

    def test_warning_lookup_persistent(self):
        result = self._convert_with_params(
            input_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lk1" persistent="true">'
                '  <mapperTableEntries name="id" expression="row1.id"/>'
                '</inputTables>'
            ),
        )
        assert any("persistent" in w and "lk1" in w for w in result.warnings)

    def test_warning_lookup_activate_global_map(self):
        result = self._convert_with_params(
            input_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lk1" activateGlobalMap="true">'
                '  <mapperTableEntries name="id" expression="row1.id"/>'
                '</inputTables>'
            ),
        )
        assert any("activateGlobalMap" in w and "lk1" in w for w in result.warnings)

    def test_warning_all_rows_matching(self):
        result = self._convert_with_params(
            input_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lk1" matchingMode="ALL_ROWS">'
                '  <mapperTableEntries name="id" expression="row1.id"/>'
                '</inputTables>'
            ),
        )
        assert any("ALL_ROWS" in w and "lk1" in w for w in result.warnings)

    def test_no_warning_unique_match(self):
        """UNIQUE_MATCH is supported -- no warning."""
        result = self._convert_with_params(
            input_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lk1" matchingMode="UNIQUE_MATCH">'
                '  <mapperTableEntries name="id" expression="row1.id"/>'
                '</inputTables>'
            ),
        )
        assert not any("ALL_ROWS" in w for w in result.warnings)

    # --- Per-output warnings ---

    def test_warning_catch_output_reject(self):
        result = self._convert_with_params(
            output_xml=(
                '<outputTables name="out1"'
                '  activateExpressionFilter="true"'
                '  expressionFilter="row1.x > 0"/>'
                '<outputTables name="out2" activateCondensedTool="true"/>'
            ),
        )
        assert any("Catch Output Reject" in w and "out2" in w for w in result.warnings)

    def test_warning_output_activate_global_map(self):
        result = self._convert_with_params(
            output_xml='<outputTables name="out1" activateGlobalMap="true"/>',
        )
        assert any("activateGlobalMap" in w and "out1" in w for w in result.warnings)

    def test_no_warning_output_defaults(self):
        """Output with defaults should not produce warnings."""
        result = self._convert_with_params(
            output_xml='<outputTables name="out1"/>',
        )
        output_warnings = [
            w for w in result.warnings
            if "out1" in w and "engine" in w.lower()
        ]
        assert output_warnings == []

    # --- Multiple warnings from different sources ---

    def test_multiple_warnings_accumulated(self):
        """Multiple unsupported features produce multiple warnings."""
        result = self._convert_with_params(
            params={"STORE_ON_DISK": "true", "LKUP_PARALLELIZE": "true"},
            input_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lk1" persistent="true">'
                '  <mapperTableEntries name="id" expression="row1.id"/>'
                '</inputTables>'
            ),
            output_xml='<outputTables name="out1" activateGlobalMap="true"/>',
        )
        assert any("STORE_ON_DISK" in w for w in result.warnings)
        assert any("LKUP_PARALLELIZE" in w for w in result.warnings)
        assert any("persistent" in w for w in result.warnings)
        assert any("activateGlobalMap" in w and "out1" in w for w in result.warnings)
        assert len(result.warnings) >= 4


# ---------------------------------------------------------------------------
# Test: completeness (Task 6)
# ---------------------------------------------------------------------------

class TestMapConverterCompleteness:
    """Verify ALL expected config keys are present after full conversion."""

    def test_all_top_level_config_keys_present(self):
        """Verify all 15 top-level config keys exist."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            var_tables_xml=(
                '<varTables name="Var">'
                '  <mapperTableEntries name="v1" expression="row1.x" type="id_String"/>'
                '</varTables>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        cfg = result.component["config"]

        expected_keys = {
            # Structural
            "inputs",
            "variables",
            "outputs",
            # Variable table-level
            "var_table_name",
            "var_table_size_state",
            # elementParameter params
            "die_on_error",
            "tstatcatcher_stats",
            "label",
            "lkup_parallelize",
            "enable_auto_convert_type",
            "store_on_disk",
            "temp_data_directory",
            "rows_buffer_size",
            "change_hash_and_equals_for_bigdecimal",
            "link_style",
        }
        assert set(cfg.keys()) == expected_keys

    def test_main_input_keys(self):
        """Verify all keys on the main input dict."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        main = result.component["config"]["inputs"]["main"]

        expected_main_keys = {
            "name",
            "filter",
            "activate_filter",
            "matching_mode",
            "lookup_mode",
            "size_state",
            "persistent",
            "activate_condensed_tool",
            "activate_global_map",
        }
        assert set(main.keys()) == expected_main_keys

    def test_lookup_keys(self):
        """Verify all keys on a lookup dict."""
        raw_xml = _make_mapper_xml(
            input_tables_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lk1">'
                '  <mapperTableEntries name="id" expression="row1.id"/>'
                '</inputTables>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        lk = result.component["config"]["inputs"]["lookups"][0]

        expected_lookup_keys = {
            "name",
            "matching_mode",
            "lookup_mode",
            "filter",
            "activate_filter",
            "join_keys",
            "join_mode",
            "size_state",
            "persistent",
            "activate_condensed_tool",
            "activate_global_map",
        }
        assert set(lk.keys()) == expected_lookup_keys

    def test_join_key_entry_keys(self):
        """Verify all keys on a join key entry dict."""
        raw_xml = _make_mapper_xml(
            input_tables_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lk1">'
                '  <mapperTableEntries name="id" expression="row1.id"'
                '    type="id_Integer" nullable="false" operator="="/>'
                '</inputTables>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        jk = result.component["config"]["inputs"]["lookups"][0]["join_keys"][0]

        expected_jk_keys = {
            "lookup_column",
            "expression",
            "type",
            "nullable",
            "operator",
        }
        assert set(jk.keys()) == expected_jk_keys

    def test_variable_entry_keys(self):
        """Verify all keys on a variable entry dict."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            var_tables_xml=(
                '<varTables>'
                '  <mapperTableEntries name="v1" expression="row1.x" type="id_String"/>'
                '</varTables>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        var = result.component["config"]["variables"][0]

        expected_var_keys = {
            "name",
            "expression",
            "type",
            "nullable",
        }
        assert set(var.keys()) == expected_var_keys

    def test_output_table_keys(self):
        """Verify all keys on an output table dict."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml='<outputTables name="out1"/>',
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        out = result.component["config"]["outputs"][0]

        expected_output_keys = {
            "name",
            "is_reject",
            "inner_join_reject",
            "filter",
            "activate_filter",
            "columns",
            "size_state",
            "catch_output_reject",
            "activate_global_map",
        }
        assert set(out.keys()) == expected_output_keys

    def test_output_column_keys(self):
        """Verify all keys on an output column dict."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml=(
                '<outputTables name="out1">'
                '  <mapperTableEntries name="col1" expression="row1.x"'
                '    type="id_String" nullable="true"/>'
                '</outputTables>'
            ),
        )
        node = _make_node(raw_xml=raw_xml)
        result = MapConverter().convert(node, [], {})
        col = result.component["config"]["outputs"][0]["columns"][0]

        expected_col_keys = {
            "name",
            "expression",
            "type",
            "nullable",
            "operator",
            "length",
            "precision",
            "pattern",
        }
        assert set(col.keys()) == expected_col_keys
