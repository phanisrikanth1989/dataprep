"""
FileArchive component - Compresses files or directories into an archive format.

Talend equivalent: tFileArchive
"""

import logging
import os
import zipfile
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent

logger = logging.getLogger(__name__)

class FileArchiveComponent(BaseComponent):
    """
    Compresses files or directories into archive formats (ZIP).

    This component creates archive files from source files or directories,
    supporting ZIP compression with configurable compression levels.

    Configuration:
        source (str): Source file or directory path. Required.
        target (str): Target archive file path. Required.
        archive_format (str): Archive format ('zip'). Default: 'zip'.
        include_subdirectories (bool): Include subdirectories in archive. Default: True
        overwrite (bool): Overwrite existing target archive. Default: True
        compression_level (int): Compression level (0-9). Default: 4
        die_on_error (bool): Fail on error. Default: True

    Inputs:
        main: Not used (archive operation is independent of input data)

    Outputs:
        main: Empty DataFrame (this component produces files, not data flows)

    Statistics:
        NB_LINE: Always 1 (represents one archive operation)
        NB_LINE_OK: 1 if successful, 0 if failed
        NB_LINE_REJECT: 0 (not applicable)

    Example configuration:
    {
        "source": "/data/input",
        "target": "/archives/backup.zip",
        "archive_format": "zip",
        "compression_level": 6,
        "include_subdirectories": True,
        "overwrite": True
    }

    Notes:
        - Creates target directory if it doesn't exist
        - Supports both file and directory archiving
        - Only ZIP format is currently supported
    """

    # Class constants
    DEFAULT_COMPRESSION_LEVEL = 4
    DEFAULT_ARCHIVE_FORMAT = 'zip'
    SUPPORTED_FORMATS = ['zip']

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Required fields
        if not self.config.get('source'):
            errors.append("Missing required config: 'source'")

        if not self.config.get('target'):
            errors.append("Missing required config: 'target'")

        # Optional field validation
        archive_format = self.config.get('archive_format', self.DEFAULT_ARCHIVE_FORMAT)
        if archive_format not in self.SUPPORTED_FORMATS:
            errors.append(f"Config 'archive_format' must be one of {self.SUPPORTED_FORMATS}, got '{archive_format}'")

        compression_level = self.config.get('compression_level', self.DEFAULT_COMPRESSION_LEVEL)
        try:
            level = int(compression_level)
            if level < 0 or level > 9:
                errors.append("Config 'compression_level' must be between 0 and 9")
        except (ValueError, TypeError):
            errors.append("Config 'compression_level' must be a valid integer")

        return errors

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Process archive creation.

        Args:
            input_data: Input DataFrame (not used for this component)

        Returns:
            Dictionary with empty main output (file operation component)

        Raises:
            FileNotFoundError: If source path doesn't exist
            FileExistsError: If target exists and overwrite is False
            NotImplementedError: If unsupported archive format is specified
        """
        logger.info(f"[{self.id}] Archive processing started")

        try:
            # Get configuration with defaults
            source = self.config.get('source')
            target = self.config.get('target')
            archive_format = self.config.get('archive_format', self.DEFAULT_ARCHIVE_FORMAT)
            include_subdirectories = self.config.get('include_subdirectories', True)
            overwrite = self.config.get('overwrite', True)
            compression_level = int(self.config.get('compression_level', self.DEFAULT_COMPRESSION_LEVEL))
            die_on_error = self.config.get('die_on_error', True)

            # Validate source exists
            if not os.path.exists(source):
                error_msg = f"Source path does not exist: {source}"
                logger.error(f"[{self.id}] {error_msg}")
                if die_on_error:
                    raise FileNotFoundError(error_msg)
                else:
                    logger.warning(f"[{self.id}] Continuing with error, returning empty result")
                    self._update_stats(1, 0, 0)
                    return {'main': pd.DataFrame()}

            # Create target directory if needed
            target_dir = os.path.dirname(target)
            if target_dir and not os.path.exists(target_dir):
                logger.debug(f"[{self.id}] Creating target directory: {target_dir}")
                os.makedirs(target_dir)

            # Check if target file exists
            if os.path.exists(target) and not overwrite:
                error_msg = f"Target archive already exists: {target}"
                logger.error(f"[{self.id}] {error_msg}")
                if die_on_error:
                    raise FileExistsError(error_msg)
                else:
                    logger.warning(f"[{self.id}] Skipping archive creation, target exists")
                    self._update_stats(1, 0, 0)
                    return {'main': pd.DataFrame()}

            # Create archive
            files_archived = 0
            if archive_format == 'zip':
                compression = zipfile.ZIP_DEFLATED if compression_level > 0 else zipfile.ZIP_STORED
                logger.debug(f"[{self.id}] Creating ZIP archive with compression level {compression_level}")

                with zipfile.ZipFile(target, 'w', compression=compression) as archive:
                    if os.path.isdir(source):
                        logger.debug(f"[{self.id}] Archiving directory: {source}")
                        for root, dirs, files in os.walk(source):
                            if not include_subdirectories:
                                dirs.clear()
                            for file in files:
                                file_path = os.path.join(root, file)
                                archive_name = os.path.relpath(file_path, source)
                                archive.write(file_path, archive_name)
                                files_archived += 1
                                logger.debug(f"[{self.id}] Added file: {archive_name}")
                    else:
                        logger.debug(f"[{self.id}] Archiving single file: {source}")
                        archive.write(source, os.path.basename(source))
                        files_archived = 1
            else:
                error_msg = f"Archive format '{archive_format}' is not supported. Supported formats: {self.SUPPORTED_FORMATS}"
                logger.error(f"[{self.id}] {error_msg}")
                raise NotImplementedError(error_msg)

            # Update statistics and log success
            self._update_stats(1, 1, 0)
            logger.info(f"[{self.id}] Archive processing complete: {files_archived} files archived to {target}")

            return {'main': pd.DataFrame()}

        except Exception as e:
            logger.error(f"[{self.id}] Archive processing failed: {e}")
            self._update_stats(1, 0, 1)

            # Re-raise if die_on_error is True
            if self.config.get('die_on_error', True):
                raise
            else:
                # Return empty result if continuing on error
                return {'main': pd.DataFrame()}