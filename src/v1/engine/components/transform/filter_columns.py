"""
tFilterColumns component - Select or remove columns
"""
import pandas as pd
from typing import Dict, Any, Optional, List
import logging

from ...base_component import BaseComponent

logger = logging.getLogger(__name__)

class FilterColumns(BaseComponent):
    """
    Select or remove specific columns from the data flow.
    Equivalent to Talend's tFilterColumns component.
    """

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Filter columns based on configuration
        """

        if input_data is None or input_data.empty:
            self._update_stats(0, 0, 0)
            return {'main': pd.DataFrame()}

        # Get configuration
        mode = self.config.get('mode', 'include')  # include or exclude
        columns = self.config.get('columns', [])
        keep_row_order = self.config.get('keep_row_order', True)

        total_rows = len(input_data)

        try:
            # Validate columns exist
            available_columns = list(input_data.columns)

            if mode == 'include':
                # Keep only specified columns
                columns_to_keep = []
                missing_columns = []

                for col in columns:
                    if col in available_columns:
                        columns_to_keep.append(col)
                    else:
                        missing_columns.append(col)

                if missing_columns:
                    logger.warning(
                        f"Component {self.id}: Columns not found: {missing_columns}"
                    )

                if not columns_to_keep:
                    logger.warning(
                        f"Component {self.id}: No valid columns to keep, returning empty DataFrame"
                    )
                    self._update_stats(total_rows, 0, total_rows)
                    return {'main': pd.DataFrame()}

                # Select columns in specified order
                result_df = input_data[columns_to_keep].copy()

            else:
                # exclude mode
                # Remove specified columns
                columns_to_remove = [
                    col for col in columns if col in available_columns
                ]
                columns_to_keep = [
                    col for col in available_columns if col not in columns
                ]

                if not columns_to_keep:
                    logger.warning(
                        f"Component {self.id}: All columns excluded, returning empty DataFrame"
                    )
                    self._update_stats(total_rows, 0, total_rows)
                    return {'main': pd.DataFrame()}

                result_df = input_data[columns_to_keep].copy()

            # Log column filtering info
            logger.info(f"Component {self.id}: " f"Input columns: {len(available_columns)}, "f"Output columns: {len(result_df.columns)}")

            # Update statistics
            self._update_stats(total_rows, total_rows, 0)

            # Store column info in global map
            if self.global_map:
                self.global_map.put(f"{self.id}_NB_COLUMNS_IN", len(available_columns))
                self.global_map.put(f"{self.id}_NB_COLUMNS_OUT", len(result_df.columns))

            return {'main': result_df}

        except Exception as e:
            logger.error(f"Component {self.id}: Error filtering columns: {e}")
            raise
