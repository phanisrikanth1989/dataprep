"""Map(BaseComponent) -- top-level orchestrator for the tMap engine component.

Delegates all real work to other modules in the map/ package. See
docs/superpowers/specs/2026-05-18-tmap-rewrite-design.md Section 5 for
the full data flow.
"""
from __future__ import annotations

import copy
import logging
import time
from typing import Any, Optional

import pandas as pd

from src.v1.engine.base_component import BaseComponent, ExecutionMode
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.exceptions import ComponentExecutionError, ConfigurationError

from .map_config import MapConfig, parse_config, validate_config, has_any_java_marker


logger = logging.getLogger(__name__)


@REGISTRY.register("Map", "tMap")
class Map(BaseComponent):
    """tMap engine implementation (modular rewrite)."""

    def _fresh_config(self) -> None:
        """Re-derive self.config from _original_config. Helper for tests."""
        self.config = copy.deepcopy(self._original_config)

    def _resolve_expressions(self) -> None:
        """Skip parent's Java expression resolution.

        Row-level {{java}} markers reference data that doesn't exist at
        config-resolution time; they're evaluated per-row inside the
        compiled Groovy script. We only resolve context vars in scalar
        config fields here.
        """
        if self.context_manager is None:
            return
        for key in ("die_on_error", "label", "enable_auto_convert_type",
                    "rows_buffer_size", "output_chunk_size"):
            if key in self.config and isinstance(self.config[key], str):
                self.config[key] = self.context_manager.resolve_string(
                    self.config[key]
                )

    def _select_mode(self, input_data) -> ExecutionMode:
        """Always BATCH -- tMap handles its own chunking via the bridge."""
        return ExecutionMode.BATCH

    def _validate_config(self) -> None:
        cfg = parse_config(self.config)
        validate_config(cfg, java_bridge_available=self.java_bridge is not None)
        self._parsed_cfg = cfg

    def _update_stats_from_result(self, result: dict) -> None:
        """Sum rows across all named outputs (not just main/reject)."""
        total = 0
        reject_count = 0
        for name, df in result.items():
            if name == "stats" or not isinstance(df, pd.DataFrame) or df.empty:
                continue
            n = len(df)
            total += n
            out_cfg = self._output_by_name(name)
            if out_cfg and (out_cfg.is_reject or out_cfg.inner_join_reject
                            or out_cfg.catch_output_reject):
                reject_count += n
        self.stats["NB_LINE"] += total
        self.stats["NB_LINE_OK"] += total - reject_count
        self.stats["NB_LINE_REJECT"] += reject_count

    def _output_by_name(self, name: str):
        for o in self._parsed_cfg.outputs:
            if o.name == name:
                return o
        return None

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        from .map_bridge_sync import push_runtime_state_to_bridge
        from .map_compiled_script import build_active_script, build_reject_script
        from .map_joins import (
            JoinStrategy, classify_join_strategy, compute_joined_df_schema,
            apply_filter, join_simple_equality, join_computed_equality,
            join_filter_as_match, join_reload_per_row, join_constant_key,
        )
        from .map_reject_routing import route_rejects

        cfg = self._parsed_cfg
        inputs = self._parse_inputs(input_data)
        if inputs is None:
            return self._create_empty_outputs(cfg)

        main_df = inputs.get(cfg.main.name)
        if main_df is None or main_df.empty:
            return self._create_empty_outputs(cfg)

        # 1. Main filter
        if cfg.main.activate_filter and cfg.main.filter:
            before_count = len(main_df)
            main_df = apply_filter(
                main_df, cfg.main.filter,
                self._bridge_eval_fn(), cfg.main.name, [],
            )
            logger.info(
                "[%s] main filter: %d -> %d rows (filter=%s)",
                self.id, before_count, len(main_df), cfg.main.filter,
            )
            if main_df.empty:
                return self._create_empty_outputs(cfg)

        # 2. Join lookups sequentially
        joined_df = main_df.copy()
        inner_join_reject_dfs: dict[str, pd.DataFrame] = {}
        consumed_lookups: list[tuple[str, list[dict]]] = []
        temp_join_key_cols: dict[str, str] = {}

        for lk in cfg.lookups:
            lookup_df = inputs.get(lk.name)
            if lookup_df is None or lookup_df.empty:
                logger.info(
                    "[%s] lookup '%s' skipped: %s",
                    self.id, lk.name,
                    "no input data" if lookup_df is None else "empty frame",
                )
                consumed_lookups.append((lk.name, self._lookup_schema(lk.name)))
                continue
            strategy = classify_join_strategy(
                lk,
                main_name=cfg.main.name,
                prior_lookup_names=[n for n, _ in consumed_lookups],
            )
            # Lookup filter is applied here ONLY for strategies where the
            # filter is a pure lookup-side pre-filter (operates on lookup_df
            # alone). Skip for:
            #   - RELOAD: per-row loop handles its own filter substitution
            #   - FILTER_AS_MATCH: the filter is the match condition,
            #     evaluated against the cross product inside
            #     join_filter_as_match (spec section 6)
            if (lk.activate_filter and lk.filter
                    and strategy != JoinStrategy.RELOAD
                    and strategy != JoinStrategy.FILTER_AS_MATCH):
                lookup_df = apply_filter(
                    lookup_df, lk.filter,
                    self._bridge_eval_fn(), cfg.main.name,
                    [n for n, _ in consumed_lookups],
                )
            logger.info(
                "[%s] lookup '%s' strategy=%s match=%s join=%s keys=[%s] "
                "main_rows=%d lookup_rows=%d filter_active=%s",
                self.id, lk.name, strategy.value, lk.matching_mode,
                lk.join_mode,
                ", ".join(
                    f"{jk.lookup_column} <= {jk.expression}"
                    for jk in lk.join_keys
                ),
                len(joined_df), len(lookup_df), lk.activate_filter,
            )
            start = time.perf_counter()
            if strategy == JoinStrategy.SIMPLE:
                joined_df, rejects = join_simple_equality(joined_df, lookup_df, lk)
            elif strategy == JoinStrategy.CONSTANT_KEY:
                joined_df, rejects = join_constant_key(
                    joined_df, lookup_df, lk,
                    main_name=cfg.main.name,
                    prior_lookups=[n for n, _ in consumed_lookups],
                    constant_eval_fn=self._constant_eval_fn(),
                )
            elif strategy == JoinStrategy.COMPUTED:
                joined_df, rejects = join_computed_equality(
                    joined_df, lookup_df, lk,
                    main_name=cfg.main.name,
                    prior_lookups=[n for n, _ in consumed_lookups],
                    bridge_eval_fn=self._bridge_eval_fn(),
                )
            elif strategy == JoinStrategy.FILTER_AS_MATCH:
                joined_df, rejects = join_filter_as_match(
                    joined_df, lookup_df, lk,
                    main_name=cfg.main.name,
                    prior_lookups=[n for n, _ in consumed_lookups],
                    bridge_eval_fn=self._bridge_eval_fn(),
                )
            else:  # RELOAD
                joined_df, rejects = join_reload_per_row(
                    joined_df, lookup_df, lk,
                    bridge_eval_fn=self._bridge_eval_fn(),
                    main_name=cfg.main.name,
                )
            elapsed = time.perf_counter() - start
            logger.info(
                "[%s] lookup '%s' joined: result_rows=%d rejects=%d elapsed=%.3fs",
                self.id, lk.name, len(joined_df),
                0 if rejects is None else len(rejects),
                elapsed,
            )
            if rejects is not None and not rejects.empty:
                inner_join_reject_dfs[lk.name] = rejects
            consumed_lookups.append((lk.name, self._lookup_schema(lk.name)))

        if joined_df.empty and not inner_join_reject_dfs:
            return self._create_empty_outputs(cfg)

        # 3. Compute joined_df schema (single source of truth for types)
        joined_schema = compute_joined_df_schema(
            main_schema=self._lookup_schema(cfg.main.name),
            consumed_lookups=consumed_lookups,
            variables=cfg.variables,
            temp_join_key_cols=temp_join_key_cols,
        )

        # 4. Build active script + push state + execute
        active_script = build_active_script(cfg)
        push_runtime_state_to_bridge(
            self.context_manager, self.global_map, self.java_bridge,
        )
        component_active_id = f"{self.id}__active"
        logger.info(
            "[%s] compiling active script (%d outputs)",
            self.id, sum(1 for o in cfg.outputs if not o.inner_join_reject),
        )
        self.java_bridge.compile_tmap_script(
            component_id=component_active_id,
            java_script=active_script,
            output_schemas={
                o.name: [c.name for c in o.columns]
                for o in cfg.outputs
                if not o.inner_join_reject
            },
            output_types={
                f"{o.name}_{c.name}": c.type
                for o in cfg.outputs
                if not o.inner_join_reject
                for c in o.columns
            },
            main_table_name=cfg.main.name,
            lookup_names=[n for n, _ in consumed_lookups],
        )
        active_raw = self.java_bridge.execute_compiled_tmap_chunked(
            component_id=component_active_id,
            df=joined_df,
            chunk_size=50000,
            input_columns=list(joined_df.columns),
            schema=joined_schema,
            reject_mode=False,
        )
        errors_df = active_raw.pop("__errors__", None)

        # 5. Reject pass (only if any inner_join_reject configured AND there are rejects to route)
        reject_raw: dict = {}
        has_inner_reject_outputs = any(o.inner_join_reject for o in cfg.outputs)
        if has_inner_reject_outputs and inner_join_reject_dfs:
            reject_source = self._build_reject_row_source(
                inner_join_reject_dfs, joined_df.columns,
            )
            if reject_source is not None and not reject_source.empty:
                reject_script = build_reject_script(cfg)
                component_reject_id = f"{self.id}__reject"
                logger.info(
                    "[%s] compiling reject script (%d outputs)",
                    self.id, sum(1 for o in cfg.outputs if o.inner_join_reject),
                )
                self.java_bridge.compile_tmap_script(
                    component_id=component_reject_id,
                    java_script=reject_script,
                    output_schemas={
                        o.name: [c.name for c in o.columns]
                        for o in cfg.outputs if o.inner_join_reject
                    },
                    output_types={
                        f"{o.name}_{c.name}": c.type
                        for o in cfg.outputs if o.inner_join_reject
                        for c in o.columns
                    },
                    main_table_name=cfg.main.name,
                    lookup_names=[n for n, _ in consumed_lookups],
                )
                push_runtime_state_to_bridge(
                    self.context_manager, self.global_map, self.java_bridge,
                )
                reject_raw = self.java_bridge.execute_compiled_tmap_chunked(
                    component_id=component_reject_id,
                    df=reject_source,
                    chunk_size=50000,
                    input_columns=list(reject_source.columns),
                    schema=joined_schema,
                    reject_mode=False,
                )

        # 6. Route rejects to final result dict
        return route_rejects(
            active_results=active_raw,
            reject_results=reject_raw,
            errors_df=errors_df,
            inner_join_reject_dfs=inner_join_reject_dfs,
            cfg=cfg,
            joined_df=joined_df,
        )

    # ---- helpers ----

    def _parse_inputs(self, input_data) -> dict[str, pd.DataFrame] | None:
        if input_data is None:
            return None
        if isinstance(input_data, dict):
            return input_data
        if isinstance(input_data, pd.DataFrame):
            return {self._parsed_cfg.main.name: input_data}
        return None

    def _create_empty_outputs(self, cfg: MapConfig) -> dict[str, pd.DataFrame]:
        return {
            o.name: pd.DataFrame(columns=[c.name for c in o.columns])
            for o in cfg.outputs
        }

    def _lookup_schema(self, flow_name: str) -> list[dict]:
        m = getattr(self, "schema_inputs_map", None)
        if isinstance(m, dict) and flow_name in m:
            return m[flow_name]
        return []

    def _build_reject_row_source(
        self, inner_join_reject_dfs: dict[str, pd.DataFrame],
        joined_columns,
    ) -> pd.DataFrame | None:
        frames = [
            df.reindex(columns=joined_columns)
            for df in inner_join_reject_dfs.values()
            if df is not None and not df.empty
        ]
        if not frames:
            return None
        return pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]

    def _bridge_eval_fn(self):
        """Build the closure passed to map_joins for bridge eval."""
        if self.java_bridge is None:
            return None
        from .map_bridge_sync import push_runtime_state_to_bridge

        def fn(df, expressions, main_table_name, lookup_names):
            push_runtime_state_to_bridge(
                self.context_manager, self.global_map, self.java_bridge,
            )
            return self.java_bridge.execute_tmap_preprocessing(
                df=df, expressions=expressions,
                main_table_name=main_table_name,
                lookup_table_names=lookup_names,
            )
        return fn

    def _constant_eval_fn(self):
        """Build the closure passed to join_constant_key for one-shot bridge eval."""
        if self.java_bridge is None:
            return None
        from .map_bridge_sync import push_runtime_state_to_bridge

        def fn(expressions):
            push_runtime_state_to_bridge(
                self.context_manager, self.global_map, self.java_bridge,
            )
            return self.java_bridge.execute_batch_one_time_expressions(
                expressions,
            )
        return fn
