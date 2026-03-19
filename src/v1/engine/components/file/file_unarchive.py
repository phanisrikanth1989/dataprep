"""
FileUnarchive component - Extracts files or directories from an archive.

Talend equivalent: tFileUnarchive
"""
import logging
import os
import zipfile
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent

logger = logging.getLogger(__name__)


class FileUnarchiveComponent(BaseComponent):
    """
    Extracts files or directories from archive formats (ZIP).

    This component extracts files from archive files to specified directories,
    supporting ZIP archives with optional password protection.

    Configuration:
        zipfile (str): Path to the archive file to extract. Required.
        directory (str): Output directory for extracted files. Required.
        extract_path (bool): Extract with full directory structure. Default: True
        check_password (bool): Use password protection. Default: False
        password (str): Password for protected archives. Default: None
        die_on_error (bool): Fail on error. Default: True

    Inputs:
        main: Not used (extraction operation is independent of input data)

    Outputs:
        main: Empty DataFrame (this component produces files, not data flows)

    Statistics:
        NB_LINE: Always 1 (represents one extraction operation)
        NB_LINE_OK: 1 if successful, 0 if failed
        NB_LINE_REJECT: 0 (not applicable)

    Example configuration:
        {
            "zipfile": "/archives/data.zip",
            "directory": "/data/extracted",
            "extract_path": True,
            "check_password": False,
            "password": None
        }

    Notes:
        - Creates output directory if it doesn't exist
        - Supports password-protected ZIP archives
        - Only ZIP format is currently supported
        - Preserves directory structure when extract_path is True
    """

    # Class constants
    DEFAULT_EXTRACT_PATH = True
    DEFAULT_CHECK_PASSWORD = False
    DEFAULT_DIE_ON_ERROR = True

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Required fields
        if not self.config.get('zipfile'):
            errors.append("Missing required config: 'zipfile'")

        if not self.config.get('directory'):
            errors.append("Missing required config: 'directory'")

        # Optional field validation
        zipfile_path = self.config.get('zipfile')
        if zipfile_path and not isinstance(zipfile_path, str):
            errors.append("Config 'zipfile' must be a string path")

        directory = self.config.get('directory')
        if directory and not isinstance(directory, str):
            errors.append("Config 'directory' must be a string path")

        check_password = self.config.get('check_password', self.DEFAULT_CHECK_PASSWORD)
        if not isinstance(check_password, bool):
            errors.append("Config 'check_password' must be a boolean")

        extract_path = self.config.get('extract_path', self.DEFAULT_EXTRACT_PATH)
        if not isinstance(extract_path, bool):
            errors.append("Config 'extract_path' must be a boolean")

        return errors

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Process archive extraction.

        Args:
            input_data: Input DataFrame (not used for this component)

        Returns:
            Dictionary with empty main output (file operation component)

        Raises:
            FileNotFoundError: If archive file doesn't exist
            zipfile.BadZipFile: If archive is corrupted
            RuntimeError: If password is required but not provided
        """
        logger.info(f"[{self.id}] Archive extraction started")

        try:
            # Get configuration with defaults
            zipfile_path = self.config.get('zipfile')
            output_directory = self.config.get('directory')
            extract_path = self.config.get('extract_path', self.DEFAULT_EXTRACT_PATH)
            check_password = self.config.get('check_password', self.DEFAULT_CHECK_PASSWORD)
            password = self.config.get('password', None)
            die_on_error = self.config.get('die_on_error', self.DEFAULT_DIE_ON_ERROR)

            # Validate source archive exists
            if not os.path.exists(zipfile_path):
                error_msg = f"Archive file does not exist: {zipfile_path}"
                logger.error(f"[{self.id}] {error_msg}")
                if die_on_error:
                    raise FileNotFoundError(error_msg)
                else:
                    logger.warning(f"[{self.id}] Continuing with error, returning empty result")
                    self._update_stats(1, 0, 1)
                    return {'main': pd.DataFrame()}

            # Create output directory if it doesn't exist
            if not os.path.exists(output_directory):
                logger.debug(f"[{self.id}] Creating output directory: {output_directory}")
                os.makedirs(output_directory)

            # Extract files from the archive
            files_extracted = 0
            logger.debug(f"[{self.id}] Opening ZIP archive: {zipfile_path}")

            with zipfile.ZipFile(zipfile_path, 'r') as archive:
                # Set password if required
                if check_password and password:
                    logger.debug(f"[{self.id}] Setting password for protected archive")
                    archive.setpassword(password.encode())

                # Extract files
                if extract_path:
                    logger.debug(f"[{self.id}] Extracting all files with directory structure")
                    archive.extractall(output_directory)
                    files_extracted = len(archive.namelist())
                else:
                    logger.debug(f"[{self.id}] Extracting files without directory structure")
                    for file in archive.namelist():
                        archive.extract(file, output_directory)
                        files_extracted += 1
                        logger.debug(f"[{self.id}] Extracted file: {file}")

            # Update statistics and log success
            self._update_stats(1, 1, 0)
            logger.info(f"[{self.id}] Archive extraction complete: "
                        f"{files_extracted} files extracted to {output_directory}")

            return {'main': pd.DataFrame()}

        except Exception as e:
            logger.error(f"[{self.id}] Archive extraction failed: {e}")
            self._update_stats(1, 0, 1)

            # Re-raise if die_on_error is True
            if self.config.get('die_on_error', self.DEFAULT_DIE_ON_ERROR):
                raise
            else:
                # Return empty result if continuing on error
                return {'main': pd.DataFrame()}
