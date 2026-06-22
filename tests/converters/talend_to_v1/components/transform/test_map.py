"""Tests for MapConverter (tMap -> v1 Map config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.map import MapConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

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


def _make_node(params=None, schema=None, component_id="m_1",
               component_type="tMap", raw_xml=None):
    """Create a TalendNode for testing."""
    if raw_xml is None:
        # Default: minimal valid MapperData
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml='<outputTables name="out1"/>',
        )
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 100, "y": 200},
        raw_xml=raw_xml,
    )


def _convert(params=None, raw_xml=None, component_id="m_1"):
    """Helper: create node and convert."""
    node = _make_node(params=params, raw_xml=raw_xml, component_id=component_id)
    return MapConverter().convert(node, [], {})


# ------------------------------------------------------------------
# TestRegistration
# ------------------------------------------------------------------

class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tMap") is MapConverter


# ------------------------------------------------------------------
# TestDefaults
# ------------------------------------------------------------------

class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    # link_style removed in a943b5f (hidden Talend param)

    def test_die_on_error_default_true(self):
        result = _convert()
        assert result.component["config"]["die_on_error"] is True

    # lkup_parallelize removed in a943b5f (hidden Talend param)

    def test_enable_auto_convert_type_default_false(self):
        result = _convert()
        assert result.component["config"]["enable_auto_convert_type"] is False

    def test_rows_buffer_size_default(self):
        result = _convert()
        assert result.component["config"]["rows_buffer_size"] == "2000000"

    def test_change_hash_default_true(self):
        """FIXED: Default is True per _java.xml (was False)."""
        result = _convert()
        assert result.component["config"]["change_hash_and_equals_for_bigdecimal"] is True

    # levenshtein, jaccard removed in a943b5f (hidden Talend params)

    def test_tstatcatcher_stats_default_false(self):
        result = _convert()
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        result = _convert()
        assert result.component["config"]["label"] == ""


# ------------------------------------------------------------------
# TestParameterExtraction
# ------------------------------------------------------------------

class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    # link_style extraction test removed in a943b5f (hidden Talend param)

    def test_rows_buffer_size_custom(self):
        result = _convert(params={"ROWS_BUFFER_SIZE": '"5000000"'})
        assert result.component["config"]["rows_buffer_size"] == "5000000"

    # levenshtein, jaccard extraction tests removed in a943b5f (hidden Talend params)

    def test_die_on_error_false(self):
        result = _convert(params={"DIE_ON_ERROR": "false"})
        assert result.component["config"]["die_on_error"] is False

    # lkup_parallelize extraction test removed in a943b5f (hidden Talend param)

    def test_enable_auto_convert_type_true(self):
        result = _convert(params={"ENABLE_AUTO_CONVERT_TYPE": "true"})
        assert result.component["config"]["enable_auto_convert_type"] is True

    def test_change_hash_false(self):
        result = _convert(params={"CHANGE_HASH_AND_EQUALS_FOR_BIGDECIMAL": "false"})
        assert result.component["config"]["change_hash_and_equals_for_bigdecimal"] is False

    def test_tstatcatcher_stats_true(self):
        result = _convert(params={"TSTATCATCHER_STATS": "true"})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        result = _convert(params={"LABEL": '"My tMap"'})
        assert result.component["config"]["label"] == "My tMap"


# ------------------------------------------------------------------
# TestMultiFlow (per D-75 -- MANDATORY)
# ------------------------------------------------------------------

class TestMultiFlow:
    """Multi-flow scenarios per D-75: main-only, main+lookup, main+reject, all three, inner/outer join."""

    def test_main_only(self):
        """nodeData with only main inputTable + outputTable."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml='<outputTables name="out1"/>',
        )
        result = _convert(raw_xml=raw_xml)
        cfg = result.component["config"]

        # Main input present
        assert cfg["inputs"]["main"]["name"] == "row1"
        # No lookups
        assert cfg["inputs"]["lookups"] == []
        # Single output
        assert len(cfg["outputs"]) == 1
        assert cfg["outputs"][0]["name"] == "out1"
        assert cfg["outputs"][0]["is_reject"] is False
        # No variables
        assert cfg["variables"] == []

    def test_main_plus_lookup(self):
        """nodeData with main + lookup inputTable (innerJoin=true, matchingMode=UNIQUE_MATCH)."""
        raw_xml = _make_mapper_xml(
            input_tables_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lookup1" innerJoin="true" matchingMode="UNIQUE_MATCH">'
                '  <mapperTableEntries name="lookup_id" expression="row1.id" type="id_Integer"/>'
                '</inputTables>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        result = _convert(raw_xml=raw_xml)
        cfg = result.component["config"]

        assert cfg["inputs"]["main"]["name"] == "row1"
        assert len(cfg["inputs"]["lookups"]) == 1
        lk = cfg["inputs"]["lookups"][0]
        assert lk["name"] == "lookup1"
        assert lk["join_mode"] == "INNER_JOIN"
        assert lk["matching_mode"] == "UNIQUE_MATCH"
        assert len(lk["join_keys"]) == 1
        assert lk["join_keys"][0]["lookup_column"] == "lookup_id"
        assert lk["join_keys"][0]["expression"] == "{{java}}row1.id"

    def test_main_plus_reject(self):
        """nodeData with main + reject outputTable (reject=true)."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml=(
                '<outputTables name="out1"/>'
                '<outputTables name="reject1" reject="true" rejectInnerJoin="true"/>'
            ),
        )
        result = _convert(raw_xml=raw_xml)
        cfg = result.component["config"]

        assert len(cfg["outputs"]) == 2
        out = cfg["outputs"][0]
        assert out["name"] == "out1"
        assert out["is_reject"] is False
        reject = cfg["outputs"][1]
        assert reject["name"] == "reject1"
        assert reject["is_reject"] is True
        assert reject["inner_join_reject"] is True

    def test_all_three_flows(self):
        """nodeData with main + lookup + reject + varTable -> all populated."""
        raw_xml = _make_mapper_xml(
            input_tables_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lookup1" innerJoin="true">'
                '  <mapperTableEntries name="lk_id" expression="row1.id" type="id_Integer"/>'
                '</inputTables>'
            ),
            var_tables_xml=(
                '<varTables name="Var">'
                '  <mapperTableEntries name="var1" expression="row1.name" type="id_String"/>'
                '</varTables>'
            ),
            output_tables_xml=(
                '<outputTables name="out1">'
                '  <mapperTableEntries name="output_id" expression="row1.id" type="id_Integer"/>'
                '</outputTables>'
                '<outputTables name="reject1" reject="true" rejectInnerJoin="true">'
                '  <mapperTableEntries name="reject_id" expression="row1.id" type="id_Integer"/>'
                '</outputTables>'
            ),
        )
        result = _convert(raw_xml=raw_xml)
        cfg = result.component["config"]

        # Main
        assert cfg["inputs"]["main"]["name"] == "row1"
        # Lookup
        assert len(cfg["inputs"]["lookups"]) == 1
        assert cfg["inputs"]["lookups"][0]["name"] == "lookup1"
        assert cfg["inputs"]["lookups"][0]["join_mode"] == "INNER_JOIN"
        # Variables
        assert len(cfg["variables"]) == 1
        assert cfg["variables"][0]["name"] == "var1"
        assert cfg["variables"][0]["expression"] == "{{java}}row1.name"
        # Outputs
        assert len(cfg["outputs"]) == 2
        assert cfg["outputs"][0]["name"] == "out1"
        assert cfg["outputs"][0]["is_reject"] is False
        assert len(cfg["outputs"][0]["columns"]) == 1
        assert cfg["outputs"][1]["name"] == "reject1"
        assert cfg["outputs"][1]["is_reject"] is True
        assert cfg["outputs"][1]["inner_join_reject"] is True

    def test_inner_join_mode(self):
        """lookup with innerJoin='true' -> lookup dict has join_mode='INNER_JOIN'."""
        raw_xml = _make_mapper_xml(
            input_tables_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lk1" innerJoin="true">'
                '  <mapperTableEntries name="k" expression="row1.k"/>'
                '</inputTables>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        result = _convert(raw_xml=raw_xml)
        lk = result.component["config"]["inputs"]["lookups"][0]
        assert lk["join_mode"] == "INNER_JOIN"

    def test_outer_join_mode(self):
        """lookup with innerJoin='false' -> lookup dict has join_mode='LEFT_OUTER_JOIN'."""
        raw_xml = _make_mapper_xml(
            input_tables_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lk1" innerJoin="false">'
                '  <mapperTableEntries name="k" expression="row1.k"/>'
                '</inputTables>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        result = _convert(raw_xml=raw_xml)
        lk = result.component["config"]["inputs"]["lookups"][0]
        assert lk["join_mode"] == "LEFT_OUTER_JOIN"


# ------------------------------------------------------------------
# TestSchema
# ------------------------------------------------------------------

class TestSchema:
    """Verify schema extraction."""

    def test_schema_empty(self):
        """tMap emits per-input-flow schemas under ``schema.inputs`` so the
        Java bridge boundary check can resolve each flow. A default node with a
        single empty ``row1`` input flow yields ``{'inputs': {'row1': []}}``."""
        result = _convert()
        assert result.component["schema"] == {"inputs": {"row1": []}}


# ------------------------------------------------------------------
# TestNeedsReview
# ------------------------------------------------------------------

class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_has_entries(self):
        """Per-feature needs_review for engine gaps."""
        result = _convert()
        assert len(result.needs_review) > 0

    def test_needs_review_engine_gap_severity(self):
        """All needs_review entries have 'engine_gap' severity."""
        result = _convert()
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        result = _convert(component_id="test_comp")
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        result = _convert()
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


# ------------------------------------------------------------------
# TestCompleteness
# ------------------------------------------------------------------

class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """Keys removed in a943b5f: link_style, lkup_parallelize,
        levenshtein, jaccard
        """
        result = _convert()
        cfg = result.component["config"]
        expected_keys = {
            # Flat params
            "die_on_error", "rows_buffer_size",
            "change_hash_and_equals_for_bigdecimal",
            "enable_auto_convert_type",
            # Nested structures
            "inputs", "outputs", "variables",
            # Framework
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(cfg.keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"


# ------------------------------------------------------------------
# TestComponentStructure
# ------------------------------------------------------------------

class TestComponentStructure:
    """Verify component wrapper structure."""

    def test_has_type(self):
        result = _convert()
        assert result.component["type"] == "Map"

    def test_has_original_type(self):
        result = _convert()
        assert result.component["original_type"] == "tMap"

    def test_has_id(self):
        result = _convert(component_id="tMap_1")
        assert result.component["id"] == "tMap_1"

    def test_has_position(self):
        result = _convert()
        assert result.component["position"] == {"x": 100, "y": 200}

    def test_top_level_keys(self):
        result = _convert()
        comp = result.component
        expected = {"id", "type", "original_type", "position", "config", "schema", "inputs", "outputs"}
        assert set(comp.keys()) == expected


# ------------------------------------------------------------------
# TestMapperDataParsing (existing coverage preserved)
# ------------------------------------------------------------------

class TestMapperDataParsing:
    """Verify nodeData/MapperData XML parsing details."""

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
        result = _convert(raw_xml=raw_xml)
        main = result.component["config"]["inputs"]["main"]
        assert main["activate_filter"] is True
        assert main["filter"] == "{{java}}row1.status != null"

    def test_main_filter_inactive(self):
        """When activateExpressionFilter is false, filter stays empty."""
        raw_xml = _make_mapper_xml(
            input_tables_xml=(
                '<inputTables name="row1"'
                '  activateExpressionFilter="false"'
                '  expressionFilter="row1.id > 0"/>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        result = _convert(raw_xml=raw_xml)
        main = result.component["config"]["inputs"]["main"]
        assert main["activate_filter"] is False
        assert main["filter"] == ""

    def test_lookup_join_keys(self):
        """A lookup table with join keys parsed correctly."""
        raw_xml = _make_mapper_xml(
            input_tables_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lk1" innerJoin="true" matchingMode="ALL_MATCHES">'
                '  <mapperTableEntries name="id" expression="row1.id" type="id_Integer"/>'
                '</inputTables>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        result = _convert(raw_xml=raw_xml)
        lk = result.component["config"]["inputs"]["lookups"][0]
        assert lk["name"] == "lk1"
        assert lk["matching_mode"] == "ALL_MATCHES"
        assert lk["join_mode"] == "INNER_JOIN"
        assert len(lk["join_keys"]) == 1
        assert lk["join_keys"][0] == {
            "lookup_column": "id",
            "expression": "{{java}}row1.id",
            "type": "int",
            "nullable": True,
            "operator": "",
        }

    def test_lookup_no_expression_entries_skipped(self):
        """mapperTableEntries without expressions are not treated as join keys."""
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
        result = _convert(raw_xml=raw_xml)
        lk = result.component["config"]["inputs"]["lookups"][0]
        assert len(lk["join_keys"]) == 1
        assert lk["join_keys"][0]["lookup_column"] == "col_b"

    def test_lookup_with_filter(self):
        """A lookup with an active filter gets the {{java}} prefix."""
        raw_xml = _make_mapper_xml(
            input_tables_xml=(
                '<inputTables name="row1"/>'
                '<inputTables name="lk1"'
                '  activateExpressionFilter="true"'
                '  expressionFilter="lk1.active == true">'
                '  <mapperTableEntries name="id" expression="row1.id"/>'
                '</inputTables>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        result = _convert(raw_xml=raw_xml)
        lk = result.component["config"]["inputs"]["lookups"][0]
        assert lk["activate_filter"] is True
        assert lk["filter"] == "{{java}}lk1.active == true"

    def test_multiple_lookups(self):
        """Multiple lookup tables are all parsed."""
        raw_xml = _make_mapper_xml(
            input_tables_xml=(
                '<inputTables name="main_row"/>'
                '<inputTables name="lk1" innerJoin="true">'
                '  <mapperTableEntries name="a" expression="main_row.a"/>'
                '</inputTables>'
                '<inputTables name="lk2" innerJoin="false">'
                '  <mapperTableEntries name="b" expression="main_row.b"/>'
                '</inputTables>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        result = _convert(raw_xml=raw_xml)
        lookups = result.component["config"]["inputs"]["lookups"]
        assert len(lookups) == 2
        assert lookups[0]["name"] == "lk1"
        assert lookups[0]["join_mode"] == "INNER_JOIN"
        assert lookups[1]["name"] == "lk2"
        assert lookups[1]["join_mode"] == "LEFT_OUTER_JOIN"

    def test_variables_parsed(self):
        """Variable table entries with name+expression are captured."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            var_tables_xml=(
                '<varTables name="Var">'
                '  <mapperTableEntries name="v_name"'
                '    expression="row1.first + row1.last"'
                '    type="id_String"/>'
                '  <mapperTableEntries name="v_total"'
                '    expression="row1.qty * row1.price"'
                '    type="id_Double"/>'
                '</varTables>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        result = _convert(raw_xml=raw_xml)
        variables = result.component["config"]["variables"]
        assert len(variables) == 2
        assert variables[0] == {
            "name": "v_name",
            "expression": "{{java}}row1.first + row1.last",
            "type": "str",
            "nullable": True,
        }
        assert variables[1] == {
            "name": "v_total",
            "expression": "{{java}}row1.qty * row1.price",
            "type": "float",
            "nullable": True,
        }

    def test_variables_skip_empty_expression(self):
        """Variables with empty expressions are skipped."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            var_tables_xml=(
                '<varTables name="Var">'
                '  <mapperTableEntries name="v_good" expression="row1.x" type="id_Integer"/>'
                '  <mapperTableEntries name="v_empty" expression="" type="id_String"/>'
                '</varTables>'
            ),
            output_tables_xml='<outputTables name="out1"/>',
        )
        result = _convert(raw_xml=raw_xml)
        variables = result.component["config"]["variables"]
        assert len(variables) == 1
        assert variables[0]["name"] == "v_good"

    def test_output_columns(self):
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
                '</outputTables>'
            ),
        )
        result = _convert(raw_xml=raw_xml)
        outputs = result.component["config"]["outputs"]
        assert len(outputs) == 1
        out = outputs[0]
        assert out["name"] == "out1"
        assert out["is_reject"] is False
        assert len(out["columns"]) == 2
        assert out["columns"][0] == {
            "name": "id",
            "expression": "{{java}}row1.id",
            "type": "int",
            "nullable": False,
            "operator": "",
            "length": -1,
            "precision": -1,
            "pattern": "",
        }

    def test_reject_output(self):
        """reject=true produces is_reject=True."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml='<outputTables name="reject_out" reject="true" rejectInnerJoin="true"/>',
        )
        result = _convert(raw_xml=raw_xml)
        out = result.component["config"]["outputs"][0]
        assert out["is_reject"] is True
        assert out["inner_join_reject"] is True

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
        result = _convert(raw_xml=raw_xml)
        out = result.component["config"]["outputs"][0]
        assert out["activate_filter"] is True
        assert out["filter"] == "{{java}}row1.amount > 0"

    def test_column_empty_expression(self):
        """A column with no expression produces empty string (no {{java}} prefix)."""
        raw_xml = _make_mapper_xml(
            input_tables_xml='<inputTables name="row1"/>',
            output_tables_xml=(
                '<outputTables name="out1">'
                '  <mapperTableEntries name="col1" expression="" type="id_String"/>'
                '</outputTables>'
            ),
        )
        result = _convert(raw_xml=raw_xml)
        col = result.component["config"]["outputs"][0]["columns"][0]
        assert col["expression"] == ""

    def test_no_raw_xml(self):
        """Node with raw_xml=None produces empty config + warning."""
        node = TalendNode(
            component_id="m_1", component_type="tMap",
            params={}, schema={}, position={"x": 0, "y": 0}, raw_xml=None,
        )
        result = MapConverter().convert(node, [], {})
        assert result.component["config"] == {}
        assert any("No MapperData" in w for w in result.warnings)

    def test_no_mapper_data_element(self):
        """Node XML with no nodeData/MapperData produces empty config."""
        raw_xml = ET.fromstring('<node componentName="tMap"/>')
        result = _convert(raw_xml=raw_xml)
        assert result.component["config"] == {}
        assert any("No MapperData" in w for w in result.warnings)

    def test_mapper_data_without_input_tables(self):
        """MapperData with no inputTables produces empty config + warning."""
        raw_xml = _make_mapper_xml(input_tables_xml="", output_tables_xml="")
        result = _convert(raw_xml=raw_xml)
        assert result.component["config"] == {}
        assert any("No inputTables" in w for w in result.warnings)


