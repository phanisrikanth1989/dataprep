"""Tests for RunJobConverter (tRunJob -> v1 run_job config)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    SchemaColumn,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.control.run_job import RunJobConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def _make_node(params=None, schema=None, component_id="rj_1",
               component_type="tRunJob"):
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


def _make_context_params_data(rows):
    """Generate CONTEXTPARAMS TABLE data with stride-2 per row.

    rows: list of tuples (param_name, param_value)
    Each tuple produces 2 elementRef entries: PARAM_NAME_COLUMN + PARAM_VALUE_COLUMN.
    """
    result = []
    for param_name, param_value in rows:
        result.append({"elementRef": "PARAM_NAME_COLUMN", "value": param_name})
        result.append({"elementRef": "PARAM_VALUE_COLUMN", "value": param_value})
    return result


def _make_jvm_arguments_data(rows):
    """Generate JVM_ARGUMENTS TABLE data with stride-1 per row.

    rows: list of strings (argument values)
    Each string produces 1 elementRef entry: ARGUMENT.
    """
    result = []
    for argument in rows:
        result.append({"elementRef": "ARGUMENT", "value": argument})
    return result


# ------------------------------------------------------------------
# Test Classes
# ------------------------------------------------------------------


class TestRegistration:
    """Verify component is registered correctly."""

    def test_registered_in_registry(self):
        """tRunJob must be registered in the converter registry."""
        assert REGISTRY.get("tRunJob") is RunJobConverter


class TestDefaults:
    """Verify all parameters have correct defaults when no params provided."""

    def test_use_dynamic_job_default(self):
        """USE_DYNAMIC_JOB defaults to False."""
        node = _make_node()
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["use_dynamic_job"] is False

    def test_context_job_default(self):
        """CONTEXT_JOB defaults to empty string."""
        node = _make_node()
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["context_job"] == ""

    def test_process_default(self):
        """PROCESS defaults to empty string."""
        node = _make_node()
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["process"] == ""

    def test_context_name_default(self):
        """CONTEXT_NAME defaults to 'Default'."""
        node = _make_node()
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["context_name"] == "Default"

    def test_use_independent_process_default(self):
        """USE_INDEPENDENT_PROCESS defaults to False."""
        node = _make_node()
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["use_independent_process"] is False

    def test_die_on_child_error_default(self):
        """DIE_ON_CHILD_ERROR defaults to True."""
        node = _make_node()
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["die_on_child_error"] is True

    def test_transmit_whole_context_default(self):
        """TRANSMIT_WHOLE_CONTEXT defaults to False."""
        node = _make_node()
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["transmit_whole_context"] is False

    def test_context_params_default(self):
        """CONTEXTPARAMS defaults to empty list."""
        node = _make_node()
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["context_params"] == []

    def test_propagate_child_result_default(self):
        """PROPAGATE_CHILD_RESULT defaults to False."""
        node = _make_node()
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["propagate_child_result"] is False

    def test_print_parameter_default(self):
        """PRINT_PARAMETER defaults to False."""
        node = _make_node()
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["print_parameter"] is False

    def test_transmit_original_context_default(self):
        """TRANSMIT_ORIGINAL_CONTEXT defaults to True."""
        node = _make_node()
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["transmit_original_context"] is True

    def test_use_child_jvm_setting_default(self):
        """USE_CHILD_JVM_SETTING defaults to True."""
        node = _make_node()
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["use_child_jvm_setting"] is True

    def test_use_custom_jvm_setting_default(self):
        """USE_CUSTOM_JVM_SETTING defaults to False."""
        node = _make_node()
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["use_custom_jvm_setting"] is False

    def test_jvm_arguments_default(self):
        """JVM_ARGUMENTS defaults to empty list."""
        node = _make_node()
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["jvm_arguments"] == []

    def test_use_dynamic_context_default(self):
        """USE_DYNAMIC_CONTEXT defaults to False."""
        node = _make_node()
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["use_dynamic_context"] is False

    def test_dynamic_context_default(self):
        """DYNAMIC_CONTEXT defaults to empty string."""
        node = _make_node()
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["dynamic_context"] == ""

    def test_use_extra_classpath_default(self):
        """USE_EXTRA_CLASSPATH defaults to False."""
        node = _make_node()
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["use_extra_classpath"] is False

    def test_extra_classpath_default(self):
        """EXTRA_CLASSPATH defaults to empty string."""
        node = _make_node()
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["extra_classpath"] == ""

    def test_load_context_from_file_default(self):
        """LOAD_CONTEXT_FROM_FILE defaults to False."""
        node = _make_node()
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["load_context_from_file"] is False


class TestParameterExtraction:
    """Verify each parameter is correctly extracted from XML params."""

    def test_use_dynamic_job_true(self):
        """USE_DYNAMIC_JOB=true extracts as True."""
        node = _make_node(params={"USE_DYNAMIC_JOB": "true"})
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["use_dynamic_job"] is True

    def test_context_job_extracted(self):
        """CONTEXT_JOB value is extracted with quotes stripped."""
        node = _make_node(params={"CONTEXT_JOB": '"myJob"'})
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["context_job"] == "myJob"

    def test_process_extracted(self):
        """PROCESS value is extracted with quotes stripped."""
        node = _make_node(params={"PROCESS": '"childJob"'})
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["process"] == "childJob"

    def test_context_name_extracted(self):
        """CONTEXT_NAME value is extracted with quotes stripped."""
        node = _make_node(params={"CONTEXT_NAME": '"Production"'})
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["context_name"] == "Production"

    def test_die_on_child_error_false(self):
        """DIE_ON_CHILD_ERROR=false extracts as False."""
        node = _make_node(params={"DIE_ON_CHILD_ERROR": "false"})
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["die_on_child_error"] is False

    def test_transmit_whole_context_true(self):
        """TRANSMIT_WHOLE_CONTEXT=true extracts as True."""
        node = _make_node(params={"TRANSMIT_WHOLE_CONTEXT": "true"})
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["transmit_whole_context"] is True

    def test_propagate_child_result_true(self):
        """PROPAGATE_CHILD_RESULT=true extracts as True."""
        node = _make_node(params={"PROPAGATE_CHILD_RESULT": "true"})
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["propagate_child_result"] is True

    def test_use_dynamic_context_true_with_value(self):
        """USE_DYNAMIC_CONTEXT=true + DYNAMIC_CONTEXT value extracted."""
        node = _make_node(params={
            "USE_DYNAMIC_CONTEXT": "true",
            "DYNAMIC_CONTEXT": '"context.myDynCtx"',
        })
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["use_dynamic_context"] is True
        assert result.component["config"]["dynamic_context"] == "context.myDynCtx"

    def test_use_independent_process_true(self):
        """USE_INDEPENDENT_PROCESS=true extracts as True."""
        node = _make_node(params={"USE_INDEPENDENT_PROCESS": "true"})
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["use_independent_process"] is True

    def test_use_extra_classpath_true_with_value(self):
        """USE_EXTRA_CLASSPATH=true + EXTRA_CLASSPATH value extracted."""
        node = _make_node(params={
            "USE_EXTRA_CLASSPATH": "true",
            "EXTRA_CLASSPATH": '"/opt/lib/custom.jar"',
        })
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["use_extra_classpath"] is True
        assert result.component["config"]["extra_classpath"] == "/opt/lib/custom.jar"

    def test_load_context_from_file_true(self):
        """LOAD_CONTEXT_FROM_FILE=true extracts as True."""
        node = _make_node(params={"LOAD_CONTEXT_FROM_FILE": "true"})
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["load_context_from_file"] is True

    def test_transmit_original_context_false(self):
        """TRANSMIT_ORIGINAL_CONTEXT=false extracts as False."""
        node = _make_node(params={"TRANSMIT_ORIGINAL_CONTEXT": "false"})
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["transmit_original_context"] is False


class TestTableParsing:
    """Verify TABLE parameter parsing for CONTEXTPARAMS and JVM_ARGUMENTS."""

    def test_context_params_parsed(self):
        """CONTEXTPARAMS with PARAM_NAME_COLUMN + PARAM_VALUE_COLUMN pairs parsed."""
        data = _make_context_params_data([("db_host", '"localhost"')])
        node = _make_node(params={"CONTEXTPARAMS": data})
        result = RunJobConverter().convert(node, [], {})
        assert len(result.component["config"]["context_params"]) == 1
        assert result.component["config"]["context_params"][0]["param_name"] == "db_host"
        assert result.component["config"]["context_params"][0]["param_value"] == "localhost"

    def test_context_params_empty_when_missing(self):
        """CONTEXTPARAMS defaults to empty list when not provided."""
        node = _make_node()
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["context_params"] == []

    def test_context_params_multiple_entries(self):
        """CONTEXTPARAMS with multiple rows parsed correctly."""
        data = _make_context_params_data([
            ("db_host", '"localhost"'),
            ("db_port", '"5432"'),
            ("db_name", '"mydb"'),
        ])
        node = _make_node(params={"CONTEXTPARAMS": data})
        result = RunJobConverter().convert(node, [], {})
        params = result.component["config"]["context_params"]
        assert len(params) == 3
        assert params[0] == {"param_name": "db_host", "param_value": "localhost"}
        assert params[1] == {"param_name": "db_port", "param_value": "5432"}
        assert params[2] == {"param_name": "db_name", "param_value": "mydb"}

    def test_context_params_strip_quotes(self):
        """CONTEXTPARAMS values have surrounding quotes stripped."""
        data = _make_context_params_data([("key", '"quoted_value"')])
        node = _make_node(params={"CONTEXTPARAMS": data})
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["context_params"][0]["param_value"] == "quoted_value"

    def test_jvm_arguments_parsed(self):
        """JVM_ARGUMENTS with ARGUMENT entries parsed."""
        data = _make_jvm_arguments_data(['"-Xmx1024m"', '"-Xms256m"'])
        node = _make_node(params={"JVM_ARGUMENTS": data})
        result = RunJobConverter().convert(node, [], {})
        args = result.component["config"]["jvm_arguments"]
        assert len(args) == 2
        assert args[0] == {"argument": "-Xmx1024m"}
        assert args[1] == {"argument": "-Xms256m"}

    def test_jvm_arguments_empty_when_missing(self):
        """JVM_ARGUMENTS defaults to empty list when not provided."""
        node = _make_node()
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["jvm_arguments"] == []

    def test_context_params_incomplete_stride_skipped(self):
        """Incomplete trailing CONTEXTPARAMS group (< 2 entries) is skipped."""
        data = _make_context_params_data([("db_host", '"localhost"')])
        # Add an incomplete group (only 1 of 2 entries)
        data.append({"elementRef": "PARAM_NAME_COLUMN", "value": "orphan"})
        node = _make_node(params={"CONTEXTPARAMS": data})
        result = RunJobConverter().convert(node, [], {})
        assert len(result.component["config"]["context_params"]) == 1

    def test_context_params_non_list_returns_empty(self):
        """Non-list CONTEXTPARAMS value returns empty list."""
        node = _make_node(params={"CONTEXTPARAMS": "bad_value"})
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["context_params"] == []


class TestFrameworkParams:
    """Verify tstatcatcher_stats and label extraction."""

    def test_tstatcatcher_stats_default_false(self):
        """TSTATCATCHER_STATS defaults to False."""
        node = _make_node()
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is False

    def test_tstatcatcher_stats_true(self):
        """TSTATCATCHER_STATS=true extracts as True."""
        node = _make_node(params={"TSTATCATCHER_STATS": "true"})
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["tstatcatcher_stats"] is True

    def test_label_default_empty(self):
        """LABEL defaults to empty string."""
        node = _make_node()
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["label"] == ""

    def test_label_extracted(self):
        """LABEL value is extracted with quotes stripped."""
        node = _make_node(params={"LABEL": '"my_run_job_label"'})
        result = RunJobConverter().convert(node, [], {})
        assert result.component["config"]["label"] == "my_run_job_label"


class TestSchema:
    """Verify schema extraction."""

    def test_schema_at_top_level(self):
        """Schema is at top level of component dict via _build_component_dict."""
        node = _make_node()
        result = RunJobConverter().convert(node, [], {})
        assert "schema" in result.component
        assert result.component["schema"] == {"input": [], "output": []}

    def test_schema_is_empty_for_control_component(self):
        """Control component has empty schema even with FLOW schema columns defined."""
        node = _make_node(schema=_make_schema_columns())
        result = RunJobConverter().convert(node, [], {})
        assert result.component["schema"] == {"input": [], "output": []}


class TestNeedsReview:
    """Verify needs_review entries for engine gaps."""

    def test_no_engine_gap_now_that_engine_exists(self):
        """No engine_gap needs_review entry -- tRunJob engine is now implemented."""
        result = RunJobConverter().convert(_make_node({}), [], {})
        assert all(nr.get("severity") != "engine_gap" for nr in result.needs_review)

    def test_no_framework_param_needs_review(self):
        """Framework params (tstatcatcher_stats, label) must NOT have needs_review."""
        node = _make_node()
        result = RunJobConverter().convert(node, [], {})
        issues = [e["issue"] for e in result.needs_review]
        for issue in issues:
            assert "tstatcatcher_stats" not in issue
            assert "label" not in issue.lower().split()


class TestCompleteness:
    """Verify all expected config keys are present."""

    def test_all_config_keys_present(self):
        """All 18 unique + 2 framework config keys must be present."""
        node = _make_node(schema=_make_schema_columns())
        result = RunJobConverter().convert(node, [], {})
        expected_keys = {
            # Core params
            "use_dynamic_job", "context_job", "process", "context_name",
            "use_independent_process", "die_on_child_error", "transmit_whole_context",
            # TABLE params
            "context_params", "jvm_arguments",
            # Advanced params
            "propagate_child_result", "print_parameter", "transmit_original_context",
            "use_child_jvm_setting", "use_custom_jvm_setting",
            "use_dynamic_context", "dynamic_context",
            "use_extra_classpath", "extra_classpath", "load_context_from_file",
            # Framework params
            "tstatcatcher_stats", "label",
        }
        actual_keys = set(result.component["config"].keys())
        missing = expected_keys - actual_keys
        assert not missing, f"Missing config keys: {missing}"

    def test_standard_component_structure(self):
        """Component dict has standard top-level keys from _build_component_dict."""
        node = _make_node(component_id="rj_1")
        result = RunJobConverter().convert(node, [], {})
        assert result.component["id"] == "rj_1"
        assert result.component["type"] == "tRunJob"
        assert result.component["original_type"] == "tRunJob"
        assert result.component["position"] == {"x": 100, "y": 200}
        assert isinstance(result.component["config"], dict)
        assert isinstance(result.component["schema"], dict)
        assert result.component["inputs"] == []
        assert result.component["outputs"] == []


class TestPhantomParams:
    """Verify no phantom params -- tRunJob had no phantom params to remove."""

    def test_no_phantom_params(self):
        """No phantom params were removed for tRunJob (all existing params were valid)."""
        node = _make_node()
        result = RunJobConverter().convert(node, [], {})
        # Verify no cruft keys in config dict
        config = result.component["config"]
        assert "component_type" not in config, "component_type should not be in config"
        assert "component_id" not in config, "component_id should not be in config"
        assert "schema" not in config, "schema should not be in config (it's at top level)"
