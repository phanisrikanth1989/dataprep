"""Tests for ExecutionPlan -- DAG construction, topological sort, validation, cross-subjob flow metadata.

Covers: EXEC-03 (execution plan DAG), EXEC-07 (validation),
D-08 (RunIf not unreachable), D-10 (streaming metadata).
"""
import json
import logging
import os
import pytest

from src.v1.engine.execution_plan import ExecutionPlan, SubjobPlan, StreamingMetadata
from src.v1.engine.exceptions import ConfigurationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plan(components, flows=None, triggers=None, subjobs=None):
    """Create an ExecutionPlan from minimal component/flow/trigger/subjob specs."""
    return ExecutionPlan(
        components=components,
        flows=flows or [],
        triggers=triggers or [],
        subjobs=subjobs,
    )


# ---------------------------------------------------------------------------
# 1. Topological sort within subjobs
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSubjobTopologicalSort:
    """Test topological ordering of components within a single subjob."""

    def test_single_component_subjob(self):
        """Single component in subjob -> order is [comp_id]."""
        plan = _make_plan(
            components=[{"id": "A", "type": "LogRow"}],
            subjobs={"s1": ["A"]},
        )
        sp = plan.get_subjob_plan("s1")
        assert sp.component_ids == ["A"]

    def test_two_components_with_flow(self):
        """A->B flow -> topological order is [A, B]."""
        plan = _make_plan(
            components=[{"id": "A", "type": "FileInputDelimited"}, {"id": "B", "type": "LogRow"}],
            flows=[{"name": "f1", "from": "A", "to": "B", "type": "flow"}],
            subjobs={"s1": ["A", "B"]},
        )
        sp = plan.get_subjob_plan("s1")
        assert sp.component_ids == ["A", "B"]

    def test_three_component_chain(self):
        """A->B->C flows -> order is [A, B, C]."""
        plan = _make_plan(
            components=[
                {"id": "A", "type": "FileInputDelimited"},
                {"id": "B", "type": "FilterRows"},
                {"id": "C", "type": "LogRow"},
            ],
            flows=[
                {"name": "f1", "from": "A", "to": "B", "type": "flow"},
                {"name": "f2", "from": "B", "to": "C", "type": "flow"},
            ],
            subjobs={"s1": ["A", "B", "C"]},
        )
        sp = plan.get_subjob_plan("s1")
        assert sp.component_ids == ["A", "B", "C"]

    def test_diamond_dependency(self):
        """A->B, A->C, B->D, C->D -> A first, D last, B/C in middle."""
        plan = _make_plan(
            components=[
                {"id": "A", "type": "FileInputDelimited"},
                {"id": "B", "type": "FilterRows"},
                {"id": "C", "type": "FilterRows"},
                {"id": "D", "type": "LogRow"},
            ],
            flows=[
                {"name": "f1", "from": "A", "to": "B", "type": "flow"},
                {"name": "f2", "from": "A", "to": "C", "type": "flow"},
                {"name": "f3", "from": "B", "to": "D", "type": "flow"},
                {"name": "f4", "from": "C", "to": "D", "type": "flow"},
            ],
            subjobs={"s1": ["A", "B", "C", "D"]},
        )
        sp = plan.get_subjob_plan("s1")
        assert sp.component_ids[0] == "A"
        assert sp.component_ids[-1] == "D"
        assert set(sp.component_ids[1:3]) == {"B", "C"}

    def test_no_internal_flows(self):
        """2 components, flow goes to different subjob -> both present in subjob, any order valid."""
        plan = _make_plan(
            components=[
                {"id": "A", "type": "FileInputDelimited"},
                {"id": "B", "type": "LogRow"},
                {"id": "C", "type": "FilterRows"},
            ],
            flows=[
                {"name": "f1", "from": "A", "to": "C", "type": "flow"},
            ],
            subjobs={"s1": ["A", "B"], "s2": ["C"]},
        )
        sp = plan.get_subjob_plan("s1")
        assert set(sp.component_ids) == {"A", "B"}


