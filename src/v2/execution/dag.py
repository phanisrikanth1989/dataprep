"""
DAG Builder for v2 Engine.

Builds and validates the execution graph from job configuration.
"""
import logging
from dataclasses import dataclass
from typing import Dict, List, Set, Optional

from ..config import JobConfig

logger = logging.getLogger(__name__)


@dataclass
class DAGNode:
    """A node in the execution DAG."""
    component_id: str
    component_type: str
    config: Dict
    upstream: Set[str]  # Component IDs that feed into this
    downstream: Set[str]  # Component IDs this feeds into


class DAGValidationError(Exception):
    """Error during DAG validation."""
    pass


class DAG:
    """
    Directed Acyclic Graph for job execution.

    Provides:
    - Topological ordering for execution
    - Cycle detection
    - Dependency resolution
    """

    def __init__(self):
        self.nodes: Dict[str, DAGNode] = {}
        self._execution_order: Optional[List[str]] = None

    def add_node(self, component_id: str, component_type: str, config: Dict) -> None:
        """Add a node to the DAG."""
        self.nodes[component_id] = DAGNode(
            component_id=component_id,
            component_type=component_type,
            config=config,
            upstream=set(),
            downstream=set(),
        )
        self._execution_order = None  # Invalidate cached order

    def add_edge(self, source: str, target: str) -> None:
        """Add an edge (flow) between nodes."""
        if source not in self.nodes:
            raise DAGValidationError(f"Source node not found: {source}")
        if target not in self.nodes:
            raise DAGValidationError(f"Target node not found: {target}")

        self.nodes[source].downstream.add(target)
        self.nodes[target].upstream.add(source)
        self._execution_order = None

    def get_sources(self) -> List[str]:
        """Get nodes with no upstream dependencies (entry points)."""
        return [
            node_id for node_id, node in self.nodes.items()
            if not node.upstream
        ]

    def get_sinks(self) -> List[str]:
        """Get nodes with no downstream dependencies (exit points)."""
        return [
            node_id for node_id, node in self.nodes.items()
            if not node.downstream
        ]

    def get_execution_order(self) -> List[str]:
        """
        Get topological execution order.

        Uses Kahn's algorithm for topological sort.

        Returns:
            List of component IDs in execution order

        Raises:
            DAGValidationError: If graph contains cycles
        """
        if self._execution_order is not None:
            return self._execution_order

        # Build in-degree map
        in_degree = {node_id: len(node.upstream) for node_id, node in self.nodes.items()}

        # Start with nodes that have no dependencies
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            # Sort for deterministic order
            queue.sort()
            node_id = queue.pop(0)
            result.append(node_id)

            # Reduce in-degree of downstream nodes
            for downstream_id in self.nodes[node_id].downstream:
                in_degree[downstream_id] -= 1
                if in_degree[downstream_id] == 0:
                    queue.append(downstream_id)

        # Check for cycles
        if len(result) != len(self.nodes):
            remaining = set(self.nodes.keys()) - set(result)
            raise DAGValidationError(f"Graph contains cycles involving: {remaining}")

        self._execution_order = result
        return result

    def get_ref_counts(self) -> Dict[str, int]:
        """Get the number of downstream consumers for each component."""
        return {
            node_id: len(node.downstream)
            for node_id, node in self.nodes.items()
        }

    def validate(self) -> List[str]:
        """
        Validate the DAG.

        Returns:
            List of validation error messages
        """
        errors = []

        # Check for empty DAG
        if not self.nodes:
            errors.append("DAG is empty - no components defined")
            return errors

        # Check for cycles
        try:
            self.get_execution_order()
        except DAGValidationError as e:
            errors.append(str(e))

        # Check for disconnected nodes
        sources = self.get_sources()
        if not sources:
            errors.append("No source components found (all components have upstream)")

        return errors

    def get_node(self, component_id: str) -> Optional[DAGNode]:
        """Get a node by ID."""
        return self.nodes.get(component_id)

    def __len__(self) -> int:
        return len(self.nodes)

    def __repr__(self) -> str:
        return f"DAG({len(self.nodes)} nodes, {sum(len(n.downstream) for n in self.nodes.values())} edges)"


class DAGBuilder:
    """
    Builds a DAG from job configuration.
    """

    @classmethod
    def build(cls, config: JobConfig) -> DAG:
        """
        Build a DAG from job configuration.

        Args:
            config: Job configuration

        Returns:
            Constructed DAG
        """
        dag = DAG()

        # Add all components as nodes
        for component in config.components:
            dag.add_node(
                component_id=component.id,
                component_type=component.type,
                config=component.config,
            )

        # Add edges from flows
        for flow in config.flows:
            dag.add_edge(flow.source, flow.target)

        # Validate
        errors = dag.validate()
        if errors:
            raise DAGValidationError(f"DAG validation failed: {errors}")

        logger.info(f"Built DAG: {dag}")
        return dag
