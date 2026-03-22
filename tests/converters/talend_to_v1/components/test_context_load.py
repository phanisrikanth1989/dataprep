"""Tests for the ContextLoadConverter (tContextLoad -> ContextLoad)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendNode,
)
from src.converters.talend_to_v1.components.context.context_load import (
    ContextLoadConverter,
)
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="ctx_load_1",
               component_type="tContextLoad"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 320, "y": 160},
        raw_xml=ET.Element("node"),
    )


# ---- CONV-CL-001: Registration -----------------------------------------

class TestContextLoadRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tContextLoad") is ContextLoadConverter


# ---- CONV-CL-001 continued: Basic conversion ----------------------------

class TestContextLoadBasicConversion:
    def test_basic_conversion_with_all_params(self):
        """Full param mapping including DIE_ON_ERROR and DISABLE_WARNINGS."""
        node = _make_node(params={
            "CONTEXTFILE": '"/opt/conf/context.properties"',
            "FORMAT": '"properties"',
            "FIELDSEPARATOR": '";"',
            "CSV_SEPARATOR": '","',
            "PRINT_OPERATIONS": "true",
            "ERROR_IF_NOT_EXISTS": "true",
            "DIE_ON_ERROR": "true",
            "DISABLE_WARNINGS": "false",
        })
        result = ContextLoadConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "ctx_load_1"
        assert comp["type"] == "ContextLoad"
        assert comp["original_type"] == "tContextLoad"
        assert comp["position"] == {"x": 320, "y": 160}

        cfg = comp["config"]
        assert cfg["filepath"] == "/opt/conf/context.properties"
        assert cfg["format"] == "properties"
        assert cfg["delimiter"] == ";"
        assert cfg["csv_separator"] == ","
        assert cfg["print_operations"] is True
        assert cfg["error_if_not_exists"] is True
        assert cfg["die_on_error"] is True
        assert cfg["disable_warnings"] is False

    def test_defaults_when_params_missing(self):
        """All optional params should fall back to their documented defaults."""
        node = _make_node(params={})
        result = ContextLoadConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["filepath"] == ""
        assert cfg["format"] == "properties"
        assert cfg["delimiter"] == ";"
        assert cfg["csv_separator"] == ","
        assert cfg["print_operations"] is False
        assert cfg["error_if_not_exists"] is True
        assert cfg["die_on_error"] is False
        assert cfg["disable_warnings"] is False


# ---- CONV-CL-002: DIE_ON_ERROR mapping ---------------------------------

class TestContextLoadDieOnError:
    """Verify DIE_ON_ERROR param is correctly mapped (CONV-CL-002 fix)."""

    def test_die_on_error_true(self):
        node = _make_node(params={"DIE_ON_ERROR": "true"})
        result = ContextLoadConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is True

    def test_die_on_error_false(self):
        node = _make_node(params={"DIE_ON_ERROR": "false"})
        result = ContextLoadConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False

    def test_die_on_error_default_is_false(self):
        node = _make_node(params={})
        result = ContextLoadConverter().convert(node, [], {})
        assert result.component["config"]["die_on_error"] is False


# ---- CONV-CL-003: DISABLE_WARNINGS mapping -----------------------------

class TestContextLoadDisableWarnings:
    """Verify DISABLE_WARNINGS param is correctly mapped (CONV-CL-003 fix)."""

    def test_disable_warnings_true(self):
        node = _make_node(params={"DISABLE_WARNINGS": "true"})
        result = ContextLoadConverter().convert(node, [], {})
        assert result.component["config"]["disable_warnings"] is True

    def test_disable_warnings_false(self):
        node = _make_node(params={"DISABLE_WARNINGS": "false"})
        result = ContextLoadConverter().convert(node, [], {})
        assert result.component["config"]["disable_warnings"] is False

    def test_disable_warnings_default_is_false(self):
        node = _make_node(params={})
        result = ContextLoadConverter().convert(node, [], {})
        assert result.component["config"]["disable_warnings"] is False


# ---- CONV-CL-004: Utility schema ----------------------------------------

class TestContextLoadSchema:
    def test_utility_component_has_empty_schema(self):
        """ContextLoad is a utility component — no data flow schema."""
        node = _make_node(params={"CONTEXTFILE": '"/tmp/ctx.properties"'})
        result = ContextLoadConverter().convert(node, [], {})

        assert result.component["schema"] == {"input": [], "output": []}
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []


# ---- CONV-CL-005: Warnings / edge cases --------------------------------

class TestContextLoadWarnings:
    def test_empty_contextfile_produces_warning(self):
        node = _make_node(params={})
        result = ContextLoadConverter().convert(node, [], {})

        assert len(result.warnings) == 1
        assert "CONTEXTFILE" in result.warnings[0]

    def test_no_warnings_when_contextfile_present(self):
        node = _make_node(params={"CONTEXTFILE": '"/etc/app.properties"'})
        result = ContextLoadConverter().convert(node, [], {})

        assert result.warnings == []
        assert result.needs_review == []

    def test_csv_format_with_custom_separators(self):
        """CSV format with non-default separators should be preserved."""
        node = _make_node(params={
            "CONTEXTFILE": '"/data/ctx.csv"',
            "FORMAT": '"csv"',
            "FIELDSEPARATOR": '"|"',
            "CSV_SEPARATOR": '"\\t"',
        })
        result = ContextLoadConverter().convert(node, [], {})
        cfg = result.component["config"]

        assert cfg["format"] == "csv"
        assert cfg["delimiter"] == "|"
        assert cfg["csv_separator"] == "\\t"
