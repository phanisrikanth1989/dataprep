"""Base class for iterate components (tFileList, tFlowToIterate, tForeach).

Iterate components produce a sequence of iteration items. Each item triggers
re-execution of downstream subjob components via the engine's iterate loop
(Phase 10, implemented in Executor._execute_iterate_body).

8-Hook Lifecycle (D-A5 -- Phase 10):
    1. prepare()                        -- one-time setup before iter loop
    2. prepare_iterations(input_data)   -- abstract; returns Iterator[ItemType]
    Per iteration:
      3. should_stop(item, index)       -- early termination guard
      4. before_iteration(item, index)  -- pre-iter hook
      5. set_iteration_globalmap(item)  -- abstract; push iter vars to globalMap
      (body subjob executes via Executor._execute_iterate_body)
      7. after_iteration(item, index)   -- post-iter hook
    9. finalize()                       -- one-time teardown after loop

Hook 8 (on_iteration_error) removed: Executor._execute_component catches all
component exceptions and converts them to string status returns ("error"). The
except ComponentExecutionError arm in the iterate loop was therefore unreachable
in production. Hook 8 is removed to match the errors-as-statuses architecture.
Body component errors are signalled via _execute_subjob_plan returning "error",
not by re-raising. (CR-03 gap closure, 2026-05-05)

The Executor drives the per-iteration loop in _execute_iterate_body. This class
only prepares state and exposes hooks; it does NOT run the loop itself.

execute() Override (D-A2):
    Skips data-pipeline lifecycle steps that do not apply to orchestration
    components (output schema validation, REJECT routing, batch/streaming
    dispatch, _count_input_rows). Keeps: status transitions, _original_config
    snapshot/restore (EXEC-06), _validate_config, _resolve_expressions,
    _update_global_map.

ITER-11 Fix (D-F7):
    get_next_iteration_context() writes f"{self.id}_CURRENT_ITERATION"
    (NOT _CURRENT_ITERATE). Canonical key per Talaxie tFlowToIterate_main.javajet.

_iterate_depth Field (D-A6):
    Records the iterate stack depth. Executor writes the value at loop start.
    Phase 10 enforces depth=1 (ConfigurationError on nesting) via ExecutionPlan.
    Phase 10.1 removes the depth check; the scope mechanism is already wired.
"""
import copy
import logging
import time
from abc import abstractmethod
from collections.abc import Iterator
from typing import Any, Dict, Optional

import pandas as pd

from .base_component import BaseComponent, ComponentStatus
from .exceptions import ComponentExecutionError, ConfigurationError

logger = logging.getLogger(__name__)


