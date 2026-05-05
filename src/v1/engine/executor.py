"""Executor: subjob and component execution with error handling.

Owns the main execution loop. Uses ExecutionPlan for ordering,
OutputRouter for data routing, TriggerManager for inter-subjob flow.

Key design:
- _execute_subjob() is THE building block for Phase 10 iterate support.
  It will be called in a loop per iteration item.
- OnSubjobOk triggers fire ONLY after ALL subjob components complete.
- OnComponentOk triggers fire after each individual component.
- tDie raises ComponentExecutionError with exit_code to stop the entire job.
- Trigger firing uses an iterative queue (collections.deque), NOT recursion,
  to avoid hitting Python's recursion limit on long trigger chains.
"""
from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any

import pandas as pd

from .base_component import BaseComponent, ComponentStatus
from .exceptions import ComponentExecutionError, ConfigurationError
from .execution_plan import ExecutionPlan, SubjobPlan
from .output_router import OutputRouter
from .trigger_manager import TriggerManager
from .global_map import GlobalMap

logger = logging.getLogger(__name__)


class Executor:
    """Execute ETL jobs by orchestrating subjobs and components.

    Uses ExecutionPlan for topological ordering, OutputRouter for data
    routing between components, and TriggerManager for inter-subjob
    trigger firing.

    Args:
        components: Dict mapping component ID to BaseComponent instance.
        execution_plan: Pre-built ExecutionPlan with validated DAG.
        output_router: OutputRouter for data flow management.
        trigger_manager: TriggerManager for trigger evaluation.
        global_map: GlobalMap for shared state.
    """

    def __init__(
        self,
        components: dict[str, BaseComponent],
        execution_plan: ExecutionPlan,
        output_router: OutputRouter,
        trigger_manager: TriggerManager,
        global_map: GlobalMap,
    ) -> None:
        self.components = components
        self.execution_plan = execution_plan
        self.output_router = output_router
        self.trigger_manager = trigger_manager
        self.global_map = global_map

        # Tracking sets
        self.executed_components: set[str] = set()
        self.failed_components: set[str] = set()

        # Execution stats per component
        self.execution_stats: dict[str, Any] = {}

        # Set by tDie to stop the entire job
        self._job_terminated: bool = False
        self._termination_error: ComponentExecutionError | None = None

        # Subjobs queued by OnComponentOk cross-subjob triggers
        self._component_triggered_subjobs: list[str] = []

        # Track which subjobs were actually attempted (for stall detection)
        self._attempted_subjobs: set[str] = set()

        # Incrementally tracked set of completed subjobs (WR-01)
        self._executed_subjobs: set[str] = set()

        # Iterate stack depth for nested-iterate prevention (D-A6, Phase 10)
        self._current_iterate_depth: int = 0

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def execute_job(self) -> dict[str, Any]:
        """Execute the full job by processing subjobs via an iterative queue.

        Seeds the queue with initial (non-triggered) subjobs, then
        processes triggered subjobs by appending to the queue. Uses
        ``collections.deque`` for the iterative approach instead of
        recursive trigger firing.

        Returns:
            Execution stats dict with keys: status, execution_time,
            components_executed, components_failed, component_stats.
        """
        start_time = time.time()

        # Iterative subjob queue -- NOT recursion
        pending_subjobs = deque(self.execution_plan.initial_subjobs)
        logger.info("Initial subjobs: %s", list(pending_subjobs))

        while pending_subjobs:
            subjob_id = pending_subjobs.popleft()
            if subjob_id in self._attempted_subjobs:
                continue
            self._attempted_subjobs.add(subjob_id)
            logger.info("Executing subjob: %s", subjob_id)

            result = self._execute_subjob(subjob_id)

            # Collect triggered subjobs (OnSubjobOk/Error/RunIf) and append to queue
            triggered = self._collect_triggered_subjobs(subjob_id, result)
            pending_subjobs.extend(triggered)

            # Also collect any subjobs triggered by OnComponentOk during subjob execution
            if self._component_triggered_subjobs:
                pending_subjobs.extend(self._component_triggered_subjobs)
                self._component_triggered_subjobs = []

            if self._job_terminated:
                logger.info("Job terminated by tDie component")
                break

        # Stall detection: check for components in attempted subjobs that never executed
        if not self._job_terminated:
            unexecuted = set(self.components.keys()) - self.executed_components
            # Exclude components marked as skipped
            unexecuted = {
                c for c in unexecuted
                if self.execution_stats.get(c, {}).get("status") != "skipped"
            }
            # Only flag components in subjobs that were actually attempted
            # (components in untriggered subjobs are not stuck, just conditional)
            unexecuted = {
                c for c in unexecuted
                if self.execution_plan.component_to_subjob.get(c) in self._attempted_subjobs
            }
            if unexecuted:
                diagnostics = self._build_stall_diagnostics(unexecuted)
                raise ConfigurationError(
                    f"Runtime stall detected: {len(unexecuted)} components never executed. "
                    f"Stuck components:\n{diagnostics}"
                )

        execution_time = time.time() - start_time

        if self._job_terminated:
            status = "error"
        elif self.failed_components:
            status = "failed"
        else:
            status = "success"

        stats = {
            "status": status,
            "execution_time": execution_time,
            "components_executed": len(self.executed_components),
            "components_failed": len(self.failed_components),
            "component_stats": self.execution_stats,
        }

        logger.info(
            "Job execution complete: status=%s, executed=%d, failed=%d, time=%.2fs",
            status, len(self.executed_components), len(self.failed_components), execution_time,
        )
        return stats

    # ------------------------------------------------------------------
    # Subjob execution -- THE building block for Phase 10
    # ------------------------------------------------------------------

    def _execute_subjob(self, subjob_id: str) -> str:
        """Execute all components in a subjob in topological order.

        Looks up the SubjobPlan from ExecutionPlan, delegates to
        _execute_subjob_plan, then records completion.

        Args:
            subjob_id: The subjob identifier.

        Returns:
            'success' if all components passed, 'error' otherwise.
        """
        subjob_plan = self.execution_plan.get_subjob_plan(subjob_id)
        result = self._execute_subjob_plan(subjob_plan)
        self._executed_subjobs.add(subjob_id)
        return result

    def _execute_subjob_plan(self, subjob_plan: SubjobPlan) -> str:
        """Execute a SubjobPlan directly.

        This is THE building block that Phase 10 iterate support calls in a
        loop per iteration item. Per-component status, trigger firing, and
        cross-subjob flow cleanup all live here.

        Args:
            subjob_plan: The SubjobPlan to execute.

        Returns:
            'success' if all components passed, 'error' otherwise.
        """
        subjob_failed = False

        # Track which components were added to executed_components by iterate body loops
        # so we can skip them when the outer subjob loop reaches them.
        body_components_executed_by_iterate: set[str] = set()

        for comp_id in subjob_plan.component_ids:
            # Skip body components already executed inside an iterate body loop
            if comp_id in body_components_executed_by_iterate:
                logger.debug(
                    "Skipping %s in subjob loop -- already executed by iterate body", comp_id
                )
                continue

            # Skip components not in our registry (unknown types)
            if comp_id not in self.components:
                logger.warning("Component %s not in components dict, skipping", comp_id)
                continue

            # Safety net: check inputs are ready
            if not self.output_router.are_inputs_ready(comp_id):
                component = self.components[comp_id]
                if component.inputs:
                    logger.warning(
                        "Component %s inputs not ready despite topological sort, skipping",
                        comp_id,
                    )
                    continue

            # Execute the component
            comp_result = self._execute_component(comp_id)

            # Iterate branch: if this is an iterate component, drive the body loop
            if comp_result == "success":
                component = self.components.get(comp_id)
                if component is not None and getattr(component, "is_iterate_component", False):
                    try:
                        body_plan = self.execution_plan.get_iterate_body_plan(comp_id)
                    except KeyError:
                        body_plan = None
                    if body_plan is not None:
                        self._execute_iterate_body(component, body_plan)
                        # Body components are now considered executed for trigger evaluation;
                        # track them so the outer loop skips them.
                        for body_id in body_plan.component_ids:
                            self.executed_components.add(body_id)
                            body_components_executed_by_iterate.add(body_id)
                            # Mark as success in trigger_manager so OnSubjobOk can fire
                            # for the parent subjob (body may not have run if 0 iterations)
                            if body_id not in self.trigger_manager.component_status:
                                self.trigger_manager.set_component_status(body_id, "success")

            if comp_result == "error":
                # Check die_on_error from resolved config (set during component.execute())
                component = self.components[comp_id]
                die_on_error = component.die_on_error

                if die_on_error:
                    # Mark remaining components in this subjob as skipped
                    remaining_idx = subjob_plan.component_ids.index(comp_id) + 1
                    for remaining_id in subjob_plan.component_ids[remaining_idx:]:
                        if remaining_id not in self.executed_components:
                            self.execution_stats[remaining_id] = {"status": "skipped"}
                    subjob_failed = True
                    break
                else:
                    # Continue but mark failure
                    subjob_failed = True
                    logger.info(
                        "Component %s failed with die_on_error=False, continuing subjob",
                        comp_id,
                    )

            # After each component: fire OnComponentOk/OnComponentError triggers
            self._fire_component_triggers(comp_id, comp_result)

            if self._job_terminated:
                return "error"

        # After all components in subjob complete:
        # Clear internal subjob flows (preserving cross-subjob flows for pending consumers)
        self.output_router.clear_subjob_flows(
            subjob_plan.component_set, self.executed_components
        )

        return "error" if subjob_failed else "success"

    # ------------------------------------------------------------------
    # Iterate body execution (Phase 10)
    # ------------------------------------------------------------------

    def _execute_iterate_body(self, iter_component: Any, body_plan: SubjobPlan) -> None:
        """Run the body subgraph once per iteration item produced by the iterate component.

        Updates iter_component.stats with cumulative counts and per-iter timing.
        Accumulates body REJECT flows into a buffer and routes them as the iterate
        component's reject output at completion (D-D4).

        Body component triggers fire per iteration (D-C1). Triggers OUT OF the
        iterate source fire exactly once after all iterations -- handled by the
        caller's trigger-firing logic after this method returns (D-C2).

        Args:
            iter_component: The iterate component (BaseIterateComponent subclass).
                execute() has already been called -- prepare_iterations/iteration_iter ready.
            body_plan: Pre-computed body SubjobPlan from ExecutionPlan.
        """
        cid = iter_component.id
        body_component_set = body_plan.component_set
        reject_buffer: list[pd.DataFrame] = []

        iter_count_attempted = 0
        iter_count_ok = 0
        iter_count_err = 0
        iter_times: list[float] = []
        iter_start_total = time.time()

        # Scope mechanism: track depth (D-A6)
        iter_component._iterate_depth = self._current_iterate_depth + 1
        self._current_iterate_depth += 1

        try:
            total_hint = iter_component.total_iterations
            logger.info(
                "[%s] Starting iterate: %d items, %d components in body",
                cid, total_hint, len(body_plan.component_ids),
            )

            for index, item in enumerate(iter_component.iteration_iter, start=1):
                # Hook 3: should_stop (D-A5.3)
                if iter_component.should_stop(item, index):
                    break

                # Hook 4: before_iteration (D-A5.4)
                iter_component.before_iteration(item, index)

                # Set CURRENT_ITERATION before body runs (D-F5)
                self.global_map.put(f"{cid}_CURRENT_ITERATION", index)

                # Hook 5: set_iteration_globalmap (D-A5.5)
                iter_component.set_iteration_globalmap(item)

                # Per-iteration logging placeholder (D-H3; full logging in Phase 10-06)
                logger.debug("[%s] Iteration %d of %d", cid, index, total_hint)

                # Run the body subjob plan
                t0 = time.time()
                iter_count_attempted += 1
                body_failed = False

                try:
                    body_result = self._execute_subjob_plan(body_plan)
                    if body_result == "error":
                        body_failed = True
                except ComponentExecutionError as e:
                    exit_code = getattr(e, "exit_code", None)
                    if exit_code is not None:
                        # tDie inside body -> kill entire job (D-E5)
                        raise
                    body_failed = True
                    # Hook 8: on_iteration_error (D-A5.8)
                    if not iter_component.on_iteration_error(item, index, e):
                        raise

                iter_time = time.time() - t0
                iter_times.append(iter_time)

                # Drain body REJECT flows for this iteration
                iter_rejects = self.output_router.drain_reject_flows(body_component_set)
                for rej_df in iter_rejects.values():
                    if rej_df is not None and not rej_df.empty:
                        reject_buffer.append(rej_df)

                # Hook 7: after_iteration (D-A5.7)
                body_stats = self._snapshot_body_stats(body_plan)
                iter_component.after_iteration(item, index, body_stats=body_stats)

                if body_failed:
                    iter_count_err += 1
                    # Check if any failed body component has die_on_error=True (D-E6)
                    # If so, stop the iterate loop after draining this iteration's rejects
                    if self._any_body_die_on_error(body_plan):
                        # Reset body state before breaking
                        for body_id in body_plan.component_ids:
                            if body_id in self.components:
                                self.components[body_id].reset()
                            self.executed_components.discard(body_id)
                        self.output_router.clear_partial_subjob_flows(
                            body_component_set, self.executed_components
                        )
                        break
                else:
                    iter_count_ok += 1

                # Reset body components for next iteration (EXEC-05, D-I1)
                for body_id in body_plan.component_ids:
                    if body_id in self.components:
                        self.components[body_id].reset()
                    # Remove from executed_components so they re-execute next iter
                    self.executed_components.discard(body_id)

                # Clear body data flows (partial clear preserving cross-subjob consumers)
                self.output_router.clear_partial_subjob_flows(
                    body_component_set, self.executed_components
                )

                # Check for tDie termination
                if self._job_terminated:
                    break

            # Hook 9: finalize (D-A5.9) -- called even on early stop
            iter_component.finalize()

        finally:
            self._current_iterate_depth -= 1

        # Iterate-end log (D-H2)
        total_elapsed = time.time() - iter_start_total
        logger.info(
            "[%s] Iterate complete: %d OK, %d errors, total elapsed=%.2fs",
            cid, iter_count_ok, iter_count_err, total_elapsed,
        )

        # Build iterate component's final stats (D-D1, D-D2)
        iter_component.stats["NB_LINE"] = iter_count_attempted
        iter_component.stats["NB_LINE_OK"] = iter_count_ok
        iter_component.stats["NB_LINE_REJECT"] = iter_count_err
        if iter_times:
            iter_component.stats["total_iter_time"] = sum(iter_times)
            iter_component.stats["avg_iter_time"] = sum(iter_times) / len(iter_times)
            iter_component.stats["slowest_iter_time"] = max(iter_times)
            iter_component.stats["fastest_iter_time"] = min(iter_times)
            iter_component.stats["slowest_iter_index"] = iter_times.index(max(iter_times)) + 1
            iter_component.stats["fastest_iter_index"] = iter_times.index(min(iter_times)) + 1

        # Concat REJECT buffer and route as iterate component's reject output
        if reject_buffer:
            accumulated_reject = pd.concat(reject_buffer, ignore_index=True)
            self.output_router.route_outputs(cid, {"reject": accumulated_reject})

        # Update globalMap (NB_LINE etc.)
        iter_component._update_global_map()

        # Mark iterate-source completed; trigger firing happens in caller (_execute_subjob_plan)
        self.executed_components.add(cid)

    def _any_body_die_on_error(self, body_plan: SubjobPlan) -> bool:
        """Check if any failed body component has die_on_error=True.

        Used to decide whether to break the iterate loop early (D-E6).

        Args:
            body_plan: The body subgraph plan.

        Returns:
            True if any failed body component has die_on_error=True.
        """
        for body_id in body_plan.component_ids:
            comp = self.components.get(body_id)
            if comp is None:
                continue
            comp_stats = self.execution_stats.get(body_id, {})
            if comp_stats.get("status") == "error" and getattr(comp, "die_on_error", False):
                return True
        return False

    def _snapshot_body_stats(self, body_plan: SubjobPlan) -> dict:
        """Capture a point-in-time snapshot of body component stats.

        Args:
            body_plan: The body subgraph plan.

        Returns:
            dict mapping comp_id to its current execution_stats entry.
        """
        return {
            bid: dict(self.execution_stats.get(bid, {}))
            for bid in body_plan.component_ids
        }

    def _log_iteration_progress(
        self,
        iter_component: Any,
        index: int,
        total_hint: int,
    ) -> None:
        """Log per-iteration progress. Placeholder for Phase 10-06 full logging.

        Args:
            iter_component: The iterate component.
            index: 1-based iteration index.
            total_hint: Total expected iterations (-1 if unbounded).
        """
        logger.debug("[%s] Iteration %d / %d", iter_component.id, index, total_hint)

    # ------------------------------------------------------------------
    # Component execution
    # ------------------------------------------------------------------

    def _execute_component(self, comp_id: str) -> str:
        """Execute a single component.

        Gets input data from OutputRouter, calls component.execute(),
        routes outputs back through OutputRouter, and records stats.

        Args:
            comp_id: The component identifier.

        Returns:
            'success' or 'error'.
        """
        component = self.components[comp_id]
        logger.info("Executing component: %s (%s)", comp_id, component.__class__.__name__)

        try:
            # Get input data
            input_data = self.output_router.get_input_data(comp_id)

            # Execute
            start_time = time.time()
            result = component.execute(input_data)
            execution_time = time.time() - start_time

            # Route outputs
            if result:
                self.output_router.route_outputs(comp_id, result)

            # Store execution stats
            stats = component.get_stats()
            stats["execution_time"] = execution_time
            self.execution_stats[comp_id] = stats

            # Update trigger manager
            self.trigger_manager.set_component_status(comp_id, "success")
            self.executed_components.add(comp_id)

            logger.info(
                "Component %s completed: %d rows processed in %.3fs",
                comp_id, stats.get("NB_LINE_OK", 0), execution_time,
            )
            return "success"

        except Exception as e:
            logger.error("Component %s failed: %s", comp_id, e)

            # Check for tDie: exit_code attribute means job should stop (D-13)
            # BaseComponent.execute() wraps _process() exceptions in a new
            # ComponentExecutionError, so exit_code may be on the cause chain.
            exit_code = getattr(e, "exit_code", None)
            if exit_code is None and hasattr(e, "cause") and e.cause is not None:
                exit_code = getattr(e.cause, "exit_code", None)
            if exit_code is None and e.__cause__ is not None:
                exit_code = getattr(e.__cause__, "exit_code", None)

            if exit_code is not None:
                self._job_terminated = True
                self._termination_error = e
                self.trigger_manager.set_component_status(comp_id, "error")
                self.failed_components.add(comp_id)
                self.executed_components.add(comp_id)
                self.execution_stats[comp_id] = {
                    "status": "error",
                    "error": str(e),
                    "exit_code": exit_code,
                }
                # Do NOT re-raise -- let execute_job handle via _job_terminated flag
                return "error"

            # Normal error handling
            self.trigger_manager.set_component_status(comp_id, "error")
            self.failed_components.add(comp_id)
            self.executed_components.add(comp_id)
            self.execution_stats[comp_id] = {
                "status": "error",
                "error": str(e),
            }
            return "error"

    # ------------------------------------------------------------------
    # Trigger firing
    # ------------------------------------------------------------------

    def _fire_component_triggers(self, comp_id: str, comp_result: str) -> None:
        """Fire OnComponentOk/OnComponentError triggers after each component.

        This is the ONLY place where per-component triggers fire.
        OnSubjobOk triggers are NEVER checked here -- they fire in
        _collect_triggered_subjobs after the entire subjob completes.

        If a triggered component is in a different subjob, that subjob
        is queued for execution via _component_triggered_subjobs.

        Args:
            comp_id: The component that just completed.
            comp_result: 'success' or 'error'.
        """
        # TriggerManager.get_triggered_components handles OnComponentOk/OnComponentError
        # evaluation internally. It also handles OnSubjobOk but that only fires
        # when ALL components in the subjob are complete, so it naturally won't fire
        # here mid-subjob (the check in TriggerManager._check_subjob_ok verifies
        # all components have status).
        #
        # NOTE (WR-04): When the last component of a subjob completes here,
        # OnSubjobOk/OnSubjobError MAY fire via get_triggered_components'
        # idempotency set. _collect_triggered_subjobs also evaluates these
        # triggers but uses _already_executed_subjobs() and _attempted_subjobs
        # guards to prevent duplicate subjob execution. This dual-path is safe
        # but relies on the dedup in execute_job's pending_subjobs loop.
        triggered = self.trigger_manager.get_triggered_components(comp_id)
        if triggered:
            logger.debug("Component triggers from %s: %s", comp_id, triggered)
            # Check if any triggered components are in different subjobs
            comp_to_subjob = self.execution_plan.component_to_subjob
            source_subjob = comp_to_subjob.get(comp_id)
            for target_comp in triggered:
                target_subjob = comp_to_subjob.get(target_comp)
                if target_subjob and target_subjob != source_subjob:
                    if target_subjob not in self._already_executed_subjobs():
                        self._component_triggered_subjobs.append(target_subjob)
                        logger.info(
                            "OnComponentOk cross-subjob trigger: %s -> %s (subjob %s)",
                            comp_id, target_comp, target_subjob,
                        )

    def _collect_triggered_subjobs(self, subjob_id: str, subjob_result: str) -> list[str]:
        """Collect subjobs triggered after a subjob completes.

        Uses ExecutionPlan to find trigger edges from this subjob,
        then evaluates which targets should fire based on the subjob result.

        This fires OnSubjobOk/OnSubjobError/RunIf triggers -- NOT
        OnComponentOk triggers (those fire in _fire_component_triggers).

        Args:
            subjob_id: The subjob that just completed.
            subjob_result: 'success' or 'error'.

        Returns:
            List of subjob IDs to execute next. Caller appends to deque.
        """
        triggered_subjobs: list[str] = []
        edges = self.execution_plan.get_all_trigger_edges_from_subjob(subjob_id)

        for edge in edges:
            if edge.to_subjob is None:
                continue

            # Already executed -- skip
            if edge.to_subjob in self._already_executed_subjobs():
                continue

            should_fire = False

            if edge.trigger_type == "OnSubjobOk":
                if subjob_result == "success":
                    should_fire = self._check_trigger_via_manager(edge)

            elif edge.trigger_type == "OnSubjobError":
                if subjob_result == "error":
                    should_fire = self._check_trigger_via_manager(edge)

            elif edge.trigger_type == "RunIf":
                # RunIf evaluates condition regardless of success/error (D-08)
                should_fire = self._check_trigger_via_manager(edge)

            elif edge.trigger_type in ("OnComponentOk", "OnComponentError"):
                # Component-level triggers are handled in _fire_component_triggers
                # They should not be re-processed here at the subjob level
                continue

            if should_fire:
                triggered_subjobs.append(edge.to_subjob)
                logger.info(
                    "Trigger %s fired: subjob %s -> subjob %s",
                    edge.trigger_type, subjob_id, edge.to_subjob,
                )

        return triggered_subjobs

    def _check_trigger_via_manager(self, edge) -> bool:
        """Check if a trigger edge should fire using the TriggerManager.

        Looks up matching triggers in TriggerManager and evaluates them.

        Args:
            edge: TriggerEdge from ExecutionPlan.

        Returns:
            True if the trigger should fire.
        """
        for trigger in self.trigger_manager.triggers:
            if (
                trigger.type.value == edge.trigger_type
                and trigger.from_component == edge.from_component
                and trigger.to_component == edge.to_component
            ):
                return self.trigger_manager.should_fire_trigger(trigger, edge.from_component)
        return False

    def _already_executed_subjobs(self) -> set[str]:
        """Return set of subjob IDs that have already been executed.

        Tracked incrementally via _executed_subjobs (populated in
        _execute_subjob) instead of recomputing from scratch each call.

        Returns:
            Set of subjob IDs whose components have all been executed or attempted.
        """
        return self._executed_subjobs

    # ------------------------------------------------------------------
    # Stall diagnostics
    # ------------------------------------------------------------------

    def _count_accounted_components(self) -> int:
        """Count components that are executed, skipped, or in untriggered subjobs.

        Returns:
            Number of components accounted for (not stuck).
        """
        accounted = set(self.executed_components)
        # Add skipped components
        for comp_id, stats in self.execution_stats.items():
            if stats.get("status") == "skipped":
                accounted.add(comp_id)
        return len(accounted)

    def _build_stall_diagnostics(self, unexecuted: set[str]) -> str:
        """Build actionable stall diagnostic message.

        Names each stuck component, its subjob, and missing input flows.

        Args:
            unexecuted: Set of component IDs that never executed.

        Returns:
            Multi-line diagnostic string.
        """
        comp_to_subjob = self.execution_plan.component_to_subjob
        lines = []

        for comp_id in sorted(unexecuted):
            subjob_id = comp_to_subjob.get(comp_id, "unknown")
            component = self.components.get(comp_id)

            # Find missing input flows
            missing_flows = []
            if component and hasattr(component, "inputs") and component.inputs:
                for flow_name in component.inputs:
                    if not self.output_router.has_flow_data(flow_name):
                        missing_flows.append(flow_name)

            if missing_flows:
                flows_str = ", ".join(missing_flows)
                lines.append(
                    f"  - {comp_id} (subjob {subjob_id}): waiting on input flows [{flows_str}]"
                )
            else:
                lines.append(
                    f"  - {comp_id} (subjob {subjob_id}): no missing inputs (subjob may not have been triggered)"
                )

        return "\n".join(lines)
