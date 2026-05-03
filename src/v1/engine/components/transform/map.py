"""Engine component for Map (tMap).

Multi-flow data mapping with lookup joins, variable evaluation, expression-based
column mappings, and multi-output routing. Preserves hybrid architecture: pandas
for bulk equality joins, Java bridge for expression evaluation.

Config keys consumed (8 total):
  inputs            (dict)  -- main input + lookups list with join keys, modes
  variables         (list)  -- variable definitions with expressions
  outputs           (list)  -- output tables with column expressions, filters, reject flags
  die_on_error      (bool, default True)  -- raise on expression error
  rows_buffer_size  (str, default "2000000")  -- buffer size hint
  enable_auto_convert_type  (bool, default False)  -- auto-cast join key types
  parallel_execution (bool, default True)  -- parallel forEach in compiled scripts
  label             (str, default "")  -- component label
"""
import logging
import re
from decimal import Decimal
from typing import Any, Optional

import numpy as np
import pandas as pd

from ...base_component import BaseComponent, ExecutionMode
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, ComponentExecutionError, DataValidationError

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

# Join types from smart routing
_JOIN_EQUALITY = "equality"
_JOIN_CONTEXT_ONLY = "context_only"
_JOIN_CROSS_TABLE = "cross_table"

# Chunk size for preprocessing and compiled script execution
_DEFAULT_CHUNK_SIZE = 50000
_DEFAULT_CHUNK_THRESHOLD = 100000  # Only chunk if DataFrame exceeds this

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
        for key in ("die_on_error", "rows_buffer_size", "label",
                     "enable_auto_convert_type"):
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

            # Apply lookup filter (skip for RELOAD -- per-row loop needs full lookup)
            if (lookup_config.get("activate_filter")
                    and lookup_config.get("filter")
                    and lookup_mode != _RELOAD_AT_EACH_ROW):
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
                join_type = self._classify_join_type(
                    lookup_config["join_keys"]
                )
                if join_type == _JOIN_EQUALITY:
                    joined_df, rejects = self._join_equality(
                        joined_df, lookup_df, lookup_config
                    )
                elif join_type == _JOIN_CONTEXT_ONLY:
                    joined_df, rejects = self._join_context_only(
                        joined_df, lookup_df, lookup_config
                    )
                else:
                    joined_df, rejects = self._join_cross_table(
                        joined_df, lookup_df, lookup_config
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
        _use_compiled = (
            self._has_java_expressions(outputs_config)
            and self.java_bridge is not None
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
        if variables_config and not _use_compiled:
            joined_df = self._evaluate_variables(
                joined_df, variables_config, main_name, joined_lookup_names
            )

        # Steps 6-8: Evaluate outputs (compiled script or simple column refs)
        result = self._evaluate_outputs(
            joined_df, outputs_config, variables_config,
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

        Uses Java bridge preprocessing for complex expressions, or
        direct column access for simple column references.

        Args:
            df: DataFrame to filter.
            filter_expr: Filter expression (may have {{java}} prefix).
            table_name: Name of the table being filtered.
            lookup_names: Names of already-joined lookups.

        Returns:
            Filtered DataFrame.
        """
        expr = self._strip_java_marker(filter_expr)

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

        # Complex expression -- use Java bridge
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
        resolved_expr = self._substitute_row_refs(
            self._strip_java_marker(filter_expr),
            main_row,
            main_name,
        )

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
    # Join Classification and Routing
    # ------------------------------------------------------------------

    def _classify_join_type(self, join_keys: list[dict]) -> str:
        """Classify join keys into equality, context_only, or cross_table.

        Args:
            join_keys: List of join key dicts with 'expression' field.

        Returns:
            One of: "equality", "context_only", "cross_table".
        """
        has_equality = False
        has_context = False

        for jk in join_keys:
            expr = self._strip_java_marker(jk["expression"])
            if self._is_simple_column_ref(expr):
                has_equality = True
            elif self._is_context_only_expression(expr):
                has_context = True
            else:
                return _JOIN_CROSS_TABLE

        if has_context and not has_equality:
            return _JOIN_CONTEXT_ONLY
        return _JOIN_EQUALITY

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
    # Context-Only Join
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
    # Cross-Table Join
    # ------------------------------------------------------------------

    def _join_cross_table(
        self,
        joined_df: pd.DataFrame,
        lookup_df: pd.DataFrame,
        lookup_config: dict,
    ) -> tuple[pd.DataFrame, Optional[pd.DataFrame]]:
        """Join where keys reference both main and lookup columns.

        Uses Java bridge preprocessing for expression evaluation.

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

        self._check_size_guard(len(joined_df), len(lookup_df), matching_mode)

        logger.warning(
            f"[{self.id}] Cross-table join with '{lookup_name}' "
            f"-- O(n*m) evaluation ({len(joined_df)} x {len(lookup_df)} rows)"
        )

        # Apply matching mode to lookup first
        key_cols = [jk["lookup_column"] for jk in join_keys]
        lookup_df = self._apply_matching_mode(lookup_df, key_cols, matching_mode)

        # Prefix lookup columns
        lookup_df = self._prefix_lookup_columns(lookup_df, lookup_name)

        # Cross join and evaluate expressions
        joined_df_cross = joined_df.assign(__cross_key__=1)
        lookup_df_cross = lookup_df.assign(__cross_key__=1)
        cross = pd.merge(joined_df_cross, lookup_df_cross, on="__cross_key__")
        cross = cross.drop(columns=["__cross_key__"])

        if cross.empty:
            if join_mode == "INNER_JOIN":
                return pd.DataFrame(columns=joined_df.columns), joined_df.copy()
            return joined_df, None

        # Evaluate all join key expressions on the cross product
        main_name = self.config["inputs"]["main"]["name"]
        exprs = {}
        for i, jk in enumerate(join_keys):
            expr = self._strip_java_marker(jk["expression"])
            exprs[f"__jk_{i}__"] = expr

        eval_results = self._evaluate_with_bridge(
            cross, exprs, main_name, [lookup_name]
        )

        # Build match mask
        match_mask = pd.Series([True] * len(cross), index=cross.index)
        for i, jk in enumerate(join_keys):
            expr_key = f"__jk_{i}__"
            lookup_col = f"{lookup_name}.{jk['lookup_column']}"
            if expr_key in eval_results:
                eval_vals = pd.Series(eval_results[expr_key], index=cross.index)
                if lookup_col in cross.columns:
                    match_mask = match_mask & (
                        eval_vals.astype(str) == cross[lookup_col].astype(str)
                    )

        matched = cross[match_mask].copy()

        rejects = None
        if join_mode == "INNER_JOIN":
            # After cross join, matched has a new RangeIndex (0..N*M-1) that
            # does NOT correspond to joined_df's index.  Compare on column
            # values to find which original main rows got at least one match.
            main_cols = list(joined_df.columns)
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

        if matched.empty and join_mode != "INNER_JOIN":
            return joined_df, None

        logger.info(
            f"[{self.id}] Cross-table join with '{lookup_name}': "
            f"{len(matched)} rows"
        )
        return matched, rejects

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
                result = self._evaluate_with_bridge(
                    joined_df, {col_name: expr}, main_name, lookup_names
                )
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

        # Check if we can use compiled script execution
        has_java_expressions = self._has_java_expressions(outputs_config)

        if has_java_expressions and self.java_bridge is not None:
            result = self._evaluate_outputs_compiled(
                joined_df, outputs_config, variables_config,
                main_name, lookup_names
            )
        else:
            result = self._evaluate_outputs_simple(
                joined_df, outputs_config, main_name, lookup_names
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
        chunk_size = int(self.config.get("rows_buffer_size", _DEFAULT_CHUNK_SIZE))
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

    def _evaluate_outputs_simple(
        self,
        joined_df: pd.DataFrame,
        outputs_config: list[dict],
        main_name: str,
        lookup_names: list[str],
    ) -> dict[str, pd.DataFrame]:
        """Evaluate outputs using simple column references.

        Fallback when Java bridge is not available. Only handles simple
        table.column references; complex expressions are skipped with a warning.

        Args:
            joined_df: Joined DataFrame.
            outputs_config: Output config list.
            main_name: Main table name.
            lookup_names: Lookup table names.

        Returns:
            Dict mapping output names to DataFrames.
        """
        result: dict[str, pd.DataFrame] = {}

        for output_cfg in outputs_config:
            out_name = output_cfg["name"]
            is_reject = output_cfg.get("is_reject", False)
            is_inner_reject = output_cfg.get("inner_join_reject", False)

            # Skip reject outputs -- they are populated from rejects
            if is_reject or is_inner_reject:
                result[out_name] = pd.DataFrame(
                    columns=[c["name"] for c in output_cfg["columns"]]
                )
                continue

            out_df = pd.DataFrame()
            for col_cfg in output_cfg["columns"]:
                col_name = col_cfg["name"]
                col_expr = col_cfg.get("expression", "")
                expr = self._strip_java_marker(col_expr)

                if self._is_simple_column_ref(expr):
                    match = _SIMPLE_COLUMN_RE.match(expr.strip())
                    if match:
                        table, column = match.group(1), match.group(2)
                        src_col = self._find_column(joined_df, table, column)
                        if src_col:
                            out_df[col_name] = joined_df[src_col].values
                        else:
                            out_df[col_name] = None
                elif expr.startswith("Var."):
                    # Variable reference
                    var_col = expr
                    if var_col in joined_df.columns:
                        out_df[col_name] = joined_df[var_col].values
                    else:
                        out_df[col_name] = None
                else:
                    # Try Java bridge preprocessing for single expression
                    eval_result = self._evaluate_with_bridge(
                        joined_df, {col_name: expr}, main_name, lookup_names
                    )
                    if col_name in eval_result:
                        out_df[col_name] = eval_result[col_name]
                    else:
                        logger.warning(
                            f"[{self.id}] Cannot evaluate expression "
                            f"for column '{col_name}' in output '{out_name}' "
                            f"-- Java bridge not available"
                        )
                        out_df[col_name] = None

            # Apply output filter
            if (output_cfg.get("activate_filter")
                    and output_cfg.get("filter")):
                out_df = self._apply_output_filter(
                    out_df, output_cfg, result, main_name, lookup_names
                )

            result[out_name] = out_df

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
        eval_result = self._evaluate_with_bridge(
            out_df, {"__out_filter__": expr}, main_name, lookup_names
        )

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
        """Route inner join reject rows to appropriate outputs.

        Args:
            result: Current result dict to update.
            inner_join_reject_dfs: Dict of reject DataFrames per lookup.
            outputs_config: Output config list.
        """
        if not inner_join_reject_dfs:
            return

        # Combine all inner join rejects
        all_rejects = pd.concat(
            list(inner_join_reject_dfs.values()), ignore_index=True
        )

        for output_cfg in outputs_config:
            if output_cfg.get("inner_join_reject"):
                out_name = output_cfg["name"]
                # Select only columns defined in this output
                out_cols = [c["name"] for c in output_cfg["columns"]]
                reject_df = pd.DataFrame()
                for col_name in out_cols:
                    if col_name in all_rejects.columns:
                        reject_df[col_name] = all_rejects[col_name].values
                    else:
                        reject_df[col_name] = None

                if out_name in result and not result[out_name].empty:
                    result[out_name] = pd.concat(
                        [result[out_name], reject_df], ignore_index=True
                    )
                else:
                    result[out_name] = reject_df

                logger.info(
                    f"[{self.id}] Routed {len(reject_df)} inner join "
                    f"rejects to output '{out_name}'"
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

        Args:
            outputs: Output config list.
            variables: Variable config list.
            main_name: Main table name.
            lookup_names: Lookup table names.

        Returns:
            Groovy script string matching bridge API contract.
        """
        die_on_error = self.config.get("die_on_error", True)

        lines: list[str] = []

        # Imports (no concurrent/stream -- using Groovy for-loop, not Java lambdas)
        lines.append("import java.util.*;")
        lines.append("import com.citi.gru.etl.RowWrapper;")
        lines.append("")

        # Pre-allocate output arrays and counters for each non-reject output
        active_outputs = [
            o for o in outputs
            if not o.get("is_reject") and not o.get("inner_join_reject")
        ]
        for output in active_outputs:
            out_name = output["name"]
            num_cols = len(output["columns"])
            lines.append(f"Object[][] {out_name}_data = new Object[rowCount][{num_cols}];")
            lines.append(f"int {out_name}_count = 0;")

        # Error tracking (if die_on_error=false or catch_output_reject)
        has_catch = any(o.get("catch_output_reject") for o in outputs)
        if not die_on_error or has_catch:
            lines.append("int errorCount = 0;")
            lines.append("Map<Integer, String> errorMap = new HashMap<>();")
        lines.append("")

        # Main processing loop -- uses Groovy for-loop (not IntStream.forEach).
        # Java lambdas in IntStream.forEach cannot access Groovy binding
        # variables (buildRowWrapper, inputRoot, etc.) -- this is a known
        # Groovy/Java interop limitation. Plain for-loop has full binding access.
        lines.append("for (int i = 0; i < rowCount; i++) {")
        lines.append("    try {")

        # Build RowWrappers using the bridge-injected buildRowWrapper closure.
        # This delegates to JavaBridge.buildArrowRowWrapper() which handles
        # Arrow vector reading, table-name prefixed column lookup, and type
        # extraction -- keeping all Arrow complexity in Java (Phase 2 design).
        lines.append(f"        RowWrapper {main_name} = buildRowWrapper(inputRoot, i, \"{main_name}\");")
        for lk_name in lookup_names:
            lines.append(f"        RowWrapper {lk_name} = buildRowWrapper(inputRoot, i, \"{lk_name}\");")
        lines.append("")

        # Variable evaluation (sequential, supports dependency chains)
        if variables:
            lines.append("        Map<String, Object> Var = new HashMap<>();")
            for var in variables:
                var_name = var.get("name", "")
                var_expr = var.get("expression", "")
                if var_expr:
                    expr = self._strip_java_marker(var_expr)
                    if not expr or expr.strip() == "":
                        expr = "null"
                    lines.append(f'        Var.put("{var_name}", {expr});')
            lines.append("")

        # Output expression evaluation
        lines.append("        // Evaluate outputs")
        for output in active_outputs:
            out_name = output["name"]
            num_cols = len(output["columns"])
            filter_expr = output.get("filter", "")
            activate_filter = output.get("activate_filter", False)

            # Output filter
            if activate_filter and filter_expr:
                clean_filter = self._strip_java_marker(filter_expr)
                lines.append(f"        if ({clean_filter}) {{")
                indent = "            "
            else:
                lines.append("        {")
                indent = "            "

            # Pre-evaluate all columns into temp array
            lines.append(f"{indent}Object[] {out_name}_row = new Object[{num_cols}];")
            for col_idx, col in enumerate(output["columns"]):
                col_expr = col.get("expression", "")
                expr = self._strip_java_marker(col_expr)
                if not expr or expr.strip() == "":
                    expr = "null"
                lines.append(f"{indent}{out_name}_row[{col_idx}] = {expr};")

            # Commit to output array
            lines.append(f"{indent}int {out_name}_idx = {out_name}_count++;")
            lines.append(f"{indent}{out_name}_data[{out_name}_idx] = {out_name}_row;")
            lines.append("        }")
            lines.append("")

        # Error handling
        lines.append("    } catch (Exception e) {")
        if die_on_error and not has_catch:
            lines.append('        throw new RuntimeException("Error at row " + i + ": " + (e.getMessage() != null ? e.getMessage() : e.toString()), e);')
        else:
            lines.append("        errorCount++;")
            lines.append('        errorMap.put(i, e.getMessage() != null ? e.getMessage() : e.toString());')
        lines.append("    }")
        lines.append("}")
        lines.append("")

        # Return results map
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

    def _has_java_expressions(self, outputs_config: list[dict]) -> bool:
        """Check if any output column has a Java expression.

        Args:
            outputs_config: Output config list.

        Returns:
            True if any column expression starts with {{java}}.
        """
        for output in outputs_config:
            for col in output.get("columns", []):
                expr = col.get("expression", "")
                if expr.startswith(_JAVA_MARKER):
                    stripped = self._strip_java_marker(expr)
                    if not self._is_simple_column_ref(stripped):
                        return True
            filter_expr = output.get("filter", "")
            if filter_expr.startswith(_JAVA_MARKER):
                stripped = self._strip_java_marker(filter_expr)
                if not self._is_simple_column_ref(stripped):
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
