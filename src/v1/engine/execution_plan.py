"""ExecutionPlan -- DAG construction, topological sort, validation, streaming metadata.

Builds a pre-computed, validated execution plan from a job configuration.
Replaces the ad-hoc BFS queue and inline _identify_subjobs() logic in the
current engine.py with a pure data structure that can be constructed and
validated independently of any running engine.

Key responsibilities:
- Build a DAG of component dependencies within each subjob
- Topologically sort components for correct execution order
- Determine which subjobs are initial (not triggered) vs triggered
- Pre-validate for unreachable subjobs and cycles before execution
- Expose cross-subjob flow metadata for safe flow cleanup
- Mark streaming metadata (requires_full_data vs streamable)
"""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from graphlib import TopologicalSorter, CycleError

from .exceptions import ConfigurationError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Component types that require full data (cannot stream)
# ---------------------------------------------------------------------------

_REQUIRES_FULL_DATA_TYPES: frozenset[str] = frozenset({
    "AggregateRow", "tAggregateRow",
    "UniqueRow", "tUniqueRow", "tUniqRow",
    "SortRow", "tSortRow",
    "AggregateSortedRow", "tAggregateSortedRow",
})


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SubjobPlan:
    """Pre-computed execution plan for a single subjob.

    Args:
        subjob_id: Unique subjob identifier.
        component_ids: Topologically sorted component execution order.
        component_set: Frozen set for O(1) membership checks.
    """
    subjob_id: str
    component_ids: list[str]
    component_set: frozenset[str]


@dataclass
class StreamingMetadata:
    """Streaming behavior metadata for a single component.

    Args:
        component_id: The component this metadata describes.
        requires_full_data: True for aggregate, sort -- cannot stream.
        streamable: True for filter, map, most transforms.
    """
    component_id: str
    requires_full_data: bool = False
    streamable: bool = True


@dataclass
class TriggerEdge:
    """A single trigger edge between two components (possibly cross-subjob).

    Args:
        from_component: Source component ID.
        to_component: Target component ID.
        trigger_type: Trigger type string (OnSubjobOk, OnComponentOk, RunIf, etc.).
        from_subjob: Subjob containing the source component.
        to_subjob: Subjob containing the target component.
        condition: Optional trigger condition expression.
    """
    from_component: str
    to_component: str
    trigger_type: str
    from_subjob: str | None = None
    to_subjob: str | None = None
    condition: str | None = None


# ---------------------------------------------------------------------------
# ExecutionPlan
# ---------------------------------------------------------------------------

