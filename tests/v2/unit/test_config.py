"""
Tests for v2 config schema (clean, no V1 compat).

Validates JobConfig, FlowConnection, and ContextVariable models.
"""
from datetime import date, datetime

import pytest
from pydantic import ValidationError
from src.v2.config.job_config import (
    JobConfig, FlowConnection, ContextVariable, TriggerType, TriggerConnection,
)


class TestJobConfig:
    def test_minimal_valid_config(self):
        config = JobConfig(
            name="test_job",
            components=[{"id": "src", "type": "file_input_delimited", "config": {}}],
            flows=[],
        )
        assert config.name == "test_job"
        assert config.version == "2.0"

    def test_context_typed_values(self):
        config = JobConfig(
            name="test",
            context={
                "rate": {"value": 0.08, "type": "float"},
                "name": {"value": "test", "type": "str"},
                "count": {"value": 10, "type": "int"},
            },
            components=[], flows=[],
        )
        vals = config.get_context_values()
        assert vals["rate"] == 0.08
        assert isinstance(vals["rate"], float)
        assert vals["count"] == 10

    def test_context_bare_values_auto_wrap(self):
        config = JobConfig(
            name="test",
            context={"env": "prod", "debug": True},
            components=[], flows=[],
        )
        vals = config.get_context_values()
        assert vals["env"] == "prod"
        assert vals["debug"] is True

    def test_context_date_iso(self):
        config = JobConfig(
            name="test",
            context={"start": {"value": "2026-03-01", "type": "date"}},
            components=[], flows=[],
        )
        val = config.get_context_values()["start"]
        assert val == date(2026, 3, 1)
        assert isinstance(val, date)

    def test_context_datetime_iso(self):
        config = JobConfig(
            name="test",
            context={"ts": {"value": "2026-03-01T14:30:00", "type": "datetime"}},
            components=[], flows=[],
        )
        val = config.get_context_values()["ts"]
        assert val == datetime(2026, 3, 1, 14, 30, 0)
        assert isinstance(val, datetime)

    def test_context_date_custom_format(self):
        config = JobConfig(
            name="test",
            context={"start": {"value": "01/03/2026", "type": "date", "format": "%d/%m/%Y"}},
            components=[], flows=[],
        )
        val = config.get_context_values()["start"]
        assert val == date(2026, 3, 1)

    def test_context_datetime_custom_format(self):
        config = JobConfig(
            name="test",
            context={"ts": {"value": "03-01-2026 02:30 PM", "type": "datetime", "format": "%m-%d-%Y %I:%M %p"}},
            components=[], flows=[],
        )
        val = config.get_context_values()["ts"]
        assert val == datetime(2026, 3, 1, 14, 30, 0)

    def test_context_date_invalid_raises(self):
        config = JobConfig(
            name="test",
            context={"bad": {"value": "not-a-date", "type": "date"}},
            components=[], flows=[],
        )
        with pytest.raises(ValueError):
            config.get_context_values()

    def test_context_date_none_value(self):
        var = ContextVariable(value=None, type="date")
        assert var.get_typed_value() is None

    def test_flow_defaults(self):
        flow = FlowConnection(source="a", target="b")
        assert flow.output == "main"
        assert flow.input == "main"

    def test_flow_named_ports(self):
        flow = FlowConnection(source="a", target="b", output="reject", input="main")
        assert flow.output == "reject"


# ── Trigger Config Tests ──────────────────────────────────────────────


class TestTriggerConnection:
    """Tests for TriggerConnection Pydantic model."""

    def test_on_success_trigger(self):
        t = TriggerConnection(source="A", target="B", type=TriggerType.ON_SUCCESS)
        assert t.source == "A"
        assert t.target == "B"
        assert t.type == TriggerType.ON_SUCCESS
        assert t.condition is None

    def test_on_failure_trigger(self):
        t = TriggerConnection(source="A", target="B", type=TriggerType.ON_FAILURE)
        assert t.type == TriggerType.ON_FAILURE

    def test_conditional_trigger_with_condition(self):
        t = TriggerConnection(
            source="A", target="B",
            type=TriggerType.CONDITIONAL,
            condition="${context.env} == 'PROD'",
        )
        assert t.type == TriggerType.CONDITIONAL
        assert t.condition == "${context.env} == 'PROD'"

    def test_trigger_type_string_values(self):
        assert TriggerType.ON_SUCCESS.value == "on_success"
        assert TriggerType.ON_FAILURE.value == "on_failure"
        assert TriggerType.CONDITIONAL.value == "conditional"

    def test_trigger_from_dict(self):
        t = TriggerConnection(**{
            "source": "ctx_load",
            "target": "file_in",
            "type": "on_success",
        })
        assert t.type == TriggerType.ON_SUCCESS

    def test_conditional_trigger_from_dict(self):
        t = TriggerConnection(**{
            "source": "A",
            "target": "B",
            "type": "conditional",
            "condition": "${context.row_count} > 0",
        })
        assert t.type == TriggerType.CONDITIONAL
        assert t.condition == "${context.row_count} > 0"

    def test_conditional_trigger_without_condition_raises(self):
        with pytest.raises(ValidationError):
            TriggerConnection(source="A", target="B", type=TriggerType.CONDITIONAL)


class TestJobConfigTriggers:
    """Tests for triggers field on JobConfig."""

    def test_job_config_no_triggers_default(self):
        config = JobConfig(
            name="test",
            components=[
                {"id": "A", "type": "file_input_delimited", "config": {}},
            ],
            flows=[],
        )
        assert config.triggers == []

    def test_job_config_with_triggers(self):
        config = JobConfig(
            name="test",
            components=[
                {"id": "A", "type": "file_input_delimited", "config": {}},
                {"id": "B", "type": "file_output_delimited", "config": {}},
            ],
            flows=[],
            triggers=[
                {"source": "A", "target": "B", "type": "on_success"},
            ],
        )
        assert len(config.triggers) == 1
        assert config.triggers[0].type == TriggerType.ON_SUCCESS

    def test_job_config_with_multiple_trigger_types(self):
        config = JobConfig(
            name="test",
            components=[
                {"id": "A", "type": "file_input_delimited", "config": {}},
                {"id": "B", "type": "file_output_delimited", "config": {}},
                {"id": "C", "type": "python_code", "config": {}},
            ],
            flows=[],
            triggers=[
                {"source": "A", "target": "B", "type": "on_success"},
                {"source": "A", "target": "C", "type": "on_failure"},
            ],
        )
        assert len(config.triggers) == 2
        assert config.triggers[0].type == TriggerType.ON_SUCCESS
        assert config.triggers[1].type == TriggerType.ON_FAILURE

    def test_job_config_triggers_from_json_roundtrip(self):
        raw = {
            "name": "test",
            "components": [{"id": "A", "type": "x", "config": {}}],
            "flows": [],
            "triggers": [
                {"source": "A", "target": "B", "type": "conditional",
                 "condition": "${context.env} == 'PROD'"},
            ],
        }
        config = JobConfig(**raw)
        assert config.triggers[0].condition == "${context.env} == 'PROD'"

