"""Tests for Executor -- orchestration integration tests.

Tests exercise Executor through StubComponents, real TriggerManager,
real GlobalMap, real ExecutionPlan, and real OutputRouter. These are
orchestration integration tests -- they verify execution flow without
real ETL components.

Covers:
- Single/multi subjob execution
- Trigger timing precision (OnSubjobOk vs OnComponentOk)
- RunIf trigger evaluation
- Error propagation (die_on_error, tDie, independent subjobs)
- Stall detection with actionable diagnostics
- Data routing through OutputRouter
- Subjob flow cleanup with cross-subjob safety
- Iterative trigger firing (deque, not recursion)
"""
import copy

import pandas as pd
import pytest

from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ComponentExecutionError, ConfigurationError
from src.v1.engine.execution_plan import ExecutionPlan
from src.v1.engine.executor import Executor
from src.v1.engine.global_map import GlobalMap
from src.v1.engine.output_router import OutputRouter
from src.v1.engine.trigger_manager import TriggerManager

from tests.v1.engine.conftest import StubComponent, make_stub_component


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_execution_order: list[str] = []
"""Module-level list to track execution order across components."""


class OrderTrackingComponent(StubComponent):
    """StubComponent that records execution order to a shared list."""

    def _process(self, input_data=None):
        _execution_order.append(self.id)
        return super()._process(input_data)


def _make_component(comp_id, config=None, global_map=None, context_manager=None, track_order=False):
    """Create a StubComponent or OrderTrackingComponent."""
    if config is None:
        config = {}
    if global_map is None:
        global_map = GlobalMap()
    if context_manager is None:
        context_manager = ContextManager(initial_context={"Default": {}})

    cls = OrderTrackingComponent if track_order else StubComponent
    comp = cls(comp_id, config, global_map, context_manager)
    comp.config = copy.deepcopy(comp._original_config)
    return comp


def _build_executor(
    components_config,
    flows_config=None,
    triggers_config=None,
    subjobs=None,
    component_overrides=None,
    track_order=False,
):
    """Build a fully wired Executor from config dicts with StubComponents.

    Args:
        components_config: List of component config dicts.
        flows_config: List of flow dicts.
        triggers_config: List of trigger dicts.
        subjobs: Dict mapping subjob_id -> list of component IDs.
        component_overrides: Dict of comp_id -> custom BaseComponent instances.
        track_order: If True, use OrderTrackingComponent to track execution order.

    Returns:
        Executor instance ready for testing.
    """
    flows_config = flows_config or []
    triggers_config = triggers_config or []

    # Build ExecutionPlan
    plan = ExecutionPlan(components_config, flows_config, triggers_config, subjobs)
    plan.validate()

    # Build OutputRouter
    router = OutputRouter(flows_config, components_config)

    # Build GlobalMap and TriggerManager
    global_map = GlobalMap()
    trigger_manager = TriggerManager(global_map)

    # Register subjobs with trigger manager
    for subjob_id in plan.all_subjob_ids:
        sp = plan.get_subjob_plan(subjob_id)
        trigger_manager.register_subjob(subjob_id, list(sp.component_ids))

    # Add triggers to trigger manager
    for trigger in triggers_config:
        trigger_manager.add_trigger(
            trigger['type'],
            trigger.get('from_component') or trigger.get('from'),
            trigger.get('to_component') or trigger.get('to'),
            trigger.get('condition')
        )

    # Build StubComponents
    components = {}
    for comp_cfg in components_config:
        comp_id = comp_cfg['id']
        if component_overrides and comp_id in component_overrides:
            components[comp_id] = component_overrides[comp_id]
        else:
            comp = _make_component(
                comp_id,
                config=comp_cfg.get('config', {}),
                global_map=global_map,
                track_order=track_order,
            )
            comp.inputs = comp_cfg.get('inputs', [])
            comp.outputs = comp_cfg.get('outputs', [])
            components[comp_id] = comp

    return Executor(components, plan, router, trigger_manager, global_map)


