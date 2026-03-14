"""
FixedFlowInputComponent - Generates fixed rows of data based on configuration.

Talend equivalent: tFixedFlowInput

This component generates fixed rows of data with support for three modes:
- Single mode: Generates rows using VALUES configuration
- Inline table mode: Uses INTABLE configuration data
- Inline content mode: Parses INLINECONTENT with separators
"""
import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent

logger = logging.getLogger(__name__)


class FixedFlowInput(BaseComponent):
    """
    Generates fixed rows of data based on configuration and selected mode.

    Configuration:
        nb_rows (int): Number of rows to generate. Default: 1
        use_singlemode (bool): Enable single mode with VALUES. Default: True
        use_intable (bool): Enable inline table mode. Default: False
        use_inlinecontent (bool): Enable inline content mode. Default: False
        schema (list): Schema definition for output columns. Required.
        values_config (dict): Column values for single mode
        rows (list): Pre-generated rows data
        intable_data (list): Table data for inline table mode
        inline_content (str): Content string for inline content mode
        row_separator (str): Row separator for inline content. Default: '\n'
        field_separator (str): Field separator for inline content. Default: ';'
        die_on_error (bool): Fail on error. Default: True

    Inputs:
        None: This component generates data without inputs

    Outputs:
        main: Generated DataFrame with fixed data

    Statistics:
        NB_LINE: Total rows generated
        NB_LINE_OK: Successful rows generated
        NB_LINE_REJECT: Always 0 (no rejection logic)

    Example:
        config = {
            "nb_rows": 5,
            "use_singlemode": True,
            "schema": [{"name": "id", "type": "id_Integer"}],
            "values_config": {"id": 1}
        }
        component = FixedFlowInputComponent("comp_1", config)
        result = component.execute()
    """

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Check that at least one mode is enabled
        use_singlemode = self.config.get('use_singlemode', True)
        use_intable = self.config.get('use_intable', False)
        use_inlinecontent = self.config.get('use_inlinecontent', False)

        if not any([use_singlemode, use_intable, use_inlinecontent]):
            errors.append("No valid mode selected (use_singlemode, use_intable, or use_inlinecontent must be True)")

        # Validate nb_rows
        nb_rows = self.config.get('nb_rows', 1)
        if not isinstance(nb_rows, int) or nb_rows < 0:
            errors.append("Config 'nb_rows' must be a non-negative integer")

        # Validate schema
        schema = self.config.get('schema', [])
        if not isinstance(schema, list):
            errors.append("Config 'schema' must be a list")
        elif len(schema) == 0:
            errors.append("Config 'schema' cannot be empty")

        # Validate specific mode requirements
        if use_singlemode:
            # Single mode should have either values_config or rows
            if not self.config.get('values_config') and not self.config.get('rows'):
                errors.append("Single mode selected but no values_config or rows provided")

        elif use_inlinecontent:
            # Inline content mode should have inline_content
            if not self.config.get('inline_content'):
                errors.append("Inline content mode selected but no inline_content provided")

        return errors

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Generate fixed rows of data based on configuration and selected mode.

        Args:
            input_data: Not used for this component

        Returns:
            Dictionary containing:
                - main: Generated DataFrame with fixed data
        """
        try:
             # Extract configuration
            nb_rows = int(self.config.get('nb_rows', 1))
            schema_columns = self.config.get('schema', [])

            # Get mode configuration
            use_singlemode = self.config.get('use_singlemode', True)
            use_intable = self.config.get('use_intable', False)
            use_inlinecontent = self.config.get('use_inlinecontent', False)

            logger.info(f"[{self.id}] Processing started: nb_rows={nb_rows}, "
                        f"single={use_singlemode}, intable={use_intable}, inlinecontent={use_inlinecontent}")

            # Generate rows based on the selected mode
            if use_singlemode:
                output_data = self._generate_single_mode_rows(nb_rows, schema_columns)
            elif use_intable:
                output_data = self._generate_intable_mode_rows(nb_rows, schema_columns)
            elif use_inlinecontent:
                output_data = self._generate_inline_content_rows(nb_rows, schema_columns)
            else:
                logger.warning(f"[{self.id}] No valid mode selected, defaulting to single_mode")
                output_data = self._generate_single_mode_rows(nb_rows, schema_columns)

            rows_generated = len(output_data)
            logger.info(f"[{self.id}] Processing complete: generated {rows_generated} rows")

            # Update statistics
            self._update_stats(0, rows_generated, 0)

            # Convert to DataFrame
            if output_data:
                df = pd.DataFrame(output_data)
                return {'main': df}
            else:
                # Return empty DataFrame with correct schema
                column_names = [col['name'] if isinstance(col, dict) else col for col in schema_columns]
                df = pd.DataFrame(columns=column_names)
                return {'main': df}

        except Exception as e:
            logger.error(f"[{self.id}] Processing failed: {str(e)}")
            if self.config.get('die_on_error', True):
                raise

            #Return empty DataFrame on error
            logger.warning(f"[{self.id}] Returning empty DataFrame due to error")
            column_names = [col['name'] if isinstance(col, dict) else col for col in self.config.get('schema', [])]
            df = pd.DataFrame(columns=column_names)
            return {'main': df}
        
    def _generate_single_mode_rows(self, nb_rows: int, schema_columns: List) -> List[Dict]:
        """Generate rows using single mode (VALUES configuration)"""
        # Get the pre-generated rows from the parser
        rows = self.config.get('rows', [])
        if rows:
            # Process each row to resolve expressions and context variables
            resolved_rows = []
            for row in rows:
                resolved_row = {}
                for key, value in row.items():
                    # Resolve context and global variables for each value
                    resolved_row[key] = self._resolve_value(value)
                resolved_rows.append(resolved_row)
            return resolved_rows

        # Fallback: generate from values config if rows not available
        values_config = self.config.get('values_config', {})
        output_data = []

        for _ in range(nb_rows):
            row = {}
            for col in schema_columns:
                col_name = col['name'] if isinstance(col, dict) else col
                value = values_config.get(col_name, None)
                # Resolve context and global variables
                row[col_name] = self._resolve_value(value)
            output_data.append(row)

        return output_data

    def _generate_intable_mode_rows(self, nb_rows: int, schema_columns: List) -> List[Dict]:
        """Generate rows using inline table mode (INTABLE configuration)"""
        intable_data = self.config.get('intable_data', [])
        output_data = []

        for i in range(nb_rows):
            if i < len(intable_data):
                row = intable_data[i].copy()
                # Resolve context and global variables in each value
                for key, value in row.items():
                    row[key] = self._resolve_value(value)
                output_data.append(row)
            else:
                # Create empty row if not enough data
                row = {}
                for col in schema_columns:
                    col_name = col['name'] if isinstance(col, dict) else col
                    row[col_name] = None
                output_data.append(row)

        return output_data

    def _generate_inline_content_rows(self, nb_rows: int, schema_columns: List) -> List[Dict]:
        """Generate rows using inline content mode (INLINECONTENT configuration)"""
        inline_content = self.config.get('inline_content', '')
        row_separator = self.config.get('row_separator', '\n')
        field_separator = self.config.get('field_separator', ';')

        logger.info(f"[{self.id}] Raw inline_content: {repr(inline_content)}")
        logger.info(f"[{self.id}] Row separator: {repr(row_separator)}")
        logger.info(f"[{self.id}] Field separator: {repr(field_separator)}")
        logger.info(f"[{self.id}] nb_rows parameter: {nb_rows} (ignored in inline content mode)")

        output_data = []

        if inline_content:
            # Handle escaped characters in separators
            if row_separator == '\\n':
                row_separator = '\n'
            if field_separator == '\\|':
                field_separator = '|'

            # Split content into rows and filter out empty rows
            raw_rows = inline_content.split(row_separator)
            logger.debug(f"[{self.id}] Split into {len(raw_rows)} raw rows: {raw_rows}")

            content_rows = [row.strip() for row in raw_rows if row.strip()]
            logger.info(f"[{self.id}] Parsed {len(content_rows)} non-empty rows from inline content: {content_rows}")

            # For inline content mode, process ALL available content rows (ignore nb_rows completely)
            # This behaves like reading a delimited file - process all content provided
            logger.info(f"[{self.id}] Processing ALL {len(content_rows)} rows from inline content (nb_rows ignored)")

            for i, current_row in enumerate(content_rows):
                field_values = current_row.split(field_separator)
                logger.debug(f"[{self.id}] Row {i}: '{current_row}' -> fields: {field_values}")

                row = {}
                for col_idx, col in enumerate(schema_columns):
                    col_name = col['name'] if isinstance(col, dict) else col
                    if col_idx < len(field_values):
                        value = field_values[col_idx].strip()
                        row[col_name] = self._resolve_value(value)
                    else:
                        row[col_name] = None
                output_data.append(row)
                logger.debug(f"[{self.id}] Generated row {i+1}: {row}")
        else:
            # No content provided, return empty result (don't create empty rows based on nb_rows)
            logger.info(f"[{self.id}] No inline content provided, returning empty result")

        return output_data

    def _resolve_value(self, value):
        """Resolve context variables, global map references, and expressions in a value"""
        if not isinstance(value, str):
            return value

        try:
            # Special handling for {{java}} expressions
            if value.startswith('{{java}}'):
                java_expr = value[8:]  # Remove {{java}} prefix
                logger.debug(f"[{self.id}] Processing Java expression: {java_expr}")

                # Extract and resolve context variables in the Java expression
                import re
                from datetime import datetime

                # Handle TalendDate function calls
                if 'TalendDate.formatDate(' in java_expr and 'TalendDate.getCurrentDate()' in java_expr:
                    # Handle TalendDate.formatDate("pattern", TalendDate.getCurrentDate())
                    pattern_match = re.search(r'TalendDate\.formatDate\("([^"]*)"', java_expr)
                    if pattern_match:
                        java_pattern = pattern_match.group(1)
                        # Convert Java date pattern to Python strftime format
                        python_pattern = self._convert_java_date_pattern_to_python(java_pattern)
                        current_date = datetime.now()
                        formatted_date = current_date.strftime(python_pattern)
                        logger.debug(f"[{self.id}] TalendDate.formatDate result: {formatted_date}")
                        return formatted_date

                # Handle Integer.toString() and other Java method calls
                # Pattern: Integer.toString((Type)globalMap.get("key"))
                java_method_pattern = r'(\w+)\.(\w+)\(\((\w+)\)\s*globalMap\.get\("([^"]+)"\)\)'
                java_method_matches = re.findall(java_method_pattern, java_expr)

                if java_method_matches:
                    for class_name, method_name, cast_type, global_key in java_method_matches:
                        # Get value from globalMap
                        global_value = self.global_map.get(global_key) if self.global_map else None

                        if global_value is not None:
                            # Apply Java-style type casting
                            if cast_type == "Integer":
                                try:
                                    casted_value = int(global_value)
                                except (ValueError, TypeError):
                                    logger.warning(f"[{self.id}] Could not cast globalMap value '{global_value}' to Integer")
                                    casted_value = 0
                            elif cast_type == "Long":
                                try:
                                    casted_value = int(global_value)
                                except (ValueError, TypeError):
                                    logger.warning(f"[{self.id}] Could not cast globalMap value '{global_value}' to Long")
                                    casted_value = 0
                            elif cast_type == "Double" or cast_type == "Float":
                                try:
                                    casted_value = float(global_value)
                                except (ValueError, TypeError):
                                    logger.warning(f"[{self.id}] Could not cast globalMap value '{global_value}' to {cast_type}")
                                    casted_value = 0.0
                            else:
                                casted_value = global_value

                            # Apply Java method call
                            if class_name == "Integer" and method_name == "toString":
                                result_value = str(casted_value)
                            elif class_name == "Long" and method_name == "toString":
                                result_value = str(casted_value)
                            elif class_name == "Double" and method_name == "toString":
                                result_value = str(casted_value)
                            elif class_name == "Float" and method_name == "toString":
                                result_value = str(casted_value)
                            elif class_name == "String" and method_name == "valueOf":
                                result_value = str(casted_value)
                            else:
                                # Unknown method, just return the casted value as string
                                result_value = str(casted_value)

                            logger.debug(f"[{self.id}] Java method call {class_name}.{method_name}({casted_value}) -> {result_value}")
                            return result_value
                        else:
                            logger.warning(f"[{self.id}] GlobalMap key '{global_key}' not found for method call")
                            # Return default based on cast type
                            if cast_type in ["Integer", "Long"]:
                                return "0"
                            elif cast_type in ["Double", "Float"]:
                                return "0.0"
                            else:
                                return ""

                # Handle simple method calls like Integer.toString((Integer)5)
                simple_method_pattern = r'(\w+)\.(\w+)\(\((\w+)\)(\d+)\)'
                simple_method_matches = re.findall(simple_method_pattern, java_expr)

                if simple_method_matches:
                    for class_name, method_name, cast_type, value_str in simple_method_matches:
                        try:
                            # Parse the literal value
                            if cast_type in ["Integer", "Long"]:
                                literal_value = int(value_str)
                            elif cast_type in ["Double", "Float"]:
                                literal_value = float(value_str)
                            else:
                                literal_value = value_str

                            # Apply method call
                            if class_name == "Integer" and method_name == "toString":
                                result_value = str(literal_value)
                            elif class_name == "Long" and method_name == "toString":
                                result_value = str(literal_value)
                            elif class_name == "Double" and method_name == "toString":
                                result_value = str(literal_value)
                            elif class_name == "Float" and method_name == "toString":
                                result_value = str(literal_value)
                            elif class_name == "String" and method_name == "valueOf":
                                result_value = str(literal_value)
                            else:
                                result_value = str(literal_value)

                            logger.debug(f"[{self.id}] Simple Java method call {class_name}.{method_name}({literal_value}) -> {result_value}")
                            return result_value
                        except (ValueError, TypeError) as e:
                            logger.warning(f"[{self.id}] Error processing simple method call: {e}")
                            return "0"

                # Handle globalMap.get() calls within Java expressions
                globalmap_pattern = r'\((\w+)\)\s*globalMap\.get\("([^"]+)"\)'
                globalmap_matches = re.findall(globalmap_pattern, java_expr)

                if globalmap_matches:
                    resolved_expr = java_expr
                    for cast_type, global_key in globalmap_matches:
                        # Get value from globalMap
                        global_value = self.global_map.get(global_key) if self.global_map else None

                        if global_value is not None:
                            # Apply Java-style type casting
                            if cast_type == "Integer":
                                try:
                                    resolved_value = int(global_value)
                                except (ValueError, TypeError):
                                    logger.warning(f"[{self.id}] Could not cast globalMap value '{global_value}' to Integer")
                                    resolved_value = 0
                            elif cast_type == "String":
                                resolved_value = str(global_value)
                            elif cast_type == "Long":
                                try:
                                    resolved_value = int(global_value)
                                except (ValueError, TypeError):
                                    logger.warning(f"[{self.id}] Could not cast globalMap value '{global_value}' to Long")
                                    resolved_value = 0
                            elif cast_type == "Double" or cast_type == "Float":
                                try:
                                    resolved_value = float(global_value)
                                except (ValueError, TypeError):
                                    logger.warning(f"[{self.id}] Could not cast globalMap value '{global_value}' to {cast_type}")
                                    resolved_value = 0.0
                            else:
                                resolved_value = global_value

                            # Replace the entire cast + globalMap.get() expression with the resolved value
                            original_expr = f"(({cast_type}) globalMap.get(\"{global_key}\"))"
                            resolved_expr = resolved_expr.replace(original_expr, str(resolved_value))
                            logger.debug(f"[{self.id}] Resolved globalMap: {original_expr} -> {resolved_value}")
                        else:
                            logger.warning(f"[{self.id}] GlobalMap key '{global_key}' not found, using default value 0")
                            # Replace with default value based on cast type
                            default_value = "0" if cast_type in ["Integer", "Long"] else "0.0" if cast_type in ["Double", "Float"] else ""
                            original_expr = f"(({cast_type}) globalMap.get(\"{global_key}\"))"
                            resolved_expr = resolved_expr.replace(original_expr, default_value)

                    java_expr = resolved_expr

                    # Handle simple globalMap.get() calls without casting
                    simple_globalmap_pattern = r'globalMap\.get\("([^"]+)"\)'
                    simple_matches = re.findall(simple_globalmap_pattern, java_expr)

                    if simple_matches:
                        resolved_expr = java_expr
                        for global_key in simple_matches:
                            global_value = self.global_map.get(global_key) if self.global_map else None
                            if global_value is not None:
                                # Replace with the actual value (as string if it's a string, otherwise as-is)
                                if isinstance(global_value, str):
                                    replacement = f'"{global_value}"'
                                else:
                                    replacement = str(global_value)

                                original_expr = f'globalMap.get("{global_key}")'
                                resolved_expr = resolved_expr.replace(original_expr, replacement)
                                logger.debug(f"[{self.id}] Resolved simple globalMap: {original_expr} -> {replacement}")
                            else:
                                logger.warning(f"[{self.id}] GlobalMap key '{global_key}' not found")
                                original_expr = f'globalMap.get("{global_key}")'
                                resolved_expr = resolved_expr.replace(original_expr, 'null')

                        java_expr = resolved_expr

                    # Handle context.variable references
                    def replace_context_vars(match):
                        var_name = match.group(1)
                        var_value = self.context_manager.get(var_name)
                        if var_value is not None:
                            # Return as quoted string if it's a string value
                            if isinstance(var_value, str):
                                return f'"{var_value}"'
                            return str(var_value)
                        return match.group(0)

                    # Replace context.variable with actual values
                    resolved_expr = re.sub(r'\bcontext\.(\w+)\b', replace_context_vars, java_expr)
                    logger.debug(f"[{self.id}] Resolved Java expression: {resolved_expr}")

            # Try to evaluate the expression as Python code
                try:
                    # Clean up the expression for Python evaluation
                    # Replace Java string concatenation with Python
                    resolved_expr = resolved_expr.replace(' + ', ' + ')
                    # Handle null values
                    resolved_expr = resolved_expr.replace('null', 'None')
                    result = eval(resolved_expr)
                    logger.debug(f"[{self.id}] Java expression result: {result}")
                    return result
                except Exception as eval_error:
                    logger.warning(f"[{self.id}] Could not evaluate Java expression '{resolved_expr}': {eval_error}")
                    return resolved_expr

            # Use the ContextManager's resolve_string method for non-Java expressions
            resolved_value = self.context_manager.resolve_string(value)

            # If the resolved value is different from input, return it
            if resolved_value != value:
                # Try to convert to appropriate type if it's a number
                try:
                    if resolved_value.isdigit():
                        return int(resolved_value)
                    elif '.' in resolved_value and resolved_value.replace('.', '').replace('-', '').isdigit():
                        return float(resolved_value)
                except:
                    pass
                return resolved_value

            # Fallback to legacy resolution methods for backward compatibility
            # Handle ${context.variable} format
            if value.startswith('${') and value.endswith('}'):
                context_ref = value[2:-1]  # Remove ${ and }
                if context_ref.startswith('context.'):
                    context_key = context_ref[8:]  # Remove 'context.'
                    resolved_value = self.context_manager.get(context_key)
                    if resolved_value is not None:
                        return resolved_value

            # Handle direct context.variable references
            elif value.startswith('context.'):
                context_key = value[8:]  # Remove 'context.'
                resolved_value = self.context_manager.get(context_key)
                if resolved_value is not None:
                    return resolved_value

            # Handle globalMap.get() references directly (fallback)
            elif "globalMap.get" in value:
                import re
                match = re.search(r'globalMap\.get\("(.*?)"\)', value)
                if match:
                    global_key = match.group(1)
                    resolved_value = self.global_map.get(global_key, None)
                    if resolved_value is not None:
                        # Replace the globalMap reference with the resolved value
                        new_value = value.replace(f'globalMap.get("{global_key}")', str(resolved_value))
                        # Clean up Java-style casting
                        new_value = new_value.replace("((Integer)", "").replace(")", "")
                        # Try to evaluate as expression
                        try:
                            return eval(new_value)
                        except:
                            return new_value

            # Return original value if no special processing needed
            return value

        except Exception as e:
            logger.warning(f"[{self.id}] Failed to resolve value '{value}': {e}")
            return value


    def _convert_java_date_pattern_to_python(self, java_pattern):
        """Convert Java SimpleDateFormat pattern to Python strftime format"""
        # Common Java to Python date pattern mappings
        pattern_mapping = {
                    'yyyy': '%Y',   # 4-digit year
                    'yy': '%y',     # 2-digit year
                    'MM': '%m',     # Month (01-12)
                    'MMM': '%b',    # Abbreviated month name
                    'MMMM': '%B',   # Full month name
                    'dd': '%d',     # Day of month (01-31)
                    'HH': '%H',     # Hour (00-23)
                    'hh': '%I',     # Hour (01-12)
                    'mm': '%M',     # Minute (00-59)
                    'ss': '%S',     # Second (00-59)
                    'SSS': '%f',    # Microsecond (000000-999999) - closest to milliseconds
                    'a': '%p',      # AM/PM
                    'E': '%a',      # Abbreviated weekday name
                    'EEEE': '%A',   # Full weekday name
                }

        python_pattern = java_pattern

        # Replace patterns in order of specificity (longer patterns first)
        for java_fmt, python_fmt in sorted(pattern_mapping.items(), key=len, reverse=True):
            python_pattern = python_pattern.replace(java_fmt, python_fmt)

        return python_pattern