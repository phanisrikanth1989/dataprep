"""
Main ETL Engine with trigger support and advanced execution capabilities
"""

import json
import logging
import time
from typing import Dict, Any, List, Optional, Set
from pathlib import Path
from collections import deque
import argparse

from .global_map import GlobalMap
from .context_manager import ContextManager
from .trigger_manager import TriggerManager
from .base_component import BaseComponent, ComponentStatus
from .base_iterate_component import BaseIterateComponent
from .java_bridge_manager import JavaBridgeManager
from .python_routine_manager import PythonRoutineManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)











































































class ETLEngine:
    """
    Main ETL execution engine with trigger support
    """

    COMPONENT_REGISTRY = {

        # File components
        'FileInputDelimited': FileInputDelimited,
        'tFileInputDelimited': FileInputDelimited,
        'FileOutputDelimited': FileOutputDelimited,
        'tFileOutputDelimited': FileOutputDelimited,
        'FileInputPositional': FileInputPositional,
        'tFileInputPositional': FileInputPositional,
        'FileInputExcel': FileInputExcel,
        'tFileInputExcel': FileInputExcel,
        'FileList': FileList,
        'tFileList': FileList,

        'FileInputMSXMLComponent': FileInputMSXMLComponent,
        'tFileInputMSXML': FileInputMSXMLComponent,
        'AdvancedFileOutputXMLComponent': AdvancedFileOutputXMLComponent,
        'tAdvancedFileOutputXML': AdvancedFileOutputXMLComponent,

        'FileInputJSONComponent': FileInputJSONComponent,
        'tFileInputJSON': FileInputJSONComponent,
        'FileOutputExcelComponent': FileOutputExcelComponent,
        'tFileOutputExcel': FileOutputExcelComponent,
        'FileInputFullRowComponent': FileInputFullRowComponent,
        'tFileInputFullRow': FileInputFullRowComponent,
        'FixedFlowInputComponent': FixedFlowInputComponent,
        'tFixedFlowInput': FixedFlowInputComponent,
        'FileArchiveComponent': FileArchiveComponent,
        'tFileArchive': FileArchiveComponent,
        'FileUnarchiveComponent': FileUnarchiveComponent,
        'tFileUnarchive': FileUnarchiveComponent,
        'FileDelete': FileDelete,
        'tFileDelete': FileDelete,
        'FileInputXML': FileInputXML,
        'tFileInputXML': FileInputXML,
        'FileCopy': FileCopy,
        'tFileCopy': FileCopy,
        'FileTouch': FileTouch,
        'tFileTouch': FileTouch,
        'TFileInputProperties': TFileInputProperties,
        'tFileInputProperties': TFileInputProperties,
        'TFileInputRaw': TFileInputRaw,
        'tFileInputRaw': TFileInputRaw,
        'TFileRowCount': TFileRowCount,
        'tFileRowCount': TFileRowCount,
        'FileExist': FileExistComponent,
        'tFileExist': FileExistComponent,
        'FileExistComponent': FileExistComponent,
        'TFileOutputEBCDIC': TFileOutputEBCDIC,
        'tFileOutputEBCDIC': TFileOutputEBCDIC,
        'TFileOutputPositional': TFileOutputPositional,
        'tFileOutputPositional': TFileOutputPositional,
        'TSwiftBlockFormatter': TSwiftBlockFormatter,
        'tSwiftBlockFormatter': TSwiftBlockFormatter,
        'TSwiftProcessor': TSwiftProcessor,
        'tSwiftProcessor': TSwiftProcessor,

        # Transform components
        'Map': Map,
        'tMap': Map,
        'FilterRows': FilterRows,
        'tFilterRows': FilterRows,
        'FilterColumns': FilterColumns,
        'tFilterColumns': FilterColumns,
        'Unite': Unite,
        'tUnite': Unite,
        'SortRow': SortRow,
        'tSortRow': SortRow,
        'TJoin': TJoin,
        'tJoin': TJoin,
        'RowGenerator': RowGenerator,
        'TReplace': TReplace,
        'tReplace': TReplace,
        'TParseRecordSet': TParseRecordSet,
        'tParseRecordSet': TParseRecordSet,
        'TSplitRow': TSplitRow,
        'tSplitRow': TSplitRow,
        'TSampleRow': TSampleRow,
        'tSampleRow': TSampleRow,
        'TReplicate': TReplicate,
        'tReplicate': TReplicate,
        'TPivotToColumnsDelimited': TPivotToColumnsDelimited,
        'tPivotToColumnsDelimited': TPivotToColumnsDelimited,
        'TParallelize': TParallelize,
        'tParallelize': TParallelize,
        'TNormalize': TNormalize,
        'tNormalize': TNormalize,
        'TConvertType': TConvertType,
        'tConvertType': TConvertType,
        'TMemorizeRows': TMemorizeRows,
        'tMemorizeRows': TMemorizeRows,
        'TExtractDelimitedFields': TExtractDelimitedFields,
        'tExtractDelimitedFields': TExtractDelimitedFields,
        'TExtractXMLField': TExtractXMLField,
        'tExtractXMLField': TExtractXMLField,
        'TExtractRegexFields': TExtractRegexFields,
        'tExtractRegexFields': TExtractRegexFields,
        'TExtractPositionalFields': TExtractPositionalFields,
        'tExtractPositionalFields': TExtractPositionalFields,
        'TExtractJSONFields': TExtractJSONFields,

        'TLoop': TLoop,
        'TSchemaComplianceCheck': TSchemaComplianceCheck,
        'tSchemaComplianceCheck': TSchemaComplianceCheck,
        'TFlowToIterate': TFlowToIterate,
        'tFlowToIterate': TFlowToIterate,
        'TXMLMap': TXMLMap,
        'tXMLMap': TXMLMap,
        'TAggregateSortedRow': TAggregateSortedRow,
        'tAggregateSortedRow': TAggregateSortedRow,
        'TChangeFileEncoding': TChangeFileEncoding,
        'tChangeFileEncoding': TChangeFileEncoding,
        'TLibraryLoad': TLibraryLoad,
        'tLibraryLoad': TLibraryLoad,
        'TSetGlobalVar': TSetGlobalVar,
        'tSetGlobalVar': TSetGlobalVar,
        'TUnpivotRow': TUnpivotRow,
        'TDenormalize': TDenormalize,
        'tDenormalize': TDenormalize,
        'THashOutput': THashOutput,

        # Java / Python components
        'JavaRowComponent': JavaRowComponent,
        'JavaRow': JavaRowComponent,
        'tJavaRow': JavaRowComponent,
        'JavaComponent': JavaComponent,
        'Java': JavaComponent,
        'tJava': JavaComponent,

        'PythonRowComponent': PythonRowComponent,
        'PythonRow': PythonRowComponent,
        'tPythonRow': PythonRowComponent,
        'PythonDataFrameComponent': PythonDataFrameComponent,
        'PythonDataFrame': PythonDataFrameComponent,
        'tPythonDataFrame': PythonDataFrameComponent,
        'PythonComponent': PythonComponent,
        'Python': PythonComponent,
        'tPython': PythonComponent,

        'LogRow': LogRow,
        'tLogRow': LogRow,

        # Iterate components
        'FlowToIterate': FlowToIterate,
        'tFlowToIterate': FlowToIterate,

        # Aggregate components
        'AggregateRow': AggregateRow,
        'tAggregateRow': AggregateRow,
        'UniqueRow': UniqueRow,
        'tUniqueRow': UniqueRow,
        'tUniqRow': UniqueRow,

        # Context components
        'ContextLoad': ContextLoad,
        'tContextLoad': ContextLoad,

        # Control components
        'Warn': Warn,
        'tWarn': Warn,
        'Die': Die,
        'tDie': Die,
        'SleepComponent': SleepComponent,
        'tSleep': SleepComponent,
        'PrejobComponent': PrejobComponent,
        'tPrejob': PrejobComponent,
        'PostjobComponent': PostjobComponent,
        'tPostjob': PostjobComponent,
        'RunJobComponent': RunJobComponent,
    }























    def __init__(self, job_config: Dict[str, Any]):
        """Initialize ETL engine with job configuration.

        Args:
            job_config: Job configuration dictionary or path to JSON file
        """

        # Load configuration
        if isinstance(job_config, str):
            with open(job_config, 'r') as f:
                self.job_config = json.load(f)
        else:
            self.job_config = job_config

        # Initialize Java bridge manager if required by job configuration
        self.java_bridge_manager = None
        java_config = self.job_config.get('java_config', {})
        enable_java = java_config.get('enabled', False)

        if enable_java:
            logger.info("Java configuration detected in job - initializing Java bridge...")
            # Get routines and libraries from java_config
            routines = java_config.get('routines', [])
            libraries = java_config.get('libraries', [])
            self.java_bridge_manager = JavaBridgeManager(enable=True,routines=routines,libraries=libraries)
            self.java_bridge_manager.start()
            logger.info(f"Java bridge initialized with {len(routines)} routines and {len(libraries)} libraries")

        # Initialize Python routine manager if required by job configuration
        self.python_routine_manager = None
        python_config = self.job_config.get('python_config', {})
        enable_python_routines = python_config.get('enabled', False)

        if enable_python_routines:
            logger.info("Python configuration detected in job - initializing Python routines...")
            routines_dir = python_config.get('routines_dir', 'src/python_routines')
            self.python_routine_manager = PythonRoutineManager(routines_dir)
            logger.info(f"Python routine manager initialized from {routines_dir}")

        # Initialize core components
        self.job_name = self.job_config.get('job_name', 'unnamed_job')
        self.global_map = GlobalMap()
        self.context_manager = ContextManager(
            initial_context=self.job_config.get('context', {}),
            default_context=self.job_config.get('default_context', 'Default'),
            java_bridge_manager=self.java_bridge_manager,
        )
        self.trigger_manager = TriggerManager(self.global_map)

        # Component storage
        self.components: Dict[str, BaseComponent] = {}
        self.data_flows: Dict[str, Any] = {}  # Store data between components

        # Execution tracking
        self.execution_stats = {}
        self.executed_components: Set[str] = set()
        self.failed_components: Set[str] = set()

        # Initialize components
        self._initialize_components()
        self._initialize_triggers()
        self._identify_subjobs()

    def _initialize_components(self) -> None:
        """Initialize all components from configuration."""
        for comp_config in self.job_config.get('components', []):
            comp_id = comp_config['id']
            comp_type = comp_config['type']

            # Get component class from registry
            comp_class = self.COMPONENT_REGISTRY.get(comp_type)

            if not comp_class:
                logger.warning(f"Unknown component type: {comp_type}")
                continue

            # Create component instance
            component = comp_class(
                comp_id,
                comp_config.get('config', {}),
                self.global_map,
                self.context_manager,
            )

            # Set additional properties
            component.subjob_id = comp_config.get('subjob_id')
            component.is_subjob_start = comp_config.get('is_subjob_start', False)
            component.inputs = comp_config.get('inputs', [])
            component.outputs = comp_config.get('outputs', [])
            component.input_schema = comp_config.get('schema', {}).get('input', [])
            component.output_schema = comp_config.get('schema', {}).get('output', [])

            # Set Java bridge if enabled
            if self.java_bridge_manager:
                component.java_bridge = self.java_bridge_manager.bridge

            # Set Python routine manager if enabled
            if self.python_routine_manager:
                component.python_routine_manager = self.python_routine_manager

            self.components[comp_id] = component

        logger.info(f"Initialized {len(self.components)} components for job '{self.job_name}'")

    def _initialize_triggers(self) -> None:
        """Initialize triggers from configuration."""
        # Load triggers from top-level triggers array
        for trigger in self.job_config.get('triggers', []):
            self.trigger_manager.add_trigger(
                trigger['type'],
                trigger.get('from_component') or trigger.get('from'),
                trigger.get('to_component') or trigger.get('to'),
                trigger.get('condition'),
            )

        # Also check component-level triggers
        for comp_config in self.job_config.get('components', []):
            comp_id = comp_config['id']
            for trigger in comp_config.get('triggers', []):
                self.trigger_manager.add_trigger(
                    trigger['type'],
                    comp_id,
                    trigger.get('target_component') or trigger.get('to'),
                    trigger.get('condition'),
                )

        logger.info(f"Initialized {len(self.trigger_manager.triggers)} triggers")

    def _identify_subjobs(self) -> None:
        """Identify subjobs from component connections."""
        subjobs: Dict[str, List[str]] = {}

        # Group components by subjob_id if provided
        for comp_id, component in self.components.items():
            if component.subjob_id:
                if component.subjob_id not in subjobs:
                    subjobs[component.subjob_id] = []
                subjobs[component.subjob_id].append(comp_id)

        # If no subjobs defined, try to auto-detect based on connectivity
        if not subjobs:
            visited: Set[str] = set()
            subjob_counter = 1

            for comp_id in self.components:
                if comp_id not in visited:
                    # Start new subjob from this component
                    subjob_id = f"subjob_{subjob_counter}"
                    subjob_components = self._find_connected_components(comp_id, visited)

                    if subjob_components:
                        subjobs[subjob_id] = subjob_components
                        subjob_counter += 1

        # Register subjobs with trigger manager
        for subjob_id, components in subjobs.items():
            # Identify source components (components with no inputs)
            source_components = [
                comp_id for comp_id in components
                if not self.components[comp_id].inputs
            ]
            self.trigger_manager.register_subjob(subjob_id, components, source_components)

        logger.info(f"Identified {len(subjobs)} subjobs")

    def _find_connected_components(self, start_comp: str, visited: Set[str]) -> List[str]:
        """Find all components connected via data flows (not triggers)."""
        connected: List[str] = []
        queue = deque([start_comp])

        while queue:
            comp_id = queue.popleft()
            if comp_id in visited:
                continue

            visited.add(comp_id)
            connected.append(comp_id)

            # Find components connected by flows
            for flow in self.job_config.get('flows', []):
                if flow.get('from') == comp_id and flow.get('to') not in visited:
                    queue.append(flow['to'])
                elif flow.get('to') == comp_id and flow.get('from') not in visited:
                    queue.append(flow['from'])

        return connected

    def execute(self) -> Dict[str, Any]:
        """
        Execute the ETL job with trigger support and input dependencies.

        Returns:
            Execution statistics
        """
        logger.info(f"Starting execution of job: {self.job_name}")
        start_time = time.time()

        try:
            # Build component ID to subjob ID mapping for quick lookup
            comp_to_subjob = {}
            for comp_config in self.job_config.get('components', []):
                comp_id = comp_config.get('id')
                subjob_id = comp_config.get('subjob_id')
                if comp_id and subjob_id:
                    comp_to_subjob[comp_id] = subjob_id

