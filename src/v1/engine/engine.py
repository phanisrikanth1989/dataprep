"""
Main ETL Engine with trigger support and advanced execution capabilities.
"""
import json
import logging
import time
from typing import Any, Dict, Optional, Set
from pathlib import Path
from collections import deque
import argparse

from .global_map import GlobalMap
from .context_manager import ContextManager
from .trigger_manager import TriggerManager
from .base_component import BaseComponent, ComponentStatus
from .java_bridge_manager import JavaBridgeManager
from .python_routine_manager import PythonRoutineManager

#import all components
from .components.file_input_delimited import FileInputDelimited, FileOutputDelimited
from .components.transform.map import Map


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)    


class ETLEngine:
    """
    Main ETL execution engine with trigger support.
    """

    #Component registry
    COMPONENT_REGISTRY = {
        #File components
        'FileInputDelimited': 'FileInputDelimited',
        'FileOutputDelimited': 'FileOutputDelimited',
        #Transform components
        'Map': 'Map',
        'tMap': 'Map'
    }

    