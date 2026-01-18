"""
tFileTouch component - creates an empty file at the specified path
"""
import os
from typing import Any, Dict, Optional
from ...base_component import BaseComponent

class FileTouch(BaseComponent):
    """
    Creates an empty file at the specified path.
    Equivalent to the Talend tFileTouch component.
    """

    def _process(self, input_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create an empty file at the specified path.

        Args:
            input_data (Optional[Dict[str, Any]]): Input data dictionary. Not used in this component.

        Returns:
            Dict[str, Any]: Output data dictionary with the file path.
        """
        filename = self.config.get("filename")
        create_dir = self.config.get("create_dir", False)

        try:
            if not filename:
                raise ValueError("Filename must be specified in the configuration.")
            
            directory = os.path.dirname(filename)

            if directory and not os.path.exists(directory):
                if create_dir:
                    os.makedirs(directory)
                else:
                    raise FileNotFoundError(f"Directory '{directory}' does not exist.")
                
            # Create the file or update its timestamp
            with open(filename, 'a'):
                os.utime(filename, None)
            
            self._update_stats(1,1,0)
            return {'status': "success", 'message': f"filename: {filename}"}

        except Exception as e:
            self._update_stats(0,0,1)
            return {'status': "error", 'message': str(e)}
        
    def validate_config(self) -> None:
        """
        Validate the component configuration.

        Returns:
            True if the configuration is valid, otherwise raises ValueError.
        """
        if 'filename' not in self.config:
            self.logger.error("Configuration error: 'filename' is required.")
            return False
        return True
