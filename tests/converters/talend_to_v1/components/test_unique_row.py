"""Tests for the UniqueRowConverter (tUniqueRow -> UniqueRow)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.aggregate.unique_row import (
    UniqueRowConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="unique_1",
               component_type="tUniqueRow"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 100, "y": 200},
        raw_xml=ET.Element("node"),
    )


def _make_unique_key_entries(*columns):
    """Build flat UNIQUE_KEY entries from (col_name, is_key, case_sensitive) tuples."""
    entries = []
    for col_name, is_key, case_sensitive in columns:
        entries.append({"elementRef": "SCHEMA_COLUMN", "value": f'"{col_name}"'})
        entries.append({"elementRef": "KEY_ATTRIBUTE", "value": str(is_key).lower()})
        entries.append({"elementRef": "CASE_SENSITIVE", "value": str(case_sensitive).lower()})
    return entries


def _make_schema_columns():
    """Return a sample FLOW schema for testing."""
    return {
        "FLOW": [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True),
            SchemaColumn(name="name", type="id_String", nullable=True),
            SchemaColumn(name="email", type="id_String", nullable=True),
        ]
    }


# ------------------------------------------------------------------
# Registration tests
# ------------------------------------------------------------------

class TestUniqueRowRegistration:
    def test_tUniqueRow_registered(self):
        assert REGISTRY.get("tUniqueRow") is UniqueRowConverter

    def test_tUniqRow_registered(self):
        assert REGISTRY.get("tUniqRow") is UniqueRowConverter

    def test_tUnqRow_registered(self):
        assert REGISTRY.get("tUnqRow") is UniqueRowConverter


# ------------------------------------------------------------------
# Basic conversion tests
# ------------------------------------------------------------------

class TestUniqueRowBasic:
    def test_single_key_column(self):
        node = _make_node(params={
            "UNIQUE_KEY": _make_unique_key_entries(
                ("id", True, True),
            ),
        })
        result = UniqueRowConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "unique_1"
        assert comp["type"] == "UniqueRow"
        assert comp["original_type"] == "tUniqueRow"
        assert comp["position"] == {"x": 100, "y": 200}
        assert comp["config"]["key_columns"] == ["id"]
        assert comp["config"]["keep"] == "first"
        assert comp["config"]["connection_format"] == "row"
        assert comp["inputs"] == []
        assert comp["outputs"] == []
        assert result.warnings == []

    def test_multiple_key_columns(self):
        node = _make_node(params={
            "UNIQUE_KEY": _make_unique_key_entries(
                ("id", True, True),
                ("name", True, False),
                ("email", False, True),
            ),
        })
        result = UniqueRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["key_columns"] == ["id", "name"]
        assert result.warnings == []

    def test_no_key_columns_selected(self):
        """All columns have KEY_ATTRIBUTE=false -> warning."""
        node = _make_node(params={
            "UNIQUE_KEY": _make_unique_key_entries(
                ("id", False, True),
                ("name", False, True),
            ),
        })
        result = UniqueRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["key_columns"] == []
        assert any("No key columns" in w for w in result.warnings)


# ------------------------------------------------------------------
# Keep behaviour (ONLY_ONCE_EACH_DUPLICATED_KEY)
# ------------------------------------------------------------------

class TestUniqueRowKeep:
    def test_keep_last_when_true(self):
        node = _make_node(params={
            "UNIQUE_KEY": _make_unique_key_entries(("id", True, True)),
            "ONLY_ONCE_EACH_DUPLICATED_KEY": "true",
        })
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["keep"] == "last"

    def test_keep_first_when_false(self):
        node = _make_node(params={
            "UNIQUE_KEY": _make_unique_key_entries(("id", True, True)),
            "ONLY_ONCE_EACH_DUPLICATED_KEY": "false",
        })
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["keep"] == "first"

    def test_keep_first_when_missing(self):
        node = _make_node(params={
            "UNIQUE_KEY": _make_unique_key_entries(("id", True, True)),
        })
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["keep"] == "first"


# ------------------------------------------------------------------
# Connection format
# ------------------------------------------------------------------

class TestUniqueRowConnectionFormat:
    def test_custom_connection_format(self):
        node = _make_node(params={
            "UNIQUE_KEY": _make_unique_key_entries(("id", True, True)),
            "CONNECTION_FORMAT": '"table"',
        })
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["connection_format"] == "table"

    def test_default_connection_format(self):
        node = _make_node(params={
            "UNIQUE_KEY": _make_unique_key_entries(("id", True, True)),
        })
        result = UniqueRowConverter().convert(node, [], {})
        assert result.component["config"]["connection_format"] == "row"


# ------------------------------------------------------------------
# Edge cases and error handling
# ------------------------------------------------------------------

class TestUniqueRowEdgeCases:
    def test_empty_unique_key_list(self):
        node = _make_node(params={"UNIQUE_KEY": []})
        result = UniqueRowConverter().convert(node, [], {})

        assert result.component["config"]["key_columns"] == []
        assert any("No key columns" in w for w in result.warnings)

    def test_missing_unique_key_param(self):
        node = _make_node(params={})
        result = UniqueRowConverter().convert(node, [], {})

        assert result.component["config"]["key_columns"] == []
        assert any("No key columns" in w for w in result.warnings)

    def test_unique_key_not_a_list(self):
        node = _make_node(params={"UNIQUE_KEY": "not_a_list"})
        result = UniqueRowConverter().convert(node, [], {})

        assert result.component["config"]["key_columns"] == []
        assert any("not a list" in w for w in result.warnings)

    def test_incomplete_group(self):
        """A trailing group with fewer than 3 entries generates a warning."""
        entries = _make_unique_key_entries(("id", True, True))
        # Add an incomplete group (only 2 entries)
        entries.append({"elementRef": "SCHEMA_COLUMN", "value": '"orphan"'})
        entries.append({"elementRef": "KEY_ATTRIBUTE", "value": "true"})

        node = _make_node(params={"UNIQUE_KEY": entries})
        result = UniqueRowConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["key_columns"] == ["id"]
        assert any("Incomplete" in w for w in result.warnings)


# ------------------------------------------------------------------
# Schema passthrough
# ------------------------------------------------------------------

class TestUniqueRowSchema:
    def test_schema_passthrough(self):
        node = _make_node(
            params={
                "UNIQUE_KEY": _make_unique_key_entries(("id", True, True)),
            },
            schema=_make_schema_columns(),
        )
        result = UniqueRowConverter().convert(node, [], {})

        schema = result.component["schema"]
        assert schema["input"] == schema["output"]
        assert len(schema["input"]) == 3
        assert schema["input"][0]["name"] == "id"
        assert schema["input"][1]["name"] == "name"
        assert schema["input"][2]["name"] == "email"

    def test_empty_schema(self):
        node = _make_node(params={
            "UNIQUE_KEY": _make_unique_key_entries(("id", True, True)),
        })
        result = UniqueRowConverter().convert(node, [], {})

        schema = result.component["schema"]
        assert schema == {"input": [], "output": []}


# ------------------------------------------------------------------
# Alias component types produce identical output
# ------------------------------------------------------------------

class TestUniqueRowAliases:
    def test_tUniqRow_alias(self):
        node = _make_node(
            params={
                "UNIQUE_KEY": _make_unique_key_entries(("col_a", True, True)),
                "ONLY_ONCE_EACH_DUPLICATED_KEY": "true",
            },
            component_type="tUniqRow",
        )
        result = UniqueRowConverter().convert(node, [], {})

        assert result.component["original_type"] == "tUniqRow"
        assert result.component["type"] == "UniqueRow"
        assert result.component["config"]["key_columns"] == ["col_a"]
        assert result.component["config"]["keep"] == "last"

    def test_tUnqRow_alias(self):
        node = _make_node(
            params={
                "UNIQUE_KEY": _make_unique_key_entries(("col_b", True, False)),
            },
            component_type="tUnqRow",
        )
        result = UniqueRowConverter().convert(node, [], {})

        assert result.component["original_type"] == "tUnqRow"
        assert result.component["type"] == "UniqueRow"
        assert result.component["config"]["key_columns"] == ["col_b"]
        assert result.component["config"]["keep"] == "first"