# ---------------------------------------------------------------------------
# 2. Subjob ordering
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSubjobOrdering:
    """Test initial vs triggered subjob identification."""

    def test_no_triggers_all_initial(self):
        """2 subjobs, no triggers -> both in initial_subjobs."""
        plan = _make_plan(
            components=[
                {"id": "A", "type": "X"},
                {"id": "B", "type": "Y"},
            ],
            subjobs={"s1": ["A"], "s2": ["B"]},
        )
        assert set(plan.initial_subjobs) == {"s1", "s2"}

    def test_on_subjob_ok_chain(self):
        """subjob_1 -> subjob_2 via OnSubjobOk -> only subjob with A is initial."""
        plan = _make_plan(
            components=[
                {"id": "A", "type": "X"},
                {"id": "B", "type": "Y"},
            ],
            triggers=[
                {"type": "OnSubjobOk", "from": "A", "to": "B"},
            ],
            subjobs={"s1": ["A"], "s2": ["B"]},
        )
        assert plan.initial_subjobs == ["s1"]

    def test_three_subjob_chain(self):
        """s1 -> s2 -> s3 via OnSubjobOk -> only s1 is initial."""
        plan = _make_plan(
            components=[
                {"id": "A", "type": "X"},
                {"id": "B", "type": "Y"},
                {"id": "C", "type": "Z"},
            ],
            triggers=[
                {"type": "OnSubjobOk", "from": "A", "to": "B"},
                {"type": "OnSubjobOk", "from": "B", "to": "C"},
            ],
            subjobs={"s1": ["A"], "s2": ["B"], "s3": ["C"]},
        )
        assert plan.initial_subjobs == ["s1"]

    def test_on_component_ok_trigger(self):
        """s1 component triggers s2 component via OnComponentOk -> s1 initial, s2 triggered."""
        plan = _make_plan(
            components=[
                {"id": "A", "type": "X"},
                {"id": "B", "type": "Y"},
                {"id": "C", "type": "Z"},
            ],
            flows=[{"name": "f1", "from": "A", "to": "B", "type": "flow"}],
            triggers=[
                {"type": "OnComponentOk", "from": "B", "to": "C"},
            ],
            subjobs={"s1": ["A", "B"], "s2": ["C"]},
        )
        assert plan.initial_subjobs == ["s1"]

    def test_mixed_trigger_types(self):
        """OnSubjobOk and OnComponentOk triggers -> correct initial set."""
        plan = _make_plan(
            components=[
                {"id": "A", "type": "X"},
                {"id": "B", "type": "Y"},
                {"id": "C", "type": "Z"},
                {"id": "D", "type": "W"},
            ],
            triggers=[
                {"type": "OnSubjobOk", "from": "A", "to": "B"},
                {"type": "OnComponentOk", "from": "B", "to": "C"},
            ],
            subjobs={"s1": ["A"], "s2": ["B"], "s3": ["C"], "s4": ["D"]},
        )
        # s1 and s4 are initial (s4 has no trigger pointing to it)
        assert set(plan.initial_subjobs) == {"s1", "s4"}


