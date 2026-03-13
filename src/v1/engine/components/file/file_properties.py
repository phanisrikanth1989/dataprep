"""
FileProperties - Extracts file metadata such as size, last modified time, etc.

Talend equivalent: tFileProperties
"""

import hashlib
import logging
import os
import pandas as pd  # Add pandas import
from datetime import datetime
from typing import Any, Dict, List, Optional

from ...base_component import BaseComponent
from ...exceptions import ConfigurationError, FileOperationError

logger = logging.getLogger(__name__)

class FileProperties(BaseComponent):
    """
    Extracts file metadata such as size, last modified time, and directory information.

    This component analyzes a file and returns various properties including path information,
    file size, modification time, and optionally MD5 checksum.

    Configuration:
        FILENAME (str): Path to the file to analyze. Required.
        MD5 (bool): Whether to calculate MD5 checksum. Default: False

    Inputs:
        None: This component does not process input data

    Outputs:
        main: Dictionary containing file properties:
            - abs_path: Absolute path to the file
            - dirname: Directory name containing the file
            - basename: Base name of the file
            - mode_string: File mode as octal string
            - size: File size in bytes
            - mtime: Modification time as timestamp
            - mtime_string: Modification time as formatted string
            - md5: MD5 checksum (if MD5=true)

    Statistics:
        NB_LINE: Always 1 (one file analyzed)
        NB_LINE_OK: 1 if successful, 0 if failed
        NB_LINE_REJECT: Always 0

    Example configuration:
    {
        "FILENAME": "/path/to/file.txt",
        "MD5": true
    }

    Notes:
        - File must exist or FileOperationError will be raised
        - MD5 calculation can be time-consuming for large files
    """

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Required fields
        if 'FILENAME' not in self.config:
            errors.append("Missing required config: 'FILENAME'")
        elif not self.config['FILENAME']:
            errors.append("Config 'FILENAME' cannot be empty")

        # Optional field validation
        if 'MD5' in self.config:
            md5_value = self.config['MD5']
            if not isinstance(md5_value, bool):
                errors.append("Config 'MD5' must be a boolean")

        return errors

    def _process(self, input_data: Optional[Any] = None) -> Dict[str, Any]:
        """
        Extract file properties based on the configuration.

        Args:
            input_data: Not used for this component

        Returns:
            Dictionary with file properties in 'main' key

        Raises:
            ConfigurationError: If FILENAME is missing or empty
            FileOperationError: If file does not exist or cannot be accessed
        """
        logger.info(f"[{self.id}] Processing started: analyzing file properties")

        try:
            # Get configuration with validation
            file_path = self.config.get('FILENAME', '')
            calculate_md5 = self.config.get('MD5', False)

            if not file_path:
                logger.error(f"[{self.id}] FILENAME is required in configuration")
                raise ConfigurationError("FILENAME is required in the configuration.")

            if not os.path.exists(file_path):
                logger.error(f"[{self.id}] File not found: {file_path}")
                raise FileOperationError(f"File not found: {file_path}")

            logger.debug(f"[{self.id}] Analyzing file: {file_path}")

            # Extract file properties (maintain exact same functionality)
            file_properties = {
                'abs_path': os.path.abspath(file_path),
                'dirname': os.path.dirname(file_path),
                'basename': os.path.basename(file_path),
                'mode_string': oct(os.stat(file_path).st_mode),
                'size': os.path.getsize(file_path),
                'mtime': os.path.getmtime(file_path),
                'mtime_string': self._format_time(os.path.getmtime(file_path))
            }

            if calculate_md5:
                logger.debug(f"[{self.id}] Calculating MD5 checksum")
                file_properties['md5'] = self._calculate_md5(file_path)

            # Update stats (maintain exact same behavior: 1, 1, 0)
            self._update_stats(1, 1, 0)

            # Convert dictionary to DataFrame for compatibility with other components
            result_df = pd.DataFrame([file_properties])

            logger.info(f"[{self.id}] Processing complete: "
                        f"analyzed file {os.path.basename(file_path)}, "
                        f"size {file_properties['size']} bytes")

            return {'main': result_df}  # Return DataFrame instead of dictionary

        except (ConfigurationError, FileOperationError):
            # Re-raise our custom exceptions as-is
            raise
        except Exception as e:
            logger.error(f"[{self.id}] Processing failed: {e}")
            raise FileOperationError(f"Failed to analyze file properties: {e}") from e

    def _calculate_md5(self, file_path: str) -> str:
        """
        Calculate the MD5 checksum of the file.

        Args:
            file_path: Path to the file

        Returns:
            MD5 checksum as hexadecimal string

        Raises:
            FileOperationError: If file cannot be read
        """
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            raise FileOperationError(f"Failed to calculate MD5 for {file_path}: {e}") from e

    def _format_time(self, timestamp: float) -> str:
        """
        Format the timestamp into a human-readable string.

        Args:
            timestamp: Unix timestamp

        Returns:
            Formatted time string in 'YYYY-MM-DD HH:MM:SS' format
        """
        return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')