"""
Stage detection, DAG, and orchestration for V2 engine.

Stages are groups of components connected by data flows.
They are auto-detected via BFS on the flow graph.
Triggers connect stages and control execution order.
"""
import logging
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from ..config.job_config import JobConfig, TriggerConnection, TriggerType

logger = logging.getLogger(__name__)


# ── Data Structures ──────────────────────────────────────────────────

class StageStatus(str, Enum):
    """Execution status of a stage."""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Stage:
    """A group of components connected by data flows."""
    stage_id: str
    component_ids: Set[str]


@dataclass
class StageResult:
    """Result of executing a single stage."""
    stage_id: str
    status: StageStatus
    component_ids: Set[str] = field(default_factory=set)
    rows_out: Dict[str, int] = field(default_factory=dict)
    duration_ms: float = 0.0
    error: Optional[str] = None


# ── Stage Detection ──────────────────────────────────────────────────

class StageDetector:
    """Detects stages from flow connections using connected-components BFS."""

    @classmethod
    def detect(cls, config: JobConfig) -> List[Stage]:
        """Detect stages from data flow connections.

        Builds an undirected graph from flows and finds connected components.
        Each connected component becomes a stage. Isolated components (no flows)
        become single-component stages.

        Returns:
            List of Stage objects, sorted by minimum component ID for determinism.
        """
        stages, _ = cls.detect_with_mapping(config)
        return stages

    @classmethod
    def detect_with_mapping(
        cls, config: JobConfig
    ) -> Tuple[List[Stage], Dict[str, str]]:
        """Detect stages and return component-to-stage mapping.

        Returns:
            Tuple of (stages, component_to_stage_id mapping).
        """
        component_ids = {c.id for c in config.components}
        if not component_ids:
            return [], {}

        # Build undirected adjacency list from data flows only
        adjacency: Dict[str, Set[str]] = {cid: set() for cid in component_ids}
        for flow in config.flows:
            if flow.source not in component_ids or flow.target not in component_ids:
                raise ValueError(
                    f"Flow references unknown component: "
                    f"source={flow.source!r}, target={flow.target!r}"
                )
            adjacency[flow.source].add(flow.target)
            adjacency[flow.target].add(flow.source)

        # Find connected components via BFS
        visited: Set[str] = set()
        groups: List[Set[str]] = []

        for cid in sorted(component_ids):  # sorted for determinism
            if cid in visited:
                continue
            # BFS from this component
            group: Set[str] = set()
            queue = deque([cid])
            while queue:
                node = queue.popleft()
                if node in visited:
                    continue
                visited.add(node)
                group.add(node)
                for neighbor in adjacency[node]:
                    if neighbor not in visited:
                        queue.append(neighbor)
            groups.append(group)

        # Sort groups by minimum component ID for deterministic stage IDs
        groups.sort(key=lambda g: min(g))

        # Build Stage objects and mapping
        stages = []
        comp_to_stage: Dict[str, str] = {}
        for i, group in enumerate(groups):
            stage_id = f"stage_{i}"
            stages.append(Stage(stage_id=stage_id, component_ids=group))
            for cid in group:
                comp_to_stage[cid] = stage_id

        return stages, comp_to_stage


# ── Stage DAG ────────────────────────────────────────────────────────

@dataclass
class _StageTrigger:
    """Internal: a trigger mapped to stage IDs."""
    source_stage: str
    target_stage: str
    trigger: TriggerConnection


