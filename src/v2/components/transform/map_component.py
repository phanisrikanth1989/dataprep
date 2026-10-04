"""
Map Component for V2 Engine.

The core transformation component supporting:
- Expression-based column transformations
- Lookups (joins) with other data sources
- Multiple outputs (main, reject)
- Variable calculations
- Match modes (FIRST, LAST, UNIQUE, ALL) for lookups
- Cartesian (cross) joins
"""
import logging
from enum import Enum
from typing import Dict, List, Union

import polars as pl

from ..base import TransformComponent
from ..registry import REGISTRY
from ...expressions import compile_expression

logger = logging.getLogger(__name__)


class MatchMode(str, Enum):
    """Match mode for lookup joins."""
    FIRST = "first"    # Keep first matching row
    LAST = "last"      # Keep last matching row
    UNIQUE = "unique"  # Keep last matching row (Talend's default)
    ALL = "all"        # Keep all matches (may multiply rows)


@REGISTRY.register("map")
class Map(TransformComponent):
    """
    Transform data using expressions and lookups.

    This is the v2 equivalent of Talend's tMap component.

    Config options:
        outputs: list - Output definitions
            - name: str - Output name ("main", "reject", etc.)
            - filter: str - Optional filter expression
            - columns: list - Column definitions
                - name: str - Output column name
                - expression: str - Expression to compute value

        lookups: list - Lookup definitions
            - name: str - Lookup name (for referencing)
            - input: str - Input name to join with
            - keys: list - Join key pairs [{main: "col", lookup: "col"}]
                         - Empty list or omitted for cartesian join
            - join_type: str - "left", "inner", "outer", "right", "cross"
            - match_mode: str - "first", "last", "unique", "all" (default: "all")

        variables: list - Variable definitions (computed before outputs)
            - name: str - Variable name (referenced as var.name)
            - expression: str - Expression to compute

        lookup_reject_output: str - Optional name of an output that receives rows
            rejected by inner-join lookups (captured via anti-join).

        filter_reject_output: str - Optional name of an output that receives rows
            not matched by any output filter (combined negation of all filters).

        error_reject_output: str - Optional name of an output that receives rows
            with expression errors (requires die_on_error: false). Includes
            auto-generated _error_message column with column-level detail.

    Match Modes:
        - "first": Keep only the first matching row from lookup
        - "last": Keep only the last matching row from lookup
        - "unique": Keep only the last matching row (Talend's default)
        - "all": Keep all matches (may multiply rows)

    Example config:
        {
            "lookups": [
                {
                    "name": "customers",
                    "input": "lookup_customers",
                    "keys": [{"main": "customer_id", "lookup": "id"}],
                    "join_type": "left",
                    "match_mode": "first"
                }
            ],
            "outputs": [
                {
                    "name": "main",
                    "columns": [
                        {"name": "order_id", "expression": "order_id"},
                        {"name": "customer_name", "expression": "customers.name"},
                        {"name": "total", "expression": "quantity * unit_price"}
                    ]
                }
            ]
        }
    """

    def validate(self) -> List[str]:
        """Validate configuration."""
        errors = []

        outputs = self.config.get('outputs', [])
        if not outputs:
            errors.append("Map requires at least one output definition")

        for i, output in enumerate(outputs):
            if 'name' not in output:
                errors.append(f"Output {i} missing 'name'")
            if 'columns' not in output:
                errors.append(f"Output {i} missing 'columns'")

        output_names = {o.get('name') for o in outputs}

        lookup_reject = self.config.get('lookup_reject_output')
        if lookup_reject:
            if lookup_reject not in output_names:
                errors.append(f"lookup_reject_output '{lookup_reject}' not found in outputs")

        filter_reject = self.config.get('filter_reject_output')
        if filter_reject:
            if filter_reject not in output_names:
                errors.append(f"filter_reject_output '{filter_reject}' not found in outputs")

        error_reject = self.config.get('error_reject_output')
        if error_reject:
            if error_reject not in output_names:
                errors.append(f"error_reject_output '{error_reject}' not found in outputs")

        return errors

    def apply(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        """Execute the map transformation."""
        data = inputs.get("main")
        if data is None:
            return {}

        # Ensure we have a LazyFrame
        if isinstance(data, pl.DataFrame):
            data = data.lazy()

        # Step 1: Apply lookups (joins)
        data, lookup_rejects = self._apply_lookups(data, inputs)

        # Step 2: Compute variables
        data = self._compute_variables(data)

        # Step 3: Generate outputs
        return self._generate_outputs(data, lookup_rejects=lookup_rejects)

    def _apply_lookups(
        self,
        main_data: pl.LazyFrame,
        inputs: Dict[str, Union[pl.LazyFrame, pl.DataFrame]]
    ) -> tuple:
        """Apply lookup joins to main data.

        Returns:
            Tuple of (joined_data, lookup_rejects) where lookup_rejects is a
            list of LazyFrames containing rows rejected by inner-join lookups.
        """
        result = main_data
        lookup_rejects: List[pl.LazyFrame] = []

        for lookup_config in self.config.get('lookups', []):
            lookup_name = lookup_config['name']
            input_name = lookup_config.get('input', lookup_name)

            if input_name not in inputs:
                logger.warning(f"Lookup input not found: {input_name}")
                continue

            lookup_data = inputs[input_name]
            if isinstance(lookup_data, pl.DataFrame):
                lookup_data = lookup_data.lazy()

            # Build join keys
            keys = lookup_config.get('keys', [])
            join_type = lookup_config.get('join_type', 'left').lower()
            match_mode = MatchMode(lookup_config.get('match_mode', 'all').lower())

            # Handle cartesian (cross) join
            if join_type == 'cross' or not keys:
                result = self._apply_cross_join(result, lookup_data, lookup_name)
                logger.debug(f"Applied cartesian join: {lookup_name}")
                continue

            left_on = [k.get('main', k.get('left')) for k in keys]
            right_on = [k.get('lookup', k.get('right')) for k in keys]

            # Determine join type
            how_map = {
                'left': 'left',
                'inner': 'inner',
                'outer': 'full',
                'right': 'right',
            }
            how = how_map.get(join_type, 'left')

            # Prefix lookup columns to avoid conflicts (lazy schema introspection)
            lookup_cols = lookup_data.collect_schema().names()
            prefixed_lookup = lookup_data.select([
                pl.col(c).alias(f"{lookup_name}.{c}") if c not in right_on else pl.col(c)
                for c in lookup_cols
            ])

            # Apply match mode before join if FIRST or LAST
            if match_mode in (MatchMode.FIRST, MatchMode.LAST, MatchMode.UNIQUE):
                prefixed_lookup = self._apply_match_mode(
                    prefixed_lookup, right_on, lookup_name, match_mode
                )

            # Capture inner-join rejects via anti-join before performing the join
            if how == 'inner':
                lookup_reject_name = self.config.get('lookup_reject_output')
                if lookup_reject_name:
                    rejected = result.join(
                        prefixed_lookup,
                        left_on=left_on,
                        right_on=right_on,
                        how='anti',
                    )
                    lookup_rejects.append(rejected)

            # Perform join
            result = result.join(
                prefixed_lookup,
                left_on=left_on,
                right_on=right_on,
                how=how,
                suffix=f"_{lookup_name}",
            )

            logger.debug(f"Applied lookup join: {lookup_name} ({how}, match={match_mode.value})")

        return result, lookup_rejects

    def _apply_cross_join(
        self,
        main_data: pl.LazyFrame,
        lookup_data: pl.LazyFrame,
        lookup_name: str
    ) -> pl.LazyFrame:
        """Apply a cartesian (cross) join."""
        # Prefix all lookup columns (lazy schema introspection)
        lookup_cols = lookup_data.collect_schema().names()
        prefixed_lookup = lookup_data.select([
            pl.col(c).alias(f"{lookup_name}.{c}")
            for c in lookup_cols
        ])

        # Polars cross join
        return main_data.join(prefixed_lookup, how='cross')

    def _apply_match_mode(
        self,
        lookup_data: pl.LazyFrame,
        key_cols: List[str],
        lookup_name: str,
        match_mode: MatchMode
    ) -> pl.LazyFrame:
        """
        Apply match mode to deduplicate lookup data before join.

        For FIRST/LAST/UNIQUE, we deduplicate the lookup data on the join keys,
        keeping only the first or last occurrence. UNIQUE behaves like LAST.
        """
        if match_mode == MatchMode.ALL:
            return lookup_data

        # Get all columns for aggregation (lazy schema introspection)
        all_cols = lookup_data.collect_schema().names()
        non_key_cols = [c for c in all_cols if c not in key_cols]

        # Build aggregation expressions
        agg_exprs = []
        for col in non_key_cols:
            if match_mode == MatchMode.FIRST:
                agg_exprs.append(pl.col(col).first())
            else:  # LAST or UNIQUE
                agg_exprs.append(pl.col(col).last())

        # Group by keys and take first/last
        if agg_exprs:
            return lookup_data.group_by(key_cols).agg(agg_exprs)
        else:
            # Only key columns, just deduplicate
            return lookup_data.unique(
                subset=key_cols,
                keep='first' if match_mode == MatchMode.FIRST else 'last'
            )

    def _compute_variables(self, data: pl.LazyFrame) -> pl.LazyFrame:
        """Compute variable columns."""
        for var_config in self.config.get('variables', []):
            var_name = var_config['name']
            expression = var_config['expression']

            try:
                expr = compile_expression(expression, self.context, routine_registry=self.routine_registry)
                data = data.with_columns(expr.alias(f"var.{var_name}"))
                logger.debug(f"Computed variable: {var_name}")
            except Exception as e:
                logger.error(f"Failed to compute variable {var_name}: {e}")
                raise

        return data

    def _build_select_exprs(
        self,
        available_cols: set,
        columns: List[dict],
        safe: bool = False,
    ) -> tuple[list, list[str]]:
        """Build select expressions from column definitions.

        Args:
            available_cols: Set of column names available in the data.
            columns: List of column config dicts with 'name' and 'expression'.
            safe: If True, compile expressions with strict=False.

        Returns:
            Tuple of (select_exprs, computed_col_names) where computed_col_names
            lists columns that went through compile_expression (for error detection).
        """
        select_exprs = []
        computed_col_names = []
        for col_config in columns:
            col_name = col_config['name']
            expression = col_config.get('expression', col_name)
            if expression in available_cols:
                select_exprs.append(pl.col(expression).alias(col_name))
            elif expression.isidentifier():
                select_exprs.append(pl.col(expression).alias(col_name))
            else:
                expr = compile_expression(expression, self.context, routine_registry=self.routine_registry, safe=safe)
                select_exprs.append(expr.alias(col_name))
                if safe:
                    computed_col_names.append(col_name)
        return select_exprs, computed_col_names

    def _generate_outputs(self, data: pl.LazyFrame, lookup_rejects: List[pl.LazyFrame] = None) -> Dict[str, pl.LazyFrame]:
        """Generate output data for each output definition.

        When ``error_reject_output`` is set and ``die_on_error`` is ``False``,
        expressions are compiled in *safe* mode (``strict=False``). Rows where
        any computed expression produced ``null`` are aggregated from all
        outputs and routed to the named error reject output with an
        ``_error_message`` column containing column-level detail.
        """
        outputs = {}
        die_on_error = self.config.get("die_on_error", True)
        safe = not die_on_error

        # Get available column names for direct reference checks (lazy schema introspection)
        available_cols = set(data.collect_schema().names())

        # Collect compiled filter expressions for filter_reject_output handling
        output_filter_exprs: List[pl.Expr] = []

        # Collect error reject rows from all outputs
        all_error_rejects: List[pl.LazyFrame] = []
        error_reject_name = self.config.get('error_reject_output')

        for output_config in self.config.get('outputs', []):
            output_name = output_config['name']

            # Skip reject-target outputs -- they are handled separately
            if output_name == self.config.get('lookup_reject_output'):
                continue
            if output_name == self.config.get('filter_reject_output'):
                continue
            if output_name == self.config.get('error_reject_output'):
                continue

            # Apply filter if specified
            filtered_data = data
            if 'filter' in output_config:
                filter_expr = compile_expression(output_config['filter'], self.context, routine_registry=self.routine_registry)
                filtered_data = data.filter(filter_expr)
                output_filter_exprs.append(filter_expr)

            # Build output columns
            columns = output_config.get('columns', [])
            if not columns:
                # No columns specified - pass through all
                outputs[output_name] = filtered_data
                continue

            select_exprs, computed_col_names = self._build_select_exprs(available_cols, columns, safe=safe)

            result = filtered_data.select(select_exprs)

            # If safe mode, generate reject output for rows where computed columns have nulls
            if safe and computed_col_names and error_reject_name:
                # Build a null-check: any computed column is null
                null_checks = [pl.col(c).is_null() for c in computed_col_names]
                has_error = null_checks[0]
                for nc in null_checks[1:]:
                    has_error = has_error | nc

                # Build error message with column-level detail
                error_msg = pl.concat_str(
                    [pl.lit("Expression produced null in column(s): ")] +
                    [pl.when(pl.col(c).is_null()).then(pl.lit(f"'{c}', ")).otherwise(pl.lit("")) for c in computed_col_names],
                )

                reject_rows = result.filter(has_error).with_columns(
                    error_msg.alias("_error_message")
                )
                all_error_rejects.append(reject_rows)

                # Filter to only good rows
                outputs[output_name] = result.filter(~has_error)
            else:
                outputs[output_name] = result

            logger.debug(f"Generated output: {output_name} with {len(columns)} columns")

        # Handle error reject output
        if error_reject_name and all_error_rejects:
            # Normalize schemas before concat -- different outputs may have
            # different column sets, so pad each frame with null columns
            all_cols: Dict[str, pl.DataType] = {}
            for lf in all_error_rejects:
                for name, dtype in lf.collect_schema().items():
                    if name not in all_cols:
                        all_cols[name] = dtype
            col_order = list(all_cols.keys())
            padded = []
            for lf in all_error_rejects:
                existing = set(lf.collect_schema().names())
                missing = [
                    pl.lit(None).cast(dtype).alias(name)
                    for name, dtype in all_cols.items()
                    if name not in existing
                ]
                frame = lf.with_columns(missing) if missing else lf
                padded.append(frame.select(col_order))
            combined_errors = pl.concat(padded, how="vertical_relaxed")
            error_config = next(
                (o for o in self.config.get('outputs', []) if o['name'] == error_reject_name),
                None
            )
            if error_config:
                cols = error_config.get('columns', [])
                if cols:
                    error_available = set(combined_errors.collect_schema().names())
                    select_exprs, _ = self._build_select_exprs(error_available, cols, safe=safe)
                    outputs[error_reject_name] = combined_errors.select(select_exprs)
                else:
                    outputs[error_reject_name] = combined_errors
        elif error_reject_name:
            # No errors but output expected -- produce empty frame
            if error_reject_name not in outputs:
                outputs[error_reject_name] = pl.LazyFrame()

        # Handle filter reject output
        filter_reject_name = self.config.get('filter_reject_output')
        if filter_reject_name:
            reject_config = next(
                (o for o in self.config.get('outputs', []) if o['name'] == filter_reject_name),
                None
            )
            if reject_config:
                # Build combined negation: NOT(filter_1 OR filter_2 OR ...)
                if output_filter_exprs:
                    combined_match = output_filter_exprs[0]
                    for fe in output_filter_exprs[1:]:
                        combined_match = combined_match | fe
                    unmatched_data = data.filter(~combined_match)
                else:
                    # No outputs have filters -- no rows can be unmatched
                    unmatched_data = data.filter(pl.lit(False))

                cols = reject_config.get('columns', [])
                if cols:
                    select_exprs, _ = self._build_select_exprs(available_cols, cols, safe=safe)
                    outputs[filter_reject_name] = unmatched_data.select(select_exprs)
                else:
                    outputs[filter_reject_name] = unmatched_data

        # Handle lookup reject output
        lookup_reject_name = self.config.get('lookup_reject_output')
        if lookup_rejects is None:
            lookup_rejects = []
        if lookup_reject_name and lookup_rejects:
            # vertical_relaxed handles schema differences when sequential inner joins
            # produce rejects with progressively wider schemas
            combined = pl.concat(lookup_rejects, how="vertical_relaxed")
            # Find the reject output config
            reject_config = next(
                (o for o in self.config.get('outputs', []) if o['name'] == lookup_reject_name),
                None
            )
            if reject_config:
                cols = reject_config.get('columns', [])
                if cols:
                    reject_available = set(combined.collect_schema().names())
                    select_exprs, _ = self._build_select_exprs(reject_available, cols)
                    outputs[lookup_reject_name] = combined.select(select_exprs)
                else:
                    outputs[lookup_reject_name] = combined
        elif lookup_reject_name:
            # No rejects but output expected -- produce empty frame
            if lookup_reject_name not in outputs:
                outputs[lookup_reject_name] = pl.LazyFrame()

        return outputs
