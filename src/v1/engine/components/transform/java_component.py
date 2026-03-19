"""
tJava component - Execute one-time Java/Groovy code

This component mimics Talend's tJava functionality:
- Executes custom Java/Groovy code once (not per-row)
- Useful for initialization and one-time operations
- Access to context and globalMap
"""

from typing import Any, Dict, Optional
import pandas as pd
import logging
from ...base_component import BaseComponent

logger = logging.getLogger(__name__)


class JavaComponent(BaseComponent):
    """
    Execute one-time Java/Groovy code (not row-based)

    Similar to Talend's tJava component - executes code once per job execution,
    not per row. Useful for:
    - Initializing resources
    - One-time calculations
    - Setting global variables

    Config parameters:
    - java_code: Java/Groovy code to execute

    Example java_code:
        // Set global variables
        globalMap.put("start_time", new java.util.Date());

        // Access context and globalMap to bridge before execution
        String output = (String) context.get("output_dir");

        // Perform calculations
        int recordCount = 1000;
        globalMap.put("expected_records", recordCount);
        """

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Execute one-time Java code"""

        # Get configuration
        java_code = self.config.get('java_code', '')

        if not java_code:
            raise ValueError(f"Component {self.id}: 'java_code' is required")

        # Get Java bridge from context manager
        if not self.context_manager or not self.context_manager.is_java_enabled():
            raise RuntimeError(
                f"Component {self.id}: Java execution is not available. "
                "Please enable JavaBridge in connection settings"
            )

        java_bridge = self.context_manager.get_java_bridge()

        try:
            logger.info(f"Component {self.id}: Executing one-time Java code")

            # Sync context and globalMap to bridge before execution
            if self.context_manager:
                ctx_all = self.context_manager.get_all()
                logger.info(f"Component {self.id}: Syncing context to bridge: {ctx_all}")
                for key, value in ctx_all.items():
                    java_bridge.set_context(key, value)
                logger.info(f"Component {self.id}: Bridge context after sync: {java_bridge.context}")

            if self.global_map:
                for key, value in self.global_map.get_all().items():
                    java_bridge.set_global_map(key, value)

            # Execute Java code
            result = java_bridge.execute_one_time_expression(java_code)

            # Sync context and globalMap back from Java to Pyython 
            # This ensures changes made in Java are visible to subsequent components
            java_bridge._sync_from_java()

            # Update ContextManager with synced context values
            if self.context_manager:
                for key, value in java_bridge.context.items():
                    self.context_manager.set(key, value)
                logger.info(f"Component {self.id}: Synced context back from Java: {java_bridge.context}")

            # Update GlobalMap with synced globalMap values
            if self.global_map:
                for key, value in java_bridge.global_map.items():
                    self.global_map.put(key, value)
                logger.info(f"Component {self.id}: Synced globalMap back from Java: {java_bridge.global_map}")

            logger.info(f"Component {self.id}: Java code executed successfully")

            if result is not None:
                logger.debug(f"Component {self.id}: Result: {result}")

            # Pass through input data unchanged
            if input_data is not None:
                self._update_stats(rows_read=len(input_data), rows_ok=len(input_data))
                return {'main': input_data}
            else:
                return {'main': pd.DataFrame()}

        except Exception as e:
            logger.error(f"Component {self.id}: Java execution failed: {e}")
            raise
