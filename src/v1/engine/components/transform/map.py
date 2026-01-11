"""
tMap component - Data transformation and lookup/join operations

This component mimics Talend's tMap functionality:
- Multiple inputs (main + lookups)
- Multiple outputs with filters
- Variable definitions
- Complex expression evaluation
- Join operations between inputs
- Optimized execution: Pandas for joins, Java for expressions
"""
from typing import Any, Dict, Optional, List, Set
import pandas as pd
import logging
import re
from ...base_component import BaseComponent, ComponentStatus

logger = logging.getLogger(__name__)


class Map(BaseComponent):
    """
    tMap component for data transformation with lookups and multiple outputs.

    Execution Strategy (Optimized Hybrid):
    1. Filter lookup tables (if filters present)
    2. Pre-evaluate complex Java expressions in ONE batch call
    3. Extract simple column references directly (no Java)
    4. Use pandas for fast bulk joins with matching mode support
    5. Evaluate variables and output expressions via Java
    6. Route to outputs based on filters

    Config parameters:
    - inputs: Dict with 'main' and 'lookups' list
    - variables: List of variable definitions
    - outputs: List of output configurations

    Matching Modes (per lookup):
    - UNIQUE_MATCH: Keep first occurrence (same as FIRST_MATCH)
    - FIRST_MATCH: Keep first matching row from lookup
    - LAST_MATCH: Keep last matching row from lookup
    - ALL_MATCHES: Keep all matches (default pandas behavior)
    """

    # Pattern to detect simple column references: table.column
    SIMPLE_COLUMN_PATTERN = re.compile(r'^([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)$')

    def execute(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Override execute() to skip base class's Java expression resolution.

        tMap expressions (variables, outputs) reference row data and must be evaluated
        row-by-row during _process(), not during config resolution.
        """
        import time
        from ...base_component import ComponentStatus

        self.status = ComponentStatus.RUNNING
        start_time = time.time()

        try:
            # Skip Java expression resolution - tMap handles this internally
            # Just resolve context variables (${context.var})
            if getattr(self, "context_manager", None):
                self.config = self.context_manager.resolve_dict(self.config)

            # Execute processing
            result = self._process(input_data)

            # Update statistics
            self.stats["EXECUTION_TIME"] = time.time() - start_time
            self._update_global_map()

            self.status = ComponentStatus.SUCCESS

            # Add stats to result
            result["stats"] = self.stats.copy()
        
            return result

        except Exception as e:
            self.status = ComponentStatus.ERROR
            self.error_message = str(e)
            self.stats["EXECUTION_TIME"] = time.time() - start_time
            self._update_global_map()
        
            logger.exception("Component %s failed", getattr(self, "id", "map"))
            raise

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Execute tMap transformation

        Args:
            input_data: Can be a single DataFrame or dict of {flow_name: DataFrame}
                        depending on whether component has single or multiple inputs
        """
        # Store input_data so _get_input_dataframes() can access it
        self._current_input_data = input_data

        # Get all input data from component inputs
        inputs = self._get_input_dataframes()

        if not inputs:
            logger.warning("Component %s: No input data", getattr(self, "id", "map"))
            return self._create_empty_outputs()

        # Get configuration
        config = self.config
        main_config = config["inputs"]["main"]
        lookups_config = config["inputs"].get("lookups", [])
        variables_config = config.get("variables", [])
        outputs_config = config["outputs"]

        # ============================================================
        # PHASE 1: FILTER LOOKUPS
        # ============================================================
        
        inputs = self._filter_lookups(inputs, lookups_config)

        # ============================================================
        # PHASE 2: FILTER MAIN INPUT & PREPARE JOIN KEYS
        # ============================================================
        
        main_name = main_config["name"]
        main_df = inputs.get(main_name)

        if main_df is None or main_df.empty:
            logger.warning("Component %s: Main input '%s' is empty", getattr(self, "id", "map"), main_name)
            return self._create_empty_outputs()

        logger.info("Component %s: Processing %s main rows", getattr(self, "id", "map"), len(main_df))

        # 2a. Apply main input filter if present
        if main_config.get("activate_filter") and main_config.get("filter"):
            filter_expr = self._strip_java_marker(main_config["filter"])

            # Check if it's a simple column reference
            if self._is_simple_column_ref(filter_expr):
                table, column = self._parse_column_ref(filter_expr)
                # Extract column value directly
                if table in main_df.columns:
                    filter_mask = main_df[table].values
                elif f"{table}.{column}" in main_df.columns:
                    filter_mask = main_df[f"{table}.{column}"].values
                elif column in main_df.columns:
                    filter_mask = main_df[column].values
                else:
                    logger.warning(f"Component {self.id}: Filter column '{table}.{column}' not found in main input")
                    filter_mask = None

                if filter_mask is not None:
                    main_df = main_df[pd.Series(filter_mask).fillna(False).values].copy()
                    logger.info(f"Component {self.id}: After filter: {len(main_df)} rows")
            else:
                # Complex expression - use Java
                filter_results = self._batch_evaluate_expressions(
                    main_df,
                    {"__main_filter__": filter_expr},
                    main_name,
                    [],  # No lookups joined yet during main filter phase
                )
                if "__main_filter__" in filter_results:
                    filter_mask = filter_results["__main_filter__"]
                    # Ensure mask is boolean and has no NA/NaN - AT17854
                    filter_mask = pd.Series(filter_mask).fillna(False).values
                    main_df = main_df[filter_mask].copy()
                    logger.info("Component %s: After filter: %s rows", getattr(self, "id", "map"), len(main_df))

        # ============================================================
        # PHASE 3: LOOKUPS - Use pandas for fast bulk joins
        # ============================================================
        
        lookup_result = self._perform_lookups(main_df, inputs, lookups_config, main_name)
        joined_df = lookup_result["joined"]
        inner_join_rejects = lookup_result["inner_join_rejects"]

        if joined_df.empty and inner_join_rejects.empty:
            logger.warning("Component %s: No rows after lookups", getattr(self, "id", "map"))
            return self._create_empty_outputs()

        logger.info(f"Component {self.id}: After lookups: {len(joined_df)} rows, {len(joined_df.columns)} columns")

        # ============================================================
        # PHASE 4: VARIABLES & OUTPUTS - Java expression evaluation
        # ============================================================
        #
        #
        #
        output_dfs = self._evaluate_and_route_outputs(
            joined_df,
            variables_config,
            outputs_config,
            inner_join_rejects=inner_join_rejects,
        )

        # Update statistics
        total_output_rows = sum(len(df) for df in output_dfs.values())
        self._update_stats(
            rows_read=len(main_df), 
            rows_ok=total_output_rows
        )
        
        logger.info(f"Component {self.id}: Produced {len(output_dfs)} outputs with {total_output_rows} total rows")

        # Debug: print first 5 rows of each output
        for output_name, output_df in output_dfs.items():
            logger.debug(f"Component {self.id}: Output '{output_name}' first 5 rows:\n{output_df.head(5)}")
            logger.debug(f"Component {self.id}: Output '{output_name}' columns: {output_df.columns.tolist()}")

        return output_dfs

    def _strip_java_marker(self, expression: str) -> str:
        """Remove {{java}} marker if present"""
        if expression.startswith("{{java}}"):
            return expression[8:]
        return expression

    def _is_simple_column_ref(self, expression: str) -> bool:
        """Check if expression is a simple column reference (table.column)"""
        return bool(self.SIMPLE_COLUMN_PATTERN.match(expression.strip()))

    def _parse_column_ref(self, expression: str) -> tuple:
        """Parse simple column reference into (table, column)"""
        match = self.SIMPLE_COLUMN_PATTERN.match(expression.strip())
        if match:
            return match.group(1), match.group(2)
        return None, None

    def _is_context_only_expression(self, expression: str) -> bool:
        """
        Check if expression contains ONLY context/globalMap references (no row data)

        Context-only expressions trigger cartesian joins since they don't depend on row values.

        Examples:
            "context.region + ' ' + context.year" -> True (cartesian join)
            "main.customer_id" -> False (normal join)
            "context.year + orders.amount" -> False (has row reference, normal join)
            "1 == 1" -> True (constant, cartesian join)

        Returns:
            True if expression has NO row references (table.column pattern)
        """
        # Strip Java marker if present
        expr = self._strip_java_marker(expression).strip()

        # Check for any row references (table.column pattern)
        # If ANY found, it's NOT context-only
        row_ref_pattern = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)\b")
        matches = row_ref_pattern.findall(expr)

        # Filter out context.* and globalMap.* references
        row_references = [
            match for match in matches
            if match[0] not in ["context", "globalMap"]
        ]

        # If no row references found, it's context-only
        return len(row_references) == 0

    def _filter_lookups(
        self,
        inputs: Dict[str, pd.DataFrame],
        lookups_config: List[Dict],
    ) -> Dict[str, pd.DataFrame]:
        """
        Filter lookup tables before joining.

        Args:
            inputs: All input DataFrames
            lookups_config: Lookup configurations

        Returns:
            Filtered inputs dict
        """
        filtered_inputs = inputs.copy()

        for lookup_config in lookups_config:
            lookup_name = lookup_config["name"]
            lookup_df = filtered_inputs.get(lookup_name)

            if lookup_df is None or lookup_df.empty:
                continue

            # Check if lookup has a filter
            if not lookup_config.get("activate_filter") or not lookup_config.get("filter"):
                continue

            filter_expr = self._strip_java_marker(lookup_config["filter"])

            logger.info(f"Component {getattr(self, 'id', 'map')}: Filtering lookup '{lookup_name}'")

            # Evaluate filter on lookup table
            if self._is_simple_column_ref(filter_expr):
                # Simple column reference - use pandas directly
                table, column = self._parse_column_ref(filter_expr)
                if column in lookup_df.columns:
                    filtered_inputs[lookup_name] = lookup_df[lookup_df[column] == True].copy()
                else:
                    logger.warning(f"Component {self.id}: Filter column '{column}' not found in lookup '{lookup_name}'")
            else:
                #Complex expression - use Java
                filter_results = self._batch_evaluate_expressions(
                    lookup_df,
                    {'filter': filter_expr},
                    lookup_name,
                    [],  # No lookups joined during filtering
                )
                if 'filter' in filter_results:
                    filter__mask = filter_results['filter']
                    #Ensure mask is boolean and has no NA/NaN - AT17854
                    filter_mask = pd.Series(filter__mask).fillna(False).values
                    filtered_inputs[lookup_name] = lookup_df[filter_mask].copy()
                    logger.info(f"Component {self.id}: Lookup '{lookup_name}' filtered: {len(lookup_df)} ->{len(filtered_inputs[lookup_name])} rows")

        return filtered_inputs
    
    def _get_input_dataframes(self) -> Dict[str, pd.DataFrame]:
        """
        Get input DataFrames from component inputs.

        The engine sets self._current_input_data during execute() call
        This is either:
        - A single DataFrame (for single input)
        - A dict of {flow_name: DataFrame} (for multiple inputs)

        Returns:
            Dict of {flow_name: DataFrame} for all inputs
        """
        input_data = getattr(self, "_current_input_data", None)

        if input_data is None:
            return {}

        # If already a dict, return as is
        if isinstance(input_data, dict):
            return input_data 
        
        #If single DataFrame, map to first input name
        if isinstance(self._current_input_data, pd.DataFrame):
        #Get first input name from config
            main_name = self.config["inputs"]["main"]["name"]
            return {main_name: input_data}

        return {}
        
    def _batch_evaluate_expressions(
        self,
        df: pd.DataFrame,
        expressions: Dict[str, str],
        main_table_name: str,
        lookup_table_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Batch evaluate multiple expressions in one Java call

        Args:
            df: DataFrame to evaluate expressions on
            expressions: Dict of {expr_id: expression_string}
            main_table_name: Name of the main table for expression context
            lookup_table_names: List of lookup table names already joined (for chained lookups)

        Returns:
            Dict of {expr_id: result_array}
        """
        if not expressions:
            return {}

        # Get Java bridge
        if not getattr(self, "context_manager", None) or not self.context_manager.is_java_enabled():
            raise RuntimeError(
                f"Component {getattr(self, 'id', 'map')}: Java execution is not available. "
                "tMap requires Java bridge for expression evaluation."
            )

        java_bridge = self.context_manager.get_java_bridge()

        try:
            # Sync context to bridge
            if getattr(self, "context_manager", None):
                context_all = self.context_manager.get_all()
                # Flatten nested context structure
                flattened_context: Dict[str, Any] = {}
                for context_name, context_vars in context_all.items():
                    if isinstance(context_vars, dict):
                        for var_name, var_info in context_vars.items():
                            if isinstance(var_info, dict) and "value" in var_info:
                                flattened_context[var_name] = var_info["value"]
                            else:
                                flattened_context[var_name] = var_info
                    else:
                        flattened_context[context_name] = context_vars

                for key, value in flattened_context.items():
                    java_bridge.set_context(key, value)

            if getattr(self, "global_map", None):
                for key, value in self.global_map.get_all().items():
                    java_bridge.set_global_map(key, value)

            # Call Java bridge to evaluate all expressions at once
            results = java_bridge.execute_tmap_preprocessing(
                df=df,
                expressions=expressions,
                main_table_name=main_table_name,
                lookup_table_names=lookup_table_names or [],
            )

            return results

        except Exception as e:
            logger.error("Component %s: Batch expression evaluation failed: %s", getattr(self, "id", "map"), e)
            raise

    def _perform_lookups(
        self,
        main_df: pd.DataFrame,
        inputs: Dict[str, pd.DataFrame],
        lookups_config: List[Dict],
        main_name: str,
    ) -> Dict[str, pd.DataFrame]:
        """
        Perform all lookup operations using pandas merge

        Supports:
        - Sequential lookup evaluation (Lookup2 can reference Lookup1's columns)
        - Cartesian joins (context-only expressions)
        - Normal joins (row-based expressions)

        Args:
            main_df: Main input DataFrame
            inputs: All input DataFrames(filtered)
            lookups_config: List of lookup configurations
            main_name: Name of the main input table

        Returns:
            Dict with 'joined' DataFrame and 'inner_join_rejects' DataFrame (if any)
        """
        joined_df = main_df.copy()
        joined_lookups: List[str] = []
        inner_join_rejects = pd.DataFrame()

        for lookup_config in lookups_config:
            lookup_name = lookup_config["name"]
            lookup_df = inputs.get(lookup_name)

            if lookup_df is None:
                logger.warning(f"Component {self.id}: Lookup table '{lookup_name}' not found")
                continue

            if lookup_df.empty:
                logger.warning(f"Component {self.id}: Lookup table '{lookup_name}' is empty after filtering")
                continue

            join_keys = lookup_config["join_keys"]

            # Detect if this is a cartesian join (all join expressions are context-only)
            is_cartesian = all(
                self._is_context_only_expression(jk["expression"]) 
                for jk in join_keys
                )

            if is_cartesian:
                # CARTESIAN JOIN PATH
                joined_df = self._perform_cartesian_join(
                    joined_df, lookup_df, lookup_name, join_keys
                )
            else:
                # NORMAL JOIN PATH (with chained lookup support)
                prev_df = joined_df.copy()
                joined_df = self._perform_normal_join(
                    joined_df, lookup_df, lookup_name, join_keys,
                    lookup_config, main_name, joined_lookups
                )

                if lookup_config.get("join_mode", "LEFT_OUTER_JOIN") == "INNER_JOIN":
                    # Find unmatched main rows
                    merged = prev_df.merge(
                        joined_df,
                        how="left",
                        indicator=True,
                    )
                    unmatched = merged[merged["_merge"] == "left_only"].drop(columns=["_merge"])
                    if not unmatched.empty:
                        inner_join_rejects = pd.concat([inner_join_rejects, unmatched], ignore_index=True)

            # Track this lookup as joined
            joined_lookups.append(lookup_name)

        return {"joined": joined_df, "inner_join_rejects": inner_join_rejects}

    def _perform_cartesian_join(
        self,
        joined_df: pd.DataFrame,
        lookup_df: pd.DataFrame,
        lookup_name: str,
        join_keys: List[Dict],
    ) -> pd.DataFrame:
        """
        Perform cartesian join with context-based filtering.

        Example:
            Join expression: context.region + " " + context.year
            Lookup column: region_year

        Steps:
            1. Evaluate expression (e.g., "WEST 2024")
            2. Filter lookup: WHERE region_year = "WEST 2024"
            3. Cross join: joined_df X filtered_lookup
        
        Args:
            joined_df: Current accumulated DataFrame
            lookup_df: Lookup table to join
            lookup_name: Name of the lookup table
            join_keys: Join key configurations

        Returns:
            DataFrame with  cartesian join applied
        """
        logger.info(f"Component {self.id}: Performing CARTESIAN join with lookup '{lookup_name}'")

        # Evaluate each context-only expression and filter lookup
        filtered_lookup = lookup_df.copy()

        for join_key in join_keys:
            expression = self._strip_java_marker(join_key["expression"])
            lookup_col = join_key["lookup_column"]

            # Evaluate context expression ONCE (not per-row)
            if self.context_manager and self.context_manager.is_java_enabled():
                java_bridge = self.context_manager.get_java_bridge()   

                #Sync context
                if self.context_manager:
                    for key, value in self.context_manager.get_all().items():
                        if isinstance(value, dict):
                            for var_name, var_info in value.items():
                                if isinstance(var_info, dict) and "value" in var_info:
                                    java_bridge.set_context(var_name, var_info["value"])

            # Evaluate expression
                try:
                    filter_value = java_bridge.execute_one_time_expression(expression)
                    logger.info(f"Component {self.id}: Cartesian filter  {lookup_col} ={filter_value}")

                    # Filter lookup table
                    filtered_lookup = filtered_lookup[filtered_lookup[lookup_col] == filter_value]
                except Exception as e:
                    logger.error(f"Component {self.id}: Failed to evaluate cartesian expression '{expression}': {e}")
                    # Continue with unfiltered lookup
            else:
                logger.warning(f"Component {self.id}: Java bridge not available for cartesian expression")

        if filtered_lookup.empty:
            logger.warning(f"Component {self.id}: Lookup '{lookup_name}' is empty after cartesian filter")
            return joined_df

        # Prefix ALL lookup columns with "lookup_name." to match normal join behavior
        lookup_df_prefixed = filtered_lookup.copy()
        lookup_df_prefixed.columns = [f"{lookup_name}.{col}" for col in filtered_lookup.columns]

        # Perform CROSS JOIN
        logger.info(f"Component {self.id}: Cartesian join: len(joined_df) rows X {len(joined_df)} rows ( all lookup columns prefixed)")

        # pandas cross join (available in pandas >= 1.2.0)
        result_df = joined_df.merge(lookup_df_prefixed, how="cross")

        logger.info(f"Component {self.id}: After cartesian join: {len(result_df)} rows"
                    )
        return result_df

    def _perform_normal_join(
        self,
        joined_df: pd.DataFrame,
        lookup_df: pd.DataFrame,
        lookup_name: str,
        join_keys: List[Dict],
        lookup_config: Dict,
        main_name: str,
        joined_lookups: List[str],
    ) -> pd.DataFrame:
        """
        Perform normal join with sequential evaluation.

        Supports chained lookups where Lookup2 can reference Lookup1's columns.
        Evaluates join keys against CURRENT joined_df (not just main_df).

        Args:
            joined_df: Current accumulated DataFrame( including previous lookups )
            lookup_df: Lookup table to join
            lookup_name: Name of the lookup table
            join_keys: Join key configurations
            lookup_config: Full lookup configuration (for join/matching mode)
            main_name: Name of the main input table
            joined_lookups: List of lookup names already joined (for expression context)

        Returns:
            DataFrame with lookup joined (ALL lookup columns prefixed with "lookup_name.")
        """
        # Evaluate join key expressions against CURRENT joined_df
        simple_expressions = {}
        complex_expressions = {}

        for idx, join_key in enumerate(join_keys):
            expr_id = f"__join_{lookup_name}_{idx}__"  # String key for consistency
            expression = self._strip_java_marker(join_key["expression"])

            if self._is_simple_column_ref(expression):
                simple_expressions[expr_id] = self._parse_column_ref(expression)
            else:
                complex_expressions[expr_id] = expression

        # Extract simple column values from joined_df
        join_key_values = {}

        for expr_id, (table, column) in simple_expressions.items():
            # Try multiple column name formats to find the right one
            found = False

            # Format 1: table.column (e.g., "orders.customer_id")
            if f"{table}.{column}" in joined_df.columns:
                join_key_values[expr_id] = joined_df[f"{table}.{column}"].values
                found = True
            # Format 2: column only (e.g., "customer_id")
            elif column in joined_df.columns:
                join_key_values[expr_id] = joined_df[column].values
                found = True
            # Format 3: table only (for boolean columns, etc.)
            elif table and table in joined_df.columns:
                join_key_values[expr_id] = joined_df[table].values
                found = True
            # Format 4: With suffix from previous lookup (e.g., "customer_id_customers")
            else:
                # Try to find column with any suffix
                    matching_cols = [col for col in joined_df.columns if col.startswith(column)]
                    if matching_cols:
                        join_key_values[expr_id] = joined_df[matching_cols[0]].values
                        logger.debug(f"Component {self.id}: Using column '{matching_cols[0]}' for join key")
                        found = True

            if not found:
                logger.warning(f"Component {self.id}: Column '{table}.{column}' not found in joined_df")

        # Evaluate complex expressions via Java
        if complex_expressions:
            logger.info(f"Component {self.id}: Evaluating {len(complex_expressions)} complex join expressions for lookup '{lookup_name}'")
            complex_results = self._batch_evaluate_expressions(
                joined_df,
                complex_expressions,
                main_name,
                joined_lookups,  # Pass list of Already joined lookups for expression context
            )
            join_key_values.update(complex_results)

        # Build join columns
        left_on = []
        right_on = []

        for idx, join_key in enumerate(join_keys):
            expr_id = f"__join_{lookup_name}_{idx}__" #Match expr_id used earlier
            lookup_col = join_key["lookup_column"]

            # Add evaluated join key as temp column
            temp_col = f"__join_{lookup_name}_{idx}"
            if expr_id in join_key_values:
                joined_df[temp_col] = join_key_values[expr_id]
                left_on.append(temp_col)
                right_on.append(lookup_col)
            else:
                logger.warning(f"Component {self.id}: Join key {idx} not evaluated for '{lookup_name}'")

        if not left_on:
            logger.warning(f"Component {self.id}: No join keys for lookup '{lookup_name}'")
            return joined_df

        # Apply matching mode BEFORE join by deduplicating lookup data
        matching_mode = lookup_config.get("matching_mode", "UNIQUE_MATCH")
        deduplicated_lookup_df = self._apply_matching_mode(
            lookup_df,
            right_on,  # Use original column names (before prefixing)
            matching_mode,
            lookup_name,
        )

        # Prefix ALL lookup columns with "lookup_name." to avoid conflicts
        lookup_df_prefixed = deduplicated_lookup_df.copy()
        lookup_df_prefixed.columns = [f"{lookup_name}.{col}" for col in deduplicated_lookup_df.columns]

        # Update right_on keys to use prefixed names
        right_on_prefixed = [f"{lookup_name}.{col}" for col in right_on]

        # JOIN MODE LOGIC ADDED HERE
        join_mode = lookup_config.get("join_mode", "LEFT_OUTER_JOIN")
        if join_mode == 'INNER_JOIN':
            how = 'inner'
        else:
            how = 'left'

        logger.info(f"Component {self.id}: Joining with lookup '{lookup_name}' on {len(left_on)} key(s) (all lookup columns prefixed), join_mode={join_mode}")

        # Perform pandas JOIN
        result_df = joined_df.merge(
            lookup_df_prefixed,
            left_on=left_on,
            right_on=right_on_prefixed,
            how=how,
        )

        # Cleanup temp join columns
        result_df.drop(columns=left_on, inplace=True)

        return result_df

    def _apply_matching_mode(
        self,
        lookup_df: pd.DataFrame,
        join_keys: List[str],
        matching_mode: str,
        lookup_name: str,
    ) -> pd.DataFrame:
        """
        Apply matching mode to lookup DataFrame by deduplicating on join keys

        Args:
            lookup_df: Lookup DataFrame to deduplicate
            join_keys: List of column names to use as join keys(without prefixes)
            matching_mode: 'UNIQUE_MATCH', 'FIRST_MATCH', 'LAST_MATCH', or 'ALL_MATCHES'
            lookup_name: Name of the lookup (for logging)
        
        Returns:
            Deduplicated DataFrame based on matching mode
        """
        if matching_mode == "ALL_MATCHES" or not join_keys:
            # No deduplication needed
            return lookup_df.copy()

        original_count = len(lookup_df)

        if matching_mode in ("UNIQUE_MATCH", "FIRST_MATCH"):
            # Keep first occurrence of each join key combination
            deduplicated_df = lookup_df.drop_duplicates(subset=join_keys, keep="first")
        elif matching_mode == "LAST_MATCH":
            # Keep last occurrence of each join key combination
            deduplicated_df = lookup_df.drop_duplicates(subset=join_keys, keep="last")
        else:
            # Unknown matching mode - default to ALL_MATCHES
            logger.warning(f"Component {self.id}: Unknown matching_mode '{matching_mode}' for lookup '{lookup_name}', defaulting to ALL_MATCHES")
            return lookup_df.copy()

        final_count = len(deduplicated_df)
        if final_count < original_count:
            logger.debug(f"Component {self.id}: Applied {matching_mode} to lookup '{lookup_name}': {original_count} -> {final_count} rows")

        return deduplicated_df

    def _evaluate_and_route_outputs(
        self,
        joined_df: pd.DataFrame,
        variables_config: List[Dict],
        outputs_config: List[Dict],
        inner_join_rejects: Optional[pd.DataFrame] = None,
    ) -> Dict[str, pd.DataFrame]:
        """
        Evaluate variables and outputs (typically via Java) and route rows.

        Use compiled java scripts for high performance parallel execution.
        """
        output_dfs = self._evaluate_outputs_java(joined_df, variables_config, outputs_config)

        # Handle inner join rejects for outputs with inner_join_reject: true
        if inner_join_rejects is not None and not inner_join_rejects.empty:
            for output in outputs_config:
                if output.get('inner_join_reject'):
                    output_name = output['name']
                    # Apply output filter if present
                    filtered_rejects = inner_join_rejects
                    filter_expr = output.get('filter')
                    activate_filter = output.get('activate_filter', False)
                    if activate_filter and filter_expr:
                        # Remove {{java}} marker if present
                        expr = self._strip_java_marker(filter_expr)
                        # Evaluate filter using Java bridge
                        filter_results = self._batch_evaluate_expressions(
                            filtered_rejects,
                            {'__inner_join_reject_filter__': expr},
                            self.config['inputs']['main']['name'],
                            []
                        )
                        mask = filter_results.get('__inner_join_reject_filter__')
                    if mask is not None:
                        filtered_rejects = filtered_rejects[mask].copy()
                    output_dfs[output_name] = filtered_rejects.copy()

        return output_dfs

    def _evaluate_outputs_java(
        self,
        joined_df: pd.DataFrame,
        variables_config: List[Dict],
        outputs_config: List[Dict]
    ) -> Dict[str, pd.DataFrame]:
        """
        OPTIMIZED: Evaluate variables and outputs using compiled script

        Generates and compiles entire tMap logic once, then executes in parallel.
        Achieves similar performance to tJavaRow (~189k rows/sec).
        """

        if not self.context_manager or not self.context_manager.is_java_enabled():
            raise RuntimeError(
                f"Component {self.id}: Java execution is not available for output evaluation")

        java_bridge = self.context_manager.get_java_bridge()

        try:
            logger.info(f"Component {self.id}: Evaluating {len(variables_config)} variables and {len(outputs_config)} outputs")

            # Sync context and globalMap to Java bridge
            flattened_context = {}
            if self.context_manager:
                context_all = self.context_manager.get_all()
                for context_name, context_vars in context_all.items():
                    if isinstance(context_vars, dict):
                        for var_name, var_info in context_vars.items():
                            if isinstance(var_info, dict) and 'value' in var_info:
                                flattened_context[var_name] = var_info['value']
                            else:
                                flattened_context[var_name] = var_info
                    else:
                        flattened_context[context_name] = context_vars

                for key, value in flattened_context.items():
                    java_bridge.set_context(key, value)

            if self.global_map:
                for key, value in self.global_map.get_all().items():
                    java_bridge.set_global_map(key, value)

            # Get main input name and lookup names
            main_name = self.config['inputs']['main']['name']
            lookup_names = [lookup['name'] for lookup in self.config['inputs'].get('lookups', [])]
        
            # Get die_on_error configuration (default: true for safety)
            die_on_error = self.config.get('die_on_error', True)

            # Generate compiled script
            script = self._generate_tmap_compiled_script(
                variables_config,
                outputs_config,
                main_name,
                lookup_names,
                die_on_error
            )

            # Prepare output schemas and types
            output_schemas = {}
            output_types = {}
            for output in outputs_config:
                output_name = output['name']
                col_names = [col['name'] for col in output['columns']]
                output_schemas[output_name] = col_names

                for col in output['columns']:
                    type_key = f"{output_name}_{col['name']}"
                    output_types[type_key] = col.get('type', 'id_String')

            # STEP 1: Compile script ONCE
            java_bridge.compile_tmap_script(
                component_id=self.id,
                java_script=script,
                output_schemas=output_schemas,
                output_types=output_types,
                main_table_name=main_name,
                lookup_names=lookup_names
                )

            # STEP 2: Execute on chunks
            output_dfs = java_bridge.execute_compiled_tmap_chunked(
            component_id=self.id,
            df=joined_df,
            chunk_size=50000
            )

            # Handle error tracking if die_on_error=false
            if not die_on_error and '__errors__' in output_dfs:
                error_info = output_dfs.pop('__errors__')
                error_count = error_info.get('count', 0)

                #Store error count in context/globalMap
                if self.global_map:
                    self.global_map.put(f"{self.id}_ERROR_COUNT", error_count)

                if error_count > 0:
                    logger.warning(f"Component {self.id}: {error_count} error rows routed to reject")

            # Sync context and globalMap back from Java to Python
            java_bridge._sync_from_java()

            # Update contextmanager with synced context values
            if self.context_manager:
                for key, value in java_bridge.context.items():
                    self.context_manager.set(key, value)

            # Update globalMap with synced globalMap values
            if self.global_map:
                for key, value in java_bridge.global_map.items():
                    self.global_map.put(key, value)

            return output_dfs

        except Exception as e:
            logger.error(f"Component {self.id}: Compiled output evaluation failed: {e}")
            raise

    def _generate_tmap_compiled_script(
        self,
        variables_config: List[Dict],
        outputs_config: List[Dict],
        main_name: str,
        lookup_names: List[str],
        die_on_error: bool = True
    ) -> str:
        """
        Generate compiled Java script for tMap execution

        Uses pure Java syntax (not Groovy shortcuts).

        Args:
                die_on_error: If True, throw exception on errors. If false, log and continue.
        """
        # Build script parts
        lines = []

        # Import statements
        lines.append("import java.util.*;")
        lines.append("import java.util.concurrent.atomic.*;")
        lines.append("import java.util.stream.*;")
        lines.append("import com.citi.gru.etl.RowWrapper;")
        lines.append("")

        # Setup output arrays and counters
        for output in outputs_config:
            output_name = output['name']
            num_cols = len(output['columns'])
            lines.append(f"// Output: {output_name}")
            lines.append(f"Object[][] {output_name}_data = new Object[rowCount][{num_cols}];")
            lines.append(f"AtomicInteger {output_name}_count = new AtomicInteger(0);")
            lines.append("")

        # If die_on_error is false, setup error tracking
        if not die_on_error:
            lines.append("// Error tracking")
            lines.append("AtomicInteger error_count = new AtomicInteger(0);")
            lines.append("java.utiil.concurrent.ConcurrentHashMap<Integer, String> error_rows = new java.util.concurrent.ConcurrentHashMap<>(); ")
            lines.append("")

        # Parallel processing loop
        lines.append("// Process rows in parallel")     
        lines.append("IntStream.range(0, rowCount).parallel().forEach(i -> {")
        lines.append("    try {")
        lines.append("        // Create row wrappers (each knows its table name for column lookup)")
        lines.append(f"        RowWrapper {main_name} = new RowWrapper(iinputRoot,i , \"{main_name}\");")
        lines.append("")       

        # Create RowWrappers for each lookup (each knows its table name)
        for lookup in lookup_names:
            lines.append(f"        RowWrapper {lookup} = new RowWrapper(iinputRoot,i , \"{lookup}\");")
        lines.append("")

        # Track if row matched any output ( for reject logic  )
        has_reject = any(output.get('reject') for output in outputs_config)
        if has_reject:
            lines.append("        boolean matchedAny = false;")
            lines.append("")

        # INNER TRY-CATCH: wrap variable and all non-reject outputs
        lines.append(" // Inner try-catch for variables and outputs can error")
        lines.append("        try {")

        # Evaluate variables IN ORDER
        for variable in variables_config:
            lines.append("            // Evaluate variables")
            lines.append("            Map<String, Object> vars = new HashMap<>();")
            for var in variables_config:
                var_name = var['name']
                var_expr = self._strip_java_marker(var['expression'])
                
                # Handle empty expression (Talend allows blank variables )
                if not var_expr or var_expr.strip() == "":
                    var_expr = "null"

                lines.append(f"            vars.put(\"{var_name}\", {var_expr});")
            lines.append("")

            # Route to outputs (first_pass: non-reject)
        for output in outputs_config:
            output_name = output['name']
            is_reject = output.get('reject', False)

            if is_reject:
                continue  # Skip reject outputs in first pass
                    
            # Check filter
            filter_expr = output.get('filter','')
            activate_filter = output.get('activate_filter', False)

            num_cols = len(output['columns'])

            if activate_filter and filter_expr:
                clean_filter = self._strip_java_marker(filter_expr)
                lines.append(f"// Output: {output_name} (with filter)")
                lines.append(f"if ({clean_filter}) {{")
                indent = "    "
            else:
                lines.append(f"// Output: {output_name} (no filter)")
                lines.append("{")
                indent = ""

            # Pre-evaluate ALL columns into temp array (atomic operation)
            lines.append(f"{indent}// Pre-evaluate all columns (if any fails, nothing is committed)")
            lines.append(f"{indent}Object[] {output_name}_tempRow = new Object[{num_cols}];")

            for col_idx, col in enumerate(output["columns"]):
                col_name = col["name"]
                col_expr = self._strip_java_marker(col["expression"])

                # Handle empty expression (Talend allows blank output columns)
                if not col_expr or col_expr.strip() == "":
                    col_expr = "null"

                lines.append(f"{indent}{output_name}_tempRow[{col_idx}] = {col_expr};")

            # Only if all columns succeeded, commit to output
            lines.append(f"{indent}// All columns evaluated successfully, commit to output")
            if has_reject:
                lines.append(f"{indent}matchedAny = true;")
            lines.append(f"{indent}int {output_name}_idx = {output_name}_count.getAndIncrement();")
            lines.append(f"{indent}{output_name}_data[{output_name}_idx] = {output_name}_tempRow;")

            lines.append("}")
            lines.append("")

        # Exception handling (INNER try-catch)
        lines.append("} catch (Exception e) {")
        if die_on_error:
            lines.append("    // die_on_error=true: Re-throw exception")
            lines.append("    String errorMsg = e.getMessage() != null ? e.getMessage() : e.toString();")
            lines.append("    throw new RuntimeException(\"Error at row \" + i + \": \" + errorMsg, e);")
        else:
            lines.append("    // die_on_error=false: Log error, row will go to reject")
            lines.append("    String errorMsg = e.getMessage() != null ? e.getMessage() : e.toString();")
            lines.append("    errorCount.incrementAndGet();")
            lines.append("    errorMap.put(i, errorMsg);")

            if has_reject:
                lines.append("    // matchedAny stays false, row will go to reject")
                lines.append("    matchedAny = false;")
                #lines.append("    // System.err.println(\"{tMap Debug} Row \" + i + \" error: \" + errorMsg);")
        lines.append("}")
        lines.append("")

        # Handle reject outputs (OUTSIDE inner try-catch)
        if has_reject:
            lines.append("// Reject outputs (if no match or if error occurred)")
            lines.append("if (!matchedAny) {")

            #Add debug statment to track reject rows
            if not die_on_error:
                lines.append("    // Debug: Check if this is an error row")
                lines.append("    if (errorMap.containsKey(i)) {")
                #lines.append("        // System.err.println(\"{tMap Debug} Row \" + i + \" is a reject due to error: \" + errorMap.get(i));")
                lines.append("    }")

            for output in outputs_config:
                if not output.get("is_reject"):
                    continue

                output_name = output["name"]
                num_cols = len(output["columns"])

                #Pre-evaluate all reject columns into temp array
                lines.append(f"    Object[] {output_name}_tempRow = new Object[{num_cols}];")
                for col_idx, col in enumerate(output["columns"]):
                    col_name = col["name"]
                    col_expr = self._strip_java_marker(col["expression"])

                    # Handle empty expression (Talend allows blank output columns)
                    if not col_expr or col_expr.strip() == "":
                        col_expr = "null"

                    lines.append(f"    {output_name}_tempRow[{col_idx}] = {col_expr};")

                # Commit to reject output
                lines.append(f"    int {output_name}_idx = {output_name}_count.getAndIncrement();")
                lines.append(f"    {output_name}_data[{output_name}_idx] = {output_name}_tempRow;")

                #Debug: Print reject output size after adding record
                #lines.append(f"    // System.err.println(\"{tMap Debug} Added row \" +i + \" to reject '{output_name}', current count : \" + {output_name}_count.get());")

            lines.append("}")
            lines.append("")

        lines.append("} catch (Exception outerE) {")
        lines.append( "    String errorMsg = outerE.getMessage() != null ? outerE.getMessage() : outerE.toString();")
        lines.append("    throw new RuntimeException(\"Error at row \" + i + \" (outer): \" + errorMsg, outerE);")
        lines.append("}")
        lines.append("});")  # End of parallel forEach
        lines.append("")

        # Return results
        lines.append("// Return results")
        lines.append("Map<String, Map<String, Object>> results = new HashMap<>();")
        for output in outputs_config:
            output_name = output["name"]
            lines.append(f"Map<String, Object> {output_name}_result = new HashMap<>();")
            lines.append(f"{output_name}_result.put(\"data\", {output_name}_data);")
            lines.append(f"{output_name}_result.put(\"count\", {output_name}_count.get());")
            lines.append(f"results.put(\"{output_name}\", {output_name}_result);")

        # Return error tracking info if die_on_error=false
        if not die_on_error:
            lines.append("")
            lines.append("// Return error tracking info")
            lines.append("Map<String, Object> errorInfo = new HashMap<>();")
            lines.append("errorInfo.put(\"count\", errorCount.get());")
            lines.append("errorInfo.put(\"indices\", new java.util.ArrayList<>(errorMap.keySet()));")
            lines.append("errorInfo.put(\"messages\", errorMap);")
            lines.append("results.put(\"__errors__\", errorInfo);")

        lines.append("return results;")
        logger.debug(f"Component {self.id}: Generated tMap compiled script:\n" + "\n".join(lines))
        return "\n".join(lines)

    def _create_empty_outputs(self) -> Dict[str, pd.DataFrame]:
        """Create empty DataFrames for all outputs based on configuration"""
        outputs = {}
        for output_config in self.config['outputs']:
            outputs[output_config['name']] = pd.DataFrame()

        return outputs