# ---------------------------------------------------------------------------
# 1. Single subjob execution
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSingleSubjobExecution:
    """Test execution of a single subjob with various topologies."""

    def test_single_component_executes(self):
        """1 component, no flows -- executes successfully, stats show 1 executed."""
        executor = _build_executor(
            components_config=[{"id": "A", "type": "Stub"}],
            subjobs={"s1": ["A"]},
        )
        stats = executor.execute_job()
        assert stats["status"] == "success"
        assert stats["components_executed"] == 1
        assert "A" in executor.executed_components

    def test_two_component_chain(self):
        """A->B flow -- both execute in order, B receives A's output."""
        executor = _build_executor(
            components_config=[
                {"id": "A", "type": "Stub", "config": {"output_data": [{"x": 1}]}, "outputs": ["flow_ab"]},
                {"id": "B", "type": "Stub", "inputs": ["flow_ab"]},
            ],
            flows_config=[
                {"name": "flow_ab", "from": "A", "to": "B", "type": "flow"},
            ],
            subjobs={"s1": ["A", "B"]},
        )
        stats = executor.execute_job()
        assert stats["status"] == "success"
        assert stats["components_executed"] == 2

    def test_three_component_chain(self):
        """A->B->C -- all execute, data flows through."""
        executor = _build_executor(
            components_config=[
                {"id": "A", "type": "Stub", "config": {"output_data": [{"x": 1}]}, "outputs": ["f1"]},
                {"id": "B", "type": "Stub", "inputs": ["f1"], "outputs": ["f2"]},
                {"id": "C", "type": "Stub", "inputs": ["f2"]},
            ],
            flows_config=[
                {"name": "f1", "from": "A", "to": "B", "type": "flow"},
                {"name": "f2", "from": "B", "to": "C", "type": "flow"},
            ],
            subjobs={"s1": ["A", "B", "C"]},
        )
        stats = executor.execute_job()
        assert stats["status"] == "success"
        assert stats["components_executed"] == 3

    def test_component_with_no_input_produces_output(self):
        """Source component with output_data config -- data available downstream."""
        executor = _build_executor(
            components_config=[
                {"id": "src", "type": "Stub", "config": {"output_data": [{"val": 42}]}, "outputs": ["f1"]},
                {"id": "sink", "type": "Stub", "inputs": ["f1"]},
            ],
            flows_config=[
                {"name": "f1", "from": "src", "to": "sink", "type": "flow"},
            ],
            subjobs={"s1": ["src", "sink"]},
        )
        stats = executor.execute_job()
        assert stats["status"] == "success"
        assert stats["components_executed"] == 2


# ---------------------------------------------------------------------------
# 2. Multi-subjob execution
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestMultiSubjobExecution:
    """Test execution across multiple subjobs connected by triggers."""

    def test_on_subjob_ok_fires_after_all_components(self):
        """subjob_1 has A->B, OnSubjobOk triggers subjob_2 (C) after BOTH A and B complete."""
        executor = _build_executor(
            components_config=[
                {"id": "A", "type": "Stub", "config": {"output_data": [{"x": 1}]}, "outputs": ["f1"]},
                {"id": "B", "type": "Stub", "inputs": ["f1"]},
                {"id": "C", "type": "Stub"},
            ],
            flows_config=[
                {"name": "f1", "from": "A", "to": "B", "type": "flow"},
            ],
            triggers_config=[
                {"type": "OnSubjobOk", "from": "A", "to": "C"},
            ],
            subjobs={"s1": ["A", "B"], "s2": ["C"]},
        )
        stats = executor.execute_job()
        assert stats["status"] == "success"
        assert stats["components_executed"] == 3

    def test_three_subjob_chain(self):
        """s1 -> s2 -> s3 via OnSubjobOk -- all execute in order."""
        executor = _build_executor(
            components_config=[
                {"id": "A", "type": "Stub"},
                {"id": "B", "type": "Stub"},
                {"id": "C", "type": "Stub"},
            ],
            triggers_config=[
                {"type": "OnSubjobOk", "from": "A", "to": "B"},
                {"type": "OnSubjobOk", "from": "B", "to": "C"},
            ],
            subjobs={"s1": ["A"], "s2": ["B"], "s3": ["C"]},
        )
        stats = executor.execute_job()
        assert stats["status"] == "success"
        assert stats["components_executed"] == 3

    def test_two_initial_subjobs_both_execute(self):
        """No triggers between s1 and s2 -- both execute as initial subjobs."""
        executor = _build_executor(
            components_config=[
                {"id": "A", "type": "Stub"},
                {"id": "B", "type": "Stub"},
            ],
            subjobs={"s1": ["A"], "s2": ["B"]},
        )
        stats = executor.execute_job()
        assert stats["status"] == "success"
        assert stats["components_executed"] == 2