class ExecutionPlan:
    """Pre-computed execution plan built from a job configuration.

    Builds a DAG from the job config, topologically sorts components within
    each subjob, determines subjob execution order from the trigger graph,
    and validates the graph for unreachable components and cycles.

    Args:
        components: List of component config dicts (must have 'id' and 'type').
        flows: List of flow dicts (name, from, to, type).
        triggers: List of trigger dicts (type, from/from_component, to/to_component).
        subjobs: Optional dict mapping subjob_id -> list of component IDs.
            If None, auto-detects subjobs from flow connectivity.
    """

    def __init__(
        self,
        components: list[dict],
        flows: list[dict],
        triggers: list[dict],
        subjobs: dict[str, list[str]] | None = None,
    ) -> None:
        self._components = {c["id"]: c for c in components}
        self._flows = flows
        self._raw_triggers = triggers

        # ---- 1. Build component-to-subjob mapping ----
        if subjobs is not None:
            self._subjobs_dict = subjobs
        else:
            logger.info(
                "No subjobs dict in job config, auto-detecting subjob boundaries from flow graph"
            )
            self._subjobs_dict = self._auto_detect_subjobs()

        self._component_to_subjob: dict[str, str] = {}
        for subjob_id, comp_ids in self._subjobs_dict.items():
            for comp_id in comp_ids:
                self._component_to_subjob[comp_id] = subjob_id

        # ---- 2. Build SubjobPlan for each subjob ----
        self._subjob_plans: dict[str, SubjobPlan] = {}
        for subjob_id, comp_ids in self._subjobs_dict.items():
            self._subjob_plans[subjob_id] = self._build_subjob_plan(subjob_id, comp_ids)

        # ---- 3. Build trigger edge list ----
        self._trigger_edges: list[TriggerEdge] = self._build_trigger_edges()

        # ---- 4. Compute initial subjobs ----
        triggered_subjob_ids: set[str] = set()
        for edge in self._trigger_edges:
            if edge.to_subjob is not None:
                triggered_subjob_ids.add(edge.to_subjob)
        self._initial_subjobs: list[str] = [
            sid for sid in self._subjobs_dict
            if sid not in triggered_subjob_ids
        ]

        # ---- 5. Build streaming metadata ----
        self._streaming_metadata: dict[str, StreamingMetadata] = {}
        for comp_id, comp_config in self._components.items():
            comp_type = comp_config.get("type", "")
            requires_full = comp_type in _REQUIRES_FULL_DATA_TYPES
            self._streaming_metadata[comp_id] = StreamingMetadata(
                component_id=comp_id,
                requires_full_data=requires_full,
                streamable=not requires_full,
            )

        # ---- 6. RunIf target subjobs ----
        self._runif_target_subjobs: set[str] = set()
        for edge in self._trigger_edges:
            if edge.trigger_type == "RunIf" and edge.to_subjob is not None:
                self._runif_target_subjobs.add(edge.to_subjob)

        # ---- 7. Cross-subjob flows and flow consumers ----
        self._cross_subjob_flows: list[dict] = []
        self._flow_consumers: dict[str, set[str]] = {}

        for flow in self._flows:
            from_comp = flow.get("from")
            to_comp = flow.get("to")
            flow_name = flow.get("name", "")

            # Track consumers
            if flow_name not in self._flow_consumers:
                self._flow_consumers[flow_name] = set()
            if to_comp:
                self._flow_consumers[flow_name].add(to_comp)

            # Detect cross-subjob flows
            from_subjob = self._component_to_subjob.get(from_comp)
            to_subjob = self._component_to_subjob.get(to_comp)
            if from_subjob and to_subjob and from_subjob != to_subjob:
                self._cross_subjob_flows.append(flow)

    # ------------------------------------------------------------------
    # Internal builders
    # ------------------------------------------------------------------

    def _auto_detect_subjobs(self) -> dict[str, list[str]]:
        """Auto-detect subjobs using connected-components on the flow graph (BFS).

        Components connected by flows (bidirectionally) are grouped into
        the same subjob. Disconnected components form separate subjobs.

        Returns:
            Dict mapping auto-generated subjob IDs to component ID lists.
        """
        visited: set[str] = set()
        subjobs: dict[str, list[str]] = {}
        counter = 1

        for comp_id in self._components:
            if comp_id in visited:
                continue

            # BFS from this component following flows bidirectionally
            group: list[str] = []
            queue: deque[str] = deque([comp_id])

            while queue:
                current = queue.popleft()
                if current in visited:
                    continue
                visited.add(current)
                group.append(current)

                for flow in self._flows:
                    if flow.get("from") == current and flow.get("to") not in visited:
                        queue.append(flow["to"])
                    elif flow.get("to") == current and flow.get("from") not in visited:
                        queue.append(flow["from"])

            if group:
                subjobs[f"subjob_{counter}"] = group
                counter += 1

        return subjobs

    def _build_subjob_plan(self, subjob_id: str, comp_ids: list[str]) -> SubjobPlan:
        """Build a topologically sorted SubjobPlan for one subjob.

        Args:
            subjob_id: The subjob identifier.
            comp_ids: Component IDs belonging to this subjob.

        Returns:
            SubjobPlan with topologically sorted component order.

        Raises:
            ConfigurationError: If a cycle is detected in the flow graph.
        """
        comp_set = frozenset(comp_ids)

        # Filter flows to only those whose from AND to are both in this subjob
        internal_flows = [
            f for f in self._flows
            if f.get("from") in comp_set and f.get("to") in comp_set
        ]

        # Build dependency graph: 'to' depends on 'from'
        sorter = TopologicalSorter()

        # Add all components as nodes (even those with no edges)
        for comp_id in comp_ids:
            sorter.add(comp_id)

        # Add edges: to depends on from
        for flow in internal_flows:
            sorter.add(flow["to"], flow["from"])

        try:
            sorted_order = list(sorter.static_order())
        except CycleError as e:
            raise ConfigurationError(
                f"Cycle detected in component flow graph for subjob '{subjob_id}': {e}"
            ) from e

        return SubjobPlan(
            subjob_id=subjob_id,
            component_ids=sorted_order,
            component_set=comp_set,
        )

    def _build_trigger_edges(self) -> list[TriggerEdge]:
        """Build trigger edge list from raw trigger configs.

        Supports both 'from'/'to' and 'from_component'/'to_component' key formats.

        Returns:
            List of TriggerEdge objects.
        """
        edges: list[TriggerEdge] = []
        for trig in self._raw_triggers:
            from_comp = trig.get("from") or trig.get("from_component", "")
            to_comp = trig.get("to") or trig.get("to_component", "")
            trigger_type = trig.get("type", "")
            condition = trig.get("condition")

            from_subjob = self._component_to_subjob.get(from_comp)
            to_subjob = self._component_to_subjob.get(to_comp)

            edges.append(TriggerEdge(
                from_component=from_comp,
                to_component=to_comp,
                trigger_type=trigger_type,
                from_subjob=from_subjob,
                to_subjob=to_subjob,
                condition=condition,
            ))

        return edges

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """Validate the execution plan graph.

        Runs reachability analysis from initial subjobs following trigger
        edges. Subjobs that are not reachable and not RunIf targets raise
        ConfigurationError.

        Raises:
            ConfigurationError: If unreachable subjobs are detected.
        """
        # BFS from initial subjobs following trigger edges
        reachable: set[str] = set(self._initial_subjobs)
        queue: deque[str] = deque(self._initial_subjobs)

        while queue:
            current_subjob = queue.popleft()
            for edge in self._trigger_edges:
                if (
                    edge.from_subjob == current_subjob
                    and edge.to_subjob is not None
                    and edge.to_subjob not in reachable
                ):
                    reachable.add(edge.to_subjob)
                    queue.append(edge.to_subjob)

        # Check for unreachable subjobs (excluding RunIf targets per D-08)
        all_subjob_ids = set(self._subjobs_dict.keys())
        unreachable = all_subjob_ids - reachable - self._runif_target_subjobs

        if unreachable:
            raise ConfigurationError(
                f"Unreachable subjobs detected: {sorted(unreachable)}. "
                f"These subjobs have no trigger path from any initial subjob "
                f"and are not RunIf targets."
            )

    # ------------------------------------------------------------------
    # Properties and accessors
    # ------------------------------------------------------------------

    @property
    def initial_subjobs(self) -> list[str]:
        """Subjob IDs not targeted by any trigger."""
        return self._initial_subjobs

    @property
    def component_to_subjob(self) -> dict[str, str]:
        """Mapping of component ID to containing subjob ID."""
        return self._component_to_subjob

    @property
    def all_subjob_ids(self) -> list[str]:
        """All subjob IDs in execution order (initial first, then by trigger chain)."""
        # BFS from initial subjobs to get ordered list
        ordered: list[str] = []
        visited: set[str] = set()
        queue: deque[str] = deque(self._initial_subjobs)

        while queue:
            sid = queue.popleft()
            if sid in visited:
                continue
            visited.add(sid)
            ordered.append(sid)

            # Add triggered subjobs
            for edge in self._trigger_edges:
                if edge.from_subjob == sid and edge.to_subjob and edge.to_subjob not in visited:
                    queue.append(edge.to_subjob)

        # Add any remaining subjobs not reached by trigger traversal
        # (e.g., RunIf targets with no standard trigger path)
        for sid in self._subjobs_dict:
            if sid not in visited:
                ordered.append(sid)

        return ordered

    def get_subjob_plan(self, subjob_id: str) -> SubjobPlan:
        """Get pre-computed plan for a subjob.

        Args:
            subjob_id: The subjob identifier.

        Returns:
            SubjobPlan with topologically sorted component order.

        Raises:
            KeyError: If subjob_id is not found.
        """
        return self._subjob_plans[subjob_id]

    def get_triggered_subjobs(self, trigger_type: str, source_component: str) -> list[TriggerEdge]:
        """Get trigger edges from a source component of a given type.

        Args:
            trigger_type: The trigger type to filter by (e.g., 'OnSubjobOk').
            source_component: The source component ID.

        Returns:
            List of matching TriggerEdge objects.
        """
        return [
            edge for edge in self._trigger_edges
            if edge.trigger_type == trigger_type and edge.from_component == source_component
        ]

    def get_all_trigger_edges_from_subjob(self, subjob_id: str) -> list[TriggerEdge]:
        """Get all trigger edges originating from components in a subjob.

        Args:
            subjob_id: The subjob identifier.

        Returns:
            List of TriggerEdge objects.
        """
        return [
            edge for edge in self._trigger_edges
            if edge.from_subjob == subjob_id
        ]

    def get_streaming_metadata(self, component_id: str) -> StreamingMetadata:
        """Get streaming metadata for a component.

        Args:
            component_id: The component identifier.

        Returns:
            StreamingMetadata for the component.
        """
        return self._streaming_metadata[component_id]

    def get_cross_subjob_flows(self) -> list[dict]:
        """Get flows where from-component and to-component are in different subjobs.

        Used by OutputRouter to avoid premature clearing of flows that cross
        subjob boundaries.

        Returns:
            List of flow dicts that cross subjob boundaries.
        """
        return self._cross_subjob_flows

    def get_flow_consumers(self, flow_name: str) -> set[str]:
        """Get all component IDs that consume a given flow.

        Used to check if all consumers are complete before clearing a flow.

        Args:
            flow_name: The flow name to look up.

        Returns:
            Set of component IDs that consume this flow.
        """
        return self._flow_consumers.get(flow_name, set())
