"""Tests for SchemaComplianceCheckConverter (tSchemaComplianceCheck -> SchemaComplianceCheck)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.schema_compliance_check import (
    SchemaComplianceCheckConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="scc_1",
               component_type="tSchemaComplianceCheck"):
    """Create a TalendNode for testing."""
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 100, "y": 200},
        raw_xml=ET.Element("node"),
    )


def _make_schema_columns():
    """Return a sample FLOW schema with varied types for testing."""
    return {
        "FLOW": [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True, length=10),
            SchemaColumn(name="name", type="id_String", nullable=True, length=50),
            SchemaColumn(name="amount", type="id_Double", nullable=True),
            SchemaColumn(name="active", type="id_Boolean", nullable=False),
            SchemaColumn(name="created", type="id_Date", nullable=True,
                         date_pattern="yyyy-MM-dd"),
        ]
    }


def _make_checkcols_table(columns):
    """Generate CHECKCOLS TABLE data with stride-5 per column.

    columns: list of (name, type, datepattern, nullable_str, max_length_str)
    """
    result = []
    for name, sel_type, datepattern, nullable, max_len in columns:
        result.extend([
            {"elementRef": "SCHEMA_COLUMN", "value": name},
            {"elementRef": "SELECTED_TYPE", "value": sel_type},
            {"elementRef": "DATEPATTERN", "value": datepattern},
            {"elementRef": "NULLABLE", "value": nullable},
            {"elementRef": "MAX_LENGTH", "value": max_len},
        ])
    return result


def _make_empty_null_table(columns):
    """Generate EMPTY_NULL_TABLE data with stride-2 per column.

    columns: list of (name, empty_null_str)
    """
    result = []
    for name, empty_null in columns:
        result.extend([
            {"elementRef": "SCHEMA_COLUMN", "value": name},
            {"elementRef": "EMPTY_NULL", "value": empty_null},
        ])
    return result


def _convert(params=None, schema=None, component_id="scc_1"):
    """Helper: create node and run converter, return ComponentResult."""
    node = _make_node(params=params, schema=schema, component_id=component_id)
    return SchemaComplianceCheckConverter().convert(node, [], {})


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tSchemaComplianceCheck") is SchemaComplianceCheckConverter


# ------------------------------------------------------------------
# Defaults (13 unique + 2 framework = 15 total)
# ------------------------------------------------------------------


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_check_all_default_true(self):
        """CHECK_ALL defaults to True (RADIO group MODE, default selection)."""
        result = _convert(schema=_make_schema_columns())
        assert result.component["config"]["check_all"] is True

    def test_customer_default_false(self):
        """CUSTOMER defaults to False (RADIO group MODE)."""
        result = _convert(schema=_make_schema_columns())
        assert result.component["config"]["customer"] is False

    def test_check_another_default_false(self):
        """CHECK_ANOTHER defaults to False (RADIO group MODE)."""
        result = _convert(schema=_make_schema_columns())
        assert result.component["config"]["check_another"] is False

    def test_checkcols_default_empty(self):
        """CHECKCOLS TABLE defaults to empty list."""
        result = _convert(schema=_make_schema_columns())
        assert result.component["config"]["checkcols"] == []

    def test_sub_string_default_false(self):
        """SUB_STRING defaults to False."""
        result = _convert(schema=_make_schema_columns())
        assert result.component["config"]["sub_string"] is False

    def test_strict_date_check_default_false(self):
        """STRICT_DATE_CHECK defaults to False."""
        result = _convert(schema=_make_schema_columns())
        assert result.component["config"]["strict_date_check"] is False

    def test_all_empty_are_null_default_true(self):
        """ALL_EMPTY_ARE_NULL defaults to True."""
        result = _convert(schema=_make_schema_columns())
        assert result.component["config"]["all_empty_are_null"] is True

    def test_fast_date_check_default_false(self):
        """FAST_DATE_CHECK defaults to False."""
        result = _convert(schema=_make_schema_columns())
        assert result.component["config"]["fast_date_check"] is False

    def test_ignore_timezone_default_false(self):
        """IGNORE_TIMEZONE defaults to False."""
        result = _convert(schema=_make_schema_columns())
        assert result.component["config"]["ignore_timezone"] is False

    def test_empty_null_table_default_empty(self):
        """EMPTY_NULL_TABLE defaults to empty list."""
        result = _convert(schema=_make_schema_columns())
        assert result.component["config"]["empty_null_table"] == []

    def test_check_string_by_byte_length_default_false(self):
        """CHECK_STRING_BY_BYTE_LENGTH defaults to False."""
        result = _convert(schema=_make_schema_columns())
        assert result.component["config"]["check_string_by_byte_length"] is False

    def test_charset_default_empty(self):
        """CHARSET defaults to empty string."""
        result = _convert(schema=_make_schema_columns())
        assert result.component["config"]["charset"] == ""

    def test_tstatcatcher_stats_default_false(self):
        """TSTATCATCHER_STATS framework param defaults to False."""
        result = _convert(schema=_make_schema_columns())
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default_empty(self):
        """LABEL framework param defaults to empty string."""
        result = _convert(schema=_make_schema_columns())
        assert result.component["config"]["label"] == ""


# ------------------------------------------------------------------
# Parameter Extraction
# ------------------------------------------------------------------


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_checkcols_parsing(self):
        """CHECKCOLS TABLE stride-5 produces list of per-column check dicts."""
        checkcols_data = _make_checkcols_table([
            ("id", "Integer", "", "false", "false"),
            ("name", "String", "", "true", "true"),
        ])
        result = _convert(
            params={"CHECKCOLS": checkcols_data},
            schema=_make_schema_columns(),
        )
        cfg = result.component["config"]
        assert len(cfg["checkcols"]) == 2
        assert cfg["checkcols"][0] == {
            "column": "id",
            "selected_type": "Integer",
            "date_pattern": "",
            "nullable": False,
            "max_length": False,
        }
        assert cfg["checkcols"][1] == {
            "column": "name",
            "selected_type": "String",
            "date_pattern": "",
            "nullable": True,
            "max_length": True,
        }

    def test_empty_null_table_parsing(self):
        """EMPTY_NULL_TABLE stride-2 produces list of per-column null dicts."""
        en_data = _make_empty_null_table([
            ("id", "false"),
            ("name", "true"),
        ])
        result = _convert(
            params={"EMPTY_NULL_TABLE": en_data},
            schema=_make_schema_columns(),
        )
        cfg = result.component["config"]
        assert len(cfg["empty_null_table"]) == 2
        assert cfg["empty_null_table"][0] == {"column": "id", "empty_is_null": False}
        assert cfg["empty_null_table"][1] == {"column": "name", "empty_is_null": True}

    def test_customer_radio_true(self):
        """CUSTOMER=true, CHECK_ALL=false -> customer mode selected."""
        result = _convert(
            params={"CUSTOMER": "true", "CHECK_ALL": "false"},
            schema=_make_schema_columns(),
        )
        cfg = result.component["config"]
        assert cfg["customer"] is True
        assert cfg["check_all"] is False

    def test_check_another_radio_true(self):
        """CHECK_ANOTHER=true, CHECK_ALL=false -> check_another mode selected."""
        result = _convert(
            params={"CHECK_ANOTHER": "true", "CHECK_ALL": "false"},
            schema=_make_schema_columns(),
        )
        cfg = result.component["config"]
        assert cfg["check_another"] is True
        assert cfg["check_all"] is False

    def test_sub_string_true(self):
        """SUB_STRING=true is extracted as True."""
        result = _convert(params={"SUB_STRING": "true"}, schema=_make_schema_columns())
        assert result.component["config"]["sub_string"] is True

    def test_strict_date_check_true(self):
        """STRICT_DATE_CHECK=true is extracted as True."""
        result = _convert(params={"STRICT_DATE_CHECK": "true"}, schema=_make_schema_columns())
        assert result.component["config"]["strict_date_check"] is True

    def test_all_empty_are_null_false(self):
        """ALL_EMPTY_ARE_NULL=false overrides default True."""
        result = _convert(params={"ALL_EMPTY_ARE_NULL": "false"}, schema=_make_schema_columns())
        assert result.component["config"]["all_empty_are_null"] is False

    def test_fast_date_check_true(self):
        """FAST_DATE_CHECK=true is extracted as True."""
        result = _convert(params={"FAST_DATE_CHECK": "true"}, schema=_make_schema_columns())
        assert result.component["config"]["fast_date_check"] is True

    def test_ignore_timezone_true(self):
        """IGNORE_TIMEZONE=true is extracted as True."""
        result = _convert(params={"IGNORE_TIMEZONE": "true"}, schema=_make_schema_columns())
        assert result.component["config"]["ignore_timezone"] is True

    def test_check_string_by_byte_length_true(self):
        """CHECK_STRING_BY_BYTE_LENGTH=true is extracted as True."""
        result = _convert(params={"CHECK_STRING_BY_BYTE_LENGTH": "true"}, schema=_make_schema_columns())
        assert result.component["config"]["check_string_by_byte_length"] is True

    def test_charset_extracted(self):
        """CHARSET with quoted value is extracted correctly."""
        result = _convert(params={"CHARSET": '"UTF-8"'}, schema=_make_schema_columns())
        assert result.component["config"]["charset"] == "UTF-8"

    def test_checkcols_date_type_with_pattern(self):
        """CHECKCOLS column with Date type and yyyy-MM-dd pattern is parsed correctly."""
        checkcols_data = _make_checkcols_table([
            ("created", "Date", "yyyy-MM-dd", "true", "false"),
        ])
        result = _convert(
            params={"CHECKCOLS": checkcols_data},
            schema=_make_schema_columns(),
        )
        row = result.component["config"]["checkcols"][0]
        assert row["column"] == "created"
        assert row["selected_type"] == "Date"
        assert row["date_pattern"] == "yyyy-MM-dd"
        assert row["nullable"] is True
        assert row["max_length"] is False

    def test_checkcols_incomplete_stride_skipped(self):
        """Incomplete trailing group (< 5 entries) is skipped in CHECKCOLS."""
        checkcols_data = [
            {"elementRef": "SCHEMA_COLUMN", "value": "id"},
            {"elementRef": "SELECTED_TYPE", "value": "Integer"},
            {"elementRef": "DATEPATTERN", "value": ""},
        ]
        result = _convert(
            params={"CHECKCOLS": checkcols_data},
            schema=_make_schema_columns(),
        )
        assert result.component["config"]["checkcols"] == []

    def test_empty_null_table_single_column(self):
        """EMPTY_NULL_TABLE with 1 column (2 elementValues) produces 1 row dict."""
        en_data = _make_empty_null_table([("amount", "true")])
        result = _convert(
            params={"EMPTY_NULL_TABLE": en_data},
            schema=_make_schema_columns(),
        )
        assert len(result.component["config"]["empty_null_table"]) == 1
        assert result.component["config"]["empty_null_table"][0] == {
            "column": "amount",
            "empty_is_null": True,
        }


# ------------------------------------------------------------------
# Framework Params
# ------------------------------------------------------------------


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_true(self):
        """TSTATCATCHER_STATS=true is extracted as True."""
        result = _convert(
            params={"TSTATCATCHER_STATS": "true"},
            schema=_make_schema_columns(),
        )
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_extracted(self):
        """LABEL with quoted value is extracted correctly."""
        result = _convert(
            params={"LABEL": '"my_label"'},
            schema=_make_schema_columns(),
        )
        assert result.component["config"]["label"] == "my_label"


# ------------------------------------------------------------------
# Schema
# ------------------------------------------------------------------


class TestSchema:
    """Verify schema extraction (transform passthrough pattern)."""

    def test_transform_schema_passthrough(self):
        """Input and output schemas should be identical (passthrough)."""
        result = _convert(
            params={"CHECK_ALL": "true"},
            schema=_make_schema_columns(),
        )
        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["input"]) == 5
        assert schema["input"][0]["name"] == "id"
        assert schema["input"][0]["type"] == "int"

    def test_empty_schema_produces_warning(self):
        """When no FLOW schema is present, a warning should be generated."""
        result = _convert(params={"CHECK_ALL": "true"})
        assert result.component["schema"] == {"input": [], "output": []}
        assert result.component["config"]["schema"] == []
        assert any("No FLOW schema" in w for w in result.warnings)

    def test_schema_types_are_converted_from_talend(self):
        """Config schema types must be Python types, not raw Talend types."""
        result = _convert(
            schema={
                "FLOW": [
                    SchemaColumn(name="col_str", type="id_String", nullable=True),
                    SchemaColumn(name="col_long", type="id_Long", nullable=False),
                    SchemaColumn(name="col_decimal", type="id_BigDecimal", nullable=True),
                    SchemaColumn(name="col_char", type="id_Character", nullable=True),
                ]
            },
        )
        cfg_schema = result.component["config"]["schema"]
        assert cfg_schema[0]["type"] == "str"
        assert cfg_schema[1]["type"] == "int"      # id_Long -> int
        assert cfg_schema[2]["type"] == "Decimal"   # id_BigDecimal -> Decimal
        assert cfg_schema[3]["type"] == "str"       # id_Character -> str

    def test_length_only_included_when_present(self):
        """Length should only appear in config schema when >= 0 in source."""
        result = _convert(
            schema={
                "FLOW": [
                    SchemaColumn(name="with_len", type="id_String", nullable=True, length=100),
                    SchemaColumn(name="no_len", type="id_String", nullable=True),
                ]
            },
        )
        cfg_schema = result.component["config"]["schema"]
        assert cfg_schema[0] == {"name": "with_len", "type": "str", "nullable": True, "length": 100}
        assert cfg_schema[1] == {"name": "no_len", "type": "str", "nullable": True}
        assert "length" not in cfg_schema[1]


# ------------------------------------------------------------------
# Needs Review (12 engine gap entries)
# ------------------------------------------------------------------


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """Converter produces exactly 12 engine_gap needs_review entries."""
        result = _convert(schema=_make_schema_columns())
        engine_gap_entries = [
            nr for nr in result.needs_review if nr.get("severity") == "engine_gap"
        ]
        assert len(engine_gap_entries) == 12

    def test_needs_review_severity(self):
        """All needs_review entries have severity 'engine_gap'."""
        result = _convert(schema=_make_schema_columns())
        for entry in result.needs_review:
            assert entry["severity"] == "engine_gap"

    def test_needs_review_has_component_id(self):
        """All needs_review entries contain the component ID."""
        result = _convert(schema=_make_schema_columns(), component_id="test_comp")
        for entry in result.needs_review:
            assert entry["component"] == "test_comp"

    def test_needs_review_covers_all_engine_gap_keys(self):
        """All 12 non-schema, non-framework config keys appear in needs_review."""
        result = _convert(schema=_make_schema_columns())
        gap_issues = {nr["issue"] for nr in result.needs_review}
        expected_keys = [
            "check_all", "customer", "check_another", "checkcols",
            "sub_string", "strict_date_check", "all_empty_are_null",
            "fast_date_check", "ignore_timezone", "empty_null_table",
            "check_string_by_byte_length", "charset",
        ]
        for key in expected_keys:
            assert any(key in issue for issue in gap_issues), (
                f"Missing engine_gap needs_review for '{key}'"
            )

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        result = _convert(
            params={"TSTATCATCHER_STATS": "true", "LABEL": '"test"'},
            schema=_make_schema_columns(),
        )
        all_issues = " ".join(nr.get("issue", "") for nr in result.needs_review)
        assert "tstatcatcher_stats" not in all_issues
        assert "label" not in all_issues


# ------------------------------------------------------------------
# Completeness
# ------------------------------------------------------------------


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """All 15 config keys (13 unique + 2 framework) must be present."""
        result = _convert(schema=_make_schema_columns())
        expected_keys = {
            "schema",
            "check_all", "customer", "check_another", "checkcols",
            "sub_string", "strict_date_check", "all_empty_are_null",
            "fast_date_check", "ignore_timezone", "empty_null_table",
            "check_string_by_byte_length", "charset",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"

    def test_no_extra_config_keys(self):
        """No unexpected config keys should be present."""
        result = _convert(schema=_make_schema_columns())
        expected_keys = {
            "schema",
            "check_all", "customer", "check_another", "checkcols",
            "sub_string", "strict_date_check", "all_empty_are_null",
            "fast_date_check", "ignore_timezone", "empty_null_table",
            "check_string_by_byte_length", "charset",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        extra = actual_keys - expected_keys
        assert not extra, f"Extra config keys: {extra}"


# ------------------------------------------------------------------
# Component Structure
# ------------------------------------------------------------------


class TestComponentStructure:
    """Verify the component output structure uses _build_component_dict."""

    def test_component_has_required_keys(self):
        """Component dict must have id, type, original_type, position, config, schema, inputs, outputs."""
        result = _convert(schema=_make_schema_columns())
        comp = result.component
        assert comp["id"] == "scc_1"
        assert comp["type"] == "SchemaComplianceCheck"
        assert comp["original_type"] == "tSchemaComplianceCheck"
        assert comp["position"] == {"x": 100, "y": 200}
        assert comp["inputs"] == []
        assert comp["outputs"] == []
        assert "config" in comp
        assert "schema" in comp

    def test_result_is_component_result(self):
        """convert() must return a ComponentResult dataclass."""
        result = _convert(schema=_make_schema_columns())
        assert isinstance(result, ComponentResult)

    def test_custom_component_id_propagates(self):
        """component_id propagates through _build_component_dict."""
        result = _convert(schema=_make_schema_columns(), component_id="compliance_42")
        assert result.component["id"] == "compliance_42"

    def test_boolean_params_as_actual_booleans(self):
        """Handle boolean params that arrive as Python bools (not strings)."""
        result = _convert(
            params={
                "CHECK_ALL": True,
                "SUB_STRING": False,
                "STRICT_DATE_CHECK": True,
                "ALL_EMPTY_ARE_NULL": False,
            },
            schema=_make_schema_columns(),
        )
        cfg = result.component["config"]
        assert cfg["check_all"] is True
        assert cfg["sub_string"] is False
        assert cfg["strict_date_check"] is True
        assert cfg["all_empty_are_null"] is False
