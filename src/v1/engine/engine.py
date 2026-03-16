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

# Import all components
from .components.file import FileInputDelimited, FileOutputDelimited, FileInputPositional, FileInputXML
from .components.file import FileInputFullRowComponent, FixedFlowInputComponent, FileArchiveComponent
from .components.file import FileUnarchiveComponent, FileDelete, FileCopy, FileTouch
from .components.file import FileInputRaw, FileRowCount, FileExistComponent, FileProperties
from .components.file import FileInputExcel, FileOutputExcel, FileInputJSON
from .components.file import SetGlobalVar
from .components.transform import Map, FilterRows, SortRow, JavaRowComponent, JavaComponent
from .components.transform import PythonRowComponent, PythonDataFrameComponent, PythonComponent
from .components.transform import SwiftBlockFormatter, SwiftTransformer, RowGenerator, LogRow
from .components.transform import ExtractDelimitedFields, ExtractJSONFields
from .components.transform import ExtractPositionalFields, ExtractXMLField
from .components.transform import Join, PivotToColumnsDelimited, SchemaComplianceCheck
from .components.transform import Unite, UnpivotRow, XMLMap
from .components.transform import FilterColumns
# from .components.database import OracleConnection, OracleClose, OracleRollback
# from .components.database import OracleInput, OracleOutput, OracleRow, OracleSP
# from .components.database import OracleBulkExec, MSSqlConnection, MSSqlInput
# from .components.database import OracleCommit
from .components.aggregate import AggregateRow, UniqueRow
from .components.aggregate import AggregateSortedRow, Denormalize, Normalize, Replicate
from .components.context import ContextLoad
from .components.control import Warn, Die, SleepComponent
from .components.control import SendMailComponent


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ETLEngine:
    """
    Main ETL execution engine with trigger support
    """

    # Component registry
    COMPONENT_REGISTRY = {
        # File components
        'FileInputDelimited': FileInputDelimited,
        'tFileInputDelimited': FileInputDelimited,
        'tFileOutputDelimited': FileOutputDelimited,
        'FileOutputDelimited': FileOutputDelimited,
        'FileInputPositional': FileInputPositional,
        'tFileInputPositional': FileInputPositional,
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
        'TFileInputRaw': FileInputRaw,
        'tFileInputRaw': FileInputRaw,
        'FileRowCount': FileRowCount,
        'tFileRowCount': FileRowCount,
        'FileExist': FileExistComponent,
        'tFileExist': FileExistComponent,
        'FileExistComponent': FileExistComponent,
        'FileProperties': FileProperties,
        'tFileProperties': FileProperties,
        'SetGlobalVar': SetGlobalVar,
        'tSetGlobalVar': SetGlobalVar,
        'FileInputExcel': FileInputExcel,
        'tFileInputExcel': FileInputExcel,
        'FileOutputExcel': FileOutputExcel,
        'tFileOutputExcel': FileOutputExcel,
        'FileInputJSON': FileInputJSON,
        'tFileInputJSON': FileInputJSON,

        # Transform components
        'Map': Map,
        'tMap': Map,
        'XMLMap': XMLMap,
        'tXMLMap': XMLMap,
        'FilterRows': FilterRows,
        'tFilterRows': FilterRows,
        'FilterColumns': FilterColumns,
        'tFilterColumns': FilterColumns,
        'SortRow': SortRow,
        'tSortRow': SortRow,
        'RowGenerator': RowGenerator,
        'tRowGenerator': RowGenerator,
        'TAggregateSortedRow': AggregateSortedRow,
        'tAggregateSortedRow': AggregateSortedRow,
        'Denormalize': Denormalize,
        'tDenormalize': Denormalize,
        'Normalize': Normalize,
        'tNormalize': Normalize,
        'Replicate': Replicate,
        'tReplicate': Replicate,
        'ExtractDelimitedFields': ExtractDelimitedFields,
        'tExtractDelimitedFields': ExtractDelimitedFields,
        'ExtractJSONFields': ExtractJSONFields,
        'tExtractJSONFields': ExtractJSONFields,
        'ExtractPositionalFields': ExtractPositionalFields,
        'tExtractPositionalFields': ExtractPositionalFields,
        'ExtractXMLField': ExtractXMLField,
        'tExtractXMLField': ExtractXMLField,
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
        'SwiftBlockFormatter': SwiftBlockFormatter,
        'tSwiftBlockFormatter': SwiftBlockFormatter,
        'SwiftTransformer': SwiftTransformer,
        'tSwiftTransformer': SwiftTransformer,
        'Join': Join,
        'tJoin': Join,
        'PivotToColumnsDelimited': PivotToColumnsDelimited,
        'tPivotToColumnsDelimited': PivotToColumnsDelimited,
        'SchemaComplianceCheck': SchemaComplianceCheck,
        'tSchemaComplianceCheck': SchemaComplianceCheck,
        'Unite': Unite,
        'tUnite': Unite,
        'UnpivotRow': UnpivotRow,
        'tUnpivotRow': UnpivotRow,

        # Iterate components

        # Aggregate components
        'AggregateRow': AggregateRow,
        'tAggregateRow': AggregateRow,
        'UniqueRow': UniqueRow,
        'tUniqueRow': UniqueRow,
        'tUniqRow': UniqueRow,  # <-- Add this line for Talend compatibility

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
        'SendMailComponent': SendMailComponent,
        'tSendMail': SendMailComponent,

        # Database components
        # 'OracleConnection': OracleConnection,
        # 'tDBConnection': OracleConnection,
        # 'OracleClose': OracleClose,
        # 'tOracleClose': OracleClose,
        # 'OracleRollback': OracleRollback,
        # 'tOracleRollback': OracleRollback,
        # 'OracleInput': OracleInput,
        # 'tOracleInput': OracleInput,
        # 'OracleOutput': OracleOutput,
        # 'tOracleOutput': OracleOutput,
        # 'OracleRow': OracleRow,
        # 'tOracleRow': OracleRow,
        # 'OracleSP': OracleSP,
        # 'tOracleSP': OracleSP,
        # 'OracleBulkExec': OracleBulkExec,
        # 'tOracleBulkExec': OracleBulkExec,
        # 'MSSqlConnection': MSSqlConnection,
        # 'tMSSqlConnection': MSSqlConnection,
        # 'MSSqlInput': MSSqlInput,
        # 'tMSSqlInput': MSSqlInput,
        # 'OracleCommit': OracleCommit,
        # 'tOracleCommit': OracleCommit,
    }

    def __init__(self, job_config: Dict[str, Any]):
        """
        Initialize ETL engine with job configuration

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
            self.java_bridge_manager = JavaBridgeManager(enable=True, routines=routines, libraries=libraries)
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
            initial_context = self.job_config.get('context', {}),
            default_context = self.job_config.get('default_context', 'Default'),
            java_bridge_manager = self.java_bridge_manager
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
        """Initialize all components from configuration"""
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
                self.context_manager
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
        """Initialize triggers from configuration"""
        # Load triggers from top-level triggers array
        for trigger in self.job_config.get('triggers', []):
            self.trigger_manager.add_trigger(
                trigger['type'],
                trigger.get('from_component') or trigger.get('from'),
                trigger.get('to_component') or trigger.get('to'),
                trigger.get('condition')
            )

        # Also check component-level triggers
        for comp_config in self.job_config.get('components', []):
            comp_id = comp_config['id']
            for trigger in comp_config.get('triggers', []):
                self.trigger_manager.add_trigger(
                    trigger['type'],
                    comp_id,
                    trigger.get('target_component') or trigger.get('to'),
                    trigger.get('condition')
                )

        logger.info(f"Initialized {len(self.trigger_manager.triggers)} triggers")

    def _identify_subjobs(self) -> None:
        """Identify subjobs from component connections"""
        subjobs = {}

        # Group components by subjob_id if provided
        for comp_id, component in self.components.items():
            if component.subjob_id:
                if component.subjob_id not in subjobs:
                    subjobs[component.subjob_id] = []
                subjobs[component.subjob_id].append(comp_id)

        # If no subjobs defined, try to auto-detect based on connectivity
        if not subjobs:
            visited = set()
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
        """Find all components connected via data flows (not triggers)"""
        connected = []
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
        Execute the ETL job with trigger support and input dependencies

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
                if comp_id:
                    comp_to_subjob[comp_id] = subjob_id

            # Identify initial subjobs (subjobs that are not triggered)
            triggered_targets = {t.to_component for t in self.trigger_manager.triggers}
            triggered_subjobs = set()
            for comp_id in triggered_targets:
                subjob_id = comp_to_subjob.get(comp_id)
                if subjob_id:
                    triggered_subjobs.add(subjob_id)

            # Active subjobs = subjobs that can currently execute
            # Start with all non-triggered subjobs
            all_subjobs = set(comp_to_subjob.values())
            active_subjobs = all_subjobs - triggered_subjobs
            logger.info(f"Initial active subjobs: {active_subjobs}")

            # Track execution queue
            execution_queue = deque()

            # Helper function to check if component can execute
            def can_execute(comp_id):
                # Check 1: Component's subjob must be active
                subjob_id = comp_to_subjob.get(comp_id)
                if subjob_id not in active_subjobs:
                    return False

                # Check 2: Component must not be already executed
                if comp_id in self.executed_components:
                    return False

                # Check 3: All inputs must be ready
                if not self._are_inputs_ready(comp_id):
                    return False

                return True

            # Initialize queue with components that can execute
            for comp_id in self.components:
                if can_execute(comp_id):
                    execution_queue.append(comp_id)

            # Main execution loop
            while execution_queue or len(self.executed_components) < len(self.components):
                # If queue is empty but there are unexecuted components, check if we're stuck
                if not execution_queue:
                    unexecuted = set(self.components.keys()) - self.executed_components
                    if unexecuted:
                        logger.warning(f"Execution stalled. Unexecuted components: {unexecuted}")
                        logger.warning(f"Active subjobs: {active_subjobs}")
                        break

                # Process ready components
                while execution_queue:
                    comp_id = execution_queue.popleft()

                    # Skip if already executed (double-check)
                    if comp_id in self.executed_components:
                        continue

                    # Execute component
                    status = self._execute_component(comp_id)

                    # Check if this component's subjob is now complete
                    completed_subjob = comp_to_subjob.get(comp_id)
                    if completed_subjob and completed_subjob in active_subjobs:
                        # Get all components in this subjob
                        subjob_components = [c for c in self.components if comp_to_subjob.get(c) == completed_subjob]
                        # Check if all components in subjob are executed
                        if all(c in self.executed_components for c in subjob_components):
                            active_subjobs.discard(completed_subjob)
                            logger.info(f"Subjob {completed_subjob} completed and removed from active subjobs")

                    # Get triggered components based on execution status
                    newly_triggered = self.trigger_manager.get_triggered_components(comp_id, status)

                    # If triggers fired, activate the target subjobs
                    if newly_triggered:
                        for triggered_comp in newly_triggered:
                            triggered_subjob = comp_to_subjob.get(triggered_comp)
                            if triggered_subjob and triggered_subjob not in active_subjobs:
                                active_subjobs.add(triggered_subjob)
                                logger.info(f"Subjob {triggered_subjob} activated by trigger from {comp_id}")

                    # Re-check all components to see if any can now execute
                    # (either due to new data flows or newly activated subjobs)
                    for pending_comp in self.components:
                        if can_execute(pending_comp) and pending_comp not in execution_queue:
                            execution_queue.append(pending_comp)
                            logger.debug(f"Component {pending_comp} added to queue")

            # Calculate execution statistics
            execution_time = time.time() - start_time
            stats = {
                'job_name': self.job_name,
                'status': 'success' if not self.failed_components else 'failed',
                'execution_time': execution_time,
                'components_executed': len(self.executed_components),
                'components_failed': len(self.failed_components),
                'component_stats': self.execution_stats,
                'global_map': self.global_map.get_all_stats()
            }

            logger.info(f"Job completed in {execution_time:.2f} seconds")

            # Cleanup Java bridge
            self._cleanup()

            return stats

        except Exception as e:
            logger.error(f"Job execution failed: {e}")

            # Cleanup Java bridge even on error
            self._cleanup()

            execution_time = time.time() - start_time

            return {
                'job_name': self.job_name,
                'status': 'error',
                'error': str(e),
                'execution_time': execution_time,
                'components_executed': len(self.executed_components),
                'components_failed': len(self.failed_components),
                'component_stats': self.execution_stats
            }

    def _execute_component(self, comp_id: str) -> str:
        """
        Execute a single component

        Returns:
            'success' or 'error'
        """
        if comp_id not in self.components:
            logger.error(f"Component {comp_id} not found")
            return 'error'

        component = self.components[comp_id]
        logger.info(f"Executing component: {comp_id} ({component.__class__.__name__})")

        try:
            # Get input data from flows
            input_data = self._get_input_data(comp_id)

            # Execute component
            start_time = time.time()
            result = component.execute(input_data)
            execution_time = time.time() - start_time

            # Check if this is an iterate component
            if isinstance(component, BaseIterateComponent) and result.get('iterate'):
                # Handle iterate execution
                return self._execute_iterate_component(comp_id, component, result, execution_time)

            # Store results in data flows (normal components)
            if result:
                # Map outputs to correct flow names based on flows section
                for flow in self.job_config.get('flows', []):
                    if flow['from'] == comp_id:
                        if flow['type'] == 'flow' and 'main' in result and result['main'] is not None:
                            self.data_flows[flow['name']] = result['main']
                        elif flow['type'] == 'reject' and 'reject' in result and result['reject'] is not None:
                            self.data_flows[flow['name']] = result['reject']
                        elif flow['type'] == 'filter' and 'main' in result and result['main'] is not None:
                            self.data_flows[flow['name']] = result['main']
                # Other named outputs (for completeness, if any)
                for key, value in result.items():
                    if key not in ['main', 'reject', 'stats'] and value is not None:
                        if key in component.outputs:
                            # Declared output - store by output name directly
                            self.data_flows[key] = value
                        else:
                            # Undeclared output - prefix with component ID
                            self.data_flows[f"{comp_id}_{key}"] = value

            # Store execution stats
            stats = component.get_stats()
            stats['execution_time'] = execution_time
            self.execution_stats[comp_id] = stats

            # Update trigger manager
            self.trigger_manager.set_component_status(comp_id, 'success')
            self.executed_components.add(comp_id)

            logger.info(f"Component {comp_id} completed: {stats.get('NB_LINE_OK', 0)} rows processed")

            return 'success'

        except Exception as e:
            # Handle component failure
            logger.error(f"Component {comp_id} failed: {str(e)}")

            # Check if it's a Die component error
            if hasattr(e, 'exit_code'):
                # Job should stop
                raise e

            # Update status
            self.trigger_manager.set_component_status(comp_id, 'error')
            self.failed_components.add(comp_id)
            self.executed_components.add(comp_id)

            # Store error in stats
            self.execution_stats[comp_id] = {
                'status': 'error',
                'error': str(e)
            }

            return 'error'

    def _execute_iterate_component(self, comp_id: str, component: BaseIterateComponent,
                                   result: Dict[str, Any], execution_time: float) ->                                   str:
        """
        Handle execution of iterate components and their downstream subjobs

        Args:
            comp_id: Component ID
            component: The iterate component instance
            result: Result from initial component execution
            execution_time: Time taken for initial execution

        Returns:
            'success' or 'error'
        """
        try:
            # Find iterate connection and target subjob
            iterate_flow = None
            for flow in self.job_config.get('flows', []):
                if flow['from'] == comp_id and flow.get('type') == 'iterate':
                    iterate_flow = flow
                    break

            if not iterate_flow:
                logger.warning(f"No iterate connection found for component {comp_id}")
                # Still mark as success since component executed
                self.trigger_manager.set_component_status(comp_id, 'success')
                self.executed_components.add(comp_id)
                return 'success'

            target_comp_id = iterate_flow['to']
            logger.info(f"Component {comp_id} will iterate {result.get('iteration_count', 0)} times to {target_comp_id}")

            # Execute iterations
            iteration_count = 0
            while component.has_next_iteration():
                iteration_count += 1

                # Get next iteration context and set globalMap variables
                iteration_context = component.get_next_iteration_context()

                logger.info(f"Executing iteration {iteration_count}/{result.get('iteration_count', 0)}")

                # Track components executed in this iteration
                iteration_executed = set()
                iteration_queue = deque([target_comp_id])

                # Execute all components and triggers for this iteration
                while iteration_queue:
                    current_comp_id = iteration_queue.popleft()

                    # Skip if already executed in this iteration
                    if current_comp_id in iteration_executed:
                        continue

                    # Clear from global executed set if it was executed in previous iteration
                    if current_comp_id in self.executed_components:
                        self.executed_components.remove(current_comp_id)

                    # Check if inputs are ready (or if it's the first component)
                    if self._are_inputs_ready(current_comp_id) or current_comp_id == target_comp_id:
                        # Execute the component
                        status = self._execute_component(current_comp_id)
                        iteration_executed.add(current_comp_id)

                        if status == 'error':
                            # Fail fast - stop iterations on error
                            logger.error(f"Iteration {iteration_count} failed at component {current_comp_id}")
                            self.trigger_manager.set_component_status(comp_id, 'error')
                            self.failed_components.add(comp_id)
                            self.executed_components.add(comp_id)
                            raise RuntimeError(f"Iteration failed at component {current_comp_id}")

                    # Check for triggered components after successful execution
                    triggered = self.trigger_manager.get_triggered_components(current_comp_id, status)
                    for triggered_comp in triggered:
                        if triggered_comp not in iteration_executed:
                            iteration_queue.append(triggered_comp)
                            logger.debug(f"Component {triggered_comp} triggered by {current_comp_id} in iteration {iteration_count}")

                    # Also check for components connected by flow
                    for flow in self.job_config.get('flows', []):
                        if flow['from'] == current_comp_id and flow['type'] != 'iterate':
                            next_comp = flow['to']
                            if next_comp not in iteration_executed and next_comp not in iteration_queue:
                                iteration_queue.append(next_comp)

                # Clear trigger states for next iteration
                for executed_comp in iteration_executed:
                    # Remove from triggered components set so they can be triggered
                    # again in next iteration
                    self.trigger_manager.triggered_components.discard(executed_comp)
                # Clear any cached data flow from this iteration
                for flow in self.job_config.get('flows', []):
                    if flow['from'] == executed_comp:
                        flow_name = flow['name']
                        if flow_name in self.data_flows:
                            del self.data_flows[flow_name]

            # Collect stats from this iteration
            iteration_stats = {'NB_LINE': 0, 'NB_LINE_OK': 0, 'NB_LINE_REJECT': 0}
            for executed_comp in iteration_executed:
                if executed_comp in self.execution_stats:
                    comp_stats = self.execution_stats[executed_comp]
                    iteration_stats['NB_LINE'] += comp_stats.get('NB_LINE', 0)
                    iteration_stats['NB_LINE_OK'] += comp_stats.get('NB_LINE_OK', 0)
                    iteration_stats['NB_LINE_REJECT'] += comp_stats.get('NB_LINE_REJECT', 0)

            component.update_iteration_stats(iteration_stats)

            logger.info(f"Iteration {iteration_count} completed - executed {len(iteration_executed)} components")

            # Finalize iterations
            component.finalize_iterations()

            # Store final stats
            stats = component.get_stats()
            stats['execution_time'] = execution_time
            stats['iterations_completed'] = iteration_count
            self.execution_stats[comp_id] = stats

            # Mark iterate component as executed
            self.trigger_manager.set_component_status(comp_id, 'success')
            self.executed_components.add(comp_id)

            logger.info(f"Iterate component {comp_id} completed all {iteration_count} iterations")

            return 'success'

        except Exception as e:
            logger.error(f"Iterate component {comp_id} failed during iteration: {str(e)}")
            self.trigger_manager.set_component_status(comp_id, 'error')
            self.failed_components.add(comp_id)
            self.executed_components.add(comp_id)

            # Store error in stats
            self.execution_stats[comp_id] = {
                'status': 'error',
                'error': str(e),
                'execution_time': execution_time
            }

            # Re-raise to trigger job termination
            raise

    def _are_inputs_ready(self, comp_id: str) -> bool:
        """Check if all required inputs for a component are available"""
        component = self.components[comp_id]

        if not component.inputs:
            return True

        # Check if all input flows have data available
        for input_flow in component.inputs:
            if input_flow not in self.data_flows:
                return False

        return True

    def _get_input_data(self, comp_id: str) -> Optional[Any]:
        """Get input data for a component from data flows"""
        component = self.components[comp_id]

        if not component.inputs:
            return None

        # Handle multiple inputs
        if len(component.inputs) == 1:
            # Single input - return the data directly
            return self.data_flows.get(component.inputs[0])
        else:
            # Multiple inputs - return as dictionary keyed by flow name
            input_data = {}
            for input_flow in component.inputs:
                input_data[input_flow] = self.data_flows.get(input_flow)
            return input_data

    def set_context_variable(self, name: str, value: Any) -> None:
        """Set or update a context variable"""
        self.context_manager.set(name, value)

        # Update all components
        for component in self.components.values():
            component.context_manager = self.context_manager

    def get_execution_stats(self) -> Dict[str, Any]:
        """Get detailed execution statistics"""
        return {
            'job_name': self.job_name,
            'components_executed': list(self.executed_components),
            'components_failed': list(self.failed_components),
            'component_stats': self.execution_stats,
            'global_map': self.global_map.get_all(),
            'context': self.context_manager.get_all()
        }

    def _cleanup(self) -> None:
        """Cleanup resources including Java bridge"""
        if self.java_bridge_manager:
            logger.info("Shutting down Java bridge...")
            self.java_bridge_manager.stop()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self._cleanup()
        return False


def run_job(job_config_path: str, context_overrides: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Convenience function to run an ETL job

    Args:
        job_config_path: Path to job configuration JSON file
        context_overrides: Context variables to override

    Returns:
        Execution statistics

    Note:
        Java execution is automatically enabled based on the job configuration's
        java_config.enabled field. No need to pass enable_java parameter.
    """
    # Create engine with context manager (auto-cleanup)
    # Java bridge is automatically initialized if java_config.enabled = true in JSON
    with ETLEngine(job_config_path) as engine:
        # Apply context overrides if provided
        if context_overrides:
            for name, value in context_overrides.items():
                logger.info(f"Setting context variable: {name} = {value}")
                engine.set_context_variable(name, value)

        # Execute job
        return engine.execute()


if __name__ == '__main__':
    import sys

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Run ETL job with optional context overrides.')
    parser.add_argument('job_config', help='Path to the job configuration JSON file')
    parser.add_argument(
        '--context_param',
        action='append',
        help='Override context variables in the format KEY=VALUE. Can be used multiple times.',
    )
    args = parser.parse_args()

    # Parse context overrides
    context_overrides = {}
    if args.context_param:
        for param in args.context_param:
            if '=' in param:
                key, value = param.split('=', 1)
                context_overrides[key.strip()] = value.strip()
            else:
                logger.error(f"Invalid context_param format: {param}. Expected format is KEY=VALUE.")
                sys.exit(1)

    # Run the job with the provided configuration and context overrides
    stats = run_job(args.job_config, context_overrides)

    # Print execution statistics
    print(json.dumps(stats, indent=2))
