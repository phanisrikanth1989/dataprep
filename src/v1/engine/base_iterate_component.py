"""
Base class for iterate components that produce iterations instead of data flows
"""
from abc import abstractmethod
from typing import Any, Dict, List, Optional, Union
import pandas as pd
import logging

from .base_component import BaseComponent, ComponentStatus

logger = logging.getLogger(__name__)


class BaseIterateComponent(BaseComponent):
    """
    Base class for components that produce iterations (tFileList, tFlowToIterate,
    etc.)

    Iterate components work differently from regular components:
    - They prepare a list of items to iterate over
    - Each item triggers a re-execution of downstream subjob
    - They set specific globalMap variables for each iteration
    """

    def __init__(
        self,
        component_id: str,
        config: Dict[str, Any],
        global_map: Any = None,
        context_manager: Any = None
    ):
        super().__init__(component_id, config, global_map, context_manager)

        # Iteration state
        self.is_iterate_component = True
        self.iteration_items: List[Any] = []
        self.current_iteration_index = 0
        self.total_iterations = 0

        # Stats tracking across iterations
        self.aggregate_stats = {
            'NB_LINE': 0,
            'NB_LINE_OK': 0,
            'NB_LINE_REJECT': 0,
            'NB_ITERATION': 0
        }

    def execute(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Execute component to prepare iterations

        Returns:
            Dict with:
                - 'iterate': True (marker that this produces iterations)
                - 'iteration_count': Number of iterations prepared
        """
        self.status = ComponentStatus.RUNNING

        try:
            # Resolve context variables first
            if self.context_manager:
                self.config = self.context_manager.resolve_dict(self.config)

            # Prepare iteration items (implemented by child classes)
            self.prepare_iterations(input_data)

            self.total_iterations = len(self.iteration_items)
            self.current_iteration_index = 0

            # Update stats
            self.stats['NB_LINE'] = self.total_iterations
            self.aggregate_stats['NB_ITERATION'] = self.total_iterations
            self._update_global_map()

            self.status = ComponentStatus.SUCCESS

            logger.info(f"Component {self.id}: Prepared {self.total_iterations} iterations")

            return {
                'iterate': True,
                'iteration_count': self.total_iterations,
                'stats': self.stats.copy()
            }

        except Exception as e:
            self.status = ComponentStatus.ERROR
            self.error_message = str(e)
            logger.error(f"Component {self.id} failed to prepare iterations: {e}")
            raise

    def has_next_iteration(self) -> bool:
        """Check if there are more iterations"""
        return self.current_iteration_index < self.total_iterations

    def get_next_iteration_context(self) -> Optional[Any]:
        """
        Get next iteration item and advance counter

        Returns:
            Next iteration item or None if no more iterations
        """
        if not self.has_next_iteration():
            return None

        item = self.iteration_items[self.current_iteration_index]
        self.current_iteration_index += 1

        # Set iteration context in globalMap
        self.set_iteration_globalmap(item)

        # Update iteration counter in globalMap
        self.global_map.put(f"{self.id}_NB_ITERATE", self.current_iteration_index)
        self.global_map.put(f"{self.id}_CURRENT_ITERATION", self.
            current_iteration_index - 1)  # 0-based index

        logger.debug(f"Component {self.id}: Starting iteration {self.current_iteration_index}/{self.total_iterations}")

        return item

    def reset_iterations(self) -> None:
        """Reset iteration state for potential re-execution"""
        self.current_iteration_index = 0
        logger.debug(f"Component {self.id}: Reset iteration counter")

    def update_iteration_stats(self, stats: Dict[str, Any]) -> None:
        """
        Update aggregate statistics from iteration execution

        Args:
            stats: Statistics from the iteration execution
        """
        self.aggregate_stats['NB_LINE'] += stats.get('NB_LINE', 0)
        self.aggregate_stats['NB_LINE_OK'] += stats.get('NB_LINE_OK', 0)
        self.aggregate_stats['NB_LINE_REJECT'] += stats.get('NB_LINE_REJECT', 0)

        # Update component's own stats
        self.stats['NB_LINE_OK'] = self.aggregate_stats['NB_LINE_OK']
        self.stats['NB_LINE_REJECT'] = self.aggregate_stats['NB_LINE_REJECT']

        self._update_global_map()

    def finalize_iterations(self) -> None:
        """Called when all iterations are complete"""
        logger.info(f"Component {self.id}: Completed all {self.total_iterations} iterations")
        logger.info(f"  Aggregate stats: {self.aggregate_stats}")

        # Final update to globalMap
        for stat_name, stat_value in self.aggregate_stats.items():
            self.global_map.put(f"{self.id}_{stat_name}", stat_value)

    @abstractmethod
    def prepare_iterations(self, input_data: Optional[pd.DataFrame] = None) -> None:
        """
        Prepare the list of items to iterate over
        Must populate self.iteration_items

        Args:
            input_data: Input data (for tFlowToIterate) or None (for tFileList)
        """
        pass

    @abstractmethod
    def set_iteration_globalmap(self, item: Any) -> None:
        """
        Set globalMap variables for the current iteration
        Follow Talend naming conventions

        Args:
            item: Current iteration item
        """
        pass

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Not used for iterate components - they use execute() instead
        """
        raise NotImplementedError("Iterate components don't use _process method")