# ---------------------------------------------------------------------------
# 3. Graph validation
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGraphValidation:
    """Test validate() for unreachable subjobs and cycles."""

    def test_valid_graph_no_error(self):
        """Well-connected graph -> validate() succeeds."""
        plan = _make_plan(
            components=[
                {"id": "A", "type": "X"},
                {"id": "B", "type": "Y"},
            ],
            triggers=[
                {"type": "OnSubjobOk", "from": "A", "to": "B"},
            ],
            subjobs={"s1": ["A"], "s2": ["B"]},
        )
        plan.validate()  # Should not raise

    def test_unreachable_subjob_raises(self):
        """Subjobs forming a disconnected trigger cycle are unreachable -> ConfigurationError.

        s3 and s4 trigger each other (D->C, C->D) but neither is initial
        nor reachable from s1. They form a disconnected triggered cluster.
        """
        plan_unreachable = _make_plan(
            components=[
                {"id": "A", "type": "X"},
                {"id": "B", "type": "Y"},
                {"id": "C", "type": "Z"},
                {"id": "D", "type": "W"},
            ],
            triggers=[
                {"type": "OnSubjobOk", "from": "A", "to": "B"},
                {"type": "OnSubjobOk", "from": "D", "to": "C"},
                {"type": "OnSubjobOk", "from": "C", "to": "D"},
            ],
            subjobs={"s1": ["A"], "s2": ["B"], "s3": ["C"], "s4": ["D"]},
        )
        with pytest.raises(ConfigurationError, match="[Uu]nreachable"):
            plan_unreachable.validate()

    def test_runif_target_not_flagged(self):
        """Subjob targeted by RunIf -> validate() succeeds (D-08)."""
        plan = _make_plan(
            components=[
                {"id": "A", "type": "X"},
                {"id": "B", "type": "Y"},
                {"id": "C", "type": "Z"},
            ],
            triggers=[
                {"type": "OnSubjobOk", "from": "A", "to": "B"},
                {"type": "RunIf", "from": "A", "to": "C"},
            ],
            subjobs={"s1": ["A"], "s2": ["B"], "s3": ["C"]},
        )
        # s3 is targeted by RunIf only, no regular trigger chain reaches it,
        # but it must NOT be flagged unreachable per D-08
        plan.validate()  # Should not raise

    def test_cycle_detection(self):
        """Circular flow A->B->A -> ConfigurationError with cycle info."""
        with pytest.raises(ConfigurationError, match="[Cc]ycle"):
            _make_plan(
                components=[
                    {"id": "A", "type": "X"},
                    {"id": "B", "type": "Y"},
                ],
                flows=[
                    {"name": "f1", "from": "A", "to": "B", "type": "flow"},
                    {"name": "f2", "from": "B", "to": "A", "type": "flow"},
                ],
                subjobs={"s1": ["A", "B"]},
            )

    def test_all_components_reachable_via_triggers(self):
        """Complex graph with branches -> validate() OK."""
        plan = _make_plan(
            components=[
                {"id": "A", "type": "X"},
                {"id": "B", "type": "Y"},
                {"id": "C", "type": "Z"},
                {"id": "D", "type": "W"},
                {"id": "E", "type": "V"},
            ],
            triggers=[
                {"type": "OnSubjobOk", "from": "A", "to": "B"},
                {"type": "OnSubjobOk", "from": "A", "to": "C"},
                {"type": "OnSubjobOk", "from": "B", "to": "D"},
                {"type": "OnComponentOk", "from": "C", "to": "E"},
            ],
            subjobs={"s1": ["A"], "s2": ["B"], "s3": ["C"], "s4": ["D"], "s5": ["E"]},
        )
        plan.validate()  # Should not raise


# ---------------------------------------------------------------------------
# 4. Streaming metadata
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestStreamingMetadata:
    """Test streaming metadata marking for component types."""

    def test_sort_requires_full_data(self):
        """SortRow -> requires_full_data=True."""
        plan = _make_plan(
            components=[{"id": "A", "type": "SortRow"}],
            subjobs={"s1": ["A"]},
        )
        meta = plan.get_streaming_metadata("A")
        assert meta.requires_full_data is True
        assert meta.streamable is False

    def test_aggregate_requires_full_data(self):
        """AggregateRow -> requires_full_data=True."""
        plan = _make_plan(
            components=[{"id": "A", "type": "AggregateRow"}],
            subjobs={"s1": ["A"]},
        )
        meta = plan.get_streaming_metadata("A")
        assert meta.requires_full_data is True
        assert meta.streamable is False

    def test_default_streamable(self):
        """Unknown type -> streamable=True, requires_full_data=False."""
        plan = _make_plan(
            components=[{"id": "A", "type": "LogRow"}],
            subjobs={"s1": ["A"]},
        )
        meta = plan.get_streaming_metadata("A")
        assert meta.requires_full_data is False
        assert meta.streamable is True


# ---------------------------------------------------------------------------
# 5. Auto-detection fallback
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestAutoDetectionFallback:
    """Test auto-detection when subjobs dict is missing."""

    def test_no_subjobs_dict_auto_detects(self):
        """Pass subjobs=None, components connected by flows -> auto-detected subjobs."""
        plan = _make_plan(
            components=[
                {"id": "A", "type": "X"},
                {"id": "B", "type": "Y"},
                {"id": "C", "type": "Z"},
            ],
            flows=[
                {"name": "f1", "from": "A", "to": "B", "type": "flow"},
            ],
            subjobs=None,
        )
        # A and B should be in same subjob, C in different
        comp_to_sub = plan.component_to_subjob
        assert comp_to_sub["A"] == comp_to_sub["B"]
        assert comp_to_sub["C"] != comp_to_sub["A"]

    def test_disconnected_components_separate_subjobs(self):
        """Components with no flows between them -> separate subjobs."""
        plan = _make_plan(
            components=[
                {"id": "A", "type": "X"},
                {"id": "B", "type": "Y"},
            ],
            flows=[],
            subjobs=None,
        )
        comp_to_sub = plan.component_to_subjob
        assert comp_to_sub["A"] != comp_to_sub["B"]

    def test_auto_detection_logs_info(self, caplog):
        """Pass subjobs=None -> verify INFO log about auto-detection."""
        with caplog.at_level(logging.INFO, logger="src.v1.engine.execution_plan"):
            _make_plan(
                components=[{"id": "A", "type": "X"}],
                subjobs=None,
            )
        assert any("auto-detecting subjob boundaries" in msg.lower() for msg in caplog.messages)


