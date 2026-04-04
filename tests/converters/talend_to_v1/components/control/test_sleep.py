"""Tests for SleepConverter (tSleep -> v1 sleep config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import SchemaColumn, TalendNode
from src.converters.talend_to_v1.components.control.sleep import SleepConverter
from src.converters.talend_to_v1.components.registry import REGISTRY

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


def _make_node(params=None, schema=None, component_id="sleep_1",
               component_type="tSleep"):
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
        assert REGISTRY.get("tSleep") is SleepConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_pause_duration_default(self):
        """PAUSE defaults to '1' per _java.xml (string, not int -- engine handles float conversion)."""
        node = _make_node()
        result = SleepConverter().convert(node, [], {})
        assert result.component["config"]["pause_duration"] == "1"

    def test_tstatcatcher_stats_default(self):
        """tstatcatcher_stats defaults to False."""
        node = _make_node()
        result = SleepConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_label_default(self):
        """label defaults to empty string."""
        node = _make_node()
        result = SleepConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_pause_duration_extracted(self):
        """PAUSE='5' extracts as '5' (string)."""
        node = _make_node(params={"PAUSE": '"5"'})
        result = SleepConverter().convert(node, [], {})
        assert result.component["config"]["pause_duration"] == "5"

    def test_pause_duration_fractional(self):
        """PAUSE='0.5' extracts as '0.5' (string, engine handles float conversion)."""
        node = _make_node(params={"PAUSE": '"0.5"'})
        result = SleepConverter().convert(node, [], {})
        assert result.component["config"]["pause_duration"] == "0.5"

    def test_pause_duration_context_var(self):
        """PAUSE with context variable is preserved as string for runtime resolution."""
        node = _make_node(params={"PAUSE": '"context.sleepTime"'})
        result = SleepConverter().convert(node, [], {})
        assert result.component["config"]["pause_duration"] == "context.sleepTime"

    def test_pause_duration_zero(self):
        """PAUSE='0' extracts as '0'."""
        node = _make_node(params={"PAUSE": '"0"'})
        result = SleepConverter().convert(node, [], {})
        assert result.component["config"]["pause_duration"] == "0"


class TestTableParsing:
    """tSleep has no TABLE params -- placeholder class."""

    def test_no_table_params(self):
        """tSleep has no TABLE parameters."""
        node = _make_node()
        result = SleepConverter().convert(node, [], {})
        # No TABLE-derived keys in config
        assert "pause_duration" in result.component["config"]


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        node = _make_node()
        result = SleepConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = SleepConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        node = _make_node()
        result = SleepConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        node = _make_node(params={"LABEL": '"my_label"'})
        result = SleepConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_label"


class TestSchema:
    """Verify schema extraction."""

    def test_schema_extracted(self):
        """Schema columns are extracted when present."""
        node = _make_node(schema=_make_schema_columns())
        result = SleepConverter().convert(node, [], {})
        assert "schema" in result.component


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_no_needs_review(self):
        """tSleep has no engine gaps -- needs_review should be empty."""
        node = _make_node()
        result = SleepConverter().convert(node, [], {})
        assert result.needs_review == []

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = SleepConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """Config has all expected keys: pause_duration, tstatcatcher_stats, label plus base keys."""
        node = _make_node(schema=_make_schema_columns())
        result = SleepConverter().convert(node, [], {})
        expected_keys = {
            "pause_duration",
            "tstatcatcher_stats",
            "label",
        }
        actual_config_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_config_keys
        assert not missing, f"Missing config keys: {missing}"


class TestPhantomParams:
    """Verify params NOT in _java.xml are NOT extracted."""

    def test_no_phantom_die_on_error(self):
        """DIE_ON_ERROR is not in tSleep _java.xml and should not appear in config."""
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = SleepConverter().convert(node, [], {})
        assert "die_on_error" not in result.component["config"]
