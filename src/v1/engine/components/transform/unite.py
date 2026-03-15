"""
Unite - Combine multiple input streams into one.

Talend equivalent: tUnite

This component combines multiple input DataFrames into a single output,
supporting both UNION (concatenation) and MERGE (join-based) operations.
Supports streaming mode for large datasets.
"""
import pandas as pd
from typing import Dict, Any, Optional, List, Union
import logging
from ...base_component import BaseComponent, ExecutionMode

logger = logging.getLogger(__name__)


class Unite(BaseComponent):
    """
    Combines multiple input streams into a single output stream.
    Equivalent to Talend's tUnite component.

    Configuration:
        mode (str): Combination mode. 'UNION' or 'MERGE'. Default: 'UNION'
        remove_duplicates (bool): Remove duplicate rows after combination. Default: False
        keep (str): Keep strategy for duplicate removal. 'first', 'last', or False. Default: 'first'
        sort_output (bool): Sort the output DataFrame. Default: False
        sort_columns (List[str]): Columns to sort by when sort_output is True. Default: []
        merge_columns (List[str]): Specific columns to merge on (MERGE mode only). Default: None
        merge_how (str): Merge strategy for MERGE mode. 'inner', 'outer', 'left', 'right', 'cross'. Default: 'inner'

    Inputs:
        Multiple inputs supported as dictionary of DataFrames

    Outputs:
        main: Combined DataFrame containing all input data

    Statistics:
        NB_LINE: Total input rows processed from all inputs
        NB_LINE_OK: Output rows produced after combination
        NB_LINE_REJECT: Always 0 (no rows are rejected)

    Example:
        # UNION mode configuration
        config = {
            "mode": "UNION",
            "remove_duplicates": True,
            "sort_output": True,
            "sort_columns": ["date", "id"]
        }

        # MERGE mode configuration
        config = {
            "mode": "MERGE",
            "merge_columns": ["customer_id"],
            "merge_how": "inner"
        }

    Notes:
        - UNION mode concatenates all inputs vertically
        - MERGE mode joins inputs based on common or specified columns
        - Streaming mode only supports UNION operations
        - Component overrides execute() to handle multiple input streams
    """

    # Class constants
    DEFAULT_MODE = 'UNION'
    VALID_MODES = ['UNION', 'MERGE']
    VALID_MERGE_HOW = ['inner', 'outer', 'left', 'right', 'cross']
    DEFAULT_MERGE_HOW = 'inner'
    DEFAULT_KEEP = 'first'

    def __init__(self, component_id: str, config: Dict[str, Any],
                 global_map: Any = None, context_manager: Any = None):
        super().__init__(component_id, config, global_map, context_manager)

        # Store multiple inputs
        self.input_data_map = {}

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Validate mode
        mode = self.config.get('mode', self.DEFAULT_MODE).upper()
        if mode not in self.VALID_MODES:
            errors.append(f"Config 'mode' must be one of: {', '.join(self.VALID_MODES)}")

        # Validate merge-specific settings
        if mode == 'MERGE':
            merge_how = self.config.get('merge_how', self.DEFAULT_MERGE_HOW)
            if merge_how not in self.VALID_MERGE_HOW:
                errors.append(f"Config 'merge_how' must be one of: {', '.join(self.VALID_MERGE_HOW)}")

        # Validate remove_duplicates settings
        if 'remove_duplicates' in self.config:
            if not isinstance(self.config['remove_duplicates'], bool):
                errors.append("Config 'remove_duplicates' must be boolean")

        # Validate sort settings
        if 'sort_output' in self.config:
            if not isinstance(self.config['sort_output'], bool):
                errors.append("Config 'sort_output' must be boolean")

        if 'sort_columns' in self.config:
            sort_columns = self.config['sort_columns']
            if not isinstance(sort_columns, list):
                errors.append("Config 'sort_columns' must be a list")

        return errors

    def execute(self, input_data: Optional[Any] = None) -> Dict[str, Any]:
        """
        Override execute to handle multiple inputs.

        Args:
            input_data: Can be a single DataFrame or dict of DataFrames

        Returns:
            Dictionary with combined output

        Note:
            This component overrides execute() instead of using _process()
            to handle multiple input streams as required by its functionality.
        """
        logger.info(f"[{self.id}] Processing started with execution mode: {self.execution_mode}")

        # Handle different input formats
        if isinstance(input_data, dict):
            # Multiple inputs provided as dictionary
            self.input_data_map = input_data
            logger.debug(f"[{self.id}] Received {len(input_data)} input streams: {list(input_data.keys())}")
        elif input_data is not None:
            # Single input provided
            self.input_data_map = {'main': input_data}
            logger.debug(f"[{self.id}] Received single input stream with {len(input_data)} rows")
        else:
            logger.warning(f"[{self.id}] No input data provided")
            self.input_data_map = {}

        # Check if we're in streaming mode
        if self.execution_mode == ExecutionMode.STREAMING:
            logger.debug(f"[{self.id}] Using streaming mode")
            return self._process_streaming()
        else:
            logger.debug(f"[{self.id}] Using batch mode")
            return self._process_batch()

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Standard processing method for single input compatibility.

        Args:
            input_data: Input DataFrame (may be None or empty)

        Returns:
            Dictionary with output DataFrames

        Note:
            This component primarily uses execute() for multiple inputs,
            but this method provides compatibility with standard processing.
        """
        if input_data is not None:
            self.input_data_map = {'main': input_data}
            return self._process_batch()
        else:
            logger.warning(f"[{self.id}] Empty input received")
            self._update_stats(0, 0, 0)
            return {'main': pd.DataFrame()}

    def _process_batch(self) -> Dict[str, Any]:
        """
        Process all inputs in batch mode.

        Returns:
            Dictionary containing combined output DataFrame
        """
        if not self.input_data_map:
            logger.warning(f"[{self.id}] No input data available for processing")
            self._update_stats(0, 0, 0)
            return {'main': pd.DataFrame()}

        # Get configuration with defaults
        mode = self.config.get('mode', self.DEFAULT_MODE).upper()
        remove_duplicates = self.config.get('remove_duplicates', False)
        keep = self.config.get('keep', self.DEFAULT_KEEP)
        sort_output = self.config.get('sort_output', False)
        sort_columns = self.config.get('sort_columns', [])

        logger.debug(f"[{self.id}] Configuration: mode={mode}, remove_duplicates={remove_duplicates}, "
                      f"sort_output={sort_output}, sort_columns={sort_columns}")

        try:
            # Collect all DataFrames
            dataframes = []
            total_input_rows = 0

            for input_name, data in self.input_data_map.items():
                if data is not None and not data.empty:
                    dataframes.append(data)
                    input_rows = len(data)
                    total_input_rows += input_rows
                    logger.debug(f"[{self.id}] Input '{input_name}' has {input_rows} rows")
                else:
                    logger.debug(f"[{self.id}] Input '{input_name}' is empty or None, skipping")

            if not dataframes:
                logger.warning(f"[{self.id}] No valid input DataFrames found")
                self._update_stats(0, 0, 0)
                return {'main': pd.DataFrame()}

            logger.info(f"[{self.id}] Combining {len(dataframes)} inputs ({total_input_rows} total rows) using {mode} mode")

            # Combine based on mode
            if mode == 'UNION':
                logger.debug(f"[{self.id}] Performing UNION operation")
                # Concatenate all inputs
                combined_df = pd.concat(dataframes, ignore_index=True, sort=False)

            elif mode == 'MERGE':
                logger.debug(f"[{self.id}] Performing MERGE operation")
                # Merge based on common columns
                merge_on = self.config.get('merge_columns', None)
                merge_how = self.config.get('merge_how', self.DEFAULT_MERGE_HOW)

                logger.debug(f"[{self.id}] Merge settings: merge_on={merge_on}, merge_how={merge_how}")

                if len(dataframes) == 1:
                    combined_df = dataframes[0]
                    logger.debug(f"[{self.id}] Single DataFrame for merge, using as-is")
                else:
                    # Start with first DataFrame
                    combined_df = dataframes[0]
                    logger.debug(f"[{self.id}] Starting merge with DataFrame of shape {combined_df.shape}")

                    # Merge with remaining DataFrames
                    for i, df in enumerate(dataframes[1:], 1):
                        logger.debug(f"[{self.id}] Merging with DataFrame {i} of shape {df.shape}")

                        if merge_on:
                            combined_df = pd.merge(
                                combined_df, df,
                                on=merge_on,
                                how=merge_how,
                                suffixes=('', '_dup')
                            )
                        else:
                            # Merge on common columns
                            common_cols = list(set(combined_df.columns) & set(df.columns))
                            if common_cols:
                                logger.debug(f"[{self.id}] Using common columns for merge: {common_cols}")
                                combined_df = pd.merge(
                                    combined_df, df,
                                    on=common_cols,
                                    how=merge_how,
                                    suffixes=('', '_dup')
                                )
                            else:
                                # No common columns, do cross join
                                logger.debug(f"[{self.id}] No common columns found, performing cross join")
                                combined_df = pd.merge(
                                    combined_df, df,
                                    how='cross'
                                )

                        logger.debug(f"[{self.id}] After merge {i}: result shape {combined_df.shape}")
            else:
                raise ValueError(f"Unknown mode: {mode}")

            # Remove duplicates if requested
            if remove_duplicates:
                before_dedup = len(combined_df)
                combined_df = combined_df.drop_duplicates(keep=keep)
                duplicates_removed = before_dedup - len(combined_df)
                logger.info(f"[{self.id}] Removed {duplicates_removed} duplicate rows")

            # Sort if requested
            if sort_output and sort_columns:
                valid_columns = [col for col in sort_columns if col in combined_df.columns]
                if valid_columns:
                    logger.debug(f"[{self.id}] Sorting by columns: {valid_columns}")
                    combined_df = combined_df.sort_values(by=valid_columns, ignore_index=True)
                else:
                    logger.warning(f"[{self.id}] No valid sort columns found in output")

            # Calculate statistics
            output_rows = len(combined_df)
            self._update_stats(total_input_rows, output_rows, 0)

            # Store additional stats in global map
            if self.global_map:
                self.global_map.put(f"{self.id}_INPUT_COUNT", len(dataframes))
                self.global_map.put(f"{self.id}_MODE", mode)
                self.global_map.put(f"{self.id}_INPUT_ROWS", total_input_rows)
                self.global_map.put(f"{self.id}_OUTPUT_ROWS", output_rows)

            logger.info(f"[{self.id}] Processing complete: "
                        f"combined {len(dataframes)} inputs ({total_input_rows} rows) "
                        f"into {output_rows} rows using {mode} mode")

            return {'main': combined_df}

        except Exception as e:
            logger.error(f"[{self.id}] Unite operation failed: {e}")
            raise

    def _process_streaming(self) -> Dict[str, Any]:
        """
        Process inputs in streaming mode.

        Returns:
            Dictionary with streaming generator

        Note:
            Only UNION mode is supported in streaming mode.
        """
        mode = self.config.get('mode', self.DEFAULT_MODE).upper()

        if mode != 'UNION':
            logger.warning(f"[{self.id}] Only UNION mode supported in streaming mode. "
                           f"Mode '{mode}' requested, falling back to batch processing")
            return self._process_batch()

        def stream_generator():
            """Generate combined stream from all inputs"""
            total_rows = 0

            logger.debug(f"[{self.id}] Starting streaming processing for {len(self.input_data_map)} inputs")

            for input_name, data_source in self.input_data_map.items():
                if data_source is None:
                    logger.debug(f"[{self.id}] Skipping None input '{input_name}'")
                    continue

                # Check if input is a generator
                if hasattr(data_source, '__iter__') and not isinstance(data_source, pd.DataFrame):
                    # Streaming input
                    logger.debug(f"[{self.id}] Processing streaming input '{input_name}'")
                    for chunk in data_source:
                        chunk_rows = len(chunk)
                        total_rows += chunk_rows
                        self._update_stats(chunk_rows, chunk_rows, 0)
                        logger.debug(f"[{self.id}] Streaming {chunk_rows} rows from '{input_name}'")
                        yield chunk
                else:
                    # Batch input in streaming context
                    if not data_source.empty:
                        rows = len(data_source)
                        total_rows += rows
                        self._update_stats(rows, rows, 0)
                        logger.debug(f"[{self.id}] Streaming {rows} rows from '{input_name}'")
                        yield data_source

            logger.info(f"[{self.id}] Streaming complete: processed total of {total_rows} rows")

        return {'main': stream_generator()}

    def add_input(self, input_name: str, data: Any) -> None:
        """
        Add an input stream to the unite operation.

        Args:
            input_name: Name of the input stream
            data: DataFrame or generator
        """
        self.input_data_map[input_name] = data
        logger.debug(f"[{self.id}] Added input '{input_name}' to unite operation")

    def validate_config(self) -> bool:
        """
        Validate component configuration.

        Returns:
            bool: True if configuration is valid, False otherwise

        Note:
            This method maintains backward compatibility. The preferred method
            is _validate_config() which returns detailed error messages.
        """
        errors = self._validate_config()

        if errors:
            for error in errors:
                logger.error(f"[{self.id}] Configuration error: {error}")
            return False

        logger.debug(f"[{self.id}] Configuration validation passed")
        return True
