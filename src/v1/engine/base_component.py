"""
Enhanced base component class with statistics tracking and exceution modes
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, Iterator
from enum import Enum
import pandas as pd
import logging
import time

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """Execution modes for components  """
    BATCH = "batch" #Process entire dataframe at once
    STREAMING = "streaming" #Process in chunks
    HYBRID = "hybrid" #Auto-switch based on data size


class ComponentStatus(Enum):
    """Component execution status"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    SKIPPED = "skipped"


class BaseComponent(ABC):
    """
    Enhanced base class for al ETL components with statistics tracking
    """

    #Memory threshold for auto-switching to streaming mode (in MB)
    MEMORY_THRESHOLD_MB = 3072

    def __init__(
            self,
            component_id: str,
            config: Dict[str, Any],
            global_map: Any = None,
            context_manager: Any = None
    ):
        self.id = component_id
        self.config = config
        self.global_map = global_map
        self.context_manager = context_manager

        #component metadata
        self.component_type = self.__class.__name__
        self.subjob_id: Optional[str] = None
        self.is_subjob_start: bool = False

        #Execution mode
        self.execution_mode = self._determine_execution_mode()
        self.chunk_size = config.get("chunk_size", 100000)

        # Java Bridge (for JavaComponent and JavaRowComponent)
        self.java_bridge = None #Will be set by engine if Java is enabled

        #python routine manager (for python expression evaluation)
        self.python_routine_manager = None #Will be set by engine if Python is enabled

        #Input/Output connections
        self.inputs: List[str] = []
        self.outputs: List[str] = []
        self.triggers: List[Dict[str, Any]] = []

        #Schema definitions
        self.input_schema: Optional[Dict[str, Any]] = None
        self.output_schema: Optional[Dict[str, Any]] = None

        #Statistics
        self.stats = {
            'NB_LINE': 0,
            'NB_LINE_OK': 0,
            'NB_LINE_REJECT': 0,
            'NB_LINE_INSERT': 0,
            'NB_LINE_UPDATE': 0,   
            'NB_LINE_DELETE': 0,
            'EXECUTION_TIME': 0.0
        }

        # Status
        self.status = ComponentStatus.PENDING
        self.error_message: Optional[str] = None

    def _determine_execution_mode(self) -> ExecutionMode:
        """Determine execution mode based on configuration"""
        mode_str = self.config.get('execution_mode', 'hybrid')

        if mode_str == "batch":
            return ExecutionMode.BATCH
        elif mode_str == "streaming":
            return ExecutionMode.STREAMING
        else:
            return ExecutionMode.HYBRID
    
    def _resolve_java_expressions(self) -> None:
        """Resolve Java expressions in configuration using the java bridge"""
        if not self.java_bridge:
            return
        
        for key, value in self.config.items():
            if isinstance(value, str) and value.startswith("java:"):
                expression = value[len("java:"):]
                resolved_value = self.java_bridge.evaluate_expression(expression)
                self.config[key] = resolved_value
                logger.debug(f"Resolved Java expression for config '{key}': {resolved_value}")