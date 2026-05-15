"""Engine component for PyMap -- pure-Python multi-flow data mapping.

A new, non-Talend component that provides the same join, variable, and
output-mapping capabilities as tMap but uses Python ``eval()`` for
expression evaluation instead of a Java/Groovy bridge.

All expressions are written as plain Python (e.g. ``row1['price'] * 1.05``,
``re.sub(r'\\s+', '_', row1['name'])``). No ``{{java}}`` prefix is used.

Config keys consumed (6 total):
  inputs            (dict)  -- ``main`` input + ``lookups`` list with join keys, modes
  variables         (list)  -- variable definitions with Python expressions
  outputs           (list)  -- output tables with Python column expressions, filters
  die_on_error      (bool, default True)  -- raise on expression error; False routes to reject
  enable_auto_convert_type  (bool, default False)  -- auto-cast join key types
  label             (str, default "")  -- component label

Expression namespace available inside every expression:
  row1, row2, ...   -- current main / lookup rows as plain ``dict`` objects
                       (key = column name without the table prefix)
  Var               -- dict of evaluated variables (populated sequentially)
  pd, np, re, datetime, Decimal, json, math  -- standard helpers
  All safe builtins from _code_component_mixin (no os / sys / open / eval / exec)

Join semantics mirror tMap (pandas-based):
  - LEFT_OUTER_JOIN / INNER_JOIN (with inner-join reject routing)
  - UNIQUE_MATCH / FIRST_MATCH / LAST_MATCH / ALL_MATCHES dedup
  - LOAD_ONCE / RELOAD_AT_EACH_ROW lookup modes
  - INNER_JOIN rejects routed to ``inner_join_reject=True`` outputs
  - Output filter rejects routed to ``is_reject=True`` outputs
"""
from __future__ import annotations

import datetime as _datetime_module
import json as _json_module
import logging
import math as _math_module
import re as _re_module
from decimal import Decimal
from typing import Any, Optional

import numpy as np
import pandas as pd

from ...base_component import BaseComponent, ExecutionMode
from ...component_registry import REGISTRY
from ...exceptions import ComponentExecutionError, ConfigurationError
from ._code_component_mixin import _SAFE_NAMESPACE_GLOBALS, _build_safe_builtins

logger = logging.getLogger(__name__)

# Pattern for simple column references: table.column
_SIMPLE_COLUMN_RE = _re_module.compile(r'^([a-zA-Z_]\w*)\.([a-zA-Z_]\w*)$')

# Matching modes
_UNIQUE_MATCH = "UNIQUE_MATCH"
_FIRST_MATCH = "FIRST_MATCH"
_LAST_MATCH = "LAST_MATCH"
_ALL_MATCHES = "ALL_MATCHES"

# Lookup modes
_LOAD_ONCE = "LOAD_ONCE"
_RELOAD_AT_EACH_ROW = "RELOAD_AT_EACH_ROW"

# Size guard thresholds
_WARN_RESULT_ROWS = 10_000_000
_FAIL_RESULT_ROWS = 100_000_000


class _Row(dict):
    """Dict subclass that also supports attribute-style access.

    Allows expressions to use either ``row1['col']`` or ``row1.col``.
    """

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"Row has no column '{name}'") from None


