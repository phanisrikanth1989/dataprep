"""
FileInputJSON - Reads and processes JSON files with JSONPath support.

Talend equivalent: tFileInputJSON

This component reads JSON files and extracts data using JSONPath expressions.
Supports URL reading, data type conversion, and reject handling for malformed data.
Enhanced for Talend compatibility with advanced separator handling and date parsing.
"""
import json
import logging
import os
import re
import codecs
from typing import Dict, Any, List
from urllib.request import urlopen
from datetime import datetime

import pandas as pd

from ...base_component import BaseComponent

logger = logging.getLogger(__name__)


class FileInputJSON(BaseComponent):
    """
    Reads and processes JSON files using JSONPath expressions for data extraction.

    This component implements the functionality of Talend's tFileInputJSON component,
    providing comprehensive JSON file processing with advanced features like URL reading,
    data type conversion, reject handling, and schema validation.

    Configuration:
        filename (str): Path to the JSON file to read. Required unless using URL.
        json_loop_query (str): JSONPath expression for iterating over JSON elements. Required.
        mapping (List[Dict]): Column to JSONPath mappings for data extraction. Required.
            Format: [{"column": "col_name", "jsonpath": "$.path"}, ...]
        encoding (str): File encoding for reading JSON file. Default: "UTF-8"
        die_on_error (bool): Whether to fail on processing errors. Default: True
        useurl (bool): Whether to read from URL instead of file. Default: False
        urlpath (str): URL path when useurl=True. Default: None
        advanced_separator (bool): Enable advanced number formatting. Default: False
        thousands_separator (str): Thousands separator for number parsing. Default: ","
        decimal_separator (str): Decimal separator for number parsing. Default: "."
        check_date (bool): Enable date parsing using column patterns. Default: False
        read_by (str): Read method (always JSONPATH). Default: "JSONPATH"
        json_path_version (str): JSONPath version specification. Default: None
        use_loop_as_root (bool): Use loop query result as root element. Default: False
        schema (List[Dict]): Column schema definitions for type conversion. Optional.

    Inputs:
        None (file input component - reads directly from file/URL)

    Outputs:
        main: Successfully processed JSON records as DataFrame
        reject: Rejected records with error information as DataFrame (if any errors occur)

    Statistics:
        NB_LINE: Total number of JSON elements processed
        NB_LINE_OK: Number of successfully processed elements
        NB_LINE_REJECT: Number of rejected elements due to errors

    Features:
        - JSONPath-based data extraction with full jsonpath-ng support
        - URL and file-based JSON reading with configurable encoding
        - Advanced data type conversion (integer, float, date) with error handling
        - Reject flow for malformed data with detailed error information
        - Schema-based validation and type coercion
        - Advanced number formatting with configurable separators
        - Date parsing with custom patterns
        - List/object serialization for complex JSON structures

    Example:
        config = {
            "filename": "/data/users.json",
            "json_loop_query": "$.users[*]",
            "mapping": [
                {"column": "user_id", "jsonpath": "$.id"},
                {"column": "username", "jsonpath": "$.name"},
                {"column": "email", "jsonpath": "$.contact.email"}
            ],
            "encoding": "UTF-8",
            "die_on_error": True
        }
    """

    def __init__(self, *args, **kwargs):
        """Initialize the FileInputJSON component."""
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)

    def _normalize_mapping(self, mapping: List[Dict]) -> List[Dict]:
        """
        Normalize Talend-style mapping to standard format.

        Converts alternating SCHEMA_COLUMN/QUERY dictionary pairs into
        standardized column/jsonpath pairs for processing.

        Args:
            mapping: Raw mapping from Talend configuration

        Returns:
            List of normalized mapping dictionaries with 'column' and 'jsonpath' keys
        """
        # Talend mapping is a list of alternating SCHEMA_COLUMN/QUERY dicts
        # Convert to a list of {column, jsonpath} pairs
        normalized = []
        col = None
        for entry in mapping:
            if entry.get('column') == 'SCHEMA_COLUMN':
                col = entry.get('jsonpath')
            elif entry.get('column') == 'QUERY' and col is not None:
                jp = entry.get('jsonpath')
                # Remove quotes if present
                if isinstance(jp, str) and jp.startswith('"') and jp.endswith('"'):
                    jp = jp[1:-1]
                normalized.append({'column': col, 'jsonpath': jp})
                col = None
        return normalized

    def _process(self, input_data=None) -> Dict[str, Any]:
        """
        Process JSON file and extract data using JSONPath expressions.

        Args:
            input_data: Not used for file input component

        Returns:
            Dictionary containing 'main' DataFrame and optional 'reject' DataFrame

        Raises:
            Exception: If die_on_error is True and processing fails
        """
        try:
            logger.debug(f"[{self.id}] Processing started with config: {self.config}")

            # Extract configuration parameters
            filename = self.config.get('filename')
            json_loop_query = self.config.get('json_loop_query')
            mapping = self.config.get('mapping', [])

            logger.info(f"[{self.id}] Reading JSON file: {filename}")
            logger.debug(f"[{self.id}] JSONPath loop query: {json_loop_query}")
            logger.debug(f"[{self.id}] Raw mapping configuration: {mapping}")

            # Normalize mapping if needed
            if mapping and isinstance(mapping, list) and mapping and isinstance(mapping[0], dict) and 'column' in mapping[0] and mapping[0]['column'] == 'SCHEMA_COLUMN':
                mapping = self._normalize_mapping(mapping)

            logger.debug(f"[{self.id}] Normalized mapping: {mapping}")

            # Get additional configuration
            die_on_error = self.config.get('die_on_error', True)
            encoding = self.config.get('encoding', 'UTF-8')
            useurl = self.config.get('useurl', False)
            urlpath = self.config.get('urlpath', None)
            advanced_separator = self.config.get('advanced_separator', False)
            thousands_separator = self.config.get('thousands_separator', ',')
            decimal_separator = self.config.get('decimal_separator', '.')
            check_date = self.config.get('check_date', False)
            read_by = self.config.get('read_by', 'JSONPATH')
            json_path_version = self.config.get('json_path_version', None)
            use_loop_as_root = self.config.get('use_loop_as_root', False)
            schema = self.config.get('schema', None)

            # Read the JSON file or URL
            if useurl and urlpath:
                logger.info(f"[{self.id}] Reading JSON from URL: {urlpath}")
                with urlopen(urlpath) as response:
                    json_bytes = response.read()
                    json_str = json_bytes.decode(encoding)
                    json_data = json.loads(json_str)
            else:
                logger.debug(f"[{self.id}] Opening file {filename} with encoding {encoding}")
                with open(filename, 'r', encoding=encoding) as file:
                    json_data = json.load(file)

            logger.debug(f"[{self.id}] Loaded JSON data type: {type(json_data)}")

            # Parse JSONPath and extract elements
            from jsonpath_ng.ext import parse
            logger.debug(f"[{self.id}] Parsing JSONPath expression: {json_loop_query}")
            jsonpath_expr = parse(json_loop_query.strip('"'))
            elements = [match.value for match in jsonpath_expr.find(json_data)]
            logger.info(f"[{self.id}] Found {len(elements)} elements with JSONPath query")

            if use_loop_as_root:
                if len(elements) == 1 and isinstance(elements[0], list):
                    elements = elements[0]

            logger.debug(f"[{self.id}] Elements after use_loop_as_root processing: {len(elements)}")

            # Process each element
            output_data = []
            reject_data = []
            for i, element in enumerate(elements):
                row = {}
                reject_row = None
                try:
                    for mapping_entry in mapping:
                        column_name = mapping_entry.get('column')
                        jsonpath = mapping_entry.get('jsonpath')
                        if isinstance(jsonpath, str) and jsonpath.startswith('"') and jsonpath.endswith('"'):
                            jsonpath = jsonpath[1:-1]
                        value_matches = parse(jsonpath).find(element)
                        # --- tExtractJSONFields logic: always keep as list if query contains [*] or .*, else flatten if single ---
                        if '[*]' in jsonpath or '.*' in jsonpath:
                            val = [v.value for v in value_matches]
                        else:
                            val = [v.value for v in value_matches]
                            if len(val) == 1:
                                val = val[0]
                        if schema:
                            col_schema = next((col for col in schema if col['name'] == column_name), None)
                            if col_schema:
                                col_type = col_schema.get('type', 'id_String')
                                if val is not None:
                                    if col_type in ('id_Integer', 'int', 'integer'):
                                        try:
                                            if advanced_separator and isinstance(val, str):
                                                val = val.replace(thousands_separator, '').replace(decimal_separator, '.')
                                            val = int(float(val))
                                        except Exception:
                                            raise ValueError(f"Invalid integer for column {column_name}: {val}")
                                    elif col_type in ('id_Float', 'float', 'double'):
                                        try:
                                            if advanced_separator and isinstance(val, str):
                                                val = val.replace(thousands_separator, '').replace(decimal_separator, '.')
                                            val = float(val)
                                        except Exception:
                                            raise ValueError(f"Invalid float for column {column_name}: {val}")
                                    elif col_type in ('id_Date', 'date', 'datetime') and check_date:
                                        pattern = col_schema.get('pattern', None)
                                        if pattern and isinstance(val, str):
                                            try:
                                                pattern = pattern.replace("'", '')
                                                val = datetime.strptime(val, pattern)
                                            except Exception:
                                                raise ValueError(f"Invalid date for column {column_name}: {val} (pattern: {pattern})")
                        row[column_name] = val
                    logger.debug(f"[{self.id}] Row {i} column '{column_name}' extracted value: {val}")
                except Exception as err:
                    reject_row = dict(row) if row else {}
                    reject_row['errorCode'] = 'PARSE_ERROR'
                    reject_row['errorMessage'] = str(err)
                    logger.debug(f"[{self.id}] Row {i} rejected due to error: {err}")
                if reject_row:
                    reject_data.append(reject_row)
                else:
                    output_data.append(row)
                    logger.debug(f"[{self.id}] Row {i} successfully processed: {row}")

            logger.info(f"[{self.id}] Processing complete - Output rows: {len(output_data)}, Rejected rows: {len(reject_data)}")
            self.logger.info(f"Component {self.id}: Processed {len(output_data)} rows from JSON file. Rejected: {len(reject_data)} rows.")

            # Update component statistics
            total_rows = len(output_data) + len(reject_data)
            self._update_stats(total_rows, len(output_data), len(reject_data))

            # Convert to DataFrame
            main_df = pd.DataFrame(output_data)
            reject_df = pd.DataFrame(reject_data) if reject_data else None

            # Serialize lists/dicts as JSON strings for output columns (inspired by t_extract_json_fields.py)
            if not main_df.empty:
                for col in main_df.columns:
                    main_df[col] = main_df[col].apply(
                        lambda v: json.dumps(v) if isinstance(v, (list, dict)) else v
                    )

            logger.debug(f"[{self.id}] Final DataFrame shape: {main_df.shape}")

            result = {'main': main_df}
            if reject_df is not None and not reject_df.empty:
                result['reject'] = reject_df
            return result

        except Exception as e:
            logger.error(f"[{self.id}] Processing failed with exception: {e}")
            self.logger.error(f"Component {self.id}: Failed to process JSON file: {e}")
            if self.config.get('die_on_error', True):
                raise
            return {'main': pd.DataFrame([]), 'reject': pd.DataFrame([])}

    def validate_config(self) -> List[str]:
        """
        Validate component configuration and return list of error messages.

        Validates required parameters and optional schema configuration
        according to V1 Engine Standards.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Validate required fields
        required_fields = ['filename', 'json_loop_query', 'mapping']
        for field in required_fields:
            if not self.config.get(field):
                errors.append(f"Missing required parameter '{field}'")

        # Validate mapping structure
        mapping = self.config.get('mapping')
        if mapping is not None:
            if not isinstance(mapping, list):
                errors.append("Parameter 'mapping' must be a list")
            elif len(mapping) == 0:
                errors.append("Parameter 'mapping' cannot be empty")

        # Validate optional schema if present
        schema = self.config.get('schema')
        if schema is not None and not isinstance(schema, list):
            errors.append("Parameter 'schema' must be a list of column definitions")

        # Validate encoding
        encoding = self.config.get('encoding')
        if encoding is not None and not isinstance(encoding, str):
            errors.append("Parameter 'encoding' must be a string")

        # Validate URL configuration
        useurl = self.config.get('useurl', False)
        if useurl and not self.config.get('urlpath'):
            errors.append("Parameter 'urlpath' is required when 'useurl' is True")

        # Log validation results
        if errors:
            for error in errors:
                self.logger.error(f"Component {self.id}: {error}")
        else:
            logger.debug(f"[{self.id}] Configuration validation passed")

        return errors
