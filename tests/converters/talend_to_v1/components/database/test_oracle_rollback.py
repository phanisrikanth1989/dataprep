"""Tests for OracleRollbackConverter (tOracleRollback -> no engine)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.database.oracle_rollback import (
    OracleRollbackConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="tOracleRollback_1",
               component_type="tOracleRollback"):
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
    """Return a sample FLOW schema for testing."""
    return {
        "FLOW": [
            SchemaColumn(name="id", type="id_Integer", nullable=False, key=True, length=10),
            SchemaColumn(name="name", type="id_String", nullable=True, length=50),
        ]
    }


# ------------------------------------------------------------------
# Test Classes (one per concern)
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tOracleRollback") is OracleRollbackConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_connection_default(self):
        node = _make_node()
        result = OracleRollbackConverter().convert(node, [], {})
        assert result.component["config"]["connection"] == ""

    def test_close_default(self):
        node = _make_node()
        result = OracleRollbackConverter().convert(node, [], {})
        assert result.component["config"]["close"] is True


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_connection_extracted(self):
        node = _make_node(params={"CONNECTION": '"tOracleConnection_1"'})
        result = OracleRollbackConverter().convert(node, [], {})
        assert result.component["config"]["connection"] == "tOracleConnection_1"

    def test_close_false(self):
        node = _make_node(params={"CLOSE": "false"})
        result = OracleRollbackConverter().convert(node, [], {})
        assert result.component["config"]["close"] is False


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = OracleRollbackConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = OracleRollbackConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = OracleRollbackConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = OracleRollbackConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction."""

    def test_schema_is_empty_dict(self):
        """Utility component has no data flow -- schema is always empty input/output."""
        node = _make_node(schema=_make_schema_columns())
        result = OracleRollbackConverter().convert(node, [], {})
        assert result.component["schema"] == {"input": [], "output": []}


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        node = _make_node()
        result = OracleRollbackConverter().convert(node, [], {})
        assert len(result.needs_review) == 1

    def test_needs_review_is_engine_gap(self):
        node = _make_node()
        result = OracleRollbackConverter().convert(node, [], {})
        assert result.needs_review[0]["severity"] == "engine_gap"

    def test_needs_review_message(self):
        node = _make_node()
        result = OracleRollbackConverter().convert(node, [], {})
        assert "No concrete engine implementation for tOracleRollback" in result.needs_review[0]["issue"]


class TestComponentStructure:
    """Verify standard component dict structure."""

    def test_id_at_top_level(self):
        node = _make_node()
        result = OracleRollbackConverter().convert(node, [], {})
        assert result.component["id"] == "tOracleRollback_1"

    def test_type_at_top_level(self):
        node = _make_node()
        result = OracleRollbackConverter().convert(node, [], {})
        assert result.component["type"] == "tOracleRollback"

    def test_original_type_at_top_level(self):
        node = _make_node()
        result = OracleRollbackConverter().convert(node, [], {})
        assert result.component["original_type"] == "tOracleRollback"


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = OracleRollbackConverter().convert(node, [], {})
        expected_keys = {
            "connection", "close",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_connection_format_not_in_output(self):
        """CONNECTION_FORMAT is a phantom param -- must NOT appear in output."""
        node = _make_node(params={"CONNECTION_FORMAT": '"row"'})
        result = OracleRollbackConverter().convert(node, [], {})
        assert "connection_format" not in result.component["config"]
