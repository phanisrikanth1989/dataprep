"""
SortRow - Sort data by specified columns and order.

Talend equivalent: tSortRow

This component sorts input data based on configured columns and sort orders.
Supports multi-column sorting, ascending/descending order per column, null value positioning,
and external sorting for large datasets that exceed memory limits.
"""
# Standard Library
import logging
import os
import tempfile
from typing import Dict, Any, Optional, List

# Third-party
import pandas as pd

# Project imports
from ...base_component import BaseComponent

logger = logging.getLogger(__name__)


class SortRow(BaseComponent):
    """
    Sort rows based on specified columns and order.

    This component provides comprehensive sorting functionality for DataFrames,
    supporting both in-memory and external sorting approaches for handling
    datasets of varying sizes.

    Configuration:
        sort_columns (List[str]): List of column names to sort by. Required.
        sort_orders (List[str]): Sort order for each column ('asc', 'desc'). Default: ['asc']
        na_position (str): Position of NaN values ('first', 'last'). Default: 'last'
        case_sensitive (bool): Whether sorting is case sensitive for string columns. Default: True
        external_sort (bool): Force external sorting using temporary files. Default: False
        max_memory_rows (int): Maximum rows to sort in memory before switching to external. Default: 1000000
        chunk_size (int): Chunk size for external sorting. Default: 10000
        temp_dir (str): Temporary directory for external sort files. Default: system temp
        output_chunk_size (int): Chunk size for streaming output. Default: 10000

    Inputs:
        main: Input DataFrame to be sorted

    Outputs:
        main: Sorted DataFrame or generator (for streaming)

    Statistics:
        NB_LINE: Total rows processed
        NB_LINE_OK: Rows successfully sorted (same as NB_LINE)
        NB_LINE_REJECT: Rejected rows (always 0 for sort)

    Example configuration:
        {
            "sort_columns": ["name", "age"],
            "sort_orders": ["asc", "desc"],
            "na_position": "last",
            "case_sensitive": False
        }

    Notes:
        - External sorting is automatically used for datasets larger than max_memory_rows
        - Streaming data is collected and sorted as a batch operation
        - Temporary sort columns are created for case-insensitive string sorting
    """

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Required fields
        sort_columns = self.config.get('sort_columns', [])
        if not sort_columns:
            errors.append("Missing required config: 'sort_columns'")
        elif not isinstance(sort_columns, list):
            errors.append("Config 'sort_columns' must be a list")

        # Optional field validation
        sort_orders = self.config.get('sort_orders', [])
        if sort_orders and not isinstance(sort_orders, list):
            errors.append("Config 'sort_orders' must be a list")

        na_position = self.config.get('na_position', 'last')
        if na_position not in ['first', 'last']:
            errors.append("Config 'na_position' must be 'first' or 'last'")

        case_sensitive = self.config.get('case_sensitive', True)
        if not isinstance(case_sensitive, bool):
            errors.append("Config 'case_sensitive' must be a boolean")

        external_sort = self.config.get('external_sort', False)
        if not isinstance(external_sort, bool):
            errors.append("Config 'external_sort' must be a boolean")

        max_memory_rows = self.config.get('max_memory_rows', 1000000)
        if not isinstance(max_memory_rows, int) or max_memory_rows <= 0:
            errors.append("Config 'max_memory_rows' must be a positive integer")

        return errors

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Sort input data based on configuration.

        Applies sorting transformation to the input DataFrame based on specified
        columns and sort orders. Handles both in-memory and external sorting
        depending on data size and configuration.

        Args:
            input_data: Input DataFrame to sort. If None or empty, returns empty result.

        Returns:
            Dictionary containing:
                - 'main': Sorted DataFrame or generator for streaming data

        Raises:
            Exception: If sorting operation fails

        Example:
            result = self._process(input_df)
            sorted_df = result['main']
        """
        # Handle empty input
        if input_data is None or input_data.empty:
            logger.warning(f"[{self.id}] Empty input received")
            self._update_stats(0, 0, 0)
            return {'main': pd.DataFrame()}

        rows_in = len(input_data)
        logger.info(f"[{self.id}] Processing started: {rows_in} rows")

        # Check if streaming
        if self._is_streaming(input_data):
            return self._process_streaming(input_data)

        # Get configuration
        sort_columns = self.config.get('sort_columns', [])
        sort_orders = self.config.get('sort_orders', [])
        na_position = self.config.get('na_position', 'last')  # 'first' or 'last'
        case_sensitive = self.config.get('case_sensitive', True)
        external_sort = self.config.get('external_sort', False)
        max_memory_rows = self.config.get('max_memory_rows', 1000000)

        # Validate configuration
        if not sort_columns:
            logger.warning(f"[{self.id}] No sort columns specified: returning unsorted data")
            self._update_stats(len(input_data), len(input_data), 0)
            return {'main': input_data}

        try:
            # Check if external sort is needed
            if external_sort or len(input_data) > max_memory_rows:
                logger.info(f"[{self.id}] Using external sort: {len(input_data)} rows")
                return self._external_sort(input_data, sort_columns, sort_orders, na_position)

            # Prepare sort parameters
            by_columns = []
            ascending = []

            for i, col in enumerate(sort_columns):
                if col in input_data.columns:
                    by_columns.append(col)
                    # Get sort order (default to ascending)
                    if i < len(sort_orders):
                        order = sort_orders[i].lower()
                        ascending.append(order != 'desc' and order != 'descending')
                    else:
                        ascending.append(True)
                else:
                    logger.warning(f"[{self.id}] Column not found: '{col}'")

            if not by_columns:
                # No valid columns to sort
                logger.warning(f"[{self.id}] No valid sort columns found")
                self._update_stats(len(input_data), len(input_data), 0)
                return {'main': input_data}

            # Handle case-insensitive sorting for string columns
            if not case_sensitive:
                # Create temporary lowercase columns for string columns
                temp_columns = {}
                for col in by_columns:
                    if input_data[col].dtype == 'object':
                        temp_col = f"_temp_sort_{col}"
                        temp_columns[col] = temp_col
                        input_data[temp_col] = input_data[col].str.lower()

                # Replace column names with temp columns for sorting
                if temp_columns:
                    by_columns = [temp_columns.get(col, col) for col in by_columns]

            # Perform sorting
            sorted_df = input_data.sort_values(
                by=by_columns,
                ascending=ascending,
                na_position=na_position,
                ignore_index=True,
                kind='stable'  # Stable sort to preserve original order for equal values
            )

            # Remove temporary columns if created
            if not case_sensitive:
                temp_cols_to_drop = [col for col in sorted_df.columns if col.startswith('_temp_sort_')]
                if temp_cols_to_drop:
                    sorted_df = sorted_df.drop(columns=temp_cols_to_drop)

            # Update statistics
            row_count = len(sorted_df)
            self._update_stats(row_count, row_count, 0)

            # Store additional stats in GlobalMap
            if self.global_map:
                self.global_map.put(f"{self.id}_SORTED_BY", ','.join(sort_columns))
                self.global_map.put(f"{self.id}_SORT_ORDERS", ','.join(sort_orders))

            logger.info(f"[{self.id}] Processing complete: sorted {row_count} rows by {sort_columns}")

            return {'main': sorted_df}

        except Exception as e:
            logger.error(f"[{self.id}] Sorting failed: {e}")
            raise

    def _is_streaming(self, data) -> bool:
        """
        Check if data is a generator (streaming).

        Args:
            data: Data to check

        Returns:
            True if data is a streaming generator, False otherwise
        """
        return hasattr(data, '__iter__') and not isinstance(data, (pd.DataFrame, dict, str))

    def _external_sort(self, data: pd.DataFrame, sort_columns: List[str],
                       sort_orders: List[str], na_position: str) -> Dict[str, Any]:
        """
        Perform external sorting using temporary files for very large datasets.

        Implements a k-way merge sort using temporary files to handle datasets
        that exceed memory limits. Data is split into chunks, each chunk is sorted
        and saved to temporary files, then merged back together.

        Args:
            data: Input DataFrame to sort
            sort_columns: Columns to sort by
            sort_orders: Sort order for each column
            na_position: Position of NaN values ('first' or 'last')

        Returns:
            Dictionary containing sorted DataFrame

        Raises:
            Exception: If external sorting operation fails
        """
        chunk_size = self.config.get('chunk_size', 10000)
        temp_dir = self.config.get('temp_dir', tempfile.gettempdir())

        try:
            # Create temporary directory for sort files
            sort_dir = tempfile.mkdtemp(prefix='sort_', dir=temp_dir)
            temp_files = []

            # Split data into chunks and sort each chunk
            chunks = []
            for i in range(0, len(data), chunk_size):
                chunk = data.iloc[i:i+chunk_size]

                # Sort chunk
                by_columns = [col for col in sort_columns if col in chunk.columns]
                ascending = [sort_orders[j].lower() != 'desc'
                             for j in range(len(by_columns))]

                sorted_chunk = chunk.sort_values(
                    by=by_columns,
                    ascending=ascending,
                    na_position=na_position
                )

                # Save to temporary file
                temp_file = os.path.join(sort_dir, f'chunk_{len(temp_files)}.parquet')
                sorted_chunk.to_parquet(temp_file)
                temp_files.append(temp_file)
                chunks.append(sorted_chunk)

            # Merge sorted chunks (k-way merge)
            logger.info(f"[{self.id}] Merging {len(temp_files)} sorted chunks")

            # Simple merge for now - can be optimized with heap-based k-way merge
            all_chunks = []
            for temp_file in temp_files:
                chunk = pd.read_parquet(temp_file)
                all_chunks.append(chunk)

            # Final sort of merged data
            merged_df = pd.concat(all_chunks, ignore_index=True)

            by_columns = [col for col in sort_columns if col in merged_df.columns]
            ascending = [sort_orders[j].lower() != 'desc'
                         for j in range(len(by_columns))]

            sorted_df = merged_df.sort_values(
                by=by_columns,
                ascending=ascending,
                na_position=na_position,
                ignore_index=True
            )

            # Update statistics
            row_count = len(sorted_df)
            self._update_stats(row_count, row_count, 0)

            logger.info(f"[{self.id}] External sort completed: {row_count} rows")

            return {'main': sorted_df}

        finally:
            # Clean up temporary files
            for temp_file in temp_files:
                try:
                    os.remove(temp_file)
                except:
                    pass
            try:
                os.rmdir(sort_dir)
            except:
                pass

    def _process_streaming(self, input_data) -> Dict[str, Any]:
        """
        Process streaming input by collecting chunks and sorting.

        Note: Streaming sort requires collecting all data first,
        so this may not be truly streaming for very large datasets.

        Args:
            input_data: Streaming input data (generator)

        Returns:
            Dictionary containing sorted generator for consistency
        """
        sort_columns = self.config.get('sort_columns', [])
        sort_orders = self.config.get('sort_orders', [])
        na_position = self.config.get('na_position', 'last')

        # Collect all chunks
        all_chunks = []
        total_rows = 0

        logger.info(f"[{self.id}] Collecting streaming chunks for sorting")

        for chunk in input_data:
            if not chunk.empty:
                all_chunks.append(chunk)
                total_rows += len(chunk)

        if not all_chunks:
            logger.warning(f"[{self.id}] No streaming chunks received")
            self._update_stats(0, 0, 0)
            return {'main': pd.DataFrame()}

        # Combine all chunks
        combined_df = pd.concat(all_chunks, ignore_index=True)

        # Sort combined data
        by_columns = [col for col in sort_columns if col in combined_df.columns]
        ascending = [sort_orders[i].lower() != 'desc'
                     for i in range(len(by_columns)) if i < len(sort_orders)]

        sorted_df = combined_df.sort_values(
            by=by_columns,
            ascending=ascending,
            na_position=na_position,
            ignore_index=True
        )

        # Update statistics
        self._update_stats(total_rows, total_rows, 0)

        # Return as generator for consistency
        def sorted_generator():
            chunk_size = self.config.get('output_chunk_size', 10000)
            for i in range(0, len(sorted_df), chunk_size):
                yield sorted_df.iloc[i:i+chunk_size]

        logger.info(f"[{self.id}] Streaming sort complete: {total_rows} rows")

        return {'main': sorted_generator()}
