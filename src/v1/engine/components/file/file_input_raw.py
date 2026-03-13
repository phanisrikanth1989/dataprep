"""
TFileInputRaw - Reads raw data from a file as a single field.

Talend equivalent: tFileInputRaw
"""

import logging
from typing import Dict, Any, Optional, List
import pandas as pd

from ...base_component import BaseComponent

logger = logging.getLogger(__name__)

class FileInputRaw(BaseComponent):
    """
    Reads raw data from a file and outputs it as a single field.
    Equivalent to Talend's tFileInputRaw component.

    Configuration:
        filename (str): Path to the file to read. Required.
        as_string (bool): Read as string (True) or binary (False). Default: True
        encoding (str): File encoding when reading as string. Default: UTF-8
        die_on_error (bool): Stop execution on error. Default: False

    Inputs:
        None - This is a source component

    Outputs:
        main: DataFrame with single row containing 'content' column

    Statistics:
        NB_LINE: Always 1 (represents one file read)
        NB_LINE_OK: 1 if successful, 0 if failed
        NB_LINE_REJECT: Always 0

    Example configuration:
    {
        "filename": "/path/to/file.txt",
        "as_string": True,
        "encoding": "UTF-8",
        "die_on_error": False
    }
    """

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        if 'filename' not in self.config:
            errors.append("Missing required config: 'filename'")

        # Validate optional parameters if present
        if 'encoding' in self.config:
            encoding = self.config['encoding']
            if not isinstance(encoding, str) or not encoding.strip():
                errors.append("Config 'encoding' must be a non-empty string")

        if 'as_string' in self.config:
            as_string = self.config['as_string']
            if not isinstance(as_string, bool):
                errors.append("Config 'as_string' must be a boolean")

        if 'die_on_error' in self.config:
            die_on_error = self.config['die_on_error']
            if not isinstance(die_on_error, bool):
                errors.append("Config 'die_on_error' must be a boolean")

        return errors

    def debug_content(self, content: str) -> None:
        """
        Debug helper to understand content formatting issues.
        """
        logger.info(f"[{self.id}] Content length: {len(content)}")
        logger.info(f"[{self.id}] Content type: {type(content)}")
        logger.info(f"[{self.id}] First 200 chars (raw): {repr(content[:200])}")
        logger.info(f"[{self.id}] First 200 chars (display): {content[:200]}")

        # Check for different line ending types
        if '\r\n' in content:
            logger.info(f"[{self.id}] Contains Windows line endings (\\r\\n)")
        elif '\n' in content:
            logger.info(f"[{self.id}] Contains Unix line endings (\\n)")
        elif '\r' in content:
            logger.info(f"[{self.id}] Contains Mac line endings (\\r)")

        # Count line endings
        logger.info(f"[{self.id}] Line break counts: \\n={content.count('\\n')}, \\r={content.count('\\r')}")

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Read raw data from the specified file.

        Args:
            input_data: Not used for this component (source component).

        Returns:
            Dictionary containing:
                - 'main': DataFrame with single row and 'content' column containing file data
        """
        # Get configuration with defaults
        file_path = self.config.get('filename')
        as_string = self.config.get('as_string', True)
        encoding = self.config.get('encoding', 'UTF-8')
        die_on_error = self.config.get('die_on_error', False)

        logger.info(f"[{self.id}] Reading raw file: {file_path}")

        try:
            # Read file content - preserve exact original logic
            if as_string:
                with open(file_path, 'r', encoding=encoding) as file:
                    content = file.read()
            else:
                with open(file_path, 'rb') as file:
                    content = file.read()

            # Add debug information
            if isinstance(content, str):
                self.debug_content(content)

            # Convert to DataFrame while preserving original data structure
            result_df = pd.DataFrame([{'content': content}])

            # Update statistics - preserve original counting logic (1 file = 1 row)
            self._update_stats(1, 1, 0)

            logger.info(f"[{self.id}] File read complete: 1 file processed successfully")

            return {'main': result_df}

        except Exception as e:
            logger.error(f"[{self.id}] Failed to read file {file_path}: {e}")

            # Update statistics for failure
            self._update_stats(1, 0, 0)

            if die_on_error:
                raise

            # Return empty DataFrame on error (preserving original behavior)
            logger.warning(f"[{self.id}] Returning empty result due to error")
            return {'main': pd.DataFrame()}