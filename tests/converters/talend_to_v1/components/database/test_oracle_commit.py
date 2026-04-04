"""Tests for OracleCommitConverter (tOracleCommit -> v1 oracle commit config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.database.oracle_commit import (
    OracleCommitConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="ocm_1",
               component_type="tOracleCommit"):
    """Create a TalendNode for tOracleCommit testing."""
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
# TestRegistration
# ------------------------------------------------------------------

class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        assert REGISTRY.get("tOracleCommit") is OracleCommitConverter


# ------------------------------------------------------------------
# TestDefaults
# ------------------------------------------------------------------

class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_connection_default(self):
        node = _make_node()
        result = OracleCommitConverter().convert(node, [], {})
        assert result.component["config"]["connection"] == ""

    def test_close_default(self):
        node = _make_node()
        result = OracleCommitConverter().convert(node, [], {})
        assert result.component["config"]["close"] is True


# ------------------------------------------------------------------
# TestParameterExtraction
# ------------------------------------------------------------------

class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_connection_extracted(self):
        node = _make_node(params={"CONNECTION": '"tOracleConnection_1"'})
        result = OracleCommitConverter().convert(node, [], {})
        assert result.component["config"]["connection"] == "tOracleConnection_1"

    def test_connection_unquoted(self):
        """Unquoted connection string should still work."""
        node = _make_node(params={"CONNECTION": "tOracleConnection_1"})
        result = OracleCommitConverter().convert(node, [], {})
        assert result.component["config"]["connection"] == "tOracleConnection_1"

    def test_close_false(self):
        node = _make_node(params={"CLOSE": "false"})
        result = OracleCommitConverter().convert(node, [], {})
        assert result.component["config"]["close"] is False

    def test_close_true(self):
        node = _make_node(params={"CLOSE": "true"})
        result = OracleCommitConverter().convert(node, [], {})
        assert result.component["config"]["close"] is True


# ------------------------------------------------------------------
# TestFrameworkParams
# ------------------------------------------------------------------

class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = OracleCommitConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = OracleCommitConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = OracleCommitConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = OracleCommitConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


# ------------------------------------------------------------------
# TestSchema
# ------------------------------------------------------------------

class TestSchema:
    """Verify schema extraction."""

    def test_schema_is_empty_dict(self):
        """Utility component has no data flow -- schema is always empty input/output."""
        node = _make_node(schema=_make_schema_columns())
        result = OracleCommitConverter().convert(node, [], {})
        assert result.component["schema"] == {"input": [], "output": []}

    def test_schema_empty_when_no_flow(self):
        """Utility component with no FLOW schema."""
        node = _make_node()
        result = OracleCommitConverter().convert(node, [], {})
        assert result.component["schema"] == {"input": [], "output": []}


# ------------------------------------------------------------------
# TestNeedsReview
# ------------------------------------------------------------------

class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_needs_review_count(self):
        """Single consolidated needs_review per D-27."""
        node = _make_node()
        result = OracleCommitConverter().convert(node, [], {})
        assert len(result.needs_review) == 1

    def test_needs_review_is_engine_gap(self):
        node = _make_node()
        result = OracleCommitConverter().convert(node, [], {})
        assert result.needs_review[0]["severity"] == "engine_gap"

    def test_needs_review_message(self):
        node = _make_node()
        result = OracleCommitConverter().convert(node, [], {})
        assert "No concrete engine implementation for tOracleCommit" in result.needs_review[0]["issue"]

    def test_needs_review_has_component_id(self):
        node = _make_node(component_id="test_comp")
        result = OracleCommitConverter().convert(node, [], {})
        assert result.needs_review[0]["component"] == "test_comp"

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = OracleCommitConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


# ------------------------------------------------------------------
# TestCompleteness
# ------------------------------------------------------------------

class TestComponentStructure:
    """Verify standard component dict structure."""

    def test_id_at_top_level(self):
        node = _make_node()
        result = OracleCommitConverter().convert(node, [], {})
        assert result.component["id"] == "ocm_1"

    def test_type_at_top_level(self):
        node = _make_node()
        result = OracleCommitConverter().convert(node, [], {})
        assert result.component["type"] == "tOracleCommit"

    def test_original_type_at_top_level(self):
        node = _make_node()
        result = OracleCommitConverter().convert(node, [], {})
        assert result.component["original_type"] == "tOracleCommit"


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        node = _make_node(schema=_make_schema_columns())
        result = OracleCommitConverter().convert(node, [], {})
        expected_keys = {
            "connection", "close",
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"
