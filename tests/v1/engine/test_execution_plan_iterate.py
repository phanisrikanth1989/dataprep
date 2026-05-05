"""Tests for ExecutionPlan iterate body subgraph BFS + nested iterate detection (Phase 10-02).

Covers _build_iterate_body_plan, _detect_nested_iterate, get_iterate_body_plan,
and the _ITERATE_TYPES constant.
"""
import pytest

from src.v1.engine.execution_plan import ExecutionPlan, SubjobPlan
from src.v1.engine.exceptions import ConfigurationError


def _make_plan(components, flows=None, triggers=None, subjobs=None):
    """Create ExecutionPlan from minimal specs."""
    return ExecutionPlan(
        components=components,
        flows=flows or [],
        triggers=triggers or [],
        subjobs=subjobs,
    )


# ---------------------------------------------------------------------------
# TestBodyBFSBasic
# ---------------------------------------------------------------------------

class TestBodyBFSBasic:
    """Body subgraph BFS builds correct intra-subjob component set."""

    def test_body_bfs_intra_subjob_two_body_components(self):
        """iter -> A (flow) -> B (flow); body = [A, B], iterate source NOT in body."""
        plan = _make_plan(
            components=[
                {"id": "iter1", "type": "tFileList"},
                {"id": "A", "type": "LogRow"},
                {"id": "B", "type": "LogRow"},
            ],
            flows=[
                {"name": "iter_iter1_A", "from": "iter1", "to": "A", "type": "iterate"},
                {"name": "flow_A_to_B", "from": "A", "to": "B", "type": "flow"},
            ],
            subjobs={"s1": ["iter1", "A", "B"]},
        )
        body = plan.get_iterate_body_plan("iter1")
        assert "iter1" not in body.component_ids
        assert "A" in body.component_ids
        assert "B" in body.component_ids
        # Topological order: A before B
        assert body.component_ids.index("A") < body.component_ids.index("B")

    def test_body_bfs_intra_subjob_two_branches(self):
        """iter -> A; A -> B; A -> C. Body = {A, B, C}."""
        plan = _make_plan(
            components=[
                {"id": "iter1", "type": "tFileList"},
                {"id": "A", "type": "LogRow"},
                {"id": "B", "type": "LogRow"},
                {"id": "C", "type": "LogRow"},
            ],
            flows=[
                {"name": "iter_iter1_A", "from": "iter1", "to": "A", "type": "iterate"},
                {"name": "flow_A_to_B", "from": "A", "to": "B", "type": "flow"},
                {"name": "flow_A_to_C", "from": "A", "to": "C", "type": "flow"},
            ],
            subjobs={"s1": ["iter1", "A", "B", "C"]},
        )
        body = plan.get_iterate_body_plan("iter1")
        assert set(body.component_ids) == {"A", "B", "C"}
        assert "iter1" not in body.component_set

    def test_body_bfs_iterate_source_not_in_body(self):
        """iter source is never included in its own body."""
        plan = _make_plan(
            components=[
                {"id": "iter1", "type": "FlowToIterate"},
                {"id": "body1", "type": "LogRow"},
            ],
            flows=[
                {"name": "iter_iter1_body1", "from": "iter1", "to": "body1", "type": "iterate"},
            ],
            subjobs={"s1": ["iter1", "body1"]},
        )
        body = plan.get_iterate_body_plan("iter1")
        assert "iter1" not in body.component_set
        assert "body1" in body.component_set

    def test_body_bfs_empty_when_no_iterate_target(self):
        """Iterate source with no ITERATE-typed outgoing flow -> empty body plan."""
        plan = _make_plan(
            components=[
                {"id": "iter1", "type": "tFileList"},
            ],
            flows=[],
            subjobs={"s1": ["iter1"]},
        )
        body = plan.get_iterate_body_plan("iter1")
        assert body.component_ids == []
        assert body.component_set == frozenset()

    def test_body_bfs_single_component_body(self):
        """Single body component scenario (iter -> A only, no further chain)."""
        plan = _make_plan(
            components=[
                {"id": "iter1", "type": "tFlowToIterate"},
                {"id": "A", "type": "LogRow"},
            ],
            flows=[
                {"name": "iter_iter1_A", "from": "iter1", "to": "A", "type": "iterate"},
            ],
            subjobs={"s1": ["iter1", "A"]},
        )
        body = plan.get_iterate_body_plan("iter1")
        assert body.component_ids == ["A"]


