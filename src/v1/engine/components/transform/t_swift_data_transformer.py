"""
TSwiftDataTransformer component - Transform SWIFT pipe-delimited data based on configuration mappings
Integrates swift_data_transformer.py functionality into ETL engine
"""

import pandas as pd
import yaml
import json
import logging
import re
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from collections import defaultdict

from ...base_component import BaseComponent

logger = logging.getLogger(__name__)


class TSwiftDataTransformer(BaseComponent):
    """
    Transform SWIFT pipe-delimited data from one format to another based on configuration mappings.

    Input: SWIFT pipe-delimited DataFrame (e.g., from TSwiftBlockFormatter)
    Output: Transformed DataFrame with business-friendly fields

    Example transformation:
    Input: messagetype|block1bic|block2bic|block4_20|block4_25|block4_61|block4_86|...
    Output: SIDE|TERMID|DESTID|OURREF|THEIRREF|AMOUNT|CURRENCY|VALUEDATE|...
    """

    def __init__(self, comp_id: str, config: Dict[str, Any], global_map: Any, context_manager: Any):
        """Initialize the SWIFT Data Transformer component"""
        super().__init__(comp_id, config, global_map, context_manager)

        # Initialize transformation configuration
        self._init_transformer_config()

    def _init_transformer_config(self):
        """Initialize transformation configuration"""

        # Get transformation configuration from component config
        self.transform_config = self.config.get('transform_config', {})

        # Load external config file if specified
        config_file = self.config.get('config_file')
        if config_file:
            self.transform_config = self._load_external_config(config_file)
        # Set default configuration if none provided
        if not self.transform_config:
            self.transform_config = self._get_default_transform_config()

        # Extract key configuration sections
        self.input_fields = self.transform_config.get('input_fields', [])
        self.output_fields = self.transform_config.get('output_fields', [])
        self.output_layout = self.transform_config.get('output_layout', [])
        self.field_mappings = self.transform_config.get('field_mappings', {})
        self.transformations = self.transform_config.get('transformations', {})

        # Build lookup dict from output_fields for quick access
        self.output_fields_map = {field['name']: field for field in self.output_fields}

        # If no output_layout defined, derive from output_fields
        if not self.output_layout:
            self.output_layout = [field['name'] for field in self.output_fields]

        # Load lookups configuration and files
        self.lookups_config = self.transform_config.get('lookups', [])
        self.lookup_data = {}
        self._load_lookup_files()

        logger.info(f"Component {self.id}: Initialized transformer with {len(self.output_layout)} output fields ({len(self.output_fields)} with transformations, {len(self.lookups_config)} lookups)")

    def _load_lookup_files(self):
        """Load all lookup files into memory"""
        for lookup in self.lookups_config:
            lookup_name = lookup.get('name', '')
            lookup_file = lookup.get('file', '')
            
            if not lookup_file:
                logger.warning(f"Component {self.id}: Lookup {lookup_name} has no file specified")
                continue
            
            try:
                # Resolve path relative to project root
                if not os.path.isabs(lookup_file):
                    current_dir = os.path.dirname(__file__)
                    project_root = os.path.abspath(os.path.join(current_dir, '../../../../../'))
                    lookup_file = os.path.join(project_root, lookup_file)
                
                # Determine delimiter based on file extension
                if lookup_file.endswith('.csv'):
                    delimiter = ','
                else:
                    delimiter = '|'
                
                # Read lookup file
                lookup_df = pd.read_csv(lookup_file, delimiter=delimiter, dtype=str, keep_default_na=False)
                
                # Store lookup data with config
                self.lookup_data[lookup_name] = {
                    'data': lookup_df,
                    'config': lookup
                }
                
                logger.info(f"Component {self.id}: Loaded lookup {lookup_name} with {len(lookup_df)} rows from {lookup_file}")
                
            except Exception as e:
                logger.error(f"Component {self.id}: Error loading lookup file {lookup_file}: {str(e)}")

    def _apply_lookups(self, output_row: Dict[str, Any]) -> Dict[str, Any]:
        """Apply all lookups to the output row"""
        for lookup_name, lookup_info in self.lookup_data.items():
            try:
                config = lookup_info['config']
                lookup_df = lookup_info['data']
                
                main_key = config.get('main_key', '')
                lookup_key = config.get('lookup_key', '')
                columns = config.get('columns', [])
                match_type = config.get('match_type', 'normal')  # 'normal' or 'regex'
                
                # Get the value from output_row to match against
                main_value = str(output_row.get(main_key, '') or '')
                
                if not main_value or lookup_key not in lookup_df.columns:
                    continue
                
                matched_row = None
                
                if match_type == 'regex':
                    # Regex matching - lookup_key column contains regex patterns
                    for idx, row in lookup_df.iterrows():
                        pattern = str(row[lookup_key])
                        if pattern and re.search(pattern, main_value):
                            matched_row = row
                            break
                else:
                    # Normal exact matching
                    matches = lookup_df[lookup_df[lookup_key] == main_value]
                    if not matches.empty:
                        matched_row = matches.iloc[0]
                
                # If match found, copy columns to output_row
                if matched_row is not None:
                    for col in columns:
                        if col in matched_row.index:
                            output_row[col] = str(matched_row[col])
                            
            except Exception as e:
                logger.warning(f"Component {self.id}: Error applying lookup {lookup_name}: {str(e)}")
        
        return output_row

    def _load_external_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from external YAML or JSON file"""
        try:
            # Resolve context variables in the config path first
            resolved_config_path = self.context_manager.resolve_string(config_path)

            # Handle relative paths - make them relative to project root
            if not os.path.isabs(resolved_config_path):
                # Get project root (recdataprep directory)
                current_dir = os.path.dirname(__file__)
                project_root = os.path.abspath(os.path.join(current_dir, '../../../../../'))
                resolved_config_path = os.path.join(project_root, resolved_config_path)

            with open(resolved_config_path, 'r', encoding='utf-8') as file:
                if resolved_config_path.endswith('.yaml') or resolved_config_path.endswith('.yml'):
                    config = yaml.safe_load(file)
                else:
                    config = json.load(file)

            logger.info(f"Component {self.id}: Loaded external config from {resolved_config_path}")
            return config

        except Exception as e:
            logger.error(f"Component {self.id}: Error loading config {resolved_config_path if 'resolved_config_path' in locals() else config_path}: {str(e)}")
            raise ValueError(f"Failed to load transformation config: {str(e)}")

    def _get_default_transform_config(self) -> Dict[str, Any]:
        """Get default transformation configuration for SWIFT data"""
        return {
            "transformer": {
                "name": "SWIFT to Business Format",
                "version": "1.0"
            },
            "input_fields": [
                "message_type", "sender_bic", "receiver_bic", "transaction_ref",
                "account_number", "opening_balance", "closing_balance",
                "transaction_data", "transaction_details"
            ],
            "output_fields": [
                {
                    "name": "SIDE",
                    "type": "constant",
                    "value": "RECV",
                    "default": "RECV"
                },
                {
                    "name": "TERMID",
                    "type": "direct",
                    "source": "sender_bic",
                    "default": ""
                },
                {
                    "name": "DESTID",
                    "type": "direct",
                    "source": "receiver_bic",
                    "default": ""
                },
                {
                    "name": "OURREF",
                    "type": "direct",
                    "source": "transaction_ref",
                    "default": ""
                },
                {
                    "name": "THEIRREF",
                    "type": "direct",
                    "source": "transaction_ref",
                    "default": ""
                },
                {
                    "name": "SUBACC",
                    "type": "direct",
                    "source": "account_number",
                    "default": ""
                },
                {
                    "name": "CURRENCY",
                    "type": "transformation",
                    "source": "opening_balance",
                    "transform_config": {
                        "type": "balance_parse",
                        "extract": "currency"
                    },
                    "default": "USD"
                },
                {
                    "name": "AMOUNT",
                    "type": "transformation",
                    "source": "transaction_data",
                    "transform_config": {
                        "type": "movement_parse",
                        "extract": "amount"
                    },
                    "default": "0.00"
                },
                {
                    "name": "VALUEDATE",
                    "type": "transformation",
                    "source": "transaction_data",
                    "transform_config": {
                        "type": "movement_parse",
                        "extract": "value_date"
                    },
                    "default": ""
                }
            ]
        }

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Transform SWIFT pipe-delimited data to business format
        """
        try:
            # Validate input
            if input_data is None or input_data.empty:
                logger.warning(f"Component {self.id}: No input data provided")
                self._update_stats(0, 0, 0)
                return {'main': pd.DataFrame()}

            logger.info(f"Component {self.id}: Processing {len(input_data)} input rows")

            # Transform data
            transformed_df = self._transform_rows(input_data)

            # Write to output file if specified
            output_file = self.config.get('output_file')
            if output_file:
                self._write_output_file(transformed_df, output_file)

            # Update statistics
            self._update_stats(len(input_data), len(transformed_df), 0)

            logger.info(f"Component {self.id}: Transformed {len(input_data)} rows to {len(transformed_df)} rows")

            return {'main': transformed_df}

        except Exception as e:
            error_msg = f"Error transforming SWIFT data: {str(e)}"
            if self.config.get('die_on_error', True):
                raise RuntimeError(error_msg)
            else:
                logger.error(f"Component {self.id}: {error_msg}")
                self._update_stats(0, 0, 1)
            return {'main': pd.DataFrame()}

    def _transform_rows(self, input_df: pd.DataFrame) -> pd.DataFrame:
        """Transform input DataFrame to output format"""
        transformed_rows = []

        for index, row in input_df.iterrows():
            try:
                # Create working row with ALL fields (including intermediate ones)
                working_row = {}
                
                # First, compute ALL output_fields (including intermediate fields not in output_layout)
                # This allows intermediate fields like XSTRING17 to be computed and used for lookups
                for field_name, output_field in self.output_fields_map.items():
                    field_value = self._get_field_value(output_field, row)
                    working_row[field_name] = field_value
                
                # Apply lookups to enrich using ALL computed fields (including intermediate)
                if self.lookup_data:
                    working_row = self._apply_lookups(working_row)
                
                # Now build final output row with only fields from output_layout
                output_row = {}
                for field_name in self.output_layout:
                    if field_name in working_row:
                        output_row[field_name] = working_row[field_name]
                    else:
                        # Field not computed - output empty string
                        output_row[field_name] = ''

                transformed_rows.append(output_row)

            except Exception as e:
                logger.error(f"Component {self.id}: Error transforming row {index}: {str(e)}")
                # Add empty row to maintain row count or skip based on configuration
                if self.config.get('skip_error_rows', False):
                    continue
                else:
                    empty_row = {field_name: '' for field_name in self.output_layout}
                    transformed_rows.append(empty_row)

        # Ensure column order matches output_layout
        return pd.DataFrame(transformed_rows, columns=self.output_layout)

    def _get_field_value(self, output_field: Dict[str, Any], input_row: pd.Series) -> str:
        """Get value for an output field based on mapping configuration"""
        field_name = output_field['name']
        mapping_type = output_field.get('type', 'direct')
        source = output_field.get('source', '')
        default_value = output_field.get('default', '')

        try:
            if mapping_type == 'direct':
                # Direct mapping from input field
                if source in input_row and pd.notna(input_row[source]):
                    value = str(input_row[source]).strip()
                    # Convert 'nan' string to empty
                    if value.lower() == 'nan':
                        value = default_value
                else:
                    value = default_value

            elif mapping_type == 'constant':
                # Constant value
                value = output_field.get('value', default_value)

            elif mapping_type == 'parsed':
                # Parse from specific input field
                value = self._parse_field_value(output_field, input_row)

            elif mapping_type == 'calculated':
                # Calculated value
                value = self._calculate_field_value(output_field, input_row)

            elif mapping_type == 'transformation':
                # Apply transformation
                if source in input_row and pd.notna(input_row[source]):
                    source_value = str(input_row[source]).strip()
                    # Convert 'nan' string to empty
                    if source_value.lower() == 'nan':
                        source_value = ''
                else:
                    source_value = ''
                value = self._apply_field_transformation(output_field, source_value, input_row)

            elif mapping_type == 'python_expression':
                # Evaluate Python expression
                value = self._evaluate_python_expression(output_field, input_row)

            elif mapping_type == 'placeholder':
                # Placeholder field - not yet implemented, return default/empty
                value = default_value

            else:
                value = default_value

            # Apply post-processing if defined
            if 'post_process' in output_field:
                value = self._post_process_value(value, output_field['post_process'])

            # Ensure we never return None or NaN
            if value is None or (isinstance(value, str) and value.lower() == 'nan'):
                value = default_value

            return str(value) if value is not None else default_value

        except Exception as e:
            logger.warning(f"Component {self.id}: Error processing field {field_name}: {str(e)}")
            return default_value

    def _parse_field_value(self, output_field: Dict[str, Any], input_row: pd.Series) -> str:
        """Parse specific value from input field using regex or position"""
        source = output_field.get('source', '')
        parse_config = output_field.get('parse_config', {})
        default_value = output_field.get('default', '')

        if source not in input_row or pd.isna(input_row[source]):
            return default_value

        source_value = str(input_row[source])

        # Parse using regex
        if 'regex' in parse_config:
            pattern = parse_config['regex']
            group = parse_config.get('group', 1)
            match = re.search(pattern, source_value)
            if match:
                return match.group(group)

        # Parse using position
        elif 'position' in parse_config:
            start = parse_config['position'].get('start', 0)
            end = parse_config['position'].get('end', len(source_value))
            return source_value[start:end]

        # Parse using split
        elif 'split' in parse_config:
            delimiter = parse_config['split'].get('delimiter', ' ')
            index = parse_config['split'].get('index', 0)
            parts = source_value.split(delimiter)
            if 0 <= index < len(parts):
                return parts[index]

        return default_value

    def _calculate_field_value(self, output_field: Dict[str, Any], input_row: pd.Series) -> str:
        """Calculate field value using formula or logic"""
        calc_config = output_field.get('calc_config', {})
        calc_type = calc_config.get('type', '')

        if calc_type == 'concatenate':
            # Concatenate multiple fields
            fields = calc_config.get('fields', [])
            separator = calc_config.get('separator', '')
            values = []
            for field in fields:
                if field in input_row and pd.notna(input_row[field]):
                    values.append(str(input_row[field]))
            return separator.join(values)

        elif calc_type == 'conditional':
            # Conditional logic
            condition_field = calc_config.get('condition_field', '')
            condition_value = calc_config.get('condition_value', '')
            true_value = calc_config.get('true_value', '')
            false_value = calc_config.get('false_value', '')

            if condition_field in input_row:
                field_value = str(input_row[condition_field])
                return true_value if field_value == condition_value else false_value

        elif calc_type == 'date_extraction':
            # Extract date components
            source_field = calc_config.get('source_field', '')
            component = calc_config.get('component', 'date')  # date, time, year, month, day

            if source_field in input_row and pd.notna(input_row[source_field]):
                return self._extract_date_component(str(input_row[source_field]), component)

        return output_field.get('default', '')

    def _evaluate_python_expression(self, output_field: Dict[str, Any], input_row: pd.Series) -> str:
        """Evaluate a Python expression to compute field value"""
        expression = output_field.get('python_expression', '')
        default_value = output_field.get('default', '')
        field_name = output_field.get('name', 'unknown')

        if not expression:
            return default_value

        try:
            # Convert Series to dict for easier access in expressions
            row_dict = input_row.to_dict()

            # Create a safe evaluation context
            eval_context = {
                'input_row': row_dict,
                're': re,
                'datetime': datetime,
                'str': str,
                'int': int,
                'float': float,
                'len': len,
                'bool': bool,
                'list': list,
                'dict': dict,
                'min': min,
                'max': max,
                'abs': abs,
                'round': round,
                'sum': sum,
                'any': any,
                'all': all,
                '__builtins__': {
                    '__import__': __import__,
                    'str': str,
                    'int': int,
                    'float': float,
                    'len': len,
                    'bool': bool,
                    'list': list,
                    'dict': dict,
                    'min': min,
                    'max': max,
                    'abs': abs,
                    'round': round,
                    'sum': sum,
                    'any': any,
                    'all': all,
                }
            }

            # Evaluate the expression
            result = eval(expression, eval_context)

            # Convert result to string
            if result is None:
                return default_value
            return str(result)

        except Exception as e:
            logger.warning(f"Component {self.id}: Error evaluating python_expression for field {field_name}: {str(e)}")
            return default_value

    def _extract_date_component(self, date_value: str, component: str) -> str:
        """Extract specific component from date value"""
        try:
            # Try different date formats
            date_formats = ['%Y%m%d', '%d%m%y', '%y%m%d', '%Y-%m-%d', '%d-%m-%Y']

            parsed_date = None
            for fmt in date_formats:
                try:
                    if len(date_value) >= 6:
                        if fmt == '%Y%m%d' and len(date_value) >= 8:
                            parsed_date = datetime.strptime(date_value[:8], fmt)
                        elif fmt == '%y%m%d' and len(date_value) >= 6:
                            parsed_date = datetime.strptime(date_value[:6], fmt)
                        else:
                            parsed_date = datetime.strptime(date_value, fmt)
                        break
                except ValueError:
                    continue

            if parsed_date:
                if component == 'year':
                    return str(parsed_date.year)
                elif component == 'month':
                    return str(parsed_date.month).zfill(2)
                elif component == 'day':
                    return str(parsed_date.day).zfill(2)
                elif component == 'date':
                    return parsed_date.strftime('%Y-%m-%d')
                elif component == 'time':
                    return parsed_date.strftime('%H:%M:%S')

        except Exception:
            pass

        return date_value

    def _apply_field_transformation(self, output_field: Dict[str, Any], source_value: str, input_row: pd.Series) -> str:
        """Apply field-specific transformation"""
        transform_config = output_field.get('transform_config', {})
        transform_type = transform_config.get('type', '')

        if transform_type == 'balance_parse':
            # Parse SWIFT balance format: C/D + Date + Currency + Amount
            return self._parse_balance_field(source_value, transform_config)

        elif transform_type == 'movement_parse':
            # Parse SWIFT movement entry (field 61)
            return self._parse_movement_field(source_value, transform_config, input_row)

        elif transform_type == 'lookup':
            # Value lookup/mapping
            lookup_table = transform_config.get('lookup_table', {})
            return lookup_table.get(source_value, transform_config.get('default', source_value))

        elif transform_type == 'format':
            # String formatting
            format_type = transform_config.get('format_type', 'upper')
            if format_type == 'upper':
                return source_value.upper()
            elif format_type == 'lower':
                return source_value.lower()
            elif format_type == 'trim':
                return source_value.strip()
        return source_value

    def _parse_balance_field(self, balance_value: str, config: Dict[str, Any]) -> str:
        """Parse SWIFT balance field and extract specific component"""
        extract_component = config.get('extract', 'amount')

        if not balance_value:
            return ''

        # SWIFT balance format: C/D + YYMMDD + Currency + Amount
        pattern = r'^([CD])(\d{6})([A-Z]{3})([\d,\.]+)'
        match = re.match(pattern, balance_value.strip())

        if match:
            sign = match.group(1)
            date = match.group(2)
            currency = match.group(3)
            amount = match.group(4).replace(',', '')

            if extract_component == 'sign':
                return 'C' if sign == 'C' else 'D'
            elif extract_component == 'date':
                return date
            elif extract_component == 'currency':
                return currency
            elif extract_component == 'amount':
                return amount
            elif extract_component == 'full_text':
                return f"{sign} {date} {currency} {amount}"

        return balance_value

    def _parse_movement_field(self, movement_value: str, config: Dict[str, Any], input_row: pd.Series) -> str:
        """Parse SWIFT movement entry (field 61) and extract specific component"""
        extract_component = config.get('extract', 'amount')

        if not movement_value:
            return ''

        # MT940 field 61 format: YYMMDD[MMDD][D/C]amount[transaction_code][reference][//supplementary]
        pattern = r'^(\d{6})(\d{4})?([DC])(\d+[.,]?\d*)([A-Z]?)([^/]*)?(//(.*))?'
        match = re.match(pattern, movement_value.strip())

        if match:
            entry_date = match.group(1)
            value_date = match.group(2) if match.group(2) else entry_date
            debit_credit = match.group(3)
            amount = match.group(4).replace(',', '')
            transaction_code = match.group(5) if match.group(5) else ''
            reference = match.group(6).strip() if match.group(6) else ''
            narrative = match.group(8) if match.group(8) else ''

            if extract_component == 'entry_date':
                return entry_date
            elif extract_component == 'value_date':
                return value_date
            elif extract_component == 'debit_credit':
                return debit_credit
            elif extract_component == 'amount':
                return amount
            elif extract_component == 'transaction_code':
                return transaction_code
            elif extract_component == 'reference':
                return reference
            elif extract_component == 'narrative':
                return narrative

        return movement_value

    def _post_process_value(self, value: str, post_process_config: Dict[str, Any]) -> str:
        """Apply post-processing to field value"""
        process_type = post_process_config.get('type', '')

        if process_type == 'truncate':
            max_length = post_process_config.get('max_length', 100)
            return value[:max_length]

        elif process_type == 'pad':
            length = post_process_config.get('length', 10)
            pad_char = post_process_config.get('pad_char', ' ')
            side = post_process_config.get('side', 'right')

            if side == 'left':
                return value.ljust(length, pad_char)
            else:
                return value.rjust(length, pad_char)

        elif process_type == 'replace':
            old_value = post_process_config.get('old', '')
            new_value = post_process_config.get('new', '')
            return value.replace(old_value, new_value)

        return value

    def _write_output_file(self, output_df: pd.DataFrame, file_path: str):
        """Write transformed data to output file"""
        try:
            delimiter = self.config.get('delimiter', '|')
            encoding = self.config.get('output_encoding', 'utf-8')
            include_header = self.config.get('include_header', True)

            # Create output directory if it doesn't exist
            output_dir = os.path.dirname(file_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            # Clean DataFrame - replace all NaN values with empty strings
            output_df = output_df.fillna('')

            # Also replace any 'nan' string values with empty strings
            output_df = output_df.replace('nan', '', regex=False)
            output_df = output_df.replace('NaN', '', regex=False)
            output_df = output_df.replace('None', '', regex=False)

            # Write to file
            output_df.to_csv(file_path, sep=delimiter, encoding=encoding,
                            index=False, header=include_header, na_rep='')

            logger.info(f"Component {self.id}: Output written to {file_path}")

        except Exception as e:
            logger.error(f"Component {self.id}: Error writing output file: {str(e)}")
            raise

                
