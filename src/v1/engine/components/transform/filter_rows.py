"""
FilterRows - Filters rows based on conditions or advanced Java expressions.

Talend equivalent: tFilterRow, tFilterRows
"""
import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent

logger = logging.getLogger(__name__)


class FilterRows(BaseComponent):
    """
    Filters rows based on specified conditions or advanced Java expressions.

    Equivalent to Talend's tFilterRow/tFilterRows component.

    Configuration:
        conditions (list): List of filter conditions (dicts with column, operator, value). Default: []
        logical_operator (str): Logical operator to combine conditions ('AND'/'OR'). Default: 'AND'
        use_advanced (bool): If True, use advanced_condition (Java expression). Default: False
        advanced_condition (str): Java-like filter expression (marked with {{java}}). Default: ''

    Inputs:
        main: DataFrame to filter

    Outputs:
        main: Filtered DataFrame (rows matching conditions)
        reject: DataFrame of rejected rows (not matching conditions)

    Statistics:
        NB_LINE: Total rows processed
        NB_LINE_OK: Rows accepted (passed filter)
        NB_LINE_REJECT: Rows rejected (failed filter)

    Example configuration:
        {
            "conditions": [
                {"column": "status", "operator": "==", "value": "ACTIVE"}
            ],
            "logical_operator": "AND",
            "use_advanced": False
        }

    Notes:
        - Supports both simple conditions and advanced Java expressions
        - Context variables in values are automatically resolved
        - Logical operators support both Java style (&&, ||) and Python style (AND, OR)
    """

    # Class constants
    DEFAULT_LOGICAL_OPERATOR = 'AND'
    SUPPORTED_OPERATORS = ['==', '!=', '>', '<', '>=', '<=']
    LOGICAL_OPERATOR_MAPPING = {
        '&&': 'AND',
        '||': 'OR',
        'AND': 'AND',
        'OR': 'OR'
    }

    def _validate_config(self) -> List[str]:
        """Validate component configuration."""
        errors = []

        use_advanced = self.config.get('use_advanced', False)

        if use_advanced:
            # Advanced mode validation
            if not self.config.get('advanced_condition'):
                errors.append("Missing required config: 'advanced_condition' when use_advanced is True")
        else:
            # Simple conditions validation
            conditions = self.config.get('conditions', [])
            if not conditions or not isinstance(conditions, list):
                errors.append("Config 'conditions' must be a non-empty list when use_advanced is False")
            else:
                for i, condition in enumerate(conditions):
                    if not isinstance(condition, dict):
                        errors.append(f"Condition {i} must be a dictionary")
                        continue

                    if 'column' not in condition:
                        errors.append(f"Condition {i} missing required field: 'column'")
                    if 'operator' not in condition:
                        errors.append(f"Condition {i} missing required field: 'operator'")
                    elif condition['operator'] not in self.SUPPORTED_OPERATORS:
                        errors.append(f"Condition {i} has unsupported operator: {condition['operator']}. "
                                      f"Supported: {', '.join(self.SUPPORTED_OPERATORS)}")
                    if 'value' not in condition:
                        errors.append(f"Condition {i} missing required field: 'value'")

        # Logical operator validation
        logical_op = self.config.get('logical_operator', self.DEFAULT_LOGICAL_OPERATOR)
        if logical_op not in self.LOGICAL_OPERATOR_MAPPING:
            errors.append(f"Config 'logical_operator' must be one of: {', '.join(self.LOGICAL_OPERATOR_MAPPING.keys())}")

        return errors

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Process input data by filtering rows based on conditions.

        Args:
            input_data: Input DataFrame. If None or empty, returns empty result.

        Returns:
            Dictionary containing:
                - 'main': DataFrame with accepted rows
                - 'reject': DataFrame with rejected rows
                - 'stats': Execution statistics

        Raises:
            Exception: If filtering operation fails
        """
        print(f"[FilterRows] {self.id} config: {self.config}")
        print(f"[FilterRows] input_data shape: {getattr(input_data, 'shape', None)}")
        print(f"[FilterRows] input_data columns: {input_data.columns.tolist() if input_data is not None else None}")
        if input_data is not None:
            print(f"[FilterRows] First 3 rows:\n{input_data.head(3)}")

        logger.debug(f"[{self.id}] Starting filter processing with input shape: {getattr(input_data, 'shape', None)}")

        # Handle empty input
        if input_data is None or input_data.empty:
            logger.warning(f"[{self.id}] Empty input received")
            self._update_stats(0, 0, 0)
            print(f"[FilterRows] Empty input, returning empty DataFrames.")
            return {'main': pd.DataFrame(), 'reject': pd.DataFrame()}

        rows_in = len(input_data)
        logger.info(f"[{self.id}] Processing started: {rows_in} rows")

        try:
            # Get configuration with defaults
            use_advanced = self.config.get('use_advanced', False)
            advanced_condition = self.config.get('advanced_condition', '')
            conditions = self.config.get('conditions', [])
            logical_operator = self.config.get('logical_operator', self.DEFAULT_LOGICAL_OPERATOR).upper()

            print(f"[FilterRows] use_advanced: {use_advanced}, logical_operator: {logical_operator}, conditions: {conditions}, advanced_condition: "
                  f"{advanced_condition}")

            # Map Talend logical operators to Python
            logical_operator = self.LOGICAL_OPERATOR_MAPPING.get(logical_operator, self.DEFAULT_LOGICAL_OPERATOR)
            if logical_operator != self.config.get('logical_operator', self.DEFAULT_LOGICAL_OPERATOR):
                print(f"[FilterRows] Mapped logical operator to: {logical_operator}")

            # Process based on mode
            if use_advanced and advanced_condition:
                mask = self._process_advanced_condition(input_data, advanced_condition)
            else:
                mask = self._process_simple_conditions(input_data, conditions, logical_operator)

            # Split data based on mask
            accepted = input_data[mask].copy()
            rejected = input_data[~mask].copy()

            rows_out = len(accepted)
            rows_rejected = len(rejected)

            print(f"[FilterRows] Accepted shape: {accepted.shape}, Rejected shape: {rejected.shape}")

            # Update statistics
            self._update_stats(rows_in, rows_out, rows_rejected)
            logger.info(f"[{self.id}] Processing complete: "
                        f"in={rows_in}, out={rows_out}, rejected={rows_rejected}")

            return {'main': accepted, 'reject': rejected}

        except Exception as e:
            logger.error(f"[{self.id}] Processing failed: {e}")
            print(f"[FilterRows] Error during filtering: {e}")
            raise

    def _process_advanced_condition(self, input_data: pd.DataFrame, advanced_condition: str) -> pd.Series:
        """
        Process advanced Java-like condition.

        Args:
            input_data: Input DataFrame
            advanced_condition: Java expression to evaluate

        Returns:
            Boolean mask Series
        """
        logger.debug(f"[{self.id}] Using advanced condition: {advanced_condition}")
        expr = advanced_condition.replace('{{java}}', '').strip()
        expr = expr.replace('input_row.', '')
        print(f"[FilterRows] Evaluating advanced condition: {expr}")

        mask = input_data.apply(lambda row: eval(expr, {}, row.to_dict()), axis=1)
        print(f"[FilterRows] Advanced mask: {mask.tolist()}")
        return mask

    def _process_simple_conditions(self, input_data: pd.DataFrame, conditions: List[Dict],
                                   logical_operator: str) -> pd.Series:
        """
        Process simple column-operator-value conditions.

        Args:
            input_data: Input DataFrame
            conditions: List of condition dictionaries
            logical_operator: 'AND' or 'OR'

        Returns:
            Boolean mask Series
        """
        logger.debug(f"[{self.id}] Using simple conditions: {conditions} with logical_operator: {logical_operator}")

        if not conditions:
            return pd.Series([True] * len(input_data))

        masks = []
        print(f"[FilterRows] Unique values in '{conditions[0]['column']}': {input_data[conditions[0]['column']].unique()}")

        for cond in conditions:
            mask = self._evaluate_single_condition(input_data, cond)
            masks.append(mask)

        # Combine masks with logical operator
        if len(masks) == 1:
            final_mask = masks[0]
        elif logical_operator == 'AND':
            final_mask = masks[0]
            for m in masks[1:]:
                final_mask = final_mask & m
        elif logical_operator == 'OR':
            final_mask = masks[0]
            for m in masks[1:]:
                final_mask = final_mask | m
        else:
            logger.warning(f"[{self.id}] Unknown logical operator '{logical_operator}', defaulting to AND")
            print(f"[FilterRows] Unknown logical operator '{logical_operator}', defaulting to AND.")
            final_mask = masks[0]
            for m in masks[1:]:
                final_mask = final_mask & m

        print(f"[FilterRows] Final mask: {final_mask.toList()}")
        return final_mask

    def _evaluate_single_condition(self, input_data: pd.DataFrame, condition: Dict[str, Any]) -> pd.Series:
        """
        Evaluate a single condition against the DataFrame.

        Args:
            input_data: Input DataFrame
            condition: Dictionary with 'column', 'operator', 'value'

        Returns:
            Boolean mask Series for this condition
        """
        col = condition.get('column')
        op = condition.get('operator')
        val = condition.get('value')

        # Resolve context variables in the value before comparison
        if isinstance(val, str) and self.context_manager:
            val = self.context_manager.resolve_string(val)

        # Strip quotes and whitespace from value
        if isinstance(val, str):
            val = val.strip().strip("'").strip("'")

        print(f"[FilterRows] Condition: column={col}, operator={op}, value={val}")

        if col not in input_data.columns:
            logger.warning(f"[{self.id}] Column '{col}' not found in input data")
            print(f"[FilterRows] Column '{col}' not found in input data.")
            return pd.Series([False] * len(input_data))

        # Use .astype(str).str.strip() for robust comparison
        col_data = input_data[col].astype(str).str.strip()
        val_stripped = str(val).strip()

        # Apply operator
        if op == '==':
            mask = col_data == val_stripped
        elif op == '!=':
            mask = col_data != val_stripped
        elif op == '>':
            mask = col_data > val_stripped
        elif op == '<':
            mask = col_data < val_stripped
        elif op == '>=':
            mask = col_data >= val_stripped
        elif op == '<=':
            mask = col_data <= val_stripped
        else:
            logger.warning(f"[{self.id}] Unsupported operator '{op}'")
            print(f"[FilterRows] Unsupported operator '{op}'.")
            mask = pd.Series([False] * len(input_data))

        # Print comparison for each row with repr
        for idx, v in enumerate(col_data):
            print(f"[FilterRows] Row {idx}: {col}={repr(v)} == {repr(val_stripped)} -> {v == val_stripped}")
        print(f"[FilterRows] Mask for condition: {mask.tolist()}")

        return mask

    def validate_config(self) -> bool:
        """
        Legacy validation method for backward compatibility.

        Returns:
            True if configuration is valid, False otherwise
        """
        errors = self._validate_config()
        if errors:
            for error in errors:
                logger.error(f"[{self.id}] {error}")
        return len(errors) == 0