@REGISTRY.register("PyMap")
class PyMap(BaseComponent):
    """Pure-Python multi-flow data mapping component.

    Provides join, variable evaluation, and expression-based column mapping
    without the Java bridge. All expressions are evaluated via Python ``eval()``
    in a sandboxed namespace.

    Config keys:
        inputs: Main input and lookups list with join keys and modes.
        variables: Variable definitions with Python expressions.
        outputs: Output tables with Python column expressions, filters.
        die_on_error: Raise on expression error (default True).
        enable_auto_convert_type: Auto-cast join key types (default False).
        label: Component label (default "").
    """

    # ------------------------------------------------------------------
    # Lifecycle Hook Overrides
    # ------------------------------------------------------------------

    def _resolve_expressions(self) -> None:
        """Resolve context variables on scalar config fields only.

        Row-level expressions reference live data that does not exist at
        config-resolution time; they are evaluated per-row in _process().
        Only scalar config fields are resolved here.
        """
        if self.context_manager is None:
            return
        for key in ("die_on_error", "label", "enable_auto_convert_type"):
            if key in self.config and isinstance(self.config[key], str):
                self.config[key] = self.context_manager.resolve_string(
                    self.config[key]
                )

    def _select_mode(self, input_data: Any) -> ExecutionMode:
        """Always BATCH -- PyMap handles its own row-level iteration."""
        return ExecutionMode.BATCH

    def _update_stats_from_result(self, result: dict) -> None:
        """Sum rows across all named output DataFrames.

        PyMap returns arbitrary named outputs, not just main/reject.

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
                if output_cfg and (
                    output_cfg.get("is_reject")
                    or output_cfg.get("inner_join_reject")
                ):
                    reject_rows += count
        self.stats["NB_LINE"] += total_rows
        self.stats["NB_LINE_OK"] += total_rows - reject_rows
        self.stats["NB_LINE_REJECT"] += reject_rows

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate PyMap component configuration.

        Raises:
            ConfigurationError: If configuration is missing or invalid.
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

    def _process(self, input_data: Any = None) -> dict:
        """Process PyMap transformation.

        Receives Dict[flow_name, DataFrame] from OutputRouter.
        Returns Dict[output_name, DataFrame] for downstream routing.

        Args:
            input_data: Dict of DataFrames keyed by flow name, or single
                DataFrame, or None.

        Returns:
            Dict mapping output names to DataFrames.
        """
        # Step 1: Parse inputs
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
            logger.warning(f"[{self.id}] Main input '{main_name}' is empty")
            return self._create_empty_outputs()

        logger.info(
            f"[{self.id}] Processing {len(main_df)} main rows "
            f"with {len(lookups_config)} lookups"
        )

        # Step 2: Apply main input filter
        if main_config.get("activate_filter") and main_config.get("filter"):
            main_df = self._apply_filter_py(main_df, main_config["filter"], main_name)
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
                # Add NaN-filled prefixed columns so output expressions that
                # reference this lookup (e.g. row2['label']) return NaN
                # instead of raising KeyError.
                if lookup_df is not None and len(lookup_df.columns) > 0:
                    for col in lookup_df.columns:
                        prefixed = f"{lookup_name}.{col}"
                        if prefixed not in joined_df.columns:
                            joined_df[prefixed] = np.nan
                joined_lookup_names.append(lookup_name)
                continue

            lookup_mode = lookup_config.get("lookup_mode", _LOAD_ONCE)

            # Apply lookup filter (skip for RELOAD -- per-row loop uses full df)
            if (
                lookup_config.get("activate_filter")
                and lookup_config.get("filter")
                and lookup_mode != _RELOAD_AT_EACH_ROW
            ):
                lookup_df = self._apply_filter_py(
                    lookup_df, lookup_config["filter"], lookup_name
                )

            if lookup_mode == _RELOAD_AT_EACH_ROW:
                joined_df, rejects = self._join_reload_per_row(
                    joined_df, lookup_df, lookup_config
                )
            else:
                joined_df, rejects = self._join_equality(
                    joined_df, lookup_df, lookup_config
                )

            if rejects is not None and not rejects.empty:
                inner_join_reject_dfs[lookup_name] = rejects

            joined_lookup_names.append(lookup_name)

        if joined_df.empty:
            logger.info(f"[{self.id}] No rows after lookups")
            result = self._create_empty_outputs()
            self._route_inner_join_rejects(
                result, inner_join_reject_dfs, outputs_config
            )
            return result

        logger.info(
            f"[{self.id}] After lookups: {len(joined_df)} rows, "
            f"{len(joined_df.columns)} columns"
        )

        # Step 4: Evaluate variables
        var_columns: dict[str, list] = {}  # var_name -> list of per-row values
        if variables_config:
            var_columns = self._evaluate_variables_py(
                joined_df, variables_config, main_name, joined_lookup_names
            )

        # Step 5: Evaluate outputs
        result = self._evaluate_outputs_py(
            joined_df, outputs_config, var_columns, main_name, joined_lookup_names
        )

        # Step 6: Route inner join rejects
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
    # Python Expression Evaluation Namespace
    # ------------------------------------------------------------------

    def _build_namespace(
        self,
        row_dicts: dict[str, dict],
        var_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """Build the eval namespace for a single row.

        Args:
            row_dicts: Mapping of table_name -> row dict (col -> value).
            var_dict: Current Var dict (populated variables).

        Returns:
            Namespace dict for ``eval()``.
        """
        ns: dict[str, Any] = {}
        ns.update(_SAFE_NAMESPACE_GLOBALS)
        ns["__builtins__"] = _build_safe_builtins()
        # Row access: expressions may use row1['col'] or row1.col
        ns.update({name: _Row(rd) for name, rd in row_dicts.items()})
        ns["Var"] = var_dict
        # Standard helpers not in _SAFE_NAMESPACE_GLOBALS
        ns["Decimal"] = Decimal
        return ns

    def _eval_expr(
        self,
        expr: str,
        ns: dict[str, Any],
        col_name: str,
        output_name: str,
    ) -> Any:
        """Safely evaluate a Python expression in a namespace.

        Args:
            expr: Python expression string.
            ns: Eval namespace dict.
            col_name: Column name (for error messages).
            output_name: Output name (for error messages).

        Returns:
            Evaluated value, or raises on error depending on die_on_error.

        Raises:
            ComponentExecutionError: When die_on_error is True and evaluation fails.
        """
        try:
            return eval(expr, ns)  # noqa: S307
        except Exception as exc:
            msg = (
                f"[{self.id}] Expression eval failed for "
                f"output '{output_name}' column '{col_name}': "
                f"{type(exc).__name__}: {exc} | expr={expr!r}"
            )
            if self.die_on_error:
                raise ComponentExecutionError(self.id, msg, cause=exc) from exc
            logger.warning(msg)
            return None

    # ------------------------------------------------------------------
    # Filter Evaluation (Python)
    # ------------------------------------------------------------------

    def _apply_filter_py(
        self,
        df: pd.DataFrame,
        filter_expr: str,
        table_name: str,
    ) -> pd.DataFrame:
        """Apply a Python filter expression to a DataFrame.

        The filter expression is evaluated per-row; rows where the
        expression is truthy are kept.

        Args:
            df: DataFrame to filter.
            filter_expr: Python boolean expression string.
            table_name: Name of the table (used as namespace key for this row).

        Returns:
            Filtered DataFrame.
        """
        if df.empty or not filter_expr:
            return df

        mask = []
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            # Provide both prefixed (table.col) and plain (col) access
            ns = self._build_namespace(
                {table_name: row_dict}, {}
            )
            # Also expose plain column names at top level for convenience
            ns.update(row_dict)
            try:
                result = eval(filter_expr, ns)  # noqa: S307
                mask.append(bool(result))
            except Exception:
                mask.append(False)

        filtered = df[mask].copy()
        logger.info(
            f"[{self.id}] Filter on '{table_name}': "
            f"{len(df)} -> {len(filtered)} rows"
        )
        return filtered

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

        Join key expressions must be simple ``table.column`` references.
        Expressions that cannot be resolved to a simple column reference
        are logged and skipped.

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
        auto_convert = self.config.get("enable_auto_convert_type", False)

        # Resolve left/right join key column names
        left_keys = []
        right_keys = []
        for jk in join_keys:
            expr = jk["expression"]
            m = _SIMPLE_COLUMN_RE.match(expr.strip())
            if m:
                table, column = m.group(1), m.group(2)
                col_name = self._find_column(joined_df, table, column)
                left_keys.append(col_name if col_name else column)
            else:
                # For non-simple expressions, fall back to column name directly
                left_keys.append(expr)
            right_keys.append(jk["lookup_column"])

        # Dedup lookup per matching mode
        lookup_df = self._apply_matching_mode(lookup_df, right_keys, matching_mode)

        # Guard against large ALL_MATCHES cartesian products
        if matching_mode == _ALL_MATCHES:
            self._check_size_guard(len(joined_df), len(lookup_df), matching_mode)

        # Prefix lookup columns to avoid collisions
        lookup_df = self._prefix_lookup_columns(lookup_df, lookup_name)
        prefixed_right_keys = [f"{lookup_name}.{k}" for k in right_keys]

        # Auto type conversion
        if auto_convert:
            joined_df, lookup_df = self._auto_convert_join_keys(
                joined_df, lookup_df, left_keys, prefixed_right_keys
            )

        # Null key pre-filter (null keys never match)
        main_nonnull, main_null = self._prefilter_null_keys(joined_df, left_keys)
        lookup_nonnull, _ = self._prefilter_null_keys(lookup_df, prefixed_right_keys)

        if main_nonnull.empty:
            merged = pd.DataFrame(
                columns=list(joined_df.columns) + list(lookup_df.columns)
            )
            rejects = main_null.copy() if join_mode == "INNER_JOIN" else None
        else:
            merged = pd.merge(
                main_nonnull, lookup_nonnull,
                left_on=left_keys, right_on=prefixed_right_keys,
                how="left", indicator=True, suffixes=("", "__dup__"),
            )

            rejects = None
            if join_mode == "INNER_JOIN":
                unmatched_mask = merged["_merge"] == "left_only"
                if unmatched_mask.any():
                    rejects = merged.loc[unmatched_mask].drop(
                        columns=["_merge"]
                    ).copy()
                if not main_null.empty:
                    rejects = (
                        pd.concat([rejects, main_null], ignore_index=True)
                        if rejects is not None
                        else main_null.copy()
                    )
                merged = merged.loc[~unmatched_mask].copy()

            if "_merge" in merged.columns:
                merged = merged.drop(columns=["_merge"])

        # Re-add null-key rows for outer join
        if join_mode != "INNER_JOIN" and not main_null.empty:
            merged = pd.concat([merged, main_null], ignore_index=True)

        # Drop duplicate key columns from lookup side
        dup_cols = [c for c in merged.columns if c.endswith("__dup__")]
        if dup_cols:
            merged = merged.drop(columns=dup_cols)

        logger.info(
            f"[{self.id}] Equality join with '{lookup_name}': {len(merged)} rows"
            + (f", {len(rejects)} inner join rejects" if rejects is not None else "")
        )
        return merged, rejects

    # ------------------------------------------------------------------
    # RELOAD_AT_EACH_ROW Join
    # ------------------------------------------------------------------

    def _join_reload_per_row(
        self,
        joined_df: pd.DataFrame,
        lookup_df: pd.DataFrame,
        lookup_config: dict,
    ) -> tuple[pd.DataFrame, Optional[pd.DataFrame]]:
        """Per-row lookup re-filter for RELOAD_AT_EACH_ROW mode.

        For each main row, re-evaluates the lookup filter against the
        full lookup DataFrame and performs single-row matching.

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

        if len(joined_df) > 10000 and len(lookup_df) > 10000:
            logger.warning(
                f"[{self.id}] RELOAD_AT_EACH_ROW with large datasets: "
                f"{len(joined_df)} main x {len(lookup_df)} lookup -- O(n*m)"
            )

        key_cols = [jk["lookup_column"] for jk in join_keys]
        lookup_prefixed_cols = [
            col if col.startswith(f"{lookup_name}.") else f"{lookup_name}.{col}"
            for col in lookup_df.columns
        ]

        result_rows = []
        reject_rows = []

        for _, main_row in joined_df.iterrows():
            # Re-filter lookup with main row context
            if lookup_config.get("activate_filter") and lookup_config.get("filter"):
                filtered = self._apply_reload_filter(
                    lookup_df,
                    lookup_config["filter"],
                    lookup_name,
                    main_row,
                )
            else:
                filtered = lookup_df

            if filtered.empty:
                if join_mode == "INNER_JOIN":
                    reject_rows.append(main_row)
                else:
                    result_rows.append(main_row)
                continue

            filtered = self._apply_matching_mode(filtered, key_cols, matching_mode)
            prefixed = self._prefix_lookup_columns(filtered, lookup_name)

            matched = False
            for _, lookup_row in prefixed.iterrows():
                key_match = True
                for jk in join_keys:
                    expr = jk["expression"]
                    lookup_col = f"{lookup_name}.{jk['lookup_column']}"
                    m = _SIMPLE_COLUMN_RE.match(expr.strip())
                    if m:
                        table, column = m.group(1), m.group(2)
                        src = self._find_column(joined_df, table, column) or column
                        main_val = main_row.get(src)
                    else:
                        main_val = None
                    lookup_val = lookup_row.get(lookup_col)
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
                    combined = main_row.copy()
                    for col in lookup_prefixed_cols:
                        combined[col] = np.nan
                    result_rows.append(combined)

        result_df = (
            pd.DataFrame(result_rows).reset_index(drop=True)
            if result_rows
            else pd.DataFrame(
                columns=list(joined_df.columns) + lookup_prefixed_cols
            )
        )
        rejects = (
            pd.DataFrame(reject_rows).reset_index(drop=True)
            if reject_rows
            else None
        )

        logger.info(
            f"[{self.id}] RELOAD_AT_EACH_ROW join with '{lookup_name}': "
            f"{len(result_df)} rows"
            + (f", {len(rejects)} inner join rejects" if rejects is not None else "")
        )
        return result_df, rejects

    def _apply_reload_filter(
        self,
        lookup_df: pd.DataFrame,
        filter_expr: str,
        lookup_name: str,
        main_row: pd.Series,
    ) -> pd.DataFrame:
        """Apply per-row filter for RELOAD_AT_EACH_ROW.

        Substitutes main row values into the filter expression before
        evaluating against the lookup DataFrame.

        Args:
            lookup_df: Full lookup DataFrame.
            filter_expr: Filter expression (Python).
            lookup_name: Lookup table name.
            main_row: Current main row values.

        Returns:
            Filtered lookup DataFrame.
        """
        main_row_dict = main_row.to_dict()
        mask = []
        for _, lookup_row in lookup_df.iterrows():
            lookup_row_dict = lookup_row.to_dict()
            ns = self._build_namespace(
                {lookup_name: lookup_row_dict}, {}
            )
            ns.update(main_row_dict)
            try:
                result = eval(filter_expr, ns)  # noqa: S307
                mask.append(bool(result))
            except (TypeError, ValueError):
                mask.append(False)
        return lookup_df[mask].copy()

    # ------------------------------------------------------------------
    # Variable Evaluation (Python)
    # ------------------------------------------------------------------

    def _evaluate_variables_py(
        self,
        joined_df: pd.DataFrame,
        variables_config: list[dict],
        main_name: str,
        lookup_names: list[str],
    ) -> dict[str, list]:
        """Evaluate variable definitions row-by-row.

        Variables are evaluated sequentially so later variables can
        reference earlier ones via ``Var['name']``.

        Args:
            joined_df: Joined DataFrame with all lookup columns.
            variables_config: List of variable config dicts.
            main_name: Main table name.
            lookup_names: Lookup table names.

        Returns:
            Dict mapping variable name to list of per-row values.
        """
        # Pre-collect all variable names to size results
        var_names = [v["name"] for v in variables_config if v.get("name")]
        var_columns: dict[str, list] = {n: [] for n in var_names}

        for _, row in joined_df.iterrows():
            row_dicts = self._build_row_dicts(row, main_name, lookup_names, joined_df)
            var_dict: dict[str, Any] = {}
            for var in variables_config:
                var_name = var.get("name", "")
                var_expr = var.get("expression", "")
                if not var_name or not var_expr:
                    continue
                ns = self._build_namespace(row_dicts, var_dict)
                val = self._eval_expr(var_expr, ns, var_name, "__variables__")
                var_dict[var_name] = val
                var_columns[var_name].append(val)

        logger.debug(
            f"[{self.id}] Evaluated {len(var_names)} variables "
            f"across {len(joined_df)} rows"
        )
        return var_columns

    # ------------------------------------------------------------------
    # Output Evaluation (Python)
    # ------------------------------------------------------------------

    def _evaluate_outputs_py(
        self,
        joined_df: pd.DataFrame,
        outputs_config: list[dict],
        var_columns: dict[str, list],
        main_name: str,
        lookup_names: list[str],
    ) -> dict[str, pd.DataFrame]:
        """Evaluate output column expressions and route to named outputs.

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
            # outputs' filter routing. Only initialise to empty if not already
            # set (avoid overwriting rows routed by a preceding output filter).
            if output_cfg.get("is_reject") or output_cfg.get("inner_join_reject"):
                if out_name not in result:
                    result[out_name] = pd.DataFrame(
                        columns=[c["name"] for c in output_cfg["columns"]]
                    )
                continue

            out_rows = []
            reject_rows = []
            col_defs = output_cfg["columns"]
            activate_filter = output_cfg.get("activate_filter", False)
            out_filter = output_cfg.get("filter", "")

            for row_idx, row in enumerate(joined_df.itertuples(index=False)):
                row_series = joined_df.iloc[row_idx]
                row_dicts = self._build_row_dicts(
                    row_series, main_name, lookup_names, joined_df
                )

                # Build Var dict for this row
                var_dict: dict[str, Any] = {
                    k: v[row_idx] for k, v in var_columns.items()
                    if row_idx < len(v)
                }

                ns = self._build_namespace(row_dicts, var_dict)

                # Evaluate output filter first
                if activate_filter and out_filter:
                    try:
                        keep = bool(eval(out_filter, ns))  # noqa: S307
                    except Exception:
                        keep = False
                    if not keep:
                        # Build the row dict for the reject output
                        reject_row_dict = self._eval_output_row(
                            col_defs, ns, out_name
                        )
                        reject_rows.append(reject_row_dict)
                        continue

                out_row_dict = self._eval_output_row(col_defs, ns, out_name)
                out_rows.append(out_row_dict)

            out_df = pd.DataFrame(
                out_rows, columns=[c["name"] for c in col_defs]
            ) if out_rows else pd.DataFrame(
                columns=[c["name"] for c in col_defs]
            )
            result[out_name] = out_df

            # Route filter-rejected rows to the first is_reject output
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

    def _eval_output_row(
        self,
        col_defs: list[dict],
        ns: dict[str, Any],
        out_name: str,
    ) -> dict[str, Any]:
        """Evaluate all column expressions for a single row.

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
            row_dict[col_name] = self._eval_expr(col_expr, ns, col_name, out_name)
        return row_dict

    # ------------------------------------------------------------------
    # Row Dict Construction
    # ------------------------------------------------------------------

    def _build_row_dicts(
        self,
        row: pd.Series,
        main_name: str,
        lookup_names: list[str],
        df: pd.DataFrame,
    ) -> dict[str, dict]:
        """Build per-table row dicts from a joined row Series.

        The joined DataFrame has columns like:
          - plain column names (main table)
          - ``lookup_name.column`` (prefixed lookup columns)

        This method splits them into per-table dicts so expressions can
        reference ``row1['col']`` or ``row2['col']``.

        Args:
            row: A single row from the joined DataFrame.
            main_name: Main table name.
            lookup_names: Lookup table names.
            df: The joined DataFrame (used for column listing).

        Returns:
            Dict of table_name -> {col -> value}.
        """
        row_dicts: dict[str, dict] = {}

        # Main table: plain columns (those not prefixed by any lookup name)
        lookup_prefixes = tuple(f"{ln}." for ln in lookup_names)
        main_row_dict: dict[str, Any] = {}
        for col in df.columns:
            val = row[col] if col in row.index else np.nan
            if not col.startswith(lookup_prefixes):
                # Also strip Var. prefix from variable columns
                if col.startswith("Var."):
                    pass  # Variables are handled separately via var_dict
                else:
                    main_row_dict[col] = val
        row_dicts[main_name] = main_row_dict

        # Lookup tables: prefixed columns
        for ln in lookup_names:
            prefix = f"{ln}."
            lookup_row_dict: dict[str, Any] = {}
            for col in df.columns:
                if col.startswith(prefix):
                    plain_col = col[len(prefix):]
                    val = row[col] if col in row.index else np.nan
                    lookup_row_dict[plain_col] = val
            row_dicts[ln] = lookup_row_dict

        return row_dicts

    # ------------------------------------------------------------------
    # Inner Join Reject Routing
    # ------------------------------------------------------------------

    def _route_inner_join_rejects(
        self,
        result: dict,
        inner_join_reject_dfs: dict[str, pd.DataFrame],
        outputs_config: list[dict],
    ) -> None:
        """Route inner join reject rows to the appropriate outputs.

        Args:
            result: Current result dict to update in-place.
            inner_join_reject_dfs: Dict of reject DataFrames per lookup.
            outputs_config: Output config list.
        """
        if not inner_join_reject_dfs:
            return

        all_rejects = pd.concat(
            list(inner_join_reject_dfs.values()), ignore_index=True
        )

        for output_cfg in outputs_config:
            if output_cfg.get("inner_join_reject"):
                out_name = output_cfg["name"]
                out_cols = [c["name"] for c in output_cfg["columns"]]
                reject_df = pd.DataFrame()
                for col_name in out_cols:
                    reject_df[col_name] = (
                        all_rejects[col_name].values
                        if col_name in all_rejects.columns
                        else None
                    )
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
    # Helper Utilities
    # ------------------------------------------------------------------

    def _get_output_config(self, output_name: str) -> Optional[dict]:
        """Find output config by name.

        Args:
            output_name: Output name.

        Returns:
            Output config dict, or None.
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

    def _find_column(
        self, df: pd.DataFrame, table: str, column: str
    ) -> Optional[str]:
        """Find a column in DataFrame by table.column reference.

        Args:
            df: DataFrame to search.
            table: Table name portion.
            column: Column name portion.

        Returns:
            Column name found in DataFrame, or None.
        """
        prefixed = f"{table}.{column}"
        if prefixed in df.columns:
            return prefixed
        if column in df.columns:
            return column
        var_name = f"Var.{column}"
        if var_name in df.columns:
            return var_name
        return None

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
            return lookup_df.drop_duplicates(subset=existing_keys, keep="last")
        elif mode == _FIRST_MATCH:
            return lookup_df.drop_duplicates(subset=existing_keys, keep="first")
        elif mode == _LAST_MATCH:
            return lookup_df.drop_duplicates(subset=existing_keys, keep="last")
        elif mode == _ALL_MATCHES:
            return lookup_df
        else:
            logger.warning(
                f"[{self.id}] Unknown matching mode '{mode}', defaulting to UNIQUE_MATCH"
            )
            return lookup_df.drop_duplicates(subset=existing_keys, keep="last")

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
        renamed = {
            col: f"{lookup_name}.{col}"
            for col in lookup_df.columns
            if not str(col).startswith(f"{lookup_name}.")
        }
        return lookup_df.rename(columns=renamed) if renamed else lookup_df

    def _prefilter_null_keys(
        self, df: pd.DataFrame, key_columns: list[str]
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Split DataFrame into rows with all keys non-null vs any key null.

        Args:
            df: DataFrame to split.
            key_columns: List of key column names.

        Returns:
            Tuple of (non_null_df, null_key_df).
        """
        if df.empty:
            return df.copy(), pd.DataFrame(columns=df.columns)
        existing_keys = [k for k in key_columns if k in df.columns]
        if not existing_keys:
            return df.copy(), pd.DataFrame(columns=df.columns)
        null_mask = df[existing_keys].isna().any(axis=1)
        return df[~null_mask].copy(), df[null_mask].copy()

    def _auto_convert_join_keys(
        self,
        main_df: pd.DataFrame,
        lookup_df: pd.DataFrame,
        left_keys: list[str],
        right_keys: list[str],
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Auto-convert join key columns to compatible types.

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
            return dtype == object or pd.api.types.is_string_dtype(dtype)

        def _safe_issubdtype(dtype, supertype) -> bool:
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

            if _is_string_like(left_dtype) and _safe_issubdtype(right_dtype, np.number):
                main_df[left_key] = pd.to_numeric(main_df[left_key], errors="coerce")
            elif _is_string_like(right_dtype) and _safe_issubdtype(left_dtype, np.number):
                lookup_df[right_key] = pd.to_numeric(lookup_df[right_key], errors="coerce")
            elif _safe_issubdtype(left_dtype, np.integer) and _safe_issubdtype(right_dtype, np.floating):
                main_df[left_key] = main_df[left_key].astype(float)
            elif _safe_issubdtype(left_dtype, np.floating) and _safe_issubdtype(right_dtype, np.integer):
                lookup_df[right_key] = lookup_df[right_key].astype(float)

        return main_df, lookup_df

    def _values_equal(self, a: Any, b: Any) -> bool:
        """Type-aware value comparison for join keys.

        Args:
            a: First value (assumed non-null).
            b: Second value (assumed non-null).

        Returns:
            True if values are equal.
        """
        a_numeric = isinstance(a, (int, float, np.integer, np.floating))
        b_numeric = isinstance(b, (int, float, np.integer, np.floating))
        if a_numeric and b_numeric:
            return float(a) == float(b)
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
        return str(a) == str(b)

    def _check_size_guard(
        self, main_count: int, lookup_count: int, mode: str
    ) -> None:
        """Warn or fail for large cartesian joins.

        Args:
            main_count: Main row count.
            lookup_count: Lookup row count.
            mode: Matching mode label.

        Raises:
            ComponentExecutionError: If estimated result exceeds _FAIL_RESULT_ROWS.
        """
        estimated = main_count * lookup_count
        if estimated > _FAIL_RESULT_ROWS:
            raise ComponentExecutionError(
                self.id,
                f"[{self.id}] {mode} join would produce ~{estimated:,} rows "
                f"(limit: {_FAIL_RESULT_ROWS:,}). Reduce lookup size.",
            )
        if estimated > _WARN_RESULT_ROWS:
            logger.warning(
                f"[{self.id}] {mode} join will produce ~{estimated:,} rows -- "
                f"consider using UNIQUE_MATCH or a lookup filter."
            )