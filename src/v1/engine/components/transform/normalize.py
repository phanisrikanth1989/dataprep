
"""
Normalize - Normalize data by splitting a column into multiple rows.

Talend equivalent: tNormalize
"""

import logging
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from ...base_component import BaseComponent
from ...exceptions import ConfigurationError, ComponentExecutionError

logger = logging.getLogger(__name__)


class Normalize(BaseComponent):
    """
    Normalize data by splitting a column into multiple rows based on a delimiter.

    Takes a single column containing delimited values and creates multiple rows,
    one for each delimited value. Similar to SQL's UNNEST or Talend's tNormalize.

    Configuration:
        normalize_column (str): Column name to normalize/split. Required.
        item_separator (str): Delimiter to split values on. Default: ','
        deduplicate (bool): Remove duplicate values after splitting. Default: False
        trim (bool): Trim whitespace from split values. Default: False
        discard_trailing_empty_str (bool): Remove empty strings after splitting. Default: False
        die_on_error (bool): Whether to fail on errors. Default: False

    Inputs:
        main: Primary input DataFrame containing column to normalize

    Outputs:
        main: Normalized DataFrame with split values as separate rows

    Statistics:
        NB_LINE: Total rows processed
        NB_LINE_OK: Rows successfully normalized
        NB_LINE_REJECT: Rows rejected (always 0)

    Example configuration:
        {
            "normalize_column": "tags",
            "item_separator": ",",
            "trim": true,
            "deduplicate": true,
            "discard_trailing_empty_str": true
        }

    Notes:
        - Each input row can generate multiple output rows
        - All columns except the normalized column remain unchanged
        - Empty delimiter values can be filtered out with discard_trailing_empty_str
    """

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Required fields
        if 'normalize_column' not in self.config:
            errors.append("Missing required config: 'normalize_column'")
        elif not isinstance(self.config['normalize_column'], str):
            errors.append("Config 'normalize_column' must be a string")
        elif not self.config['normalize_column'].strip():
            errors.append("Config 'normalize_column' cannot be empty")

        # Optional field validation
        if 'item_separator' in self.config:
            separator = self.config['item_separator']
            if not isinstance(separator, str):
                errors.append("Config 'item_separator' must be a string")

        # Boolean validations
        for bool_param in ['deduplicate', 'trim', 'discard_trailing_empty_str', 'die_on_error']:
            if bool_param in self.config and not isinstance(self.config[bool_param], bool):
                errors.append(f"Config '{bool_param}' must be a boolean")

        return errors

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Process input data to normalize a column into multiple rows.

        Args:
            input_data: Input DataFrame containing rows to normalize.
                If None or empty, returns empty result.

        Returns:
            Dictionary containing:
                - 'main': Normalized DataFrame with split values as separate rows

        Raises:
            ConfigurationError: If required configuration is missing or invalid
            ComponentExecutionError: If normalization processing fails
        """
        # Handle empty input
        if input_data is None or input_data.empty:
            logger.warning(f"[{self.id}] Empty input received")
            self._update_stats(0, 0, 0)
            return {'main': pd.DataFrame()}

        rows_in = len(input_data)
        logger.info(f"[{self.id}] Processing started: {rows_in} rows")

        try:
            # Validate configuration
            config_errors = self._validate_config()
            if config_errors:
                error_msg = f"Configuration validation failed: {'; '.join(config_errors)}"
                logger.error(f"[{self.id}] {error_msg}")
                if self.config.get('die_on_error', False):
                    raise ConfigurationError(f"[{self.id}] {error_msg}. "
                                             f"Check component configuration and ensure all required parameters are set.")
                else:
                    self._update_stats(rows_in, rows_in, 0)
                    return {'main': input_data}

            # Get configuration with defaults
            normalize_column: str = self.config.get('normalize_column', '')
            item_separator: str = self.config.get('item_separator', ',')
            deduplicate: bool = self.config.get('deduplicate', False)
            trim: bool = self.config.get('trim', False)
            discard_trailing_empty_str: bool = self.config.get('discard_trailing_empty_str', False)
            die_on_error: bool = self.config.get('die_on_error', False)

            # Validate normalize column exists in input
            if normalize_column not in input_data.columns:
                error_msg = f"Column '{normalize_column}' not found in input data. Available columns: {list(input_data.columns)}"
                logger.error(f"[{self.id}] {error_msg}")
                if die_on_error:
                    raise ConfigurationError(f"[{self.id}] {error_msg}. "
                                             f"Check that the normalize_column parameter matches an existing column name.")
                else:
                    # Return original data unchanged
                    self._update_stats(rows_in, rows_in, 0)
                    return {'main': input_data}

            # Perform normalization
            normalized_rows: List[pd.Series] = []

            for idx, row in input_data.iterrows():
                try:
                    # Get the value to split (handle None/NaN)
                    cell_value: Union[str, float, None] = row[normalize_column]
                    if pd.isna(cell_value):
                        cell_value = ''
                    else:
                        cell_value = str(cell_value)

                    # Split the value
                    values: List[str] = cell_value.split(item_separator)

                    # Apply transformations
                    if trim:
                        values = [value.strip() for value in values]

                    if discard_trailing_empty_str:
                        values = [value for value in values if value]

                    if deduplicate:
                        # Preserve order while removing duplicates
                        seen: set = set()
                        unique_values: List[str] = []
                        for value in values:
                            if value not in seen:
                                seen.add(value)
                                unique_values.append(value)
                        values = unique_values

                    # Create new rows for each split value
                    if not values:
                        # If no values after processing, create one row with empty string
                        new_row: pd.Series = row.copy()
                        new_row[normalize_column] = ''
                        normalized_rows.append(new_row)
                    else:
                        for value in values:
                            new_row: pd.Series = row.copy()
                            new_row[normalize_column] = value
                            normalized_rows.append(new_row)

                except Exception as e:
                    error_msg = f"Failed to normalize row {idx}: {e}"
                    logger.error(f"[{self.id}] {error_msg}")
                    if die_on_error:
                        raise ComponentExecutionError(self.id, error_msg, e) from e
                    else:
                        # Include original row unchanged
                        normalized_rows.append(row.copy())

            # Create result DataFrame
            if normalized_rows:
                result_df: pd.DataFrame = pd.DataFrame(normalized_rows).reset_index(drop=True)
            else:
                result_df: pd.DataFrame = pd.DataFrame()

            rows_out: int = len(result_df)
            self._update_stats(rows_in, rows_out, 0)

            logger.info(f"[{self.id}] Processing complete: "
                        f"in={rows_in}, out={rows_out}, rejected=0")

            return {'main': result_df}

        except (ConfigurationError, ComponentExecutionError):
            # Re-raise custom exceptions
            raise
        except Exception as e:
            error_msg = f"Unexpected error during normalization: {e}"
            logger.error(f"[{self.id}] {error_msg}")
            raise ComponentExecutionError(self.id, error_msg, e) from e