class StageDAG:
    """DAG of stages, built from trigger connections.

    Provides topological ordering of stages and trigger lookup.
    """

    def __init__(self):
        self._stages: Dict[str, Stage] = {}
        self._incoming: Dict[str, List[_StageTrigger]] = {}
        self._outgoing: Dict[str, List[_StageTrigger]] = {}
        self._upstream: Dict[str, Set[str]] = {}
        self._downstream: Dict[str, Set[str]] = {}
        self._execution_order: Optional[List[str]] = None

    @classmethod
    def build(
        cls,
        stages: List[Stage],
        triggers: List[TriggerConnection],
        comp_to_stage: Dict[str, str],
    ) -> "StageDAG":
        """Build a StageDAG from stages and trigger connections.

        Args:
            stages: Detected stages.
            triggers: Trigger connections from config.
            comp_to_stage: Mapping of component ID -> stage ID.

        Returns:
            Constructed StageDAG.

        Raises:
            ValueError: If triggers form a cycle.
        """
        dag = cls()

        for stage in stages:
            dag._stages[stage.stage_id] = stage
            dag._incoming[stage.stage_id] = []
            dag._outgoing[stage.stage_id] = []
            dag._upstream[stage.stage_id] = set()
            dag._downstream[stage.stage_id] = set()

        for trigger in triggers:
            source_stage = comp_to_stage.get(trigger.source)
            target_stage = comp_to_stage.get(trigger.target)

            if source_stage is None or target_stage is None:
                raise ValueError(
                    f"Trigger references unknown component: "
                    f"source='{trigger.source}', target='{trigger.target}'"
                )

            if source_stage == target_stage:
                logger.warning(
                    f"Trigger from '{trigger.source}' to '{trigger.target}' "
                    f"ignored: both are in {source_stage}"
                )
                continue

            st = _StageTrigger(
                source_stage=source_stage,
                target_stage=target_stage,
                trigger=trigger,
            )
            dag._incoming[target_stage].append(st)
            dag._outgoing[source_stage].append(st)
            dag._upstream[target_stage].add(source_stage)
            dag._downstream[source_stage].add(target_stage)

        dag._execution_order = dag._topological_sort()
        return dag

    def get_execution_order(self) -> List[str]:
        """Get stage IDs in topological execution order."""
        return list(self._execution_order)

    def get_entry_stages(self) -> List[str]:
        """Get stage IDs with no incoming triggers (entry points)."""
        return [
            sid for sid in self._execution_order
            if not self._upstream[sid]
        ]

    def get_incoming_triggers(self, stage_id: str) -> List[TriggerConnection]:
        """Get trigger connections targeting the given stage."""
        return [st.trigger for st in self._incoming.get(stage_id, [])]

    def get_stage(self, stage_id: str) -> Optional[Stage]:
        """Get a Stage by ID."""
        return self._stages.get(stage_id)

    def _topological_sort(self) -> List[str]:
        """Kahn's algorithm on the stage DAG.

        Raises:
            ValueError: If the stage graph contains cycles.
        """
        in_degree = {
            sid: len(self._upstream[sid])
            for sid in self._stages
        }
        queue = sorted(
            [sid for sid, deg in in_degree.items() if deg == 0]
        )
        result = []

        while queue:
            queue.sort()
            stage_id = queue.pop(0)
            result.append(stage_id)

            for downstream_id in self._downstream[stage_id]:
                in_degree[downstream_id] -= 1
                if in_degree[downstream_id] == 0:
                    queue.append(downstream_id)

        if len(result) != len(self._stages):
            remaining = set(self._stages.keys()) - set(result)
            raise ValueError(
                f"Circular trigger dependency detected between stages: {remaining}"
            )
        return result


# ── Stage Executor ───────────────────────────────────────────────────

class StageExecutor:
    """Evaluates trigger rules and tracks stage execution results.

    This is the orchestration decision-maker. It does NOT execute pipelines
    directly — it tells the engine WHETHER a stage should run, and records
    the result after execution.
    """

    def __init__(
        self,
        dag: StageDAG,
        comp_to_stage: Dict[str, str],
        context_vars: Dict[str, Any],
    ):
        self._dag = dag
        self._comp_to_stage = comp_to_stage
        self._context_vars = context_vars
        self._results: Dict[str, StageResult] = {}

    def should_stage_run(self, stage_id: str) -> bool:
        """Determine if a stage should run based on its incoming triggers.

        Entry stages (no incoming triggers) always run.
        For others, OR semantics: if ANY trigger is satisfied, run.
        """
        incoming = self._dag.get_incoming_triggers(stage_id)

        # Entry stage — no incoming triggers
        if not incoming:
            return True

        # Evaluate each incoming trigger — OR semantics
        for trigger in incoming:
            source_stage = self._comp_to_stage[trigger.source]
            source_result = self._results.get(source_stage)

            if source_result is None:
                continue

            from .trigger import TriggerEvaluator
            if TriggerEvaluator.evaluate(
                trigger, source_result.status, self._context_vars
            ):
                return True

        return False

    def record_result(self, result: StageResult) -> None:
        """Record the result of a stage execution."""
        self._results[result.stage_id] = result

    def get_results(self) -> List[StageResult]:
        """Get all stage results in execution order."""
        order = self._dag.get_execution_order()
        return [self._results[sid] for sid in order if sid in self._results]

    def get_job_status(self) -> str:
        """Determine overall job status from stage results.

        Returns 'success' if all non-skipped stages succeeded.
        Returns 'error' if any stage failed.
        """
        for result in self._results.values():
            if result.status == StageStatus.FAILED:
                return "error"
        return "success"

    def update_context_vars(self, context_vars: Dict[str, Any]) -> None:
        """Update context vars (e.g., after ContextLoad stage)."""
        self._context_vars = context_vars
