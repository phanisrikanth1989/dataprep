"""Engine component for Map (tMap).

Multi-flow data mapping with lookup joins, variable evaluation, expression-based
column mappings, and multi-output routing. Preserves hybrid architecture: pandas
for bulk equality joins, Java bridge for expression evaluation.

Config keys consumed (8 total):
  inputs            (dict)  -- main input + lookups list with join keys, modes
  variables         (list)  -- variable definitions with expressions
  outputs           (list)  -- output tables with column expressions, filters, reject flags
  die_on_error      (bool, default True)  -- raise on expression error
  output_chunk_size (str, default "50000")    -- compiled output script chunk size (D-05)
  rows_buffer_size  (str, legacy alias for output_chunk_size, default "50000")
  enable_auto_convert_type  (bool, default False)  -- auto-cast join key types
  parallel_execution (bool, default True)  -- parallel forEach in compiled scripts
  label             (str, default "")  -- component label
"""
import logging
import re
import types
from decimal import Decimal
from typing import Any, Optional

import numpy as np
import pandas as pd

from ...base_component import BaseComponent, ExecutionMode
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, ComponentExecutionError, DataValidationError
from ._code_component_mixin import _SAFE_NAMESPACE_GLOBALS, _build_safe_builtins

logger = logging.getLogger(__name__)

# Pattern to detect simple column references: table.column
_SIMPLE_COLUMN_RE = re.compile(r'^([a-zA-Z_]\w*)\.([a-zA-Z_]\w*)$')

# Pattern to detect table.column references in expressions (non-anchored)
_ROW_REF_PATTERN = re.compile(
    r'\b([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)\b'
)

# Matching modes
_UNIQUE_MATCH = "UNIQUE_MATCH"
_FIRST_MATCH = "FIRST_MATCH"
_LAST_MATCH = "LAST_MATCH"
_ALL_MATCHES = "ALL_MATCHES"

# Lookup modes
_LOAD_ONCE = "LOAD_ONCE"
_RELOAD_AT_EACH_ROW = "RELOAD_AT_EACH_ROW"
_CACHE_OR_RELOAD = "CACHE_OR_RELOAD"

# Chunk size for preprocessing and compiled script execution
_DEFAULT_CHUNK_SIZE = 50000

# Parallel stream processing for compiled script execution.
# True = IntStream.parallel().forEach() for high throughput (thread-safe:
#   Var map is local to each lambda iteration, output indices use AtomicInteger,
#   error tracking uses ConcurrentHashMap).
# False = IntStream.forEach() for sequential processing.
# Configurable via 'parallel_execution' config key (default: True).
_DEFAULT_PARALLEL_EXECUTION = True

# Size guard thresholds for cartesian/cross-table joins
_WARN_RESULT_ROWS = 10_000_000
_FAIL_RESULT_ROWS = 100_000_000

# Java marker prefix
_JAVA_MARKER = "{{java}}"

# Locality buckets for per-key join classification (D-03)
_LOCALITY_CONTEXT = "context"        # only context/globalMap/Var refs, no row data
_LOCALITY_MAIN_SIDE = "main_side"    # only main + previously-joined lookups (in joined_df)
_LOCALITY_LOOKUP_SIDE = "lookup_side"  # only the current lookup
_LOCALITY_TWO_SIDED = "two_sided"    # references both main side and current lookup


class _VarBag:
    """Live attribute-access wrapper around a single shared dict.

    Used for the tMap ``Var`` namespace in the Python-eval path.
    Sequential variable evaluations mutate the same backing dict via
    ``__setattr__``, so later variable expressions see earlier assignments
    through ``__getattr__``.

    Why not ``types.SimpleNamespace``?  SimpleNamespace.__init__(**d) copies
    keys onto the instance at construction time.  Mutating the original dict
    afterwards does NOT propagate.  That breaks chained Var eval:
    ``Var.v2 = Var.v1 + "_USD"`` would see ``Var.v1`` as undefined because
    the SimpleNamespace was constructed before v1 was assigned.

    Args:
        d: Optional initial dict. A new empty dict is created if None.
    """

    __slots__ = ("_d",)

    def __init__(self, d: dict | None = None) -> None:
        object.__setattr__(self, "_d", d if d is not None else {})

    def __getattr__(self, name: str) -> Any:
        # Called only when normal attribute lookup fails (not in __slots__).
        try:
            return object.__getattribute__(self, "_d")[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name: str, value: Any) -> None:
        object.__getattribute__(self, "_d")[name] = value


class _NullNamespace:
    """Read-only namespace where every attribute access returns ``None``.

    Used for lookup tables that had no rows (empty lookup or unmatched
    left-outer-join rows).  Talend left-outer semantics return ``null``
    for all lookup columns when there is no match; this class replicates
    that by silently returning ``None`` for any attribute reference.
    """

    def __getattr__(self, name: str) -> None:  # noqa: ANN001
        return None

    def __setattr__(self, name: str, value: Any) -> None:  # noqa: ANN001
        pass  # discard -- null namespaces are read-only


class _NullRow:
    """Sentinel for a lookup row that was not matched in an inner join.

    Unlike ``_NullNamespace`` (which silently returns ``None`` to mirror
    Talend left-outer-join semantics), ``_NullRow`` raises
    ``AttributeError`` to signal that a column reference on a failed
    inner-join lookup is an expression-evaluation error.  The error
    propagates through the existing per-column ``_eval_expr`` machinery
    -- with ``die_on_error=True`` it surfaces as
    ``ComponentExecutionError``; with ``die_on_error=False`` it is logged
    as a warning and the column resolves to ``None``.  This matches the
    Talend inner-join-reject semantic where dereferencing the failing
    lookup is an error, not a silent null (D-04 of phase 05.4-02).

    ASCII-only error message (per project convention -- RHEL log targets
    must remain pure ASCII).
    """

    def __getattr__(self, name: str) -> None:  # noqa: ANN001
        raise AttributeError(
            f"lookup was not matched; column '{name}' unavailable on reject row"
        )

    def __setattr__(self, name: str, value: Any) -> None:  # noqa: ANN001
        pass  # discard -- null rows are read-only


def _infer_arrow_schema_dict(df: pd.DataFrame) -> dict[str, str]:
    """Infer the bridge-side type string for each column of ``df``.

    Maps pandas dtypes to one of the 7 Java-bridge type strings
    (str, int, float, bool, datetime, Decimal, object).

    Uses case-insensitive dtype matching so pandas nullable extension dtypes
    such as ``Int64``, ``Float64`` and ``boolean`` map to the same bridge
    types as their numpy equivalents (``int64``, ``float64``, ``bool``).
    Without this, ``"int" in "Int64"`` is False and the column would be
    serialized as a String -- breaking expressions like
    ``String.format("%03d", row1.empid)`` with ``IllegalFormatConversionException``.

    For ``object`` dtype columns, samples the first non-null value to detect
    Decimal / datetime / date payloads so they round-trip as BigDecimal /
    Timestamp instead of String.
    """
    import datetime as _dt

    schema: dict[str, str] = {}
    for col in df.columns:
        dtype_lower = str(df[col].dtype).lower()
        if "int" in dtype_lower:
            schema[col] = "int"
        elif "float" in dtype_lower:
            schema[col] = "float"
        elif "datetime" in dtype_lower:
            schema[col] = "datetime"
        elif "bool" in dtype_lower:
            schema[col] = "bool"
        elif "decimal" in dtype_lower:
            schema[col] = "Decimal"
        else:
            # object dtype -- sample first non-null value to detect payload type
            sample = None
            try:
                non_null = df[col].dropna()
                if len(non_null) > 0:
                    sample = non_null.iloc[0]
            except Exception:
                sample = None
            if isinstance(sample, Decimal):
                schema[col] = "Decimal"
            elif isinstance(sample, (_dt.datetime, pd.Timestamp)):
                schema[col] = "datetime"
            else:
                schema[col] = "str"
    return schema