# ---------------------------------------------------------------------------
# TestBodyBFSTriggerFollowing
# ---------------------------------------------------------------------------

class TestBodyBFSTriggerFollowing:
    """Body BFS follows outbound trigger edges from body components."""

    def test_body_bfs_follows_outbound_triggers(self):
        """A is in body; A has OnComponentOk trigger to D in same subjob; D included in body."""
        plan = _make_plan(
            components=[
                {"id": "iter1", "type": "tFileList"},
                {"id": "A", "type": "LogRow"},
                {"id": "D", "type": "LogRow"},
            ],
            flows=[
                {"name": "iter_iter1_A", "from": "iter1", "to": "A", "type": "iterate"},
            ],
            triggers=[
                {"type": "OnComponentOk", "from": "A", "to": "D"},
            ],
            subjobs={"s1": ["iter1", "A", "D"]},
        )
        body = plan.get_iterate_body_plan("iter1")
        assert "D" in body.component_set
        assert "A" in body.component_set

    def test_body_bfs_excludes_cross_subjob_via_trigger(self):
        """Trigger from body A to component E in a different subjob; E excluded from body."""
        plan = _make_plan(
            components=[
                {"id": "iter1", "type": "tFileList"},
                {"id": "A", "type": "LogRow"},
                {"id": "E", "type": "LogRow"},
            ],
            flows=[
                {"name": "iter_iter1_A", "from": "iter1", "to": "A", "type": "iterate"},
            ],
            triggers=[
                {"type": "OnComponentOk", "from": "A", "to": "E"},
            ],
            subjobs={"s1": ["iter1", "A"], "s2": ["E"]},
        )
        body = plan.get_iterate_body_plan("iter1")
        # E is in s2, not s1 -- excluded from body
        assert "E" not in body.component_set

    def test_body_bfs_excludes_cross_subjob_via_flow(self):
        """D is in subjob_2 (different from iterate source's subjob_1); body excludes D."""
        plan = _make_plan(
            components=[
                {"id": "iter1", "type": "FileList"},
                {"id": "A", "type": "LogRow"},
                {"id": "D", "type": "LogRow"},
            ],
            flows=[
                {"name": "iter_iter1_A", "from": "iter1", "to": "A", "type": "iterate"},
                {"name": "flow_A_to_D", "from": "A", "to": "D", "type": "flow"},
            ],
            subjobs={"s1": ["iter1", "A"], "s2": ["D"]},
        )
        body = plan.get_iterate_body_plan("iter1")
        assert "D" not in body.component_set
        assert "A" in body.component_set


# ---------------------------------------------------------------------------
# TestNestedIterateDetection
# ---------------------------------------------------------------------------

