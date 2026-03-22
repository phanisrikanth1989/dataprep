"""Tests for the UnpivotRowConverter (tUnpivotRow -> UnpivotRow)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.transform.unpivot_row import (
    UnpivotRowConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="unpivot_1",
               component_type="tUnpivotRow"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 100, "y": 200},
        raw_xml=ET.Element("node"),
    )


def _make_schema_columns():
    """Return a sample FLOW schema for testing."""
    return {
        "FLOW": [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True),
            SchemaColumn(name="name", type="id_String", nullable=True),
            SchemaColumn(name="amount", type="id_Double", nullable=True),
        ]
    }


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------
class TestUnpivotRowRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tUnpivotRow") is UnpivotRowConverter


# ------------------------------------------------------------------
# Basic / happy-path
# ------------------------------------------------------------------
class TestUnpivotRowBasic:
    def test_full_config(self):
        """All parameters supplied — no warnings expected."""
        node = _make_node(params={
            "PIVOT_COLUMN": '"my_pivot"',
            "VALUE_COLUMN": '"my_value"',
            "GROUP_BY_COLUMNS": '"colA;colB"',
            "ROW_KEYS": [
                {"elementRef": "COLUMN", "value": '"key1"'},
                {"elementRef": "COLUMN", "value": '"key2"'},
            ],
            "DIE_ON_ERROR": "true",
        })
        result = UnpivotRowConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "unpivot_1"
        assert comp["type"] == "UnpivotRow"
        assert comp["original_type"] == "tUnpivotRow"
        assert comp["position"] == {"x": 100, "y": 200}
        cfg = comp["config"]
        assert cfg["pivot_column"] == "my_pivot"
        assert cfg["value_column"] == "my_value"
        assert cfg["group_by_columns"] == ["colA", "colB"]
        assert cfg["row_keys"] == ["key1", "key2"]
        assert cfg["die_on_error"] is True
        assert comp["inputs"] == []
        assert comp["outputs"] == []
        assert result.warnings == []

    def test_defaults_when_params_missing(self):
        """Missing scalar params should fall back to safe defaults."""
        node = _make_node(params={})
        result = UnpivotRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["pivot_column"] == "pivot_key"
        assert cfg["value_column"] == "pivot_value"
        assert cfg["group_by_columns"] == []
        assert cfg["row_keys"] == []
        assert cfg["die_on_error"] is False
        # Should warn about empty row_keys
        assert any("No row keys" in w for w in result.warnings)


# ------------------------------------------------------------------
# CONV-UPV-001: No hardcoded business column names
# ------------------------------------------------------------------
class TestUnpivotRowNoHardcodedDefaults:
    """The old code had hardcoded fallback defaults for row_keys like
    COBDATE, AGREEMENTID, etc. Verify these are GONE."""

    HARDCODED_NAMES = [
        "COBDATE", "AGREEMENTID", "MASTERMNEMONIC",
        "CLIENT_OR_AFFILIATE", "MNEMONIC", "GMIACCOUNT", "CURRENCY",
    ]

    def test_empty_row_keys_no_hardcoded_fallback(self):
        """When ROW_KEYS is empty, row_keys must be [] — not business names."""
        node = _make_node(params={"ROW_KEYS": []})
        result = UnpivotRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["row_keys"] == []
        for name in self.HARDCODED_NAMES:
            assert name not in cfg["row_keys"], (
                f"Hardcoded column '{name}' found — CONV-UPV-001 not fixed"
            )

    def test_missing_row_keys_no_hardcoded_fallback(self):
        """When ROW_KEYS param is missing entirely, row_keys must be []."""
        node = _make_node(params={})
        result = UnpivotRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["row_keys"] == []
        for name in self.HARDCODED_NAMES:
            assert name not in cfg["row_keys"], (
                f"Hardcoded column '{name}' found — CONV-UPV-001 not fixed"
            )


# ------------------------------------------------------------------
# ROW_KEYS edge cases
# ------------------------------------------------------------------
class TestUnpivotRowRowKeys:
    def test_row_keys_filters_empty_values(self):
        """Empty-string COLUMN entries should be skipped."""
        node = _make_node(params={
            "ROW_KEYS": [
                {"elementRef": "COLUMN", "value": '"key1"'},
                {"elementRef": "COLUMN", "value": '""'},
                {"elementRef": "COLUMN", "value": '"key2"'},
            ],
        })
        result = UnpivotRowConverter().convert(node, [], {})

        assert result.component["config"]["row_keys"] == ["key1", "key2"]

    def test_row_keys_ignores_non_column_refs(self):
        """Entries with elementRef != 'COLUMN' should be ignored."""
        node = _make_node(params={
            "ROW_KEYS": [
                {"elementRef": "COLUMN", "value": '"keep_me"'},
                {"elementRef": "OTHER", "value": '"ignore_me"'},
                {"elementRef": "COLUMN", "value": '"also_keep"'},
            ],
        })
        result = UnpivotRowConverter().convert(node, [], {})

        assert result.component["config"]["row_keys"] == ["keep_me", "also_keep"]

    def test_row_keys_not_a_list_warns(self):
        """If ROW_KEYS is not a list, produce a warning."""
        node = _make_node(params={"ROW_KEYS": "bad_data"})
        result = UnpivotRowConverter().convert(node, [], {})

        assert result.component["config"]["row_keys"] == []
        assert any("not a list" in w for w in result.warnings)


# ------------------------------------------------------------------
# GROUP_BY_COLUMNS
# ------------------------------------------------------------------
class TestUnpivotRowGroupBy:
    def test_group_by_single(self):
        node = _make_node(params={"GROUP_BY_COLUMNS": '"single_col"'})
        result = UnpivotRowConverter().convert(node, [], {})

        assert result.component["config"]["group_by_columns"] == ["single_col"]

    def test_group_by_multiple(self):
        node = _make_node(params={"GROUP_BY_COLUMNS": '"a;b;c"'})
        result = UnpivotRowConverter().convert(node, [], {})

        assert result.component["config"]["group_by_columns"] == ["a", "b", "c"]

    def test_group_by_empty(self):
        node = _make_node(params={"GROUP_BY_COLUMNS": '""'})
        result = UnpivotRowConverter().convert(node, [], {})

        assert result.component["config"]["group_by_columns"] == []


# ------------------------------------------------------------------
# Schema
# ------------------------------------------------------------------
class TestUnpivotRowSchema:
    def test_schema_passthrough(self):
        """UnpivotRow passes the schema through: input == output."""
        node = _make_node(
            params={
                "ROW_KEYS": [
                    {"elementRef": "COLUMN", "value": '"id"'},
                ],
            },
            schema=_make_schema_columns(),
        )
        result = UnpivotRowConverter().convert(node, [], {})

        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["input"]) == 3
        assert schema["input"][0]["name"] == "id"

    def test_empty_schema(self):
        """When no FLOW schema is present, input and output are empty lists."""
        node = _make_node(params={})
        result = UnpivotRowConverter().convert(node, [], {})

        schema = result.component["schema"]
        assert schema == {"input": [], "output": []}
