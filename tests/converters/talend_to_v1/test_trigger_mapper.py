from src.converters.talend_to_v1.components.base import TalendConnection
from src.converters.talend_to_v1.trigger_mapper import map_triggers


def _conn(name, source, target, connector_type, condition=None):
    return TalendConnection(
        name=name, source=source, target=target,
        connector_type=connector_type, condition=condition,
    )


class TestTriggerTypeMapping:
    def test_subjob_ok(self):
        conns = [_conn("t1", "A", "B", "SUBJOB_OK")]
        result = map_triggers(conns, {"A", "B"})
        assert len(result.triggers) == 1
        assert result.triggers[0]["type"] == "OnSubjobOk"

    def test_subjob_error(self):
        conns = [_conn("t1", "A", "B", "SUBJOB_ERROR")]
        result = map_triggers(conns, {"A", "B"})
        assert result.triggers[0]["type"] == "OnSubjobError"

    def test_component_ok(self):
        conns = [_conn("t1", "A", "B", "COMPONENT_OK")]
        result = map_triggers(conns, {"A", "B"})
        assert result.triggers[0]["type"] == "OnComponentOk"

    def test_component_error(self):
        conns = [_conn("t1", "A", "B", "COMPONENT_ERROR")]
        result = map_triggers(conns, {"A", "B"})
        assert result.triggers[0]["type"] == "OnComponentError"

    def test_run_if(self):
        conns = [_conn("t1", "A", "B", "RUN_IF", condition="x > 0")]
        result = map_triggers(conns, {"A", "B"})
        assert result.triggers[0]["type"] == "RunIf"
        assert "condition" in result.triggers[0]

    def test_run_if_flags_for_review(self):
        conns = [_conn("t1", "A", "B", "RUN_IF", condition="x > 0")]
        result = map_triggers(conns, {"A", "B"})
        assert len(result.needs_review) == 1
        assert result.needs_review[0]["field"] == "trigger_condition"


class TestPrejobHandling:
    def test_prejob_forced_to_on_component_ok(self):
        conns = [_conn("t1", "tPrejob_1", "B", "SUBJOB_OK")]
        result = map_triggers(conns, {"tPrejob_1", "B"})
        assert result.triggers[0]["type"] == "OnComponentOk"

    def test_non_prejob_not_affected(self):
        conns = [_conn("t1", "A", "B", "SUBJOB_OK")]
        result = map_triggers(conns, {"A", "B"})
        assert result.triggers[0]["type"] == "OnSubjobOk"


class TestFiltering:
    def test_skips_non_trigger_connections(self):
        conns = [
            _conn("r1", "A", "B", "FLOW"),
            _conn("t1", "A", "B", "SUBJOB_OK"),
        ]
        result = map_triggers(conns, {"A", "B"})
        assert len(result.triggers) == 1

    def test_filters_missing_source(self):
        conns = [_conn("t1", "MISSING", "B", "SUBJOB_OK")]
        result = map_triggers(conns, {"B"})
        assert len(result.triggers) == 0

    def test_filters_missing_target(self):
        conns = [_conn("t1", "A", "MISSING", "SUBJOB_OK")]
        result = map_triggers(conns, {"A"})
        assert len(result.triggers) == 0

    def test_skips_empty_source_or_target(self):
        conns = [_conn("t1", "", "B", "SUBJOB_OK")]
        result = map_triggers(conns, {"", "B"})
        assert len(result.triggers) == 0


class TestTriggerStructure:
    def test_trigger_has_required_keys(self):
        conns = [_conn("t1", "A", "B", "SUBJOB_OK")]
        result = map_triggers(conns, {"A", "B"})
        trigger = result.triggers[0]
        assert "type" in trigger
        assert "from" in trigger
        assert "to" in trigger
        assert trigger["from"] == "A"
        assert trigger["to"] == "B"
