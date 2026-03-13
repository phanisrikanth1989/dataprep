"""
tFileTouch component - Creates an empty file at the specified location

Talend equivalent: tFileTouch
"""
import os
from typing import Dict, Any, List, Optional
import logging

from ...base_component import BaseComponent

logger = logging.getLogger(__name__)

class FileTouch(BaseComponent):
    """
    Creates an empty file at the specified location or updates its timestamp.

    Configuration:
        filename (str): Path to the file to create or touch. Required.
        create_directory (bool): Whether to create parent directories if they don't exist. Default: False

    Inputs:
        None: This component does not process input data

    Outputs:
        main: Result dictionary with status and message

    Statistics:
        NB_LINE: Number of touch operations attempted (always 1)
        NB_LINE_OK: Number of successful file touches
        NB_LINE_REJECT: Number of failed file touches

    Example configuration:
    {
        "filename": "/path/to/file.txt",
        "create_directory": True
    }
    """

    def _process(self, input_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Perform the file touch operation based on the configuration.

        Args:
            input_data: Not used for this component

        Returns:
            Dictionary containing:
                - 'main': Result dictionary with status and message

        Raises:
            ValueError: If required configuration is missing
            FileNotFoundError: If directory doesn't exist and create_directory is False
        """
        # Get configuration with defaults
        filename = self.config.get('filename')
        create_directory = self.config.get('create_directory', False)

        logger.info(f"[{self.id}] Touch operation started: {filename}")

        rows_processed = 1
        result = {'status': 'error', 'message': ''}

        try:
            if not filename:
                error_msg = "Missing required config: 'filename'"
                logger.error(f"[{self.id}] {error_msg}")
                raise ValueError(f"[{self.id}] {error_msg}")

            # Get directory path
            directory = os.path.dirname(filename)

            # Check and create directory if needed
            if directory and not os.path.exists(directory):
                if create_directory:
                    logger.debug(f"[{self.id}] Creating directory: {directory}")
                    os.makedirs(directory)
                else:
                    error_msg = f"Directory does not exist: {directory}"
                    logger.error(f"[{self.id}] {error_msg}")
                    raise FileNotFoundError(f"[{self.id}] {error_msg}")

            # Create the file or update its timestamp
            logger.debug(f"[{self.id}] Touching file: {filename}")
            with open(filename, 'a'):
                os.utime(filename, None)

            # Update statistics and create result
            self._update_stats(rows_processed, 1, 0)
            result = {'status': 'success', 'message': f"File touched: {filename}"}

            logger.info(f"[{self.id}] Touch operation complete: "
                        f"processed={rows_processed}, success=1, failed=0")

        except Exception as e:
            logger.error(f"[{self.id}] Touch operation failed: {e}")
            self._update_stats(rows_processed, 0, 1)
            result = {'status': 'error', 'message': str(e)}

        return {'main': result}