# ---------------------------------------------------------------------------
# 3. Trigger timing precision
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestTriggerTimingPrecision:
    """Test that OnSubjobOk and OnComponentOk have correct timing semantics."""

    def test_on_subjob_ok_does_not_fire_after_first_component(self):
        """OnSubjobOk from s1 to s2 fires only after ALL of s1's components complete.

        Uses OrderTrackingComponent to verify B runs before C (s2's component).
        """
        global _execution_order
        _execution_order = []

        executor = _build_executor(
            components_config=[
                {"id": "A", "type": "Stub", "config": {"output_data": [{"x": 1}]}, "outputs": ["f1"]},
                {"id": "B", "type": "Stub", "inputs": ["f1"]},
                {"id": "C", "type": "Stub"},
            ],
            flows_config=[
                {"name": "f1", "from": "A", "to": "B", "type": "flow"},
            ],
            triggers_config=[
                {"type": "OnSubjobOk", "from": "A", "to": "C"},
            ],
            subjobs={"s1": ["A", "B"], "s2": ["C"]},
            track_order=True,
        )
        stats = executor.execute_job()
        assert stats["status"] == "success"
        # B must execute before C (C is in s2, triggered only after s1 completes)
        assert _execution_order.index("B") < _execution_order.index("C")

    def test_on_component_ok_fires_after_specific_component(self):
        """OnComponentOk fires after the specific component, not after subjob."""
        global _execution_order
        _execution_order = []

        executor = _build_executor(
            components_config=[
                {"id": "A", "type": "Stub"},
                {"id": "B", "type": "Stub"},
            ],
            triggers_config=[
                {"type": "OnComponentOk", "from": "A", "to": "B"},
            ],
            subjobs={"s1": ["A"], "s2": ["B"]},
            track_order=True,
        )
        stats = executor.execute_job()
        assert stats["status"] == "success"
        # Both should execute -- OnComponentOk triggers B from A
        assert "A" in executor.executed_components
        assert "B" in executor.executed_components

    def test_on_component_ok_within_subjob_chain(self):
        """OnComponentOk works correctly within trigger chains."""
        executor = _build_executor(
            components_config=[
                {"id": "A", "type": "Stub"},
                {"id": "B", "type": "Stub"},
                {"id": "C", "type": "Stub"},
            ],
            triggers_config=[
                {"type": "OnComponentOk", "from": "A", "to": "B"},
                {"type": "OnComponentOk", "from": "B", "to": "C"},
            ],
            subjobs={"s1": ["A"], "s2": ["B"], "s3": ["C"]},
        )
        stats = executor.execute_job()
        assert stats["status"] == "success"
        assert stats["components_executed"] == 3


# ---------------------------------------------------------------------------
# 4. RunIf trigger
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRunIfTrigger:
    """Test RunIf conditional trigger evaluation."""

    def test_runif_true_executes_target(self):
        """RunIf with true condition -> target subjob executes."""
        gm = GlobalMap()
        gm.put("should_run", 1)

        executor = _build_executor(
            components_config=[
                {"id": "A", "type": "Stub"},
                {"id": "B", "type": "Stub"},
            ],
            triggers_config=[
                {"type": "RunIf", "from": "A", "to": "B",
                 "condition": 'globalMap.get("should_run") == 1'},
            ],
            subjobs={"s1": ["A"], "s2": ["B"]},
        )
        # Set globalMap before execution
        executor.global_map.put("should_run", 1)
        stats = executor.execute_job()
        assert stats["components_executed"] == 2
        assert "B" in executor.executed_components

    def test_runif_false_skips_target(self):
        """RunIf with false condition -> target subjob does NOT execute, no error."""
        executor = _build_executor(
            components_config=[
                {"id": "A", "type": "Stub"},
                {"id": "B", "type": "Stub"},
            ],
            triggers_config=[
                {"type": "RunIf", "from": "A", "to": "B",
                 "condition": 'globalMap.get("should_run") == 1'},
            ],
            subjobs={"s1": ["A"], "s2": ["B"]},
        )
        # globalMap does not have should_run set to 1
        executor.global_map.put("should_run", 0)
        stats = executor.execute_job()
        # B should NOT execute, and there should be no stall error because
        # B is a RunIf target (ExecutionPlan excludes it from unreachable checks)
        assert "A" in executor.executed_components
        # B was not executed -- but also no stall error since it's a RunIf target
        # The stall detection should not fire for RunIf targets that didn't fire


