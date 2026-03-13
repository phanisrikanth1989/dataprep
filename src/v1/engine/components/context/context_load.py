"""
ContextLoad Component

This module implements the ContextLoad component for loading context variables from files.
The component supports multiple input formats and provides flexible context management capabilities.

Author: Data Preparation Team
Version: 1.0
Last Updated: 2024
"""

import pandas as pd
from typing import Dict, Any, Optional
import logging
import os
from ...base_component import BaseComponent

logger = logging.getLogger(__name__)


class ContextLoad(BaseComponent):
    """
    ContextLoad Component - Load context variables from files or DataFrames

    This component loads context variables and makes them available to other components
    in the data processing pipeline. It supports multiple input formats and provides
    flexible configuration options.

    Supported Input Formats:
    - Properties files (key=value format)
    - CSV files with key/value columns
    - CSV files with key/value/type columns
    - Direct DataFrame input

    Configuration Parameters:
    - filepath (str): Path to the context file
    - format (str): File format - 'properties' or 'csv' (default: 'properties')
    - delimiter (str): Delimiter for properties format (default: '=')
    - csv_separator (str): Separator for CSV format (default: ',')
    - print_operations (bool): Whether to log loaded operations (default: False)
    - error_if_not_exists (bool): Raise error if file doesn't exist (default: True)

    Returns:
    - Empty DataFrame (component loads context without producing data output)

    Global Map Variables:
    - {component_id}_NB_CONTEXT_LOADED: Number of context variables loaded

    Examples:
    ```python
    # Load from properties file
    context_load = ContextLoad({
        'filepath': '/path/to/context.properties',
        'format': 'properties',
        'print_operations': True
    })

    # Load from CSV file
    context_load = ContextLoad({
        'filepath': '/path/to/context.csv',
        'format': 'csv',
        'csv_separator': ','
    })
    ```
    """

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Process context loading from file or DataFrame input

        Args:
            input_data (Optional[pd.DataFrame]): Input DataFrame with context data.
                                                 Must contain 'key' and 'value' columns.
                                                 Optional 'type' column for type information.

        Returns:
            Dict[str, Any]: Dictionary containing empty main DataFrame

        Raises:
            ValueError: If required parameters are missing or invalid
            FileNotFoundError: If context file doesn't exist and error_if_not_exists is True

        Note:
            This method handles two input modes:
            1. DataFrame input: Processes context from provided DataFrame
            2. File input: Loads context from specified file path
        """
        # Extract configuration parameters
        filepath = self.config.get('filepath', '')
        file_format = self.config.get('format', 'properties')
        delimiter = self.config.get('delimiter', '=')
        csv_separator = self.config.get('csv_separator', ',')
        print_operations = self.config.get('print_operations', False)
        error_if_not_exists = self.config.get('error_if_not_exists', True)

        # Process DataFrame input if provided
        if input_data is not None:
            return self._process_dataframe_input(input_data, print_operations)

        # Process file input
        return self._process_file_input(
            filepath, file_format, delimiter, csv_separator,
            print_operations, error_if_not_exists
        )

    def _process_dataframe_input(self, input_data: pd.DataFrame, print_operations: bool) -> Dict[str, Any]:
        """
        Process context loading from DataFrame input

        Args:
            input_data (pd.DataFrame): Input DataFrame with context data
            print_operations (bool): Whether to log loaded operations

        Returns:
            Dict[str, Any]: Dictionary containing empty main DataFrame

        Raises:
            ValueError: If DataFrame doesn't have required columns
        """
        logger.debug(f"Component {self.id}: Processing DataFrame input: {input_data}")

        # Validate required columns
        if 'key' not in input_data.columns or 'value' not in input_data.columns:
            raise ValueError("Input DataFrame must have 'key' and 'value' columns")

        loaded_count = 0

        # Process each row in the DataFrame
        for _, row in input_data.iterrows():
            key = str(row['key']).strip()
            value = str(row['value'])

            # Determine value type
            value_type = self._determine_value_type(row, key, input_data.columns)

            # Set context variable
            if self.context_manager:
                self.context_manager.set(key, value, value_type)

            # Log operation if requested
            if print_operations:
                logger.info(f"Context loaded: {key} = {value} (type: {value_type})")

            loaded_count += 1

        # Update statistics and global map
        self._update_component_stats(loaded_count)
        logger.info(f"Component {self.id}: Loaded {loaded_count} context variables from input data")

        return {'main': pd.DataFrame()}

    def _process_file_input(self, filepath: str, file_format: str, delimiter: str,
                            csv_separator: str, print_operations: bool,
                            error_if_not_exists: bool) -> Dict[str, Any]:
        """
        Process context loading from file input

        Args:
            filepath (str): Path to the context file
            file_format (str): File format ('properties' or 'csv')
            delimiter (str): Key-value delimiter
            csv_separator (str): Separator for CSV format
            print_operations (bool): Whether to log loaded operations
            error_if_not_exists (bool): Raise error if file doesn't exist

        Returns:
            Dict[str, Any]: Dictionary containing empty main DataFrame

        Raises:
            ValueError: If filepath is not provided
            FileNotFoundError: If file doesn't exist and error_if_not_exists is True
        """
        # Validate filepath
        if not filepath:
            raise ValueError(f"Component {self.id}: filepath is required")

        # Check file existence
        if not os.path.exists(filepath):
            if error_if_not_exists:
                raise FileNotFoundError(f"Context file not found: {filepath}")
            else:
                logger.warning(f"Context file not found: {filepath}")
                self._update_component_stats(0)
                return {'main': pd.DataFrame()}

        try:
            # Load context based on format
            if file_format == 'csv':
                loaded_count = self._load_csv_context(filepath, csv_separator, print_operations)
            else:  # properties format
                loaded_count = self._load_properties_context(filepath, delimiter, print_operations)

            # Update statistics and global map
            self._update_component_stats(loaded_count)
            logger.info(f"Component {self.id}: Loaded {loaded_count} context variables from {filepath}")

            return {'main': pd.DataFrame()}

        except Exception as e:
            logger.error(f"Component {self.id}: Error loading context from {filepath}: {e}")
            raise

    def _load_csv_context(self, filepath: str, csv_separator: str, print_operations: bool) -> int:
        """
        Load context variables from CSV file

        Args:
            filepath (str): Path to CSV file
            csv_separator (str): CSV separator character
            print_operations (bool): Whether to log loaded operations

        Returns:
            int: Number of context variables loaded

        Raises:
            ValueError: If CSV doesn't have required columns
        """
        df = pd.read_csv(filepath, sep=csv_separator)

        # Validate required columns
        if 'key' not in df.columns or 'value' not in df.columns:
            raise ValueError("CSV must have 'key' and 'value' columns")

        loaded_count = 0

        # Process each row
        for _, row in df.iterrows():
            key = str(row['key']).strip()
            value = str(row['value'])

            # Determine value type
            value_type = self._determine_value_type(row, key, df.columns)

            # Set context variable
            if self.context_manager:
                self.context_manager.set(key, value, value_type)

            # Log operation if requested
            if print_operations:
                logger.info(f"Context loaded: {key} = {value} (type: {value_type})")

            loaded_count += 1

        return loaded_count

    def _load_properties_context(self, filepath: str, delimiter: str, print_operations: bool) -> int:
        """
        Load context variables from properties file

        Args:
            filepath (str): Path to properties file
            delimiter (str): Key-value delimiter
            print_operations (bool): Whether to log loaded operations

        Returns:
            int: Number of context variables loaded
        """
        loaded_count = 0

        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith('#') or line.startswith('//'):
                    continue

                # Parse key=value
                if delimiter in line:
                    key, value = line.split(delimiter, 1)
                    key = key.strip()
                    value = self._clean_value(value.strip())

                    # Get existing type from context manager
                    value_type = None
                    if self.context_manager and self.context_manager.get_type(key):
                        value_type = self.context_manager.get_type(key)
                        logger.debug(f"Component {self.id}: Using original type '{value_type}' for key '{key}'")

                    # Set context variable
                    if self.context_manager:
                        self.context_manager.set(key, value, value_type)

                    # Log operation if requested
                    if print_operations:
                        logger.info(f"Context loaded: {key} = {value} (type: {value_type})")

                    loaded_count += 1
                else:
                    logger.warning(f"Line {line_num}: Invalid format (missing '{delimiter}'): {line}")

        return loaded_count

    def _determine_value_type(self, row: pd.Series, key: str, columns: pd.Index) -> str:
        """
        Determine the appropriate type for a context variable

        Args:
            row (pd.Series): Current row data
            key (str): Context variable key
            columns (pd.Index): Available DataFrame columns

        Returns:
            str: Type identifier for the context variable
        """
        # Check if type is explicitly provided
        if 'type' in columns:
            return row.get('type', 'id_String')

        # Check existing context type
        if self.context_manager and self.context_manager.get_type(key):
            value_type = self.context_manager.get_type(key)
            logger.debug(f"Component {self.id}: Using original type '{value_type}' for key '{key}'")
            return value_type

        # Default to string type
        return 'id_String'

    def _clean_value(self, value: str) -> str:
        """
        Clean and normalize property values by removing quotes

        Args:
            value (str): Raw property value

        Returns:
            str: Cleaned property value
        """
        # Remove surrounding quotes if present
        if value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        elif value.startswith("'") and value.endswith("'"):
            return value[1:-1]
        return value

    def _update_component_stats(self, loaded_count: int) -> None:
        """
        Update component statistics and global map variables

        Args:
            loaded_count (int): Number of context variables loaded
        """
        # Update internal statistics
        self._update_stats(loaded_count, loaded_count, 0)

        # Store count in global map
        if self.global_map:
            self.global_map.put(f"{self.id}_NB_CONTEXT_LOADED", loaded_count)
