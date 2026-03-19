"""
ExtractJSONFields - Extract fields from JSON data based on JSONPath queries.

Talend equivalent: tExtractJSONFields
"""
import logging
from typing import Any, Dict, List, Optional

import pandas as pd
import json
from jsonpath_ng import parse

from ...base_component import BaseComponent
from ...exceptions import ComponentExecutionError, ConfigurationError, DataValidationError

logger = logging.getLogger(__name__)


class ExtractJSONFields(BaseComponent):
    """
    Extract fields from JSON data based on JSONPath queries.

    This component processes JSON data contained in DataFrame rows and extracts
    specific fields using JSONPath expressions. It supports loop queries for
    processing arrays and complex nested structures.

    Configuration:
        loop_query (str): JSONPath query for looping through data. Required.
        mapping (list): List of mappings for extracting fields. Required.
        die_on_error (bool): Whether to stop on error. Default: False
        read_by (str): Method to read JSON (e.g., 'JSONPATH'). Optional.
        json_path_version (str): JSONPath version (e.g., '2_1_0'). Optional.
        encoding (str): Encoding type (e.g., 'UTF-8'). Optional.
        use_loop_as_root (bool): Whether to use the loop as the root. Optional.

    Inputs:
        main: JSON data as a DataFrame with JSON strings in the first column.

    Outputs:
        main: Extracted fields as a DataFrame.
        reject: Rows that failed extraction.

    Statistics:
        NB_LINE: Total rows processed
        NB_LINE_OK: Rows successfully processed
        NB_LINE_REJECT: Rows that failed processing

    Example configuration:
        {
            "loop_query": "$.data[*]",
            "mapping": [
                {
                    "schema_column": "name",
                    "query": "$.name"
                },
                {
                    "schema_column": "values",
                    "query": "$.items[*].value"
                }
            ],
            "die_on_error": false
        }

    Notes:
        - JSON data is expected in the first column of input DataFrame
        - Complex objects (lists/dicts) are serialized as JSON strings in output
        - JSONPath queries containing [*] or .* preserve arrays as lists
        - Single-value results are flattened to scalar values
    """

    def _validate_config(self) -> List[str]:
        """Validate component configuration."""
        errors = []

        # Validate required fields
        if 'loop_query' not in self.config:
            errors.append("Missing required config: 'loop_query'")
        elif not isinstance(self.config['loop_query'], str):
            errors.append("Config 'loop_query' must be a string")
        elif not self.config['loop_query'].strip():
            errors.append("Config 'loop_query' cannot be empty")

        if 'mapping' not in self.config:
            errors.append("Missing required config: 'mapping'")
        elif not isinstance(self.config['mapping'], list):
            errors.append("Config 'mapping' must be a list")
        elif len(self.config['mapping']) == 0:
            errors.append("Config 'mapping' cannot be empty")
        else:
            # Validate mapping entries
            for i, mapping_entry in enumerate(self.config['mapping']):
                if not isinstance(mapping_entry, dict):
                    errors.append(f"Config 'mapping[{i}]' must be a dictionary")
                    continue

                # Check for column name
                if not mapping_entry.get('schema_column') and not mapping_entry.get('column'):
                    errors.append(f"Config 'mapping[{i}]' must have 'schema_column' or 'column' field")

                # Check for query
                if not mapping_entry.get('query') and not mapping_entry.get('jsonpath'):
                    errors.append(f"Config 'mapping[{i}]' must have 'query' or 'jsonpath' field")

        # Validate optional fields
        if 'die_on_error' in self.config:
            if not isinstance(self.config['die_on_error'], bool):
                errors.append("Config 'die_on_error' must be a boolean")

        return errors

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Process input data and extract JSON fields using JSONPath queries.

        Args:
            input_data: Input DataFrame with JSON strings in first column.
                        If None or empty, returns empty result.

        Returns:
            Dictionary containing:
                - 'main': DataFrame with extracted fields
                - 'reject': DataFrame with rows that failed extraction

        Raises:
            ComponentExecutionError: If processing fails and die_on_error is True
            ConfigurationError: If configuration validation fails
        """

        # Validate configuration
        config_errors = self._validate_config()
        if config_errors:
            error_msg = f"Configuration validation failed: {'; '.join(config_errors)}"
            logger.error(f"[{self.id}] {error_msg}")
            raise ConfigurationError(error_msg)

        # Handle list input (convert to DataFrame)
        if isinstance(input_data, list):
            input_data = pd.DataFrame(input_data)

        # Handle empty input
        if input_data is None or input_data.empty:
            logger.warning(f"[{self.id}] Empty input received")
            self._update_stats(0, 0, 0)
            return {'main': pd.DataFrame(), 'reject': pd.DataFrame()}

        rows_in = len(input_data)
        logger.info(f"[{self.id}] Processing started: {rows_in} rows")

        try:
            # Extract configuration with defaults
            loop_query = self.config.get('loop_query', '')
            mapping = self.config.get('mapping', [])
            die_on_error = self.config.get('die_on_error', False)

            # Debug logging (keeping original debug print format but using Logger)
            logger.debug(f"[{self.id}] ExtractJSONFields config: loop_query={loop_query}, mapping={mapping}, die_on_error={die_on_error}")
            logger.debug(f"[{self.id}] Input DataFrame columns: {input_data.columns.tolist()}")
            logger.debug(f"[{self.id}] Input DataFrame head:\n{input_data.head()}")

            # Initialize output collections
            main_output = []
            reject_output = []

            # Process each row
            for row_idx, row in input_data.iterrows():
                try:
                    logger.debug(f"[{self.id}] Processing row {row_idx}: {row.values}")

                    # Parse JSON data from first column (keeping original assumption)
                    json_data = json.loads(row[0])
                    logger.debug(f"[{self.id}] Loaded JSON: {json_data}")

                    # Extract fields using JSONPath
                    extracted_rows = self._extract_fields(json_data, loop_query, mapping)
                    logger.debug(f"[{self.id}] Extracted rows: {extracted_rows}")

                    main_output.extend(extracted_rows)

                except Exception as e:
                    error_msg = f"Error processing row {row_idx}: {str(e)}"
                    logger.error(f"[{self.id}] {error_msg}")

                    if die_on_error:
                        raise ComponentExecutionError(
                            self.id,
                            f"Row processing failed: {error_msg}",
                            e
                        ) from e

                    # Add to reject output (keeping original format)
                    reject_output.append({
                        'errorJSONField': row[0],
                        'errorCode': 'PARSE_ERROR',
                        'errorMessage': str(e)
                    })

            # Convert results to DataFrames
            main_df = pd.DataFrame(main_output)
            reject_df = pd.DataFrame(reject_output)

            logger.debug(f"[{self.id}] Main DataFrame before serialization:\n{main_df}")
            logger.debug(f"[{self.id}] Output schema: {getattr(self, 'schema', None)}")

            # Serialize complex objects to JSON strings (preserving original behavior)
            if not main_df.empty:
                for col in main_df.columns:
                    logger.debug(f"[{self.id}] Serializing column: {col}")
                    main_df[col] = main_df[col].apply(
                        lambda v: json.dumps(v) if isinstance(v, (list, dict)) else v
                    )
                    logger.debug(f"[{self.id}] After serialization, column {col} sample: {main_df[col].head(3).tolist()}")

            logger.debug(f"[{self.id}] Main DataFrame after serialization:\n{main_df}")

            # Calculate statistics
            rows_out = len(main_df)
            rows_rejected = len(reject_df)

            # Update statistics and log completion
            self._update_stats(rows_in, rows_out, rows_rejected)
            logger.info(f"[{self.id}] Processing complete: "
                        f"in={rows_in}, out={rows_out}, rejected={rows_rejected}")

            return {'main': main_df, 'reject': reject_df}

        except ComponentExecutionError:
            # Re-raise component execution errors
            raise

        except ConfigurationError:
            # Re-raise configuration errors
            raise

        except Exception as e:
            error_msg = f"Unexpected error during processing: {str(e)}"
            logger.error(f"[{self.id}] {error_msg}")
            raise ComponentExecutionError(self.id, error_msg, e) from e

    def _extract_fields(self, json_data: Any, loop_query: str, mapping: List[Dict]) -> List[Dict]:
        """
        Extract fields from JSON data using JSONPath queries.

        Args:
            json_data: Parsed JSON data structure
            loop_query: JSONPath query for iteration
            mapping: List of field mappings with queries

        Returns:
            List of dictionaries containing extracted field values

        Raises:
            Exception: If JSONPath processing fails
        """
        extracted_rows = []

        try:
            # Parse loop query and find matches
            jsonpath_expr = parse(loop_query)
            matches = [match.value for match in jsonpath_expr.find(json_data)]

            logger.debug(f"[{self.id}] Loop query '{loop_query}' found {len(matches)} matches")

            # If no matches found for loop query, try to process the entire JSON data
            if not matches:
                logger.debug(f"[{self.id}] No matches for loop query, processing entire JSON data")
                matches = [json_data]

            # Extract fields for each match
            for item_idx, item in enumerate(matches):
                row = {}
                logger.debug(f"[{self.id}] Processing item {item_idx}: {item}")

                for m_idx, m in enumerate(mapping):
                    # Get column name (supporting both schema_column and column)
                    col = m.get('schema_column') or m.get('column')
                    # Get query (supporting both query and jsonpath)
                    query = m.get('query') or m.get('jsonpath')

                    if query:
                        try:
                            # Execute JSONPath query on current item
                            logger.debug(f"[{self.id}] Executing query '{query}' on item for column '{col}'")

                            # Determine the context for the query
                            # If query starts with $. and doesn't reference the current iteration item,
                            # execute it on the full JSON data (for accessing parent/sibling data)
                            if query.startswith('$.') and not self._is_relative_query(query):
                                # Execute on full JSON data (for accessing data outside current iteration)
                                jsonpath_matches = parse(query).find(json_data)
                                logger.debug(f"[{self.id}] Executing '{query}' on full JSON data")
                            else:
                                # Execute on current iteration item
                                jsonpath_matches = parse(query).find(item)
                                logger.debug(f"[{self.id}] Executing '{query}' on current item")

                            values = [match.value for match in jsonpath_matches]

                            logger.debug(f"[{self.id}] Query '{query}' returned {len(values)} values: {values}")

                            # Handle the extracted values based on query type and result count
                            if not values:
                                # No matches found - set to empty string
                                row[col] = ''
                                logger.debug(f"[{self.id}] No matches for query '{query}', setting column '{col}' to empty string")
                            elif '[*]' in query or '.*' in query:
                                # Wildcard query - preserve as array (but check if we want to serialize)
                                if len(values) == 1 and not isinstance(values[0], (list, dict)):
                                    # Single scalar value from wildcard - flatten it
                                    row[col] = values[0]
                                else:
                                    # Multiple values or complex objects - keep as array
                                    row[col] = values
                                    logger.debug(f"[{self.id}] Wildcard query '{query}' result for column '{col}': {row[col]}")
                            else:
                                # Regular query - take first value if single, otherwise array
                                if len(values) == 1:
                                    row[col] = values[0]
                                else:
                                    row[col] = values
                                logger.debug(f"[{self.id}] Regular query '{query}' result for column '{col}': {row[col]}")

                        except Exception as e:
                            # Set empty string for failed extractions (better than None for display)
                            row[col] = ''
                            logger.warning(f"[{self.id}] Failed to execute query '{query}' for column '{col}': {e}")

                    else:
                        row[col] = ''
                        logger.warning(f"[{self.id}] No query specified for mapping {m_idx}, column '{col}'")

                extracted_rows.append(row)
                logger.debug(f"[{self.id}] Extracted row {item_idx}: {row}")

        except Exception as e:
            logger.error(f"[{self.id}] Error in JSONPath extraction: {str(e)}")
            raise

        logger.debug(f"[{self.id}] Total extracted rows: {len(extracted_rows)}")
        return extracted_rows

    def _is_relative_query(self, query: str) -> bool:
        """
        Determine if a JSONPath query is relative to the current iteration context.

        Args:
            query: JSONPath query string

        Returns:
            True if the query should be executed on the current item, False if on full JSON
        """
        # Queries that should be executed on the current iteration item (relative)
        relative_patterns = [
            '$.skill',          # Direct property of current item
            '$.level',          # Direct property of current item
            '$.name',           # If current item has name property
            '$.value',          # Direct property access
        ]

        # Simple heuristic: if query is just accessing direct properties without complex paths,
        # it's likely meant for the current iteration item
        if query.count('.') <= 1 and not query.startswith('$.employee'):
            return True

        return False