class TestNestedIterateDetection:
    """Nested iterate detection raises ConfigurationError naming both iterate IDs."""

    def test_nested_iterate_raises_configuration_error(self):
        """Body of iter_1 includes another iterate component iter_2; raises ConfigurationError."""
        with pytest.raises(ConfigurationError) as exc_info:
            _make_plan(
                components=[
                    {"id": "iter1", "type": "tFileList"},
                    {"id": "iter2", "type": "tFlowToIterate"},
                    {"id": "A", "type": "LogRow"},
                ],
                flows=[
                    {"name": "iter_iter1_iter2", "from": "iter1", "to": "iter2", "type": "iterate"},
                    {"name": "iter_iter2_A", "from": "iter2", "to": "A", "type": "iterate"},
                ],
                subjobs={"s1": ["iter1", "iter2", "A"]},
            )
        msg = str(exc_info.value)
        assert "iter1" in msg
        assert "iter2" in msg
        assert "nested" in msg.lower()

    def test_no_iterate_components_no_body_plans(self):
        """No iterate components in job -> _iterate_body_plans is empty dict."""
        plan = _make_plan(
            components=[
                {"id": "A", "type": "LogRow"},
                {"id": "B", "type": "FilterRows"},
            ],
            flows=[
                {"name": "f1", "from": "A", "to": "B", "type": "flow"},
            ],
            subjobs={"s1": ["A", "B"]},
        )
        # No iterate body plans should exist
        with pytest.raises(KeyError):
            plan.get_iterate_body_plan("A")

    def test_nested_iterate_with_filelist_types(self):
        """Two FileList types as nested iterates also raises."""
        with pytest.raises(ConfigurationError) as exc_info:
            _make_plan(
                components=[
                    {"id": "fl1", "type": "FileList"},
                    {"id": "fl2", "type": "tFileList"},
                ],
                flows=[
                    {"name": "iter_fl1_fl2", "from": "fl1", "to": "fl2", "type": "iterate"},
                ],
                subjobs={"s1": ["fl1", "fl2"]},
            )
        assert "fl1" in str(exc_info.value)
        assert "fl2" in str(exc_info.value)


# ---------------------------------------------------------------------------
# TestGetIterateBodyPlanAPI
# ---------------------------------------------------------------------------

class TestGetIterateBodyPlanAPI:
    """Public get_iterate_body_plan API returns valid SubjobPlan."""

    def test_get_iterate_body_plan_returns_subjob_plan(self):
        """get_iterate_body_plan returns SubjobPlan with topo-sorted component_ids."""
        plan = _make_plan(
            components=[
                {"id": "iter1", "type": "tFileList"},
                {"id": "A", "type": "LogRow"},
                {"id": "B", "type": "LogRow"},
            ],
            flows=[
                {"name": "iter_iter1_A", "from": "iter1", "to": "A", "type": "iterate"},
                {"name": "flow_A_to_B", "from": "A", "to": "B", "type": "flow"},
            ],
            subjobs={"s1": ["iter1", "A", "B"]},
        )
        body = plan.get_iterate_body_plan("iter1")
        assert isinstance(body, SubjobPlan)
        assert body.subjob_id == "iter1_body"
        assert isinstance(body.component_ids, list)
        assert isinstance(body.component_set, frozenset)

    def test_get_iterate_body_plan_raises_key_error_for_non_iterate(self):
        """KeyError raised for non-iterate component ID."""
        plan = _make_plan(
            components=[{"id": "A", "type": "LogRow"}],
            subjobs={"s1": ["A"]},
        )
        with pytest.raises(KeyError):
            plan.get_iterate_body_plan("A")

    def test_iterate_body_plan_subjob_id_format(self):
        """Body plan subjob_id is '{iter_id}_body'."""
        plan = _make_plan(
            components=[
                {"id": "myIter", "type": "FlowToIterate"},
                {"id": "B", "type": "LogRow"},
            ],
            flows=[
                {"name": "iter_myIter_B", "from": "myIter", "to": "B", "type": "iterate"},
            ],
            subjobs={"s1": ["myIter", "B"]},
        )
        body = plan.get_iterate_body_plan("myIter")
        assert body.subjob_id == "myIter_body"

    def test_all_four_iterate_types_recognized(self):
        """FlowToIterate, tFlowToIterate, FileList, tFileList are all recognized."""
        for comp_type in ("FlowToIterate", "tFlowToIterate", "FileList", "tFileList"):
            plan = _make_plan(
                components=[
                    {"id": "iter1", "type": comp_type},
                    {"id": "body1", "type": "LogRow"},
                ],
                flows=[
                    {"name": "iter_iter1_body1", "from": "iter1", "to": "body1", "type": "iterate"},
                ],
                subjobs={"s1": ["iter1", "body1"]},
            )
            body = plan.get_iterate_body_plan("iter1")
            assert "body1" in body.component_set, f"Failed for type {comp_type}"
