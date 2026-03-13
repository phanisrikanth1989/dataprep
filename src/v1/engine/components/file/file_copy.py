"""
tFileCopy component - Copies files from source to destination

Talend equivalent: tFileCopy
"""
import os
import shutil
from typing import Dict, Any, List, Optional
import logging

from ...base_component import BaseComponent

logger = logging.getLogger(__name__)


class FileCopy(BaseComponent):
    """
    Copies files or directories from source to destination.

    Configuration:
        source (str): Source file or directory path. Required.
        destination (str): Destination file or directory path. Required.
        rename (bool): Whether to rename the copied file. Default: False
        new_name (str): New name for the copied file (if rename is True). Default: ''
        replace_file (bool): Whether to replace existing files. Default: True
        create_directory (bool): Whether to create destination directory if it doesn't exist. Default: True
        preserve_last_modified (bool): Whether to preserve last modified time. Default: False

    Inputs:
        None: This component does not process input data

    Outputs:
        main: Result dictionary with status and message

    Statistics:
        NB_LINE: Number of copy operations attempted (always 1)
        NB_LINE_OK: Number of successful copies
        NB_LINE_REJECT: Number of failed copies

    Example configuration:
    {
        "source": "/source/file.txt",
        "destination": "/dest/",
        "rename": True,
        "new_name": "newfile.txt",
        "replace_file": True
    }
    """

    def _process(self, input_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Perform the file copy operation based on the configuration.

        Args:
            input_data: Not used for this component

        Returns:
            Dictionary containing:
                - 'main': Result dictionary with status and message

        Raises:
            ValueError: If required configuration is missing
            FileNotFoundError: If source file doesn't exist
            FileExistsError: If destination exists and replace_file is False
        """
        # Get configuration with defaults
        source = self.config.get('source')
        destination = self.config.get('destination')
        rename = self.config.get('rename', False)
        new_name = self.config.get('new_name', '')
        replace_file = self.config.get('replace_file', True)
        create_directory = self.config.get('create_directory', True)
        preserve_last_modified = self.config.get('preserve_last_modified', False)

        logger.info(f"[{self.id}] Copy operation started: {source} -> {destination}")

        rows_processed = 1
        result = {'status': 'error', 'message': ''}

        try:
            if not source or not destination:
                error_msg = "Source and destination paths must be provided"
                logger.error(f"[{self.id}] {error_msg}")
                raise ValueError(f"[{self.id}] {error_msg}")

            if not os.path.exists(source):
                error_msg = f"Source path does not exist: {source}"
                logger.error(f"[{self.id}] {error_msg}")
                raise FileNotFoundError(f"[{self.id}] {error_msg}")

            # Create destination directory if needed
            if not os.path.exists(destination) and create_directory:
                logger.debug(f"[{self.id}] Creating destination directory: {destination}")
                os.makedirs(destination)

            # Handle renaming
            final_destination = destination
            if rename and new_name:
                final_destination = os.path.join(destination, new_name)
                logger.debug(f"[{self.id}] Renaming to: {new_name}")

            # Check if destination exists
            if os.path.exists(final_destination) and not replace_file:
                error_msg = f"Destination already exists and replace_file is False: {final_destination}"
                logger.error(f"[{self.id}] {error_msg}")
                raise FileExistsError(f"[{self.id}] {error_msg}")

            # Perform the copy operation
            if os.path.isdir(source):
                logger.debug(f"[{self.id}] Copying directory: {source} -> {final_destination}")
                shutil.copytree(source, final_destination, dirs_exist_ok=replace_file)
            else:
                logger.debug(f"[{self.id}] Copying file: {source} -> {final_destination}")
                shutil.copy2(source, final_destination)

            # Preserve last modified time if requested
            if preserve_last_modified:
                logger.debug(f"[{self.id}] Preserving last modified time")
                shutil.copystat(source, final_destination)

            # Update statistics and create result
            self._update_stats(rows_processed, 1, 0)
            result = {'status': 'success', 'message': f"Copied {source} to {final_destination}"}

            logger.info(f"[{self.id}] Copy operation complete: "
                f"processed={rows_processed}, success=1, failed=0")

        except Exception as e:
            logger.error(f"[{self.id}] Copy operation failed: {e}")
            self._update_stats(rows_processed, 0, 1)
            result = {'status': 'error', 'message': str(e)}

        return {'main': result}