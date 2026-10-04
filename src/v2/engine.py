"""PyETL Engine v2 - Barrier-aware lazy execution."""
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union

import polars as pl

from .config import JobConfig
from .execution.context import ExecutionContext
from .execution.dag import DAGBuilder
from .execution.stage import StageDetector, StageDAG, StageExecutor, StageResult, StageStatus
from .components.base import Component
from .components.registry import REGISTRY
from .routines import RoutineManager

# Import component modules so they self-register via @REGISTRY.register()
from .components import file as _file_components  # noqa: F401  # triggers file I/O registration
from .components import transform as _transform_components  # noqa: F401  # triggers transform registration
from .components import aggregate as _aggregate_components  # noqa: F401  # triggers aggregate registration
from .components import python as _python_components  # noqa: F401  # triggers python UDF registration
from .components import iterate as _iterate_components  # noqa: F401  # triggers iterate registration
from .components import utility as _utility_components  # noqa: F401  # triggers utility registration

logger = logging.getLogger(__name__)


class PyETLEngine:
    """
    V2 ETL Engine with lazy pipeline fusion.

    Components pass pl.LazyFrame between each other.
    .collect() only at barrier points (sinks, multi-output, Python UDFs).
    """

    def __init__(
        self,
        config: Union[Dict, JobConfig, str, Path],
        routines_dir: Optional[str] = None,
    ):
        if isinstance(config, (str, Path)):
            with open(config) as f:
                config = json.load(f)
        if isinstance(config, dict):
            self.config = JobConfig(**config)
        else:
            self.config = config

        self.job_name = self.config.name
        self.streaming = self.config.streaming
        self.routine_manager = RoutineManager(routines_dir, auto_load=True)
        self.dag = DAGBuilder.build(self.config)
        self._components: Dict[str, Component] = {}
        self._iterate_managed: set = set()  # components managed by iterate loops
        self._collect_kwargs: Dict[str, Any] = (
            {"engine": "streaming"} if self.streaming else {}
        )

    def execute(self) -> Dict[str, Any]:
        """Execute the ETL job.

        If triggers are present, uses stage-based orchestration.
        Otherwise, runs flat pipeline (existing behavior).
        """
        if self.config.triggers:
            return self._execute_with_stages()
        return self._execute_flat()

    def _execute_flat(self) -> Dict[str, Any]:
        """Execute as a flat pipeline (no triggers — existing behavior)."""
        start = time.perf_counter()

        context = ExecutionContext(
            context_vars=self.config.get_context_values(),
        )

        try:
            # Initialize ref counts from DAG
            ref_counts = self.dag.get_ref_counts()
            for comp_id, count in ref_counts.items():
                context.set_ref_count(comp_id, count)

            # Create components
            self._create_components(context)

            # Execute in topological order
            self._iterate_managed = set()
            execution_order = self.dag.get_execution_order()

            n_components = len(execution_order)
            streaming_tag = " | streaming=on" if self.streaming else ""
            logger.info(
                f"[{self.job_name}] Starting job execution "
                f"({n_components} components{streaming_tag})"
            )
            logger.info(
                f"[{self.job_name}] Execution order: "
                + " -> ".join(execution_order)
            )

            for component_id in execution_order:
                if component_id in self._iterate_managed:
                    continue  # handled by iterate loop
                self._execute_component(component_id, context)

            duration_ms = (time.perf_counter() - start) * 1000
            result = context.get_execution_result()
            result["status"] = "success"
            result["job_name"] = self.job_name
            result["duration_ms"] = round(duration_ms, 2)

            # Job summary log
            total_rows = self._get_total_sink_rows(result)
            logger.info(
                f"[{self.job_name}] Job completed: success | "
                f"{n_components} components | "
                f"{duration_ms:.1f}ms"
                + (f" | {total_rows:,} rows written" if total_rows else "")
            )
            return result

        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error(
                f"[{self.job_name}] Job failed: {type(e).__name__}: {e} "
                f"({duration_ms:.1f}ms)"
            )
            return {
                "status": "error",
                "job_name": self.job_name,
                "error": str(e),
                "error_type": type(e).__name__,
                "duration_ms": round(duration_ms, 2),
                "components": context.get_execution_result()["components"],
            }

    def _execute_with_stages(self) -> Dict[str, Any]:
        """Execute with stage-based orchestration."""
        start = time.perf_counter()
        context = ExecutionContext(context_vars=self.config.get_context_values())

        # Detect stages and build stage DAG
        stages, comp_to_stage = StageDetector.detect_with_mapping(self.config)
        stage_dag = StageDAG.build(stages, self.config.triggers, comp_to_stage)
        stage_executor = StageExecutor(
            stage_dag, comp_to_stage, context.context_vars,
        )

        n_stages = len(stages)
        stage_order = stage_dag.get_execution_order()
        logger.info(
            f"[{self.job_name}] Starting staged execution "
            f"({n_stages} stages, {len(self.config.components)} components)"
        )
        logger.info(
            f"[{self.job_name}] Stage order: "
            + " -> ".join(stage_order)
        )

        # Execute stages in order
        for stage_id in stage_order:
            stage = stage_dag.get_stage(stage_id)

            # Check if this stage should run
            if not stage_executor.should_stage_run(stage_id):
                logger.info(
                    f"[{self.job_name}] Stage {stage_id}: SKIPPED "
                    f"(trigger rule not satisfied)"
                )
                stage_executor.record_result(StageResult(
                    stage_id=stage_id,
                    status=StageStatus.SKIPPED,
                    component_ids=stage.component_ids,
                ))
                continue

            # Execute this stage's pipeline
            stage_result = self._execute_stage(stage, context)
            stage_executor.record_result(stage_result)

            # Update context vars in executor (for conditional triggers)
            stage_executor.update_context_vars(context.context_vars)

            # Free stage intermediates
            context.clear_stage(stage.component_ids)

            logger.info(
                f"[{self.job_name}] Stage {stage_id}: "
                f"{stage_result.status.value} ({stage_result.duration_ms:.1f}ms)"
            )

        # Build result
        duration_ms = (time.perf_counter() - start) * 1000
        result = context.get_execution_result()
        result["status"] = stage_executor.get_job_status()
        result["job_name"] = self.job_name
        result["duration_ms"] = round(duration_ms, 2)
        result["stages"] = [
            {
                "stage_id": sr.stage_id,
                "status": sr.status.value,
                "component_ids": sorted(sr.component_ids),
                "rows_out": sr.rows_out,
                "duration_ms": sr.duration_ms,
                "error": sr.error,
            }
            for sr in stage_executor.get_results()
        ]

        total_rows = self._get_total_sink_rows(result)
        logger.info(
            f"[{self.job_name}] Job completed: {result['status']} | "
            f"{n_stages} stages | {duration_ms:.1f}ms"
            + (f" | {total_rows:,} rows written" if total_rows else "")
        )
        return result

    def _execute_stage(
        self,
        stage,
        context: ExecutionContext,
    ) -> StageResult:
        """Execute a single stage as a mini-pipeline."""
        stage_start = time.perf_counter()

        try:
            # Build DAG for just this stage's components
            stage_config = self._build_stage_config(stage)
            stage_dag = DAGBuilder.build(stage_config)

            # Set up ref counts for stage components
            ref_counts = stage_dag.get_ref_counts()
            for comp_id, count in ref_counts.items():
                context.set_ref_count(comp_id, count)

            # Create components (only for this stage)
            self._create_stage_components(stage, context)

            # Execute in topo order
            self._iterate_managed = set()
            execution_order = stage_dag.get_execution_order()

            for component_id in execution_order:
                if component_id in self._iterate_managed:
                    continue
                self._execute_component(component_id, context)

            duration_ms = (time.perf_counter() - stage_start) * 1000

            # Collect rows_out from barrier components in this stage
            rows_out = {}
            for comp_id in stage.component_ids:
                stats = context.get_component_stats(comp_id)
                if stats and stats.get("rows_out"):
                    for port, count in stats["rows_out"].items():
                        rows_out[f"{comp_id}.{port}"] = count

            return StageResult(
                stage_id=stage.stage_id,
                status=StageStatus.SUCCESS,
                component_ids=stage.component_ids,
                rows_out=rows_out,
                duration_ms=round(duration_ms, 2),
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - stage_start) * 1000
            logger.error(
                f"[{self.job_name}] Stage {stage.stage_id} failed: "
                f"{type(e).__name__}: {e}"
            )
            return StageResult(
                stage_id=stage.stage_id,
                status=StageStatus.FAILED,
                component_ids=stage.component_ids,
                duration_ms=round(duration_ms, 2),
                error=str(e),
            )

    def _build_stage_config(self, stage) -> JobConfig:
        """Build a minimal JobConfig for a single stage's components."""
        stage_components = [
            c for c in self.config.components
            if c.id in stage.component_ids
        ]
        stage_flows = [
            f for f in self.config.flows
            if f.source in stage.component_ids and f.target in stage.component_ids
        ]
        return JobConfig(
            name=f"{self.job_name}__{stage.stage_id}",
            components=stage_components,
            flows=stage_flows,
        )

    def _create_stage_components(
        self, stage, context: ExecutionContext
    ) -> None:
        """Create component instances for a single stage."""
        for comp_config in self.config.components:
            if comp_config.id not in stage.component_ids:
                continue
            if comp_config.id in self._components:
                continue  # already created

            comp_type = comp_config.type.lower()
            component_class = REGISTRY.get(comp_type)
            if component_class is None:
                raise ValueError(
                    f"Unknown component type: {comp_type}. "
                    f"Registered: {REGISTRY.list_types()}"
                )

            component = component_class(
                component_id=comp_config.id,
                config=comp_config.config,
                context=context.context_vars,
                routine_registry=self.routine_manager.get_registry(),
                streaming=self.streaming,
            )

            errors = component.validate()
            if errors:
                raise ValueError(
                    f"Component {comp_config.id} validation errors: {errors}"
                )

            self._components[comp_config.id] = component

    def _create_components(self, context: ExecutionContext) -> None:
        """Instantiate all components using the registry."""
        for comp_config in self.config.components:
            comp_type = comp_config.type.lower()

            # Look up in registry
            component_class = REGISTRY.get(comp_type)
            if component_class is None:
                raise ValueError(
                    f"Unknown component type: {comp_type}. "
                    f"Registered: {REGISTRY.list_types()}"
                )

            component = component_class(
                component_id=comp_config.id,
                config=comp_config.config,
                context=context.context_vars,
                routine_registry=self.routine_manager.get_registry(),
                streaming=self.streaming,
            )

            errors = component.validate()
            if errors:
                raise ValueError(
                    f"Component {comp_config.id} validation errors: {errors}"
                )

            self._components[comp_config.id] = component

    def _execute_component(
        self, component_id: str, context: ExecutionContext
    ) -> None:
        """Execute a single component with barrier-aware logic."""
        component = self._components[component_id]
        comp_type = component.__class__.__name__
        dag_node = self.dag.get_node(component_id)

        # Gather inputs from upstream
        inputs = {}
        rows_in = {}
        for upstream_id in dag_node.upstream:
            flow = self._get_flow(upstream_id, component_id)
            source_output = flow.output if flow else "main"
            target_input = flow.input if flow else "main"
            output_data = context.get_output(upstream_id, source_output)
            if output_data is not None:
                inputs[target_input] = output_data
                # Track input row counts from upstream barrier stats
                upstream_stats = context.get_component_stats(upstream_id) or {}
                upstream_rows = upstream_stats.get("rows_out", {})
                if source_output in upstream_rows:
                    rows_in[target_input] = upstream_rows[source_output]

        # Execute and time
        start = time.perf_counter()
        result = component.apply(inputs)
        duration_ms = (time.perf_counter() - start) * 1000

        # Check for iterate result
        if isinstance(result, dict) and "__iterations__" in result:
            iterations = result["__iterations__"]
            logger.info(
                f"[{self.job_name}] {component_id} ({comp_type}): "
                f"{len(iterations)} iterations [BARRIER] ({duration_ms:.1f}ms)"
            )
            self._execute_iterations(component_id, iterations, context)
            # Record stats
            context.record_component_stats(component_id, {
                "type": comp_type,
                "duration_ms": round(duration_ms, 2),
                "iterations": len(iterations),
                "barrier": True,
            })
            # Decrement upstream refs
            for upstream_id in dag_node.upstream:
                context.decrement_ref(upstream_id)
            return  # skip normal output storage

        # Handle context updates from utility components (e.g., context_load)
        ctx_load_stats = None
        if isinstance(result, dict) and "__context_updates__" in result:
            ctx_updates = result.pop("__context_updates__")
            for key, value in ctx_updates.items():
                context.context_vars[key] = value
            logger.info(
                f"[{self.job_name}] {component_id} ({comp_type}): "
                f"loaded {len(ctx_updates)} context variable(s) ({duration_ms:.1f}ms)"
            )
            # Extract stats for inclusion in component stats
            ctx_load_stats = result.pop("__context_load_stats__", None)

        # Determine barrier status
        is_barrier = component.is_barrier or len(result) > 1

        # Materialize at barriers
        rows_out = {}
        if is_barrier and result:
            materialized = {}
            for name, data in result.items():
                if isinstance(data, pl.LazyFrame):
                    df = data.collect(**self._collect_kwargs)
                    materialized[name] = df.lazy()  # re-wrap for downstream
                    rows_out[name] = len(df)
                elif isinstance(data, pl.DataFrame):
                    materialized[name] = data.lazy()
                    rows_out[name] = len(data)
                else:
                    materialized[name] = data
                    rows_out[name] = 0
            result = materialized

        # Store outputs
        for output_name, data in result.items():
            context.store_output(component_id, output_name, data)

        # Record stats
        comp_stats = {
            "type": comp_type,
            "duration_ms": round(duration_ms, 2),
            "rows_out": rows_out,
            "barrier": is_barrier,
        }
        if ctx_load_stats:
            comp_stats["context_load"] = ctx_load_stats
        context.record_component_stats(component_id, comp_stats)

        # Component execution log
        self._log_component(
            component_id, comp_type, duration_ms, is_barrier,
            rows_in, rows_out, result,
        )

        # Decrement ref counts on upstream (free memory)
        for upstream_id in dag_node.upstream:
            context.decrement_ref(upstream_id)

    def _execute_iterations(
        self, iterate_id: str, iterations: list, context: ExecutionContext
    ) -> None:
        """Execute downstream sub-pipeline once per iteration."""
        # Get downstream component IDs in execution order
        downstream = self._get_downstream_subpipeline(iterate_id)

        # Mark downstream components as iterate-managed so the main loop skips them
        self._iterate_managed.update(downstream)

        for i, iter_ctx in enumerate(iterations):
            logger.debug(f"Iteration {i+1}/{len(iterations)} for {iterate_id}")

            # Inject iteration variables into context
            for key, value in iter_ctx.items():
                context.context_vars[key] = value

            # Execute each downstream component
            for comp_id in downstream:
                self._execute_component(comp_id, context)

    def _get_downstream_subpipeline(self, iterate_id: str) -> list:
        """Get downstream components in topological order."""
        execution_order = self.dag.get_execution_order()
        dag_node = self.dag.get_node(iterate_id)

        # Find all components reachable from iterate_id
        reachable = set()
        to_visit = list(dag_node.downstream)
        while to_visit:
            node_id = to_visit.pop(0)
            if node_id not in reachable:
                reachable.add(node_id)
                downstream_node = self.dag.get_node(node_id)
                to_visit.extend(downstream_node.downstream)

        # Return in topological order
        return [c for c in execution_order if c in reachable]

    def _log_component(
        self,
        component_id: str,
        comp_type: str,
        duration_ms: float,
        is_barrier: bool,
        rows_in: Dict,
        rows_out: Dict,
        result: Dict,
    ) -> None:
        """Log component execution with row counts at barriers."""
        tag = "[BARRIER]" if is_barrier else "[lazy]"

        if is_barrier and rows_out:
            # Format per-output row counts
            if len(rows_out) == 1:
                out_key = next(iter(rows_out))
                out_count = rows_out[out_key]
                # Include input count if available
                if rows_in:
                    in_count = next(iter(rows_in.values()))
                    row_info = f" | {in_count:,} rows in -> {out_count:,} rows out"
                else:
                    row_info = f" | {out_count:,} rows out"
            else:
                # Multi-output: show each port
                parts = [f"{k}={v:,}" for k, v in rows_out.items()]
                if rows_in:
                    in_count = next(iter(rows_in.values()))
                    row_info = f" | {in_count:,} rows in -> {', '.join(parts)}"
                else:
                    row_info = f" | {', '.join(parts)}"
        else:
            row_info = ""

        logger.info(
            f"[{self.job_name}] {component_id} ({comp_type}): "
            f"{tag} ({duration_ms:.1f}ms){row_info}"
        )

    @staticmethod
    def _get_total_sink_rows(result: Dict) -> int:
        """Sum rows written across all sink (barrier) components."""
        total = 0
        for stats in result.get("components", {}).values():
            if stats.get("barrier") and stats.get("rows_out"):
                for count in stats["rows_out"].values():
                    total += count
        return total

    def _get_flow(self, source: str, target: str):
        """Get flow definition between two components."""
        for flow in self.config.flows:
            if flow.source == source and flow.target == target:
                return flow
        return None

    def get_component(self, component_id: str) -> Optional[Component]:
        """Get a component instance by ID."""
        return self._components.get(component_id)

    def get_routine_manager(self) -> RoutineManager:
        """Get the routine manager."""
        return self.routine_manager

    def __repr__(self) -> str:
        return f"PyETLEngine(job={self.job_name}, components={len(self.dag)})"
