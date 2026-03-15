"""
FileInputFullRow - Read each row of a file as a single string

Talend equivalent: tFileInputFullRow

This component reads each row of a file as a single string, with configurable
row separators and filtering options. Each row becomes a single column value
in the output DataFrame.
"""
import logging
import os
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent

logger = logging.getLogger(__name__)


class FileInputFullRow(BaseComponent):
    """
    Read each row of a file as a single string.

    Configuration:
        filename (str): Path to input file. Required.
        row_separator (str): Row separator character/string. Default: '\n'
        remove_empty_row (bool): Remove empty rows from output. Default: False
        encoding (str): File encoding. Default: 'UTF-8'
        limit (str): Maximum number of rows to read. Default: None (no limit)
        die_on_error (bool): Fail on error vs continue. Default: True

    Inputs:
        None (file input component)

    Outputs:
        main: DataFrame with single column 'line' containing each file row

    Statistics:
        NB_LINE: Total rows read from file
        NB_LINE_OK: Successfully processed rows
        NB_LINE_REJECT: Rejected rows (always 0 for this component)

    Example Configuration:
        {
            "filename": "data/input.txt",
            "row_separator": "\\n",
            "remove_empty_row": true,
            "encoding": "UTF-8",
            "limit": "1000"
        }

    Notes:
        - Each fle row becomes a single string value in the 'line' column of the output DataFrame.
        - Row separators can be multi-character strings (e.g., "\\r\\n" or custom delimiters).
        - Quote stripping is applied to row_separator configuration to allow for common escape sequences.
        - Empty rows are preserved by default but can be removed with the remove_empty_row option.
        - If the file does not exist and die_on_error is False, an empty DataFrame is returned.        
    """

    def _validate_config(self) -> List[str]:
        """Validate component configuration."""
        errors = []

        # Required fields
        if 'filename' not in self.config:
            errors.append("Missing required config: 'filename'")
        elif not self.config['filename']:
            errors.append("Config 'filename' cannot be empty")

        # Optional field validation
        if 'encoding' in self.config:
            encoding = self.config['encoding']
            if not isinstance(encoding, str):
                errors.append("Config 'encoding' must be a string")

        if 'limit' in self.config:
            limit = self.config['limit']
            if limit is not None and limit != '':
                if not str(limit).isdigit():
                    errors.append("Config 'limit' must be a numeric string or empty")

        return errors

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Read each row of the file as a single string.

        Args:
            input_data (pd.DataFrame, optional): Not used for file input component.
        
        Returns:
            Dict[str, Any]: Output data with key 'main' containing the resulting DataFrame.
        """
        # Validate configuration
        config_errors = self._validate_config()
        if config_errors:
            error_msg = "; ".join(config_errors)
            logger.error(f"[{self.id}] Configuration validation failed: {error_msg}")
            if self.config.get('die_on_error', True):
                raise ValueError(f"[{self.id}] {error_msg}")
            else:
                self._update_stats(0, 0, 0)
                return {'main': pd.DataFrame()}

        try:
            # Extract configuration with defaults
            filename = self.config.get('filename')
            row_separator = self.config.get('row_separator', '\n')

            # Remove quotes from row_separator if present
            if row_separator.startswith('"') and row_separator.endswith('"'):
                row_separator = row_separator[1:-1]

            # Decode escape sequences
            row_separator = row_separator.encode().decode('unicode_escape')

            remove_empty_row = self.config.get('remove_empty_row', False)
            encoding = self.config.get('encoding', 'UTF-8')
            limit = self.config.get('limit', None)
            die_on_error = self.config.get('die_on_error', True)

            logger.info(f"[{self.id}] Reading file: {filename}")
            logger.debug(f"[{self.id}] Config - row_separator: '{row_separator}', "
                         f"remove_empty_row: {remove_empty_row}, encoding: {encoding}, limit: {limit}")

            # Validate file existence
            if not os.path.exists(filename):
                error_msg = f"File not found: {filename}"
                logger.error(f"[{self.id}] {error_msg}")
                if die_on_error:
                    raise FileNotFoundError(f"[{self.id}] {error_msg}")
                else:
                    logger.warning(f"[{self.id}] {error_msg}, returning empty result")
                    self._update_stats(0, 0, 0)
                    return {'main': pd.DataFrame()}

            # Read the file
            with open(filename, 'r', encoding=encoding) as file:
                file_content = file.read()

            # Normalize CRLF
            file_content = file_content.replace('\r\n', '\n')

            # Split into rows
            lines = file_content.split(row_separator)

            logger.debug(f"[{self.id}] Read {len(lines)} raw lines from file")

            # Remove empty rows if configured
            if remove_empty_row:
                original_count = len(lines)
                lines = [line for line in lines if line.strip()]
                logger.debug(f"[{self.id}] Removed {original_count - len(lines)} empty rows")

            # Apply limit
            if limit and str(limit).isdigit():
                limit_val = int(limit)
                if len(lines) > limit_val:
                    lines = lines[:limit_val]
                    logger.debug(f"[{self.id}] Applied limit: kept first {limit_val} rows")

            # Prepare DataFrame
            output_data = [{'line': line} for line in lines]
            df = pd.DataFrame(output_data)

            # Update statistics
            rows_processed = len(output_data)
            self._update_stats(rows_processed, rows_processed, 0)

            logger.info(f"[{self.id}] Processing complete: {rows_processed} rows from {filename}")
            logger.debug(f"[{self.id}] Output DataFrame shape: {df.shape}, columns: {list(df.columns)}")

            return {'main': df}

        except FileNotFoundError:
            #Re-raise to be handled by caller based on die_on_error config
            raise
        except Exception as e:
            error_msg = f"Failed to process file: {str(e)}"
            logger.error(f"[{self.id}] {error_msg}")

            if self.config.get('die_on_error', True):
                raise RuntimeError(f"[{self.id}] {error_msg}") from e
            else:
                logger.warning(f"[{self.id}] {error_msg}, returning empty result")
                self._update_stats(0, 0, 0)
                return {'main': pd.DataFrame()}


    def validate_config(self) -> bool:
        """
        Validates the component configuration.
        """

        try:
            errors = self._validate_config()
            if errors:
                error_msg = "; ".join(errors)
                logger.error(f"[{self.id}] Configuration validation failed: {error_msg}")
                return False
            return True
        except Exception:
            logger.error(f"[{self.id}] Exception during configuration validation")
            return False