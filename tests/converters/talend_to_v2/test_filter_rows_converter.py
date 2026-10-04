"""Tests for talend_to_v2 FilterRows converter."""
from xml.etree.ElementTree import parse as xml_parse
from pathlib import Path

from src.converters.talend_to_v2.components.base import TalendNode, TalendConnection
from src.converters.talend_to_v2.components.transform.filter_rows_converter import (
    FilterRowsConverter,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestFilterRowsConverter:
    """Round-trip tests for tFilterRow converter (D-28)."""

    def _parse_fixture(self, filename: str) -> TalendNode:
        """Parse an XML fixture into a TalendNode.

        Handles TEXT, CHECK, CLOSED_LIST, TABLE, and MEMO_JAVA field types.
        TABLE params collect child elementValue entries into a list of dicts.
        CLOSED_LIST values have surrounding Talend quotes stripped.
        """
        fixture_path = FIXTURES_DIR / filename
        tree = xml_parse(fixture_path)
        root = tree.getroot()

        # Extract params from elementParameter elements
        params = {}
        for elem in root.findall("elementParameter"):
            name = elem.get("name", "")
            value = elem.get("value", "")
            field_type = elem.get("field", "")

            if field_type == "CHECK":
                params[name] = value.lower() == "true"
            elif field_type == "TABLE":
                # Collect child elementValue entries into a list of dicts
                entries = []
                for child in elem.findall("elementValue"):
                    entries.append({
                        "elementRef": child.get("elementRef", ""),
                        "value": child.get("value", ""),
                    })
                params[name] = entries
            elif field_type == "CLOSED_LIST":
                # Strip surrounding Talend quotes
                params[name] = value.strip('"')
            else:
                params[name] = value

        # Extract schema from metadata
        schema = []
        for meta in root.findall("metadata"):
            for col in meta.findall("column"):
                schema.append({
                    "name": col.get("name", ""),
                    "type": col.get("type", "id_String"),
                    "nullable": col.get("nullable", "true") == "true",
                })

        return TalendNode(
            component_id=params.get("UNIQUE_NAME", "unknown"),
            component_type=root.get("componentName", ""),
            params=params,
            schema=schema,
            raw_xml=root,
        )

    def test_basic_single_condition(self):
        """Single condition without FUNCTION produces bare column comparison."""
        node = self._parse_fixture("tFilterRow_basic.xml")
        converter = FilterRowsConverter()
        result = converter.convert(node, [], {})

        assert result.component["type"] == "filter_rows"
        assert result.component["id"] == "tFilterRow_1"
        condition = result.component["config"]["condition"]
        assert "amount" in condition
        assert "100" in condition
        assert ">" in condition
        # No REJECT connection -> no reject_output key
        assert "reject_output" not in result.component["config"]

    def test_multi_condition_or(self):
        """Two conditions joined by OR produce || in the DSL expression."""
        node = self._parse_fixture("tFilterRow_multi_condition.xml")
        converter = FilterRowsConverter()
        result = converter.convert(node, [], {})

        condition = result.component["config"]["condition"]
        assert "||" in condition
        assert "amount" in condition
        assert "100" in condition
        assert "status" in condition
        assert "'active'" in condition

    def test_function_pretransforms(self):
        """FUNCTION pre-transforms compile to correct DSL function names."""
        node = self._parse_fixture("tFilterRow_functions.xml")
        converter = FilterRowsConverter()
        result = converter.convert(node, [], {})

        condition = result.component["config"]["condition"]
        assert "LOWER(name)" in condition
        assert "LENGTH(code)" in condition
        assert "'admin'" in condition
        assert "5" in condition

    def test_advanced_unsupported(self):
        """USE_ADVANCED=true triggers UNSUPPORTED warning and needs_review."""
        node = self._parse_fixture("tFilterRow_advanced.xml")
        converter = FilterRowsConverter()
        result = converter.convert(node, [], {})

        assert len(result.warnings) > 0
        assert any("UNSUPPORTED" in w for w in result.warnings)
        assert len(result.needs_review) > 0
        assert any("USE_ADVANCED" in nr["issue"] for nr in result.needs_review)
        assert result.needs_review[0]["severity"] == "engine_gap"

    def test_reject_flow_detection(self):
        """REJECT connection wired -> config includes reject_output: True."""
        node = self._parse_fixture("tFilterRow_reject.xml")
        connections = [
            TalendConnection(
                name="row1",
                source="tInput_1",
                target="tFilterRow_5",
                connector_type="FLOW",
            ),
            TalendConnection(
                name="reject1",
                source="tFilterRow_5",
                target="tLogRow_1",
                connector_type="REJECT",
            ),
        ]
        converter = FilterRowsConverter()
        result = converter.convert(node, connections, {})

        assert result.component["config"]["reject_output"] is True

    def test_no_reject_without_connection(self):
        """No REJECT connection -> reject_output not in config."""
        node = self._parse_fixture("tFilterRow_basic.xml")
        connections = [
            TalendConnection(
                name="row1",
                source="tInput_1",
                target="tFilterRow_1",
                connector_type="FLOW",
            ),
        ]
        converter = FilterRowsConverter()
        result = converter.convert(node, connections, {})

        assert "reject_output" not in result.component["config"]

    def test_flows_passthrough(self):
        """Converter builds simple flows from incoming and outgoing connections."""
        node = self._parse_fixture("tFilterRow_basic.xml")
        connections = [
            TalendConnection(
                name="row1",
                source="tInput_1",
                target="tFilterRow_1",
                connector_type="FLOW",
            ),
            TalendConnection(
                name="row2",
                source="tFilterRow_1",
                target="tOutput_1",
                connector_type="FLOW",
            ),
        ]
        converter = FilterRowsConverter()
        result = converter.convert(node, connections, {})

        assert len(result.flows) == 2
        sources = [f["source"] for f in result.flows]
        targets = [f["target"] for f in result.flows]
        assert "tInput_1" in sources
        assert "tFilterRow_1" in sources
        assert "tFilterRow_1" in targets
        assert "tOutput_1" in targets

    def test_empty_function_no_wrap(self):
        """Empty FUNCTION value does NOT wrap the column in a function call."""
        node = self._parse_fixture("tFilterRow_basic.xml")
        converter = FilterRowsConverter()
        result = converter.convert(node, [], {})

        condition = result.component["config"]["condition"]
        # Should be "amount > 100", not "SOME_FUNC(amount) > 100"
        assert condition == "amount > 100"

    def test_quoted_string_values(self):
        """Talend-quoted RVALUE strings are correctly stripped and re-quoted as DSL strings.

        Verifies no double-quoting occurs -- condition should contain 'foo bar'
        not '\"foo bar\"' or ''foo bar''.
        """
        node = self._parse_fixture("tFilterRow_quoted_values.xml")
        converter = FilterRowsConverter()
        result = converter.convert(node, [], {})

        condition = result.component["config"]["condition"]
        # After quote-stripping, "foo bar" becomes foo bar, then DSL-quoted as 'foo bar'
        assert "'foo bar'" in condition
        # Must NOT contain double-quoted remnants
        assert "'\"" not in condition
        assert "\"'" not in condition

    def test_null_keyword_handling(self):
        """RVALUE of 'null' (Java null keyword) produces bare null in DSL, not 'null'.

        In Talend XML, Java null appears as value="null" (no surrounding quotes).
        After _strip_talend_quotes, bare null -> DSL null keyword (unquoted).
        """
        node = self._parse_fixture("tFilterRow_quoted_values.xml")
        converter = FilterRowsConverter()
        result = converter.convert(node, [], {})

        condition = result.component["config"]["condition"]
        # The second condition should be "name == null" (bare null, not quoted)
        assert "name == null" in condition
        # Must NOT be 'null' (with single quotes)
        assert "'null'" not in condition

    def test_unsupported_function_warning(self):
        """Unsupported FUNCTION value emits UNSUPPORTED warning and needs_review."""
        node = TalendNode(
            component_id="tFilterRow_99",
            component_type="tFilterRow",
            params={
                "LOGICAL_OP": "AND",
                "USE_ADVANCED": False,
                "CONDITIONS": [
                    {"elementRef": "INPUT_COLUMN", "value": '"col1"'},
                    {"elementRef": "FUNCTION", "value": '"CUSTOM_JAVA_FUNC"'},
                    {"elementRef": "OPERATOR", "value": '"=="'},
                    {"elementRef": "RVALUE", "value": '"test"'},
                ],
            },
        )
        converter = FilterRowsConverter()
        result = converter.convert(node, [], {})

        assert len(result.warnings) > 0
        assert any("CUSTOM_JAVA_FUNC" in w for w in result.warnings)
        assert any("UNSUPPORTED" in w for w in result.warnings)
        assert len(result.needs_review) > 0
        assert any("CUSTOM_JAVA_FUNC" in nr["issue"] for nr in result.needs_review)
        # Condition should be 'true' since the only condition was unsupported
        assert result.component["config"]["condition"] == "true"

    def test_contains_with_negation(self):
        """FUNCTION=CONTAINS with OPERATOR=!= produces negated CONTAINS expression."""
        node = TalendNode(
            component_id="tFilterRow_neg",
            component_type="tFilterRow",
            params={
                "LOGICAL_OP": "AND",
                "USE_ADVANCED": False,
                "CONDITIONS": [
                    {"elementRef": "INPUT_COLUMN", "value": '"name"'},
                    {"elementRef": "FUNCTION", "value": '"CONTAINS"'},
                    {"elementRef": "OPERATOR", "value": '"!="'},
                    {"elementRef": "RVALUE", "value": '"admin"'},
                ],
            },
        )
        converter = FilterRowsConverter()
        result = converter.convert(node, [], {})

        condition = result.component["config"]["condition"]
        assert "!(CONTAINS(name, 'admin'))" == condition

    def test_match_regex_with_negation(self):
        """FUNCTION=MATCH_REGEX with OPERATOR=!= produces negated REGEX_MATCH."""
        node = TalendNode(
            component_id="tFilterRow_neg2",
            component_type="tFilterRow",
            params={
                "LOGICAL_OP": "AND",
                "USE_ADVANCED": False,
                "CONDITIONS": [
                    {"elementRef": "INPUT_COLUMN", "value": '"code"'},
                    {"elementRef": "FUNCTION", "value": '"MATCH_REGEX"'},
                    {"elementRef": "OPERATOR", "value": '"!="'},
                    {"elementRef": "RVALUE", "value": '"^[A-Z]{3}$"'},
                ],
            },
        )
        converter = FilterRowsConverter()
        result = converter.convert(node, [], {})

        condition = result.component["config"]["condition"]
        assert "!(REGEX_MATCH(code," in condition

    def test_empty_function_with_negation(self):
        """FUNCTION=EMPTY with OPERATOR=!= produces negated empty check (NOT empty)."""
        node = TalendNode(
            component_id="tFilterRow_neg3",
            component_type="tFilterRow",
            params={
                "LOGICAL_OP": "AND",
                "USE_ADVANCED": False,
                "CONDITIONS": [
                    {"elementRef": "INPUT_COLUMN", "value": '"name"'},
                    {"elementRef": "FUNCTION", "value": '"EMPTY"'},
                    {"elementRef": "OPERATOR", "value": '"!="'},
                    {"elementRef": "RVALUE", "value": '""'},
                ],
            },
        )
        converter = FilterRowsConverter()
        result = converter.convert(node, [], {})

        condition = result.component["config"]["condition"]
        assert "!(ISNULL(name) || name == '')" == condition

    def test_empty_function_positive(self):
        """FUNCTION=EMPTY with OPERATOR=== produces positive empty check."""
        node = TalendNode(
            component_id="tFilterRow_emp",
            component_type="tFilterRow",
            params={
                "LOGICAL_OP": "AND",
                "USE_ADVANCED": False,
                "CONDITIONS": [
                    {"elementRef": "INPUT_COLUMN", "value": '"name"'},
                    {"elementRef": "FUNCTION", "value": '"EMPTY"'},
                    {"elementRef": "OPERATOR", "value": '"=="'},
                    {"elementRef": "RVALUE", "value": '""'},
                ],
            },
        )
        converter = FilterRowsConverter()
        result = converter.convert(node, [], {})

        condition = result.component["config"]["condition"]
        assert "ISNULL(name) || name == ''" == condition
        assert "!(" not in condition

    def test_upper_trim_abs_functions(self):
        """UPPER_CASE, TRIM, and ABS_VALUE compile to correct DSL functions."""
        node = TalendNode(
            component_id="tFilterRow_funcs",
            component_type="tFilterRow",
            params={
                "LOGICAL_OP": "AND",
                "USE_ADVANCED": False,
                "CONDITIONS": [
                    {"elementRef": "INPUT_COLUMN", "value": '"name"'},
                    {"elementRef": "FUNCTION", "value": '"UPPER_CASE"'},
                    {"elementRef": "OPERATOR", "value": '"=="'},
                    {"elementRef": "RVALUE", "value": '"ADMIN"'},
                    {"elementRef": "INPUT_COLUMN", "value": '"label"'},
                    {"elementRef": "FUNCTION", "value": '"TRIM"'},
                    {"elementRef": "OPERATOR", "value": '"!="'},
                    {"elementRef": "RVALUE", "value": '""'},
                    {"elementRef": "INPUT_COLUMN", "value": '"score"'},
                    {"elementRef": "FUNCTION", "value": '"ABS_VALUE"'},
                    {"elementRef": "OPERATOR", "value": '">"'},
                    {"elementRef": "RVALUE", "value": '"10"'},
                ],
            },
        )
        converter = FilterRowsConverter()
        result = converter.convert(node, [], {})

        condition = result.component["config"]["condition"]
        assert "UPPER(name) == 'ADMIN'" in condition
        assert "TRIM(label) != ''" in condition
        assert "ABS(score) > 10" in condition

    def test_empty_conditions_default(self):
        """Empty CONDITIONS list produces condition='true'."""
        node = TalendNode(
            component_id="tFilterRow_empty",
            component_type="tFilterRow",
            params={
                "LOGICAL_OP": "AND",
                "USE_ADVANCED": False,
                "CONDITIONS": [],
            },
        )
        converter = FilterRowsConverter()
        result = converter.convert(node, [], {})

        assert result.component["config"]["condition"] == "true"