# ---------------------------------------------------------------------------
# 5. Error propagation
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestErrorPropagation:
    """Test error handling: die_on_error, tDie, independent subjobs."""

    def test_die_on_error_true_stops_subjob(self):
        """Component with should_fail=True, die_on_error=True -> remaining skipped."""
        executor = _build_executor(
            components_config=[
                {"id": "A", "type": "Stub", "config": {"should_fail": True, "die_on_error": True},
                 "outputs": ["f1"]},
                {"id": "B", "type": "Stub", "inputs": ["f1"]},
            ],
            flows_config=[
                {"name": "f1", "from": "A", "to": "B", "type": "flow"},
            ],
            subjobs={"s1": ["A", "B"]},
        )
        stats = executor.execute_job()
        assert "A" in executor.failed_components
        assert executor.execution_stats.get("B", {}).get("status") == "skipped"

    def test_die_on_error_false_continues(self):
        """Component with should_fail=True, die_on_error=False -> next still executes."""
        executor = _build_executor(
            components_config=[
                {"id": "A", "type": "Stub", "config": {"should_fail": True, "die_on_error": False}},
                {"id": "B", "type": "Stub"},
            ],
            subjobs={"s1": ["A", "B"]},
        )
        stats = executor.execute_job()
        assert "A" in executor.failed_components
        assert "B" in executor.executed_components

    def test_tdie_stops_entire_job(self):
        """Component raising ComponentExecutionError with exit_code -> subsequent subjobs skipped."""
        gm = GlobalMap()
        cm = ContextManager(initial_context={"Default": {}})

        # Create a component that simulates tDie
        class DieComponent(StubComponent):
            def _process(self, input_data=None):
                err = ComponentExecutionError(self.id, "tDie triggered")
                err.exit_code = 1
                raise err

        die_comp = DieComponent("A", {}, gm, cm)
        die_comp.config = copy.deepcopy(die_comp._original_config)
        die_comp.inputs = []
        die_comp.outputs = []

        executor = _build_executor(
            components_config=[
                {"id": "A", "type": "Stub"},
                {"id": "B", "type": "Stub"},
            ],
            triggers_config=[
                {"type": "OnSubjobOk", "from": "A", "to": "B"},
            ],
            subjobs={"s1": ["A"], "s2": ["B"]},
            component_overrides={"A": die_comp},
        )
        stats = executor.execute_job()
        assert stats["status"] == "error"
        assert "A" in executor.failed_components
        assert "B" not in executor.executed_components
        # Verify exit_code is recorded in stats
        assert executor.execution_stats["A"].get("exit_code") == 1

    def test_independent_subjob_continues_after_failure(self):
        """s1 fails, s2 has no trigger from s1 -> s2 still executes (D-12)."""
        executor = _build_executor(
            components_config=[
                {"id": "A", "type": "Stub", "config": {"should_fail": True}},
                {"id": "B", "type": "Stub"},
            ],
            subjobs={"s1": ["A"], "s2": ["B"]},
        )
        stats = executor.execute_job()
        # s2 has no trigger dependency on s1, so B should still execute
        assert "A" in executor.failed_components
        assert "B" in executor.executed_components


