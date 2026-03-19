"""
TSwiftBlockFormatter component - Parse SWIFT messages and output pipe-delimited format
Integrates swift_block_formatter.py functionality into ETL engine
"""

import pandas as pd
import os
import re
import logging
import yaml
from typing import Dict, Any, Optional, List
from datetime import datetime
from collections import defaultdict

from ...base_component import BaseComponent

logger = logging.getLogger(__name__)


class SwiftBlockFormatter(BaseComponent):
    """
    Parse SWIFT messages and convert to pipe-delimited output format.
    Equivalent to a specialized tFileInputDelimited for SWIFT messages.
    """

    def __init__(self, comp_id: str, config: Dict[str, Any], global_map: Any, context_manager: Any):
        """Initialize the SWIFT Block Formatter component"""
        super().__init__(comp_id, config, global_map, context_manager)

        # Initialize SWIFT parser components
        self._init_swift_parser()

    def _init_swift_parser(self):
        """Initialize SWIFT parsing configuration - defer layout loading until execution"""
        # Store layout file path for later resolution during execution
        self.layout_file = self.config.get('layout_file')
        self.layout_spec = None  # Will be loaded during execution

        # Check if we have inline layout configuration as fallback
        self.inline_layout = self.config.get('layout', {})

        if not self.layout_file and not self.inline_layout:
            raise ValueError(f"Component {self.id}: 'layout_file' or 'layout' configuration is required")

        # Get pipe fields configuration (REQUIRED)
        pipe_fields_config = self.config.get('pipe_fields', [])
        if not pipe_fields_config:
            raise ValueError(f"Component {self.id}: 'pipe_fields' configuration is required")

        # Extract field names from pipe_fields configuration
        # pipe_fields can be either:
        # 1. List of strings (field names)
        # 2. List of dictionaries with 'name', 'source', 'default' keys
        self.pipe_fields = []
        self.pipe_fields_mapping = {}  # Store source mapping for later use

        for field in pipe_fields_config:
            if isinstance(field, str):
                # Simple string field name
                self.pipe_fields.append(field)
                self.pipe_fields_mapping[field] = {"source": field, "default": ""}
            elif isinstance(field, dict) and 'name' in field:
                # Dictionary configuration with name, source, default
                field_name = field['name']
                self.pipe_fields.append(field_name)
                self.pipe_fields_mapping[field_name] = {
                    "source": field.get('source', field_name),
                    "default": field.get('default', "")
                }
            else:
                logger.warning(f"Component {self.id}: Invalid pipe_field configuration: {field}")

        if not self.pipe_fields:
            raise ValueError(f"Component {self.id}: No valid pipe_fields found in configuration")

        # Processing options
        self.processing_options = self.config.get('processing', {})

        logger.info(f"Component {self.id}: Initialized SWIFT parser with {len(self.pipe_fields)} output fields")

    def _ensure_layout_loaded(self):
        """Ensure layout is loaded at execution time when context is available"""
        if self.layout_spec is None:
            if self.layout_file:
                # Resolve context variables in the layout file path now
                resolved_layout_file = self.context_manager.resolve_string(self.layout_file)
                self.layout_spec = self._load_layout_from_file(resolved_layout_file)
            else:
                # Use inline layout configuration
                self.layout_spec = self.inline_layout

            if not self.layout_spec:
                raise ValueError(f"Component {self.id}: No valid layout configuration available")

    def _load_layout_from_file(self, layout_file_path: str) -> Dict[str, str]:
        """Load SWIFT layout configuration from YAML file"""
        try:
            # Use the resolved path directly (context variables provide complete
            # absolute paths)
            resolved_path = os.path.normpath(layout_file_path)

            # Check if file exists
            if not os.path.exists(resolved_path):
                raise FileNotFoundError(f"Layout configuration file not found: {resolved_path}")

            # Load YAML configuration
            with open(resolved_path, 'r', encoding='utf-8') as file:
                yaml_config = yaml.safe_load(file)

            # Extract block4_layout from the YAML structure
            layout_config = yaml_config.get('swift_layout', {}).get('block4_layout', {})

            if not layout_config:
                raise ValueError(f"No 'swift_layout.block4_layout' found in {resolved_path}")

            # Validate and clean layout configuration - ONLY allow string values
            cleaned_layout = {}
            for key, value in layout_config.items():
                if isinstance(value, dict):
                    logger.warning(f"Component {self.id}: Skipping layout config {key} - contains dict: {value}")
                    continue
                elif not isinstance(value, str):
                    logger.warning(f"Component {self.id}: Converting layout config {key} from {type(value)} to string: {value}")
                    cleaned_layout[key] = str(value)
                else:
                    # Valid string value
                    cleaned_layout[key] = value

            if not cleaned_layout:
                raise ValueError(f"No valid layout configuration found in {resolved_path}")

            logger.info(f"Component {self.id}: Loaded layout configuration from {resolved_path}")
            logger.debug(f"Component {self.id}: Validated layout config: {cleaned_layout}")
            return cleaned_layout

        except Exception as e:
            logger.error(f"Component {self.id}: Error loading layout file {layout_file_path}: {str(e)}")
            raise ValueError(f"Failed to load layout configuration: {str(e)}")

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Process SWIFT messages and return pipe-delimited DataFrame
        """
        try:
            # Ensure layout is loaded now that context variables are available
            self._ensure_layout_loaded()

            # Enable debug logging for this component
            logger.setLevel(logging.DEBUG)

            # Determine input source
            if input_data is not None:
                # Input from previous component (DataFrame with SWIFT message content)
                swift_messages = self._parse_dataframe_input(input_data)
            else:
                # Input from file
                input_file = self.config.get('input_file', '')
                if not input_file:
                    raise ValueError(f"Component {self.id}: input_file is required when no input data provided")
                swift_messages = self._parse_swift_file(input_file)

            if not swift_messages:
                logger.warning(f"Component {self.id}: No SWIFT messages found to process")
                self._update_stats(0, 0, 0)
                return {'main': pd.DataFrame()}

            # Convert to pipe-delimited DataFrame
            result_df = self._convert_to_dataframe(swift_messages)

            # Write to output file if specified
            output_file = self.config.get('output_file', '')
            if output_file:
                self._write_output_file(result_df, output_file)

            # Update statistics
            self._update_stats(len(swift_messages), len(result_df), 0)

            logger.info(f"Component {self.id}: Processed {len(swift_messages)} SWIFT messages into {len(result_df)} rows")

            return {'main': result_df}

        except Exception as e:
            error_msg = f"Error processing SWIFT messages: {str(e)}"
            if self.config.get('die_on_error', True):
                raise RuntimeError(error_msg)
            else:
                logger.error(f"Component {self.id}: {error_msg}")
                self._update_stats(0, 0, 1)
                return {'main': pd.DataFrame()}

    def _parse_dataframe_input(self, input_data: pd.DataFrame) -> List[Dict[str, Any]]:
        """Parse SWIFT messages from DataFrame input"""
        swift_messages = []

        # Assume DataFrame has a column containing SWIFT message content
        content_column = self.config.get('content_column', 'content')

        if content_column not in input_data.columns:
            # Try to find a column with SWIFT-like content
            for col in input_data.columns:
                sample_value = str(input_data[col].iloc[0]) if len(input_data) > 0 else ""
                if '{' in sample_value and ':' in sample_value:
                    content_column = col
                    break
            else:
                raise ValueError(f"No SWIFT content column found. Specify 'content_column' in config or ensure DataFrame has column named 'content'")

        # Parse each row as a SWIFT message
        for idx, row in input_data.iterrows():
            message_content = str(row[content_column])
            if message_content and message_content.strip():
                parsed_msg = self._parse_single_message(message_content)
                if parsed_msg:
                    swift_messages.append(parsed_msg)

        return swift_messages

    def _parse_swift_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Parse SWIFT message file into structured data"""
        try:
            encoding = self.config.get('encoding', 'UTF-8')

            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Input file not found: {file_path}")

            with open(file_path, 'r', encoding=encoding) as file:
                content = file.read()

            # Split into individual messages
            messages = self._split_messages(content)

            # Parse each message
            parsed_messages = []
            for message in messages:
                parsed_msg = self._parse_single_message(message)
                if parsed_msg:
                    parsed_messages.append(parsed_msg)

            return parsed_messages

        except Exception as e:
            logger.error(f"Component {self.id}: Error parsing SWIFT file {file_path}: {str(e)}")
            raise

    def _split_messages(self, content: str) -> List[str]:
        """Split file content into individual SWIFT messages"""
        content = content.strip().replace('\r\n', '\n').replace('\r', '\n')
        messages = []

        # Pattern to find message boundaries
        message_pattern = r'(\{1:[^}]*\}.*?)(?=\{1:|$)'
        matches = re.findall(message_pattern, content, re.DOTALL)

        if matches:
            messages = matches
        else:
            # Fallback: split by empty lines
            potential_messages = content.split('\n\n')
            for msg in potential_messages:
                if msg.strip() and '{' in msg:
                    messages.append(msg.strip())

        return [msg.strip() for msg in messages if msg.strip()]

    def _parse_single_message(self, message: str) -> Optional[Dict[str, Any]]:
        """Parse a single SWIFT message into structured data"""
        try:
            parsed_data = {}

            # Extract message type from block2 only
            block2_pattern = r'\{2:[IO](\d{3})'
            block2_match = re.search(block2_pattern, message)
            if block2_match:
                parsed_data['messagetype'] = block2_match.group(1)  # Just the numeric part

            # Parse all blocks
            parsed_data.update(self._parse_block1(message))
            parsed_data.update(self._parse_block2(message))
            parsed_data.update(self._parse_block3(message))
            parsed_data.update(self._parse_block4_with_layout(message))
            parsed_data.update(self._parse_block5(message))

            return parsed_data

        except Exception as e:
            logger.error(f"Component {self.id}: Error parsing SWIFT message: {str(e)}")
            return None

    def _parse_block1(self, message: str) -> Dict[str, Any]:
        """Parse Block 1 - Basic Header Block"""
        block1_data = {}

        block1_pattern = r'\{1:([^}]*)\}'
        match = re.search(block1_pattern, message)

        if match:
            block1_content = match.group(1)

            if len(block1_content) >= 11:
                block1_data['block1_app_id'] = block1_content[0:1] if len(block1_content) > 0 else ''
                block1_data['block1_service_id'] = block1_content[1:3] if len(block1_content) > 2 else ''
                block1_data['block1bic'] = block1_content[3:15] if len(block1_content) > 14 else block1_content[3:]
                block1_data['block1_session'] = block1_content[15:19] if len(block1_content) > 18 else ''
                block1_data['block1_sequence'] = block1_content[19:25] if len(block1_content) > 24 else ''

        return block1_data

    def _parse_block2(self, message: str) -> Dict[str, Any]:
        """Parse Block 2 - Application Header Block"""
        block2_data = {}

        block2_pattern = r'\{2:([^}]*)\}'
        match = re.search(block2_pattern, message)

        if match:
            block2_content = match.group(1)

            if block2_content.startswith('I'):  # Input message
                block2_data['block2_direction'] = 'I'
                block2_data['block2_msg_type'] = block2_content[1:4] if len(block2_content) > 3 else ''
                block2_data['block2bic'] = block2_content[4:16] if len(block2_content) > 15 else block2_content[4:]
            elif block2_content.startswith('O'):  # Output message
                block2_data['block2_direction'] = 'O'
                block2_data['block2_msg_type'] = block2_content[1:4] if len(block2_content) > 3 else ''
                block2_data['block2_time'] = block2_content[4:10] if len(block2_content) > 9 else ''
                block2_data['block2_mir'] = block2_content[10:22] if len(block2_content) > 21 else ''
                block2_data['block2bic'] = block2_content[14:26] if len(block2_content) > 25 else block2_content[16:]

        return block2_data

    def _parse_block3(self, message: str) -> Dict[str, Any]:
        """Parse Block 3 - User Header Block"""
        block3_data = {}

        block3_pattern = r'\{3:([^}]*)\}'
        match = re.search(block3_pattern, message)

        if match:
            block3_content = match.group(1)
            block3_data['block3_content'] = block3_content

        return block3_data

    def _parse_block4_with_layout(self, message: str) -> Dict[str, Any]:
        """Parse Block 4 with layout specification and handle block 61/86 pairs"""
        block4_data = {}

        block4_pattern = r'\{4:(.*?)-\}'
        match = re.search(block4_pattern, message, re.DOTALL)

        if match:
            block4_content = match.group(1).strip()

            # Parse field tags with multiple occurrence handling
            # Split block4 content into lines and process sequentially
            lines = block4_content.split('\n')
            all_fields = []

            current_field = None
            current_value = []

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Check if line starts with a field tag (e.g., :20:, :61:, :86:)
                field_match = re.match(r':(\d{2}[A-Z]?):(.*)', line)

                if field_match:
                    # Save previous field if exists
                    if current_field:
                        field_tag = current_field
                        field_value = '\n'.join(current_value).strip()

                        # Handle special formatting
                        if field_tag == '61':
                            field_value = field_value.replace('\n', 'sfield9=')
                        else:
                            field_value = field_value.replace('\n', ' ')

                        field_key = f'block4_{field_tag}'

                        # Only process fields that are defined in layout
                        if field_key in self.layout_spec:
                            all_fields.append({
                                'tag': field_tag,
                                'key': field_key,
                                'value': field_value,
                                'position': len(all_fields)
                            })

                    # Start new field
                    current_field = field_match.group(1)
                    current_value = [field_match.group(2)]
                else:
                    # Continuation of current field
                    if current_field:
                        current_value.append(line)

            # Don't forget the last field
            if current_field:
                field_tag = current_field
                field_value = '\n'.join(current_value).strip()

                # Handle special formatting
                if field_tag == '61':
                    field_value = field_value.replace('\n', 'sfield9=')
                else:
                    field_value = field_value.replace('\n', ' ')

                field_key = f'block4_{field_tag}'

                # Only process fields that are defined in layout
                if field_key in self.layout_spec:
                    all_fields.append({
                        'tag': field_tag,
                        'key': field_key,
                        'value': field_value,
                        'position': len(all_fields)
                    })

            # Handle block 61 and 86 pairing
            block61_list = []
            block86_list = []
            field_occurrences = {}

            i = 0
            while i < len(all_fields):
                field = all_fields[i]
                field_tag = field['tag']
                field_key = field['key']
                field_value = field['value']

                # Get layout specification (we know it exists since we filtered above)
                layout_type = self.layout_spec[field_key]

                if field_tag == '61':
                    # This is a block 61, look for corresponding block 86
                    block61_list.append(field_value)

                    # Check if next field is block 86
                    if i + 1 < len(all_fields) and all_fields[i + 1]['tag'] == '86':
                        # Found corresponding block 86
                        block86_list.append(all_fields[i + 1]['value'])
                        i += 2  # Skip both 61 and 86
                    else:
                        # No corresponding block 86, add empty
                        block86_list.append('')
                        i += 1  # Move to next field

                elif field_tag == '86' and not block61_list:
                    # Standalone block 86 (not paired with 61)
                    if layout_type == 'M':
                        if field_key not in field_occurrences:
                            field_occurrences[field_key] = []
                        field_occurrences[field_key].append(field_value)
                    else:
                        if field_key not in block4_data:
                            block4_data[field_key] = field_value
                    i += 1

                elif field_tag == '86':
                    # This 86 should have been handled with its 61 pair, skip it
                    i += 1

                else:
                    # Regular field processing
                    if layout_type == 'M':
                        # Multiple occurrence field
                        if field_key not in field_occurrences:
                            field_occurrences[field_key] = []
                        field_occurrences[field_key].append(field_value)
                    else:
                        # Single occurrence field
                        if field_key not in block4_data:
                            block4_data[field_key] = field_value
                        # Take the first occurrence silently
                    i += 1

            # Store the paired 61 and 86 blocks
            if block61_list:
                block4_data['block4_61'] = block61_list if len(block61_list) > 1 else block61_list[0]

            if block86_list:
                # Remove empty trailing 86 blocks
                while block86_list and block86_list[-1] == '':
                    block86_list.pop()

                if block86_list:
                    block4_data['block4_86'] = block86_list if len(block86_list) > 1 else block86_list[0]

            # Store other multiple occurrence fields
            for field_key, values in field_occurrences.items():
                if isinstance(values, list):
                    # Check if any values are dicts
                    for i, val in enumerate(values):
                        if isinstance(val, dict):
                            logger.error(f"Component {self.id}: Found dict in field_occurrences[{field_key}][{i}]: {val}")
                            values[i] = str(val)  # Convert to string
                    block4_data[field_key] = values if len(values) > 1 else values[0] if values else ''
                else:
                    if isinstance(values, dict):
                        logger.error(f"Component {self.id}: Found dict in field_occurrences[{field_key}]: {values}")
                        block4_data[field_key] = str(values)
                    else:
                        block4_data[field_key] = values

            # Final validation: ensure no dict values in block4_data
            for key, value in block4_data.items():
                if isinstance(value, dict):
                    logger.error(f"Component {self.id}: Found dict in final block4_data[{key}]: {value}")
                    block4_data[key] = str(value)
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            logger.error(f"Component {self.id}: Found dict in final block4_data[{key}][{i}]: {item}")
                            value[i] = str(item)

        return block4_data

    def _parse_block5(self, message: str) -> Dict[str, Any]:
        """Parse Block 5 - Trailer Block"""
        block5_data = {}

        block5_pattern = r'\{5:([^}]*)\}'
        match = re.search(block5_pattern, message)

        if match:
            block5_content = match.group(1)
            block5_data['block5_content'] = block5_content

        return block5_data

    def _convert_to_dataframe(self, swift_messages: List[Dict[str, Any]]) -> pd.DataFrame:
        """Convert parsed SWIFT messages to pipe-delimited DataFrame"""
        all_rows = []

        logger.debug(f"Component {self.id}: Converting {len(swift_messages)} SWIFT messages to DataFrame")

        for idx, message in enumerate(swift_messages):
            #logger.debug(f"Component {self.id}: Processing message {idx}, keys: {list(message.keys())}")

            # Check for any dict values in the message
            for key, value in message.items():
                if isinstance(value, dict):
                    logger.warning(f"Component {self.id}: Found dict in message[{key}]: {value}")
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            logger.warning(f"Component {self.id}: Found dict in message[{key}][{i}]: {item}")

            normalized_rows = self._normalize_message_data(message)
            #logger.debug(f"Component {self.id}: Message {idx} normalized to {len(normalized_rows)} rows")
            all_rows.extend(normalized_rows)

        # Create DataFrame
        if all_rows:
            # Debug: Check for any dict values in all_rows
            logger.debug(f"Component {self.id}: Creating DataFrame with {len(all_rows)} rows")

            for row_idx, row in enumerate(all_rows):
                if not isinstance(row, list):
                    logger.error(f"Component {self.id}: Row {row_idx} is not a list: {type(row)} = {row}")
                else:
                    for col_idx, item in enumerate(row):
                        if isinstance(item, dict):
                            logger.error(f"Component {self.id}: Found dict at row {row_idx}, col {col_idx}: {item}")
                        elif item is not None and not isinstance(item, (str, int, float, bool)):
                            logger.warning(f"Component {self.id}: Unexpected type at row {row_idx}, col {col_idx}: {type(item)} = {item}")

            # Validate that all rows contain only strings (not dicts or other unhashable types)
            validated_rows = []
            for row_idx, row in enumerate(all_rows):
                if isinstance(row, list):
                    # Ensure all elements in the row are strings
                    validated_row = []
                    for col_idx, item in enumerate(row):
                        if isinstance(item, dict):
                            str_val = str(item)
                            logger.info(f"Component {self.id}: Converting dict at row {row_idx}, col {col_idx} to string: {str_val}")
                            validated_row.append(str_val)
                        elif isinstance(item, list):
                            str_val = str(item)
                            logger.info(f"Component {self.id}: Converting list at row {row_idx}, col {col_idx} to string: {str_val}")
                            validated_row.append(str_val)
                        else:
                            validated_row.append(str(item) if item is not None else '')
                    validated_rows.append(validated_row)
                else:
                    logger.warning(f"Component {self.id}: Expected list but got {type(row)} at row {row_idx}, converting to string")
                    validated_rows.append([str(row)])

            try:
                # pipe_fields is a list of field names (strings)
                df = pd.DataFrame(validated_rows, columns=self.pipe_fields)
                logger.debug(f"Component {self.id}: Successfully created DataFrame with shape {df.shape}")
            except Exception as e:
                logger.error(f"Component {self.id}: Failed to create DataFrame: {e}")
                logger.error(f"Component {self.id}: validated_rows sample: {validated_rows[:2] if validated_rows else 'empty'}")
                logger.error(f"Component {self.id}: pipe_fields: {self.pipe_fields}")
                raise

            # Apply data type conversions based on output schema if available
            if hasattr(self, 'output_schema') and self.output_schema:
                df = self.validate_schema(df, self.output_schema)
        else:
            # Empty DataFrame with correct columns
            df = pd.DataFrame(columns=self.pipe_fields)

        return df

    def _normalize_message_data(self, message_data: Dict[str, Any]) -> List[List[str]]:
        """Normalize message data based on multiple occurrences with proper 61/86 pairing"""
        # Get all occurrences of block4_61 (the normalizing field)
        block4_61_data = message_data.get('block4_61', [])

        # Convert to list if single string
        if isinstance(block4_61_data, str):
            block4_61_data = [block4_61_data]
        elif not isinstance(block4_61_data, list):
            block4_61_data = []

        # If no block4_61 data, create one row
        if not block4_61_data:
            block4_61_data = ['']

        # Get paired block4_86 data
        block4_86_data = message_data.get('block4_86', [])
        if isinstance(block4_86_data, str):
            block4_86_data = [block4_86_data]
        elif not isinstance(block4_86_data, list):
            block4_86_data = []

        # Ensure same number of 86 entries as 61 entries
        while len(block4_86_data) < len(block4_61_data):
            block4_86_data.append('')

        normalized_rows = []

        # Create one row for each occurrence of block4_61
        for i, block61_value in enumerate(block4_61_data):
            row = []

            # pipe_fields is a list of field names (strings)
            for field_name in self.pipe_fields:
                # Get the source field mapping
                source_field = self.pipe_fields_mapping[field_name]['source']
                default_value = self.pipe_fields_mapping[field_name]['default']

                if source_field == 'block4_61':
                    # Use current block4_61 value
                    row.append(str(block61_value))
                elif source_field == 'block4_86':
                    # Use corresponding paired block4_86 value
                    if i < len(block4_86_data):
                        row.append(str(block4_86_data[i]))
                    else:
                        row.append(default_value)
                else:
                    # For single occurrence fields, repeat same value
                    value = message_data.get(source_field, default_value)

                    # Handle different value types safely to prevent unhashable dict errors
                    if isinstance(value, dict):
                        # Convert dict to string representation
                        value = str(value)
                    elif isinstance(value, list) and value:
                        # If it's a list, take first value and handle its type
                        first_value = value[0]
                        if isinstance(first_value, dict):
                            value = str(first_value)
                        else:
                            value = str(first_value)
                    elif isinstance(value, list):
                        # Empty list
                        value = ''
                    else:
                        # Convert to string
                        value = str(value) if value is not None else ''

                    row.append(value)

            normalized_rows.append(row)

        return normalized_rows

    def _write_output_file(self, df: pd.DataFrame, output_file: str):
        """Write DataFrame to pipe-delimited output file"""
        try:
            delimiter = self.config.get('delimiter', '|')
            encoding = self.config.get('output_encoding', 'UTF-8')
            include_header = self.config.get('include_header', True)

            df.to_csv(
                output_file,
                sep=delimiter,
                encoding=encoding,
                index=False,
                header=include_header
            )

            logger.info(f"Component {self.id}: Output written to {output_file}")

        except Exception as e:
            logger.error(f"Component {self.id}: Error writing output file: {str(e)}")
            raise
