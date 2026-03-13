"""
Main converter for complex Talend jobs
"""
import xml.etree.ElementTree as ET
import json
from typing import Dict, List, Any, Optional, Set
from pathlib import Path
import logging

from .component_parser import ComponentParser
from .expression_converter import ExpressionConverter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ComplexTalendConverter:
    """Converts complex Talend .item XML files to JSON format with trigger support"""

    def __init__(self):
        self.namespaces = {
            'xmi': 'http://www.omg.org/XMI',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
            'TalendMapper': 'http://www.talend.org/mapper',
            'talendfile': 'platform:/resource/org.talend.model/model/TalendFile.xsd'
        }

        self.component_parser = ComponentParser()
        self.expr_converter = ExpressionConverter()
        self.logger = logging.getLogger("ComplexTalendConverter")
        logging.basicConfig(level=logging.INFO)

    def convert_file(self, filepath: str) -> Dict[str, Any]:
        """
        Convert Talend .item XML file to JSON format for complex ETL engine

        Args:
            filepath: Path to .item XML file

        Returns:
            Dictionary with job configuration
        """
        tree = ET.parse(filepath)
        root = tree.getroot()

        job_name = Path(filepath).stem

        # Parse routines and libraries first
        routines = self._parse_routines(root)
        libraries = self._parse_libraries(root)

        result = {
            'job_name': job_name,
            'job_type': root.get('jobType', 'Standard'),
            'default_context': root.get('defaultContext', 'Default'),
            'context': self._parse_context(root),
            'components': [],
            'flows': [],
            'triggers': []
        }

        # Parse all components (nodes)
        components_map = {}
        for node in root.iter('node'):  # Use iter() for reliable node finding
            component = self._parse_component(node)
            if component:
                components_map[component['id']] = component
                result['components'].append(component)

        # Parse all connections (flows and triggers)
        for connection in root.findall('.//connection'):
            conn_type = connection.get('connectorName', '')

            if conn_type in ['FLOW', 'MAIN', 'REJECT', 'FILTER', 'UNIQUE', 'DUPLICATE', 'ITERATE']:
                # Data flow connection
                flow = self._parse_flow(connection)
                if flow:
                    result['flows'].append(flow)
                    # Update component input/output connections
                    self._update_component_connections(components_map, flow)

            elif conn_type in ['SUBJOB_OK', 'SUBJOB_ERROR', 'COMPONENT_OK', 'COMPONENT_ERROR', 'RUN_IF']:
                # Trigger connection
                trigger = self._parse_trigger(connection)
                if trigger:
                    result['triggers'].append(trigger)

        # Filter out triggers that reference skipped components (e.g., tLibraryLoad)
        valid_triggers = []
        for trigger in result['triggers']:
            from_comp = trigger.get('from')
            to_comp = trigger.get('to')

            # Only keep triggers where both components exist
            if from_comp in components_map and to_comp in components_map:
                valid_triggers.append(trigger)
            else:
                logger.debug(f"Skipping trigger from '{from_comp}' to '{to_comp}' - one or both components were skipped")

        result['triggers'] = valid_triggers

        # Auto-detect subjobs based on connectivity
        result['subjobs'] = self._detect_subjobs(components_map, result['flows'])

        # Add subjob information to components
        for subjob_id, comp_ids in result['subjobs'].items():
            for comp_id in comp_ids:
                if comp_id in components_map:
                    components_map[comp_id]['subjob_id'] = subjob_id
                    # Mark first component as subjob start
                    if comp_ids[0] == comp_id:
                        components_map[comp_id]['is_subjob_start'] = True

        # Detect if Java is required and create java_config section
        requires_java = self._detect_java_requirement(result['components'])
        result['java_config'] = {
            'enabled': requires_java,
            'routines': routines,
            'libraries': libraries
        }

        logger.info(f"Converted {filepath}: {len(result['components'])} components, "
                    f"{len(result['flows'])} flows, {len(result['triggers'])} triggers, "
                    f"Java required: {requires_java}")

        return result

    def _parse_context(self, root) -> Dict[str, Any]:
        """Parse context parameters"""
        context = {}

        for ctx in root.findall('.//context'):
            ctx_name = ctx.get('name', 'Default')
            context[ctx_name] = {}

            for param in ctx.findall('.//contextParameter'):
                param_name = param.get('name')
                param_value = param.get('value', '')
                param_type = param.get('type', 'id_String')

                if param_name:
                    # Convert type to Python type
                    python_type = self.expr_converter.convert_type(param_type)

                    # Strip quotes from string values (XML encoded as &quot;US&quot;)
                    if python_type == 'str' and isinstance(param_value, str):
                        if param_value.startswith('"') and param_value.endswith('"'):
                            param_value = param_value[1:-1]

                    context[ctx_name][param_name] = {
                        'value': param_value,
                        'type': python_type
                    }

        return context

    def _parse_routines(self, root) -> List[str]:
        """
        Parse routine dependencies from job XML.
        Extracts routinesParameter tags and returns list of routine class names.
        """
        routines = []

        # Find all routinesParameter elements (typically under parameters section)
        for routine_param in root.findall('.//routinesParameter'):
            routine_name = routine_param.get('name')
            if routine_name:
                # Add 'routines.' package prefix if not already present
                if not routine_name.startswith('routines.'):
                    routine_name = f'routines.{routine_name}'
                routines.append(routine_name)

        # Remove duplicates while preserving order
        seen = set()
        unique_routines = []
        for routine in routines:
            if routine not in seen:
                seen.add(routine)
                unique_routines.append(routine)

        logger.info(f"Found {len(unique_routines)} routine dependencies: {unique_routines}")
        return unique_routines

    def _parse_libraries(self, root) -> List[str]:
        """
        Parse external library dependencies from tLibraryLoad components.
        Extracts JAR file names from MODULE_LIST parameter.
        Returns list of JAR names (e.g., ['commons-lang3-3.14.0.jar', 'gson-2.8.9.jar'])
        """
        libraries = []

        # Find all tLibraryLoad component nodes
        for node in root.findall('.//node[@componentName="tLibraryLoad"]'):
            # Look for LIBRARY parameter
            for param in node.findall('.//elementParameter[@name="LIBRARY"]'):
                library_value = param.get('value', '')
                if library_value:
                    # Value format: &quot;commons-lang3-3.14.0.jar&quot;
                    # After unescaping: "commons-lang3-3.14.0.jar"
                    # We need to extract: commons-lang3-3.14.0.jar
                    library_value = library_value.replace('&quot;', '').strip('"')
                    if library_value and library_value.endswith('.jar'):
                        libraries.append(library_value)

        # Remove duplicates while preserving order
        seen = set()
        unique_libraries = []
        for lib in libraries:
            if lib not in seen:
                seen.add(lib)
                unique_libraries.append(lib)

        logger.info(f"Found {len(unique_libraries)} library dependencies: {unique_libraries}")
        return unique_libraries

    def _parse_component(self, node) -> Optional[Dict[str, Any]]:
        """Parse a single component node"""
        component_type = node.get('componentName')

        # Skip tLibraryLoad components - libraries are now handled at engine startup
        if component_type == 'tLibraryLoad':
            logger.debug(f"Skipping tLibraryLoad component (handled at engine startup)")
            return None

        # Get base component
        component = self.component_parser.parse_base_component(node)
        if not component:
            logger.warning(f"Skipping node due to missing or invalid component: {ET.tostring(node, encoding='unicode')}")
            return None

        # Apply component-specific parsing
        if component_type == 'tMap':
            component = self.component_parser.parse_tmap(node, component)
        elif component_type == 'tAggregateRow':
            component = self.component_parser.parse_aggregate(node, component)
        elif component_type in ['tFilterRow', 'tFilterRows']:  # Handle both singular and plural
            component = self.component_parser.parse_filter_rows(node, component)
        elif component_type == 'tFilterColumns':
            component = self.component_parser.parse_filter_columns(node, component)
        elif component_type == 'tUniqRow':
            component = self.component_parser.parse_unique(node, component)
        elif component_type == 'tUnqRow':
            component = self.component_parser.parse_unique(node, component)
        elif component_type == 'tSortRow':
            component = self.component_parser.parse_sort_row(node, component)
        elif component_type == 'tUnite':
            component = self.component_parser.parse_unite(node, component)
        elif component_type == 'tJoin':
            component = self.component_parser.parse_tjoin(node, component)
        elif component_type == 'tFileInputExcel':
            component = self.component_parser.parse_file_input_excel(node, component)
        elif component_type == 'tFileList':
            component = self.component_parser.parse_base_component(node)
        elif component_type == 'tFileInputFullRow':
            component = self.component_parser.parse_tfileinputfullrow(node, component)
        elif component_type == 'tSleep':
            component = self.component_parser.parse_tsleep(node, component)
        elif component_type == 'tPrejob':
            component = self.component_parser.parse_tprejob(node, component)
        elif component_type == 'tPostjob':
            component = self.component_parser.parse_tpostjob(node, component)
        elif component_type == 'tRunJob':
            component = self.component_parser.parse_trunjob(node, component)