@REGISTRY.register("Map", "tMap")
class Map(BaseComponent):
    """tMap engine implementation.

    Multi-flow data mapping with lookup joins, variable evaluation,
    expression-based column mappings, and multi-output routing.

    Config keys:
        inputs: Main input and lookups list with join keys and modes.
        variables: Variable definitions with expressions.
        outputs: Output tables with column expressions, filters, reject flags.
        die_on_error: Raise on expression error (default True).
        rows_buffer_size: Buffer size hint (default "2000000").
        enable_auto_convert_type: Auto-cast join key types (default False).
        label: Component label (default "").
    """

    # ------------------------------------------------------------------
    # Lifecycle Hook Overrides
    # ------------------------------------------------------------------

    def _resolve_expressions(self) -> None:
        """Resolve context variables on scalar config fields only.

        tMap's expressions (output columns, filters, variables, join keys)
        reference row data (row1.column, lookup1.column) that do not exist
        at config resolution time. We skip Java expression resolution
        entirely and only resolve context variables on scalar config fields.

        Does NOT delegate to the parent class resolve method.
        """
        if self.context_manager is None:
            return
        for key in ("die_on_error", "rows_buffer_size", "output_chunk_size", "label",
                     "enable_auto_convert_type", "cross_join_chunk_size"):
            if key in self.config and isinstance(self.config[key], str):
                self.config[key] = self.context_manager.resolve_string(
                    self.config[key]
                )

    def _select_mode(self, input_data) -> ExecutionMode:
        """Always BATCH -- tMap handles its own chunking via Java bridge."""
        return ExecutionMode.BATCH

    def _update_stats_from_result(self, result: dict) -> None:
        """Sum rows across ALL named output DataFrames.

        tMap returns arbitrary named outputs (out1, reject1, etc.),
        not just main/reject. Iterates all result keys except 'stats'.

        Args:
            result: Dict returned by _process().
        """
        total_rows = 0
        reject_rows = 0
        for key, value in result.items():
            if key == "stats":
                continue
            if isinstance(value, pd.DataFrame) and not value.empty:
                count = len(value)
                total_rows += count
                output_cfg = self._get_output_config(key)
                if output_cfg and (output_cfg.get("is_reject")
                                   or output_cfg.get("inner_join_reject")):
                    reject_rows += count
        self.stats["NB_LINE"] += total_rows
        self.stats["NB_LINE_OK"] += total_rows - reject_rows
        self.stats["NB_LINE_REJECT"] += reject_rows

    # ------------------------------------------------------------------
    # Per-flow Schema Access (ENG-CR-04 CONSUMER)
    # ------------------------------------------------------------------

    def _schema_for_flow(self, flow_name: str) -> Optional[list]:
        """Return per-flow schema from schema_inputs_map[flow_name] when present.

        Falls back to self.input_schema (legacy single-map) for back-compat
        with non-multi-input components or pre-Phase-7.1 configs.

        ENG-CR-04 CONSUMER side (Phase 7.1, REVIEWS.md HIGH gap).

        The converter producer fix (same plan, Task 4) writes
        comp_config["schema"]["inputs"][flow_name] = list_of_column_dicts.
        The engine initialization (engine.py) sets
        component.schema_inputs_map = comp_config["schema"].get("inputs", {}).
        This method reads from schema_inputs_map, not from self.config["inputs"]
        (which is the join config, not the schema map).

        Args:
            flow_name: The flow/connector name (e.g. "row1", "row2", "main_flow").

        Returns:
            List of column dicts for the flow, or self.input_schema for back-compat.
        """
        schema_inputs_map = getattr(self, "schema_inputs_map", None)
        if isinstance(schema_inputs_map, dict) and flow_name in schema_inputs_map:
            flow_schema = schema_inputs_map[flow_name]
            if isinstance(flow_schema, list):
                return flow_schema
            # Tolerate nested {"schema": [...]} format
            if isinstance(flow_schema, dict) and "schema" in flow_schema:
                return flow_schema["schema"]
        # Back-compat: legacy single-map behavior (pre-7.1 or single-input components)
        return getattr(self, "input_schema", None)

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate tMap component configuration.

        Raises:
            ConfigurationError: If configuration is invalid.
        """
        if "inputs" not in self.config or not isinstance(self.config["inputs"], dict):
            raise ConfigurationError(
                f"[{self.id}] Missing or invalid 'inputs' config key"
            )
        inputs_cfg = self.config["inputs"]
        if "main" not in inputs_cfg:
            raise ConfigurationError(
                f"[{self.id}] Missing 'inputs.main' config key"
            )
        if "name" not in inputs_cfg["main"]:
            raise ConfigurationError(
                f"[{self.id}] Missing 'inputs.main.name' config key"
            )
        lookups = inputs_cfg.get("lookups", [])
        if not isinstance(lookups, list):
            raise ConfigurationError(
                f"[{self.id}] 'inputs.lookups' must be a list"
            )
        for i, lookup in enumerate(lookups):
            if "name" not in lookup:
                raise ConfigurationError(
                    f"[{self.id}] Lookup [{i}] missing 'name'"
                )
            if "join_keys" not in lookup or not isinstance(lookup["join_keys"], list):
                raise ConfigurationError(
                    f"[{self.id}] Lookup '{lookup.get('name', i)}' missing "
                    f"or invalid 'join_keys'"
                )
            for j, jk in enumerate(lookup["join_keys"]):
                if "lookup_column" not in jk:
                    raise ConfigurationError(
                        f"[{self.id}] Lookup '{lookup['name']}' join_key [{j}] "
                        f"missing 'lookup_column'"
                    )
                if "expression" not in jk:
                    raise ConfigurationError(
                        f"[{self.id}] Lookup '{lookup['name']}' join_key [{j}] "
                        f"missing 'expression'"
                    )
            if "join_mode" not in lookup:
                raise ConfigurationError(
                    f"[{self.id}] Lookup '{lookup['name']}' missing 'join_mode'"
                )

        if "outputs" not in self.config or not isinstance(self.config["outputs"], list):
            raise ConfigurationError(
                f"[{self.id}] Missing or invalid 'outputs' config key"
            )
        if len(self.config["outputs"]) < 1:
            raise ConfigurationError(
                f"[{self.id}] At least one output is required"
            )
        for i, output in enumerate(self.config["outputs"]):
            if "name" not in output:
                raise ConfigurationError(
                    f"[{self.id}] Output [{i}] missing 'name'"
                )
            if "columns" not in output or not isinstance(output["columns"], list):
                raise ConfigurationError(
                    f"[{self.id}] Output '{output.get('name', i)}' missing "
                    f"or invalid 'columns'"
                )

        # D-01: Hard-fail when any {{java}} marker is present but bridge is unavailable.
        # This fires at _validate_config time (called from execute() before _process)
        # so the job fails fast rather than silently emitting empty cells.
        if self._has_any_java_marker() and self.java_bridge is None:
            raise ConfigurationError(
                f"[{self.id}] tMap config contains {{{{java}}}} expressions but Java bridge is "
                "unavailable. Either start the bridge (java_config.enabled=true) "
                "or remove Java expressions from the job."
            )

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data=None) -> dict:
        """Process tMap transformation.

        Receives Dict[flow_name, DataFrame] from OutputRouter.
        Returns Dict[output_name, DataFrame] for downstream routing.

        Args:
            input_data: Dict of DataFrames keyed by flow name, or single
                DataFrame, or None.

        Returns:
            Dict mapping output names to DataFrames.
        """
        # Step 1: Parse input
        inputs = self._parse_inputs(input_data)
        if inputs is None:
            return self._create_empty_outputs()

        config = self.config
        main_config = config["inputs"]["main"]
        lookups_config = config["inputs"].get("lookups", [])
        variables_config = config.get("variables", [])
        outputs_config = config["outputs"]
        main_name = main_config["name"]

        main_df = inputs.get(main_name)
        if main_df is None or main_df.empty:
            logger.warning(
                f"[{self.id}] Main input '{main_name}' is empty"
            )
            return self._create_empty_outputs()

        logger.info(
            f"[{self.id}] Processing {len(main_df)} main rows "
            f"with {len(lookups_config)} lookups"
        )

        # Step 2: Apply main input filter
        if main_config.get("activate_filter") and main_config.get("filter"):
            main_df = self._apply_filter(
                main_df, main_config["filter"], main_name, []
            )
            if main_df.empty:
                logger.warning(f"[{self.id}] Main input empty after filter")
                return self._create_empty_outputs()

        # Step 3: Process lookups sequentially
        joined_df = main_df.copy()
        inner_join_reject_dfs: dict[str, pd.DataFrame] = {}
        joined_lookup_names: list[str] = []

        for lookup_config in lookups_config:
            lookup_name = lookup_config["name"]
            lookup_df = inputs.get(lookup_name)

            if lookup_df is None or lookup_df.empty:
                logger.warning(
                    f"[{self.id}] Lookup '{lookup_name}' is empty, skipping"
                )
                joined_lookup_names.append(lookup_name)
                continue

            # Read lookup mode BEFORE filter application
            lookup_mode = lookup_config.get("lookup_mode", _LOAD_ONCE)

            # Determine join_keys early (needed for filter-locality check below)
            join_keys = lookup_config.get("join_keys", [])

            # Apply lookup filter with locality awareness (D-03).
            # For empty join_keys + activate_filter: the filter may be two-sided
            # (referencing both row1 and row2), which means it CANNOT be applied
            # to the lookup alone -- it must be used as the match condition inside
            # the chunked cross-product. Classify the filter locality first.
            # For non-empty join_keys: apply the filter pre-join as before.
            if (lookup_config.get("activate_filter")
                    and lookup_config.get("filter")
                    and lookup_mode != _RELOAD_AT_EACH_ROW):
                if not join_keys:
                    # Empty-keys path: check filter locality before applying.
                    # Two-sided or main-side filters cannot be applied to lookup
                    # alone; they are handled inside the empty-keys dispatch below.
                    filter_expr = lookup_config["filter"]
                    filter_locality = self._classify_key_locality(
                        filter_expr, main_name, lookup_name, joined_lookup_names
                    )
                    if filter_locality == _LOCALITY_LOOKUP_SIDE:
                        # Lookup-side-only filter: safe to pre-filter the lookup
                        # (reduces cross-product size before join).
                        lookup_df = self._apply_filter(
                            lookup_df, filter_expr, lookup_name, joined_lookup_names
                        )
                    # else: two_sided / main_side / context filters are deferred
                    # to the empty-keys cross-product dispatch below.
                else:
                    # Non-empty join_keys: apply filter unconditionally as before.
                    lookup_df = self._apply_filter(
                        lookup_df, lookup_config["filter"],
                        lookup_name, joined_lookup_names
                    )

            # Route to appropriate join handler

            if lookup_mode == _RELOAD_AT_EACH_ROW:
                joined_df, rejects = self._join_reload_per_row(
                    joined_df, lookup_df, lookup_config
                )
            else:
                # D-03: locality-based per-key classification replaces the old
                # coarse _classify_join_type bucket.
                if not join_keys:
                    # D-03 empty-keys dispatch (issue 2c fix).
                    # Empty join_keys -> dispatch based on filter presence and locality.
                    # The lookup-side-only filter was already applied above (pre-filter).
                    # Two-sided / main-side / context filters are used as match conditions.
                    match_expr: Optional[str] = None
                    if (lookup_config.get("activate_filter")
                            and lookup_config.get("filter")):
                        filter_expr = lookup_config["filter"]
                        filter_locality = self._classify_key_locality(
                            filter_expr, main_name, lookup_name, joined_lookup_names
                        )
                        if filter_locality != _LOCALITY_LOOKUP_SIDE:
                            # Two-sided, main-side, or context filter -> use as
                            # match condition in the chunked cross-product.
                            match_expr = filter_expr
                        # else: already pre-applied above; pure cartesian now.
                    else:
                        logger.warning(
                            f"[{self.id}] Pure cartesian join with lookup "
                            f"'{lookup_name}' (no keys, no filter) -- O(n*m)."
                        )

                    lookup_df_prefixed = self._prefix_lookup_columns(lookup_df, lookup_name)
                    cross_result = self._chunked_cross_product(
                        joined_df, lookup_df_prefixed,
                        match_expr=match_expr,
                        main_name=main_name,
                        lookup_name=lookup_name,
                        joined_lookup_names=joined_lookup_names,
                    )

                    join_mode = lookup_config.get("join_mode", "LEFT_OUTER_JOIN")
                    rejects = None
                    if join_mode == "INNER_JOIN":
                        main_cols = list(joined_df.columns)
                        if not cross_result.empty:
                            matched_main = cross_result[main_cols].drop_duplicates()
                            joined_with_flag = joined_df.merge(
                                matched_main.assign(__matched__=True),
                                on=main_cols, how="left",
                            )
                            unmatched = joined_with_flag[
                                joined_with_flag["__matched__"].isna()
                            ].drop(columns=["__matched__"])
                            if not unmatched.empty:
                                rejects = unmatched.copy()
                        else:
                            rejects = joined_df.copy()

                    if cross_result.empty and join_mode != "INNER_JOIN":
                        rejects = None
                        # Keep joined_df unchanged (no match from this lookup)
                    else:
                        joined_df = cross_result

                else:
                    localities = [
                        self._classify_key_locality(
                            jk["expression"], main_name, lookup_name,
                            joined_lookup_names
                        )
                        for jk in join_keys
                    ]
                    if any(loc == _LOCALITY_TWO_SIDED for loc in localities):
                        # Any two-sided key -> cross-product evaluation
                        joined_df, rejects = self._join_cross_table(
                            joined_df, lookup_df, lookup_config, joined_lookup_names
                        )
                    elif all(
                        loc in (_LOCALITY_CONTEXT, _LOCALITY_MAIN_SIDE)
                        for loc in localities
                    ):
                        # All keys are context or main-side.
                        # If all are simple column refs -> _join_equality (fast path).
                        # If any are computed -> _join_main_side_computed_key (D-03).
                        exprs_stripped = [
                            self._strip_java_marker(jk["expression"])
                            for jk in join_keys
                        ]
                        if all(self._is_simple_column_ref(e) for e in exprs_stripped):
                            joined_df, rejects = self._join_equality(
                                joined_df, lookup_df, lookup_config
                            )
                        else:
                            # D-03: at least one main-side key is computed.
                            # Batch-eval keys once on joined_df, then pd.merge (O(n+m)).
                            joined_df, rejects = self._join_main_side_computed_key(
                                joined_df, lookup_df, join_keys,
                                main_name, lookup_name, joined_lookup_names,
                                lookup_config
                            )
                    elif all(loc == _LOCALITY_LOOKUP_SIDE for loc in localities):
                        # All keys are lookup-side only.
                        exprs_stripped = [
                            self._strip_java_marker(jk["expression"])
                            for jk in join_keys
                        ]
                        if all(self._is_simple_column_ref(e) for e in exprs_stripped):
                            joined_df, rejects = self._join_equality(
                                joined_df, lookup_df, lookup_config
                            )
                        else:
                            # D-03: at least one lookup-side key is computed.
                            # Batch-eval keys once on lookup_df, then pd.merge (O(n+m)).
                            joined_df, rejects = self._join_lookup_side_computed_key(
                                joined_df, lookup_df, join_keys,
                                main_name, lookup_name, joined_lookup_names,
                                lookup_config
                            )
                    else:
                        # Mixed context + lookup-side -- treat as cross-table
                        joined_df, rejects = self._join_cross_table(
                            joined_df, lookup_df, lookup_config, joined_lookup_names
                        )

            if rejects is not None and not rejects.empty:
                inner_join_reject_dfs[lookup_name] = rejects

            joined_lookup_names.append(lookup_name)

        if joined_df.empty:
            logger.info(f"[{self.id}] No rows after lookups")
            # Still route inner join rejects
            result = self._create_empty_outputs()
            self._route_inner_join_rejects(
                result, inner_join_reject_dfs, outputs_config
            )
            return result

        logger.info(
            f"[{self.id}] After lookups: {len(joined_df)} rows, "
            f"{len(joined_df.columns)} columns"
        )

        # Decide execution path once so both Step 5 and Step 6 use the same decision.
        # D-02: marker-presence anywhere in config is the sole dispatch signal.
        _use_compiled = self._has_any_java_marker()
        # Hard-fail already enforced in _validate_config; assertion is defense-in-depth.
        assert (not _use_compiled) or (self.java_bridge is not None), (
            "Marker-present + bridge-missing should have failed in _validate_config"
        )

        # Step 5: Evaluate variables.
        # SKIPPED when using the compiled Groovy path: the generated script
        # re-evaluates all variables internally (see _build_compiled_script).
        # Running _evaluate_variables first would:
        #   (a) make N unnecessary Java bridge round-trips (one per variable),
        #   (b) populate joined_df with Py4J Java-object proxies (Date,
        #       BigDecimal) that then require toString() Py4J calls during
        #       Arrow serialisation for every subsequent bridge call, and
        #   (c) cause the first call to initialise the Groovy runtime JVM
        #       (10-30 s one-time cost) before the compiled script even starts.
        #
        # D-02 Python-eval path: use _evaluate_variables_py (returns per-row
        # dict, no bridge needed) so _evaluate_outputs_py can build the correct
        # _VarBag per row (sequential Var chaining via live attribute access).
        py_var_columns: dict[str, list] = {}
        if variables_config and not _use_compiled:
            py_var_columns = self._evaluate_variables_py(
                joined_df, variables_config, main_name, joined_lookup_names
            )

        # Steps 6-8: Evaluate outputs (compiled script or Python eval)
        if _use_compiled:
            result = self._evaluate_outputs(
                joined_df, outputs_config, variables_config,
                main_name, joined_lookup_names
            )
        else:
            result = self._evaluate_outputs_py(
                joined_df, outputs_config, py_var_columns,
                main_name, joined_lookup_names
            )

        # Step 9: Route inner join rejects
        self._route_inner_join_rejects(
            result, inner_join_reject_dfs, outputs_config
        )

        return result

    # ------------------------------------------------------------------
    # Input Parsing
    # ------------------------------------------------------------------

    def _parse_inputs(
        self, input_data: Any
    ) -> Optional[dict[str, pd.DataFrame]]:
        """Parse input_data into Dict[flow_name, DataFrame].

        Args:
            input_data: Dict of DataFrames, single DataFrame, or None.

        Returns:
            Dict of DataFrames keyed by flow name, or None if no data.
        """
        if input_data is None:
            return None
        if isinstance(input_data, dict):
            return input_data
        if isinstance(input_data, pd.DataFrame):
            main_name = self.config["inputs"]["main"]["name"]
            return {main_name: input_data}
        return None

    # ------------------------------------------------------------------
    # Filter Evaluation
    # ------------------------------------------------------------------

    def _apply_filter(
        self,
        df: pd.DataFrame,
        filter_expr: str,
        table_name: str,
        lookup_names: list[str],
    ) -> pd.DataFrame:
        """Apply a filter expression to a DataFrame.

        Dispatches based on marker presence (D-02):
        - No ``{{java}}`` marker -> pure-Python eval via ``_apply_filter_py``.
        - ``{{java}}`` marker present (simple col ref or complex) -> Java bridge.

        Args:
            df: DataFrame to filter.
            filter_expr: Filter expression (may have {{java}} prefix).
            table_name: Name of the table being filtered.
            lookup_names: Names of already-joined lookups.

        Returns:
            Filtered DataFrame.
        """
        if not filter_expr:
            return df

        has_marker = filter_expr.startswith(_JAVA_MARKER)
        expr = self._strip_java_marker(filter_expr)

        if not has_marker:
            # No-marker path: pure-Python eval (D-02).
            return self._apply_filter_py(df, expr, table_name)

        if self._is_simple_column_ref(expr):
            match = _SIMPLE_COLUMN_RE.match(expr.strip())
            if match:
                table, column = match.group(1), match.group(2)
                col_name = self._find_column(df, table, column)
                if col_name is not None:
                    mask = df[col_name].astype(bool)
                    filtered = df[mask].copy()
                    logger.info(
                        f"[{self.id}] Filter on {table}.{column}: "
                        f"{len(df)} -> {len(filtered)} rows"
                    )
                    return filtered
                logger.warning(
                    f"[{self.id}] Filter column '{table}.{column}' not found"
                )
                return df

        # Complex expression with marker -- use Java bridge.
        # Note: table_name is used as main_name because this method is called
        # for both main-table and lookup-table filtering. D-04 is addressed by
        # callers passing the full joined_lookup_names list (which already
        # happened correctly at map.py:385-388, the "already correct call site").
        # 05.4-05: bridge submits expr to GroovyShell.parse, so apply the
        # Groovy escape before forwarding.
        expr = self._groovy_escape_expression(expr)
        result = self._evaluate_with_bridge(
            df, {"__filter__": expr}, table_name, lookup_names
        )
        if "__filter__" in result:
            mask = pd.Series(result["__filter__"]).fillna(False).values
            filtered = df[mask].copy()
            logger.info(
                f"[{self.id}] Java filter: {len(df)} -> {len(filtered)} rows"
            )
            return filtered

        return df

    def _apply_filter_per_row(
        self,
        lookup_df: pd.DataFrame,
        filter_expr: str,
        lookup_name: str,
        main_row: pd.Series,
        main_name: str,
    ) -> pd.DataFrame:
        """Apply filter expression with main row values substituted.

        For RELOAD_AT_EACH_ROW: replaces main table column references
        (e.g., row1.region) with the actual main row values before
        evaluating the filter against the lookup DataFrame.

        Addresses review concern: None/NaN main row values are substituted
        as Python None literals. If evaluation raises TypeError (e.g.,
        None > 5), the filter returns an empty DataFrame (no match) rather
        than crashing -- consistent with Talend's null-never-matches
        semantics.

        Args:
            lookup_df: Full unfiltered lookup DataFrame.
            filter_expr: Filter expression (may have {{java}} prefix).
            lookup_name: Name of the lookup table.
            main_row: Current main row (pd.Series).
            main_name: Main table name (e.g., "row1").

        Returns:
            Filtered lookup DataFrame (rows matching the filter).
        """
        # Substitute row refs on the bare expression (no marker), then
        # re-attach the marker so _apply_filter can correctly dispatch.
        # Without this, a {{java}}-marked expression forwarded here after
        # stripping would fall through to _apply_filter_py (Python path),
        # breaking bridge-evaluated RELOAD_AT_EACH_ROW filters.
        has_marker = filter_expr.startswith(_JAVA_MARKER)
        bare_expr = self._strip_java_marker(filter_expr)
        substituted = self._substitute_row_refs(bare_expr, main_row, main_name)
        resolved_expr = (_JAVA_MARKER + substituted) if has_marker else substituted

        # Null-safe evaluation: if the resolved expression contains
        # a None literal from a NaN/null main row value, the downstream
        # evaluation may raise TypeError (e.g., None > 5). In that case,
        # return empty DataFrame (null never matches per MAP-03 semantics).
        try:
            return self._apply_filter(
                lookup_df, resolved_expr, lookup_name, []
            )
        except (TypeError, ValueError, ComponentExecutionError) as exc:
            logger.debug(
                f"[{self.id}] Per-row filter raised {type(exc).__name__} "
                f"(likely null main value in comparison): {exc}. "
                f"Treating as no match."
            )
            return lookup_df.iloc[0:0]

    @staticmethod
    def _find_quoted_ranges(expr: str) -> list[tuple[int, int]]:
        """Find all ranges in expr that are inside quoted strings.

        Handles both single and double quotes. Escaped quotes within
        strings are handled (e.g., 'it\\'s' or "he said \\"hi\\"").

        Args:
            expr: Expression string.

        Returns:
            List of (start, end) tuples marking quoted regions.
        """
        ranges = []
        i = 0
        while i < len(expr):
            if expr[i] in ('"', "'"):
                quote_char = expr[i]
                start = i
                i += 1
                while i < len(expr):
                    if expr[i] == '\\':
                        i += 2  # Skip escaped character
                        continue
                    if expr[i] == quote_char:
                        i += 1
                        break
                    i += 1
                ranges.append((start, i))
            else:
                i += 1
        return ranges

    def _substitute_row_refs(
        self,
        expr: str,
        row: pd.Series,
        table_name: str,
    ) -> str:
        """Replace table.column references for a specific table with literal values.

        For RELOAD_AT_EACH_ROW per-row filter evaluation. Replaces references
        like row1.region with the actual value from the current main row,
        leaving lookup table references intact for downstream evaluation.

        Addresses review concern: This method is quote-aware -- it will NOT
        replace table.column patterns that appear inside string literals
        (e.g., the "row1.label" inside '"Look at row1.label"' is left alone).

        Args:
            expr: Expression string (e.g., 'row1.region == row2.region').
            row: Row data (pd.Series) to substitute values from.
            table_name: Table name to match (e.g., "row1").

        Returns:
            Expression with matched table references replaced by Python literals.
            References inside quoted strings are left untouched.
        """
        # Pre-compute quoted ranges to avoid substituting inside string literals
        quoted_ranges = self._find_quoted_ranges(expr)

        def _in_quoted_region(start: int, end: int) -> bool:
            """Check if a match span falls inside any quoted string."""
            for q_start, q_end in quoted_ranges:
                if start >= q_start and end <= q_end:
                    return True
            return False

        def _replace_ref(match):
            # Skip matches inside quoted strings (addresses review concern
            # about regex brittleness with string literals)
            if _in_quoted_region(match.start(), match.end()):
                return match.group(0)

            table = match.group(1)
            column = match.group(2)
            if table != table_name:
                return match.group(0)  # Not our table, leave as-is

            # Try to find column in the row (supports prefixed and plain names)
            col_name = None
            prefixed = f"{table}.{column}"
            if prefixed in row.index:
                col_name = prefixed
            elif column in row.index:
                col_name = column
            if col_name is None:
                return match.group(0)  # Column not found, leave as-is

            val = row[col_name]
            # Null/NaN -> substitute as Python None literal
            # Downstream _apply_filter_per_row handles TypeError from
            # None comparisons (addresses review concern about NaN handling)
            if pd.isna(val):
                return "None"
            if isinstance(val, str):
                escaped = val.replace("\\", "\\\\").replace('"', '\\"')
                return f'"{escaped}"'
            if isinstance(val, (bool, np.bool_)):
                return "True" if val else "False"
            # Numeric types: int, float, numpy numeric
            return repr(val)

        return _ROW_REF_PATTERN.sub(_replace_ref, expr)

    # ------------------------------------------------------------------
    # Equality Join (pandas merge)
    # ------------------------------------------------------------------

    def _join_equality(
        self,
        joined_df: pd.DataFrame,
        lookup_df: pd.DataFrame,
        lookup_config: dict,
    ) -> tuple[pd.DataFrame, Optional[pd.DataFrame]]:
        """Perform equality join using pandas merge.

        Args:
            joined_df: Current joined DataFrame (main + previous lookups).
            lookup_df: Lookup DataFrame.
            lookup_config: Lookup configuration dict.

        Returns:
            Tuple of (joined result, inner join rejects or None).
        """
        lookup_name = lookup_config["name"]
        join_keys = lookup_config["join_keys"]
        join_mode = lookup_config.get("join_mode", "LEFT_OUTER_JOIN")
        matching_mode = lookup_config.get("matching_mode", _UNIQUE_MATCH)
        auto_convert = self.config.get("enable_auto_convert_type", False)

        # Build key column mappings
        left_keys = []
        right_keys = []
        for jk in join_keys:
            expr = self._strip_java_marker(jk["expression"])
            match = _SIMPLE_COLUMN_RE.match(expr.strip())
            if match:
                table, column = match.group(1), match.group(2)
                col_name = self._find_column(joined_df, table, column)
                if col_name is None:
                    col_name = column
                left_keys.append(col_name)
            else:
                left_keys.append(expr)
            right_keys.append(jk["lookup_column"])

        # Apply matching mode dedup to lookup
        lookup_df = self._apply_matching_mode(lookup_df, right_keys, matching_mode)

        # Size guard for ALL_MATCHES
        if matching_mode == _ALL_MATCHES:
            self._check_size_guard(len(joined_df), len(lookup_df), matching_mode)

        # Prefix lookup columns to avoid collisions
        lookup_df = self._prefix_lookup_columns(lookup_df, lookup_name)
        prefixed_right_keys = [f"{lookup_name}.{k}" for k in right_keys]

        # Auto type conversion (MAP-06)
        if auto_convert:
            joined_df, lookup_df = self._auto_convert_join_keys(
                joined_df, lookup_df, left_keys, prefixed_right_keys
            )

        # Null key pre-filter (MAP-03)
        main_nonnull, main_null = self._prefilter_null_keys(joined_df, left_keys)
        lookup_nonnull, _ = self._prefilter_null_keys(lookup_df, prefixed_right_keys)

        # Perform pandas merge
        if main_nonnull.empty:
            merged = pd.DataFrame(
                columns=list(joined_df.columns) + list(lookup_df.columns)
            )
            rejects = main_null.copy() if join_mode == "INNER_JOIN" else None
        else:
            merged = pd.merge(
                main_nonnull, lookup_nonnull,
                left_on=left_keys, right_on=prefixed_right_keys,
                how="left", indicator=True, suffixes=("", "__dup__")
            )

            # Track inner join rejects (MAP-02)
            rejects = None
            if join_mode == "INNER_JOIN":
                unmatched_mask = merged["_merge"] == "left_only"
                if unmatched_mask.any():
                    rejects = merged.loc[unmatched_mask].drop(
                        columns=["_merge"]
                    ).copy()
                # Also add null-key main rows to rejects
                if not main_null.empty:
                    if rejects is not None:
                        rejects = pd.concat(
                            [rejects, main_null], ignore_index=True
                        )
                    else:
                        rejects = main_null.copy()
                # Keep only matched rows for inner join
                merged = merged.loc[~unmatched_mask].copy()

            # Drop merge indicator
            if "_merge" in merged.columns:
                merged = merged.drop(columns=["_merge"])

        # For left outer join, re-add null-key rows (they get NaN lookup cols)
        if join_mode != "INNER_JOIN" and not main_null.empty:
            merged = pd.concat([merged, main_null], ignore_index=True)

        # Drop duplicate join key columns from lookup side
        dup_cols = [c for c in merged.columns if c.endswith("__dup__")]
        if dup_cols:
            merged = merged.drop(columns=dup_cols)

        logger.info(
            f"[{self.id}] Equality join with '{lookup_name}': "
            f"{len(merged)} rows"
            + (f", {len(rejects)} inner join rejects" if rejects is not None else "")
        )
        return merged, rejects

    # ------------------------------------------------------------------
    # Computed-Key Joins (Plan 05.3-03, D-03)
    # ------------------------------------------------------------------

    def _join_main_side_computed_key(
        self,
        joined_df: pd.DataFrame,
        lookup_df: pd.DataFrame,
        join_keys: list[dict],
        main_name: str,
        lookup_name: str,
        joined_lookup_names: list[str],
        lookup_config: dict,
    ) -> tuple[pd.DataFrame, Optional[pd.DataFrame]]:
        """Equality join where all keys are main-side with at least one computed.

        Batch-evaluates the join key expressions ONCE on joined_df (passing
        joined_lookup_names so the bridge can resolve prior-joined lookup refs
        per D-04), adds results as temporary columns, then delegates to a
        standard pd.merge (O(n+m) -- Talend hashmap parity).

        This replaces the _join_cross_table fallback for this case. Mirrors
        the full _join_equality structure (matching mode, null pre-filter,
        inner-join reject routing, column cleanup).

        Args:
            joined_df: Current joined DataFrame (main + all previously-joined lookups).
            lookup_df: Lookup DataFrame.
            join_keys: List of join key dicts from lookup config.
            main_name: Main input table name.
            lookup_name: Name of the current lookup being joined.
            joined_lookup_names: Names of all previously-joined lookups (D-04).
            lookup_config: Full lookup configuration dict.

        Returns:
            Tuple of (joined result, inner join rejects or None).
        """
        join_mode = lookup_config.get("join_mode", "LEFT_OUTER_JOIN")
        matching_mode = lookup_config.get("matching_mode", _UNIQUE_MATCH)
        auto_convert = self.config.get("enable_auto_convert_type", False)

        # Step 1: batch-eval all main-side join key expressions on joined_df.
        # D-04: pass joined_lookup_names so the bridge can resolve refs to
        # previously-joined lookups (e.g. row3.col where row3 was joined earlier).
        # 05.4-05: expressions reach GroovyShell.parse on the bridge side, so
        # the Groovy escape (in-string $ -> \$) is applied before forwarding.
        exprs = {
            f"__jk_main_{i}__": self._groovy_escape_expression(
                self._strip_java_marker(jk["expression"])
            )
            for i, jk in enumerate(join_keys)
        }
        eval_results = self._bridge_eval(joined_df, exprs, joined_lookup_names)

        # Step 2: add computed values as temporary columns on a copy of joined_df
        # (avoid mutating the caller's frame).
        joined_df = joined_df.copy()
        temp_key_cols = []
        for i in range(len(join_keys)):
            temp_col = f"__jk_main_{i}__"
            temp_key_cols.append(temp_col)
            if temp_col in eval_results:
                joined_df[temp_col] = eval_results[temp_col]
            else:
                joined_df[temp_col] = [None] * len(joined_df)

        # Step 3: right-side keys are the literal lookup column names.
        right_keys = [jk["lookup_column"] for jk in join_keys]

        # Apply matching mode dedup to lookup
        lookup_df = self._apply_matching_mode(lookup_df, right_keys, matching_mode)

        # Size guard for ALL_MATCHES
        if matching_mode == _ALL_MATCHES:
            self._check_size_guard(len(joined_df), len(lookup_df), matching_mode)

        # Prefix lookup columns to avoid collisions
        lookup_df = self._prefix_lookup_columns(lookup_df, lookup_name)
        prefixed_right_keys = [f"{lookup_name}.{k}" for k in right_keys]

        # Auto type conversion (MAP-06)
        if auto_convert:
            joined_df, lookup_df = self._auto_convert_join_keys(
                joined_df, lookup_df, temp_key_cols, prefixed_right_keys
            )

        # Null key pre-filter (MAP-03) using the computed temp columns
        main_nonnull, main_null = self._prefilter_null_keys(joined_df, temp_key_cols)
        lookup_nonnull, _ = self._prefilter_null_keys(lookup_df, prefixed_right_keys)

        # Perform pandas merge using temp columns as left keys
        if main_nonnull.empty:
            merged = pd.DataFrame(
                columns=list(joined_df.columns) + list(lookup_df.columns)
            )
            rejects = main_null.copy() if join_mode == "INNER_JOIN" else None
        else:
            merged = pd.merge(
                main_nonnull, lookup_nonnull,
                left_on=temp_key_cols, right_on=prefixed_right_keys,
                how="left", indicator=True, suffixes=("", "__dup__")
            )

            # Track inner join rejects (MAP-02)
            rejects = None
            if join_mode == "INNER_JOIN":
                unmatched_mask = merged["_merge"] == "left_only"
                if unmatched_mask.any():
                    rejects = merged.loc[unmatched_mask].drop(
                        columns=["_merge"]
                    ).copy()
                # Also add null-key main rows to rejects
                if not main_null.empty:
                    if rejects is not None:
                        rejects = pd.concat(
                            [rejects, main_null], ignore_index=True
                        )
                    else:
                        rejects = main_null.copy()
                # Keep only matched rows for inner join
                merged = merged.loc[~unmatched_mask].copy()

            # Drop merge indicator
            if "_merge" in merged.columns:
                merged = merged.drop(columns=["_merge"])

        # For left outer join, re-add null-key rows (they get NaN lookup cols)
        if join_mode != "INNER_JOIN" and not main_null.empty:
            merged = pd.concat([merged, main_null], ignore_index=True)

        # Step 4: drop temp key columns from output
        drop_cols = temp_key_cols + [c for c in merged.columns if c.endswith("__dup__")]
        existing_drop = [c for c in drop_cols if c in merged.columns]
        if existing_drop:
            merged = merged.drop(columns=existing_drop)

        # Reindex rejects to drop temp columns if present
        if rejects is not None:
            reject_drop = [c for c in temp_key_cols if c in rejects.columns]
            if reject_drop:
                rejects = rejects.drop(columns=reject_drop)

        logger.info(
            f"[{self.id}] Main-side computed-key join with '{lookup_name}': "
            f"{len(merged)} rows"
            + (f", {len(rejects)} inner join rejects" if rejects is not None else "")
        )
        return merged, rejects

    def _join_lookup_side_computed_key(
        self,
        joined_df: pd.DataFrame,
        lookup_df: pd.DataFrame,
        join_keys: list[dict],
        main_name: str,
        lookup_name: str,
        joined_lookup_names: list[str],
        lookup_config: dict,
    ) -> tuple[pd.DataFrame, Optional[pd.DataFrame]]:
        """Equality join where all keys are lookup-side with at least one computed.

        Symmetric counterpart to _join_main_side_computed_key. Batch-evaluates
        the join key expressions ONCE on lookup_df. The lookup has no joined-with-
        others context, so the bridge is called with the lookup as the "main" table
        and an empty lookup_names list.

        This is correct because the lookup-side expressions reference only the
        current lookup's columns (e.g. row2.region.trim()). The main table is not
        in scope for these expressions.

        Note: We call _evaluate_with_bridge directly here (bypassing _bridge_eval)
        because _bridge_eval always uses the config's main_name as the table name.
        For lookup-side eval, we need to pass lookup_name as main_table_name so
        the bridge registers the lookup's columns under row2.col (not row1.col).

        Args:
            joined_df: Current joined DataFrame (main + all previously-joined lookups).
            lookup_df: Lookup DataFrame.
            join_keys: List of join key dicts from lookup config.
            main_name: Main input table name (unused for eval, kept for signature parity).
            lookup_name: Name of the current lookup being joined.
            joined_lookup_names: Names of all previously-joined lookups (D-04).
            lookup_config: Full lookup configuration dict.

        Returns:
            Tuple of (joined result, inner join rejects or None).
        """
        join_mode = lookup_config.get("join_mode", "LEFT_OUTER_JOIN")
        matching_mode = lookup_config.get("matching_mode", _UNIQUE_MATCH)
        auto_convert = self.config.get("enable_auto_convert_type", False)

        # Step 1: batch-eval lookup-side join key expressions on lookup_df.
        # The lookup has no "already-joined" context, so pass [] as lookup_names.
        # We call _evaluate_with_bridge directly (not _bridge_eval) because
        # _bridge_eval always uses the config's main_name; here we need to pass
        # lookup_name as main_table_name so the bridge resolves row2.col etc.
        # 05.4-05: expressions reach GroovyShell.parse on the bridge side, so
        # the Groovy escape (in-string $ -> \$) is applied before forwarding.
        exprs = {
            f"__jk_lookup_{i}__": self._groovy_escape_expression(
                self._strip_java_marker(jk["expression"])
            )
            for i, jk in enumerate(join_keys)
        }
        eval_results = self._evaluate_with_bridge(
            lookup_df, exprs, lookup_name, []
        )

        # Step 2: add computed values as temporary columns on a copy of lookup_df.
        lookup_df = lookup_df.copy()
        temp_key_cols = []
        for i in range(len(join_keys)):
            temp_col = f"__jk_lookup_{i}__"
            temp_key_cols.append(temp_col)
            if temp_col in eval_results:
                lookup_df[temp_col] = eval_results[temp_col]
            else:
                lookup_df[temp_col] = [None] * len(lookup_df)

        # Step 3: left-side keys are real column names from joined_df.
        # Extract the lookup_column from join_keys as the right side reference,
        # but the actual right key we merge on is the temp computed column.
        # The main-side match value comes from the join_key's lookup_column
        # (what the main row's expression was supposed to equal).
        # For lookup-side computed keys, the join_key.expression is on the lookup
        # (e.g. row2.region.trim()). The lookup_column is what the main side has
        # as-is (e.g. main's 'region' column). We need to determine the left key.
        #
        # Since this is an equality join where lookup expr == main column,
        # the main side uses a simple column ref (otherwise it'd be two-sided).
        # Extract main-side column refs from join_keys if they exist; otherwise
        # use the lookup_column name as a guess (matching _join_equality logic).
        left_keys = []
        right_keys = [jk["lookup_column"] for jk in join_keys]
        for jk in join_keys:
            # For lookup-side computed keys, the "expression" is on the lookup.
            # The matching main-side value is the lookup_column itself (implicitly).
            # In Talend, a lookup-side key like row2.region.trim() pairs with
            # the main row's field that was named in the config as lookup_column.
            # We look for that column name in joined_df.
            col_name = jk["lookup_column"]
            found = self._find_column(joined_df, main_name, col_name)
            if found is not None:
                left_keys.append(found)
            else:
                # Try to find it as a bare column name in joined_df
                if col_name in joined_df.columns:
                    left_keys.append(col_name)
                else:
                    left_keys.append(col_name)

        # Apply matching mode dedup to lookup (before prefixing)
        lookup_df = self._apply_matching_mode(lookup_df, right_keys, matching_mode)

        # Size guard for ALL_MATCHES
        if matching_mode == _ALL_MATCHES:
            self._check_size_guard(len(joined_df), len(lookup_df), matching_mode)

        # Prefix lookup columns to avoid collisions
        lookup_df = self._prefix_lookup_columns(lookup_df, lookup_name)
        # The temp key columns also got prefixed -- update temp_key_cols
        prefixed_temp_key_cols = [f"{lookup_name}.{c}" for c in temp_key_cols]

        # Auto type conversion (MAP-06)
        if auto_convert:
            joined_df, lookup_df = self._auto_convert_join_keys(
                joined_df, lookup_df, left_keys, prefixed_temp_key_cols
            )

        # Null key pre-filter (MAP-03) using the computed temp columns
        main_nonnull, main_null = self._prefilter_null_keys(joined_df, left_keys)
        lookup_nonnull, _ = self._prefilter_null_keys(
            lookup_df, prefixed_temp_key_cols
        )

        # Perform pandas merge using temp computed columns as right keys
        if main_nonnull.empty:
            merged = pd.DataFrame(
                columns=list(joined_df.columns) + list(lookup_df.columns)
            )
            rejects = main_null.copy() if join_mode == "INNER_JOIN" else None
        else:
            merged = pd.merge(
                main_nonnull, lookup_nonnull,
                left_on=left_keys, right_on=prefixed_temp_key_cols,
                how="left", indicator=True, suffixes=("", "__dup__")
            )

            # Track inner join rejects (MAP-02)
            rejects = None
            if join_mode == "INNER_JOIN":
                unmatched_mask = merged["_merge"] == "left_only"
                if unmatched_mask.any():
                    rejects = merged.loc[unmatched_mask].drop(
                        columns=["_merge"]
                    ).copy()
                # Also add null-key main rows to rejects
                if not main_null.empty:
                    if rejects is not None:
                        rejects = pd.concat(
                            [rejects, main_null], ignore_index=True
                        )
                    else:
                        rejects = main_null.copy()
                # Keep only matched rows for inner join
                merged = merged.loc[~unmatched_mask].copy()

            # Drop merge indicator
            if "_merge" in merged.columns:
                merged = merged.drop(columns=["_merge"])

        # For left outer join, re-add null-key rows (they get NaN lookup cols)
        if join_mode != "INNER_JOIN" and not main_null.empty:
            merged = pd.concat([merged, main_null], ignore_index=True)

        # Step 4: drop temp key columns from output
        drop_cols = (
            prefixed_temp_key_cols
            + [c for c in merged.columns if c.endswith("__dup__")]
        )
        existing_drop = [c for c in drop_cols if c in merged.columns]
        if existing_drop:
            merged = merged.drop(columns=existing_drop)

        # Reindex rejects to drop temp columns if present
        if rejects is not None:
            reject_drop = [c for c in prefixed_temp_key_cols if c in rejects.columns]
            if reject_drop:
                rejects = rejects.drop(columns=reject_drop)

        logger.info(
            f"[{self.id}] Lookup-side computed-key join with '{lookup_name}': "
            f"{len(merged)} rows"
            + (f", {len(rejects)} inner join rejects" if rejects is not None else "")
        )
        return merged, rejects

    # ------------------------------------------------------------------
    # Context-Only Join
    # DEPRECATED(05.3-02): unrouted; all-context keys now route to
    # _join_equality (the hash-join handles context-only keys correctly).
    # Deferred deletion to a future cleanup task -- do NOT remove here.
    # ------------------------------------------------------------------

    def _join_context_only(
        self,
        joined_df: pd.DataFrame,
        lookup_df: pd.DataFrame,
        lookup_config: dict,
    ) -> tuple[pd.DataFrame, Optional[pd.DataFrame]]:
        """Join where all keys are context-only expressions.

        Evaluates context expressions once, filters lookup, cross-joins.

        Args:
            joined_df: Current joined DataFrame.
            lookup_df: Lookup DataFrame.
            lookup_config: Lookup configuration dict.

        Returns:
            Tuple of (joined result, inner join rejects or None).
        """
        lookup_name = lookup_config["name"]
        join_keys = lookup_config["join_keys"]
        join_mode = lookup_config.get("join_mode", "LEFT_OUTER_JOIN")
        matching_mode = lookup_config.get("matching_mode", _UNIQUE_MATCH)

        # Evaluate context expressions for lookup filter
        filter_mask = pd.Series([True] * len(lookup_df), index=lookup_df.index)
        for jk in join_keys:
            expr = self._strip_java_marker(jk["expression"])
            lookup_col = jk["lookup_column"]
            # Resolve context value
            if self.context_manager:
                resolved = self.context_manager.resolve_string(expr)
            elif self.global_map:
                # Try globalMap.get pattern
                resolved = expr
            else:
                resolved = expr

            if lookup_col in lookup_df.columns:
                filter_mask = filter_mask & (
                    lookup_df[lookup_col].astype(str) == str(resolved)
                )

        filtered_lookup = lookup_df[filter_mask].copy()

        # Apply matching mode
        key_cols = [jk["lookup_column"] for jk in join_keys]
        filtered_lookup = self._apply_matching_mode(
            filtered_lookup, key_cols, matching_mode
        )

        # Prefix and cross-join
        filtered_lookup = self._prefix_lookup_columns(filtered_lookup, lookup_name)

        if filtered_lookup.empty:
            if join_mode == "INNER_JOIN":
                return pd.DataFrame(columns=joined_df.columns), joined_df.copy()
            return joined_df, None

        self._check_size_guard(
            len(joined_df), len(filtered_lookup), matching_mode
        )

        # Cross join
        joined_df = joined_df.assign(__cross_key__=1)
        filtered_lookup = filtered_lookup.assign(__cross_key__=1)
        result = pd.merge(joined_df, filtered_lookup, on="__cross_key__")
        result = result.drop(columns=["__cross_key__"])

        logger.info(
            f"[{self.id}] Context-only join with '{lookup_name}': "
            f"{len(result)} rows"
        )
        return result, None

    # ------------------------------------------------------------------
    # Cross-Table Join (D-05: memory-bounded chunked implementation)
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_cross_chunk_size(lookup_rows: int) -> int:
        """Auto-tune cross-product chunk size to bound peak memory to ~100M cells.

        Formula (D-05):
            chunk_size = max(100, min(10_000, 100_000_000 // max(1, lookup_rows)))

        This caps peak intermediate-frame cells at ~100M regardless of lookup
        size, mirroring Talend's row-by-row streaming behavior.

        Args:
            lookup_rows: Number of rows in the lookup DataFrame.

        Returns:
            Chunk size for main DataFrame slicing in cross-product.
        """
        return max(100, min(10_000, 100_000_000 // max(1, lookup_rows)))

    def _chunked_cross_product(
        self,
        main_df: pd.DataFrame,
        lookup_df: pd.DataFrame,
        match_expr: Optional[str],
        main_name: str,
        lookup_name: str,
        joined_lookup_names: list[str],
    ) -> pd.DataFrame:
        """Memory-bounded chunked cross-product (D-05).

        Iterates main_df in chunks, computes per-chunk cross-product with
        lookup_df, optionally applies match_expr as a filter via bridge eval,
        and concatenates surviving rows. This mirrors Talend's row-by-row
        streaming behavior while bounding peak intermediate-frame memory.

        If cross_join_chunk_size is set in config, that value is used instead
        of the auto-tuned value from _compute_cross_chunk_size.

        Args:
            main_df: Main (left) DataFrame to iterate in chunks.
            lookup_df: Lookup (right) DataFrame. Already prefixed if applicable.
            match_expr: Expression string (with or without {{java}} marker) to
                evaluate as match condition, or None for pure cartesian join.
            main_name: Name of the main table (used for bridge eval).
            lookup_name: Name of the lookup table (used for bridge eval).
            joined_lookup_names: Full list of already-joined lookup names (D-04).

        Returns:
            Concatenated DataFrame of all rows that survived the (optional)
            match condition. Empty frame with main_df columns if no matches.
        """
        if lookup_df.empty:
            # Cross-product with empty lookup is always empty.
            return main_df.iloc[0:0]

        # Allow config override; auto-tune as fallback (D-05).
        chunk_size = int(
            self.config.get(
                "cross_join_chunk_size",
                self._compute_cross_chunk_size(len(lookup_df)),
            )
        )

        stripped_expr: Optional[str] = None
        if match_expr is not None:
            # 05.4-05: match_expr is forwarded to _bridge_eval which submits
            # it to GroovyShell.parse on the bridge side. Apply the Groovy
            # escape (in-string $ -> \$) once here, not in the per-chunk loop.
            stripped_expr = self._groovy_escape_expression(
                self._strip_java_marker(match_expr)
            )

        result_chunks: list[pd.DataFrame] = []

        for start in range(0, len(main_df), chunk_size):
            chunk = main_df.iloc[start:start + chunk_size]
            chunk_cross = pd.merge(chunk, lookup_df, how="cross")

            if stripped_expr is None:
                # Pure cartesian -- no filtering needed.
                result_chunks.append(chunk_cross)
                continue

            # Evaluate match expression on this chunk's cross-product.
            # D-04: pass joined_lookup_names + [lookup_name] so prior-joined
            # lookup refs (e.g. row3.col) are visible to the bridge.
            eval_results = self._bridge_eval(
                chunk_cross,
                {"__match__": stripped_expr},
                joined_lookup_names + [lookup_name],
            )

            if "__match__" in eval_results:
                mask = (
                    pd.Series(eval_results["__match__"])
                    .fillna(False)
                    .astype(bool)
                    .values
                )
                result_chunks.append(chunk_cross[mask])

        if not result_chunks:
            return main_df.iloc[0:0]

        return pd.concat(result_chunks, ignore_index=True)

    def _join_cross_table(
        self,
        joined_df: pd.DataFrame,
        lookup_df: pd.DataFrame,
        lookup_config: dict,
        joined_lookup_names: Optional[list[str]] = None,
    ) -> tuple[pd.DataFrame, Optional[pd.DataFrame]]:
        """Join where keys reference both main and lookup columns (two-sided).

        Delegates to _chunked_cross_product for memory-bounded execution (D-05).
        Join key expressions are combined into a single match condition that is
        evaluated per-chunk instead of materializing the full cross-product.

        Args:
            joined_df: Current joined DataFrame.
            lookup_df: Lookup DataFrame.
            lookup_config: Lookup configuration dict.
            joined_lookup_names: Full list of already-joined lookup names (D-04).
                Must include ALL prior-joined lookups so the bridge can resolve
                references like row3.col when row3 was joined before current.

        Returns:
            Tuple of (joined result, inner join rejects or None).
        """
        lookup_name = lookup_config["name"]
        join_keys = lookup_config.get("join_keys", [])
        join_mode = lookup_config.get("join_mode", "LEFT_OUTER_JOIN")
        matching_mode = lookup_config.get("matching_mode", _UNIQUE_MATCH)
        _joined_lookup_names = joined_lookup_names or []

        self._check_size_guard(len(joined_df), len(lookup_df), matching_mode)

        logger.warning(
            f"[{self.id}] Cross-table join with '{lookup_name}' "
            f"-- chunked O(n*m) evaluation ({len(joined_df)} x {len(lookup_df)} rows)"
        )

        # Apply matching mode to lookup first (dedup before cross-product)
        key_cols = [jk["lookup_column"] for jk in join_keys]
        lookup_df = self._apply_matching_mode(lookup_df, key_cols, matching_mode)

        # Prefix lookup columns before cross-product so column names in the
        # cross frame match what downstream code and bridge expressions expect.
        lookup_df_prefixed = self._prefix_lookup_columns(lookup_df, lookup_name)

        if lookup_df_prefixed.empty:
            if join_mode == "INNER_JOIN":
                return pd.DataFrame(columns=joined_df.columns), joined_df.copy()
            return joined_df, None

        # Build a combined match expression from all join key pairs.
        # Each key pair: evaluated_expr == lookup_name.lookup_column.
        # If join_keys is empty (pure cartesian path), match_expr is None.
        if join_keys:
            # Combine per-key comparisons into one AND expression evaluated in
            # _chunked_cross_product. Each key expression is compared against
            # the prefixed lookup column value.
            # We use a sentinel-based approach: evaluate each join key expression
            # via bridge and compare against the prefixed lookup column.
            # For two-sided keys, pass the joined cross-product to the bridge.
            matched = self._chunked_cross_product_with_keys(
                joined_df, lookup_df_prefixed, join_keys,
                lookup_name, _joined_lookup_names, join_mode,
            )
        else:
            # Empty join_keys -> pure cartesian (called from internal fallback only)
            matched = self._chunked_cross_product(
                joined_df, lookup_df_prefixed,
                match_expr=None,
                main_name=self.config["inputs"]["main"]["name"],
                lookup_name=lookup_name,
                joined_lookup_names=_joined_lookup_names,
            )

        rejects = None
        if join_mode == "INNER_JOIN":
            # Compare on column values to find which original main rows got at
            # least one match (matched has new RangeIndex from concat).
            main_cols = list(joined_df.columns)
            if not matched.empty:
                matched_main_rows = matched[main_cols].drop_duplicates()
                joined_with_flag = joined_df.merge(
                    matched_main_rows.assign(__matched__=True),
                    on=main_cols,
                    how="left",
                )
                unmatched = joined_with_flag[
                    joined_with_flag["__matched__"].isna()
                ].drop(columns=["__matched__"])
                if not unmatched.empty:
                    rejects = unmatched.copy()
            else:
                rejects = joined_df.copy()

        if matched.empty and join_mode != "INNER_JOIN":
            return joined_df, None

        logger.info(
            f"[{self.id}] Cross-table join with '{lookup_name}': "
            f"{len(matched)} rows"
        )
        return matched, rejects

    def _chunked_cross_product_with_keys(
        self,
        main_df: pd.DataFrame,
        lookup_df_prefixed: pd.DataFrame,
        join_keys: list[dict],
        lookup_name: str,
        joined_lookup_names: list[str],
        join_mode: str,
    ) -> pd.DataFrame:
        """Cross-product with per-key expression evaluation (two-sided joins).

        Iterates main_df in chunks, evaluates each join key expression via
        the bridge, and filters rows where all key expressions match the
        corresponding prefixed lookup column values.

        This is the inner logic of _join_cross_table for the case where
        join_keys is non-empty.

        Args:
            main_df: Main DataFrame.
            lookup_df_prefixed: Lookup DataFrame with prefixed column names.
            join_keys: List of join key dicts with 'expression' and 'lookup_column'.
            lookup_name: Name of the lookup table.
            joined_lookup_names: Already-joined lookup names (D-04).
            join_mode: Join mode string (affects empty-result handling).

        Returns:
            Concatenated DataFrame of matched rows.
        """
        main_name = self.config["inputs"]["main"]["name"]
        chunk_size = int(
            self.config.get(
                "cross_join_chunk_size",
                self._compute_cross_chunk_size(len(lookup_df_prefixed)),
            )
        )
        full_lookup_names = joined_lookup_names + [lookup_name]
        result_chunks: list[pd.DataFrame] = []

        for start in range(0, len(main_df), chunk_size):
            chunk = main_df.iloc[start:start + chunk_size]
            chunk_cross = pd.merge(chunk, lookup_df_prefixed, how="cross")

            if chunk_cross.empty:
                continue

            # Evaluate all join key expressions on this chunk's cross-product.
            # D-04: pass joined_lookup_names + [lookup_name] so expressions that
            # reference previously-joined lookups resolve correctly.
            # 05.4-05: expressions reach GroovyShell.parse on the bridge side,
            # so the Groovy escape (in-string $ -> \$) is applied before
            # forwarding.
            exprs = {}
            for i, jk in enumerate(join_keys):
                expr = self._groovy_escape_expression(
                    self._strip_java_marker(jk["expression"])
                )
                exprs[f"__jk_{i}__"] = expr

            eval_results = self._bridge_eval(chunk_cross, exprs, full_lookup_names)

            # Build match mask: all key expressions must match their lookup column
            match_mask = pd.Series([True] * len(chunk_cross), index=chunk_cross.index)
            for i, jk in enumerate(join_keys):
                expr_key = f"__jk_{i}__"
                lookup_col = f"{lookup_name}.{jk['lookup_column']}"
                if expr_key in eval_results:
                    eval_vals = pd.Series(eval_results[expr_key], index=chunk_cross.index)
                    if lookup_col in chunk_cross.columns:
                        match_mask = match_mask & (
                            eval_vals.astype(str) == chunk_cross[lookup_col].astype(str)
                        )

            matched_chunk = chunk_cross[match_mask]
            if not matched_chunk.empty:
                result_chunks.append(matched_chunk)

        if not result_chunks:
            return pd.DataFrame(columns=list(main_df.columns) + list(lookup_df_prefixed.columns))

        return pd.concat(result_chunks, ignore_index=True)

    # ------------------------------------------------------------------
    # RELOAD_AT_EACH_ROW Join (MAP-08)
    # ------------------------------------------------------------------

    def _join_reload_per_row(
        self,
        joined_df: pd.DataFrame,
        lookup_df: pd.DataFrame,
        lookup_config: dict,
    ) -> tuple[pd.DataFrame, Optional[pd.DataFrame]]:
        """Per-row lookup re-filter for RELOAD_AT_EACH_ROW mode.

        For each main row, sets globalMap variables from the row,
        re-evaluates the lookup filter expression against the full
        lookup DataFrame, and performs single-row join.

        Args:
            joined_df: Current joined DataFrame.
            lookup_df: Full unfiltered lookup DataFrame.
            lookup_config: Lookup configuration dict.

        Returns:
            Tuple of (joined result, inner join rejects or None).
        """
        lookup_name = lookup_config["name"]
        join_keys = lookup_config["join_keys"]
        join_mode = lookup_config.get("join_mode", "LEFT_OUTER_JOIN")
        matching_mode = lookup_config.get("matching_mode", _UNIQUE_MATCH)

        if (len(joined_df) > 10000 and len(lookup_df) > 10000):
            logger.warning(
                f"[{self.id}] RELOAD_AT_EACH_ROW with large datasets: "
                f"{len(joined_df)} main x {len(lookup_df)} lookup rows "
                f"-- O(n*m) operation"
            )

        result_rows = []
        reject_rows = []
        key_cols = [jk["lookup_column"] for jk in join_keys]
        main_name = self.config["inputs"]["main"]["name"]
        # Compute prefixed column names for the empty-result fallback without
        # copying the full DataFrame (prefix is also applied per-row inside loop).
        lookup_prefixed_cols = [
            col if col.startswith(f"{lookup_name}.") else f"{lookup_name}.{col}"
            for col in lookup_df.columns
        ]

        for idx, main_row in joined_df.iterrows():
            # Set globalMap variables from main row
            if self.global_map:
                for col in joined_df.columns:
                    self.global_map.put(f"{main_name}.{col}", main_row[col])

            # Re-filter lookup with main row context
            if (lookup_config.get("activate_filter")
                    and lookup_config.get("filter")):
                filtered = self._apply_filter_per_row(
                    lookup_df, lookup_config["filter"],
                    lookup_name, main_row, main_name,
                )
            else:
                filtered = lookup_df

            if filtered.empty:
                if join_mode == "INNER_JOIN":
                    reject_rows.append(main_row)
                else:
                    result_rows.append(main_row)
                continue

            # Apply matching mode
            filtered = self._apply_matching_mode(filtered, key_cols, matching_mode)
            filtered = self._prefix_lookup_columns(filtered, lookup_name)

            # Evaluate join keys for this single row
            matched = False
            for _, lookup_row in filtered.iterrows():
                key_match = True
                for jk in join_keys:
                    expr = self._strip_java_marker(jk["expression"])
                    lookup_col = f"{lookup_name}.{jk['lookup_column']}"
                    match = _SIMPLE_COLUMN_RE.match(expr.strip())
                    if match:
                        table, column = match.group(1), match.group(2)
                        main_val = main_row.get(
                            self._find_column(joined_df, table, column)
                            or column
                        )
                    else:
                        main_val = None
                    lookup_val = lookup_row.get(lookup_col)

                    # Null keys never match (MAP-03)
                    if pd.isna(main_val) or pd.isna(lookup_val):
                        key_match = False
                        break
                    if not self._values_equal(main_val, lookup_val):
                        key_match = False
                        break

                if key_match:
                    combined = pd.concat([main_row, lookup_row])
                    result_rows.append(combined)
                    matched = True
                    if matching_mode in (_UNIQUE_MATCH, _FIRST_MATCH, _LAST_MATCH):
                        break

            if not matched:
                if join_mode == "INNER_JOIN":
                    reject_rows.append(main_row)
                else:
                    # Build combined row with NaN-filled lookup columns.
                    # Uses lookup_prefixed_cols to ensure column order matches
                    # the lookup schema exactly (addresses review suggestion
                    # about column alignment verification).
                    combined = main_row.copy()
                    for col in lookup_prefixed_cols:
                        combined[col] = np.nan
                    result_rows.append(combined)

        # Build result DataFrames
        if result_rows:
            result_df = pd.DataFrame(result_rows).reset_index(drop=True)
        else:
            result_df = pd.DataFrame(
                columns=list(joined_df.columns) + lookup_prefixed_cols
            )

        rejects = None
        if reject_rows:
            rejects = pd.DataFrame(reject_rows).reset_index(drop=True)

        logger.info(
            f"[{self.id}] RELOAD_AT_EACH_ROW join with '{lookup_name}': "
            f"{len(result_df)} rows"
            + (f", {len(rejects)} inner join rejects" if rejects is not None else "")
        )
        return result_df, rejects

    # ------------------------------------------------------------------
    # Variable Evaluation
    # ------------------------------------------------------------------

    def _evaluate_variables(
        self,
        joined_df: pd.DataFrame,
        variables_config: list[dict],
        main_name: str,
        lookup_names: list[str],
    ) -> pd.DataFrame:
        """Evaluate variable definitions and add as columns.

        Variables are evaluated sequentially (dependency chains supported).
        Results stored as Var.{variable_name} columns in joined_df.

        Args:
            joined_df: Joined DataFrame with all lookup columns.
            variables_config: List of variable config dicts.
            main_name: Main table name.
            lookup_names: Lookup table names.

        Returns:
            DataFrame with variable columns added.
        """
        for var in variables_config:
            var_name = var.get("name", "")
            var_expr = var.get("expression", "")
            if not var_expr:
                continue

            expr = self._strip_java_marker(var_expr)
            col_name = f"Var.{var_name}"

            if self._is_simple_column_ref(expr):
                match = _SIMPLE_COLUMN_RE.match(expr.strip())
                if match:
                    table, column = match.group(1), match.group(2)
                    src_col = self._find_column(joined_df, table, column)
                    if src_col:
                        joined_df[col_name] = joined_df[src_col].values
                    else:
                        joined_df[col_name] = None
            else:
                # D-04: pass full lookup_names so prior-joined lookups are visible.
                # 05.4-05: bridge submits expr to GroovyShell.parse, so apply
                # the Groovy escape (in-string $ -> \$) before forwarding.
                bridge_expr = self._groovy_escape_expression(expr)
                result = self._bridge_eval(joined_df, {col_name: bridge_expr}, lookup_names)
                if col_name in result:
                    joined_df[col_name] = result[col_name]
                else:
                    joined_df[col_name] = None

        logger.debug(
            f"[{self.id}] Evaluated {len(variables_config)} variables"
        )
        return joined_df

    # ------------------------------------------------------------------
    # Output Evaluation
    # ------------------------------------------------------------------

    def _evaluate_outputs(
        self,
        joined_df: pd.DataFrame,
        outputs_config: list[dict],
        variables_config: list[dict],
        main_name: str,
        lookup_names: list[str],
    ) -> dict[str, pd.DataFrame]:
        """Evaluate output expressions and route to named outputs.

        Uses Java bridge compile-once-execute-many pattern when available,
        falls back to simple column reference evaluation otherwise.

        Args:
            joined_df: Joined DataFrame with all lookup and variable columns.
            outputs_config: List of output config dicts.
            variables_config: List of variable config dicts.
            main_name: Main table name.
            lookup_names: Lookup table names.

        Returns:
            Dict mapping output names to DataFrames.
        """
        result: dict[str, pd.DataFrame] = {}

        # D-02: marker-presence anywhere is the sole dispatch signal (set in _process).
        # Re-derive here for the case where _evaluate_outputs is called standalone.
        _use_compiled = self._has_any_java_marker()

        if _use_compiled:
            result = self._evaluate_outputs_compiled(
                joined_df, outputs_config, variables_config,
                main_name, lookup_names
            )
        else:
            # Python-eval path (no markers anywhere -> bridge not needed).
            # Variables were already evaluated by _process via _evaluate_variables_py;
            # re-evaluate here in case _evaluate_outputs is called standalone.
            var_columns: dict[str, list] = {}
            if variables_config:
                var_columns = self._evaluate_variables_py(
                    joined_df, variables_config, main_name, lookup_names
                )
            result = self._evaluate_outputs_py(
                joined_df, outputs_config, var_columns, main_name, lookup_names
            )

        return result

    def _evaluate_outputs_compiled(
        self,
        joined_df: pd.DataFrame,
        outputs_config: list[dict],
        variables_config: list[dict],
        main_name: str,
        lookup_names: list[str],
    ) -> dict[str, pd.DataFrame]:
        """Evaluate outputs using compiled Java script execution.

        Generates a Groovy script, compiles once, executes in chunks.
        Handles output filters and catch output reject routing.

        Args:
            joined_df: Joined DataFrame.
            outputs_config: Output config list.
            variables_config: Variable config list.
            main_name: Main table name.
            lookup_names: Lookup table names.

        Returns:
            Dict mapping output names to DataFrames.
        """
        # Build script and output schemas
        script = self._build_compiled_script(
            outputs_config, variables_config, main_name, lookup_names
        )
        output_schemas, output_types = self._build_output_schema(outputs_config)

        # Build schema dict for Arrow serialization
        schema_dict = _infer_arrow_schema_dict(joined_df)

        # Compile script
        try:
            self.java_bridge.compile_tmap_script(
                component_id=self.id,
                java_script=script,
                output_schemas=output_schemas,
                output_types=output_types,
                main_table_name=main_name,
                lookup_names=lookup_names,
                input_columns=list(joined_df.columns),
                schema=schema_dict,
            )
        except Exception as e:
            logger.error(
                f"[{self.id}] Failed to compile tMap script: {e}"
            )
            raise ComponentExecutionError(
                self.id, f"Failed to compile tMap script: {e}", cause=e
            )

        # Execute in chunks
        # D-05: 'output_chunk_size' is the new canonical key.
        # 'rows_buffer_size' is the legacy alias for back-compat with
        # already-converted JSON jobs (no re-conversion needed).
        chunk_size = int(
            self.config.get(
                "output_chunk_size",
                self.config.get("rows_buffer_size", _DEFAULT_CHUNK_SIZE),
            )
        )
        try:
            raw_result = self.java_bridge.execute_compiled_tmap_chunked(
                component_id=self.id,
                df=joined_df,
                chunk_size=chunk_size,
                input_columns=list(joined_df.columns),
                schema=schema_dict,
            )
        except Exception as e:
            logger.error(
                f"[{self.id}] Failed to execute compiled tMap script: {e}"
            )
            raise ComponentExecutionError(
                self.id, f"Failed to execute compiled tMap script: {e}",
                cause=e,
            )

        # Process compiled results
        # NOTE: Output filters are already applied inside the compiled Groovy
        # script (_build_compiled_script embeds `if (filter)` per output).
        # Do NOT call _apply_output_filter here -- it would re-evaluate the
        # filter on the *output* DataFrame whose columns no longer include
        # the input row fields (e.g. row1.line), producing 0 rows.
        result: dict[str, pd.DataFrame] = {}
        for output_cfg in outputs_config:
            out_name = output_cfg["name"]
            if out_name in raw_result:
                result[out_name] = raw_result[out_name]
            else:
                result[out_name] = pd.DataFrame(
                    columns=[c["name"] for c in output_cfg["columns"]]
                )

        # Handle catch output reject (MAP-05)
        self._route_catch_output_rejects(result, raw_result, outputs_config)

        return result

    # ------------------------------------------------------------------
    # Python Expression Evaluation (no-marker path, D-02)
    # ------------------------------------------------------------------

    def _build_row_dicts_for_py(
        self,
        row: pd.Series,
        main_name: str,
        lookup_names: list[str],
        df: pd.DataFrame,
    ) -> dict[str, dict]:
        """Build per-table row dicts from a joined row Series.

        Splits columns prefixed by lookup names into per-table dicts so
        tMap expressions can reference ``row1.col`` (attribute access via
        the SimpleNamespace wrapper) and ``row2.col`` for lookups.

        Variables (``Var.*`` columns) are intentionally excluded; they are
        handled separately via the ``_VarBag`` in the caller's namespace.

        Args:
            row: A single row from the joined DataFrame.
            main_name: Main table name.
            lookup_names: Lookup table names.
            df: The joined DataFrame (used for column listing).

        Returns:
            Dict of table_name -> {col -> value}.
        """
        row_dicts: dict[str, dict] = {}

        lookup_prefixes = tuple(f"{ln}." for ln in lookup_names)
        main_row: dict[str, Any] = {}
        for col in df.columns:
            val = row[col] if col in row.index else np.nan
            if col.startswith("Var."):
                pass  # handled via _VarBag
            elif not col.startswith(lookup_prefixes):
                main_row[col] = val
        row_dicts[main_name] = main_row

        for ln in lookup_names:
            prefix = f"{ln}."
            lookup_row: dict[str, Any] = {}
            for col in df.columns:
                if col.startswith(prefix):
                    plain = col[len(prefix):]
                    val = row[col] if col in row.index else np.nan
                    lookup_row[plain] = val
            row_dicts[ln] = lookup_row

        return row_dicts

    def _build_namespace(
        self,
        row_dicts: dict[str, dict],
        var_bag: "_VarBag",
        failed_lookups: "set[str] | None" = None,
    ) -> dict[str, Any]:
        """Build the eval namespace for a single row (Python-eval path).

        Per PATTERNS.md ``row1.col`` compatibility note:
        - The converter emits ``row1.col`` (attribute) not ``row1['col']``.
        - Rows are wrapped in ``types.SimpleNamespace`` (read-only per row,
          so copy semantics are fine).
        - The ``Var`` namespace uses ``_VarBag`` for live attribute access
          (sequential mutation must be visible to later var expressions).

        Args:
            row_dicts: Mapping of table_name -> {col -> value} per row.
            var_bag: Shared ``_VarBag`` instance for the current row.
            failed_lookups: Optional set of lookup names that failed an
                inner join for this row (D-04 of phase 05.4-02).  When a
                table name appears in this set its namespace binding is a
                ``_NullRow`` sentinel (raises ``AttributeError`` on any
                attribute access) instead of the default ``_NullNamespace``
                (silent ``None``).  This distinguishes inner-join-reject
                semantics ("reference to failing lookup is an error") from
                left-outer-join semantics ("unmatched lookup columns are
                null").  Default ``None`` means no failed lookups.

        Returns:
            Namespace dict ready for ``eval()``.
        """
        ns: dict[str, Any] = {}
        ns.update(_SAFE_NAMESPACE_GLOBALS)
        ns["__builtins__"] = _build_safe_builtins()
        failed_lookups = failed_lookups or set()
        # tMap converter emits ``row1.col`` (attribute), not ``row1['col']``.
        # Wrap each row dict in SimpleNamespace so attribute access works.
        # An empty row_data dict means the lookup had no data in the joined_df
        # (empty lookup / unmatched left-outer row).  Use _NullNamespace so
        # that ``row2.label`` returns ``None`` instead of AttributeError --
        # this matches Talend left-outer semantics where unmatched rows yield
        # null for all lookup columns.  For lookups listed in failed_lookups
        # (inner-join-reject row source, D-04) bind a _NullRow sentinel
        # instead so that ``row2.label`` raises -- matching Talend's
        # inner-join semantic that the failing lookup is an error to deref.
        for table_name, row_data in row_dicts.items():
            if table_name in failed_lookups:
                ns[table_name] = _NullRow()
            elif row_data:
                ns[table_name] = types.SimpleNamespace(**row_data)
            else:
                ns[table_name] = _NullNamespace()
        # Var uses _VarBag for live access -- subsequent variable evaluations
        # on the same row must see earlier assignments.
        ns["Var"] = var_bag
        ns["Decimal"] = Decimal
        if self.context_manager:
            try:
                ctx_dict = self.context_manager.get_all()
                ns["context"] = types.SimpleNamespace(**ctx_dict)
            except Exception:
                ns["context"] = types.SimpleNamespace()
        else:
            ns["context"] = types.SimpleNamespace()
        if self.global_map:
            ns["globalMap"] = self.global_map
        return ns

    def _eval_expr(
        self,
        expr: str,
        ns: dict[str, Any],
        output_name: str = "",
        col_name: str = "",
    ) -> Any:
        """Safely evaluate a Python expression in a sandboxed namespace.

        Args:
            expr: Python expression string (no ``{{java}}`` marker).
            ns: Eval namespace dict.
            output_name: Output name (for error messages).
            col_name: Column/variable name (for error messages).

        Returns:
            Evaluated value, or ``None`` when ``die_on_error`` is False
            and evaluation raises.

        Raises:
            ComponentExecutionError: When ``die_on_error`` is True and
                evaluation fails.
        """
        try:
            return eval(expr, ns)  # noqa: S307
        except Exception as exc:
            msg = (
                f"[{self.id}] Expression eval failed for "
                f"output='{output_name}' col='{col_name}': "
                f"{type(exc).__name__}: {exc} | expr={expr!r}"
            )
            if self.die_on_error:
                raise ComponentExecutionError(self.id, msg, cause=exc) from exc
            logger.warning(msg)
            return None

    def _apply_filter_py(
        self,
        df: pd.DataFrame,
        filter_expr: str,
        table_name: str,
    ) -> pd.DataFrame:
        """Apply a Python filter expression to a DataFrame (no-marker path).

        Evaluates ``filter_expr`` per row; rows where the expression is
        truthy are kept.  Non-truthy or error rows are dropped (no-match
        semantics matching Talend null-never-matches).

        Handles two calling contexts:

        1. **Joined DataFrame** (main + prefixed lookup columns): columns in
           ``df`` include ``{lookup_name}.{col}`` prefixes.  The full
           ``_build_row_dicts_for_py`` path splits them correctly.

        2. **Single-table DataFrame** (unfiltered main_df or lookup_df):
           columns have NO prefix.  In this case ``table_name`` IS the
           table, so we put all columns directly into ``ns[table_name]``
           and also at top level for convenience.

        Args:
            df: DataFrame to filter.
            filter_expr: Python boolean expression string (no marker).
            table_name: Name of the table (used as the namespace key).

        Returns:
            Filtered DataFrame.
        """
        if df.empty or not filter_expr:
            return df

        # Determine all known lookup names from config (for joined-df context).
        lookup_names: list[str] = []
        if self.config:
            for lkp in self.config.get("inputs", {}).get("lookups", []):
                lookup_names.append(lkp.get("name", ""))

        # Detect whether we are in a joined-df context or a single-table context.
        # A joined-df has at least one column starting with a lookup prefix.
        prefix_in_cols = any(
            col.startswith(f"{ln}.")
            for ln in lookup_names
            for col in df.columns
        ) if lookup_names else False

        mask = []
        for _, row in df.iterrows():
            var_bag = _VarBag()
            if prefix_in_cols:
                # Joined-df context: split prefixed columns by table.
                main_name = (
                    self.config["inputs"]["main"]["name"]
                    if self.config else table_name
                )
                row_dicts = self._build_row_dicts_for_py(
                    row, main_name, lookup_names, df
                )
            else:
                # Single-table context: all columns belong to table_name.
                # Build a direct column -> value mapping for the table.
                table_dict = row.to_dict()
                # Build row_dicts for any other known tables as empty, plus
                # the actual table.
                row_dicts = {table_name: table_dict}
                # Also populate other table names as empty (in case the
                # expression references them but they have no data here).
                main_name = (
                    self.config["inputs"]["main"]["name"]
                    if self.config else table_name
                )
                if main_name != table_name:
                    row_dicts[main_name] = {}
                for ln in lookup_names:
                    if ln != table_name:
                        row_dicts[ln] = {}

            ns = self._build_namespace(row_dicts, var_bag)
            # Also expose plain column names at top level for convenience.
            ns.update(row.to_dict())
            try:
                result = eval(filter_expr, ns)  # noqa: S307
                mask.append(bool(result))
            except Exception:
                mask.append(False)

        filtered = df[mask].copy()
        logger.info(
            f"[{self.id}] Python filter on '{table_name}': "
            f"{len(df)} -> {len(filtered)} rows"
        )
        return filtered

    def _evaluate_variables_py(
        self,
        joined_df: pd.DataFrame,
        variables_config: list[dict],
        main_name: str,
        lookup_names: list[str],
    ) -> dict[str, list]:
        """Evaluate variable definitions row-by-row (Python-eval path).

        Variables are evaluated sequentially so later variables can
        reference earlier ones via ``Var.<name>`` (live attribute access
        via ``_VarBag``).

        Args:
            joined_df: Joined DataFrame with all lookup columns.
            variables_config: List of variable config dicts.
            main_name: Main table name.
            lookup_names: Lookup table names.

        Returns:
            Dict mapping variable name to list of per-row values.
        """
        var_names = [v["name"] for v in variables_config if v.get("name")]
        var_columns: dict[str, list] = {n: [] for n in var_names}

        for _, row in joined_df.iterrows():
            row_dicts = self._build_row_dicts_for_py(
                row, main_name, lookup_names, joined_df
            )
            var_bag = _VarBag()
            for var in variables_config:
                var_name = var.get("name", "")
                var_expr = var.get("expression", "")
                if not var_name or not var_expr:
                    continue
                # Strip any stray marker (no-marker path should have none,
                # but be defensive).
                expr = self._strip_java_marker(var_expr)
                ns = self._build_namespace(row_dicts, var_bag)
                val = self._eval_expr(expr, ns, "__variables__", var_name)
                setattr(var_bag, var_name, val)
                if var_name in var_columns:
                    var_columns[var_name].append(val)

        logger.debug(
            f"[{self.id}] Python-eval: evaluated {len(var_names)} variables "
            f"across {len(joined_df)} rows"
        )
        return var_columns

    def _eval_output_row(
        self,
        col_defs: list[dict],
        ns: dict[str, Any],
        out_name: str,
    ) -> dict[str, Any]:
        """Evaluate all column expressions for a single output row.

        Args:
            col_defs: Column definition list from output config.
            ns: Eval namespace for this row.
            out_name: Output name (for error messages).

        Returns:
            Dict of column name -> evaluated value.
        """
        row_dict: dict[str, Any] = {}
        for col_cfg in col_defs:
            col_name = col_cfg["name"]
            col_expr = col_cfg.get("expression", "")
            if not col_expr:
                row_dict[col_name] = None
                continue
            expr = self._strip_java_marker(col_expr)
            row_dict[col_name] = self._eval_expr(expr, ns, out_name, col_name)
        return row_dict

    def _evaluate_output_columns_py(
        self,
        row_source: pd.DataFrame,
        output_cfg: dict,
        var_columns: dict[str, list],
        main_name: str,
        lookup_names: list[str],
        failed_lookups: "set[str] | None" = None,
    ) -> pd.DataFrame:
        """Evaluate one output's column expressions over an arbitrary row source.

        Thin loop wrapper around ``_eval_output_row``: iterates the rows of
        ``row_source``, builds a per-row eval namespace (row dicts + _VarBag
        of variable values), evaluates each column expression, and
        materialises the result via a single ``pd.DataFrame(rows, columns=...)``
        allocation.  Empty fast path returns ``pd.DataFrame(columns=col_names)``
        when ``row_source`` is empty.

        This helper is the shared building block for the Python-eval path
        across all output kinds -- normal outputs (called by
        ``_evaluate_outputs_py``) and the three reject routing sites
        (inner-join reject, filter reject, catch-output reject) that Plans
        02-04 wire in.

        Args:
            row_source: DataFrame to iterate; one output row is emitted per
                input row.  Can be the full ``joined_df``, an
                inner-join-reject row source, a failed-filter row source, or
                a catch-output row source.
            output_cfg: The output configuration dict (must contain ``name``
                and ``columns``).
            var_columns: Pre-computed variable values per row
                (name -> [val]).  Indexed positionally against ``row_source``.
            main_name: Main table name (for row-dict construction).
            lookup_names: Lookup table names (for row-dict construction).
            failed_lookups: Optional set of lookup names that failed an
                inner join for this row source (D-04 of phase 05.4-02).
                Forwarded to ``_build_namespace`` which binds ``_NullRow``
                (raises ``AttributeError`` on attribute access) for those
                table names instead of the default ``_NullNamespace``
                (silent ``None``).  Used by ``_route_inner_join_rejects``;
                normal-output callers leave this ``None``.

        Returns:
            A single-allocation DataFrame with one row per ``row_source``
            row and one column per ``output_cfg['columns']`` entry.  Empty
            ``row_source`` yields an empty DataFrame with the declared
            column schema.
        """
        col_defs = output_cfg["columns"]
        out_name = output_cfg["name"]
        col_names = [c["name"] for c in col_defs]

        # Empty fast path: skip iteration, return empty schema-only frame.
        if row_source.empty:
            return pd.DataFrame(columns=col_names)

        out_rows: list[dict] = []
        for row_idx, _row in enumerate(row_source.itertuples(index=False)):
            row_series = row_source.iloc[row_idx]
            row_dicts = self._build_row_dicts_for_py(
                row_series, main_name, lookup_names, row_source
            )

            # Build _VarBag for this row from pre-computed variable values.
            var_bag = _VarBag()
            for v_name, v_vals in var_columns.items():
                if row_idx < len(v_vals):
                    setattr(var_bag, v_name, v_vals[row_idx])

            ns = self._build_namespace(row_dicts, var_bag, failed_lookups)
            out_row = self._eval_output_row(col_defs, ns, out_name)
            out_rows.append(out_row)

        return (
            pd.DataFrame(out_rows, columns=col_names)
            if out_rows
            else pd.DataFrame(columns=col_names)
        )

    def _evaluate_outputs_py(
        self,
        joined_df: pd.DataFrame,
        outputs_config: list[dict],
        var_columns: dict[str, list],
        main_name: str,
        lookup_names: list[str],
    ) -> dict[str, pd.DataFrame]:
        """Evaluate output column expressions (Python-eval path, no-marker branch).

        Per-row output column eval, output filter dispatch, and reject routing
        to the first ``is_reject`` output.  Honors the skip-when-already-populated
        guard: ``is_reject`` outputs are initialised empty exactly once; rows
        filtered out by an earlier output are appended to the first reject output.

        Non-filter outputs (``activate_filter`` is False) delegate to
        ``_evaluate_output_columns_py``; outputs with an active filter retain
        the inline per-row loop here because it must split each row between
        the output frame and the filter-reject frame in lockstep.  Plan 03
        will lift the filter path onto the shared helper.

        Args:
            joined_df: Joined DataFrame.
            outputs_config: List of output config dicts.
            var_columns: Pre-computed variable values per row (name -> [val]).
            main_name: Main table name.
            lookup_names: Lookup table names.

        Returns:
            Dict mapping output names to DataFrames.
        """
        result: dict[str, pd.DataFrame] = {}

        for output_cfg in outputs_config:
            out_name = output_cfg["name"]

            # Reject outputs are populated by _route_* methods or by earlier
            # outputs' filter routing.  Initialise to empty only if not yet
            # set (skip-when-already-populated guard: avoid overwriting rows
            # routed by a preceding output filter).
            if output_cfg.get("is_reject") or output_cfg.get("inner_join_reject"):
                if out_name not in result:
                    result[out_name] = pd.DataFrame(
                        columns=[c["name"] for c in output_cfg["columns"]]
                    )
                continue

            col_defs = output_cfg["columns"]
            activate_filter = output_cfg.get("activate_filter", False)
            out_filter = output_cfg.get("filter", "")

            # Non-filter outputs delegate to the shared helper (Plan 05.4-01).
            if not (activate_filter and out_filter):
                result[out_name] = self._evaluate_output_columns_py(
                    joined_df, output_cfg, var_columns, main_name, lookup_names
                )
                continue

            # Active-filter outputs keep the inline loop so kept/rejected rows
            # can be split in one pass.  Plan 05.4-03 lifts this onto
            # _evaluate_output_columns_py via a precomputed keep-mask.
            out_rows: list[dict] = []
            reject_rows: list[dict] = []

            for row_idx, _row in enumerate(joined_df.itertuples(index=False)):
                row_series = joined_df.iloc[row_idx]
                row_dicts = self._build_row_dicts_for_py(
                    row_series, main_name, lookup_names, joined_df
                )

                # Build _VarBag for this row from pre-computed variable values.
                var_bag = _VarBag()
                for v_name, v_vals in var_columns.items():
                    if row_idx < len(v_vals):
                        setattr(var_bag, v_name, v_vals[row_idx])

                ns = self._build_namespace(row_dicts, var_bag)

                # Evaluate output filter first (per Talend: filter-then-emit).
                try:
                    keep = bool(eval(out_filter, ns))  # noqa: S307
                except Exception:
                    keep = False
                if not keep:
                    reject_row = self._eval_output_row(col_defs, ns, out_name)
                    reject_rows.append(reject_row)
                    continue

                out_row = self._eval_output_row(col_defs, ns, out_name)
                out_rows.append(out_row)

            out_df = (
                pd.DataFrame(out_rows, columns=[c["name"] for c in col_defs])
                if out_rows
                else pd.DataFrame(columns=[c["name"] for c in col_defs])
            )
            result[out_name] = out_df

            # Route filter-rejected rows to the first is_reject output.
            if reject_rows:
                reject_df = pd.DataFrame(
                    reject_rows, columns=[c["name"] for c in col_defs]
                )
                for oc in outputs_config:
                    if oc.get("is_reject") and not oc.get("inner_join_reject"):
                        rej_name = oc["name"]
                        if rej_name in result and not result[rej_name].empty:
                            result[rej_name] = pd.concat(
                                [result[rej_name], reject_df], ignore_index=True
                            )
                        else:
                            result[rej_name] = reject_df
                        break

        return result

    def _apply_output_filter(
        self,
        out_df: pd.DataFrame,
        output_cfg: dict,
        result: dict,
        main_name: str,
        lookup_names: list[str],
    ) -> pd.DataFrame:
        """Apply output filter and route rejects.

        Args:
            out_df: Output DataFrame before filtering.
            output_cfg: Output configuration.
            result: Current result dict (to add reject rows).
            main_name: Main table name.
            lookup_names: Lookup table names.

        Returns:
            Filtered output DataFrame.
        """
        filter_expr = output_cfg.get("filter", "")
        if not filter_expr or out_df.empty:
            return out_df

        expr = self._strip_java_marker(filter_expr)
        # 05.4-05: bridge submits expr to GroovyShell.parse, so apply the
        # Groovy escape (in-string $ -> \$) before forwarding.
        expr = self._groovy_escape_expression(expr)
        # D-04: use _bridge_eval to ensure full lookup_names passed
        eval_result = self._bridge_eval(out_df, {"__out_filter__": expr}, lookup_names)

        if "__out_filter__" in eval_result:
            mask = pd.Series(eval_result["__out_filter__"]).fillna(False).values
            passed = out_df[mask].copy()
            failed = out_df[~mask].copy()

            # Route failed rows to reject outputs
            if not failed.empty:
                outputs_config = self.config.get("outputs", [])
                for oc in outputs_config:
                    if oc.get("is_reject") and not oc.get("inner_join_reject"):
                        rej_name = oc["name"]
                        if rej_name in result:
                            result[rej_name] = pd.concat(
                                [result[rej_name], failed], ignore_index=True
                            )
                        else:
                            result[rej_name] = failed

            return passed

        return out_df

    # ------------------------------------------------------------------
    # Catch Output Reject Routing (MAP-05)
    # ------------------------------------------------------------------

    def _route_catch_output_rejects(
        self,
        result: dict,
        raw_result: dict,
        outputs_config: list[dict],
    ) -> None:
        """Route expression error rows to catch output reject outputs.

        Catch output outputs receive rows where expression evaluation
        threw an exception, with an added errorMessage column.

        Args:
            result: Current result dict to update.
            raw_result: Raw result from compiled script execution.
            outputs_config: Output config list.
        """
        error_key = "__errors__"
        if error_key not in raw_result:
            return

        error_df = raw_result[error_key]
        if error_df is None or (isinstance(error_df, pd.DataFrame) and error_df.empty):
            return

        for output_cfg in outputs_config:
            if output_cfg.get("catch_output_reject"):
                out_name = output_cfg["name"]
                if isinstance(error_df, pd.DataFrame):
                    output_df = error_df.copy()
                    if "errorMessage" not in output_df.columns:
                        output_df["errorMessage"] = "Expression evaluation error"
                    result[out_name] = output_df
                    logger.info(
                        f"[{self.id}] Routed {len(error_df)} error rows "
                        f"to catch output '{out_name}'"
                    )

    # ------------------------------------------------------------------
    # Inner Join Reject Routing
    # ------------------------------------------------------------------

    def _route_inner_join_rejects(
        self,
        result: dict,
        inner_join_reject_dfs: dict[str, pd.DataFrame],
        outputs_config: list[dict],
    ) -> None:
        """Route inner join reject rows to ``inner_join_reject`` outputs.

        Phase 05.4-02 (R1, R7, D-02, D-03, D-04, D-05) rewrite:

        For each ``inner_join_reject: True`` output, evaluate that output's
        own column expressions per row against the failing-lookup rejects
        DataFrame -- via ``_evaluate_output_columns_py``.  This replaces the
        legacy name-based column copy (which dropped hard-coded literals,
        renamed simple refs, and ``{{java}}`` expressions to ``None``) and
        the incremental ``reject_df[col] = ...`` writes (which fragmented
        the result DataFrame, emitting ``PerformanceWarning``).

        The ``inner_join_reject_dfs`` mapping carries per-failing-lookup
        rejects: each entry's rows had main columns + any previously
        matched lookup columns but are missing the failing lookup's columns
        (D-05 partial-match binding).  This routine processes each failing
        lookup separately so the per-row failed-lookup identity is
        preserved -- ``_NullRow`` is bound only for the failing lookup
        (D-04), while previously-matched lookups remain as data namespaces.

        ``var_columns`` is intentionally ``{}``: per-row variable values
        were computed against the joined (matched) DataFrame and are not
        defined for unmatched rows in the reject row source.  Reject output
        expressions that reference ``Var.*`` will resolve to ``None`` via
        ``_VarBag.__getattr__`` semantics.

        Args:
            result: Current result dict to update in place.  When an output
                already has rows from the matched path they are concatenated
                with the rejects in a single allocation; otherwise the
                rejects frame becomes the output frame.
            inner_join_reject_dfs: Dict mapping the failing lookup's name to
                its rejects DataFrame.
            outputs_config: The component's full output list (filtered here
                for ``inner_join_reject: True`` entries).
        """
        if not inner_join_reject_dfs:
            return

        main_name = self.config["inputs"]["main"]["name"]
        lookup_names = [
            lk["name"]
            for lk in self.config["inputs"].get("lookups", [])
        ]

        for output_cfg in outputs_config:
            if not output_cfg.get("inner_join_reject"):
                continue
            out_name = output_cfg["name"]
            per_lookup_frames: list[pd.DataFrame] = []
            total_rows = 0
            for failing_lookup, rejects_df in inner_join_reject_dfs.items():
                if rejects_df is None or rejects_df.empty:
                    continue
                # _NullRow injection: only the failing lookup raises on
                # attribute access; previously-matched lookups keep their
                # data bindings (D-05).
                evaluated = self._evaluate_output_columns_py(
                    rejects_df,
                    output_cfg,
                    {},  # var_columns: not defined for reject rows
                    main_name,
                    lookup_names,
                    failed_lookups={failing_lookup},
                )
                if not evaluated.empty:
                    per_lookup_frames.append(evaluated)
                    total_rows += len(evaluated)

            if not per_lookup_frames:
                continue

            col_names = [c["name"] for c in output_cfg["columns"]]
            reject_df = (
                pd.concat(per_lookup_frames, ignore_index=True)
                if len(per_lookup_frames) > 1
                else per_lookup_frames[0]
            )
            # Single-allocation concat with any matched-path rows.
            if out_name in result and not result[out_name].empty:
                result[out_name] = pd.concat(
                    [result[out_name], reject_df], ignore_index=True
                )
            else:
                # Preserve declared column order even when matched path
                # left no frame (the helper already emits the right
                # columns, but the explicit reindex is cheap insurance).
                result[out_name] = reject_df.reindex(columns=col_names)

            logger.info(
                "[%s] Routed %d inner join rejects to output '%s'",
                self.id, total_rows, out_name,
            )

    # ------------------------------------------------------------------
    # Compiled Script Generation
    # ------------------------------------------------------------------

    def _build_compiled_script(
        self,
        outputs: list[dict],
        variables: list[dict],
        main_name: str,
        lookup_names: list[str],
    ) -> str:
        """Generate Groovy script for compiled tMap execution.

        MUST match the format expected by JavaBridge.compileTMapScript() and
        executeTMapCompiled(). The bridge injects these binding variables:
          - inputRoot       (VectorSchemaRoot)
          - rowCount        (int)
          - buildRowWrapper (Closure) -- calls JavaBridge.buildArrowRowWrapper()
          - context         (Map)
          - globalMap       (Map)

        The script must return Map<String, Map<String, Object>> where each
        output entry contains:
          "data"  -> Object[][] (row-major, data[row][col])
          "count" -> int (actual row count written)

        RowWrappers are created via buildRowWrapper(inputRoot, i, tableName)
        -- a Groovy closure injected by buildTMapBinding that delegates to
        JavaBridge.buildArrowRowWrapper(). This keeps Arrow vector reading
        in Java (Phase 2 design) while giving scripts clean row access via
        Groovy's propertyMissing (row1.columnName).

        Per-output method split (TMAP-METHOD-SIZE fix)
        ----------------------------------------------
        The compiled Groovy script is divided into per-output helper
        methods plus a thin row loop:

            def evalOutput_<name>(int i, RowWrapper main, RowWrapper lk1, ...,
                                  Map<String,Object> Var) {
                if (!(<filter>)) return null;     // when activate_filter
                Object[] row = new Object[N];
                row[0] = ...;
                ...
                return row;
            }

            for (int i = 0; i < rowCount; i++) {
                try {
                    RowWrapper main = buildRowWrapper(inputRoot, i, "main");
                    ...                          // lookup wrappers
                    Map Var = new HashMap();
                    Var.put(...)                 // variables
                    Object[] r = evalOutput_<name>(i, main, lk1, ..., Var);
                    if (r != null) <name>_data[<name>_count++] = r;
                    ...
                } catch (Exception e) { ... }
            }

        Each helper compiles into its own JVM method with its own 64KB
        bytecode budget, so an output with up to 250 columns (the
        agreed-on cap) stays comfortably under the per-method limit. The
        prior monolithic run() body summed every output's bytecode and
        overflowed the JVM Code-attribute limit at high column counts,
        triggering groovyjarjarasm.asm.MethodTooLargeException.

        Helpers receive everything they need as arguments. Bindings
        (buildRowWrapper, inputRoot) are touched only inside run().
        Routine classes (TalendString etc.) and the context / globalMap
        maps remain accessible from helper bodies via Groovy's Script
        getProperty -> binding fall-through.

        Args:
            outputs: Output config list.
            variables: Variable config list.
            main_name: Main table name.
            lookup_names: Lookup table names.

        Returns:
            Groovy script string matching bridge API contract.
        """
        die_on_error = self.config.get("die_on_error", True)
        has_catch = any(o.get("catch_output_reject") for o in outputs)

        # Active (non-reject) outputs are emitted as helpers and called
        # from the row loop. is_reject and inner_join_reject outputs are
        # populated elsewhere in the Python pipeline (see _route_*
        # methods); emitting helpers for them would generate dead code.
        active_outputs = [
            o for o in outputs
            if not o.get("is_reject") and not o.get("inner_join_reject")
        ]

        lines: list[str] = []

        # Imports (Groovy for-loop, not Java lambdas -- lambdas can't see
        # Groovy script-binding variables like buildRowWrapper).
        lines.append("import java.util.*;")
        lines.append("import com.citi.gru.etl.RowWrapper;")
        lines.append("")

        # ----- Per-output helper methods (one method per output) --------
        # Helper signature: receives the row index, every RowWrapper that
        # exists in run() (main + each lookup), and the populated Var map.
        # All names are passed as method parameters so the helper body
        # never relies on Groovy script-binding lookups for row data.
        helper_params = (
            f"int i, RowWrapper {main_name}"
            + "".join(f", RowWrapper {lk}" for lk in lookup_names)
            + ", Map<String, Object> Var"
        )

        # CHUNK size for column fill helpers.
        # Each fillOutput_<name>_chunkN method handles this many column
        # assignments. A single complex Talend expression can compile to
        # several hundred bytes of JVM bytecode; keeping to 1 column per
        # helper guarantees no individual method ever exceeds 64 KB even
        # for the most complex expressions (ternary chains, regex, etc.).
        _FILL_CHUNK = 1

        # Chunk-fill params: receive the shared row array + all wrappers.
        # The row array is passed by reference so each chunk writes into
        # the same Object[] that evalOutput_<name> allocated.
        chunk_fill_params = (
            f"Object[] row, RowWrapper {main_name}"
            + "".join(f", RowWrapper {lk}" for lk in lookup_names)
            + ", Map<String, Object> Var"
        )
        chunk_fill_args = (
            f"row, {main_name}"
            + "".join(f", {lk}" for lk in lookup_names)
            + ", Var"
        )

        for output in active_outputs:
            out_name = output["name"]
            num_cols = len(output["columns"])
            columns = output["columns"]
            filter_expr = output.get("filter", "")
            activate_filter = output.get("activate_filter", False)

            # --- Emit one fill helper per chunk of columns ---
            for chunk_start in range(0, num_cols, _FILL_CHUNK):
                chunk_cols = columns[chunk_start:chunk_start + _FILL_CHUNK]
                chunk_idx = chunk_start // _FILL_CHUNK
                lines.append(
                    f"void fillOutput_{out_name}_chunk{chunk_idx}"
                    f"({chunk_fill_params}) {{"
                )
                for col_offset, col in enumerate(chunk_cols):
                    abs_idx = chunk_start + col_offset
                    col_expr = col.get("expression", "")
                    expr = self._groovy_escape_expression(
                        self._strip_java_marker(col_expr)
                    )
                    if not expr or expr.strip() == "":
                        expr = "null"
                    lines.append(f"    row[{abs_idx}] = {expr};")
                lines.append("}")
                lines.append("")

            # --- Coordinator: evalOutput_<name> allocates array, calls chunks ---
            num_chunks = -(-num_cols // _FILL_CHUNK)  # ceiling division
            lines.append(f"Object[] evalOutput_{out_name}({helper_params}) {{")
            # Filter guard: return null if this row is filtered out.
            if activate_filter and filter_expr:
                clean_filter = self._groovy_escape_expression(
                    self._strip_java_marker(filter_expr)
                )
                lines.append(f"    if (!({clean_filter})) return null;")
            lines.append(f"    Object[] row = new Object[{num_cols}];")
            for chunk_idx in range(num_chunks):
                lines.append(
                    f"    fillOutput_{out_name}_chunk{chunk_idx}({chunk_fill_args});"
                )
            lines.append("    return row;")
            lines.append("}")
            lines.append("")

        # ----- Output buffers + counters --------------------------------
        for output in active_outputs:
            out_name = output["name"]
            num_cols = len(output["columns"])
            lines.append(f"Object[][] {out_name}_data = new Object[rowCount][{num_cols}];")
            lines.append(f"int {out_name}_count = 0;")

        # Error tracking (when die_on_error=false or any catch_output_reject).
        if not die_on_error or has_catch:
            lines.append("int errorCount = 0;")
            lines.append("Map<Integer, String> errorMap = new HashMap<>();")
        lines.append("")

        # ----- Main row loop (thin) -------------------------------------
        lines.append("for (int i = 0; i < rowCount; i++) {")
        lines.append("    try {")

        # Build RowWrappers via the bridge-injected closure -- keeps Arrow
        # vector reading in Java (Phase 2 design).
        lines.append(
            f"        RowWrapper {main_name} = buildRowWrapper(inputRoot, i, \"{main_name}\");"
        )
        for lk_name in lookup_names:
            lines.append(
                f"        RowWrapper {lk_name} = buildRowWrapper(inputRoot, i, \"{lk_name}\");"
            )
        lines.append("")

        # Variable evaluation (sequential -- later vars can read earlier
        # ones via Var.get(...)). Var is always emitted, even when
        # variables is empty, because helpers declare it as a parameter.
        lines.append("        Map<String, Object> Var = new HashMap<>();")
        for var in variables or []:
            var_name = var.get("name", "")
            var_expr = var.get("expression", "")
            if var_expr:
                expr = self._groovy_escape_expression(
                    self._strip_java_marker(var_expr)
                )
                if not expr or expr.strip() == "":
                    expr = "null"
                lines.append(f'        Var.put("{var_name}", {expr});')
        lines.append("")

        # Per-output helper invocations. Helper returns null when the
        # output's filter rejects the row -- skip the slot in that case.
        helper_args = (
            f"i, {main_name}"
            + "".join(f", {lk}" for lk in lookup_names)
            + ", Var"
        )
        for output in active_outputs:
            out_name = output["name"]
            lines.append(
                f"        Object[] {out_name}_row = evalOutput_{out_name}({helper_args});"
            )
            lines.append(f"        if ({out_name}_row != null) {{")
            lines.append(f"            {out_name}_data[{out_name}_count++] = {out_name}_row;")
            lines.append("        }")

        # Error handling -- semantics unchanged from the pre-split script.
        lines.append("    } catch (Exception e) {")
        if die_on_error and not has_catch:
            lines.append(
                '        throw new RuntimeException("Error at row " + i + ": " '
                '+ (e.getMessage() != null ? e.getMessage() : e.toString()), e);'
            )
        else:
            lines.append("        errorCount++;")
            lines.append(
                '        errorMap.put(i, e.getMessage() != null ? e.getMessage() : e.toString());'
            )
        lines.append("    }")
        lines.append("}")
        lines.append("")

        # ----- Return results map ---------------------------------------
        lines.append("Map<String, Map<String, Object>> results = new HashMap<>();")
        for output in active_outputs:
            out_name = output["name"]
            lines.append(f'Map<String, Object> {out_name}_result = new HashMap<>();')
            lines.append(f'{out_name}_result.put("data", {out_name}_data);')
            lines.append(f'{out_name}_result.put("count", {out_name}_count);')
            lines.append(f'results.put("{out_name}", {out_name}_result);')

        if not die_on_error or has_catch:
            lines.append('Map<String, Object> errorInfo = new HashMap<>();')
            lines.append('errorInfo.put("count", errorCount);')
            lines.append('errorInfo.put("indices", new java.util.ArrayList<>(errorMap.keySet()));')
            lines.append('errorInfo.put("messages", errorMap);')
            lines.append('results.put("__errors__", errorInfo);')

        lines.append("return results;")

        return "\n".join(lines)

    def _build_output_schema(
        self, outputs: list[dict]
    ) -> tuple[dict[str, list], dict[str, str]]:
        """Build output_schemas and output_types for compile/execute calls.

        output_schemas: {output_name: [col_name, ...]}
        output_types:   {output_name + "_" + col_name: python_type_str}

        The output_types format is required by JavaBridge.convertTMapOutputsToArrow()
        which looks up types as outputTypes.get(outputName + "_" + colName).

        Args:
            outputs: Output config list.

        Returns:
            Tuple of (output_schemas, output_types).
        """
        output_schemas: dict[str, list] = {}
        output_types: dict[str, str] = {}

        for output in outputs:
            out_name = output["name"]
            cols = output["columns"]
            output_schemas[out_name] = [c["name"] for c in cols]
            for col in cols:
                col_name = col["name"]
                col_type = col.get("type", "str")
                type_key = f"{out_name}_{col_name}"
                output_types[type_key] = col_type

        return output_schemas, output_types

    # ------------------------------------------------------------------
    # Java Bridge Wrappers
    # ------------------------------------------------------------------

    def _evaluate_with_bridge(
        self,
        df: pd.DataFrame,
        expressions: dict[str, str],
        main_name: str,
        lookup_names: list[str],
    ) -> dict:
        """Evaluate expressions via Java bridge preprocessing.

        Falls back gracefully if Java bridge is not available.

        Args:
            df: DataFrame to evaluate against.
            expressions: Dict of expr_id -> expression_string.
            main_name: Main table name.
            lookup_names: Lookup table names.

        Returns:
            Dict of expr_id -> numpy array of results.
        """
        if self.java_bridge is None:
            logger.warning(
                f"[{self.id}] Java bridge not available, "
                f"skipping expression evaluation for "
                f"{list(expressions.keys())}"
            )
            return {}

        if df.empty:
            return {}

        # Build schema dict for Arrow
        schema_dict = _infer_arrow_schema_dict(df)

        try:
            return self.java_bridge.execute_tmap_preprocessing(
                df=df,
                expressions=expressions,
                main_table_name=main_name,
                lookup_table_names=lookup_names,
                schema=schema_dict,
            )
        except Exception as e:
            logger.error(
                f"[{self.id}] Java bridge preprocessing failed: {e}"
            )
            if self.die_on_error:
                raise ComponentExecutionError(
                    self.id, f"Expression evaluation failed: {e}", cause=e
                )
            return {}

    def _bridge_eval(
        self,
        df: pd.DataFrame,
        exprs: dict[str, str],
        joined_lookup_names: list[str],
    ) -> dict:
        """Single-source-of-truth wrapper around _evaluate_with_bridge (D-04).

        Every tMap bridge call must go through here so joined_lookup_names is
        consistently the full prior-join list. Callers that evaluate on a
        cross-product that includes the current lookup should pass
        ``joined_lookup_names + [current_lookup_name]`` as the third argument.

        Args:
            df: DataFrame to evaluate against.
            exprs: Dict of expr_id -> expression_string.
            joined_lookup_names: Full list of already-joined lookup names that
                should be visible to the bridge (D-04).

        Returns:
            Dict of expr_id -> list of results.
        """
        main_name = self.config["inputs"]["main"]["name"]
        return self._evaluate_with_bridge(df, exprs, main_name, joined_lookup_names)

    def _has_any_java_marker(self) -> bool:
        """Check whether ANY expression-bearing config field starts with {{java}}.

        Scans all marker-bearing fields in self.config:
          - inputs.main.filter
          - inputs.lookups[*].filter
          - inputs.lookups[*].join_keys[*].expression
          - variables[*].expression
          - outputs[*].filter
          - outputs[*].columns[*].expression

        Per D-01/D-02: the marker itself is the routing signal. No per-column
        simplicity check; any single {{java}} prefix anywhere forces the
        compiled Groovy path.

        Returns:
            True if any field starts with the {{java}} marker.
        """
        cfg = self.config

        # -- main filter --
        main_filter = cfg.get("inputs", {}).get("main", {}).get("filter", "")
        if isinstance(main_filter, str) and main_filter.startswith(_JAVA_MARKER):
            return True

        # -- lookup filters and join key expressions --
        for lookup in cfg.get("inputs", {}).get("lookups", []):
            lf = lookup.get("filter", "")
            if isinstance(lf, str) and lf.startswith(_JAVA_MARKER):
                return True
            for jk in lookup.get("join_keys", []):
                jk_expr = jk.get("expression", "")
                if isinstance(jk_expr, str) and jk_expr.startswith(_JAVA_MARKER):
                    return True

        # -- variable expressions --
        for var in cfg.get("variables", []):
            v_expr = var.get("expression", "")
            if isinstance(v_expr, str) and v_expr.startswith(_JAVA_MARKER):
                return True

        # -- output filters and column expressions --
        for output in cfg.get("outputs", []):
            out_filter = output.get("filter", "")
            if isinstance(out_filter, str) and out_filter.startswith(_JAVA_MARKER):
                return True
            for col in output.get("columns", []):
                col_expr = col.get("expression", "")
                if isinstance(col_expr, str) and col_expr.startswith(_JAVA_MARKER):
                    return True

        return False

    # ------------------------------------------------------------------
    # Helper Methods
    # ------------------------------------------------------------------

    def _strip_java_marker(self, expr: str) -> str:
        """Remove {{java}} prefix from expression.

        Args:
            expr: Expression string, possibly with {{java}} prefix.

        Returns:
            Expression with prefix stripped.
        """
        if expr.startswith(_JAVA_MARKER):
            return expr[len(_JAVA_MARKER):]
        return expr

    def _groovy_escape_expression(self, java_expr: str) -> str:
        """Escape Groovy-special characters in a Java expression before
        embedding into a Groovy script.

        The expression text reaches the Groovy runtime via two paths in
        this module:
          - interpolation into a Groovy source line emitted by
            ``_build_compiled_script`` (compiled-script path), and
          - direct submission as the body of a ``GroovyShell.parse(...)``
            call inside ``JavaBridge.executeTMapPreprocessing`` (bridge-
            eval path).

        Both paths reach a GroovyShell. Groovy's double-quoted string
        literal is a GString, which interpolates ``$identifier`` and
        ``${expr}`` at runtime. A Talend Java expression such as
        ``"Total: $100"`` therefore raises a parse error or, worse,
        evaluates an unintended identifier when it reaches GroovyShell.
        This helper neutralises that difference by tokenising the input
        and escaping ``$`` -> ``\\$`` inside double-quoted string regions
        only. Outside string regions, ``$`` is a legal identifier
        character in both languages and is left alone.

        Escape sequences (``\\\\``, ``\\"``) inside a string region are
        consumed as a two-character unit so they cannot mis-detect the
        closing quote of the string.

        The full character-class disposition matrix lives in
        ``.planning/phases/05.4-tmap-reject-correctness-and-groovy-safety/
        05.4-GROOVY-AUDIT.md`` (D-07). Any future addition belongs in
        that table first, then in this helper.

        Args:
            java_expr: Raw Java/Talend expression text (already stripped of
                the ``{{java}}`` marker by ``_strip_java_marker``).

        Returns:
            Expression string safe for embedding into a Groovy source line
            or for submission as a standalone Groovy script body.
        """
        result: list[str] = []
        in_string = False
        i = 0
        n = len(java_expr)
        while i < n:
            ch = java_expr[i]
            if not in_string:
                if ch == '"':
                    in_string = True
                    result.append(ch)
                    i += 1
                else:
                    result.append(ch)
                    i += 1
                continue
            # Inside a double-quoted string literal.
            if ch == "\\" and i + 1 < n:
                # Java escape sequence -- pass both chars through unchanged.
                # This keeps \" and \\ from mis-detecting the closing quote.
                result.append(ch)
                result.append(java_expr[i + 1])
                i += 2
            elif ch == '"':
                # End of string literal.
                in_string = False
                result.append(ch)
                i += 1
            elif ch == "$":
                # Groovy GString interpolation trigger -- escape it.
                result.append("\\$")
                i += 1
            else:
                result.append(ch)
                i += 1
        return "".join(result)

    def _is_simple_column_ref(self, expr: str) -> bool:
        """Check if expression is a simple column reference (table.column).

        Args:
            expr: Expression string (already stripped of {{java}}).

        Returns:
            True if expression matches table.column pattern.
        """
        return bool(_SIMPLE_COLUMN_RE.match(expr.strip()))

    def _is_context_only_expression(self, expr: str) -> bool:
        """Check if expression references only context/globalMap values.

        An expression is context-only if it contains NO row references
        (table.column patterns where table is not 'context' or 'globalMap').

        Args:
            expr: Expression string (already stripped of {{java}}).

        Returns:
            True if expression has no row-data references.
        """
        stripped = expr.strip()  # Already stripped of {{java}} by caller

        # Find all table.column patterns
        matches = _ROW_REF_PATTERN.findall(stripped)

        # Filter out context.* and globalMap.* references
        row_references = [
            m for m in matches
            if m[0] not in ("context", "globalMap", "Var")
        ]

        return len(row_references) == 0

    def _classify_key_locality(
        self,
        expr: str,
        main_name: str,
        current_lookup: str,
        joined_lookup_names: list[str],
    ) -> str:
        """Classify a single join key expression by locality (D-03).

        Strips the {{java}} marker before classification. Each expression is
        classified into exactly one of the four locality buckets based on which
        row references it contains.

        Args:
            expr: Join key expression (may have {{java}} prefix).
            main_name: Name of the main input table.
            current_lookup: Name of the lookup currently being joined.
            joined_lookup_names: Names of lookups already joined (in joined_df).

        Returns:
            One of: _LOCALITY_CONTEXT, _LOCALITY_MAIN_SIDE,
            _LOCALITY_LOOKUP_SIDE, _LOCALITY_TWO_SIDED.
        """
        stripped = self._strip_java_marker(expr).strip()
        matches = _ROW_REF_PATTERN.findall(stripped)
        # matches returns tuples (table_name, column_name); filter out
        # context/globalMap/Var which are not row references.
        row_refs = {m[0] for m in matches if m[0] not in ("context", "globalMap", "Var")}

        if not row_refs:
            return _LOCALITY_CONTEXT

        # joined_df contains main + all previously-joined lookups -- they are all
        # "main side" relative to the current lookup being joined.
        main_side_tables = {main_name, *joined_lookup_names}
        refs_main = bool(row_refs & main_side_tables)
        refs_lookup = current_lookup in row_refs

        if refs_main and refs_lookup:
            return _LOCALITY_TWO_SIDED
        if refs_lookup:
            return _LOCALITY_LOOKUP_SIDE
        return _LOCALITY_MAIN_SIDE

    def _find_column(
        self, df: pd.DataFrame, table: str, column: str
    ) -> Optional[str]:
        """Find a column in DataFrame by table.column reference.

        Tries multiple name patterns:
        1. Exact table.column (prefixed lookup columns)
        2. Just column name (main table columns)
        3. Var.column (variable references)

        Args:
            df: DataFrame to search.
            table: Table name portion.
            column: Column name portion.

        Returns:
            Column name found in DataFrame, or None.
        """
        # Try prefixed form first (for lookup columns)
        prefixed = f"{table}.{column}"
        if prefixed in df.columns:
            return prefixed

        # Try plain column name (for main table)
        if column in df.columns:
            return column

        # Try Var. prefix (for variable references)
        var_name = f"Var.{column}"
        if var_name in df.columns:
            return var_name

        return None

    def _values_equal(self, a: Any, b: Any) -> bool:
        """Type-aware value comparison for join keys.

        Numeric types compared as numbers (int 1 == float 1.0).
        When one side is a string that looks numeric and the other is
        numeric, attempts safe cast before comparison.
        Non-numeric compared as strings. Null/NaN handled by caller.

        Note: float promotion may lose precision for very large 64-bit
        integers (>2^53). This is a known limitation -- ETL join keys
        rarely use integers that large. (Addresses LOW review concern
        about float precision.)

        Args:
            a: First value (assumed non-null by caller).
            b: Second value (assumed non-null by caller).

        Returns:
            True if values are equal under type-aware comparison.
        """
        a_numeric = isinstance(a, (int, float, np.integer, np.floating))
        b_numeric = isinstance(b, (int, float, np.integer, np.floating))

        if a_numeric and b_numeric:
            return float(a) == float(b)

        # One numeric, one string: try safe cast of string to numeric
        # (addresses review suggestion for string-to-numeric edge case)
        if a_numeric and isinstance(b, str):
            try:
                return float(a) == float(b)
            except (ValueError, TypeError):
                return False
        if b_numeric and isinstance(a, str):
            try:
                return float(a) == float(b)
            except (ValueError, TypeError):
                return False

        # Both non-numeric: string comparison
        return str(a) == str(b)

    def _prefilter_null_keys(
        self, df: pd.DataFrame, key_columns: list[str]
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Split DataFrame into rows with all keys non-null vs any key null.

        Implements MAP-03: Null join keys never match (SQL/Talend semantics).

        Args:
            df: DataFrame to split.
            key_columns: List of key column names.

        Returns:
            Tuple of (non_null_df, null_key_df).
        """
        if df.empty:
            return df.copy(), pd.DataFrame(columns=df.columns)

        # Filter to only key columns that exist in the DataFrame
        existing_keys = [k for k in key_columns if k in df.columns]
        if not existing_keys:
            return df.copy(), pd.DataFrame(columns=df.columns)

        null_mask = df[existing_keys].isna().any(axis=1)
        return df[~null_mask].copy(), df[null_mask].copy()

    def _apply_matching_mode(
        self,
        lookup_df: pd.DataFrame,
        key_columns: list[str],
        mode: str,
    ) -> pd.DataFrame:
        """Deduplicate lookup DataFrame per matching mode.

        Args:
            lookup_df: Lookup DataFrame.
            key_columns: Join key column names.
            mode: Matching mode string.

        Returns:
            Deduplicated DataFrame.
        """
        if lookup_df.empty:
            return lookup_df

        existing_keys = [k for k in key_columns if k in lookup_df.columns]
        if not existing_keys:
            return lookup_df

        if mode == _UNIQUE_MATCH:
            # Talend HashMap.put overwrites -- last row wins (keep='last')
            return lookup_df.drop_duplicates(
                subset=existing_keys, keep="last"
            )
        elif mode == _FIRST_MATCH:
            return lookup_df.drop_duplicates(
                subset=existing_keys, keep="first"
            )
        elif mode == _LAST_MATCH:
            return lookup_df.drop_duplicates(
                subset=existing_keys, keep="last"
            )
        elif mode == _ALL_MATCHES:
            # No dedup -- cartesian product possible
            return lookup_df
        else:
            logger.warning(
                f"[{self.id}] Unknown matching mode '{mode}', "
                f"defaulting to UNIQUE_MATCH"
            )
            return lookup_df.drop_duplicates(
                subset=existing_keys, keep="last"
            )

    def _prefix_lookup_columns(
        self, lookup_df: pd.DataFrame, lookup_name: str
    ) -> pd.DataFrame:
        """Prefix all lookup columns with lookup_name to avoid collisions.

        Args:
            lookup_df: Lookup DataFrame.
            lookup_name: Lookup table name.

        Returns:
            DataFrame with prefixed column names.
        """
        renamed = {}
        for col in lookup_df.columns:
            col_str = str(col)
            if not col_str.startswith(f"{lookup_name}."):
                renamed[col] = f"{lookup_name}.{col_str}"
        if renamed:
            return lookup_df.rename(columns=renamed)
        return lookup_df

    def _auto_convert_join_keys(
        self,
        main_df: pd.DataFrame,
        lookup_df: pd.DataFrame,
        left_keys: list[str],
        right_keys: list[str],
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Auto-convert join key columns to compatible types (MAP-06).

        Handles common type mismatches: str<->numeric, int<->float.

        Args:
            main_df: Main DataFrame.
            lookup_df: Lookup DataFrame.
            left_keys: Main side join key columns.
            right_keys: Lookup side join key columns.

        Returns:
            Tuple of (main_df, lookup_df) with converted types.
        """
        main_df = main_df.copy()
        lookup_df = lookup_df.copy()

        def _is_string_like(dtype) -> bool:
            """Check if dtype is string-like (object or pandas StringDtype)."""
            if dtype == object:
                return True
            return pd.api.types.is_string_dtype(dtype)

        def _safe_issubdtype(dtype, supertype) -> bool:
            """np.issubdtype wrapper safe for pandas extension dtypes."""
            try:
                return np.issubdtype(dtype, supertype)
            except TypeError:
                return False

        for left_key, right_key in zip(left_keys, right_keys):
            if left_key not in main_df.columns or right_key not in lookup_df.columns:
                continue

            left_dtype = main_df[left_key].dtype
            right_dtype = lookup_df[right_key].dtype

            if left_dtype == right_dtype:
                continue

            # Auto-conversion strategy: when types mismatch between str and
            # numeric, always convert str -> numeric (matches Talend BigDecimal
            # coercion).  No numeric -> str branch needed.
            if _is_string_like(left_dtype) and _safe_issubdtype(right_dtype, np.number):
                main_df[left_key] = pd.to_numeric(
                    main_df[left_key], errors="coerce"
                )
            elif _is_string_like(right_dtype) and _safe_issubdtype(left_dtype, np.number):
                lookup_df[right_key] = pd.to_numeric(
                    lookup_df[right_key], errors="coerce"
                )
            # int <-> float
            elif _safe_issubdtype(left_dtype, np.integer) and _safe_issubdtype(right_dtype, np.floating):
                main_df[left_key] = main_df[left_key].astype(float)
            elif _safe_issubdtype(left_dtype, np.floating) and _safe_issubdtype(right_dtype, np.integer):
                lookup_df[right_key] = lookup_df[right_key].astype(float)

            logger.debug(
                f"[{self.id}] Auto-converted join key types: "
                f"{left_key}({left_dtype}) <-> {right_key}({right_dtype})"
            )

        return main_df, lookup_df

    def _get_output_config(self, output_name: str) -> Optional[dict]:
        """Find output config by name.

        Args:
            output_name: Output name to find.

        Returns:
            Output config dict, or None if not found.
        """
        for output in self.config.get("outputs", []):
            if output.get("name") == output_name:
                return output
        return None

    def _create_empty_outputs(self) -> dict:
        """Create dict with empty DataFrames for all configured outputs.

        Returns:
            Dict mapping output names to empty DataFrames.
        """
        result = {}
        for output in self.config.get("outputs", []):
            out_name = output["name"]
            cols = [c["name"] for c in output.get("columns", [])]
            result[out_name] = pd.DataFrame(columns=cols)
        return result

    def _check_size_guard(
        self, main_count: int, lookup_count: int, mode: str
    ) -> None:
        """Warn or fail for large cartesian/cross-table joins.

        Implements T-05-02 and T-05-03 threat mitigations.

        Args:
            main_count: Number of main rows.
            lookup_count: Number of lookup rows.
            mode: Matching mode or join description.

        Raises:
            ComponentExecutionError: If product exceeds hard limit.
        """
        product = main_count * lookup_count
        if product >= _FAIL_RESULT_ROWS:
            raise ComponentExecutionError(
                self.id,
                f"Join would produce ~{product:,} rows "
                f"(main={main_count:,} x lookup={lookup_count:,}, "
                f"mode={mode}). Exceeds safety limit of "
                f"{_FAIL_RESULT_ROWS:,} rows."
            )
        if product >= _WARN_RESULT_ROWS:
            logger.warning(
                f"[{self.id}] Large join: ~{product:,} rows "
                f"(main={main_count:,} x lookup={lookup_count:,}, "
                f"mode={mode})"
            )
