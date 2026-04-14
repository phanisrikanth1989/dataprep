"""Base class for iterate components (tFileList, tFlowToIterate, tForeach).

Iterate components produce a sequence of iteration items. Each item triggers
re-execution of downstream subjob components via the engine's iterate loop (Phase 10).

Unlike the old implementation, this does NOT override execute(). Instead it hooks
into the BaseComponent lifecycle via _process(), which prepares iteration items.
The engine's iterate loop consumes them via has_next_iteration() and
get_next_iteration_context().
"""
import logging
from abc import abstractmethod
from typing import Any, Optional

import pandas as pd

from .base_component import BaseComponent, ComponentStatus

logger = logging.getLogger(__name__)


class BaseIterateComponent(BaseComponent):
    """Base class for components that produce iterations.

    Iterate components (tFileList, tFlowToIterate, tForeach) work differently
    from regular components:
        - They prepare a list of items to iterate over via ``prepare_iterations()``
        - Each item triggers re-execution of downstream subjob via the engine
        - They set specific globalMap variables for each iteration via
          ``set_iteration_globalmap()``

    The iterate lifecycle:
        1. ``execute()`` (inherited from BaseComponent) calls ``_process()``
        2. ``_process()`` calls ``prepare_iterations()`` to populate iteration items
        3. Engine iterate loop calls ``has_next_iteration()`` / ``get_next_iteration_context()``
        4. After all iterations, engine calls ``finalize_iterations()``
    """

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
        self.is_iterate_component = True
        self.iteration_items: list[Any] = []
        self.current_iteration_index: int = 0
        self.total_iterations: int = 0

    # ------------------------------------------------------------------
    # BaseComponent hook -- implements abstract _process()
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Prepare iteration items. The engine's iterate loop consumes them.

        Calls the abstract ``prepare_iterations()`` method which subclasses
        must implement to populate the iteration items list.

        Args:
            input_data: Input DataFrame (for tFlowToIterate) or None
                (for tFileList, tForeach).

        Returns:
            dict with 'main' key (pass-through input) and 'reject' as None.
        """
        self.iteration_items = self.prepare_iterations(input_data)
        self.total_iterations = len(self.iteration_items)
        self.current_iteration_index = 0

        logger.info(
            f"[{self.id}] Prepared {self.total_iterations} iteration items"
        )

        return {"main": input_data, "reject": None}

    # ------------------------------------------------------------------
    # Abstract Methods -- Subclasses MUST Implement
    # ------------------------------------------------------------------

    @abstractmethod
    def prepare_iterations(self, input_data: Optional[pd.DataFrame] = None) -> list[Any]:
        """Prepare the list of items to iterate over. Subclass MUST implement.

        Args:
            input_data: Input DataFrame (for tFlowToIterate) or None
                (for tFileList, tForeach).

        Returns:
            List of iteration items. Each item will be passed to
            ``set_iteration_globalmap()`` during iteration.
        """
        ...

    @abstractmethod
    def set_iteration_globalmap(self, item: Any) -> None:
        """Set globalMap variables for one iteration item. Subclass MUST implement.

        Follow Talend naming conventions for globalMap keys. For example,
        tFileList sets ``tFileList_1_CURRENT_FILE``, ``tFileList_1_CURRENT_FILEPATH``, etc.

        Args:
            item: The current iteration item from ``iteration_items``.
        """
        ...

    # ------------------------------------------------------------------
    # Iteration Query Methods (used by engine iterate loop)
    # ------------------------------------------------------------------

    def has_next_iteration(self) -> bool:
        """Check if there are more iteration items to process.

        Returns:
            True if there are remaining items.
        """
        return self.current_iteration_index < self.total_iterations

    def get_next_iteration_context(self) -> dict[str, Any]:
        """Get next iteration item and advance index. Sets globalMap vars.

        Calls ``set_iteration_globalmap()`` to push the item's variables
        to globalMap, then advances the iteration counter.

        Returns:
            dict with 'item' and 'index' keys, or empty dict if no more items.
        """
        if not self.has_next_iteration():
            return {}

        item = self.iteration_items[self.current_iteration_index]
        self.set_iteration_globalmap(item)
        self.current_iteration_index += 1

        if self.global_map:
            self.global_map.put(
                f"{self.id}_CURRENT_ITERATE", self.current_iteration_index
            )

        logger.debug(
            f"[{self.id}] Iteration {self.current_iteration_index}/"
            f"{self.total_iterations}"
        )

        return {"item": item, "index": self.current_iteration_index}

    def update_iteration_stats(self, iteration_stats: dict) -> None:
        """Accumulate stats from one iteration into component stats.

        Called by the engine after each iteration completes to roll up
        per-iteration statistics into the component's cumulative stats.

        Args:
            iteration_stats: Dict with NB_LINE, NB_LINE_OK, NB_LINE_REJECT
                keys from the executed iteration.
        """
        self.stats["NB_LINE"] += iteration_stats.get("NB_LINE", 0)
        self.stats["NB_LINE_OK"] += iteration_stats.get("NB_LINE_OK", 0)
        self.stats["NB_LINE_REJECT"] += iteration_stats.get("NB_LINE_REJECT", 0)

    def finalize_iterations(self) -> None:
        """Called after all iterations complete.

        Updates stats to reflect the total number of iterations processed
        and pushes final stats to globalMap.
        """
        self.stats["NB_LINE"] = self.total_iterations
        self.stats["NB_LINE_OK"] = self.total_iterations
        self._update_global_map()

        logger.info(
            f"[{self.id}] Completed all {self.total_iterations} iterations"
        )

    # ------------------------------------------------------------------
    # Reset (Override for iterate-specific state)
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset iterate state for re-execution.

        Clears iterate-specific state (items, index, count) in addition
        to the base component state (stats, status, globalMap).
        """
        super().reset()
        self.iteration_items = []
        self.current_iteration_index = 0
        self.total_iterations = 0
