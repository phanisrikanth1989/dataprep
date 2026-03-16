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


class FixedFlowInputComponent(BaseComponent):
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
        row_separator (str): Row separator for inline content. Default: '\\n'
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
                logger.warning(f"[{self.id}] No valid mode selected, defaulting to single mode")
                output_data = self._generate_single_mode_rows(nb_rows, schema_columns)

            rows_generated = len(output_data)
            logger.info(f"[{self.id}] Processing complete: generated {rows_generated} rows")

            # Update statistics
            self._update_stats(0, rows_generated, 0)  # No input rows, generated rows as output, no rejects

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

            # Return empty DataFrame on error
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

        # Fallback: generate from values_config if rows not available
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
            # Use the ContextManager's resolve_string method which handles {{java}} expressions
            # and provides fallback for GlobalMap access when Java bridge is unavailable
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
