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
        elif component_type == 'tSendMail':
            component = self.component_parser.parse_tsendmail(node, component)
        elif component_type == 'tXMLMap':
            component = self.component_parser.parse_t_xml_map(node, component)
        elif component_type == 'tFileInputXML':
            component = self.component_parser.parse_tfileinputxml(node, component)
        elif component_type == 'tFileInputMSXML':
            component = self.component_parser.parse_tfileinputmsxml(node, component)
        elif component_type == 'tAdvancedFileOutputXML':
            component = self.component_parser.parse_tadvancedfileoutputxml(node, component)
        elif component_type == 'tFileInputJSON':
            component = self.component_parser.parse_tfileinputjson(node, component)
        elif component_type == 'tFileOutputExcel':
            component = self.component_parser.parse_tfileoutputexcel(node, component)
        elif component_type == 'tFixedFlowInput':
            component = self.component_parser.parse_tfixedflowinput(node, component)
        elif component_type == 'tFileArchive':
            component = self.component_parser.parse_tfilearchive(node, component)
        elif component_type == 'tFileUnarchive':
            component = self.component_parser.parse_tfileunarchive(node, component)
        elif component_type == 'tFileDelete':
            component = self.component_parser.parse_base_component(node)
        elif component_type == 'tFileCopy':
            component = self.component_parser.parse_tfilecopy(node, component)
        elif component_type == 'tFileTouch':
            component = self.component_parser.parse_tfiletouch(node, component)
        elif component_type == 'tFileExist':
            component = self.component_parser.parse_tfileexist(node, component)
        elif component_type == 'tFileProperties':
            component = self.component_parser.parse_tfileproperties(node, component)
        elif component_type == 'tFileRowCount':
            component = self.component_parser.parse_tfile_row_count(node, component)
        elif component_type == 'tFileInputProperties':
            # Add logic for handling tFileInputProperties
            pass
        elif component_type == 'tRowGenerator':
            component = self._parse_row_generator(node)
        elif component_type == 'tReplace':
            component = self.component_parser.parse_treplace(node, component)
        elif component_type == 'tParseRecordSet':
            component = self.component_parser.parse_tparse_record_set(node, component)
        elif component_type == 'tSplitRow':
            component = self.component_parser.parse_tsplit_row(node, component)
        elif component_type == 'tSampleRow':
            component = self.component_parser.parse_tsample_row(node, component)
        elif component_type == 'tReplicate':
            component = self.component_parser.parse_treplicate(node, component)
        elif component_type == 'tPivotToColumnsDelimited':
            component = self.component_parser.parse_tpivot_to_columns_delimited(node, component)
        elif component_type == 'tParallelize':
            component = self.component_parser.parse_tparallelize(node, component)
        elif component_type == 'tNormalize':
            component = self.component_parser.parse_tnormalize(node, component)
        elif component_type == 'tConvertType':
            component = self.component_parser.parse_tconverttype(node, component)
        elif component_type == 'tMemorizeRows':
            component = self.component_parser.parse_tmemorizerows(node, component)
        elif component_type == 'tExtractDelimitedFields':
            component = self.component_parser.parse_textract_delimited_fields(node, component)
        elif component_type == 'tExtractRegexFields':
            component = self.component_parser.parse_textract_regex_fields(node, component)
        elif component_type == 'tExtractPositionalFields':
            component = self.component_parser.parse_textract_positional_fields(node, component)
        elif component_type == 'tExtractJSONFields':
            component = self.component_parser.parse_textract_json_fields(node, component)
        elif component_type == 'tExtractXMLField':
            component = self.component_parser.parse_textract_xml_field(node, component)
        elif component_type == 'tLoop':
            component = self.component_parser.parse_tloop(node, component)
        elif component_type == 'tSchemaComplianceCheck':
            component = self.component_parser.parse_tschema_compliance_check(node, component)
        elif component_type == 'tFileInputRaw':
            component = self.component_parser.parse_t_file_input_raw(node, component)
        elif component_type == 'tFlowToIterate':
            component = self.component_parser.parse_t_flow_to_iterate(node, component)
        elif component_type == 'tAggregateSortedRow':
            component = self.component_parser.parse_t_aggregate_sorted_row(node, component)
        elif component_type == 'tOracleCommit':
            component = self.component_parser.parse_t_oracle_commit(node, component)
        elif component_type == 'tOracleClose':
            component = self.component_parser.parse_t_oracle_close(node, component)
        elif component_type == 'tOracleRollback':
            component = self.component_parser.parse_t_oracle_rollback(node, component)
        elif component_type == 'tForeach':
            component = self.component_parser.parse_t_foreach(node, component)
        elif component_type == 'tOracleInput':
            component = self.component_parser.parse_t_oracle_input(node, component)
        elif component_type == 'tOracleOutput':
            component = self.component_parser.parse_t_oracle_output(node, component)
        elif component_type == 'tOracleRow':
            component = self.component_parser.parse_t_oracle_row(node, component)
        elif component_type == 'tUnpivotRow':
            component = self.component_parser.parse_unpivot_row(node, component)
        elif component_type == 'tMSSqlConnection':
            component = self.component_parser.parse_t_mssql_connection(node, component)
        elif component_type == 'tMSSqlInput':
            component = self.component_parser.parse_t_mssql_input(node, component)
        elif component_type == 'tChangeFileEncoding':
            component = self.component_parser.parse_t_change_file_encoding(node, component)
        elif component_type == 'tOracleSP':
            component = self.component_parser.parse_t_oracle_sp(node, component)
        elif component_type == 'tOracleBulkExec':
            component = self.component_parser.parse_t_oracle_bulk_exec(node, component)
        elif component_type == 'tSetGlobalVar':
            component = self.component_parser.parse_tsetglobalvar(node, component)
        elif component_type == 'tDenormalize':
            component = self.component_parser.parse_tdenormalize(node, component)
        elif component_type == 'tFileOutputEBCDIC':
            component = self.component_parser.parse_tfileoutputebcdic(node, component)
        elif component_type == 'tHashOutput':
            component = self.component_parser.parse_thash_output(node, component)
        elif component_type == 'tJavaRow':
            component = self.component_parser.parse_java_row(node, component)
        elif component_type == 'tFileOutputPositional':
            component = self.component_parser.parse_tfileoutputpositional(node, component)
        elif component_type == 'tOracleConnection':
            component = self.component_parser.parse_oracle_connection(node, component)

        return component

    def _parse_flow(self, connection) -> Optional[Dict[str, Any]]:
        """Parse a data flow connection"""
        source = connection.get('source', '')
        target = connection.get('target', '')
        label = connection.get('label', '')
        connector = connection.get('connectorName', 'FLOW')

        if not source or not target:
            return None

        # Get unique name
        unique_name = label
        for param in connection.findall('.//elementParameter[@name="UNIQUE_NAME"]'):
            unique_name = param.get('value', '').strip('"')
            break

        return {
            'name': unique_name or label,
            'from': source,
            'to': target,
            'type': connector.lower()
        }

    def _parse_trigger(self, connection) -> Optional[Dict[str, Any]]:
        """Parse a trigger connection and ensure tPrejob executes first."""
        source = connection.get('source', '')
        target = connection.get('target', '')
        trigger_type = connection.get('connectorName', '')

        if not source or not target or not trigger_type:
            return None

        # Map Talend trigger types to our trigger types
        trigger_mapping = {
            'SUBJOB_OK': 'OnSubjobOk',
            'SUBJOB_ERROR': 'OnSubjobError',
            'COMPONENT_OK': 'OnComponentOk',
            'COMPONENT_ERROR': 'OnComponentError',
            'RUN_IF': 'RunIf'
        }

        mapped_type = trigger_mapping.get(trigger_type, trigger_type)

        # Ensure tPrejob executes first
        if source.startswith('tPrejob'):
            self.logger.info(f"Ensuring tPrejob ({source}) executes before {target}.")
            return {
                'type': 'OnComponentOk',
                'from': source,
                'to': target
            }

        trigger = {
            'type': mapped_type,
            'from': source,
            'to': target
        }

        # Parse condition for RunIf triggers
        if trigger_type == 'RUN_IF':
            for param in connection.findall('.//elementParameter[@name="CONDITION"]'):
                condition = param.get('value', '')
                if condition:
                    trigger['condition'] = self.expr_converter.convert(condition)

        return trigger

    def _update_component_connections(self, components_map: Dict, flow: Dict) -> None:
        """Update component input/output connections based on flows"""
        from_comp = flow['from']
        to_comp = flow['to']
        flow_name = flow['name']

        # Update source component outputs
        if from_comp in components_map:
            if flow_name not in components_map[from_comp]['outputs']:
                components_map[from_comp]['outputs'].append(flow_name)

        # Update target component inputs
        if to_comp in components_map:
            if flow_name not in components_map[to_comp]['inputs']:
                components_map[to_comp]['inputs'].append(flow_name)

    def _detect_subjobs(self, components_map: Dict, flows: List[Dict]) -> Dict[str, List[str]]:
        """Auto-detect subjobs based on component connectivity"""
        subjobs = {}
        visited = set()
        subjob_counter = 1

        # Build adjacency lists
        connections = {}
        for flow in flows:
            from_comp = flow['from']
            to_comp = flow['to']

            if from_comp not in connections:
                connections[from_comp] = []
            connections[from_comp].append(to_comp)

            if to_comp not in connections:
                connections[to_comp] = []

        # Find connected components (subjobs)
        for comp_id in components_map:
            if comp_id not in visited:
                # DFS to find all connected components
                subjob_components = []
                stack = [comp_id]

                while stack:
                    current = stack.pop()
                    if current in visited:
                        continue

                    visited.add(current)
                    subjob_components.append(current)

                    # Add connected components
                    if current in connections:
                        for neighbor in connections[current]:
                            if neighbor not in visited:
                                stack.append(neighbor)

                    # Also check reverse connections
                    for from_comp, to_comps in connections.items():
                        if current in to_comps and from_comp not in visited:
                            stack.append(from_comp)

                if subjob_components:
                    subjob_id = f"subjob_{subjob_counter}"
                    subjobs[subjob_id] = subjob_components
                    subjob_counter += 1

        return subjobs

    def _detect_java_requirement(self, components: List[Dict]) -> bool:
        """
        Detect if Java/Groovy execution is required for this job.

        Checks for:
        - Java-specific components (TJavaRow, TJava)
        - Components with {{java}} expressions in config

        Returns:
            True if Java bridge should be enabled
        """
        for component in components:
            component_type = component.get('type', '')

            # Check for Java components
            if component_type in ['tJavaRow', 'tJava', 'JavaRowComponent', 'JavaComponent', 'JavaRow', 'Java']:
                logger.info(f"Java required: Found {component_type} component")
                return True

            # Check for {{java}} markers in config (recursive scan)
            config = component.get('config', {})
            if self._has_java_expressions(config):
                logger.info(f"Java required: Component {component.get('id')} contains {{{{java}}}} expressions")
                return True

        return False

    def _has_java_expressions(self, obj: Any) -> bool:
        """
        Recursively check if object contains {{java}} markers.

        Args:
            obj: Object to scan (dict, list, or primitive)

        Returns:
            True if {{java}} marker found
        """
        if isinstance(obj, dict):
            for value in obj.values():
                if self._has_java_expressions(value):
                    return True
        elif isinstance(obj, list):
            for item in obj:
                if self._has_java_expressions(item):
                    return True
        elif isinstance(obj, str):
            if '{{java}}' in obj:
                return True

        return False

    def save_json(self, job_config: Dict, output_path: str) -> None:
        """Save job configuration to JSON file"""
        with open(output_path, 'w') as f:
            json.dump(job_config, f, indent=2)
        logger.info(f"Saved job configuration to {output_path}")

    def _parse_row_generator(self, node):
        """
        Parse tRowGenerator component from Talend XML node.
        Extracts NB_ROWS, VALUES (with hex decoding), and output schema.
        Maps to ETL-AGENT RowGenerator config format.
        """
        component = self.component_parser.parse_base_component(node)
        # Extract NB_ROWS
        nb_rows = None
        for param in node.findall('.//elementParameter[@name="NB_ROWS"]'):
            nb_rows = param.get('value', '1')
            break
        # Extract VALUES table
        values = []
        for table in node.findall('.//elementParameter[@name="VALUES"]'):
            schema_column = None
            array = None
            for elem in table.findall('.//elementValue'):
                ref = elem.get('elementRef')
                val = elem.get('value', '')
                hex_val = elem.get('hexValue', 'false').lower() == 'true'
                if ref == 'SCHEMA_COLUMN':
                    schema_column = val
                elif ref == 'ARRAY':
                    if hex_val:
                        try:
                            import binascii
                            val = binascii.unhexlify(val).decode('utf-8')
                        except Exception:
                            pass
                    array = val
            if schema_column:
                values.append({'schema_column': schema_column, 'array': array})
        # Extract output schema from metadata
        output_schema = []
        for metadata in node.findall('.//metadata[@connector="FLOW"]'):
            for column in metadata.findall('.//column'):
                output_schema.append({
                    'name': column.get('name', ''),
                    'type': column.get('type', 'id_String'),
                    'nullable': column.get('nullable', 'true').lower() == 'true',
                    'key': column.get('key', 'false').lower() == 'true',
                    'length': int(column.get('length', -1)),
                    'precision': int(column.get('precision', -1))
                })
        # Map to RowGenerator config
        component['config']['nb_rows'] = nb_rows
        component['config']['values'] = values
        component['schema']['output'] = output_schema
        return component


def convert_complex_job(input_path: str, output_path: str = None) -> Dict[str, Any]:
    """
    Convert a complex Talend job to JSON format

    Args:
        input_path: Path to .item XML file
        output_path: Optional path to save JSON output

    Returns:
        Job configuration dictionary
    """
    converter = ComplexTalendConverter()
    try:
        # Debugging log to verify input path
        logger.debug(f"Converting Talend XML file: {input_path}")

        # Parse the XML file
        job_config = converter.convert_file(input_path)

        # Debugging log to verify job configuration
        logger.debug(f"Job configuration parsed: {job_config}")

        if output_path:
            converter.save_json(job_config, output_path)

        return job_config
    except Exception as e:
        logger.error(f"Error during conversion: {e}")
        raise


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python converter.py <input.item> [output.json]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    if not output_file:
        output_file = Path(input_file).stem + '_converted.json'

    job_config = convert_complex_job(input_file, output_file)

    print(f"Successfully converted {input_file}")
    print(f"Components: {len(job_config['components'])}")
    print(f"Flows: {len(job_config['flows'])}")
    print(f"Triggers: {len(job_config['triggers'])}")
    print(f"Subjobs: {len(job_config['subjobs'])}")
