"""Unit tests for Executor iterate loop (Phase 10-02).

Covers EXEC-04, EXEC-05, EXEC-06 + per-iter trigger firing + REJECT accumulation
+ tDie termination + die_on_error semantics + empty iterate.

Tests use IterateStubComponent (from conftest) as iterate source and StubComponent as body.
All tests are pure unit tests -- no @pytest.mark.java.
"""
import copy
from collections.abc import Iterator
from typing import Any, Optional
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from src.v1.engine.base_component import BaseComponent, ComponentStatus
from src.v1.engine.base_iterate_component import BaseIterateComponent
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ComponentExecutionError, ConfigurationError
from src.v1.engine.execution_plan import ExecutionPlan
from src.v1.engine.executor import Executor
from src.v1.engine.global_map import GlobalMap
from src.v1.engine.output_router import OutputRouter
from src.v1.engine.trigger_manager import TriggerManager

from tests.v1.engine.conftest import (
    IterateStubComponent,
    StubComponent,
    make_iterate_job_config,
    make_stub_component,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_iterate_executor(
    iter_id: str,
    body_comps: list[dict],
    items: list,
    extra_flows: Optional[list[dict]] = None,
    extra_triggers: Optional[list[dict]] = None,
    extra_components: Optional[list[dict]] = None,
    component_overrides: Optional[dict] = None,
    subjobs: Optional[dict] = None,
):
    """Build a fully wired Executor with IterateStubComponent + body StubComponents.

    Args:
        iter_id: Component ID for the IterateStubComponent.
        body_comps: List of body component config dicts (id + optional config).
        items: Items to yield from IterateStubComponent.
        extra_flows: Additional flows beyond the ITERATE edge.
        extra_triggers: Trigger dicts.
        extra_components: Additional components beyond iter + body.
        component_overrides: Dict of comp_id -> custom component instance.
        subjobs: Explicit subjob assignments; None = auto-detect.

    Returns:
        Executor instance.
    """
    global_map = GlobalMap()
    ctx = ContextManager(initial_context={"Default": {}})

    # Build the iterate source config
    iter_cfg = {
        "id": iter_id,
        "type": "tFileList",
        "items": items,
        "globalmap_key_prefix": "TEST_",
    }

    all_comp_configs = [iter_cfg] + list(body_comps) + list(extra_flows and [] or [])
    if extra_components:
        all_comp_configs += extra_components

    # Build ITERATE flows: iter_id -> each body component
    iterate_flows = []
    if body_comps:
        first_body_id = body_comps[0]["id"]
        iterate_flows.append({
            "name": f"iterate_{iter_id}_{first_body_id}",
            "from": iter_id,
            "to": first_body_id,
            "type": "iterate",
        })

    flows = iterate_flows + (extra_flows or [])
    triggers = extra_triggers or []

    # Build ExecutionPlan
    plan = ExecutionPlan(all_comp_configs, flows, triggers, subjobs)

    # Build OutputRouter
    router = OutputRouter(flows, all_comp_configs)

    # Build TriggerManager
    trigger_manager = TriggerManager(global_map)
    for subjob_id in plan.all_subjob_ids:
        sp = plan.get_subjob_plan(subjob_id)
        trigger_manager.register_subjob(subjob_id, list(sp.component_ids))

    for trigger in triggers:
        trigger_manager.add_trigger(
            trigger["type"],
            trigger.get("from_component") or trigger.get("from"),
            trigger.get("to_component") or trigger.get("to"),
            trigger.get("condition"),
        )

    # Build components dict
    components = {}

    # Iterate source
    if component_overrides and iter_id in component_overrides:
        components[iter_id] = component_overrides[iter_id]
    else:
        iter_comp = IterateStubComponent(iter_id, {"items": items}, global_map, ctx)
        iter_comp.config = copy.deepcopy(iter_comp._original_config)
        iter_comp.inputs = []
        iter_comp.outputs = []
        components[iter_id] = iter_comp

    # Body components
    for bc in body_comps:
        bid = bc["id"]
        if component_overrides and bid in component_overrides:
            components[bid] = component_overrides[bid]
        else:
            bcomp = StubComponent(bid, bc.get("config", {}), global_map, ctx)
            bcomp.config = copy.deepcopy(bcomp._original_config)
            bcomp.inputs = bc.get("inputs", [])
            bcomp.outputs = bc.get("outputs", [])
            components[bid] = bcomp

    # Extra components
    if extra_components:
        for ec in extra_components:
            eid = ec["id"]
            if component_overrides and eid in component_overrides:
                components[eid] = component_overrides[eid]
            else:
                ecomp = StubComponent(eid, ec.get("config", {}), global_map, ctx)
                ecomp.config = copy.deepcopy(ecomp._original_config)
                ecomp.inputs = ec.get("inputs", [])
                ecomp.outputs = ec.get("outputs", [])
                components[eid] = ecomp

    return Executor(components, plan, router, trigger_manager, global_map)


# ---------------------------------------------------------------------------
# EXEC-04: Iterate loop runs body N times
# ---------------------------------------------------------------------------

class TestIterateLoopRunsBodyPerItem:
    """EXEC-04: Body components execute once per iteration item."""

    def test_body_runs_per_item(self):
        """Iterate source produces 3 items; body StubComponent executes 3 times."""
        call_count = {"count": 0}

        class CountingStub(StubComponent):
            def _process(self, input_data=None):
                call_count["count"] += 1
                return {"main": pd.DataFrame({"x": [1]})}

        global_map = GlobalMap()
        ctx = ContextManager(initial_context={"Default": {}})
        iter_id = "iter1"
        body_id = "body1"

        iter_comp = IterateStubComponent(
            iter_id, {"items": ["a", "b", "c"]}, global_map, ctx
        )
        iter_comp.config = copy.deepcopy(iter_comp._original_config)

        body_comp = CountingStub(body_id, {}, global_map, ctx)
        body_comp.config = copy.deepcopy(body_comp._original_config)
        body_comp.inputs = []
        body_comp.outputs = []

        flows = [
            {"name": f"iterate_{iter_id}_{body_id}", "from": iter_id, "to": body_id, "type": "iterate"},
        ]
        comps_config = [
            {"id": iter_id, "type": "tFileList"},
            {"id": body_id, "type": "Stub"},
        ]

        plan = ExecutionPlan(comps_config, flows, [], None)
        router = OutputRouter(flows, comps_config)
        trigger_manager = TriggerManager(global_map)
        for sid in plan.all_subjob_ids:
            sp = plan.get_subjob_plan(sid)
            trigger_manager.register_subjob(sid, list(sp.component_ids))

        executor = Executor(
            {iter_id: iter_comp, body_id: body_comp},
            plan, router, trigger_manager, global_map,
        )
        stats = executor.execute_job()

        assert stats["status"] == "success"
        assert call_count["count"] == 3, f"Expected 3 body executions, got {call_count['count']}"

    def test_body_runs_zero_times_for_empty_iterate(self):
        """Iterate source produces 0 items; body never executes."""
        call_count = {"count": 0}

        class CountingStub(StubComponent):
            def _process(self, input_data=None):
                call_count["count"] += 1
                return {"main": pd.DataFrame()}

        global_map = GlobalMap()
        ctx = ContextManager(initial_context={"Default": {}})
        iter_id = "iter1"
        body_id = "body1"

        iter_comp = IterateStubComponent(iter_id, {"items": []}, global_map, ctx)
        iter_comp.config = copy.deepcopy(iter_comp._original_config)

        body_comp = CountingStub(body_id, {}, global_map, ctx)
        body_comp.config = copy.deepcopy(body_comp._original_config)
        body_comp.inputs = []
        body_comp.outputs = []

        flows = [
            {"name": f"iterate_{iter_id}_{body_id}", "from": iter_id, "to": body_id, "type": "iterate"},
        ]
        comps_config = [
            {"id": iter_id, "type": "tFileList"},
            {"id": body_id, "type": "Stub"},
        ]
        plan = ExecutionPlan(comps_config, flows, [], None)
        router = OutputRouter(flows, comps_config)
        trigger_manager = TriggerManager(global_map)
        for sid in plan.all_subjob_ids:
            sp = plan.get_subjob_plan(sid)
            trigger_manager.register_subjob(sid, list(sp.component_ids))

        executor = Executor(
            {iter_id: iter_comp, body_id: body_comp},
            plan, router, trigger_manager, global_map,
        )
        stats = executor.execute_job()
        assert stats["status"] == "success"
        assert call_count["count"] == 0


# ---------------------------------------------------------------------------
# EXEC-05: BaseComponent.reset() called between iterations
# ---------------------------------------------------------------------------

class TestComponentResetBetweenIterations:
    """EXEC-05: reset() is called between iterations."""

    def test_reset_called_between_iters(self):
        """Body StubComponent has reset() spy; assert reset() called between iterations."""
        reset_calls = {"count": 0}

        class ResetTrackingStub(StubComponent):
            def reset(self):
                reset_calls["count"] += 1
                super().reset()

        global_map = GlobalMap()
        ctx = ContextManager(initial_context={"Default": {}})
        iter_id = "iter1"
        body_id = "body1"

        iter_comp = IterateStubComponent(iter_id, {"items": [1, 2, 3]}, global_map, ctx)
        iter_comp.config = copy.deepcopy(iter_comp._original_config)

        body_comp = ResetTrackingStub(body_id, {}, global_map, ctx)
        body_comp.config = copy.deepcopy(body_comp._original_config)
        body_comp.inputs = []
        body_comp.outputs = []

        flows = [
            {"name": f"iterate_{iter_id}_{body_id}", "from": iter_id, "to": body_id, "type": "iterate"},
        ]
        comps_config = [
            {"id": iter_id, "type": "tFileList"},
            {"id": body_id, "type": "Stub"},
        ]
        plan = ExecutionPlan(comps_config, flows, [], None)
        router = OutputRouter(flows, comps_config)
        trigger_manager = TriggerManager(global_map)
        for sid in plan.all_subjob_ids:
            sp = plan.get_subjob_plan(sid)
            trigger_manager.register_subjob(sid, list(sp.component_ids))

        executor = Executor(
            {iter_id: iter_comp, body_id: body_comp},
            plan, router, trigger_manager, global_map,
        )
        executor.execute_job()

        # 3 items: reset called after iter 1, 2, 3 => 3 times
        assert reset_calls["count"] == 3, (
            f"Expected 3 reset() calls (one per iteration), got {reset_calls['count']}"
        )

    def test_reset_not_called_before_first_iter(self):
        """reset() is NOT called before the first iteration (component starts fresh)."""
        reset_calls = {"count": 0, "before_first_execute": 0}
        execute_calls = {"count": 0}

        class ResetTrackingStub(StubComponent):
            def reset(self):
                reset_calls["count"] += 1
                super().reset()

            def _process(self, input_data=None):
                execute_calls["count"] += 1
                return {"main": pd.DataFrame()}

        global_map = GlobalMap()
        ctx = ContextManager(initial_context={"Default": {}})
        iter_id = "iter1"
        body_id = "body1"

        iter_comp = IterateStubComponent(iter_id, {"items": [1]}, global_map, ctx)
        iter_comp.config = copy.deepcopy(iter_comp._original_config)

        body_comp = ResetTrackingStub(body_id, {}, global_map, ctx)
        body_comp.config = copy.deepcopy(body_comp._original_config)
        body_comp.inputs = []
        body_comp.outputs = []

        flows = [
            {"name": f"iterate_{iter_id}_{body_id}", "from": iter_id, "to": body_id, "type": "iterate"},
        ]
        comps_config = [
            {"id": iter_id, "type": "tFileList"},
            {"id": body_id, "type": "Stub"},
        ]
        plan = ExecutionPlan(comps_config, flows, [], None)
        router = OutputRouter(flows, comps_config)
        trigger_manager = TriggerManager(global_map)
        for sid in plan.all_subjob_ids:
            sp = plan.get_subjob_plan(sid)
            trigger_manager.register_subjob(sid, list(sp.component_ids))

        executor = Executor(
            {iter_id: iter_comp, body_id: body_comp},
            plan, router, trigger_manager, global_map,
        )

        # reset_calls starts at 0 before execute_job
        assert reset_calls["count"] == 0
        executor.execute_job()
        # 1 item: reset called once (AFTER the first execution, before potential next)
        assert reset_calls["count"] == 1
        assert execute_calls["count"] == 1


# ---------------------------------------------------------------------------
# EXEC-06: Config freshness per iteration
# ---------------------------------------------------------------------------

class TestConfigFreshnessPerIteration:
    """EXEC-06: Body components see fresh config per iteration."""

    def test_body_config_freshness(self):
        """Body StubComponent config is mutated during iter 1; iter 2 sees original config."""
        seen_configs = []

        class ConfigMutatingStub(StubComponent):
            def _process(self, input_data=None):
                # Record what config key "sentinel" is at start of this execution
                seen_configs.append(self.config.get("sentinel", "MISSING"))
                # Mutate config to simulate a component that modifies its config
                self.config["sentinel"] = "MUTATED"
                return {"main": pd.DataFrame()}

        global_map = GlobalMap()
        ctx = ContextManager(initial_context={"Default": {}})
        iter_id = "iter1"
        body_id = "body1"

        iter_comp = IterateStubComponent(iter_id, {"items": [1, 2]}, global_map, ctx)
        iter_comp.config = copy.deepcopy(iter_comp._original_config)

        body_comp = ConfigMutatingStub(body_id, {"sentinel": "ORIGINAL"}, global_map, ctx)
        # Set _original_config to include sentinel key
        body_comp._original_config = {"sentinel": "ORIGINAL"}
        body_comp.config = copy.deepcopy(body_comp._original_config)
        body_comp.inputs = []
        body_comp.outputs = []

        flows = [
            {"name": f"iterate_{iter_id}_{body_id}", "from": iter_id, "to": body_id, "type": "iterate"},
        ]
        comps_config = [
            {"id": iter_id, "type": "tFileList"},
            {"id": body_id, "type": "Stub"},
        ]
        plan = ExecutionPlan(comps_config, flows, [], None)
        router = OutputRouter(flows, comps_config)
        trigger_manager = TriggerManager(global_map)
        for sid in plan.all_subjob_ids:
            sp = plan.get_subjob_plan(sid)
            trigger_manager.register_subjob(sid, list(sp.component_ids))

        executor = Executor(
            {iter_id: iter_comp, body_id: body_comp},
            plan, router, trigger_manager, global_map,
        )
        executor.execute_job()

        # iter 1: sees "ORIGINAL"; iter 2: also sees "ORIGINAL" (reset restores config)
        assert len(seen_configs) == 2
        assert seen_configs[0] == "ORIGINAL", f"Iter 1 should see ORIGINAL, got {seen_configs[0]}"
        assert seen_configs[1] == "ORIGINAL", f"Iter 2 should see ORIGINAL (config freshness), got {seen_configs[1]}"


# ---------------------------------------------------------------------------
# Stats rollup
# ---------------------------------------------------------------------------

class TestStatsRollup:
    """D-D1, D-D2: Stats accumulated from iterate loop."""

    def _make_simple_executor(self, items):
        """Build executor with N-item iterate + 1 body comp."""
        global_map = GlobalMap()
        ctx = ContextManager(initial_context={"Default": {}})
        iter_id = "iter1"
        body_id = "body1"

        iter_comp = IterateStubComponent(iter_id, {"items": items}, global_map, ctx)
        iter_comp.config = copy.deepcopy(iter_comp._original_config)

        body_comp = StubComponent(body_id, {}, global_map, ctx)
        body_comp.config = copy.deepcopy(body_comp._original_config)
        body_comp.inputs = []
        body_comp.outputs = []

        flows = [
            {"name": f"iterate_{iter_id}_{body_id}", "from": iter_id, "to": body_id, "type": "iterate"},
        ]
        comps_config = [
            {"id": iter_id, "type": "tFileList"},
            {"id": body_id, "type": "Stub"},
        ]
        plan = ExecutionPlan(comps_config, flows, [], None)
        router = OutputRouter(flows, comps_config)
        trigger_manager = TriggerManager(global_map)
        for sid in plan.all_subjob_ids:
            sp = plan.get_subjob_plan(sid)
            trigger_manager.register_subjob(sid, list(sp.component_ids))

        executor = Executor(
            {iter_id: iter_comp, body_id: body_comp},
            plan, router, trigger_manager, global_map,
        )
        return executor, iter_id

    def test_nb_line_equals_iterations_attempted(self):
        """5 iterations -> iter_comp's stats NB_LINE == 5."""
        executor, iter_id = self._make_simple_executor([1, 2, 3, 4, 5])
        executor.execute_job()

        iter_comp = executor.components[iter_id]
        assert iter_comp.stats["NB_LINE"] == 5

    def test_per_iter_timing_recorded(self):
        """Stats include total_iter_time, avg_iter_time, slowest, fastest fields."""
        executor, iter_id = self._make_simple_executor([1, 2, 3])
        executor.execute_job()

        iter_comp = executor.components[iter_id]
        stats = iter_comp.stats
        assert "total_iter_time" in stats
        assert "avg_iter_time" in stats
        assert "slowest_iter_time" in stats
        assert "fastest_iter_time" in stats
        assert "slowest_iter_index" in stats
        assert "fastest_iter_index" in stats

    def test_nb_line_ok_and_reject_counts(self):
        """3 successful iterations -> NB_LINE_OK=3, NB_LINE_REJECT=0."""
        executor, iter_id = self._make_simple_executor(["a", "b", "c"])
        executor.execute_job()

        iter_comp = executor.components[iter_id]
        assert iter_comp.stats["NB_LINE_OK"] == 3
        assert iter_comp.stats["NB_LINE_REJECT"] == 0


# ---------------------------------------------------------------------------
# REJECT accumulation
# ---------------------------------------------------------------------------

class TestRejectAccumulation:
    """D-D4: Body reject DataFrames are accumulated across iterations."""

    def test_body_rejects_accumulated_concatenated(self):
        """Body emits 2 reject rows per iter; 3 iters => accumulated reject has 6 rows.

        The body component has a reject-type outgoing flow. The iterate loop drains these
        per-iteration rejects and accumulates them. At the end of the loop, the accumulated
        reject (6 rows) is routed via route_outputs as the iterate component's reject output.

        We intercept route_outputs to capture what the iterate loop routes.
        Note: the body reject flow should NOT have an intra-body consumer -- the iterate
        loop's drain_reject_flows accumulates them for the iterate source's reject output.
        """
        routed_rejects = []

        global_map = GlobalMap()
        ctx = ContextManager(initial_context={"Default": {}})
        iter_id = "iter1"
        body_id = "body1"
        # External sink in a SEPARATE subjob (not in the body)
        sink_id = "reject_sink"

        iter_comp = IterateStubComponent(iter_id, {"items": [1, 2, 3]}, global_map, ctx)
        iter_comp.config = copy.deepcopy(iter_comp._original_config)

        # Body component produces 2 reject rows per iteration.
        # The body comp's reject flow goes to sink_id which is in s2 (cross-subjob).
        body_comp = StubComponent(body_id, {
            "reject_data": [{"errorMessage": "err1"}, {"errorMessage": "err2"}],
        }, global_map, ctx)
        body_comp.config = copy.deepcopy(body_comp._original_config)
        body_comp.inputs = []
        body_comp.outputs = []

        sink_comp = StubComponent(sink_id, {}, global_map, ctx)
        sink_comp.config = copy.deepcopy(sink_comp._original_config)
        sink_comp.inputs = [f"reject_{body_id}_to_sink"]
        sink_comp.outputs = []

        flows = [
            {"name": f"iterate_{iter_id}_{body_id}", "from": iter_id, "to": body_id, "type": "iterate"},
            {"name": f"reject_{body_id}_to_sink", "from": body_id, "to": sink_id, "type": "reject"},
        ]
        comps_config = [
            {"id": iter_id, "type": "tFileList"},
            {"id": body_id, "type": "Stub"},
            {"id": sink_id, "type": "Stub"},
        ]
        # s2 contains sink_id which is cross-subjob so it won't be included in body BFS
        subjobs = {"s1": [iter_id, body_id], "s2": [sink_id]}
        triggers = [{"type": "OnSubjobOk", "from": iter_id, "to": sink_id}]

        plan = ExecutionPlan(comps_config, flows, triggers, subjobs)
        router = OutputRouter(flows, comps_config)
        trigger_manager = TriggerManager(global_map)
        for sid_k in plan.all_subjob_ids:
            sp = plan.get_subjob_plan(sid_k)
            trigger_manager.register_subjob(sid_k, list(sp.component_ids))

        trigger_manager.add_trigger("OnSubjobOk", iter_id, sink_id, None)

        # Wrap route_outputs to capture calls with reject data from iter_id
        original_route = router.route_outputs
        def capturing_route(comp_id, result):
            if comp_id == iter_id and result.get("reject") is not None:
                routed_rejects.append(result["reject"])
            original_route(comp_id, result)

        router.route_outputs = capturing_route

        executor = Executor(
            {iter_id: iter_comp, body_id: body_comp, sink_id: sink_comp},
            plan, router, trigger_manager, global_map,
        )
        executor.execute_job()

        # Verify accumulated reject was routed from iter_id (3 iters x 2 rows = 6)
        assert len(routed_rejects) == 1, (
            f"Expected 1 accumulated reject routing call, got {len(routed_rejects)}"
        )
        assert len(routed_rejects[0]) == 6, (
            f"Expected 6 accumulated reject rows (3 iters * 2 rows), got {len(routed_rejects[0])}"
        )


# ---------------------------------------------------------------------------
# Failure semantics
# ---------------------------------------------------------------------------

class TestFailureSemantics:
    """D-E1, D-E2, D-E5: Error handling inside iterate loop."""

    def test_die_on_error_false_continues(self):
        """Body component fails iter 2 with die_on_error=False; iter 3 still runs."""
        call_counts = {"count": 0}

        class FailOnSecondStub(StubComponent):
            def _process(self, input_data=None):
                call_counts["count"] += 1
                if call_counts["count"] == 2:
                    raise ComponentExecutionError(self.id, "fail on iter 2")
                return {"main": pd.DataFrame()}

        global_map = GlobalMap()
        ctx = ContextManager(initial_context={"Default": {}})
        iter_id = "iter1"
        body_id = "body1"

        iter_comp = IterateStubComponent(iter_id, {"items": [1, 2, 3]}, global_map, ctx)
        iter_comp.config = copy.deepcopy(iter_comp._original_config)

        body_comp = FailOnSecondStub(body_id, {"die_on_error": False}, global_map, ctx)
        body_comp.config = copy.deepcopy(body_comp._original_config)
        body_comp.inputs = []
        body_comp.outputs = []

        flows = [
            {"name": f"iterate_{iter_id}_{body_id}", "from": iter_id, "to": body_id, "type": "iterate"},
        ]
        comps_config = [
            {"id": iter_id, "type": "tFileList"},
            {"id": body_id, "type": "Stub"},
        ]
        plan = ExecutionPlan(comps_config, flows, [], None)
        router = OutputRouter(flows, comps_config)
        trigger_manager = TriggerManager(global_map)
        for sid in plan.all_subjob_ids:
            sp = plan.get_subjob_plan(sid)
            trigger_manager.register_subjob(sid, list(sp.component_ids))

        executor = Executor(
            {iter_id: iter_comp, body_id: body_comp},
            plan, router, trigger_manager, global_map,
        )
        executor.execute_job()

        # Body should have been called 3 times (iter 2 failed but loop continues)
        assert call_counts["count"] == 3
        iter_comp_ref = executor.components[iter_id]
        assert iter_comp_ref.stats["NB_LINE_REJECT"] == 1
        assert iter_comp_ref.stats["NB_LINE_OK"] == 2

    def test_t_die_in_body_terminates_job(self):
        """Body component throws ComponentExecutionError with exit_code; job terminates."""
        call_counts = {"count": 0}

        class DieOnFirstStub(StubComponent):
            def _process(self, input_data=None):
                call_counts["count"] += 1
                err = ComponentExecutionError(self.id, "tDie triggered")
                err.exit_code = 1
                raise err

        global_map = GlobalMap()
        ctx = ContextManager(initial_context={"Default": {}})
        iter_id = "iter1"
        body_id = "body1"

        iter_comp = IterateStubComponent(iter_id, {"items": [1, 2, 3]}, global_map, ctx)
        iter_comp.config = copy.deepcopy(iter_comp._original_config)

        body_comp = DieOnFirstStub(body_id, {}, global_map, ctx)
        body_comp.config = copy.deepcopy(body_comp._original_config)
        body_comp.inputs = []
        body_comp.outputs = []

        flows = [
            {"name": f"iterate_{iter_id}_{body_id}", "from": iter_id, "to": body_id, "type": "iterate"},
        ]
        comps_config = [
            {"id": iter_id, "type": "tFileList"},
            {"id": body_id, "type": "Stub"},
        ]
        plan = ExecutionPlan(comps_config, flows, [], None)
        router = OutputRouter(flows, comps_config)
        trigger_manager = TriggerManager(global_map)
        for sid in plan.all_subjob_ids:
            sp = plan.get_subjob_plan(sid)
            trigger_manager.register_subjob(sid, list(sp.component_ids))

        executor = Executor(
            {iter_id: iter_comp, body_id: body_comp},
            plan, router, trigger_manager, global_map,
        )
        stats = executor.execute_job()

        # tDie should terminate -- body called only once
        assert call_counts["count"] == 1, f"Expected 1 body call (tDie), got {call_counts['count']}"
        assert executor._job_terminated is True
        assert stats["status"] == "error"


# ---------------------------------------------------------------------------
# Iterate-source triggers fire once (D-C2)
# ---------------------------------------------------------------------------

class TestIterateSourceTriggersFireOnce:
    """D-C2: Triggers from iterate source fire exactly once after all iterations."""

    def test_iterate_source_triggers_fire_once(self):
        """iterate source OnSubjobOk trigger to subjob_2 fires exactly once."""
        call_counts = {"subjob2_body": 0}

        global_map = GlobalMap()
        ctx = ContextManager(initial_context={"Default": {}})
        iter_id = "iter1"
        body_id = "body1"
        downstream_id = "downstream1"

        iter_comp = IterateStubComponent(iter_id, {"items": [1, 2, 3]}, global_map, ctx)
        iter_comp.config = copy.deepcopy(iter_comp._original_config)

        body_comp = StubComponent(body_id, {}, global_map, ctx)
        body_comp.config = copy.deepcopy(body_comp._original_config)
        body_comp.inputs = []
        body_comp.outputs = []

        class CountingDownstream(StubComponent):
            def _process(self, input_data=None):
                call_counts["subjob2_body"] += 1
                return {"main": pd.DataFrame()}

        downstream = CountingDownstream(downstream_id, {}, global_map, ctx)
        downstream.config = copy.deepcopy(downstream._original_config)
        downstream.inputs = []
        downstream.outputs = []

        flows = [
            {"name": f"iterate_{iter_id}_{body_id}", "from": iter_id, "to": body_id, "type": "iterate"},
        ]
        triggers = [
            {"type": "OnSubjobOk", "from": iter_id, "to": downstream_id},
        ]
        comps_config = [
            {"id": iter_id, "type": "tFileList"},
            {"id": body_id, "type": "Stub"},
            {"id": downstream_id, "type": "Stub"},
        ]
        # Two subjobs: s1 has iter+body, s2 has downstream
        subjobs = {"s1": [iter_id, body_id], "s2": [downstream_id]}

        plan = ExecutionPlan(comps_config, flows, triggers, subjobs)
        router = OutputRouter(flows, comps_config)
        trigger_manager = TriggerManager(global_map)
        for sid in plan.all_subjob_ids:
            sp = plan.get_subjob_plan(sid)
            trigger_manager.register_subjob(sid, list(sp.component_ids))

        trigger_manager.add_trigger("OnSubjobOk", iter_id, downstream_id, None)

        executor = Executor(
            {iter_id: iter_comp, body_id: body_comp, downstream_id: downstream},
            plan, router, trigger_manager, global_map,
        )
        executor.execute_job()

        # downstream fires exactly ONCE, not 3 times
        assert call_counts["subjob2_body"] == 1, (
            f"Expected 1 downstream execution (source trigger), got {call_counts['subjob2_body']}"
        )


# ---------------------------------------------------------------------------
# Nested iterate detection
# ---------------------------------------------------------------------------

class TestNestedIterateRaises:
    """D-B4: ExecutionPlan rejects nested iterate at construction time."""

    def test_execution_plan_rejects_nested_iterate(self):
        """Nested iterate components raise ConfigurationError during ExecutionPlan construction."""
        with pytest.raises(ConfigurationError) as exc_info:
            ExecutionPlan(
                components=[
                    {"id": "iter1", "type": "tFileList"},
                    {"id": "iter2", "type": "tFlowToIterate"},
                    {"id": "body1", "type": "LogRow"},
                ],
                flows=[
                    {"name": "iter_iter1_iter2", "from": "iter1", "to": "iter2", "type": "iterate"},
                    {"name": "iter_iter2_body1", "from": "iter2", "to": "body1", "type": "iterate"},
                ],
                triggers=[],
                subjobs={"s1": ["iter1", "iter2", "body1"]},
            )
        msg = str(exc_info.value)
        assert "iter1" in msg or "iter2" in msg


# ---------------------------------------------------------------------------
# Empty iterate fires subjob OK (D-F1, D-C2)
# ---------------------------------------------------------------------------

class TestEmptyIterate:
    """D-F1, D-C2: Empty iterate still fires OnSubjobOk."""

    def test_empty_iterate_fires_subjob_ok(self):
        """iterate source produces 0 items; still fires OnSubjobOk trigger once."""
        call_counts = {"downstream": 0}

        global_map = GlobalMap()
        ctx = ContextManager(initial_context={"Default": {}})
        iter_id = "iter1"
        body_id = "body1"
        downstream_id = "downstream1"

        iter_comp = IterateStubComponent(iter_id, {"items": []}, global_map, ctx)
        iter_comp.config = copy.deepcopy(iter_comp._original_config)

        body_comp = StubComponent(body_id, {}, global_map, ctx)
        body_comp.config = copy.deepcopy(body_comp._original_config)
        body_comp.inputs = []
        body_comp.outputs = []

        class CountingDownstream(StubComponent):
            def _process(self, input_data=None):
                call_counts["downstream"] += 1
                return {"main": pd.DataFrame()}

        downstream = CountingDownstream(downstream_id, {}, global_map, ctx)
        downstream.config = copy.deepcopy(downstream._original_config)
        downstream.inputs = []
        downstream.outputs = []

        flows = [
            {"name": f"iterate_{iter_id}_{body_id}", "from": iter_id, "to": body_id, "type": "iterate"},
        ]
        triggers = [
            {"type": "OnSubjobOk", "from": iter_id, "to": downstream_id},
        ]
        comps_config = [
            {"id": iter_id, "type": "tFileList"},
            {"id": body_id, "type": "Stub"},
            {"id": downstream_id, "type": "Stub"},
        ]
        subjobs = {"s1": [iter_id, body_id], "s2": [downstream_id]}

        plan = ExecutionPlan(comps_config, flows, triggers, subjobs)
        router = OutputRouter(flows, comps_config)
        trigger_manager = TriggerManager(global_map)
        for sid in plan.all_subjob_ids:
            sp = plan.get_subjob_plan(sid)
            trigger_manager.register_subjob(sid, list(sp.component_ids))

        trigger_manager.add_trigger("OnSubjobOk", iter_id, downstream_id, None)

        executor = Executor(
            {iter_id: iter_comp, body_id: body_comp, downstream_id: downstream},
            plan, router, trigger_manager, global_map,
        )
        executor.execute_job()

        assert call_counts["downstream"] == 1, (
            f"Expected downstream to fire once even with 0 items, got {call_counts['downstream']}"
        )
        iter_comp_ref = executor.components[iter_id]
        assert iter_comp_ref.stats["NB_LINE"] == 0


# ---------------------------------------------------------------------------
# Partial iterate on die_on_error=true mid-loop (D-E6)
# ---------------------------------------------------------------------------

class TestPartialIterateOnDieOnError:
    """D-E6: die_on_error=True mid-iter preserves prior rejects."""

    def test_die_on_error_true_stops_loop(self):
        """Body fails on iter 3 with die_on_error=True; loop stops after iter 3."""
        call_counts = {"count": 0}

        class FailOnThirdStub(StubComponent):
            def _process(self, input_data=None):
                call_counts["count"] += 1
                if call_counts["count"] == 3:
                    raise ComponentExecutionError(self.id, "fail on iter 3")
                return {"main": pd.DataFrame()}

        global_map = GlobalMap()
        ctx = ContextManager(initial_context={"Default": {}})
        iter_id = "iter1"
        body_id = "body1"

        iter_comp = IterateStubComponent(iter_id, {"items": [1, 2, 3, 4, 5]}, global_map, ctx)
        iter_comp.config = copy.deepcopy(iter_comp._original_config)

        # die_on_error=True: body failure propagates up
        body_comp = FailOnThirdStub(body_id, {"die_on_error": True}, global_map, ctx)
        body_comp.config = copy.deepcopy(body_comp._original_config)
        body_comp.inputs = []
        body_comp.outputs = []

        flows = [
            {"name": f"iterate_{iter_id}_{body_id}", "from": iter_id, "to": body_id, "type": "iterate"},
        ]
        comps_config = [
            {"id": iter_id, "type": "tFileList"},
            {"id": body_id, "type": "Stub"},
        ]
        plan = ExecutionPlan(comps_config, flows, [], None)
        router = OutputRouter(flows, comps_config)
        trigger_manager = TriggerManager(global_map)
        for sid in plan.all_subjob_ids:
            sp = plan.get_subjob_plan(sid)
            trigger_manager.register_subjob(sid, list(sp.component_ids))

        executor = Executor(
            {iter_id: iter_comp, body_id: body_comp},
            plan, router, trigger_manager, global_map,
        )
        executor.execute_job()

        # Body should have been called 3 times (stops at iter 3 failure with die_on_error)
        assert call_counts["count"] == 3
        iter_comp_ref = executor.components[iter_id]
        # NB_LINE_OK = 2 (iters 1-2), NB_LINE_REJECT = 1 (iter 3), NB_LINE = 3
        assert iter_comp_ref.stats["NB_LINE"] == 3
        assert iter_comp_ref.stats["NB_LINE_OK"] == 2
        assert iter_comp_ref.stats["NB_LINE_REJECT"] == 1


# ---------------------------------------------------------------------------
# CR-02 + CR-03 + CR-04 API contract tests
# ---------------------------------------------------------------------------

class TestIterateAPIContract:
    """Prove CR-02, CR-03, and CR-04 gap-closure fixes.

    CR-02: current_iteration_index advances per iteration (executor uses
           has_next_iteration/get_next_iteration_context public API).
    CR-03: on_iteration_error is removed (Hook 8 was unreachable because
           _execute_component uses errors-as-statuses, not re-raises).
    CR-04: stale 'error' status from iteration N does not cause spurious
           die_on_error termination in iteration N+1.
    """

    def test_current_iteration_index_advances(self):
        """CR-02 fix: current_iteration_index equals number of completed iterations."""
        items = ["a", "b", "c"]
        # Build a 3-item iterate executor using existing _make_iterate_executor helper
        exc = _make_iterate_executor(
            iter_id="iter1",
            body_comps=[{"id": "body1", "type": "StubComponent", "config": {}}],
            items=items,
        )
        iter_comp = exc.components["iter1"]
        # Execute the job (which runs the iterate loop)
        exc.execute_job()
        # After 3 items, current_iteration_index must equal 3
        assert iter_comp.current_iteration_index == 3, (
            f"Expected current_iteration_index=3, got {iter_comp.current_iteration_index}. "
            "CR-02: executor must drive loop via has_next_iteration/get_next_iteration_context."
        )

    def test_on_iteration_error_removed(self):
        """CR-03 fix: on_iteration_error is not present on BaseIterateComponent subclasses."""
        assert not hasattr(BaseIterateComponent, "on_iteration_error"), (
            "on_iteration_error must be removed (CR-03): Hook 8 was unreachable "
            "because _execute_component uses errors-as-statuses, not re-raises."
        )

    def test_stale_stats_do_not_trigger_die_on_error(self):
        """CR-04 fix: stale 'error' status from iter N does not cause early termination in iter N+1.

        Setup: 3 iterations. Body has one component (body_a, die_on_error=False).
        body_a fails only on iteration 1. Iterations 2 and 3 must still complete.

        Before CR-04 fix: iteration 2 check sees stale 'error' for body_a from iter 1
        in execution_stats and terminates early even though die_on_error=False.
        After CR-04 fix: iter_local_failed_bodies scopes the die_on_error check to
        the current iteration only -- stale stats are ignored.

        IMPORTANT: We patch _process (not execute) so that the full execute() lifecycle
        runs, setting die_on_error=False from config before _process is called.
        Patching execute() directly would prevent die_on_error from being set from config.
        """
        call_count = [0]

        class FailFirstThenOkStub(StubComponent):
            def _process(self, input_data=None):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise Exception("synthetic body_a error on iter 1")
                return {"main": pd.DataFrame()}

        items = [1, 2, 3]
        global_map = GlobalMap()
        ctx = ContextManager(initial_context={"Default": {}})
        iter_id = "iter1"
        body_id = "body_a"

        iter_comp = IterateStubComponent(iter_id, {"items": items}, global_map, ctx)
        iter_comp.config = copy.deepcopy(iter_comp._original_config)

        body_comp = FailFirstThenOkStub(body_id, {"die_on_error": False}, global_map, ctx)
        body_comp.config = copy.deepcopy(body_comp._original_config)
        body_comp.inputs = []
        body_comp.outputs = []

        flows = [
            {"name": f"iterate_{iter_id}_{body_id}", "from": iter_id, "to": body_id, "type": "iterate"},
        ]
        comps_config = [
            {"id": iter_id, "type": "tFileList"},
            {"id": body_id, "type": "Stub"},
        ]
        plan = ExecutionPlan(comps_config, flows, [], None)
        router = OutputRouter(flows, comps_config)
        trigger_manager = TriggerManager(global_map)
        for sid in plan.all_subjob_ids:
            sp = plan.get_subjob_plan(sid)
            trigger_manager.register_subjob(sid, list(sp.component_ids))

        executor = Executor(
            {iter_id: iter_comp, body_id: body_comp},
            plan, router, trigger_manager, global_map,
        )
        executor.execute_job()

        # All 3 iterations must have been attempted (stale error from iter 1 must not stop iter 2/3)
        assert iter_comp.stats.get("NB_LINE") == 3, (
            f"Expected NB_LINE=3 (all iterations attempted), got {iter_comp.stats.get('NB_LINE')}. "
            "CR-04: stale execution_stats from iter N must not cause die_on_error check to fire in iter N+1."
        )
