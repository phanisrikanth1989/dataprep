"""Tests for the RunJobConverter (tRunJob -> RunJobComponent)."""
import xml.etree.ElementTree as ET

from src.converters.talend_to_v1.components.base import (
    ComponentResult,
    TalendConnection,
    TalendNode,
)
from src.converters.talend_to_v1.components.control.run_job import RunJobConverter
from src.converters.talend_to_v1.components.registry import REGISTRY


def _make_node(params=None, schema=None, component_id="run_job_1",
               component_type="tRunJob"):
    return TalendNode(
        component_id=component_id,
        component_type=component_type,
        params=params or {},
        schema=schema or {},
        position={"x": 320, "y": 160},
        raw_xml=ET.Element("node"),
    )


class TestRunJobConverterRegistration:
    def test_registered_in_registry(self):
        assert REGISTRY.get("tRunJob") is RunJobConverter


class TestRunJobConverterBasic:
    def test_basic_conversion_with_all_params(self):
        node = _make_node(params={
            "PROCESS": '"child_job_001"',
            "CONTEXT_NAME": '"Production"',
            "DIE_ON_CHILD_ERROR": "true",
            "PRINT_PARAMETER": "true",
            "CONTEXTPARAMS": [
                {"elementRef": "db_host", "value": '"localhost"'},
                {"elementRef": "db_port", "value": '"5432"'},
            ],
        })
        result = RunJobConverter().convert(node, [], {})

        assert isinstance(result, ComponentResult)
        comp = result.component
        assert comp["id"] == "run_job_1"
        assert comp["type"] == "RunJobComponent"
        assert comp["original_type"] == "tRunJob"
        assert comp["position"] == {"x": 320, "y": 160}
        assert comp["config"]["process"] == "child_job_001"
        assert comp["config"]["context_name"] == "Production"
        assert comp["config"]["die_on_child_error"] is True
        assert comp["config"]["print_parameter"] is True
        assert comp["config"]["context_params"] == [
            {"name": "db_host", "value": "localhost"},
            {"name": "db_port", "value": "5432"},
        ]
        assert comp["inputs"] == []
        assert comp["outputs"] == []

    def test_defaults_when_params_missing(self):
        node = _make_node(params={})
        result = RunJobConverter().convert(node, [], {})

        cfg = result.component["config"]
        assert cfg["process"] == ""
        assert cfg["context_name"] == "Default"
        assert cfg["die_on_child_error"] is True
        assert cfg["print_parameter"] is False
        assert cfg["context_params"] == []

    def test_die_on_child_error_false(self):
        node = _make_node(params={
            "PROCESS": '"some_job"',
            "DIE_ON_CHILD_ERROR": "false",
        })
        result = RunJobConverter().convert(node, [], {})

        assert result.component["config"]["die_on_child_error"] is False

    def test_quoted_process_name(self):
        """PROCESS param often arrives with surrounding quotes."""
        node = _make_node(params={
            "PROCESS": '"my_etl_job"',
        })
        result = RunJobConverter().convert(node, [], {})

        assert result.component["config"]["process"] == "my_etl_job"

    def test_unquoted_process_name(self):
        """PROCESS param without quotes should pass through as-is."""
        node = _make_node(params={
            "PROCESS": "my_etl_job",
        })
        result = RunJobConverter().convert(node, [], {})

        assert result.component["config"]["process"] == "my_etl_job"


class TestRunJobConverterContextParams:
    def test_empty_context_params(self):
        node = _make_node(params={
            "PROCESS": '"job_1"',
            "CONTEXTPARAMS": [],
        })
        result = RunJobConverter().convert(node, [], {})

        assert result.component["config"]["context_params"] == []

    def test_multiple_context_params(self):
        node = _make_node(params={
            "PROCESS": '"job_1"',
            "CONTEXTPARAMS": [
                {"elementRef": "param_a", "value": '"value_a"'},
                {"elementRef": "param_b", "value": '"value_b"'},
                {"elementRef": "param_c", "value": '"value_c"'},
            ],
        })
        result = RunJobConverter().convert(node, [], {})

        ctx = result.component["config"]["context_params"]
        assert len(ctx) == 3
        assert ctx[0] == {"name": "param_a", "value": "value_a"}
        assert ctx[1] == {"name": "param_b", "value": "value_b"}
        assert ctx[2] == {"name": "param_c", "value": "value_c"}

    def test_context_params_skips_empty_element_ref(self):
        """Entries without a meaningful elementRef should be skipped."""
        node = _make_node(params={
            "PROCESS": '"job_1"',
            "CONTEXTPARAMS": [
                {"elementRef": "", "value": '"orphan_value"'},
                {"elementRef": "valid_param", "value": '"ok"'},
            ],
        })
        result = RunJobConverter().convert(node, [], {})

        ctx = result.component["config"]["context_params"]
        assert len(ctx) == 1
        assert ctx[0] == {"name": "valid_param", "value": "ok"}

    def test_context_params_not_a_list_produces_warning(self):
        """If CONTEXTPARAMS is not a list (e.g. malformed XML), warn."""
        node = _make_node(params={
            "PROCESS": '"job_1"',
            "CONTEXTPARAMS": "bad_value",
        })
        result = RunJobConverter().convert(node, [], {})

        assert result.component["config"]["context_params"] == []
        assert any("CONTEXTPARAMS" in w for w in result.warnings)


class TestRunJobConverterWarnings:
    def test_empty_process_produces_warning(self):
        node = _make_node(params={})
        result = RunJobConverter().convert(node, [], {})

        assert any("PROCESS" in w for w in result.warnings)

    def test_no_warnings_for_valid_config(self):
        node = _make_node(params={
            "PROCESS": '"child_job"',
            "CONTEXT_NAME": '"Default"',
            "DIE_ON_CHILD_ERROR": "true",
            "PRINT_PARAMETER": "false",
        })
        result = RunJobConverter().convert(node, [], {})

        assert result.warnings == []
        assert result.needs_review == []


class TestRunJobConverterSchema:
    def test_utility_component_has_empty_schema(self):
        """RunJobComponent is a utility component -- no data flow schema."""
        node = _make_node(params={"PROCESS": '"job_1"'})
        result = RunJobConverter().convert(node, [], {})

        assert result.component["schema"] == {"input": [], "output": []}
