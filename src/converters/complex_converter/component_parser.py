"""
Component-specific parsers for Talend components
"""

from typing import Dict, Any, Optional
from .expression_converter import ExpressionConverter
import logging


class ComponentParser:
    """Parses different types of Talend components"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.expr_converter = ExpressionConverter()

        # Map Talend components to our Python components
        self.component_mapping = {

            # File components
            'tFileInputDelimited': 'FileInputDelimited',
            'tFileOutputDelimited': 'FileOutputDelimited',
            'tFileInputPositional': 'FileInputPositional',
            'tFileOutputPositional': 'FileOutputPositional',
            'tFileInputXML': 'FileInputXML',
            'tFileInputFullRow': 'FileInputFullRowComponent',
            'tFileInputRaw': 'TFileInputRaw',
            'tFixedFlowInput': 'FixedFlowInputComponent',
            'tFileArchive': 'FileArchiveComponent',
            'tFileUnarchive': 'FileUnarchiveComponent',
            'tFileDelete': 'FileDelete',
            'tFileCopy': 'FileCopy',
            'tFileExist': 'FileExistComponent',
            'tFileProperties': 'FileProperties',
            'tFileRowCount': 'FileRowCount',
            'tFileTouch': 'FileTouch',
            'tSetGlobalVar': 'SetGlobalVar',

            # Database components - Oracle
            'tOracleConnection': 'OracleConnection',
            'tOracleInput': 'OracleInput',
            'tOracleOutput': 'OracleOutput',
            'tOracleClose': 'OracleClose',
            'tOracleCommit': 'OracleCommit',
            'tOracleRollback': 'OracleRollback',
            'tOracleRow': 'OracleRow',
            'tOracleSP': 'OracleSP',
            'tOracleBulkExec': 'OracleBulkExec',

            # Database components - MS SQL Server
            'tMSSqlConnection': 'MSSqlConnection',
            'tMSSqlInput': 'MSSqlInput',

            # Transform components
            'tMap': 'Map',
            'tFilterRow': 'FilterRows',
            'tFilterRows': 'FilterRows',
            'tSortRow': 'SortRow',
            'tLogRow': 'LogRow',
            'tJavaRow': 'JavaRowComponent',
            'tJava': 'JavaComponent',
            'tPythonRow': 'PythonRowComponent',
            'tPython': 'PythonComponent',
            'tPythonDataFrame': 'PythonDataFrameComponent',
            'tRowGenerator': 'RowGenerator',
            'tReplicate': 'Replicate',
            'tNormalize': 'Normalize',
            'tDenormalize': 'Denormalize',
            'tExtractDelimitedFields': 'ExtractDelimitedFields',
            'tExtractJSONFields': 'ExtractJSONFields',
            'tAggregateSortedRow': 'TAggregateSortedRow',
            'tSwiftDataTransformer': 'TSwiftDataTransformer',

            # Aggregate components
            'tAggregateRow': 'AggregateRow',
            'tUniqueRow': 'UniqueRow',
            'tUniqRow': 'UniqueRow',

            # Context components
            'tContextLoad': 'ContextLoad',

            # Control components
            'tDie': 'Die',
            'tWarn': 'Warn',
            'tPrejob': 'PrejobComponent',
            'tPostjob': 'PostjobComponent',
            'tRunJob': 'RunJobComponent',
            'tSendMail': 'SendMailComponent',
            'tSleep': 'SleepComponent',

            # Iterate components (registered in engine)
            'tFileList': 'FileList',
            'tFlowToIterate': 'FlowToIterate',

            # Legacy mappings for backward compatibility
            'tDBConnection': 'OracleConnection',
            'tFileInputExcel': 'FileInputExcel',
            'tXMLMap': 'TXMLMap',
            'tFileInputMSXML': 'FileInputMSXMLComponent',
            'tAdvancedFileOutputXML': 'AdvancedFileOutputXMLComponent',
            'tFileInputJSON': 'FileInputJSONComponent',
            'tFileOutputExcel': 'FileOutputExcelComponent'
        }

    def _map_component_parameters(self, component_type: str, config_raw: Dict[str, Any]) -> Dict[str, Any]:
        """Map Talend parameters to Python parameters based on component type"""

        # FileInputDelimited mapping
        if component_type == 'tFileInputDelimited':
            header_value = config_raw.get('HEADER', '0')
            footer_value = config_raw.get('FOOTER', '0')

            return {
                'filepath': config_raw.get('FILENAME', ''),
                'delimiter': config_raw.get('FIELDSEPARATOR', ','),
                'row_separator': config_raw.get('ROWSEPARATOR', '\n'),
                'header_rows': int(header_value) if header_value.isdigit() else header_value,
                'footer_rows': int(footer_value) if footer_value.isdigit() else footer_value,
                'limit': config_raw.get('LIMIT', ''),
                'encoding': config_raw.get('ENCODING', 'UTF-8'),
                'text_enclosure': config_raw.get('TEXT_ENCLOSURE', '').replace('\\\"', ''),
                'escape_char': config_raw.get('ESCAPE_CHAR', '\\').replace('\\\\', '').replace('\\\\\\', '\\'),
                'remove_empty_rows': config_raw.get('REMOVE_EMPTY_ROW', False),
                'trim_all': config_raw.get('TRIMALL', False),
                'die_on_error': config_raw.get('DIE_ON_ERROR', False)
            }

            # FileOutputDelimited mapping
        elif component_type == 'tFileOutputDelimited':
            csv_option = config_raw.get('CSV_OPTION', False)
            if str(csv_option).lower() == 'true':
                text_enclosure = config_raw.get('TEXT_ENCLOSURE', '').replace('\\"', '')
            else:
                text_enclosure = None
            return {
                'filepath': config_raw.get('FILENAME', ''),
                'delimiter': config_raw.get('FIELDSEPARATOR', ','),
                'row_separator': config_raw.get('ROWSEPARATOR', '\n'),
                'encoding': config_raw.get('ENCODING', 'UTF-8'),
                'text_enclosure': text_enclosure,
                'include_header': config_raw.get('INCLUDEHEADER', True),
                'append': config_raw.get('APPEND', False),
                'create_directory': config_raw.get('CREATE', True),
                'delete_empty_file': config_raw.get('DELETE_EMPTYFILE', True),
                'die_on_error': config_raw.get('DIE_ON_ERROR', False),
                'csv_option': csv_option
            }

        # FileInputPositional mapping
        elif component_type == 'tFileInputPositional':
            header_value = config_raw.get('HEADER', '0')
            footer_value = config_raw.get('FOOTER', '0')
            return {
                'filepath': config_raw.get('FILENAME', ''),
                'row_separator': config_raw.get('ROWSEPARATOR', '\n'),
                'pattern': config_raw.get('PATTERN', ''),
                'pattern_units': config_raw.get('PATTERN_UNITS', 'SYMBOLS'),
                'remove_empty_row': config_raw.get('REMOVE_EMPTY_ROW', False),
                'trim_all': config_raw.get('TRIMALL', False),
                'encoding': config_raw.get('ENCODING', 'UTF-8'),
                'header_rows': int(header_value) if header_value.isdigit() else header_value,
                'footer_rows': int(footer_value) if footer_value.isdigit() else footer_value,
                'limit': config_raw.get('LIMIT', ''),
                'die_on_error': config_raw.get('DIE_ON_ERROR', False),
                'process_long_row': config_raw.get('PROCESS_LONG_ROW', False),
                'advanced_separator': config_raw.get('ADVANCED_SEPARATOR', False),
                'thousands_separator': config_raw.get('THOUSANDS_SEPARATOR', ','),
                'decimal_separator': config_raw.get('DECIMAL_SEPARATOR', '.'),
                'check_date': config_raw.get('CHECK_DATE', False),
                'uncompress': config_raw.get('UNCOMPRESS', False)
            }
        # FileOutputPositional mapping
        elif component_type == 'tFileOutputPositional':
            return {
                'filepath': config_raw.get('FILENAME', ''),
                'row_separator': config_raw.get('ROWSEPARATOR', '\n'),
                'append': config_raw.get('APPEND', False),
                'include_header': config_raw.get('INCLUDEHEADER', True),
                'compress': config_raw.get('COMPRESS', False),
                'encoding': config_raw.get('ENCODING', 'UTF-8'),
                'create': config_raw.get('CREATE', True),
                'flush_on_row': config_raw.get('FLUSHONROW', False),
                'flush_on_row_num': config_raw.get('FLUSHONROW_NUM', 1),
                'delete_empty_file': config_raw.get('DELETE_EMPTYFILE', False),
                'formats': config_raw.get('FORMATS', []),
                'die_on_error': config_raw.get('DIE_ON_ERROR', True)
            }

        # FilterRows mapping
        elif component_type in ['tFilterRow', 'tFilterRows']:
            # FilterRows has special handling for conditions
            return {
                'conditions': config_raw.get('CONDITIONS', []),
                'logical_operator': config_raw.get('LOGICAL_OP', 'AND').strip('""'),
                'use_advanced': config_raw.get('USE_ADVANCED', False),
                'advanced_condition': config_raw.get('ADVANCED_CONDITION', '')
            }

        # FilterColumns mapping
        elif component_type == 'tFilterColumns':
            return {
                'columns': config_raw.get('COLUMNS', []),
                'mode': config_raw.get('MODE', 'include'),
                'keep_row_order': config_raw.get('KEEP_ROW_ORDER', True)
            }

        # UniqueRow mapping
        elif component_type == 'tUniqueRow':
            return {
                'key_columns': config_raw.get('UNIQUE_KEY', []),
                'case_sensitive': config_raw.get('CASE_SENSITIVE', True),
                'keep': 'first' if config_raw.get('KEEP_FIRST', True) else 'last',
                'output_duplicates': config_raw.get('OUTPUT_DUPLICATES', True),
                'is_reject_duplicate': config_raw.get('IS_REJECT_DUPLICATE', True)
            }
        # SortRow mapping
        elif component_type == 'tSortRow':
            return {
                'sort_columns': config_raw.get('CRITERIA', []),
                'sort_orders': config_raw.get('SORT_ORDERS', []),
                'na_position': config_raw.get('NA_POSITION', 'last'),
                'case_sensitive': config_raw.get('CASE_SENSITIVE', True),
                'external_sort': config_raw.get('EXTERNAL_SORT', False),
                'max_memory_rows': int(config_raw.get('MAX_MEMORY_ROWS', '1000000')) if str(config_raw.get('MAX_MEMORY_ROWS', '1000000')).isdigit() else 1000000,
                'temp_dir': config_raw.get('TEMPFILE', ''),
                'chunk_size': int(config_raw.get('CHUNK_SIZE', '10000')) if str(config_raw.get('CHUNK_SIZE', '10000')).isdigit() else 10000
            }

        # Unite mapping
        elif component_type == 'tUnite':
            return {
                'mode': config_raw.get('MODE', 'UNION'),
                'remove_duplicates': config_raw.get('REMOVE_DUPLICATES', False),
                'keep': config_raw.get('KEEP', 'first'),
                'sort_output': config_raw.get('SORT_OUTPUT', False),
                'sort_columns': config_raw.get('SORT_COLUMNS', []),
                'merge_columns': config_raw.get('MERGE_COLUMNS', None),
                'merge_how': config_raw.get('MERGE_HOW', 'inner')
            }

        # ContextLoad mapping
        elif component_type == 'tContextLoad':
            return {
                'filepath': config_raw.get('CONTEXTFILE', ''),
                'format': config_raw.get('FORMAT', 'properties'),
                'delimiter': config_raw.get('FIELDSEPARATOR', ';'),
                'csv_separator': config_raw.get('CSV_SEPARATOR', ','),
                'print_operations': config_raw.get('PRINT_OPERATIONS', False),
                'error_if_not_exists': config_raw.get('ERROR_IF_NOT_EXISTS', True)
            }

        # Warn mapping
        elif component_type == 'tWarn':
            return {
                'message': config_raw.get('MESSAGE', 'Warning'),
                'code': int(config_raw.get('CODE', '0')) if str(config_raw.get('CODE', '0')).isdigit() else 0,
                'priority': int(config_raw.get('PRIORITY', '4')) if str(config_raw.get('PRIORITY', '4')).isdigit() else 4
            }

        # Die mapping
        elif component_type == 'tDie':
            return {
                'message': config_raw.get('MESSAGE', 'Job execution stopped'),
                'code': int(config_raw.get('CODE', '1')) if str(config_raw.get('CODE', '1')).isdigit() else 1,
                'priority': int(config_raw.get('PRIORITY', '5')) if str(config_raw.get('PRIORITY', '5')).isdigit() else 5,
                'exit_code': int(config_raw.get('EXIT_CODE', '1')) if str(config_raw.get('EXIT_CODE', '1')).isdigit() else 1
            }

        # Map component - special handling, can have two styles
        elif component_type == 'tMap':
            # tMap configuration is handled specially in parse_tmap method
            # Just return the raw config for now
            return config_raw

        # tFileCopy mapping
        elif component_type == 'tFileCopy':
            return {
                'source': config_raw.get('FILENAME', ''),
                'destination': config_raw.get('DESTINATION', ''),
                'rename': config_raw.get('RENAME', False),
                'new_name': config_raw.get('DESTINATION_RENAME', ''),
                'replace_file': config_raw.get('REPLACE_FILE', True),
                'create_directory': config_raw.get('CREATE_DIRECTORY', True),
                'preserve_last_modified': config_raw.get('PRESERVE_LAST_MODIFIED_TIME', False)
            }

        # tFileTouch mapping
        elif component_type == 'tFileTouch':
            return {
                'filename': config_raw.get('FILENAME', ''),
                'create_directory': config_raw.get('CREATEDIR', False)
            }

        # tExtractJSONFields mapping
        elif component_type == 'tExtractDelimitedFields':
            sep = config_raw.get('FIELDSEPARATOR', ';')
            sep = sep.strip()
            # Handle XML-encoded and plain quoted values
            if (sep.startswith('&quot;') and sep.endswith('&quot;')) or (sep.startswith('"') and sep.endswith('"')):
                sep = sep[1:-1]
            return {
                'field': config_raw.get('FIELD', ''),
                'field_separator': sep,
                'ignore_source_null': config_raw.get('IGNORE_SOURCE_NULL', False),
                'die_on_error': config_raw.get('DIE_ON_ERROR', False),
                'advanced_separator': config_raw.get('ADVANCED_SEPARATOR', False),
                'thousands_separator': config_raw.get('THOUSANDS_SEPARATOR', ','),
                'decimal_separator': config_raw.get('DECIMAL_SEPARATOR', '.'),
                'trim': config_raw.get('TRIM', False),
                'check_fields_num': config_raw.get('CHECK_FIELDS_NUM', False),
                'check_date': config_raw.get('CHECK_DATE', False),
                'schema_opt_num': config_raw.get('SCHEMA_OPT_NUM', '100'),
                'connection_format': config_raw.get('CONNECTION_FORMAT', 'row')
            }

        # tJavaRow mapping
        elif component_type == 'tJavaRow':
            # Decode the Java code (XML entities)
            code = config_raw.get('CODE', '')
            # Replace XML line break entities with actual newlines
            code = code.replace('&#xD;&#xA;', '\n').replace('&#xA;', '\n').replace('&#xD;', '\n')

            # Decode imports
            imports = config_raw.get('IMPORT', '')
            imports = imports.replace('&#xD;&#xA;', '\n').replace('&#xA;', '\n').replace('&#xD;', '\n')

            return {
                'java_code': code,
                'imports': imports
            }

        # tJava mapping (similar to tJavaRow but for one-time execution)
        elif component_type == 'tJava':
            # Decode the Java code (XML entities)
            code = config_raw.get('CODE', '')
            # Replace XML line break entities with actual newlines
            code = code.replace('&#xD;&#xA;', '\n').replace('&#xA;', '\n').replace('&#xD;', '\n')

            # Decode imports
            imports = config_raw.get('IMPORT', '')
            imports = imports.replace('&#xD;&#xA;', '\n').replace('&#xA;', '\n').replace('&#xD;', '\n')

            return {
                'java_code': code,
                'imports': imports
            }
        # tFileList mapping
        elif component_type == 'tFileList':
            # Parse file masks table
            files = []
            files_config = config_raw.get('FILES', [])
            if isinstance(files_config, list):
                for file_mask in files_config:
                    if isinstance(file_mask, dict):
                        files.append({'filemask': file_mask.get('FILEMASK', '*')})
                    else:
                        files.append({'filemask': str(file_mask)})

            return {
                'directory': config_raw.get('DIRECTORY', ''),
                'list_mode': config_raw.get('LIST_MODE', 'FILES'),
                'include_subdirs': config_raw.get('INCLUDESUBDIR', False),
                'case_sensitive': config_raw.get('CASE_SENSITIVE', 'YES'),
                'error': config_raw.get('ERROR', True),
                'glob_expressions': config_raw.get('GLOBEXPRESSIONS', True),
                'files': files,
                'order_by_nothing': config_raw.get('ORDER_BY_NOTHING', False),
                'order_by_filename': config_raw.get('ORDER_BY_FILENAME', False),
                'order_by_filesize': config_raw.get('ORDER_BY_FILESIZE', False),
                'order_by_modifieddate': config_raw.get('ORDER_BY_MODIFIEDDATE', False),
                'order_action_asc': config_raw.get('ORDER_ACTION_ASC', True),
                'order_action_desc': config_raw.get('ORDER_ACTION_DESC', False),
                'exclude_file': config_raw.get('IFEXCLUDE', False),
                'exclude_filemask': config_raw.get('EXCLUDEFILEMASK', '')
            }

        # tFlowToIterate mapping
        elif component_type == 'tFlowToIterate':
            return {
                'default_map': config_raw.get('DEFAULT_MAP', True),
                'map': config_raw.get('MAP', [])
            }

        # Default - return raw config for unmapped components
        else:
            return config_raw
        
    def parse_base_component(self, node) -> Optional[Dict[str, Any]]:
        """Parse basic component information"""
        component_name = node.get('componentName')
        if not component_name:
            return None

        # Get unique name
        unique_name = None
        for param in node.findall('.//elementParameter[@name="UNIQUE_NAME"]'):
            unique_name = param.get('value', '').strip('"')
            break

        if not unique_name:
            unique_name = f"{component_name}_{node.get('offsetLabelX', '0')}_{node.get('offsetLabelY', '0')}"

        # Map to our component type
        mapped_type = self.component_mapping.get(component_name, component_name)

        component = {
            'id': unique_name,
            'type': mapped_type,
            'original_type': component_name,
            'position': {
                'x': int(node.get('posX', 0)),
                'y': int(node.get('posY', 0))
            },
            'config': {},
            'schema': {'input': [], 'output': []},
            'inputs': [],
            'outputs': []
        }

        # **Components with dedicated parsers that handle all config internally**
        components_with_dedicated_parsers = [
            'tFileInputExcel',  # Has comprehensive parse_file_input_excel()
            'tMap',             # Has comprehensive parse_tmap()
            # Add more components here as they get dedicated parsers
        ]

        # **Skip raw parameter processing for components with dedicated parsers**
        if component_name in components_with_dedicated_parsers:
            # Only set empty config - dedicated parser will populate it completely
            component['config'] = {}
        else:
            # Parse basic configuration for components without dedicated parsers
            config_raw = {}
            for param in node.findall('.//elementParameter'):
                name = param.get('name')
                value = param.get('value', '')
                field = param.get('field')

                if name and name != 'UNIQUE_NAME':
                    # Clean up value
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]

                    # Convert boolean values
                    if field == 'CHECK':
                        value = value.lower() == 'true'
                    # Skip CODE and IMPORT fields - they contain raw Java code
                    # and are handled by component-specific parsers (tJava, tJavaRow)
                    elif name not in ['CODE', 'IMPORT'] and isinstance(value, str) and 'context.' in value:
                        # For string values with context references, check if it's a Java expression first
                        # If it's a Java expression (has operators, methods, etc.), leave as-is
                        # ExpressionConverter will mark it with {{java}} later
                        # Otherwise, wrap simple context refs with ${...} for ContextManager
                        if not self.expr_converter.detect_java_expression(value):
                            # Simple context reference - wrap with ${...}
                            value = '${' + value + '}'

                    config_raw[name] = value

            # Mark Java expressions in config_raw (BEFORE mapping to component config)
            # Skip for components that handle Java code specially
            if component_name not in ['tMap', 'tJavaRow', 'tJava']:
                # Skip CODE and IMPORT fields (handled specially in parameter mapping)
                skip_fields = ['CODE', 'IMPORT', 'UNIQUE_NAME']

                for key, value in config_raw.items():
                    if key not in skip_fields and isinstance(value, str):
                        # Mark with {{java}} if it's a Java expression
                        config_raw[key] = self.expr_converter.mark_java_expression(value)

            # Map parameters based on component type
            component['config'] = self._map_component_parameters(component_name, config_raw)

            # Parse metadata schemas (always needed)
            for metadata in node.findall('./metadata'):
                connector = metadata.get('connector', 'FLOW')
                schema_cols = []

                for column in metadata.findall('./column'):
                    col_info = {
                        'name': column.get('name', ''),
                        'type': self.expr_converter.convert_type(column.get('type', 'id_String')),
                        'nullable': column.get('nullable', 'true').lower() == 'true',
                        'key': column.get('key', 'false').lower() == 'true'
                    }

                    # Add additional properties if present
                    if column.get('length'):
                        col_info['length'] = int(column.get('length'))
                    if column.get('precision'):
                        col_info['precision'] = int(column.get('precision'))
                    # Capture date pattern if present
                    if column.get('pattern'):
                        pattern = column.get('pattern').strip('"')
                        if pattern:  # Only add if not empty
                            # Convert Java date pattern to Python strftime format
                            # TODO: Handle more Java datetime formats beyond basic yyyy-mm-dd
                            pattern = pattern.replace('yyyy', '%Y').replace('MM', '%m').replace('dd', '%d')
                            pattern = pattern.replace('HH', '%H').replace('mm', '%M').replace('ss', '%S')
                            col_info['date_pattern'] = pattern

                    schema_cols.append(col_info)

                if connector == 'FLOW':
                    component['schema']['output'] = schema_cols
                elif connector == 'REJECT':
                    component['schema']['reject'] = schema_cols

            return component

    def parse_tmap(self, node, component: Dict) -> Dict:
        """
        Parse tMap specific configuration to match new JSON structure

        New structure:
        {
            "inputs": {
                "main": {...},
                "lookups": [...]
            },
            "variables": [...],
            "outputs": [...]
        }
        """
        # Look for nodeData element with MapperData type
        mapper_data = None
        for node_data in node.findall('.//nodeData'):
            if 'MapperData' in node_data.get('{http://www.w3.org/2001/XMLSchema-instance}type', ''):
                mapper_data = node_data
                break

        if not mapper_data:
            # Fallback to old structure
            mapper_data = node.find('.//MapperData')

        if not mapper_data:
            return component

        # ============================================================
        # PHASE 1: Parse inputTables (main + lookups)
        # ============================================================
        input_tables_xml = mapper_data.findall('.//inputTables')

        if not input_tables_xml:
            return component

        # First input is always MAIN
        main_input_xml = input_tables_xml[0]
        main_name = main_input_xml.get('name', '')

        main_filter = ''
        if main_input_xml.get('activateExpressionFilter', 'false').lower() == 'true':
            main_filter = main_input_xml.get('expressionFilter', '').strip()
        # Mark with {{java}} for Java execution
        if main_filter:
            main_filter = f"{{{{java}}}}{main_filter}"

        main_config = {
            'name': main_name,
            'filter': main_filter,
            'activate_filter': main_input_xml.get('activateExpressionFilter', 'false').lower() == 'true',
            'matching_mode': main_input_xml.get('matchingMode', 'UNIQUE_MATCH'),
            'lookup_mode': main_input_xml.get('lookupMode', 'LOAD_ONCE')
        }

        # Remaining inputs are LOOKUPS
        lookups_config = []
        for lookup_xml in input_tables_xml[1:]:
            lookup_name = lookup_xml.get('name', '')

            # Parse join keys (mapperTableEntries with 'expression' attribute)
            join_keys = []
            for col in lookup_xml.findall('./mapperTableEntries'):
                col_expression = col.get('expression', '').strip()
                if col_expression:  # Has expression = this is a join key
                    join_key = {
                        'lookup_column': col.get('name', ''),
                        'expression': f"{{{{java}}}}{col_expression}"  # Mark for Java execution
                    }
                    join_keys.append(join_key)

            # Parse lookup filter (if exists)
            lookup_filter = ''
            if lookup_xml.get('activateExpressionFilter', 'false').lower() == 'true':
                lookup_filter = lookup_xml.get('expressionFilter', '').strip()
                if lookup_filter:
                    lookup_filter = f"{{{{java}}}}{lookup_filter}"

            # Parse join mode
            join_mode = "INNER_JOIN" if lookup_xml.get('innerJoin', 'false').lower() == 'true' else "LEFT_OUTER_JOIN"

            lookup_config = {
                'name': lookup_name,
                'matching_mode': lookup_xml.get('matchingMode', 'UNIQUE_MATCH'),
                'lookup_mode': lookup_xml.get('lookupMode', 'LOAD_ONCE'),
                'filter': lookup_filter,
                'activate_filter': lookup_xml.get('activateExpressionFilter', 'false').lower() == 'true',
                'join_keys': join_keys,
                'join_mode': join_mode
            }
            lookups_config.append(lookup_config)

        # ============================================================
        # PHASE 2: Parse varTables (variables)
        # ============================================================
        variables_config = []
        for var_table in mapper_data.findall('./varTables'):
            for var_entry in var_table.findall('./mapperTableEntries'):
                var_name = var_entry.get('name', '')
                var_expression = var_entry.get('expression', '').strip()
                var_type = self.expr_converter.convert_type(var_entry.get('type', 'id_String'))

                if var_name and var_expression:
                    variable = {
                        'name': var_name,
                        'expression': f"{{{{java}}}}{var_expression}",  # Mark for Java execution
                        'type': var_entry.get('type', 'id_String')  # Keep Talend type format
                    }
                    variables_config.append(variable)

        # ============================================================
        # PHASE 3: Parse outputTables (outputs)
        # ============================================================
        outputs_config = []
        for output_xml in mapper_data.findall('./outputTables'):
            output_name = output_xml.get('name', '')
            is_reject = output_xml.get('reject', 'false').lower() == 'true'
            # -- inner_join_reject logic ---
            inner_join_reject = output_xml.get('rejectInnerJoin', 'false').lower() == 'true'

            # Parse output filter
            output_filter = ''
            if output_xml.get('activateExpressionFilter', 'false').lower() == 'true':
                output_filter = output_xml.get('expressionFilter', '').strip()
                if output_filter:
                    output_filter = f"{{{{java}}}}{output_filter}"

            # Parse output columns
            columns = []
            for col in output_xml.findall('./mapperTableEntries'):
                col_name = col.get('name', '')
                col_expression = col.get('expression', '').strip()
                col_type = col.get('type', 'id_String')
                col_nullable = col.get('nullable', 'true').lower() == 'true'

                column = {
                    'name': col_name,
                    'expression': f"{{{{java}}}}{col_expression}" if col_expression else "",
                    'type': col_type,  # Keep Talend type format
                    'nullable': col_nullable
                }
                columns.append(column)

            output = {
                'name': output_name,
                'is_reject': is_reject,
                'inner_join_reject': inner_join_reject,  # <-- Added here
                'filter': output_filter,
                'activate_filter': output_xml.get('activateExpressionFilter', 'false').lower() == 'true',
                'columns': columns
            }
            outputs_config.append(output)

        # ============================================================
        # Build final config structure
        # ============================================================
        component['config'] = {
            'inputs': {
                'main': main_config,
                'lookups': lookups_config
            },
            'variables': variables_config,
            'outputs': outputs_config
        }

        # Also populate component.inputs and component.outputs arrays
        # These are used by the engine for flow routing
        component['inputs'] = [main_name] + [lookup['name'] for lookup in lookups_config]
        component['outputs'] = [output['name'] for output in outputs_config]

        return component
    
    def parse_aggregate(self, node, component: Dict) -> Dict:
        """
        Parse tAggregateRow component from Talend XML node.
        Extracts GROUPBYS and OPERATIONS tables and builds output schema.
        Maps to ETL-AGENT AggregateRow config format.
        """

        # Parse GROUPBYS
        group_by = []
        for table in node.findall('.//elementParameter[@name="GROUPBYS"]'):
            for elem in table.findall('./elementValue'):
                if elem.get('elementRef') == 'INPUT_COLUMN':
                    group_by.append(elem.get('value', ''))

        # Parse OPERATIONS
        operations = []
        for table in node.findall('.//elementParameter[@name="OPERATIONS"]'):
            elems = list(table.findall('.//elementValue'))
            # Each operation is a group of 4: OUTPUT_COLUMN, INPUT_COLUMN, FUNCTION, IGNORE_NULL
            for i in range(0, len(elems), 4):
                op = {}
                for j in range(4):
                    if i + j < len(elems):
                        ref = elems[i + j].get('elementRef')
                        val = elems[i + j].get('value', '')
                        if ref == 'OUTPUT_COLUMN':
                            op['output_column'] = val
                        elif ref == 'INPUT_COLUMN':
                            op['input_column'] = val
                        elif ref == 'FUNCTION':
                            op['function'] = val
                        elif ref == 'IGNORE_NULL':
                            op['ignore_null'] = val.lower() == 'true'
                if op:
                    operations.append(op)

        # --- DEBUG: Log group_by and operations parsing ---
        print(f"[parse_aggregate] Parsed group_by columns: {group_by}")
        print(f"[parse_aggregate] Parsed operations: {operations}")

        # Build output schema from metadata
        output_schema = []
        for metadata in node.findall('./metadata[@connector="FLOW"]'):
            for column in metadata.findall('./column'):
                output_schema.append({
                    'name': column.get('name', ''),
                    'type': column.get('type', 'id_String'),
                    'nullable': column.get('nullable', 'true').lower() == 'true',
                    'key': column.get('key', 'false').lower() == 'true',
                    'length': int(column.get('length', -1)),
                    'precision': int(column.get('precision', -1))
                })

        # --- DEBUG: Log output schema ---
        print(f"[parse_aggregate] Parsed output schema: {output_schema}")

        component['config']['group_by'] = group_by
        component['config']['operations'] = operations
        component['config']['output'] = output_schema
        return component

    def parse_filter_rows(self, node, component: Dict) -> Dict:
        """
        Parse tFilterRow/tFilterRows component from Talend XML node.
        Extracts filter conditions and maps to ETL-AGENT FilterRows config format.
        """
        # Extract LOGICAL_OP
        logical_op = None
        for param in node.findall('.//elementParameter[@name="LOGICAL_OP"]'):
            logical_op = param.get('value', 'AND').replace('&amp;&amp;', 'AND').replace('||', 'OR')
            break
        # Extract USE_ADVANCED
        use_advanced = False
        for param in node.findall('.//elementParameter[@name="USE_ADVANCED"]'):
            use_advanced = param.get('value', 'false').lower() == 'true'
            break
        # Extract ADVANCED_COND
        advanced_cond = ''
        for param in node.findall('.//elementParameter[@name="ADVANCED_COND"]'):
            advanced_cond = param.get('value', '')
            break
        # Extract CONDITIONS table
        conditions = []
        for table in node.findall('.//elementParameter[@name="CONDITIONS"]'):
            cond = {}
            for elem in table.findall('.//elementValue'):
                ref = elem.get('elementRef')
                val = elem.get('value', '')
                if ref == 'INPUT_COLUMN':
                    cond['column'] = val
                elif ref == 'OPERATOR':
                    cond['operator'] = val
                elif ref == 'RVALUE':
                    cond['value'] = val
            if cond:
                conditions.append(cond)
        # Map to config
        component['config']['logical_operator'] = logical_op or 'AND'
        component['config']['use_advanced'] = use_advanced
        component['config']['advanced_condition'] = advanced_cond
        component['config']['conditions'] = conditions
        return component

    def parse_filter_columns(self, node, component: Dict) -> Dict:
        """Parse tFilterColumns specific configuration"""
        columns = []
        # FIX: Extract columns from <metadata connector="FLOW"> section, not <elementParameter name="SCHEMA">
        for metadata in node.findall('.//metadata[@connector="FLOW"]'):
            for column in metadata.findall('./column'):
                col_name = column.get('name', '')
                if col_name:
                    columns.append(col_name)
        component['config']['columns'] = columns
        return component

    def parse_unique(self, node, component: Dict) -> Dict:
        """Parse tUniqueRow specific configuration"""
        key_columns = []

        # Add debugging to see what we're parsing
        print(f"[DEBUG] Parsing tUniqueRow component: {component.get('id', 'unknown')}")

        # Parse UNIQUE_KEY table parameter - handle SCHEMA_COLUMN/KEY_ATTRIBUTE pairs
        unique_key_params = node.findall('.//elementParameter[@name="UNIQUE_KEY"]')
        print(f"[DEBUG] Found {len(unique_key_params)} UNIQUE_KEY parameters")

        for param in unique_key_params:
            elements = list(param.findall('./elementValue'))
            print(f"[DEBUG] Found {len(elements)} elementValue entries in UNIQUE_KEY")

# Group elements by sets of 3 (SCHEMA_COLUMN, KEY_ATTRIBUTE, CASE_SENSITIVE)
        for i in range(0, len(elements), 3):
            if i + 2 < len(elements):
                schema_col_elem = elements[i]
                key_attr_elem = elements[i + 1]
                case_sensitive_elem = elements[i + 2]

                print(f"[DEBUG] Element {i//3 + 1}:")
                print(f"  Schema: ref='{schema_col_elem.get('elementRef')}' value='{schema_col_elem.get('value')}'")
                print(f"  Key Attr: ref='{key_attr_elem.get('elementRef')}' value='{key_attr_elem.get('value')}'")
                print(f"  Case Sens: ref='{case_sensitive_elem.get('elementRef')}' value='{case_sensitive_elem.get('value')}'")

                # Check if this is a key column (KEY_ATTRIBUTE = true)
                if (schema_col_elem.get('elementRef') == 'SCHEMA_COLUMN' and
                    key_attr_elem.get('elementRef') == 'KEY_ATTRIBUTE' and
                    key_attr_elem.get('value', 'false').lower() == 'true'):

                    col_name = schema_col_elem.get('value', '').strip('"')
                    if col_name:
                        key_columns.append(col_name)
                        print(f"[DEBUG] Added key column: {col_name}")

        print(f"[DEBUG] Final key_columns list: {key_columns}")

        # Parse other configuration parameters
        only_once_each_duplicated_key = False
        for param in node.findall('.//elementParameter[@name="ONLY_ONCE_EACH_DUPLICATED_KEY"]'):
            only_once_each_duplicated_key = param.get('value', 'false').lower() == 'true'
            break

        connection_format = 'row'
        for param in node.findall('.//elementParameter[@name="CONNECTION_FORMAT"]'):
            connection_format = param.get('value', 'row')
            break

        # Map to component config
        component['config']['key_columns'] = key_columns
        component['config']['case_sensitive'] = component['config'].get('CASE_SENSITIVE', True)
        component['config']['keep'] = 'last' if only_once_each_duplicated_key else 'first'
        component['config']['output_duplicates'] = True
        component['config']['is_reject_duplicate'] = True
        component['config']['connection_format'] = connection_format

        print(f"[DEBUG] Final component config: {component['config']}")

        return component

    def parse_sort_row(self, node, component: Dict) -> Dict:
        """Parse tSortRow specific configuration"""
        sort_columns = []
        sort_orders = []

        # Parse CRITERIA table parameter
        for param in node.findall('.//elementParameter[@name="CRITERIA"]'):
            for item in param.findall('./elementValue'):
                if item.get('elementRef') == 'COLNAME':
                    col = item.get('value', '')
                    if col:
                        sort_columns.append(col)
                elif item.get('elementRef') == 'SORT':
                    order = item.get('value', 'asc')
                    sort_orders.append(order.lower())

        # Parse other parameters
        for param in node.findall('.//elementParameter'):
            name = param.get('name')
            value = param.get('value', '')

            if name == 'EXTERNAL_SORT':
                component['config']['external_sort'] = value.lower() == 'true'
            elif name == 'TEMPFILE':
                component['config']['temp_file'] = value.strip('"')

        component['config']['sort_columns'] = sort_columns
        component['config']['sort_orders'] = sort_orders

        return component

    def parse_unite(self, node, component: Dict) -> Dict:
        """Parse tUnite specific configuration"""
        # tUnite is simple - just combines inputs
        # Most configuration is done through connections

        # Check if there are any specific settings
        for param in node.findall('.//elementParameter'):
            name = param.get('name')
            value = param.get('value', '')

        if name == 'REMOVE_DUPLICATES':
            component['config']['remove_duplicates'] = value.lower() == 'true'
        elif name == 'MODE':
            # Some versions might have merge mode
            component['config']['mode'] = value.strip('"')

        # Default mode is UNION
        if 'mode' not in component['config']:
            component['config']['mode'] = 'UNION'

        return component

    def parse_java_row(self, node, component: Dict) -> Dict:
        """Parse tJavaRow specific configuration"""
        # Build output_schema from FLOW metadata
        # Format: {'column_name': 'Type', ...}
        output_schema = {}

        if component['schema'].get('output'):
            for col in component['schema']['output']:
                # Convert Python type back to Java type names
                python_type = col['type']
                java_type = self._python_type_to_java(python_type)
                output_schema[col['name']] = java_type

        component['config']['output_schema'] = output_schema

        return component

    def _python_type_to_java(self, python_type: str) -> str:
        """Convert Python type name to Java type name for output_schema"""
        type_mapping = {
            'str': 'String',
            'int': 'Integer',
            'float': 'Double',
            'bool': 'Boolean',
            'date': 'Date',
            'datetime': 'Date',
            'bytes': 'byte[]'
        }
        return type_mapping.get(python_type, 'String')
    
    def parse_tjoin(self, node, component: Dict) -> Dict:
        """Parse tJoin specific configuration from Talend XML, including FILTER connections as main/lookup inputs"""
        join_keys = []
        case_sensitive = True
        use_inner_join = False
        die_on_error = False

        # Parse JOIN_KEY table parameter
        for param in node.findall('.//elementParameter[@name="JOIN_KEY"]'):
            # Support both LEFT_COLUMN/RIGHT_COLUMN and INPUT_COLUMN/LOOKUP_COLUMN
            main_col = None
            lookup_col = None
            for item in param.findall('./elementValue'):
                ref = item.get('elementRef')
                value = item.get('value', '')
                if ref in ('LEFT_COLUMN', 'INPUT_COLUMN'):
                    main_col = value
                elif ref in ('RIGHT_COLUMN', 'LOOKUP_COLUMN'):
                    lookup_col = value
            # If both are set, append and reset
            if main_col is not None and lookup_col is not None:
                join_keys.append({'main': main_col, 'lookup': lookup_col})
                main_col = None
                lookup_col = None

        # Parse other parameters
        for param in node.findall('.//elementParameter'):
            name = param.get('name')
            value = param.get('value', '')
            if name == 'USE_INNER_JOIN':
                use_inner_join = value.lower() == 'true'
            elif name == 'CASE_SENSITIVE':
                case_sensitive = value.lower() == 'true'
            elif name == 'DIE_ON_ERROR':
                die_on_error = value.lower() == 'true'

        # Find all connections in the document (root-level search)
        root = node
        while hasattr(root, 'getparent') and root.getparent() is not None:
            root = root.getparent()
        connections = []
        for conn in root.findall('.//connection'):
            if conn.get('target') == component['id'] and conn.get('connectorName') in ['FILTER', 'FLOW']:
                connections.append(conn)
        if len(connections) >= 2:
            main_input = connections[0].get('source')
            lookup_input = connections[1].get('source')
            component['inputs'] = [main_input, lookup_input]
        elif len(connections) == 1:
            component['inputs'] = [connections[0].get('source')]

        component['config']['JOIN_KEY'] = join_keys
        component['config']['USE_INNER_JOIN'] = use_inner_join
        component['config']['CASE_SENSITIVE'] = case_sensitive
        component['config']['DIE_ON_ERROR'] = die_on_error
        return component

    def parse_oracle_connection(self, node, component: Dict) -> Dict:
        """Parse tOracleConnection specific configuration"""
        config = component['config']

        for param in node.findall('.//elementParameter'):
            name = param.get('name')
            value = param.get('value', '')

            if name in ['CONNECTION_TYPE', 'HOST', 'PORT', 'DBNAME', 'USER', 'PASS', 'AUTO_COMMIT', 'SUPPORT_NLS']:
                # Map XML parameter names to JSON keys
                key_mapping = {
                    'CONNECTION_TYPE': 'connection_type',
                    'HOST': 'host',
                    'PORT': 'port',
                    'DBNAME': 'dbname',
                    'USER': 'user',
                    'PASS': 'password',
                    'AUTO_COMMIT': 'auto_commit',
                    'SUPPORT_NLS': 'support_nls'
                }

                # Convert values where necessary
                # if name == 'PORT':
                # Strip quotes and check if the value is a valid integer
                stripped_value = value.strip('"')
                # config[key_mapping[name]] = int(context.DB_PORT) if stripped_value.isdigit() else 1521
                # elif name in ['AUTO_COMMIT', 'SUPPORT_NLS']:
                # config[key_mapping[name]] = value.lower() == 'true'
                #elif name == 'PASS':
            # Fetch password from context.DB_PASSWORD
            # config[key_mapping[name]] = 'context.DB_PASSWORD'
        #else:
        config[key_mapping[name]] = value.strip('"')

        component['config'] = config
        return component

    def parse_file_list(self, node, component: Dict) -> Dict:
        """Parse tFileList specific configuration"""
        config = component['config']

        # Map Talend XML parameters to config keys
        for param in node.findall('.//elementParameter'):
            name = param.get('name')
            value = param.get('value', '')
            field = param.get('field')

            if name == 'DIRECTORY':
                config['directory'] = value.strip('"')
            elif name == 'INCLUDESUBDIR':
                config['include_subdirectories'] = value.lower() == 'true'
            elif name == 'CASE_SENSITIVE':
                config['case_sensitive'] = value.lower() == 'yes'
            elif name == 'GLOBEXPRESSIONS':
                config['use_glob_expressions'] = value.lower() == 'true'
            elif name == 'ORDER_BY_FILENAME':
                config['sort_by'] = 'name' if value.lower() == 'true' else config.get('sort_by', 'none')
            elif name == 'ORDER_BY_FILESIZE':
                config['sort_by'] = 'size' if value.lower() == 'true' else config.get('sort_by', 'none')
            elif name == 'ORDER_BY_MODIFIEDDATE':
                config['sort_by'] = 'modified_date' if value.lower() == 'true' else config.get('sort_by', 'none')
            elif name == 'ORDER_ACTION_ASC':
                config['sort_order'] = 'asc' if value.lower() == 'true' else config.get('sort_order', 'desc')
            elif name == 'ORDER_ACTION_DESC':
                config['sort_order'] = 'desc' if value.lower() == 'true' else config.get('sort_order', 'asc')
            elif name == 'IFEXCLUDE':
                config['exclude_files'] = value.lower() == 'true'
            elif name == 'EXCLUDEFILENAME':
                config['exclude_mask'] = value.strip('"')

        component['config'] = config
        return component

    def parse_file_input_full_row(self, node, component: Dict) -> Dict:
        """Parse tFileInputFullRow specific configuration."""
        for param in node.findall('.//elementParameter'):
            name = param.get('name')
            value = param.get('value', '')

            if name == 'FILENAME':
                component['config']['filename'] = value.strip('"')
            elif name == 'ROWSEPARATOR':
                component['config']['row_separator'] = value.strip('"')
            elif name == 'ENCODING':
                component['config']['encoding'] = value.strip('"')
            elif name == 'REMOVE_EMPTY_ROW':
                component['config']['remove_empty_rows'] = value.lower() == 'true'

        return component

    def parse_tfileinputfullrow(self, node, component: Dict) -> Dict:
        """Parse tFileInputFullRow specific configuration"""
        component['config']['filename'] = node.find('.//elementParameter[@name="FILENAME"]').get('value', '')
        component['config']['row_separator'] = node.find('.//elementParameter[@name="ROWSEPARATOR"]').get('value', '\n')
        component['config']['remove_empty_row'] = node.find('.//elementParameter[@name="REMOVE_EMPTY_ROW"]').get('value', 'false').lower() == 'true'
        component['config']['encoding'] = node.find('.//elementParameter[@name="ENCODING"]').get('value', 'UTF-8')
        component['config']['limit'] = node.find('.//elementParameter[@name="LIMIT"]').get('value', '')
        return component

    def parse_tsleep(self, node, component: Dict) -> Dict:
        """Parse tSleep specific configuration"""
        # Extract the pause duration
        for param in node.findall('.//elementParameter[@name="PAUSE"]'):
            component['config']['pause_duration'] = float(param.get('value', '0'))

        return component

    def parse_tprejob(self, node, component: Dict) -> Dict:
        """Parse tPrejob specific configuration"""
        # No specific parameters to parse for tPrejob
        return component

    def parse_tpostjob(self, node, component: Dict) -> Dict:
        """Parse tPostjob specific configuration"""
        # No specific parameters to parse for tPostjob
        return component

    def parse_trunjob(self, node, component: Dict) -> Dict:
        """Parse tRunJob specific configuration"""
        # Extract relevant parameters
        component['config']['process'] = node.find('.//elementParameter[@name="PROCESS"]').get('value', '')
        component['config']['context_name'] = node.find('.//elementParameter[@name="CONTEXT_NAME"]').get('value', 'Default')
        component['config']['die_on_child_error'] = node.find('.//elementParameter[@name="DIE_ON_CHILD_ERROR"]').get('value', 'true').lower() == 'true'
        component['config']['print_parameter'] = node.find('.//elementParameter[@name="PRINT_PARAMETER"]').get('value', 'false').lower() == 'true'
        component['config']['context_params'] = []

        # Parse CONTEXTPARAMS table
        for param in node.findall('.//elementParameter[@name="CONTEXTPARAMS"]/elementValue'):
            context_param = {
                'name': param.get('elementRef', ''),
                'value': param.get('value', '')
            }
            component['config']['context_params'].append(context_param)

        return component

    def parse_tsendmail(self, node, component: Dict) -> Dict:
        """Parse tSendMail specific configuration"""
        component['config']['smtp_host'] = node.find('.//elementParameter[@name="SMTP_HOST"]').get('value', '')
        component['config']['smtp_port'] = int(node.find('.//elementParameter[@name="SMTP_PORT"]').get('value', '25'))
        component['config']['from_email'] = node.find('.//elementParameter[@name="FROM"]').get('value', '')
        component['config']['to'] = [email.strip() for email in node.find('.//elementParameter[@name="TO"]').get('value', '').split(';')]
        component['config']['cc'] = [email.strip() for email in node.find('.//elementParameter[@name="CC"]').get('value', '').split(';')]
        component['config']['bcc'] = [email.strip() for email in node.find('.//elementParameter[@name="BCC"]').get('value', '').split(';')]
        component['config']['subject'] = node.find('.//elementParameter[@name="SUBJECT"]').get('value', '')
        component['config']['message'] = node.find('.//elementParameter[@name="MESSAGE"]').get('value', '')
        component['config']['attachments'] = []
        component['config']['ssl'] = node.find('.//elementParameter[@name="SSL"]').get('value', 'false').lower() == 'true'
        component['config']['starttls'] = node.find('.//elementParameter[@name="STARTTLS"]').get('value', 'false').lower() == 'true'
        component['config']['auth_username'] = node.find('.//elementParameter[@name="AUTH_USERNAME"]').get('value', '')
        component['config']['auth_password'] = node.find('.//elementParameter[@name="AUTH_PASSWORD"]').get('value', '')
        component['config']['die_on_error'] = node.find('.//elementParameter[@name="DIE_ON_ERROR"]').get('value', 'true').lower() == 'true'
        return component


    def parse_t_xml_map(self, node, component: Dict) -> Dict:
        """Parse tXMLMap specific configuration"""
        # Parse advanced settings with null checks
        die_on_error_elem = node.find('.//elementParameter[@name="DIE_ON_ERROR"]')
        die_on_error = die_on_error_elem.get('value', 'true').lower() == 'true' if die_on_error_elem is not None else True

        keep_order_elem = node.find('.//elementParameter[@name="KEEP_ORDER_FOR_DOCUMENT"]')
        keep_order = keep_order_elem.get('value', 'false').lower() == 'true' if keep_order_elem is not None else False

        connection_format_elem = node.find('.//elementParameter[@name="CONNECTION_FORMAT"]')
        connection_format = connection_format_elem.get('value', 'row') if connection_format_elem is not None else 'row'

        # Update component configuration
        component['config']['die_on_error'] = die_on_error
        component['config']['keep_order'] = keep_order
        component['config']['connection_format'] = connection_format

        # Parse nodeData for input/output trees and connections
        node_data = node.find('./nodeData')
        input_trees = []
        output_trees = []
        connections = []
        metadata = []

        def parse_nested_children(element):
            """Recursively parse nested children elements from tXMLMap structure"""
            children = []
            for child in element.findall('./children'):
                child_data = {
                    'name': child.get('name', ''),
                    'type': child.get('type', 'id_String'),
                    'xpath': child.get('xpath', ''),
                    'nodeType': child.get('nodeType', ''),
                    'loop': child.get('loop', '').lower() == 'true',
                    'main': child.get('main', '').lower() == 'true',
                    'outgoingConnections': child.get('outgoingConnections', ''),
                    'children': parse_nested_children(child)
                }
                children.append(child_data)
            return children

        if node_data is not None:
            # Parse input trees with full nested structure
            for input_tree in node_data.findall('./inputTrees'):
                tree_data = {
                    'name': input_tree.get('name', ''),
                    'matchingMode': input_tree.get('matchingMode', 'ALL_ROWS'),
                    'lookupMode': input_tree.get('lookupMode', 'LOAD_ONCE'),
                    'nodes': []
                }

                # Parse nodes within input tree
                for tree_node in input_tree.findall('./nodes'):
                    node_info = {
                        'name': tree_node.get('name', ''),
                        'expression': tree_node.get('expression', ''),
                        'type': tree_node.get('type', 'id_Document'),
                        'xpath': tree_node.get('xpath', ''),
                        'children': parse_nested_children(tree_node)
                    }
                    tree_data['nodes'].append(node_info)

                input_trees.append(tree_data)

            # Parse output trees with full nested structure
            for output_tree in node_data.findall('./outputTrees'):
                tree_data = {
                    'name': output_tree.get('name', ''),
                    'expressionFilter': output_tree.get('expressionFilter', ''),
                    'activateExpressionFilter': output_tree.get('activateExpressionFilter', 'false').lower() == 'true',
                    'nodes': []
                }

                # Parse nodes within output tree
                for tree_node in output_tree.findall('./nodes'):
                    node_info = {
                        'name': tree_node.get('name', ''),
                        'expression': tree_node.get('expression', ''),
                        'type': tree_node.get('type', 'id_String'),
                        'xpath': tree_node.get('xpath', ''),
                        'children': parse_nested_children(tree_node)
                    }
                    tree_data['nodes'].append(node_info)

                output_trees.append(tree_data)

            # Parse connections
            for conn in node_data.findall('./connections'):
                connections.append({
                    'source': conn.get('source', ''),
                    'target': conn.get('target', ''),
                    'sourceExpression': conn.get('sourceExpression', '')
                })
        # Parse output schema from metadata
        output_schema = []
        for metadata_node in node.findall('./metadata[@connector="FLOW"]'):
            for column in metadata_node.findall('./column'):
                output_schema.append({
                    'name': column.get('name', ''),
                    'type': column.get('type', 'id_String'),
                    'nullable': column.get('nullable', 'true').lower() == 'true',
                    'key': column.get('key', 'false').lower() == 'true',
                    'length': int(column.get('length', -1)),
                    'precision': int(column.get('precision', -1))
                })
        component['config']['INPUT_TREES'] = input_trees
        component['config']['OUTPUT_TREES'] = output_trees
        component['config']['CONNECTIONS'] = connections
        component['config']['output_schema'] = output_schema
        component['schema']['output'] = output_schema

        # Extract expression filter from first output tree
        expression_filter = None
        activate_expression_filter = False
        if output_trees:
            first_tree = output_trees[0]
            expression_filter = first_tree.get('expressionFilter', '')
            activate_expression_filter = first_tree.get('activateExpressionFilter', False)

        component['config']['expression_filter'] = expression_filter
        component['config']['activate_expression_filter'] = activate_expression_filter

        # --- ENHANCED MAPPING EXTRACTION ---
        # Build expressions for each output column based on connections using parsed tree structure
        expressions = {}
        # Build comprehensive node map from parsed input trees
        input_tree_nodes = {}

        def build_enhanced_node_map(children_list, path_prefix=""):
            """Build node map from parsed tree structure"""
            for idx, child in enumerate(children_list):
                child_path = f"{path_prefix}/@children.{idx}"
                name = child.get('name', '')
                node_type = child.get('nodeType', '')
                input_tree_nodes[child_path] = (name, node_type, child)
                # Recursively process nested children
                build_enhanced_node_map(child.get('children', []), child_path)

        # Build node map from parsed input trees
        for input_tree_idx, input_tree in enumerate(input_trees):
            for node_idx, tree_node in enumerate(input_tree.get('nodes', [])):
                root_path = f"inputTrees.{input_tree_idx}/@nodes.{node_idx}"
                name = tree_node.get('name', '')
                node_type = tree_node.get('type', '')
                input_tree_nodes[root_path] = (name, node_type, tree_node)
                # Process children of this node
                build_enhanced_node_map(tree_node.get('children', []), root_path)

        # Map output node index to column name
        output_col_map = {i: col['name'] for i, col in enumerate(output_schema)}

        import re
        # Build expressions from connections
        for conn in connections:
            target = conn.get('target', '')
            source = conn.get('source', '')

            # Extract output column index
            m = re.search(r'outputTrees\.0/@nodes\.(\d+)', target)
            if m:
                out_idx = int(m.group(1))
                out_col = output_col_map.get(out_idx)
                if not out_col:
                    continue

                # Build XPath from source path
                path_parts = re.findall(r'(@nodes\.\d+|@children\.\d+)', source)
                full_path = 'inputTrees.0'
                xpath_parts = []
                node_types = []

                for part in path_parts:
                    full_path += f'/{part}'
                    node_info = input_tree_nodes.get(full_path)
                    if node_info:
                        name, node_type, node_obj = node_info
                        if name and name not in ['newColumn']:  # Skip DataFrame column names
                            xpath_parts.append(name)
                            node_types.append(node_type)

                # Build final XPath expression
                if xpath_parts:
                    # Remove root element if it's the document root (e.g., CMARGINSCLM)
                    if xpath_parts and xpath_parts[0] in ['CMARGINSCLM', 'root']:
                        xpath_parts = xpath_parts[1:]

                    # Check if last element is an attribute
                    if node_types and node_types[-1] == 'ATTRIBUT':
                        # Handle attribute: remove from path and add as @attribute
                        attribute_name = xpath_parts.pop() if xpath_parts else ''
                        if xpath_parts:
                            xpath = './' + '/'.join(xpath_parts) + '/@' + attribute_name
                        else:
                            xpath = './@' + attribute_name
                    else:
                        # Regular element path
                        xpath = './' + '/'.join(xpath_parts) if xpath_parts else '.'
                else:
                    xpath = '.'

                expressions[out_col] = xpath
                print(f"[tXMLMAP DEBUG] Mapped connection: {out_col} -> {xpath} (from {source} -> {target})")
        # FIX: Preserve correct looping element from converter config

        #looping_element = component.get("config", {}).get("looping_element")
        looping_element = None
        for child in node.findall('.//children'):
            if child.get('loop', '').lower() == 'true' and child.get('name'):
                looping_element = child.get('name')
                break

        if looping_element:
            if 'config' not in component:
                component['config'] = {}
            component['config']['looping_element'] = looping_element
            print(f"[tXMLMap DEBUG] current looping_element (first): '{looping_element}'")

        # Only check elementParameters if still missing or blank
        if not looping_element:
            for param in node.findall('elementParameter'):
                if param.get('name', '').upper() == 'LOOPING_ELEMENT':
                    looping_element = (param.get('value') or '').strip()
                    break

        # Normalize to plain string (avoid dict/tuple types)
        if isinstance(looping_element, (list, tuple, dict)):
            looping_element = str(next(iter(looping_element.values()), "")) if isinstance(looping_element, dict) else str(looping_element[0])
        looping_element = str(looping_element or "").strip()

        print(f"[tXMLMap DEBUG] Normalized looping_element (final): '{looping_element}'")

        # END FIX

        # --- Auto-detect looping element if not set ---
        if not looping_element:
            # Find the deepest path in input_tree_nodes (most nested node)
            max_depth = 0
            for path, name in input_tree_nodes.items():
                depth = path.count('/')
                if depth > max_depth:
                    max_depth = depth
                    looping_element = name

        # --- DEBUG: Print before XPath rewrite ---
        print(f"[tXMLMap DEBUG] looping_element: {looping_element}, expressions before rewrite: {expressions}")

        # [NEW LOGIC] XPath rewrite based on looping element position

        # Normalize looping element name
        loop_name = str(looping_element or "").strip()
        print(f"[tXMLMap DEBUG] Normalized looping element: '{loop_name}'")

        # Rebuild expressions based on whether fields are inside or outside loop
        for out_col, xpath in list(expressions.items()):
            if not xpath:
                continue

            # Clean and normalize the field path
            xpath = xpath.strip().lstrip('.', '/')
            field_abs_path = xpath
            field_abs_path = '/'.join(p.strip('/') for p in field_abs_path.split('/') if p.strip('/'))
            print(f"[tXMLMap TRACE] Field: {out_col}, loop_name={loop_name},")
            field_parts = field_abs_path.split('/')
            # Detect if the field belongs to the loop element (case-insensitive)
            in_loop = loop_name and any(p.lower() == loop_name.lower() for p in field_parts)

            if in_loop:
                print(f"[tXMLMap TRACE] Field: {out_col}, loop_name={loop_name}, field_parts={field_parts}")
                # Inside loop d*: derive relative path
                loop_index = next(
                    (i for i, p in enumerate(field_parts) if p.lower() == loop_name.lower()),
                    None
                )

                if loop_index is not None:
                    rel_parts = field_parts[loop_index + 1:]
                    if rel_parts:
                        new_xpath = './' + '/'.join(rel_parts)
                    else:
                        new_xpath = f"./{loop_name}"
                        print(f"[tXMLMap DEBUG] Rewriting XPath for {out_col} inside loop: {new_xpath}")
                else:
                    # Fallback
                    new_xpath = f"./{field_abs_path}"
            else:
                # Outside loop d*: use ancestor path
                new_xpath = f"./ancestor::{field_abs_path}"
                print(f"[tXMLMap DEBUG] Rewriting XPath for {out_col} outside loop: {new_xpath}")

            expressions[out_col] = new_xpath

        # Update component expressions
        component['config']['expressions'] = expressions
        # -------------------------------------------------------
        # [END NEW LOGIC]
        # -------------------------------------------------------
        print(f"[tXMLMap DEBUG] expressions after rewrite: {expressions}")
        print(f"[Converter] tXMLMAP output_schema: {output_schema}")

        return component

    def parse_tfileinputxml(self, node, component: Dict) -> Dict:
        """Parse tFileInputXML specific configuration and build full output schema from metadata"""
        # Parse basic config
        component['config']['filename'] = node.find('.//elementParameter[@name="FILENAME"]').get('value', '')
        component['config']['loop_query'] = node.find('.//elementParameter[@name="LOOP_QUERY"]').get('value', '')
        component['config']['mapping'] = []
        for mapping_entry in node.findall('.//elementParameter[@name="MAPPING"]/elementValue'):
            column = mapping_entry.get('elementRef', '')
            xpath = mapping_entry.get('value', '')
            component['config']['mapping'].append({'column': column, 'xpath': xpath})
        component['config']['limit'] = node.find('.//elementParameter[@name="LIMIT"]').get('value', '')
        component['config']['die_on_error'] = node.find('.//elementParameter[@name="DIE_ON_ERROR"]').get('value', 'false').lower() == 'true'
        component['config']['encoding'] = node.find('.//elementParameter[@name="ENCODING"]').get('value', 'UTF-8')
        component['config']['ignore_ns'] = node.find('.//elementParameter[@name="IGNORE_NS"]').get('value', 'false').lower() == 'true'
        # Build output schema from metadata (not just mapping)
        output_schema = []
        for metadata_node in node.findall('./metadata[@connector="FLOW"]'):
            for column in metadata_node.findall('./column'):
                output_schema.append({
                    'name': column.get('name', ''),
                    'type': 'str',
                    'nullable': True,
                    'key': False,
                    'length': -1,
                    'precision': -1
                })
        component['schema']['output'] = output_schema
        return component

    def parse_tfileinputmsxml(self, node, component: Dict) -> Dict:
        """Parse tFileInputMSXML specific configuration"""
        component['config']['filename'] = node.find('.//elementParameter[@name="FILENAME"]').get('value', '')
        component['config']['root_loop_query'] = node.find('.//elementParameter[@name="ROOT_LOOP_QUERY"]').get('value', '')
        component['config']['schemas'] = []
        for schema_entry in node.findall('.//elementParameter[@name="SCHEMAS"]/elementValue'):
            column = schema_entry.get('elementRef', '')
            xpath = schema_entry.get('value', '')
            component['config']['schemas'].append({'column': column, 'xpath': xpath})
        component['config']['die_on_error'] = node.find('.//elementParameter[@name="DIE_ON_ERROR"]').get('value', 'false').lower() == 'true'
        component['config']['trim_all'] = node.find('.//elementParameter[@name="TRIMALL"]').get('value', 'false').lower() == 'true'
        component['config']['encoding'] = node.find('.//elementParameter[@name="ENCODING"]').get('value', 'UTF-8')
        return component

    def parse_tadvancedfileoutputxml(self, node, component: Dict) -> Dict:
        """Parse tAdvancedFileOutputXML specific configuration"""
        component['config']['filename'] = node.find('.//elementParameter[@name="FILENAME"]').get('value', '')
        component['config']['encoding'] = node.find('.//elementParameter[@name="ENCODING"]').get('value', 'UTF-8')
        component['config']['pretty_compact'] = node.find('.//elementParameter[@name="PRETTY_COMPACT"]').get('value', 'false').lower() == 'true'
        component['config']['create'] = node.find('.//elementParameter[@name="CREATE"]').get('value', 'true').lower() == 'true'
        component['config']['create_empty_element'] = node.find('.//elementParameter[@name="CREATE_EMPTY_ELEMENT"]').get('value', 'true').lower() == 'true'
        component['config']['add_blank_line_after_declaration'] = node.find('.//elementParameter[@name="ADD_BLANK_LINE_AFTER_DECLARATION"]').get('value', 'false')
        return component

    def parse_tfileinputjson(self, node, component: Dict) -> Dict:
        """Parse tFileInputJSON specific configuration"""
        component['config']['filename'] = node.find('.//elementParameter[@name="FILENAME"]').get('value', '')
        component['config']['json_loop_query'] = node.find('.//elementParameter[@name="JSON_LOOP_QUERY"]').get('value', '')
        component['config']['mapping'] = []
        for mapping_entry in node.findall('.//elementParameter[@name="MAPPING_JSONPATH"]/elementValue'):
            column = mapping_entry.get('elementRef', '')
            jsonpath = mapping_entry.get('value', '')
            component['config']['mapping'].append({'column': column, 'jsonpath': jsonpath})
        component['config']['die_on_error'] = node.find('.//elementParameter[@name="DIE_ON_ERROR"]').get('value', 'false').lower() == 'true'
        component['config']['encoding'] = node.find('.//elementParameter[@name="ENCODING"]').get('value', 'UTF-8')
        return component

    def parse_tfileoutputexcel(self, node, component: Dict) -> Dict:
        """Parse tFileOutputExcel specific configuration"""
        component['config']['filename'] = node.find('.//elementParameter[@name="FILENAME"]').get('value', '')
        component['config']['sheetname'] = node.find('.//elementParameter[@name="SHEETNAME"]').get('value', 'Sheet1')
        component['config']['includeheader'] = node.find('.//elementParameter[@name="INCLUDEHEADER"]').get('value', 'false').lower() == 'true'
        component['config']['append_file'] = node.find('.//elementParameter[@name="APPEND_FILE"]').get('value', 'false').lower() == 'true'
        component['config']['create'] = node.find('.//elementParameter[@name="CREATE"]').get('value', 'true').lower() == 'true'
        component['config']['encoding'] = node.find('.//elementParameter[@name="ENCODING"]').get('value', 'UTF-8')
        return component

    def parse_tfixedflowinput(self, node, component: Dict) -> Dict:
        """Parse tFixedFlowInput specific configuration to match Talend behavior"""

        # Helper function to get parameter value
        def get_param(name, default=None):
            elem = node.find(f".//elementParameter[@name='{name}']")
            if elem is not None:
                value = elem.get('value', default)
                # Clean quotes if present
                if isinstance(value, str) and value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                return value
            return default

        # Helper function to convert string boolean
        def str_to_bool(value, default=False):
            if isinstance(value, str):
                return value.lower() == 'true'
            return default if value is None else bool(value)

        # Parse basic configuration
        component['config']['nb_rows'] = int(get_param('NB_ROWS', '1'))
        component['config']['connection_format'] = get_param('CONNECTION_FORMAT', 'row')

        # Parse mode selection
        use_singlemode = str_to_bool(get_param('USE_SINGLEMODE', 'true'))
        use_intable = str_to_bool(get_param('USE_INTABLE', 'false'))
        use_inlinecontent = str_to_bool(get_param('USE_INLINECONTENT', 'false'))

        component['config']['use_singlemode'] = use_singlemode
        component['config']['use_intable'] = use_intable
        component['config']['use_inlinecontent'] = use_inlinecontent

        # Parse inline content parameters (even if not used, for completeness)
        component['config']['row_separator'] = get_param('ROWSEPARATOR', '\n')
        component['config']['field_separator'] = get_param('FIELDSEPARATOR', ';')
        component['config']['inline_content'] = get_param('INLINECONTENT', '')

        # Get schema columns from metadata
        schema_columns = []
        for metadata in node.findall('./metadata[@connector="FLOW"]'):
            for column in metadata.findall('./column'):
                schema_columns.append({
                    'name': column.get('name', ''),
                    'type': self.expr_converter.convert_type(column.get('type', 'id_String')),
                    'nullable': column.get('nullable', 'true').lower() == 'true'
                })

        component['config']['schema'] = schema_columns

        # Parse VALUES table for single mode
        values_config = {}
        if use_singlemode:
            # Parse VALUES table - each elementValue represents a column-value pair
            values_table = node.find('.//elementParameter[@name="VALUES"]')
            if values_table is not None:
                elements = values_table.findall('./elementValue')
                # Group elements by pairs (SCHEMA_COLUMN, VALUE)
                for i in range(0, len(elements), 2):
                    if i + 1 < len(elements):
                        schema_col_elem = elements[i]
                        value_elem = elements[i + 1]

                        # Get the actual column name and value
                        if (schema_col_elem.get('elementRef') == 'SCHEMA_COLUMN' and
                                value_elem.get('elementRef') == 'VALUE'):
                            column_name = schema_col_elem.get('value', '').strip('"')
                            column_value = value_elem.get('value', '').strip('"')

                            if column_name:
                                # Handle context variables and expressions
                                if column_value.startswith('context.'):
                                    column_value = '${' + column_value + '}'
                                elif column_value and not column_value.startswith('"'):
                                    # Mark potential Java expressions
                                    column_value = self.expr_converter.mark_java_expression(column_value)

                                values_config[column_name] = column_value

        # Parse INTABLE for inline table mode
        intable_data = []
        if use_intable:
            intable_table = node.find('.//elementParameter[@name="INTABLE"]')
            if intable_table is not None:
                # Parse inline table structure - this would be rows of data
                # Implementation depends on how Talend structures this table
                pass

        # Generate rows based on mode
        rows = []
        for row_idx in range(component['config']['nb_rows']):
            if use_singlemode:
                # Single mode: use VALUES configuration
                row = {}
                for col in schema_columns:
                    col_name = col['name']
                    # Use configured value or None/empty as default
                    row[col_name] = values_config.get(col_name, None)
                rows.append(row)

            elif use_inlinecontent:
                # Inline content mode: parse the inline content
                inline_content = component['config']['inline_content']
                if inline_content:
                    # Parse content based on separators
                    row_sep = component['config']['row_separator']
                    field_sep = component['config']['field_separator']

                    content_rows = inline_content.split(row_sep)
                    if row_idx < len(content_rows):
                        field_values = content_rows[row_idx].split(field_sep)
                        row = {}
                        for col_idx, col in enumerate(schema_columns):
                            if col_idx < len(field_values):
                                row[col['name']] = field_values[col_idx]
                            else:
                                row[col['name']] = None
                        rows.append(row)

            elif use_intable:
                # Inline table mode: use INTABLE data
                if row_idx < len(intable_data):
                    rows.append(intable_data[row_idx])
                else:
                    # Create empty row if not enough data
                    row = {col['name']: None for col in schema_columns}
                    rows.append(row)

        component['config']['rows'] = rows
        component['config']['values_config'] = values_config  # Keep for debugging

        return component

    def parse_tfilearchive(self, node, component: Dict) -> Dict:
        """Parse tFileArchive specific configuration"""
        component['config']['source'] = node.find('.//elementParameter[@name="SOURCE"]').get('value', '')
        component['config']['target'] = node.find('.//elementParameter[@name="TARGET"]').get('value', '')
        component['config']['archive_format'] = node.find('.//elementParameter[@name="ARCHIVE_FORMAT"]').get('value', 'zip')
        component['config']['include_subdirectories'] = node.find('.//elementParameter[@name="SUB_DIRECTORY"]').get('value', 'false').lower() == 'true'
        component['config']['overwrite'] = node.find('.//elementParameter[@name="OVERWRITE"]').get('value', 'false').lower() == 'true'
        component['config']['compression_level'] = node.find('.//elementParameter[@name="LEVEL"]').get('value', '4')
        return component

    def parse_tfileunarchive(self, node, component: Dict) -> Dict:
        """Parse tFileUnarchive specific configuration"""
        component['config']['zipfile'] = node.find('.//elementParameter[@name="ZIPFILE"]').get('value', '')
        component['config']['directory'] = node.find('.//elementParameter[@name="DIRECTORY"]').get('value', '')
        component['config']['extract_path'] = node.find('.//elementParameter[@name="EXTRACTPATH"]').get('value', '')
        component['config']['check_password'] = node.find('.//elementParameter[@name="CHECKPASSWORD"]').get('value', 'false').lower() == 'true'
        component['config']['password'] = node.find('.//elementParameter[@name="PASSWORD"]').get('value', '')
        component['config']['die_on_error'] = node.find('.//elementParameter[@name="DIE_ON_ERROR"]').get('value', 'false').lower() == 'true'
        return component

    def parse_tfiletouch(self, node, component: Dict) -> Dict:
        """Parse tFileTouch specific configuration"""
        component['config']['filename'] = node.find('.//elementParameter[@name="FILENAME"]').get('value', '')
        component['config']['create_directory'] = node.find('.//elementParameter[@name="CREATEDIR"]').get('value', 'false').lower() == 'true'
        return component

    def parse_tfileexist(self, node, component: Dict) -> Dict:
        """Parse tFileExist specific configuration"""
        file_name = node.find('.//elementParameter[@name="FILE_NAME"]').get('value', '')
        component['config']['FILE_NAME'] = file_name.strip('"')
        return component

    def parse_tfileproperties(self, node, component: Dict) -> Dict:
        """Parse tFileProperties specific configuration"""
        file_name = node.find('.//elementParameter[@name="FILENAME"]').get('value', '')
        calculate_md5 = node.find('.//elementParameter[@name="MD5"]').get('value', 'false').lower() == 'true'

        component['config']['FILENAME'] = file_name.strip('"')
        component['config']['MD5'] = calculate_md5
        return component

    def parse_tfile_row_count(self, node, component: Dict) -> Dict:
        """
        Parse tFileRowCount specific configuration.
        """
        component['config']['filename'] = node.find('.//elementParameter[@name="FILENAME"]').get('value', '')
        # Normalize ROWSEPARATOR to remove surrounding quotes if present
        row_separator = node.find('.//elementParameter[@name="ROWSEPARATOR"]').get('value', '\n')
        if row_separator.startswith('"') and row_separator.endswith('"'):
            row_separator = row_separator[1:-1]
        component['config']['row_separator'] = row_separator
        component['config']['ignore_empty_row'] = node.find('.//elementParameter[@name="IGNORE_EMPTY_ROW"]').get('value', 'false').lower() == 'true'
        component['config']['encoding'] = node.find('.//elementParameter[@name="ENCODING"]').get('value', 'UTF-8')
        return component

    def parse_tfileinputproperties(self, node, component: Dict) -> Dict:
        """Parse tFileInputProperties specific configuration"""
        # Add parsing logic here
        return component

    def parse_row_generator(self, node, component: Dict) -> Dict:
        """Parse RowGenerator (tRowGenerator) specific configuration"""
        component['config']['rows'] = int(node.find('.//elementParameter[@name="NB_ROWS"]').get('value', '1'))
        component['config']['columns'] = []

        # Parse columns and their values
        for param in node.findall('.//elementParameter[@name="VALUES"]/elementValue'):
            column = param.get('elementRef', '')
            value = param.get('value', '')
            component['config']['columns'].append({'column': column, 'value': value})

        return component

    def parse_treplace(self, node, component: Dict) -> Dict:
        """Parse tReplace specific configuration"""
        # Parse SIMPLE_MODE and ADVANCED_MODE
        simple_mode = node.find('.//elementParameter[@name="SIMPLE_MODE"]')
        simple_mode = simple_mode.get('value', 'true').lower() == 'true' if simple_mode is not None else True

        advanced_mode = node.find('.//elementParameter[@name="ADVANCED_MODE"]')
        advanced_mode = advanced_mode.get('value', 'false').lower() == 'true' if advanced_mode is not None else False

        # Parse STRICT_MATCH (only shown when advanced_mode is true)
        strict_match = node.find('.//elementParameter[@name="STRICT_MATCH"]')
        strict_match = strict_match.get('value', 'true').lower() == 'true' if strict_match is not None else True

        # Parse CONNECTION_FORMAT
        connection_format = node.find('.//elementParameter[@name="CONNECTION_FORMAT"]')
        connection_format = connection_format.get('value', 'row') if connection_format is not None else 'row'

        # Parse SUBSTITUTIONS table - use correct field names from Talend XML
        substitutions = []
        for table_param in node.findall('.//elementParameter[@name="SUBSTITUTIONS"]'):
            elements = list(table_param.findall('.//elementValue'))
            # Group elements by sets of 7 (INPUT_COLUMN, SEARCH_PATTERN, REPLACE_STRING, WHOLE_WORD, CASE_SENSITIVE, USE_GLOB, COMMENT)
            for i in range(0, len(elements), 7):
                if i + 6 < len(elements):
                    # Extract the seven elements for this substitution rule
                    row_data = {}
                    for j in range(7):
                        elem = elements[i + j]
                        ref = elem.get('elementRef', '')
                        value = elem.get('value', '')

                        if ref == 'INPUT_COLUMN':
                            row_data['input_column'] = value
                        elif ref == 'SEARCH_PATTERN':
                            # Clean search pattern: remove quotes if present
                            if value.startswith('&quot;') and value.endswith('&quot;'):
                                value = value[6:-6]  # Remove &quot; from both ends
                            elif value.startswith('"') and value.endswith('"'):
                                value = value[1:-1]  # Remove quotes
                            row_data['search_pattern'] = value
                        elif ref == 'REPLACE_STRING':
                            # Clean replace string: remove quotes if present
                            if value.startswith('&quot;') and value.endswith('&quot;'):
                                value = value[6:-6]  # Remove &quot; from both ends
                            elif value.startswith('"') and value.endswith('"'):
                                value = value[1:-1]  # Remove quotes
                            row_data['replace_string'] = value
                        elif ref == 'WHOLE_WORD':
                            row_data['whole_word'] = value.lower() == 'true'
                        elif ref == 'CASE_SENSITIVE':
                            row_data['case_sensitive'] = value.lower() == 'true'
                        elif ref == 'USE_GLOB':
                            row_data['use_glob'] = value.lower() == 'true'
                        elif ref == 'COMMENT':
                            row_data['comment'] = value

                    # Only add if we have a valid input_column and search_pattern
                    if row_data.get('input_column') and 'search_pattern' in row_data:
                        # Set defaults for missing values
                        substitutions.append({
                            'input_column': row_data.get('input_column', ''),
                            'search_pattern': row_data.get('search_pattern', ''),
                            'replace_string': row_data.get('replace_string', ''),
                            'whole_word': row_data.get('whole_word', False),
                            'case_sensitive': row_data.get('case_sensitive', False),
                            'use_glob': row_data.get('use_glob', False),
                            'comment': row_data.get('comment', '')
                        })

        # Parse ADVANCED_SUBST table if in advanced mode
        advanced_substitutions = []
        if advanced_mode:
            for table_param in node.findall('.//elementParameter[@name="ADVANCED_SUBST"]'):
                # Parse advanced substitution logic here if needed
                pass

        # Extract all unique columns mentioned in substitutions
        columns = list(set([sub['input_column'] for sub in substitutions if sub.get('input_column')]))

        # Update component configuration
        component['config']['substitutions'] = substitutions
        component['config']['simple_mode'] = simple_mode
        component['config']['advanced_mode'] = advanced_mode
        component['config']['strict_match'] = strict_match
        component['config']['connection_format'] = connection_format
        component['config']['columns'] = columns
        component['config']['advanced_substitutions'] = advanced_substitutions

        return component

    def parse_tparse_record_set(self, node, component: Dict) -> Dict:
        """Parse tParseRecordSet specific configuration"""
        recordset_field = node.find('.//elementParameter[@name="RECORDSET_FIELD"]').get('value', '')
        connection_format = node.find('.//elementParameter[@name="CONNECTION_FORMAT"]').get('value', 'row')

        # Parse ATTRIBUTE_TABLE
        attribute_table = []
        for param in node.findall('.//elementParameter[@name="ATTRIBUTE_TABLE"]/elementValue'):
            attribute_table.append(param.get('value', ''))

        component['config']['recordset_field'] = recordset_field
        component['config']['connection_format'] = connection_format
        component['config']['attribute_table'] = attribute_table

        return component

    def parse_tsplit_row(self, node, component: Dict) -> Dict:
        """Parse tSplitRow specific configuration"""
        col_mapping = []
        for param in node.findall('.//elementParameter[@name="COL_MAPPING"]/elementValue'):
            mapping = {}
            for item in param.findall('.//elementValue'):
                source_col = item.get('elementRef', '')
                target_col = item.get('value', '')
                if source_col and target_col:
                    mapping[target_col] = source_col
            col_mapping.append(mapping)

        connection_format = node.find('.//elementParameter[@name="CONNECTION_FORMAT"]').get('value', 'row')

        component['config']['col_mapping'] = col_mapping
        component['config']['connection_format'] = connection_format

        return component

    def parse_tsample_row(self, node, component: Dict) -> Dict:
        """Parse tSampleRow specific configuration"""
        range_config = node.find('.//elementParameter[@name="RANGE"]').get('value', '')
        connection_format = node.find('.//elementParameter[@name="CONNECTION_FORMAT"]').get('value', 'row')

        component['config']['range'] = range_config
        component['config']['connection_format'] = connection_format

        return component

    def parse_treplicate(self, node, component: Dict) -> Dict:
        """Parse tReplicate specific configuration"""
        connection_format = node.find('.//elementParameter[@name="CONNECTION_FORMAT"]').get('value', 'row')

        component['config']['connection_format'] = connection_format

        return component

    def parse_tpivot_to_columns_delimited(self, node, component: Dict) -> Dict:
        """Parse tPivotToColumnsDelimited specific configuration"""
        pivot_column = node.find('.//elementParameter[@name="PIVOT_COLUMN"]').get('value', '')
        aggregation_column = node.find('.//elementParameter[@name="AGGREGATION_COLUMN"]').get('value', '')
        aggregation_function = node.find('.//elementParameter[@name="AGGREGATION_FUNCTION"]').get('value', 'sum')
        group_bys = [param.get('value', '') for param in node.findall('.//elementParameter[@name="GROUPBYS"]/elementValue')]
        filename = node.find('.//elementParameter[@name="FILENAME"]').get('value', '')
        row_separator = node.find('.//elementParameter[@name="ROWSEPARATOR"]').get('value', '\n')
        field_separator = node.find('.//elementParameter[@name="FIELDSEPARATOR"]').get('value', ';')
        encoding = node.find('.//elementParameter[@name="ENCODING"]').get('value', 'UTF-8')
        create = node.find('.//elementParameter[@name="CREATE"]').get('value', 'true').lower() == 'true'

        component['config'].update({
            'pivot_column': pivot_column,
            'aggregation_column': aggregation_column,
            'aggregation_function': aggregation_function,
            'group_by_columns': group_bys,
            'filename': filename,
            'row_separator': row_separator,
            'field_separator': field_separator,
            'encoding': encoding,
            'create': create
        })

        return component

    def parse_tparallelize(self, node, component: Dict) -> Dict:
        """Parse tParallelize specific configuration"""
        wait_for = node.find('.//elementParameter[@name="WAIT_FOR"]').get('value', 'All')
        sleep_time = node.find('.//elementParameter[@name="SLEEPTIME"]').get('value', '100')
        die_on_error = node.find('.//elementParameter[@name="DIE_ON_ERROR"]').get('value', 'false').lower() == 'true'

        component['config'].update({
            'wait_for': wait_for,
            'sleep_time': sleep_time,
            'die_on_error': die_on_error
        })

        return component

    def parse_tnormalize(self, node, component: Dict) -> Dict:
        """Parse tNormalize specific configuration"""
        normalize_column = node.find('.//elementParameter[@name="NORMALIZE_COLUMN"]').get('value', '')
        item_separator = node.find('.//elementParameter[@name="ITEMSEPARATOR"]').get('value', ';').strip('"')
        deduplicate = node.find('.//elementParameter[@name="DEDUPLICATE"]').get('value', 'false').lower() == 'true'
        trim = node.find('.//elementParameter[@name="TRIM"]').get('value', 'false').lower() == 'true'
        discard_trailing_empty_str = node.find('.//elementParameter[@name="DISCARD_TRAILING_EMPTY_STR"]').get('value', 'false').lower() == 'true'

        component['config'].update({
            'normalize_column': normalize_column,
            'item_separator': item_separator,
            'deduplicate': deduplicate,
            'trim': trim,
            'discard_trailing_empty_str': discard_trailing_empty_str
        })

        return component

    def parse_tconverttype(self, node, component: Dict) -> Dict:
        """Parse tConvertType specific configuration"""
        config = component['config']

        # Parse AUTOCAST parameter
        autocast = node.find('.//elementParameter[@name="AUTOCAST"]').get('value', 'false').lower() == 'true'
        config['autocast'] = autocast

        # Parse EMPTYTONULL parameter
        empty_to_null = node.find('.//elementParameter[@name="EMPTYTONULL"]').get('value', 'false').lower() == 'true'
        config['empty_to_null'] = empty_to_null

        # Parse DIEONERROR parameter
        die_on_error = node.find('.//elementParameter[@name="DIEONERROR"]').get('value', 'false').lower() == 'true'
        config['die_on_error'] = die_on_error

        # Parse MANUALTABLE parameter
        manual_table = []
        for param in node.findall('.//elementParameter[@name="MANUALTABLE"]/elementValue'):
            column = param.get('elementRef', '')
            target_type = param.get('value', '')
            manual_table.append({'column': column, 'target_type': target_type})
        config['manual_table'] = manual_table

        component['config'] = config
        return component

    def parse_tmemorizerows(self, node, component: Dict) -> Dict:
        """Parse tMemorizeRows specific configuration"""
        component['config']['row_count'] = int(node.find('.//elementParameter[@name="ROW_COUNT"]').get('value', '1'))
        component['config']['reset_on_condition'] = node.find('.//elementParameter[@name="RESET_ON_CONDITION"]').get('value', 'false').lower() == 'true'
        component['config']['condition'] = node.find('.//elementParameter[@name="CONDITION"]').get('value', '')
        return component

    def parse_textract_delimited_fields(self, node, component: Dict) -> Dict:
        """Parse tExtractDelimitedFields specific configuration"""
        config = component['config']

        def get_param(name, default=None):
            elem = node.find(f'.//elementParameter[@name="{name}"]')
            return elem.get('value', default) if elem is not None else default

        config['field_separator'] = get_param('FIELDSEPARATOR', ';')
        config['row_separator'] = get_param('ROWSEPARATOR', '\n')
        config['advanced_separator'] = get_param('ADVANCED_SEPARATOR', 'false').lower() == 'true'
        config['thousands_separator'] = get_param('THOUSANDS_SEPARATOR', ',')
        config['decimal_separator'] = get_param('DECIMAL_SEPARATOR', '.')
        config['trim_all'] = get_param('TRIMALL', 'false').lower() == 'true'
        config['remove_empty_row'] = get_param('REMOVE_EMPTY_ROW', 'false').lower() == 'true'
        config['die_on_error'] = get_param('DIE_ON_ERROR', 'false').lower() == 'true'
        # ...existing code for schema parsing...
        return component

    def parse_textract_regex_fields(self, node, component: Dict) -> Dict:
        """Parse tExtractRegexFields specific configuration"""
        config = component['config']

        # Extract relevant parameters
        config['regex'] = node.find('.//elementParameter[@name="REGEX"]').get('value', '')
        config['group'] = int(node.find('.//elementParameter[@name="GROUP"]').get('value', '0'))
        config['die_on_error'] = node.find('.//elementParameter[@name="DIE_ON_ERROR"]').get('value', 'false').lower() == 'true'

        # Parse metadata schemas
        for metadata in node.findall('.//metadata'):
            connector = metadata.get('connector', 'FLOW')
            schema_cols = []

            for column in metadata.findall('.//column'):
                col_info = {
                    'name': column.get('name', ''),
                    'type': self.expr_converter.convert_type(column.get('type', 'id_String')),
                    'nullable': column.get('nullable', 'true').lower() == 'true',
                    'key': column.get('key', 'false').lower() == 'true'
                }

                # Add additional properties if present
                if column.get('length'):
                    col_info['length'] = int(column.get('length'))
                if column.get('precision'):
                    col_info['precision'] = int(column.get('precision'))
                # Capture date pattern if present
                if column.get('pattern'):
                    pattern = column.get('pattern').strip('"')
                    if pattern:  # Only add if not empty
                        # Convert Java date pattern to Python strftime format
                        pattern = pattern.replace('yyyy', '%Y').replace('MM', '%m').replace('dd', '%d')
                        pattern = pattern.replace('HH', '%H').replace('mm', '%M').replace('ss', '%S')
                        col_info['date_pattern'] = pattern

                schema_cols.append(col_info)

            if connector == 'FLOW':
                component['schema']['output'] = schema_cols
            elif connector == 'REJECT':
                component['schema']['reject'] = schema_cols

        return component

    def parse_textract_positional_fields(self, node, component):
        """
        Parse tExtractPositionalFields component from Talend XML.
        """
        for param in node.findall('.//elementParameter'):
            name = param.get('name')
            value = param.get('value', '').strip('"')

            if name == 'PATTERN':
                component['config']['pattern'] = value
            elif name == 'DIE_ON_ERROR':
                component['config']['die_on_error'] = value.lower() == 'true'
            elif name == 'TRIM':
                component['config']['trim'] = value.lower() == 'true'
            elif name == 'ADVANCED_SEPARATOR':
                component['config']['advanced_separator'] = value.lower() == 'true'
            elif name == 'THOUSANDS_SEPARATOR':
                component['config']['thousands_separator'] = value
            elif name == 'DECIMAL_SEPARATOR':
                component['config']['decimal_separator'] = value

        return component

    def parse_tloop(self, node, component: Dict) -> Dict:
        """Parse tLoop specific configuration"""
        loop_type = node.find('.//elementParameter[@name="LOOP_TYPE"]').get('value', 'FOR')
        start_value = node.find('.//elementParameter[@name="START_VALUE"]').get('value', '0')
        end_value = node.find('.//elementParameter[@name="END_VALUE"]').get('value', '10')
        step_value = node.find('.//elementParameter[@name="STEP_VALUE"]').get('value', '1')
        iterate_on = node.find('.//elementParameter[@name="ITERATE_ON"]').get('value', '')
        die_on_error = node.find('.//elementParameter[@name="DIE_ON_ERROR"]').get('value', 'false').lower() == 'true'

        component['config'].update({
            'loop_type': loop_type,
            'start_value': start_value,
            'end_value': end_value,
            'step_value': step_value,
            'iterate_on': iterate_on,
            'die_on_error': die_on_error
        })

        return component

    def parse_tschema_compliance_check(self, node, component: Dict) -> Dict:
        """Parse tSchemaComplianceCheck specific configuration"""
        schema = []

        # Parse schema from metadata
        for metadata in node.findall('.//metadata'):
            if metadata.get('connector') == 'FLOW':
                for column in metadata.findall('.//column'):
                    schema.append({
                        'name': column.get('name', ''),
                        'type': self.expr_converter.convert_type(column.get('type', 'id_String')),
                        'nullable': column.get('nullable', 'true').lower() == 'true',
                        'length': int(column.get('length', 0)) if column.get('length') else None
                    })

        # Parse additional parameters
        component['config']['schema'] = schema
        component['config']['check_all'] = node.find('.//elementParameter[@name="CHECK_ALL"]').get('value', 'false').lower() == 'true'
        component['config']['sub_string'] = node.find('.//elementParameter[@name="SUB_STRING"]').get('value', 'false').lower() == 'true'
        component['config']['strict_date_check'] = node.find('.//elementParameter[@name="STRICT_DATE_CHECK"]').get('value', 'false').lower() == 'true'
        component['config']['all_empty_are_null'] = node.find('.//elementParameter[@name="ALL_EMPTY_ARE_NULL"]').get('value', 'false').lower() == 'true'

        return component

    def parse_t_file_input_raw(self, node, component: Dict) -> Dict:
        """Parse tFileInputRaw specific configuration"""
        # Parse file path
        filename = node.find('.//elementParameter[@name="FILENAME"]').get('value', '').strip('"')
        as_string = node.find('.//elementParameter[@name="AS_STRING"]').get('value', 'true').lower() == 'true'
        encoding = node.find('.//elementParameter[@name="ENCODING"]').get('value', 'UTF-8').strip('"')
        die_on_error = node.find('.//elementParameter[@name="DIE_ON_ERROR"]').get('value', 'false').lower() == 'true'

        # Update component configuration
        component['config']['filename'] = filename
        component['config']['as_string'] = as_string
        component['config']['encoding'] = encoding
        component['config']['die_on_error'] = die_on_error

        return component

    def parse_t_flow_to_iterate(self, node, component: Dict) -> Dict:
        """Parse tFlowToIterate specific configuration"""
        # Parse default mapping
        default_map = node.find('.//elementParameter[@name="DEFAULT_MAP"]').get('value', 'true').lower() == 'true'
        connection_format = node.find('.//elementParameter[@name="CONNECTION_FORMAT"]').get('value', 'row')

        # Update component configuration
        component['config']['default_map'] = default_map
        component['config']['connection_format'] = connection_format

        return component

    def parse_t_aggregate_sorted_row(self, node, component: Dict) -> Dict:
        """
        Parse tAggregateSortedRow component from Talend XML node.
        Extracts GROUPBYS and OPERATIONS tables and builds output schema.
        Maps to ETL-AGENT tAggregateSortedRow config format.
        """
        # Parse GROUPBYS
        group_bys = []
        for table in node.findall('.//elementParameter[@name="GROUPBYS"]'):
            for elem in table.findall('.//elementValue'):
                if elem.get('elementRef') == 'INPUT_COLUMN':
                    group_bys.append(elem.get('value', ''))

        # Parse OPERATIONS (group every 4 consecutive elementValue as one op)
        operations = []
        for table in node.findall('.//elementParameter[@name="OPERATIONS"]'):
            elements = list(table.findall('.//elementValue'))
            for i in range(0, len(elements), 4):
                op = {}
                for elem in elements[i:i+4]:
                    ref = elem.get('elementRef')
                    val = elem.get('value', '')
                    if ref == 'OUTPUT_COLUMN':
                        op['output_column'] = val
                    elif ref == 'INPUT_COLUMN':
                        op['input_column'] = val
                    elif ref == 'FUNCTION':
                        op['function'] = val
                    elif ref == 'IGNORE_NULL':
                        op['ignore_null'] = val.lower() == 'true'
                if op:
                    operations.append(op)

        # Parse ROW_COUNT
        row_count = None
        for param in node.findall('.//elementParameter[@name="ROW_COUNT"]'):
            row_count = param.get('value', None)
            break

        # Parse CONNECTION_FORMAT
        connection_format = None
        for param in node.findall('.//elementParameter[@name="CONNECTION_FORMAT"]'):
            connection_format = param.get('value', None)
            break

        # Log for debug
        print(f"[parse_t_aggregate_sorted_row] Parsed group_bys: {group_bys}")
        print(f"[parse_t_aggregate_sorted_row] Parsed operations: {operations}")

        # Build output schema from metadata
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

        component['config']['group_bys'] = group_bys
        component['config']['operations'] = operations
        component['config']['row_count'] = row_count
        component['config']['connection_format'] = connection_format
        component['schema']['output'] = output_schema
        return component

    def parse_t_oracle_commit(self, node, component: Dict) -> Dict:
        """Parse tOracleCommit specific configuration"""
        # Parse CONNECTION parameter
        connection = node.find('.//elementParameter[@name="CONNECTION"]').get('value', '')
        close_connection = node.find('.//elementParameter[@name="CLOSE"]').get('value', 'true').lower() == 'true'

        # Update component configuration
        component['config']['connection'] = connection
        component['config']['close_connection'] = close_connection

        return component

    def parse_t_oracle_close(self, node, component: Dict) -> Dict:
        """Parse tOracleClose specific configuration"""
        # Parse CONNECTION parameter
        connection = node.find('.//elementParameter[@name="CONNECTION"]').get('value', '')

        # Update component configuration
        component['config']['connection'] = connection

        return component

    def parse_t_oracle_rollback(self, node, component: Dict) -> Dict:
        """Parse tOracleRollback specific configuration"""
        # Parse CONNECTION parameter
        connection = node.find('.//elementParameter[@name="CONNECTION"]').get('value', '')
        close = node.find('.//elementParameter[@name="CLOSE"]').get('value', 'true').lower() == 'true'
        connection_format = node.find('.//elementParameter[@name="CONNECTION_FORMAT"]').get('value', 'row')

        # Update component configuration
        component['config']['connection'] = connection
        component['config']['close'] = close
        component['config']['connection_format'] = connection_format

        return component

    def parse_t_foreach(self, node, component: Dict) -> Dict:
        """Parse tForeach specific configuration"""
        # Parse VALUES parameter
        values = []
        for param in node.findall('.//elementParameter[@name="VALUES"]/elementValue'):
            values.append(param.get('value', ''))

        connection_format = node.find('.//elementParameter[@name="CONNECTION_FORMAT"]').get('value', 'row')

        # Update component configuration
        component['config']['values'] = values
        component['config']['connection_format'] = connection_format

        return component

    def parse_tfileoutputdelimited(self, node, component: Dict) -> Dict:
        """Parse tFileOutputDelimited specific configuration"""
        component['config']['filepath'] = node.find('.//elementParameter[@name="FILENAME"]').get('value', '')
        component['config']['delimiter'] = node.find('.//elementParameter[@name="FIELDSEPARATOR"]').get('value', ';')
        component['config']['row_separator'] = node.find('.//elementParameter[@name="ROWSEPARATOR"]').get('value', '\n')
        component['config']['include_header'] = node.find('.//elementParameter[@name="INCLUDEHEADER"]').get('value', 'true').lower() == 'true'
        component['config']['append'] = node.find('.//elementParameter[@name="APPEND"]').get('value', 'false').lower() == 'true'
        component['config']['encoding'] = node.find('.//elementParameter[@name="ENCODING"]').get('value', 'UTF-8')
        component['config']['die_on_error'] = node.find('.//elementParameter[@name="DIE_ON_ERROR"]').get('value', 'false').lower() == 'true'

        # Ensure the component is ready to accept input data
        component['inputs'] = [input_flow.get('name') for input_flow in node.findall('.//connection[@connectorName="FLOW"]')]
        return component

    def parse_t_oracle_input(self, node, component: Dict) -> Dict:
        """
        Parse tOracleInput specific configuration.
        """
        config = component['config']

        # Map Talend XML parameters to config keys
        for param in node.findall('.//elementParameter'):
            name = param.get('name')
            value = param.get('value', '')

            if name == 'HOST':
                config['host'] = value.strip('"')
            elif name == 'PORT':
                port_val = value.strip('"')
                try:
                    config['port'] = int(port_val)
                except ValueError:
                    config['port'] = port_val  # fallback to string if not integer
                print(f"[DEBUG] Set PORT value: {config['port']}")
            elif name == 'DBNAME':
                config['dbname'] = value.strip('"')
            elif name == 'USER':
                config['user'] = value.strip('"')
            elif name == 'PASSWORD':
                config['password'] = value.strip('"')
            elif name == 'QUERY':
                config['query'] = value.strip('"')
        component['config'] = config
        return component

    def parse_t_oracle_output(self, node, component: Dict) -> Dict:
        """
        Parse tOracleOutput specific configuration to match the properties required
        by TOracleOutput.
        Extracts HOST, PORT, DBNAME, USER, PASSWORD, TABLE, DATA_ACTION, CONNECTION,
        USE_EXISTING_CONNECTION.
        """

        config = component['config']
        for param in node.findall('.//elementParameter'):
            name = param.get('name')
            value = param.get('value', '')
            if name == 'HOST':
                config['HOST'] = value.strip('"')
            elif name == 'PORT':
                port_val = value.strip('"')
                try:
                    config['PORT'] = int(port_val)
                except ValueError:
                    config['PORT'] = port_val
            elif name == 'DBNAME':
                config['DBNAME'] = value.strip('"')
            elif name == 'USER':
                config['USER'] = value.strip('"')
            elif name == 'PASSWORD':
                config['PASSWORD'] = value.strip('"')
            elif name == 'TABLE':
                config['TABLE'] = value.strip('"')
            elif name == 'DATA_ACTION':
                config['DATA_ACTION'] = value.strip('"')
            elif name == 'CONNECTION':
                config['CONNECTION'] = value.strip('"')
            elif name == 'USE_EXISTING_CONNECTION':
                config['USE_EXISTING_CONNECTION'] = value.lower() == 'true'
        component['config'] = config
        return component

    def parse_t_oracle_row(self, node, component: Dict) -> Dict:
        """
        Parse tOracleRow specific configuration to match the properties required by
        TOracleRow.
        Extracts HOST, PORT, DBNAME, USER, PASSWORD, QUERY, CONNECTION,
        USE_EXISTING_CONNECTION, etc.
        """

        config = component['config']
        for param in node.findall('.//elementParameter'):
            name = param.get('name')
            value = param.get('value', '')
            if name == 'USE_EXISTING_CONNECTION':
                config['USE_EXISTING_CONNECTION'] = value.lower() == 'true'
            elif name == 'CONNECTION':
                config['CONNECTION'] = value.strip('"')
            elif name == 'CONNECTION_TYPE':
                config['CONNECTION_TYPE'] = value.strip('"')
            elif name == 'HOST':
                config['HOST'] = value.strip('"')
            elif name == 'PORT':
                port_val = value.strip('"')
                try:
                    config['PORT'] = int(port_val)
                except ValueError:
                    config['PORT'] = port_val
            elif name == 'DBNAME':
                config['DBNAME'] = value.strip('"')
            elif name == 'USER':
                config['USER'] = value.strip('"')
            elif name == 'PASSWORD':
                config['PASSWORD'] = value.strip('"')
            elif name == 'QUERY':
                config['QUERY'] = value.strip('"')
            elif name == 'ENCODING':
                config['ENCODING'] = value.strip('"')
            elif name == 'COMMIT_EVERY':
                config['COMMIT_EVERY'] = int(value) if value.isdigit() else 10000
            elif name == 'SUPPORT_NLS':
                config['SUPPORT_NLS'] = value.lower() == 'true'
            elif name == 'DIE_ON_ERROR':
                config['DIE_ON_ERROR'] = value.lower() == 'true'
        component['config'] = config
        return component

    def parse_t_oracle_sp(self, node, component: Dict) -> Dict:
        """
        Parse tOracleSP specific configuration to match the properties required by
        tOracleSP.
        Extracts HOST, PORT, DBNAME, USER, PASSWORD, PROCEDURE, DIE_ON_ERROR, etc.
        """

        config = component['config']
        for param in node.findall('.//elementParameter'):
            name = param.get('name')
            value = param.get('value', '')
            if name == 'HOST':
                config['HOST'] = value.strip('"')
            elif name == 'PORT':
                port_val = value.strip('"')
                try:
                    config['PORT'] = int(port_val)
                except ValueError:
                    config['PORT'] = port_val
            elif name == 'DBNAME':
                config['DBNAME'] = value.strip('"')
            elif name == 'USER':
                config['USER'] = value.strip('"')
            elif name == 'PASSWORD':
                config['PASSWORD'] = value.strip('"')
            elif name == 'PROCEDURE':
                config['PROCEDURE'] = value.strip('"')
            elif name == 'DIE_ON_ERROR':
                config['DIE_ON_ERROR'] = value.lower() == 'true'
        component['config'] = config
        return component

    def parse_t_oracle_bulk_exec(self, node, component: Dict) -> Dict:
        """
        Parse tOracleBulkExec specific configuration to match the properties
        required by tOracleBulkExec.
        Extracts HOST, PORT, DBNAME, USER, PASS, DATA, TABLE, CLT_FILE,
        DIE_ON_ERROR, etc.
        PASS field now simply strips quotes, no cleaning or decryption logic.
        """
        config = component['config']
        for param in node.findall('.//elementParameter'):
            name = param.get('name')
            value = param.get('value', '')
            if name == 'HOST':
                config['HOST'] = value.strip('"')
            elif name == 'PORT':
                port_val = value.strip('"')
                try:
                    config['PORT'] = int(port_val)
                except ValueError:
                    config['PORT'] = port_val
            elif name == 'DBNAME':
                config['DBNAME'] = value.strip('"')
            elif name == 'USER':
                config['USER'] = value.strip('"')
            elif name == 'PASS':
                config['PASS'] = value.strip('"')
            elif name == 'DATA':
                config['DATA'] = value.strip('"')
            elif name == 'TABLE':
                config['TABLE'] = value.strip('"')
            elif name == 'CLT_FILE':
                config['CLT_FILE'] = value.strip('"')
            elif name == 'DIE_ON_ERROR':
                config['DIE_ON_ERROR'] = value.lower() == 'true'
        component['config'] = config
        return component

    def parse_textract_json_fields(self, node, component: dict) -> dict:
        """Parse tExtractJSONFields specific configuration from Talend XML node."""
        def get_param(name, default=None):
            param = node.find(f'.//elementParameter[@name="{name}"]')
            return param.get('value', default) if param is not None else default

        # Map Talend XML parameters to config
        component['config']['read_by'] = get_param('READ_BY', 'JSONPATH')
        component['config']['json_path_version'] = get_param('JSON_PATH_VERSION', '2_1_0')
        # Remove extra quotes from loop_query
        loop_query = get_param('LOOP_QUERY', '') or get_param('JSON_LOOP_QUERY', '')
        if loop_query and loop_query.startswith('"') and loop_query.endswith('"'):
            loop_query = loop_query[1:-1]
        component['config']['loop_query'] = loop_query
        component['config']['die_on_error'] = get_param('DIE_ON_ERROR', 'false').lower() == 'true'
        component['config']['encoding'] = get_param('ENCODING', 'UTF-8')
        component['config']['use_loop_as_root'] = get_param('USE_LOOP_AS_ROOT', 'false').lower() == 'true'
        component['config']['split_list'] = get_param('SPLIT_LIST', 'false').lower() == 'true'
        component['config']['json_field'] = get_param('JSONFIELD', '')

        # Parse mapping table (MAPPING_4_JSONPATH)
        mapping = []
        mapping_table = node.find('.//elementParameter[@name="MAPPING_4_JSONPATH"]')
        if mapping_table is not None:
            entries = list(mapping_table.findall('elementValue'))
            for i in range(0, len(entries), 2):
                schema_col = entries[i].get('value', '').strip('"')
                query = entries[i+1].get('value', '').strip('"')
                mapping.append({'schema_column': schema_col, 'query': query})
        component['config']['mapping'] = mapping
        return component

    def parse_unpivot_row(self, node, component: Dict) -> Dict:
        """Parse tUnpivotRow specific configuration"""
        component['config']['pivot_column'] = node.get('PIVOT_COLUMN', 'pivot_key')
        component['config']['value_column'] = node.get('VALUE_COLUMN', 'pivot_value')
        component['config']['group_by_columns'] = node.get('GROUP_BY_COLUMNS', '').split(';')

        # Extract ROW_KEYS from XML
        row_keys = []
        for element in node.findall('.//elementParameter[@name="ROW_KEYS"]/elementValue'):
            if element.get('elementRef') == 'COLUMN':
                row_keys.append(element.get('value', ''))

        # Ensure row_keys does not contain empty strings and provide default values if empty
        component['config']['row_keys'] = [key for key in row_keys if key ] or ['COBDATE', 'AGREEMENTID', 'MASTERMNEMONIC', 'CLIENT_OR_AFFILIATE', 'MNEMONIC', 'GMIACCOUNT', 'CURRENCY']
        component['config']['die_on_error'] = node.get('DIE_ON_ERROR', False)

        # Update schema to include only pivot_key, pivot_value, and row_keys in the specified order
        output_schema = [
            {'name': 'pivot_key', 'type': 'str', 'nullable': True, 'key': False},
            {'name': 'pivot_value', 'type': 'str', 'nullable': True, 'key': False}
        ]

        for key in component['config']['row_keys']:
            output_schema.append({'name': key, 'type': 'str', 'nullable': True, 'key': False})

        component['schema']['output'] = output_schema
        return component

    def parse_t_mssql_connection(self, node, component: Dict) -> Dict:
        """Parse tMSSqlConnection specific configuration"""
        config = component['config']

        for param in node.findall('.//elementParameter'):
            name = param.get('name')
            value = param.get('value', '')

            if name == 'HOST':
                config['host'] = value.strip('"')
            elif name == 'PORT':
                port_val = value.strip('"')
                try:
                    config['port'] = int(port_val)
                except ValueError:
                    config['port'] = port_val  # fallback to string if not integer
                    print(f"[DEBUG] Set PORT value: {config['port']}")
            elif name == 'DBNAME':
                config['dbname'] = value.strip('"')
            elif name == 'USER':
                config['user'] = value.strip('"')
            elif name == 'PASSWORD':
                if value.startswith('enc:system.encryption.key.v1:'):
                    cleaned = value.replace('enc:system.encryption.key.v1:', '')
                    print(f"[DEBUG] Cleaned PASSWORD value: {cleaned}")
                    config['password'] = cleaned
                else:
                    config['password'] = value.strip('"')
            elif name == 'PROPERTIES':
                config['properties'] = value.strip('"')
            elif name == 'AUTO_COMMIT':
                config['auto_commit'] = value.lower() == 'true'

        component['config'] = config
        return component

    def parse_t_mssql_input(self, node, component: Dict) -> Dict:
        """Parse tMSSqlInput specific configuration"""
        config = component['config']

        for param in node.findall('.//elementParameter'):
            name = param.get('name')
            value = param.get('value', '')

            if name == 'HOST':
                config['host'] = value.strip('"')
            elif name == 'PORT':
                port_val = value.strip('"')
                try:
                    config['port'] = int(port_val)
                except ValueError:
                    config['port'] = port_val  # fallback to string if not integer
                    print(f"[DEBUG] Set PORT value: {config['port']}")
            elif name == 'DBNAME':
                config['dbname'] = value.strip('"')
            elif name == 'USER':
                config['user'] = value.strip('"')
            elif name == 'PASSWORD':
                if value.startswith('enc:system.encryption.key.v1:'):
                    cleaned = value.replace('enc:system.encryption.key.v1:', '')
                    print(f"[DEBUG] Cleaned PASSWORD value: {cleaned}")
                    config['password'] = cleaned
                else:
                    config['password'] = value.strip('"')
            elif name == 'QUERY':
                config['query'] = value.strip('"')
            elif name == 'PROPERTIES':
                config['properties'] = value.strip('"')
            elif name == 'QUERY_TIMEOUT_IN_SECONDS':
                config['query_timeout'] = int(value) if value.isdigit() else 30
            elif name == 'TRIM_ALL_COLUMN':
                config['trim_all_columns'] = value.lower() == 'true'
                
            component['config'] = config
            return component

    def parse_t_change_file_encoding(self, node, component: Dict) -> Dict:
        """Parse tChangeFileEncoding specific configuration"""
        config = component['config']

        for param in node.findall('.//elementParameter'):
            name = param.get('name')
            value = param.get('value', '')

            if name == 'INFILE_NAME':
                config['infile'] = value.strip('"')
            elif name == 'OUTFILE_NAME':
                config['outfile'] = value.strip('"')
            elif name == 'USE_INENCODING':
                config['use_inencoding'] = value.lower() == 'true'
            elif name == 'INENCODING':
                config['inencoding'] = value.strip('"')
            elif name == 'ENCODING':
                config['outencoding'] = value.strip('"')
            elif name == 'BUFFERSIZE':
                config['buffer_size'] = int(value) if value.isdigit() else 8192
            elif name == 'CREATE':
                config['create'] = value.lower() == 'true'

        component['config'] = config
        return component

    def parse_textract_xml_field(self, node, component: Dict) -> Dict:
        """Parse tExtractXMLField specific configuration from Talend XML node."""
        def get_param(name, default=None):
            param = node.find(f'.//elementParameter[@name="{name}"]')
            return param.get('value', default) if param is not None else default

        # Remove extra quotes from loop_query
        loop_query = get_param('LOOP_QUERY', '')
        if loop_query and loop_query.startswith('"') and loop_query.endswith('"'):
            loop_query = loop_query[1:-1]
        xml_field = get_param('XMLFIELD', 'line')
        limit = get_param('LIMIT', '0')
        die_on_error = get_param('DIE_ON_ERROR', 'false').lower() == 'true'
        ignore_ns = get_param('IGNORE_NS', 'false').lower() == 'true'

        # Parse mapping table (MAPPING)
        mapping = []
        mapping_table = node.find('.//elementParameter[@name="MAPPING"]')
        if mapping_table is not None:
            entries = list(mapping_table.findall('elementValue'))
            for i in range(0, len(entries), 3):
                schema_col = entries[i].get('value', '').strip('"') if i < len(entries) else ''
                query = entries[i+1].get('value', '').strip('"') if (i+1) < len(entries) else ''
                nodecheck = entries[i+2].get('value', '') if (i+2) < len(entries) else ''
                mapping.append({'schema_column': schema_col, 'query': query, 'nodecheck': nodecheck})

        component['config']['xml_field'] = xml_field
        component['config']['loop_query'] = loop_query
        component['config']['mapping'] = mapping
        component['config']['limit'] = limit
        component['config']['die_on_error'] = die_on_error
        component['config']['ignore_ns'] = ignore_ns
        return component

    def parse_tsetglobalvar(self, node, component: Dict) -> Dict:
        """Parse tSetGlobalVar specific configuration"""
        variables = []

        # Parse VARIABLES table parameter - handle the specific Talend
        for param in node.findall('.//elementParameter[@name="VARIABLES"]'):
            # Get all elementValue entries
            element_values = param.findall('.//elementValue')

            if element_values:
                # Process pairs of KEY/VALUE elementRef entries
                current_key = None
                current_value = None

                for elem in element_values:
                    element_ref = elem.get('elementRef', '')
                    element_value = elem.get('value', '').strip('"')

                    if element_ref == 'KEY':
                        # If we have a pending key-value pair, save it first
                        if current_key is not None and current_value is not None:
                            variables.append({
                                'name': current_key,
                                'value': current_value
                            })
                        # Start new key-value pair
                        current_key = element_value
                        current_value = None
                    elif element_ref == 'VALUE':
                        current_value = element_value

                        # If we have both key and value, save the pair
                        if current_key is not None:
                            variables.append({
                                'name': current_key,
                                'value': current_value
                            })
                            current_key = None
                            current_value = None

                # Handle any remaining unpaired key
                if current_key is not None and current_value is not None:
                    variables.append({
                        'name': current_key,
                        'value': current_value
                    })

        # Fallback: Check for other structures if no variables found
        if not variables:
            # Check for alternative table structure
            for table in node.findall(".//elementParameter[@name='VARIABLES']/TABLE"):
                for row in table.findall("./row"):
                    var_name = ""
                    var_value = ""
                    for cell in row.findall("./cell"):
                        column_name = cell.get('columnName', '')
                        if column_name in ['KEY', 'NAME', 'VARIABLE_NAME']:
                            var_name = cell.text or cell.get('value', '')
                        elif column_name in ['VALUE', 'VARIABLE_VALUE']:
                            var_value = cell.text or cell.get('value', '')

                    if var_name:
                        variables.append({
                            'name': var_name.strip('"'),
                            'value': var_value.strip('"')
                        })

        # Check for code-based variable declarations in elementParameter
        if not variables:
            for param in node.findall('.//elementParameter'):
                param_name = param.get('name', '')
                param_value = param.get('value', '').strip('"')

                # Skip standard tSetGlobalVar parameters
                if param_name in ['VARIABLES', 'UNIQUE_NAME', 'CONNECTION_FORMAT']:
                    continue

                # Look for Java variable declarations
                if param_value and ('java.util.' in param_value or 'new ' in param_value):
                    variables.append({
                        'name': param_name,
                        'value': param_value
                    })

        component['config']['VARIABLES'] = variables

        # Debug output
        if variables:
            self.logger.info(f"[TSetGlobalVar] Parsed {len(variables)} variable(s): {variables}")
        else:
            self.logger.warning(f"[TSetGlobalVar] No variables found in component {component.get('id', 'unknown')}")

        return component

    def parse_tdenormalize(self, node, component: Dict) -> Dict:
        """
        Parse tDenormalize specific configuration from Talend XML.
        Handles the DENORMALIZE_COLUMNS table parameter properly.
        """
        config = component['config']

        # Parse NULL_AS_EMPTY parameter
        null_as_empty_elem = node.find(".//elementParameter[@name='NULL_AS_EMPTY']")
        config['null_as_empty'] = null_as_empty_elem.get('value', 'false').lower() == 'true' if null_as_empty_elem is not None else False

        # Parse CONNECTION_FORMAT parameter
        connection_format_elem = node.find(".//elementParameter[@name='CONNECTION_FORMAT']")
        config['connection_format'] = connection_format_elem.get('value', 'row') if connection_format_elem is not None else 'row'

        # Parse DENORMALIZE_COLUMNS table parameter
        denormalize_columns = []
        for param in node.findall(".//elementParameter[@name='DENORMALIZE_COLUMNS']"):

            # Get all elementValue entries for this table
            elements = param.findall('./elementValue')
            # Group elements by sets of 3 (INPUT_COLUMN, DELIMITER, MERGE)
            for i in range(0, len(elements), 3):
                if i + 2 < len(elements):
                    # Extract the three elements for this row
                    elem1 = elements[i]
                    elem2 = elements[i + 1]
                    elem3 = elements[i + 2]

                    # Parse based on elementRef to handle any order
                    row_data = {}
                    for elem in [elem1, elem2, elem3]:
                        ref = elem.get('elementRef', '')
                        value = elem.get('value', '')

                        if ref == 'INPUT_COLUMN':
                            row_data['input_column'] = value
                        elif ref == 'DELIMITER':
                            # clean delimiter: remove XML encoding and quotes
                            if value.startswith('&quot;') and value.endswith('&quot;'):
                                value = value[6:-6]  # Remove &quot; from both ends
                            elif value.startswith('"') and value.endswith('"'):
                                value = value[1:-1]  # Remove quotes
                            row_data['delimiter'] = value
                        elif ref == 'MERGE':
                            row_data['merge'] = value.lower() == 'true'

                    # Only add if we have a valid input_column
                    if row_data.get('input_column'):
                        # Set defaults for missing values
                        denormalize_columns.append({
                            'input_column': row_data.get('input_column', ''),
                            'delimiter': row_data.get('delimiter', ','),
                            'merge': row_data.get('merge', True)
                        })

        config['denormalize_columns'] = denormalize_columns

        component['config'] = config
        return component

    def parse_thash_output(self, node, component: Dict) -> Dict:
        """Parse tHashOutput specific configuration"""
        # All settings are optional, map all advanced settings
        for param in node.findall('.//elementParameter'):
            name = param.get('name')
            value = param.get('value', '')
            if name and value:
                if value.lower() in ['true', 'false']:
                    value = value.lower() == 'true'
                component['config'][name] = value
        return component

    def parse_tfileoutputpositional(self, node, component: Dict) -> Dict:
        """Parse tFileOutputPositional specific configuration"""
        # Parse FORMATS table
        formats = []
        format_map = {}
        for param in node.findall('.//elementParameter[@name="FORMATS"]'):
            fmt = {}
            current_col = None
            for item in param.findall('./elementValue'):
                ref = item.get('elementRef')
                value = item.get('value', '')
                if ref == 'SCHEMA_COLUMN':
                    if fmt and current_col:
                        formats.append(fmt)
                        format_map[current_col] = fmt
                        fmt = {}
                    current_col = value.strip('"')
                    fmt['SCHEMA_COLUMN'] = current_col
                elif ref and value:
                    fmt[ref.lower()] = value.strip('"')
            if fmt and current_col:
                formats.append(fmt)
                format_map[current_col] = fmt
        component['config']['formats'] = formats

        # Merge formatting info into schema columns if available
        if 'output' in component['schema']:
            for col in component['schema']['output']:
                col_fmt = format_map.get(col['name'])
                if col_fmt:
                    # Add size, padding_char, align, etc. to schema column
                    if 'size' in col_fmt:
                        col['size'] = col_fmt['size']
                    if 'padding_char' in col_fmt:
                        col['padding_char'] = col_fmt['padding_char']
                    if 'align' in col_fmt:
                        col['align'] = col_fmt['align']
        return component

    def parse_file_input_excel(self, node, component: dict) -> dict:
        """
        Parse tFileInputExcel specific configuration from Talend XML node.
        Comprehensive parsing of all tFileInputExcel parameters including complex tables.
        """
        # Helper function to get parameters
        def get_param(name, default=None):
            elem = node.find(f".//elementParameter[@name='{name}']")
            return elem.get('value', default) if elem is not None else default

        # Helper function to convert string boolean to actual boolean
        def str_to_bool(value, default=False):
            if isinstance(value, str):
                return value.lower() == 'true'
            return default if value is None else bool(value)

        # Helper function to convert string to int with fallback
        def str_to_int(value, default=0):
            if isinstance(value, str) and value.isdigit():
                return int(value)
            elif isinstance(value, int):
                return value
            return default

        # **Basic File Parameters**
        component['config']['filepath'] = get_param('FILENAME', '')
        component['config']['password'] = get_param('PASSWORD', '')

        # **Excel Version and Sheet Selection**
        component['config']['version_2007'] = str_to_bool(get_param('VERSION_2007', 'true'), True)
        component['config']['all_sheets'] = str_to_bool(get_param('ALL_SHEETS', 'false'), False)

        # **Parse SHEETLIST table for sheet names and regex patterns**
        sheetlist = []
        for table in node.findall(".//elementParameter[@name='SHEETLIST']"):
            sheet_entry = {}
            for elem in table.findall('./elementValue'):
                ref = elem.get('elementRef', '')
                val = elem.get('value', '')
                if ref == 'SHEETNAME':
                    sheet_entry['sheetname'] = val
                elif ref == 'USE_REGEX':
                    sheet_entry['use_regex'] = str_to_bool(val, False)

            if sheet_entry:  # Only add if we have data
                sheetlist.append(sheet_entry)

        component['config']['sheetlist'] = sheetlist

        # **Row and Column Parameters**
        component['config']['header'] = str_to_int(get_param('HEADER', '1'), 1)
        component['config']['footer'] = str_to_int(get_param('FOOTER', '0'), 0)
        component['config']['limit'] = get_param('LIMIT', '')
        component['config']['affect_each_sheet'] = str_to_bool(get_param('AFFECT_EACH_SHEET', 'false'), False)
        component['config']['first_column'] = str_to_int(get_param('FIRST_COLUMN', '1'), 1)
        component['config']['last_column'] = get_param('LAST_COLUMN', '')

        # **Error Handling**
        component['config']['die_on_error'] = str_to_bool(get_param('DIE_ON_ERROR', 'false'), False)
        component['config']['suppress_warn'] = str_to_bool(get_param('SUPPRESS_WARN', 'false'), False)
        component['config']['novalidate_on_cell'] = str_to_bool(get_param('NOVALIDATE_ON_CELL', 'false'), False)

        # **Advanced Separators**
        component['config']['advanced_separator'] = str_to_bool(get_param('ADVANCED_SEPARATOR', 'false'), False)
        thousands_sep = get_param('THOUSANDS_SEPARATOR', ',')
        decimal_sep = get_param('DECIMAL_SEPARATOR', '.')
        # Clean quotes from separators
        component['config']['thousands_separator'] = thousands_sep.strip('"') if isinstance(thousands_sep, str) else ','
        component['config']['decimal_separator'] = decimal_sep.strip('"') if isinstance(decimal_sep, str) else '.'

        # **Trimming Configuration**
        component['config']['trimall'] = str_to_bool(get_param('TRIMALL', 'false'), False)

        # **Parse TRIMSELECT table for column-specific trimming**
        trim_select = []
        for table in node.findall(".//elementParameter[@name='TRIMSELECT']"):
            trim_entry = {}
            for elem in table.findall('./elementValue'):
                ref = elem.get('elementRef', '')
                val = elem.get('value', '')
                if ref == 'SCHEMA_COLUMN':
                    trim_entry['column'] = val
                elif ref == 'TRIM':
                    trim_entry['trim'] = str_to_bool(val, False)

            if trim_entry and 'column' in trim_entry:
                trim_select.append(trim_entry)

        component['config']['trim_select'] = trim_select

        # **Date Conversion Configuration**
        component['config']['convertdatetostring'] = str_to_bool(get_param('CONVERTDATETOSTRING', 'false'), False)

        # **Parse DATESELECT table for date conversion settings**
        date_select = []
        for table in node.findall(".//elementParameter[@name='DATESELECT']"):
            date_entry = {}
            for elem in table.findall('./elementValue'):
                ref = elem.get('elementRef', '')
                val = elem.get('value', '')
                if ref == 'SCHEMA_COLUMN':
                    date_entry['column'] = val
                elif ref == 'CONVERTDATE':
                    date_entry['convert_date'] = str_to_bool(val, False)
                elif ref == 'PATTERN':
                    date_entry['pattern'] = val.strip('"') if val else "MM-dd-yyyy"

            if date_entry and 'column' in date_entry:
                date_select.append(date_entry)

        component['config']['date_select'] = date_select

        # **Reading Behavior**
        component['config']['read_real_value'] = str_to_bool(get_param('READ_REAL_VALUE', 'false'), False)
        component['config']['stopread_on_emptyrow'] = str_to_bool(get_param('STOPREAD_ON_EMPTYROW', 'false'), False)
        component['config']['include_phoneticruns'] = str_to_bool(get_param('INCLUDE_PHONETICRUNS', 'true'), True)

        # **Generation and Performance**
        component['config']['generation_mode'] = get_param('GENERATION_MODE', 'EVENT_MODE')
        component['config']['configure_inflation_ratio'] = str_to_bool(get_param('CONFIGURE_INFLATION_RATIO', 'false'), False)
        component['config']['inflation_ratio'] = get_param('INFLATION_RATIO', '')

        # **Encoding**
        encoding = get_param('ENCODING', 'UTF-8')
        component['config']['encoding'] = encoding.strip('"') if isinstance(encoding, str) else 'UTF-8'

        # **Additional Parameters for Compatibility**
        component['config']['sheet_name'] = get_param('SHEET_NAME', '')  # For single sheet mode
        component['config']['execution_mode'] = get_param('EXECUTION_MODE', '')
        component['config']['chunk_size'] = get_param('CHUNK_SIZE', '')

        # **Normalize parameter names to match FileInputExcel component expectations**
        # Map Talend parameter names to component-expected names
        if 'filepath' not in component['config'] and component['config']['filename']:
            component['config']['filepath'] = component['config']['filename']

        return component