"""Output routing: manage data flows between components.

Replaces inline routing in engine.py _execute_component() (lines 542-559)
and _get_input_data()/_are_inputs_ready() (lines 739-769).

OutputRouter owns the data_flows dict, routes component outputs to named
flows based on flow config, resolves component inputs from upstream flows,
and manages memory by clearing subjob flows after completion.

Cross-subjob safety (D-16): clear_subjob_flows checks for pending
cross-subjob consumers before clearing -- flows with unexecuted downstream
consumers outside the subjob are preserved.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Flow type -> result key mapping
_FLOW_TYPE_TO_RESULT_KEY = {
    "flow": "main",
    "reject": "reject",
    "filter": "main",
    "iterate": "iterate",
    "unique": "main",       # tUniqRow UNIQUE connector -> main (unique rows)
    "duplicate": "reject",  # tUniqRow DUPLICATE connector -> reject (duplicate rows)
}


class OutputRouter:
    """Manage data flow routing between ETL components.

    Owns the data_flows dict and provides methods for:
    - Routing component outputs to named flows based on flow config
    - Resolving component inputs from upstream flows
    - Checking input readiness
    - Clearing subjob flows after completion with cross-subjob safety

    Args:
        flows_config: List of flow dicts from job config
            (keys: name, from, to, type).
        components_config: List of component dicts from job config
            (keys: id, inputs, outputs).
    """

    def __init__(self, flows_config: list[dict], components_config: list[dict]) -> None:
        self._flows_config = flows_config

        # Pre-compute lookup structures
        # comp_id -> list of outgoing flow configs
        self._outgoing: dict[str, list[dict]] = {}
        # comp_id -> list of incoming flow names
        self._incoming: dict[str, list[str]] = {}
        # comp_id -> declared outputs list
        self._component_outputs: dict[str, list[str]] = {}
        # comp_id -> declared inputs list
        self._component_inputs: dict[str, list[str]] = {}
        # flow_name -> set of component IDs that consume this flow
        self._flow_consumers: dict[str, set[str]] = {}

        # Build component lookups
        for comp in components_config:
            comp_id = comp["id"]
            self._component_inputs[comp_id] = list(comp.get("inputs", []))
            self._component_outputs[comp_id] = list(comp.get("outputs", []))

        # Build flow lookups
        for flow in flows_config:
            from_id = flow["from"]
            to_id = flow["to"]
            flow_name = flow["name"]

            # Outgoing flows per component
            if from_id not in self._outgoing:
                self._outgoing[from_id] = []
            self._outgoing[from_id].append(flow)

            # Incoming flows per component
            if to_id not in self._incoming:
                self._incoming[to_id] = []
            self._incoming[to_id].append(flow_name)

            # Flow consumers
            if flow_name not in self._flow_consumers:
                self._flow_consumers[flow_name] = set()
            self._flow_consumers[flow_name].add(to_id)

        # The data store
        self._data_flows: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Output routing
    # ------------------------------------------------------------------

    def route_outputs(self, comp_id: str, result: dict[str, Any]) -> None:
        """Route component result to named flows based on flow config.

        Maps result keys to flow names:
        - flow type 'flow' -> result['main']
        - flow type 'reject' -> result['reject']
        - flow type 'filter' -> result['main']
        - flow type 'iterate' -> result['iterate']

        Named outputs (keys not in main/reject/stats) are stored by their
        declared output name if listed in component outputs, otherwise as
        {comp_id}_{key}.

        Args:
            comp_id: The component that produced the result.
            result: Dict with keys like 'main', 'reject', 'stats', etc.
        """
        if not result:
            return

        # Route via flow config
        for flow in self._outgoing.get(comp_id, []):
            flow_type = flow["type"]
            result_key = _FLOW_TYPE_TO_RESULT_KEY.get(flow_type)
            if result_key is None:
                continue

            value = result.get(result_key)
            if value is None:
                continue

            flow_name = flow["name"]
            self._data_flows[flow_name] = value
            logger.debug(f"Routed {comp_id} output to flow {flow_name}")

        # Named outputs (keys not in standard set)
        declared_outputs = set(self._component_outputs.get(comp_id, []))
        for key, value in result.items():
            if key in ("main", "reject", "stats"):
                continue
            if value is None:
                continue

            if key in declared_outputs:
                self._data_flows[key] = value
                logger.debug(f"Routed {comp_id} named output to {key}")
            else:
                prefixed = f"{comp_id}_{key}"
                self._data_flows[prefixed] = value
                logger.debug(f"Routed {comp_id} undeclared output to {prefixed}")

    # ------------------------------------------------------------------
    # Input resolution
    # ------------------------------------------------------------------

    def get_input_data(self, comp_id: str) -> Optional[Any]:
        """Get input data from upstream flows.

        Args:
            comp_id: The component requesting input data.

        Returns:
            None if component has no inputs.
            DataFrame directly if single input.
            Dict[flow_name, DataFrame] if multiple inputs.
        """
        inputs = self._component_inputs.get(comp_id, [])

        if not inputs:
            return None

        if len(inputs) == 1:
            return self._data_flows.get(inputs[0])

        return {flow_name: self._data_flows.get(flow_name) for flow_name in inputs}

    def are_inputs_ready(self, comp_id: str) -> bool:
        """Check if all required inputs for a component are available.

        Args:
            comp_id: The component to check.

        Returns:
            True if component has no inputs or all input flows have data.
        """
        inputs = self._component_inputs.get(comp_id, [])

        if not inputs:
            return True

        for flow_name in inputs:
            if flow_name not in self._data_flows:
                return False

        return True

    # ------------------------------------------------------------------
    # Flow cleanup
    # ------------------------------------------------------------------

    def clear_flow(self, flow_name: str) -> None:
        """Remove a specific flow's data.

        Used for iterate cleanup between iterations.

        Args:
            flow_name: The flow to clear.
        """
        self._data_flows.pop(flow_name, None)

    def clear_subjob_flows(
        self,
        subjob_component_ids: set[str],
        executed_components: set[str] | None = None,
    ) -> None:
        """Clear outgoing flows from components in the given subjob.

        Preserves flows that have cross-subjob consumers that have NOT yet
        executed (D-16 safety). This prevents data loss when a downstream
        subjob hasn't consumed the flow yet.

        Args:
            subjob_component_ids: Set of component IDs in the subjob.
            executed_components: Set of component IDs that have already
                executed. Used to determine if cross-subjob consumers
                have consumed the flow data.
        """
        if executed_components is None:
            executed_components = set()

        cleared = 0
        preserved = 0

        for comp_id in subjob_component_ids:
            for flow in self._outgoing.get(comp_id, []):
                flow_name = flow["name"]

                if flow_name not in self._data_flows:
                    continue

                # Check consumers of this flow
                consumers = self._flow_consumers.get(flow_name, set())

                # Are there cross-subjob consumers that haven't executed?
                should_preserve = False
                for consumer_id in consumers:
                    if consumer_id not in subjob_component_ids:
                        # Cross-subjob consumer
                        if consumer_id not in executed_components:
                            # Consumer hasn't run yet -- preserve
                            should_preserve = True
                            logger.debug(
                                f"Preserving flow {flow_name}: cross-subjob "
                                f"consumer {consumer_id} has not yet executed"
                            )
                            break

                if should_preserve:
                    preserved += 1
                else:
                    self._data_flows.pop(flow_name, None)
                    cleared += 1

        logger.debug(
            f"clear_subjob_flows: cleared {cleared}, preserved {preserved}"
        )

    # ------------------------------------------------------------------
    # Direct access helpers
    # ------------------------------------------------------------------

    def get_flow_data(self, flow_name: str) -> Optional[Any]:
        """Direct access to a specific flow's data.

        Args:
            flow_name: The flow to retrieve.

        Returns:
            The flow data or None if not available.
        """
        return self._data_flows.get(flow_name)

    def has_flow_data(self, flow_name: str) -> bool:
        """Check if a flow has data available.

        Args:
            flow_name: The flow to check.

        Returns:
            True if the flow has data stored.
        """
        return flow_name in self._data_flows

    def get_pending_flow_names(self) -> list[str]:
        """Return list of flow names that currently have data stored.

        For diagnostic purposes (stall detection).

        Returns:
            List of flow names with data.
        """
        return list(self._data_flows.keys())

    # ------------------------------------------------------------------
    # Iterate support helpers (Phase 10-02)
    # ------------------------------------------------------------------

    def drain_reject_flows(self, component_ids: set[str]) -> dict[str, "pd.DataFrame"]:
        """Drain all reject-type outgoing flows from the given component set.

        Returns a dict keyed by flow name with the DataFrame currently held in
        each reject flow. Removes the drained flows from internal _data_flows.
        Used by the iterate loop in Executor._execute_iterate_body to accumulate
        body REJECT data per iteration (D-D4).

        Args:
            component_ids: Body components to drain.

        Returns:
            dict[flow_name -> DataFrame] for every drained reject flow.
        """
        drained: dict[str, "pd.DataFrame"] = {}
        for comp_id in component_ids:
            for flow in self._outgoing.get(comp_id, []):
                if flow.get("type") != "reject":
                    continue
                flow_name = flow.get("name") or flow.get("from")
                if flow_name in self._data_flows:
                    drained[flow_name] = self._data_flows.pop(flow_name)
        return drained

    def clear_partial_subjob_flows(
        self,
        body_component_ids: "frozenset[str] | set[str]",
        executed_components: set[str],
    ) -> None:
        """Clear data flows owned by a SUBSET of subjob components (the iterate body).

        Preserves any flow whose downstream consumer is in another subjob that has
        not yet executed. Mirrors clear_subjob_flows preservation logic but
        parameterized on a body subset rather than the full subjob (D-I4).

        This is a SUBSET-aware variant of clear_subjob_flows; preservation behavior
        is identical.

        Args:
            body_component_ids: Components in the iterate body.
            executed_components: Set of already-executed component IDs (so we can
                detect which downstream subjobs still need the flows).
        """
        cleared = 0
        preserved = 0

        for comp_id in body_component_ids:
            for flow in self._outgoing.get(comp_id, []):
                flow_name = flow["name"]

                if flow_name not in self._data_flows:
                    continue

                # Check consumers of this flow
                consumers = self._flow_consumers.get(flow_name, set())

                # Are there cross-subjob consumers that haven't executed?
                should_preserve = False
                for consumer_id in consumers:
                    if consumer_id not in body_component_ids:
                        # Consumer is outside the body subset (cross-subjob or parent-subjob)
                        if consumer_id not in executed_components:
                            # Consumer hasn't run yet -- preserve
                            should_preserve = True
                            logger.debug(
                                f"Preserving flow {flow_name}: cross-body "
                                f"consumer {consumer_id} has not yet executed"
                            )
                            break

                if should_preserve:
                    preserved += 1
                else:
                    self._data_flows.pop(flow_name, None)
                    cleared += 1

        logger.debug(
            f"clear_partial_subjob_flows: cleared {cleared}, preserved {preserved}"
        )
