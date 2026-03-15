"""
tJavaRow component - Execute Java/Groovy code on each row

This component mimics Talend's tJavaRow functionality:
- Executes custom Java/Groovy code for each row
- Provides input_row and output_row objects
- Access to context and globalMap
- Automatic parallelization for performance
"""

from typing import Any, Dict, Optional
import pandas as pd

import logging
from ...base_component import BaseComponent

logger = logging.getLogger(__name__)

class JavaRowComponent(BaseComponent):
    """
    Execute Java/Groovy code on DataFrame rows

    Config parameters:
    - java_code: Java/Groovy code to execute for each row
    - output_schema: Dictionary mapping output column names to types

    Example java_code:
        // Access input columns
        String firstName = (String) input_row.get("first_name");
        Integer age = (Integer) input_row.get("age");

        // Set output columns
        output_row.set("full_name", firstName + " " + lastName);
        output_row.set("is_adult", age >= 18);
    """

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Execute Java code on each row"""

        if input_data is None or input_data.empty:
            logger.warning(f"Component {self.id}: No input data")
            return {'main': pd.DataFrame()}

        # Get configuration
        java_code = self.config.get('java_code', '')
        imports = self.config.get('imports', '')
        output_schema = self.config.get('output_schema', {})

        if not java_code:
            raise ValueError(f"Component {self.id}: 'java_code' is required")

        if not output_schema:
            raise ValueError(f"Component {self.id}: 'output_schema' is required")

        # Prepend imports to java_code if present
        if imports:
            java_code = imports + '\n' + java_code

        # Get Java bridge from context manager
        if not self.context_manager or not self.context_manager.is_java_enabled():
            raise RuntimeError(
                f"Component {self.id}: Java execution is not available. "
                f"Please ensure JavaBridge is initialized in ContextManager."
            )

        java_bridge = self.context_manager.get_java_bridge()

        try:
            logger.info(f"Component {self.id}: Executing Java code on {len(input_data)} rows")

            # Sync context_manager to bridge before execution
            if self.context_manager:
                for key, value in self.context_manager.get_all().items():
                    java_bridge.set_context(key, value)

            if self.global_map:
                for key, value in self.global_map.get_all().items():
                    java_bridge.set_global_map(key, value)

            # Execute Java code via bridge
            result_df = java_bridge.execute_java_row(
                df=input_data,
                java_code=java_code,
                output_schema=output_schema
            )

            # Update statistics
            self._update_stats(
                rows_read=len(input_data),
                rows_ok=len(result_df)
            )

            logger.info(f"Component {self.id}: Produced {len(result_df)} rows with {len(result_df.columns)} columns")

            return {'main': result_df}

        except Exception as e:
            logger.error(f"Component {self.id}: Java execution failed: {e}")
            raise