class BaseIterateComponent(BaseComponent):
    """Base class for components that produce iterations.

    Iterate components (tFileList, tFlowToIterate, tForeach) work differently
    from regular components:
        - They prepare an Iterator of items via prepare_iterations()
        - Each item triggers re-execution of the downstream body subjob
        - They set specific globalMap variables per iteration via
          set_iteration_globalmap()
        - The Executor drives the loop; execute() only primes the state

    Subclasses must implement _validate_config(), prepare_iterations(),
    and set_iteration_globalmap(). Subclasses MUST NOT override execute().

    See module docstring for full 8-hook lifecycle.
    """

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------

    def __init__(
        self,
        component_id: str,
        config: dict,
        global_map=None,
        context_manager=None,
    ):
        """Initialize iterate component.

        Args:
            component_id: Unique identifier for this component instance.
            config: Component configuration dictionary.
            global_map: GlobalMap instance for stats and variable storage.
            context_manager: ContextManager instance for variable resolution.
        """
        super().__init__(component_id, config, global_map, context_manager)
        # Executor branch flag (D-B2): Executor checks is_iterate_component=True
        # to branch into _execute_iterate_body instead of the normal subjob loop.
        self.is_iterate_component = True
        # Iterator of items produced by prepare_iterations() (D-A3).
        # Bounded subclasses yield from iter(list); unbounded yield forever.
        self.iteration_iter: Iterator[Any] = iter(())
        # total_iterations: positive = bounded, -1 = unbounded (sentinel).
        self.total_iterations: int = -1
        # Index advances as the Executor consumes items via get_next_iteration_context.
        self.current_iteration_index: int = 0
        # Per-iteration stats accumulation list (Executor appends per iteration).
        self.iteration_stats: list = []
        # Iterate stack depth (D-A6): Executor sets this at loop start.
        # Phase 10 enforces depth=1 via ExecutionPlan nested-iterate check.
        # Phase 10.1 lifts the check; the field is already wired.
        self._iterate_depth: int = 0

    # ------------------------------------------------------------------
    # execute() Override (D-A2)
    # ------------------------------------------------------------------

    def execute(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Iterate-specific execute(). Skips data-pipeline lifecycle steps.

        Keeps: status transitions, _original_config snapshot/restore (EXEC-06),
        _validate_config, _resolve_expressions.
        Skips: output schema validation, REJECT routing, batch/streaming dispatch,
        _count_input_rows, _update_stats_from_result.

        After this returns, the Executor's _execute_iterate_body drives the loop.

        Args:
            input_data: Input DataFrame (for tFlowToIterate) or None (for
                tFileList, source-type iterate components).

        Returns:
            dict with main=None, reject=None, stats=self.stats. Iterate
            components produce no DataFrame output; the output is body-subjob
            re-execution and globalMap variable puts.

        Raises:
            ConfigurationError: If _validate_config() raises.
            ComponentExecutionError: If any other step fails.
        """
        self.status = ComponentStatus.RUNNING
        start = time.time()
        try:
            # Per-iteration config freshness (EXEC-06 / D-I2):
            # _original_config deepcopy re-derives config to clean state each call.
            self.config = copy.deepcopy(self._original_config)

            # Validate structure (D-L4: structural checks only, no content checks).
            self._validate_config()

            # Resolve Java markers + context variables (D-A2: keep this step).
            # Iterate components may have {{java}} expressions in MAP entries.
            self._resolve_expressions()

            # Read die_on_error from resolved config.
            self.die_on_error = bool(self.config.get("die_on_error", False))

            # Hook 1: one-time setup before iter loop (D-A5.1).
            self.prepare()

            # Hook 2: produce iteration iterator (D-A5.2 / D-A3).
            # Subclass sets self.total_iterations = len(items) if bounded,
            # leaves total_iterations = -1 if unbounded.
            self.iteration_iter = self.prepare_iterations(input_data)

            # Reset iteration index for fresh execution.
            self.current_iteration_index = 0

            # Executor flips status to SUCCESS after iterate completes.
            self.execution_time = time.time() - start
            return {
                "main": None,   # iterate components produce no main DataFrame
                "reject": None, # reject is accumulated by Executor across iterations
                "stats": self.stats,
            }

        except ConfigurationError:
            self.status = ComponentStatus.ERROR
            raise
        except Exception as exc:
            self.status = ComponentStatus.ERROR
            self.execution_time = time.time() - start
            raise ComponentExecutionError(self.id, str(exc), cause=exc) from exc

    # ------------------------------------------------------------------
    # Lifecycle Hooks (D-A5) -- override in subclasses as needed
    # ------------------------------------------------------------------

    def prepare(self) -> None:
        """Hook 1: one-time setup before the iter loop. Default no-op."""
        pass

    @abstractmethod
    def prepare_iterations(self, input_data: Optional[pd.DataFrame] = None) -> Iterator[Any]:
        """Hook 2 (abstract): produce iteration items as an Iterator.

        Bounded subclasses should yield from iter([...]) and set
        self.total_iterations = len(items). Unbounded subclasses
        (tInfiniteLoop, future) yield forever and rely on should_stop().

        Args:
            input_data: Input DataFrame (for tFlowToIterate) or None.

        Returns:
            Iterator over iteration items. The Executor drives consumption.
        """
        raise NotImplementedError(f"[{self.id}] must implement prepare_iterations()")

    def should_stop(self, item: Any, index: int) -> bool:
        """Hook 3: per-item early termination. Default False (continue).

        Args:
            item: The current iteration item.
            index: 0-based iteration index.

        Returns:
            True to stop the loop before executing body for this item.
        """
        return False

    def before_iteration(self, item: Any, index: int) -> None:
        """Hook 4: pre-iteration setup. Default no-op.

        Args:
            item: The current iteration item.
            index: 0-based iteration index.
        """
        pass

    @abstractmethod
    def set_iteration_globalmap(self, item: Any) -> None:
        """Hook 5 (abstract): push iteration variables to globalMap.

        Called per-iteration BEFORE the body subjob executes. Subclasses
        set Talend-parity globalMap keys (e.g., tFileList_1_CURRENT_FILE).
        Always guard with: if self.global_map: ...

        Args:
            item: The current iteration item.
        """
        raise NotImplementedError(f"[{self.id}] must implement set_iteration_globalmap()")

    def after_iteration(
        self,
        item: Any,
        index: int,
        body_stats: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Hook 7: post-iteration callback. Default no-op.

        Args:
            item: The current iteration item.
            index: 0-based iteration index.
            body_stats: Stats dict from the body subjob execution, or None.
        """
        pass

    def finalize(self) -> None:
        """Hook 9: one-time teardown after the iterate loop. Default no-op.

        Runs even on early-stop (Executor calls it in a finally block).
        """
        pass

    # ------------------------------------------------------------------
    # Iteration Query Methods (used by Executor iterate loop)
    # ------------------------------------------------------------------

    def has_next_iteration(self) -> bool:
        """Check if there are more iteration items to process.

        For bounded iterators (total_iterations >= 0), uses the index counter.
        For unbounded iterators (total_iterations == -1), always returns True
        until the caller breaks via should_stop() or exhausts the iterator.

        Returns:
            True if more items may exist.
        """
        if self.total_iterations == -1:
            # Unbounded: caller controls termination via should_stop()
            return True
        return self.current_iteration_index < self.total_iterations

    def get_next_iteration_context(self) -> Dict[str, Any]:
        """Get next iteration item and advance index. Sets globalMap vars.

        Calls set_iteration_globalmap() to push the item's variables to
        globalMap, then advances the iteration counter.

        Writes f"{self.id}_CURRENT_ITERATION" to globalMap (ITER-11 / D-F7).
        Canonical key per Talaxie tFlowToIterate_main.javajet.

        Returns:
            dict with 'item' and 'index' keys, or empty dict if exhausted.
        """
        if not self.has_next_iteration():
            return {}

        try:
            item = next(self.iteration_iter)
        except StopIteration:
            return {}

        self.set_iteration_globalmap(item)
        self.current_iteration_index += 1

        if self.global_map:
            # ITER-11 / D-F7: canonical key is _CURRENT_ITERATION (NOT _CURRENT_ITERATE)
            self.global_map.put(
                f"{self.id}_CURRENT_ITERATION", self.current_iteration_index
            )

        logger.debug(
            "[%s] Iteration %s - index %s",
            self.id,
            self.current_iteration_index,
            self.current_iteration_index - 1,
        )

        return {"item": item, "index": self.current_iteration_index}

    # ------------------------------------------------------------------
    # Stats Accumulation
    # ------------------------------------------------------------------

    def update_iteration_stats(self, iteration_stats: dict) -> None:
        """Accumulate stats from one iteration into component stats.

        Called by the Executor after each iteration completes to roll up
        per-iteration statistics into the component's cumulative stats.

        Args:
            iteration_stats: Dict with NB_LINE, NB_LINE_OK, NB_LINE_REJECT
                keys from the executed iteration.
        """
        self.stats["NB_LINE"] += iteration_stats.get("NB_LINE", 0)
        self.stats["NB_LINE_OK"] += iteration_stats.get("NB_LINE_OK", 0)
        self.stats["NB_LINE_REJECT"] += iteration_stats.get("NB_LINE_REJECT", 0)

    # ------------------------------------------------------------------
    # Logging hook (D-H3) -- override in subclasses for component-specific info
    # ------------------------------------------------------------------

    def get_iter_key_info(self, item: Any, index: int) -> str:
        """Return a short key-info string for per-iteration log lines (D-H3).

        Called by the Executor (via iterate_logging.log_iteration_progress) to
        populate the key_info field in the D-H3 per-iteration log line.

        Default implementation returns "index=<index>". Subclasses override to
        provide component-specific information (e.g. FileList returns
        "file=<path>", FlowToIterate returns "row_index=<index>").

        Args:
            item: The current iteration item (type varies by subclass).
            index: 1-based iteration index.

        Returns:
            A short ASCII-only string describing the current iteration.
        """
        return f"index={index}"

    # ------------------------------------------------------------------
    # finalize_iterations -- backward-compat synonym for finalize()
    # ------------------------------------------------------------------

    def finalize_iterations(self) -> None:
        """Backward-compat stub. Delegates to finalize().

        Kept so any callers from before the Phase 10 refactor still work.
        New code should call finalize() directly.
        """
        self.finalize()

    # ------------------------------------------------------------------
    # _process() -- delegates to execute() override
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Iterate components do not use the BaseComponent._process path.

        Raises:
            NotImplementedError: Always. Use the iterate lifecycle hooks instead.
        """
        raise NotImplementedError(
            f"[{self.id}] Iterate components do not implement _process; "
            "use the lifecycle hooks (prepare_iterations, set_iteration_globalmap, "
            "before_iteration, after_iteration, finalize)."
        )

    # ------------------------------------------------------------------
    # Reset (Override for iterate-specific state)
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset iterate state for re-execution.

        Clears iterate-specific state (iterator, index, count, depth) in
        addition to the base component state (stats, status, globalMap).
        """
        super().reset()
        self.iteration_iter = iter(())
        self.current_iteration_index = 0
        self.total_iterations = -1
        self.iteration_stats = []
        self._iterate_depth = 0