# ------------------------------------------------------------------
# TestRoutingArrays
# ------------------------------------------------------------------

class TestRoutingArrays:
    """Verify component['inputs'] and component['outputs'] arrays for engine routing."""

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
        result = _convert(raw_xml=raw_xml)
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
        result = _convert(raw_xml=raw_xml)
        assert result.component["outputs"] == ["out1", "out2"]


# ------------------------------------------------------------------
# TestFullScenario
# ------------------------------------------------------------------

class TestFullScenario:
    """Full end-to-end scenario with all tMap features."""

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
                '</inputTables>'
            ),
            var_tables_xml=(
                '<varTables name="Var">'
                '  <mapperTableEntries name="full_name"'
                '    expression="customers.first + &quot; &quot; + customers.last"'
                '    type="id_String"/>'
                '</varTables>'
            ),
            output_tables_xml=(
                '<outputTables name="enriched"'
                '  activateExpressionFilter="true"'
                '  expressionFilter="Var.full_name != null">'
                '  <mapperTableEntries name="name" expression="Var.full_name"'
                '    type="id_String" nullable="true"/>'
                '  <mapperTableEntries name="total" expression="orders.amount"'
                '    type="id_Double" nullable="false"/>'
                '</outputTables>'
                '<outputTables name="rejects" reject="true" rejectInnerJoin="true"/>'
            ),
        )
        result = _convert(raw_xml=raw_xml, params={"DIE_ON_ERROR": "true"})
        cfg = result.component["config"]

        # Inputs
        main = cfg["inputs"]["main"]
        assert main["name"] == "customers"
        assert main["activate_filter"] is True
        assert main["filter"] == "{{java}}customers.active == true"

        lookups = cfg["inputs"]["lookups"]
        assert len(lookups) == 1
        lk = lookups[0]
        assert lk["name"] == "orders"
        assert lk["join_mode"] == "INNER_JOIN"
        assert len(lk["join_keys"]) == 2

        # Variables
        variables = cfg["variables"]
        assert len(variables) == 1
        assert variables[0]["name"] == "full_name"
        assert variables[0]["expression"].startswith("{{java}}")

        # Outputs
        outputs = cfg["outputs"]
        assert len(outputs) == 2
        enriched = outputs[0]
        assert enriched["name"] == "enriched"
        assert enriched["activate_filter"] is True
        assert len(enriched["columns"]) == 2
        rejects = outputs[1]
        assert rejects["is_reject"] is True
        assert rejects["inner_join_reject"] is True

        # Routing arrays
        assert result.component["inputs"] == ["customers", "orders"]
        assert result.component["outputs"] == ["enriched", "rejects"]
