"""
tFileExist component - Checks if a file exists at a specified path

Talend equivalent: tFileExist
"""

import os
from typing import Dict, Any, List, Optional
import logging

from ...base_component import BaseComponent

logger = logging.getLogger(__name__)

class FileExistComponent(BaseComponent):
    """
    Checks if a file or directory exists at the specified path.

    Configuration:
        file_path (str): Path to the file or directory to check. Required.
        check_directory (bool): Whether to check for directory existence specifically. Default: False

    Inputs:
        None: This component does not process input data

    Outputs:
        main: Dictionary containing file existence status

    Statistics:
        NB_LINE: Number of existence checks performed (always 1)
        NB_LINE_OK: Number of successful checks (always 1)
        NB_LINE_REJECT: Number of failed checks (always 0)

    Example configuration:
    {
        "file_path": "/path/to/file.txt",
        "check_directory": false
    }

    Notes:
        - Also accepts legacy 'FILE_NAME' parameter for backward compatibility
        - Returns file_exists boolean in the result dictionary
    """

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Check for either new or legacy parameter
        file_path = self.config.get('file_path') or self.config.get('FILE_NAME')

        if not file_path:
            errors.append("Missing required config: 'file_path' (or legacy 'FILE_NAME')")
        elif not isinstance(file_path, str):
            errors.append("Config 'file_path' must be a string")
        elif not file_path.strip():
            errors.append("Config 'file_path' cannot be empty")

        # Optional field validation
        if 'check_directory' in self.config:
            if not isinstance(self.config['check_directory'], bool):
                errors.append("Config 'check_directory' must be a boolean")

        return errors

    def _process(self, input_data: Optional[Any] = None) -> Dict[str, Any]:
        """
        Check if the file or directory exists.

        Args:
            input_data: Not used for this component

        Returns:
            Dictionary containing:
                - 'main': Dictionary with file_exists boolean status

        Raises:
            ValueError: If required configuration is missing
        """
        # Support both new and legacy parameter names for backward compatibility
        file_path = self.config.get('file_path') or self.config.get('FILE_NAME')
        check_directory = self.config.get('check_directory', False)

        logger.info(f"[{self.id}] File existence check started: {file_path}")

        rows_processed = 1

        if not file_path:
            error_msg = "Missing required config: 'file_path' (or legacy 'FILE_NAME')"
            logger.error(f"[{self.id}] {error_msg}")
            raise ValueError(f"[{self.id}] {error_msg}")

        try:
            # Perform existence check
            if check_directory:
                file_exists = os.path.isdir(file_path)
                check_type = "directory"
            else:
                file_exists = os.path.exists(file_path)
                check_type = "file/directory"

            # Update statistics - existence checks always succeed as operations
            self._update_stats(rows_processed, 1, 0)

            result = {'file_exists': file_exists}

            logger.info(f"[{self.id}] File existence check complete: "
                        f"{check_type} '{file_path}' exists={file_exists}")

        except Exception as e:
            logger.error(f"[{self.id}] File existence check failed: {e}")
            self._update_stats(rows_processed, 0, 1)
            raise

        return {'main': result}