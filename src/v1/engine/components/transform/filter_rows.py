"""
FilterRows component - Filters rows based on conditions or advanced Java expressions
"""
import pandas as pd
import logging
from ...base_component import BaseComponent

logger = logging.getLogger(__name__)

class FilterRows(BaseComponent):
    """
    Filters rows based on specified conditions or advanced Java expressions.
    Equivalent to Talend's tFilterRow/tFilterRows component.

    Configuration:
        conditions (list): List of filter conditions (dicts with column, operator, value)
        logical_operator (str): Logical operator to combine conditions ('AND'/'OR')
        use_advanced (bool): If True, use advanced_condition (Java expression)
        advanced_condition (str): Java-like filter expression (marked with {{java}})

    Inputs:
        main: DataFrame to filter

    Outputs:
        main: Filtered DataFrame (rows matching conditions)
        reject: DataFrame of rejected rows (not matching)
    """

    def _process(self, input_data: pd.DataFrame = None):
        print(f"[FilterRows] {self.id} config: {self.config}")
        print(f"[FilterRows] input_data shape: {getattr(input_data, 'shape', None)}")
        print(f"[FilterRows] input_data columns: {input_data.columns.tolist() if input_data is not None else None}")
        if input_data is not None:
            print(f"[FilterRows] First 3 rows:\n{input_data.head(3)}")

        logger.debug(
            f"FilterRows[{self.id}] - Starting _process with input_data shape: {getattr(input_data, 'shape', None)}"
        )

        if input_data is None or input_data.empty:
            self._update_stats(0, 0, 0)
            logger.debug(f"FilterRows[{self.id}] - Empty input, returning empty DataFrames.")
            print("[FilterRows] Empty input, returning empty DataFrames.")
            return {'main': pd.DataFrame(), 'reject': pd.DataFrame()}

        try:
            config = self.config
            use_advanced = config.get('use_advanced', False)
            advanced_condition = config.get('advanced_condition', '')
            conditions = config.get('conditions', [])
            logical_operator = config.get('logical_operator', 'AND').upper()

            print(
                f"[FilterRows] use_advanced: {use_advanced}, "
                f"logical_operator: {logical_operator}, "
                f"conditions: {conditions}"
            )

            # Map Talend logical operators to Python
            if logical_operator in ['&&', 'AND']:
                logical_operator = 'AND'
            elif logical_operator in ['||', 'OR']:
                logical_operator = 'OR'
            else:
                print(
                    f"[FilterRows] Unknown logical operator '{logical_operator}', defaulting to AND."
                )
                logical_operator = 'AND'

            # Advanced mode: Java-like expression
            if use_advanced and advanced_condition:
                logger.debug(
                    f"FilterRows[{self.id}] - Using advanced condition: {advanced_condition}"
                )
                expr = advanced_condition.replace('{{java}}', '').strip()
                expr = expr.replace('input_row.', '')
                print(f"[FilterRows] Evaluating advanced condition: {expr}")

                mask = input_data.apply(
                    lambda row: eval(expr, {}, row.to_dict()), axis=1
                )
                print(f"[FilterRows] Advanced mask: {mask.tolist()}")

            else:
                logger.debug(
                    f"FilterRows[{self.id}] - Using simple conditions: {conditions} "
                    f"with logical_operator: {logical_operator}"
                )
                masks = []

                for cond in conditions:
                    col = cond.get('column')
                    op = cond.get('operator')
                    val = cond.get('value')

                    # Resolve context variables
                    if isinstance(val, str) and self.context_manager:
                        val = self.context_manager.resolve_string(val)

                    # Strip quotes
                    if isinstance(val, str):
                        val = val.strip().strip('"').strip("'")

                    print(
                        f"[FilterRows] Condition: column={col}, operator={op}, value={val}"
                    )

                    if col not in input_data.columns:
                        logger.warning(
                            f"FilterRows[{self.id}] - Column '{col}' not found in input data."
                        )
                        print(
                            f"[FilterRows] Column '{col}' not found in input data."
                        )
                        masks.append(pd.Series([False] * len(input_data)))
                        continue

                    col_data = input_data[col].astype(str).str.strip()
                    val_stripped = str(val).strip()

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
                        logger.warning(
                            f"FilterRows[{self.id}] - Unsupported operator '{op}'."
                        )
                        print(
                            f"[FilterRows] Unsupported operator '{op}'."
                        )
                        mask = pd.Series([False] * len(input_data))

                    print(
                        f"[FilterRows] Mask for condition: {mask.tolist()}"
                    )
                    masks.append(mask)

                if masks:
                    if logical_operator == 'AND':
                        final_mask = masks[0]
                        for m in masks[1:]:
                            final_mask = final_mask & m
                    elif logical_operator == 'OR':
                        final_mask = masks[0]
                        for m in masks[1:]:
                            final_mask = final_mask | m
                    else:
                        logger.warning(
                            f"FilterRows[{self.id}] - Unknown logical operator '{logical_operator}', defaulting to AND."
                        )
                        print(
                            f"[FilterRows] Unknown logical operator '{logical_operator}', defaulting to AND."
                        )
                        final_mask = masks[0]
                        for m in masks[1:]:
                            final_mask = final_mask & m
                else:
                    final_mask = pd.Series([True] * len(input_data))

                mask = final_mask

            print(f"[FilterRows] Final mask: {mask.tolist()}")

            accepted = input_data[mask].copy()
            rejected = input_data[~mask].copy()

            print(
                f"[FilterRows] Accepted shape: {accepted.shape}, "
                f"Rejected shape: {rejected.shape}"
            )

            self._update_stats(len(input_data), len(accepted), len(rejected))

            logger.debug(
                f"FilterRows[{self.id}] - Accepted rows: {len(accepted)}, "
                f"Rejected rows: {len(rejected)}"
            )

            return {'main': accepted, 'reject': rejected}

        except Exception as e:
            logger.error(
                f"FilterRows[{self.id}] - Error during filtering: {e}"
            )
            print(f"[FilterRows] Error during filtering: {e}")
            raise

    def validate_config(self) -> bool:
        config = self.config

        if config.get('use_advanced', False):
            if not config.get('advanced_condition'):
                logger.error(
                    f"FilterRows[{self.id}] - advanced_condition required when use_advanced is True."
                )
                return False
        else:
            if not config.get('conditions') or not isinstance(config.get('conditions'), list):
                logger.error(
                    f"FilterRows[{self.id}] - conditions must be a non-empty list."
                )
                return False

        return True