# ---------------------------------------------------------------------------
# 6. Cross-subjob flows
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCrossSubjobFlows:
    """Test cross-subjob flow detection and consumer tracking."""

    def test_no_cross_subjob_flows(self):
        """All flows within same subjob -> get_cross_subjob_flows() returns empty."""
        plan = _make_plan(
            components=[
                {"id": "A", "type": "X"},
                {"id": "B", "type": "Y"},
            ],
            flows=[{"name": "f1", "from": "A", "to": "B", "type": "flow"}],
            subjobs={"s1": ["A", "B"]},
        )
        assert plan.get_cross_subjob_flows() == []

    def test_cross_subjob_flow_detected(self):
        """Flow from comp in subjob_1 to comp in subjob_2 -> detected."""
        plan = _make_plan(
            components=[
                {"id": "A", "type": "X"},
                {"id": "B", "type": "Y"},
            ],
            flows=[{"name": "cross_flow", "from": "A", "to": "B", "type": "flow"}],
            subjobs={"s1": ["A"], "s2": ["B"]},
        )
        cross = plan.get_cross_subjob_flows()
        assert len(cross) == 1
        assert cross[0]["name"] == "cross_flow"

    def test_get_flow_consumers(self):
        """Flow 'row1' consumed by comp B -> get_flow_consumers('row1') returns {'B'}."""
        plan = _make_plan(
            components=[
                {"id": "A", "type": "X"},
                {"id": "B", "type": "Y"},
            ],
            flows=[{"name": "row1", "from": "A", "to": "B", "type": "flow"}],
            subjobs={"s1": ["A", "B"]},
        )
        consumers = plan.get_flow_consumers("row1")
        assert consumers == {"B"}


# ---------------------------------------------------------------------------
# 7. Real job config integration tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRealJobConfig:
    """Test with actual converted job config files."""

    @pytest.fixture
    def json_dir(self):
        """Path to converted JSON test fixtures."""
        return os.path.join(
            os.path.dirname(__file__),
            "..", "..", "talend_xml_samples", "converted_jsons",
        )

    def test_file_row_count_job(self, json_dir):
        """Job_tFileRowCount: 3 subjobs, subjob_2 is initial, topo order correct."""
        config_path = os.path.join(json_dir, "Job_tFileRowCount_0.1.json")
        with open(config_path) as f:
            config = json.load(f)

        plan = ExecutionPlan(
            components=config["components"],
            flows=config["flows"],
            triggers=config["triggers"],
            subjobs=config.get("subjobs"),
        )
        plan.validate()

        assert len(plan.all_subjob_ids) == 3

        # subjob_2 contains tFileInputDelimited_1 which is the trigger source for
        # the chain: subjob_2 -> subjob_1 -> subjob_3
        assert "subjob_2" in plan.initial_subjobs

        # Within subjob_2, topo order is tFileInputDelimited_1 then tLogRow_1
        sp2 = plan.get_subjob_plan("subjob_2")
        assert sp2.component_ids == ["tFileInputDelimited_1", "tLogRow_1"]

    def test_context_load_job(self, json_dir):
        """Job_tContextLoad: 2 subjobs, OnComponentOk trigger, subjob_1 initial."""
        config_path = os.path.join(json_dir, "Job_tContextLoad_0.1.json")
        with open(config_path) as f:
            config = json.load(f)

        plan = ExecutionPlan(
            components=config["components"],
            flows=config["flows"],
            triggers=config["triggers"],
            subjobs=config.get("subjobs"),
        )
        plan.validate()

        assert len(plan.all_subjob_ids) == 2
        assert plan.initial_subjobs == ["subjob_1"]

        # OnComponentOk from tContextLoad_1 to tJava_1 should be recognized
        edges = plan.get_triggered_subjobs("OnComponentOk", "tContextLoad_1")
        assert len(edges) == 1
        assert edges[0].to_component == "tJava_1"
