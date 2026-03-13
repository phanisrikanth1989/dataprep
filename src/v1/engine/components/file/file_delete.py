"""
tFileDelete component - Delete files or directories

Talend equivalent: tFileDelete
"""
import os
import shutil
from typing import Dict, Any, List, Optional
import logging

from ...base_component import BaseComponent

logger = logging.getLogger(__name__)


class FileDelete(BaseComponent):
    """
    Delete files or directories from the filesystem.

    Configuration:
        path (str): File or directory path to delete. Required.
        fail_on_error (bool): Whether to fail if deletion encounters error. Default: True
        is_directory (bool): Whether to treat path as directory. Default: False
        is_folder_file (bool): Whether to delete file or directory, whichever exists. Default: False
        recursive (bool): Whether to delete directories recursively. Default: False

    Inputs:
        None: This component does not process input data

    Outputs:
        main: None (no data output)
        status: Status message string

    Statistics:
        NB_LINE: Number of items processed (1 if deleted, 0 if not)
        NB_LINE_OK: Number of successful deletions
        NB_LINE_REJECT: Number of failed deletions

    Example configuration:
    {
        "path": "/tmp/file.txt",
        "fail_on_error": True,
        "is_directory": False,
        "recursive": False
    }
    """

    def _process(self, input_data: Optional[Any] = None) -> Dict[str, Any]:
        """
        Delete the specified file or directory based on the configuration.

        Args:
            input_data: Not used for this component

        Returns:
            Dictionary containing:
                - 'main': None (no data output)
                - 'status': Status message string

        Raises:
            ValueError: If required configuration is missing
            FileOperationError: If deletion fails and fail_on_error is True
        """
        # Get configuration with defaults
        path = self.config.get('path', '')
        fail_on_error = self.config.get('fail_on_error', True)
        is_directory = self.config.get('is_directory', False)
        is_folder_file = self.config.get('is_folder_file', False)
        recursive = self.config.get('recursive', False)

        logger.info(f"[{self.id}] Delete operation started: {path}")

        status_message = ""
        deleted = False
        rows_processed = 0

        if not path:
            error_msg = "Missing required config: 'path'"
            logger.error(f"[{self.id}] {error_msg}")
            raise ValueError(f"[{self.id}] {error_msg}")

        try:
            rows_processed = 1

            # FOLDER_FILE: delete file or directory, whichever exists
            if is_folder_file:
                if os.path.isfile(path):
                    os.remove(path)
                    logger.info(f"[{self.id}] File deleted: {path}")
                    status_message = "File (or path) deleted."
                    deleted = True
                elif os.path.isdir(path):
                    if recursive:
                        shutil.rmtree(path)
                    else:
                        os.rmdir(path)
                    logger.info(f"[{self.id}] Directory deleted: {path}")
                    status_message = "File (or path) deleted."
                    deleted = True
                else:
                    logger.warning(f"[{self.id}] File or directory does not exist: {path}")
                    status_message = "File (or path) does not exist or is invalid."
            elif is_directory:
                # Delete directory
                if os.path.isdir(path):
                    if recursive:
                        shutil.rmtree(path)
                    else:
                        os.rmdir(path)
                    logger.info(f"[{self.id}] Directory deleted: {path}")
                    status_message = "File (or path) deleted."
                    deleted = True
                else:
                    logger.warning(f"[{self.id}] Directory does not exist: {path}")
                    status_message = "File (or path) does not exist or is invalid."
            else:
                # Delete file
                if os.path.isfile(path):
                    os.remove(path)
                    logger.info(f"[{self.id}] File deleted: {path}")
                    status_message = "File (or path) deleted."
                    deleted = True
                else:
                    logger.warning(f"[{self.id}] File does not exist: {path}")
                    status_message = "File (or path) does not exist or is invalid."

            # Update statistics
            rows_ok = 1 if deleted else 0
            rows_reject = 0 if deleted else 1
            self._update_stats(rows_processed, rows_ok, rows_reject)

            logger.info(f"[{self.id}] Delete operation complete: "
                        f"processed={rows_processed}, success={rows_ok}, failed={rows_reject}")

        except Exception as e:
            logger.error(f"[{self.id}] Error deleting {path}: {e}")
            status_message = f"Error: {e}"
            self._update_stats(rows_processed, 0, 1)
            if fail_on_error:
                raise

        return {'main': None, 'status': status_message}

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Required fields
        if 'path' not in self.config:
            errors.append("Missing required config: 'path'")
        elif not isinstance(self.config['path'], str):
            errors.append("Config 'path' must be a non-empty string")

        # Optional fields validation
        if 'fail_on_error' in self.config:
            if not isinstance(self.config['fail_on_error'], bool):
                errors.append("Config 'fail_on_error' must be a boolean")

        if 'is_directory' in self.config:
            if not isinstance(self.config['is_directory'], bool):
                errors.append("Config 'is_directory' must be a boolean")

        if 'is_folder_file' in self.config:
            if not isinstance(self.config['is_folder_file'], bool):
                errors.append("Config 'is_folder_file' must be a boolean")
        
        if 'recursive' in self.config:
            if not isinstance(self.config['recursive'], bool):
                errors.append("Config 'recursive' must be a boolean")
        
        return errors