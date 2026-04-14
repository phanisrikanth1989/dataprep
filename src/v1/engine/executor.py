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

from .base_component import BaseComponent, ComponentStatus
from .exceptions import ComponentExecutionError, ConfigurationError
from .execution_plan import ExecutionPlan
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

        This is THE building block that Phase 10 iterate support will call
        in a loop per iteration item.

        Args:
            subjob_id: The subjob identifier.

        Returns:
            'success' if all components passed, 'error' otherwise.
        """
        subjob_plan = self.execution_plan.get_subjob_plan(subjob_id)
        subjob_failed = False

        for comp_id in subjob_plan.component_ids:
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

            if comp_result == "error":
                # Check die_on_error config (resolved config)
                component = self.components[comp_id]
                die_on_error = component._original_config.get("die_on_error", True)

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

        Used to prevent duplicate subjob execution.

        Returns:
            Set of subjob IDs whose components have all been executed or attempted.
        """
        executed_subjobs: set[str] = set()

        for subjob_id in self.execution_plan.all_subjob_ids:
            plan = self.execution_plan.get_subjob_plan(subjob_id)
            # A subjob is "done" if all its components have been executed
            if plan.component_set.issubset(self.executed_components):
                executed_subjobs.add(subjob_id)
            # Also check if any component was marked as skipped
            elif all(
                comp_id in self.executed_components
                or self.execution_stats.get(comp_id, {}).get("status") == "skipped"
                for comp_id in plan.component_ids
            ):
                executed_subjobs.add(subjob_id)

        return executed_subjobs

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