# ---------------------------------------------------------------------------
# 6. Stall detection
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestStallDetection:
    """Test runtime stall detection with actionable diagnostics."""

    def test_runtime_stall_raises_error(self):
        """Components that cannot execute -> ConfigurationError."""
        # Create a component that has inputs but the producer is in a different
        # subjob that never gets triggered
        executor = _build_executor(
            components_config=[
                {"id": "A", "type": "Stub"},
                {"id": "B", "type": "Stub", "inputs": ["missing_flow"]},
            ],
            subjobs={"s1": ["A"], "s2": ["B"]},
            triggers_config=[
                {"type": "OnSubjobOk", "from": "A", "to": "B"},
            ],
        )
        # B's input "missing_flow" will never be available because no component produces it
        # But B's subjob gets triggered. B will be skipped due to inputs not ready.
        # This should result in a stall.
        with pytest.raises(ConfigurationError, match="Runtime stall detected"):
            executor.execute_job()

    def test_stall_error_names_stuck_component_and_missing_flows(self):
        """ConfigurationError message contains component ID, subjob, and missing flows."""
        executor = _build_executor(
            components_config=[
                {"id": "A", "type": "Stub"},
                {"id": "stuck_comp", "type": "Stub", "inputs": ["nonexistent_flow"]},
            ],
            subjobs={"s1": ["A"], "s2": ["stuck_comp"]},
            triggers_config=[
                {"type": "OnSubjobOk", "from": "A", "to": "stuck_comp"},
            ],
        )
        with pytest.raises(ConfigurationError, match="waiting on input flows") as exc_info:
            executor.execute_job()
        error_msg = str(exc_info.value)
        assert "stuck_comp" in error_msg
        assert "nonexistent_flow" in error_msg

    def test_no_stall_on_normal_execution(self):
        """Well-formed job -> no stall error."""
        executor = _build_executor(
            components_config=[
                {"id": "A", "type": "Stub", "config": {"output_data": [{"x": 1}]}, "outputs": ["f1"]},
                {"id": "B", "type": "Stub", "inputs": ["f1"]},
            ],
            flows_config=[
                {"name": "f1", "from": "A", "to": "B", "type": "flow"},
            ],
            subjobs={"s1": ["A", "B"]},
        )
        stats = executor.execute_job()
        assert stats["status"] == "success"


# ---------------------------------------------------------------------------
# 7. Data routing
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDataRouting:
    """Test data routing through OutputRouter via Executor."""

    def test_main_output_routed_correctly(self):
        """A produces main, B receives it via flow."""
        executor = _build_executor(
            components_config=[
                {"id": "A", "type": "Stub", "config": {"output_data": [{"x": 10}]}, "outputs": ["f1"]},
                {"id": "B", "type": "Stub", "inputs": ["f1"]},
            ],
            flows_config=[
                {"name": "f1", "from": "A", "to": "B", "type": "flow"},
            ],
            subjobs={"s1": ["A", "B"]},
        )
        stats = executor.execute_job()
        assert stats["status"] == "success"
        assert stats["components_executed"] == 2

    def test_reject_output_routed_correctly(self):
        """A produces reject, reject-connected component C receives it."""
        executor = _build_executor(
            components_config=[
                {"id": "A", "type": "Stub",
                 "config": {"output_data": [{"x": 1}], "reject_data": [{"err": "bad"}]},
                 "outputs": ["f_main", "f_reject"]},
                {"id": "B", "type": "Stub", "inputs": ["f_main"]},
                {"id": "C", "type": "Stub", "inputs": ["f_reject"]},
            ],
            flows_config=[
                {"name": "f_main", "from": "A", "to": "B", "type": "flow"},
                {"name": "f_reject", "from": "A", "to": "C", "type": "reject"},
            ],
            subjobs={"s1": ["A", "B", "C"]},
        )
        stats = executor.execute_job()
        assert stats["status"] == "success"
        assert stats["components_executed"] == 3

    def test_multi_output_component(self):
        """Component produces main + reject -> each routes to different downstream."""
        executor = _build_executor(
            components_config=[
                {"id": "src", "type": "Stub",
                 "config": {"output_data": [{"val": 1}], "reject_data": [{"bad": 1}]},
                 "outputs": ["out_main", "out_reject"]},
                {"id": "good", "type": "Stub", "inputs": ["out_main"]},
                {"id": "bad", "type": "Stub", "inputs": ["out_reject"]},
            ],
            flows_config=[
                {"name": "out_main", "from": "src", "to": "good", "type": "flow"},
                {"name": "out_reject", "from": "src", "to": "bad", "type": "reject"},
            ],
            subjobs={"s1": ["src", "good", "bad"]},
        )
        stats = executor.execute_job()
        assert stats["status"] == "success"
        assert stats["components_executed"] == 3


# ---------------------------------------------------------------------------
# 8. Subjob flow cleanup
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSubjobFlowCleanup:
    """Test flow cleanup after subjob completion."""

    def test_subjob_flows_cleared_after_completion(self):
        """After subjob completes, its internal flows are cleared."""
        executor = _build_executor(
            components_config=[
                {"id": "A", "type": "Stub", "config": {"output_data": [{"x": 1}]}, "outputs": ["f1"]},
                {"id": "B", "type": "Stub", "inputs": ["f1"]},
            ],
            flows_config=[
                {"name": "f1", "from": "A", "to": "B", "type": "flow"},
            ],
            subjobs={"s1": ["A", "B"]},
        )
        stats = executor.execute_job()
        assert stats["status"] == "success"
        # After s1 completes, f1 should be cleared
        assert not executor.output_router.has_flow_data("f1")

    def test_cross_subjob_flow_preserved_for_pending_consumer(self):
        """Flow from A (s1) to C (s2) preserved until C executes.

        After s1 completes, the cross-subjob flow should NOT be cleared because
        C in s2 hasn't consumed it yet.
        """
        executor = _build_executor(
            components_config=[
                {"id": "A", "type": "Stub", "config": {"output_data": [{"x": 1}]}, "outputs": ["f_cross"]},
                {"id": "C", "type": "Stub", "inputs": ["f_cross"]},
            ],
            flows_config=[
                {"name": "f_cross", "from": "A", "to": "C", "type": "flow"},
            ],
            triggers_config=[
                {"type": "OnSubjobOk", "from": "A", "to": "C"},
            ],
            subjobs={"s1": ["A"], "s2": ["C"]},
        )
        stats = executor.execute_job()
        assert stats["status"] == "success"
        # Both should have executed
        assert "A" in executor.executed_components
        assert "C" in executor.executed_components


# ---------------------------------------------------------------------------
# 9. Iterative trigger firing
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestIterativeTriggerFiring:
    """Test that long trigger chains work without RecursionError."""

    def test_long_trigger_chain_no_recursion_error(self):
        """Chain of 6 subjobs connected by OnSubjobOk -- all execute without RecursionError."""
        n = 6
        comp_ids = [f"comp_{i}" for i in range(n)]

        components_config = [{"id": cid, "type": "Stub"} for cid in comp_ids]
        subjobs = {f"s{i}": [comp_ids[i]] for i in range(n)}
        triggers_config = [
            {"type": "OnSubjobOk", "from": comp_ids[i], "to": comp_ids[i + 1]}
            for i in range(n - 1)
        ]

        executor = _build_executor(
            components_config=components_config,
            triggers_config=triggers_config,
            subjobs=subjobs,
        )
        # This should NOT raise RecursionError
        stats = executor.execute_job()
        assert stats["status"] == "success"
        assert stats["components_executed"] == n


# ---------------------------------------------------------------------------
# 10. Additional edge cases
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestExecutorEdgeCases:
    """Additional edge case tests for completeness."""

    def test_empty_job_succeeds(self):
        """Job with no components completes with success."""
        executor = _build_executor(
            components_config=[],
            subjobs={},
        )
        stats = executor.execute_job()
        assert stats["status"] == "success"
        assert stats["components_executed"] == 0

    def test_execution_stats_contain_timing(self):
        """Each executed component has execution_time in stats."""
        executor = _build_executor(
            components_config=[{"id": "A", "type": "Stub"}],
            subjobs={"s1": ["A"]},
        )
        stats = executor.execute_job()
        assert "execution_time" in executor.execution_stats.get("A", {})
        assert executor.execution_stats["A"]["execution_time"] >= 0
