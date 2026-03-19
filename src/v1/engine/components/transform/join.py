"""
Join - Join two data flows (main and lookup) based on key columns.

Talend equivalent: tJoin

This component joins two input data flows (main and lookup) based on specified key columns,
supporting both inner and left outer joins. Closely follows Talend tJoin XML configuration
and behavior patterns. Provides flexible input mapping, case sensitivity options, and
comprehensive reject output handling for data quality monitoring.
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...exceptions import ComponentExecutionError, ConfigurationError

logger = logging.getLogger(__name__)


class Join(BaseComponent):
    """
    Joins main and lookup data flows using specified key columns.

    This component provides comprehensive join capabilities equivalent to Talend's tJoin
    component. It performs either inner or left outer joins between two DataFrames based
    on configurable key column mappings. The component supports flexible input mapping,
    case-insensitive matching, and provides both joined results and reject outputs for
    comprehensive data flow control.

    The component closely follows Talend XML configuration patterns and handles various
    edge cases including empty inputs, missing keys, and join failures with appropriate
    error handling and statistics tracking.

    Configuration:
        USE_INNER_JOIN (bool): True for inner join, False for left outer join. Default: False
        JOIN_KEY (List[Dict]): List of dictionaries with 'main' and 'lookup' keys defining join columns. Required.
        CASE_SENSITIVE (bool): Whether join comparison is case sensitive. Default: True
        DIE_ON_ERROR (bool): Whether to raise error on join failure vs. graceful degradation. Default: False
        OUTPUT_COLUMNS (List[str]): Specific columns to include in output. Default: None (All columns)

    Inputs:
        main: Main input DataFrame (primary data stream)
        lookup: Lookup input DataFrame (reference data stream)

    Outputs:
        main: Joined DataFrame containing successful matches
        reject: DataFrame containing main rows with no matches in lookup

    Statistics:
        NB_LINE: Total main input rows processed
        NB_LINE_OK: Successfully joined rows (main output rows)
        NB_LINE_REJECT: Main rows with no lookup matches (reject output rows)

    Example:
        # Inner join configuration
        config = {
            "USE_INNER_JOIN": True,
            "JOIN_KEY": [
                {"main": "customer_id", "lookup": "cust_id"},
                {"main": "product_code", "lookup": "prod_code"}
            ],
            "CASE_SENSITIVE": False,
            "DIE_ON_ERROR": False
        }

        # Left outer join with output column filtering
        config = {
            "USE_INNER_JOIN": False,
            "JOIN_KEY": [{"main": "id", "lookup": "ref_id"}],
            "OUTPUT_COLUMNS": ["id", "name", "lookup_value", "lookup_status"],
            "CASE_SENSITIVE": True
        }

    Notes:
        - Configuration parameter names follow Talend XML conventions (UPPER_CASE)
        - Supports flexible input mapping when input names differ from 'main'/'lookup'
        - Case-insensitive joins convert string values to lowercase for comparison
        - Reject output always contains main rows with no lookup matches (even for inner joins)
        - Join validation uses a 'm:1' (many-to-one) relationship validation
        - Output column filtering only includes columns that exist in the joined result
        - Graceful degradation returns empty main and full main as reject on errors
        - Component handles empty inputs and missing join keys gracefully
        - Duplicate column handling uses suffixes ('', '_lookup') in pandas merge
    """

    # Class constants for default values
    DEFAULT_USE_INNER_JOIN = True        # Talend tJoin uses inner join by default
    DEFAULT_CASE_SENSITIVE = True
    DEFAULT_DIE_ON_ERROR = False
    JOIN_TYPES = ['inner', 'left']
    MERGE_SUFFIXES = ('', '_lookup')

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Required fields
        if 'JOIN_KEY' not in self.config:
            errors.append("Missing required config: 'JOIN_KEY'")
        else:
            join_keys = self.config['JOIN_KEY']
            if not isinstance(join_keys, list):
                errors.append("Config 'JOIN_KEY' must be a list")
            elif len(join_keys) == 0:
                errors.append("Config 'JOIN_KEY' cannot be empty")
            else:
                for i, key_mapping in enumerate(join_keys):
                    if not isinstance(key_mapping, dict):
                        errors.append(f"Config 'JOIN_KEY[{i}]' must be a dictionary")
                        continue

                    if 'main' not in key_mapping:
                        errors.append(f"Config 'JOIN_KEY[{i}]' missing required field 'main'")
                    elif not isinstance(key_mapping['main'], str):
                        errors.append(f"Config 'JOIN_KEY[{i}].main' must be a string")

                    if 'lookup' not in key_mapping:
                        errors.append(f"Config 'JOIN_KEY[{i}]' missing required field 'lookup'")
                    elif not isinstance(key_mapping['lookup'], str):
                        errors.append(f"Config 'JOIN_KEY[{i}].lookup' must be a string")

        # Optional field validation
        if 'USE_INNER_JOIN' in self.config:
            if not isinstance(self.config['USE_INNER_JOIN'], bool):
                errors.append("Config 'USE_INNER_JOIN' must be boolean")

        if 'CASE_SENSITIVE' in self.config:
            if not isinstance(self.config['CASE_SENSITIVE'], bool):
                errors.append("Config 'CASE_SENSITIVE' must be boolean")

        if 'DIE_ON_ERROR' in self.config:
            if not isinstance(self.config['DIE_ON_ERROR'], bool):
                errors.append("Config 'DIE_ON_ERROR' must be boolean")

        if 'OUTPUT_COLUMNS' in self.config:
            output_columns = self.config['OUTPUT_COLUMNS']
            if output_columns is not None and not isinstance(output_columns, list):
                errors.append("Config 'OUTPUT_COLUMNS' must be a list or None")
            elif isinstance(output_columns, list):
                for i, col in enumerate(output_columns):
                    if not isinstance(col, str):
                        errors.append(f"Config 'OUTPUT_COLUMNS[{i}]' must be a string")

        return errors

    def _process(self, input_data: Optional[Dict[str, pd.DataFrame]] = None) -> Dict[str, Any]:
        """
        Join main and lookup data flows based on configuration.

        Performs join operation between main and lookup DataFrames using specified
        key columns. Handles flexible input mapping, case sensitivity, and provides
        comprehensive error handling with optional graceful degradation.

        Args:
            input_data: Dictionary containing 'main' and 'lookup' DataFrames,
                or dictionary with dynamically named inputs that get mapped

        Returns:
            Dictionary containing:
                - 'main': Joined DataFrame with successful matches
                - 'reject': DataFrame with main rows that had no lookup matches

        Raises:
            ComponentExecutionError: If join operation fails and DIE_ON_ERROR is True
            ConfigurationError: If configuration is invalid
        """
        # Map actual incoming input names to 'main' and 'lookup' based on self.inputs order
        if input_data and ('main' not in input_data or 'lookup' not in input_data):
            logger.debug(f"[{self.id}] Input mapping required: {list(input_data.keys())}")
            mapped_inputs = {}
            if hasattr(self, 'inputs') and isinstance(self.inputs, list):
                if len(self.inputs) >= 2:
                    # Map first to 'main', second to 'lookup'
                    if self.inputs[0] in input_data:
                        mapped_inputs['main'] = input_data[self.inputs[0]]
                        logger.debug(f"[{self.id}] Mapped '{self.inputs[0]}' to 'main'")
                    if self.inputs[1] in input_data:
                        mapped_inputs['lookup'] = input_data[self.inputs[1]]
                        logger.debug(f"[{self.id}] Mapped '{self.inputs[1]}' to 'lookup'")
                elif len(self.inputs) == 1:
                    if self.inputs[0] in input_data:
                        mapped_inputs['main'] = input_data[self.inputs[0]]
                        logger.debug(f"[{self.id}] Mapped '{self.inputs[0]}' to 'main'")
            # Add any other keys that may exist
            for k, v in input_data.items():
                if k not in mapped_inputs:
                    mapped_inputs[k] = v
            input_data = mapped_inputs

        # Validate input
        if not input_data or 'main' not in input_data or 'lookup' not in input_data:
            error_msg = "Both 'main' and 'lookup' inputs are required."
            logger.error(f"[{self.id}] Input validation failed: {error_msg}")
            self._update_stats(0, 0, 0)
            return {'main': pd.DataFrame(), 'reject': pd.DataFrame()}

        main_df = input_data['main']
        lookup_df = input_data['lookup']

        if main_df is None or lookup_df is None or main_df.empty:
            logger.warning(f"[{self.id}] Empty or None input data received")
            self._update_stats(0, 0, 0)
            return {'main': pd.DataFrame(), 'reject': pd.DataFrame()}

        # Get configuration with defaults
        use_inner_join = self.config.get('USE_INNER_JOIN', self.DEFAULT_USE_INNER_JOIN)
        join_keys = self.config.get('JOIN_KEY', [])
        case_sensitive = self.config.get('CASE_SENSITIVE', self.DEFAULT_CASE_SENSITIVE)
        die_on_error = self.config.get('DIE_ON_ERROR', self.DEFAULT_DIE_ON_ERROR)
        output_columns = self.config.get('OUTPUT_COLUMNS')

        main_rows = len(main_df)
        lookup_rows = len(lookup_df)
        logger.info(f"[{self.id}] Processing started: main={main_rows} rows, lookup={lookup_rows} rows")
        logger.debug(f"[{self.id}] Configuration: USE_INNER_JOIN={use_inner_join}, "
                      f"CASE_SENSITIVE={case_sensitive}, join_keys={len(join_keys)} mappings")

        # Extract join key columns
        main_keys = [k['main'] for k in join_keys]
        lookup_keys = [k['lookup'] for k in join_keys]
        logger.debug(f"[{self.id}] Join keys: main={main_keys}, lookup={lookup_keys}")

        try:
            # Handle case insensitive joins by converting to lowercase
            if not case_sensitive:
                logger.debug(f"[{self.id}] Applying case-insensitive conversion")
                # Create copies to avoid modifying original data
                main_df = main_df.copy()
                lookup_df = lookup_df.copy()

                for col in main_keys:
                    if col in main_df.columns:
                        main_df[col] = main_df[col].astype(str).str.lower()
                        logger.debug(f"[{self.id}] Converted main column '{col}' to lowercase")

                for col in lookup_keys:
                    if col in lookup_df.columns:
                        lookup_df[col] = lookup_df[col].astype(str).str.lower()
                        logger.debug(f"[{self.id}] Converted lookup column '{col}' to lowercase")

            # TALEND SPECIFIC: Remove duplicates from Lookup to ensure 1:1 matching
            # This is the key difference - Talend's tJoin takes only first match per key
            lookup_df_unique = lookup_df.drop_duplicates(subset=lookup_keys, keep='first')
            logger.debug(f"[{self.id}] Lookup rows before deduplication: {len(lookup_df)}, after: {len(lookup_df_unique)}")

            # Perform the join
            how = 'inner' if use_inner_join else 'left'
            logger.info(f"[{self.id}] Performing {how} join operation")

            joined = pd.merge(
                main_df,
                lookup_df_unique,  # Use deduplicated Lookup
                left_on=main_keys,
                right_on=lookup_keys,
                how=how,
                suffixes=self.MERGE_SUFFIXES,
                copy=False,
                sort=False
            )

            # Always compute rejects as main rows with no match in Lookup
            logger.debug(f"[{self.id}] Computing reject rows")
            # FIXED: Use original main_df for reject computation, not merged data
            # Find main rows that have no match in Lookup
            main_with_lookup_indicator = pd.merge(
                main_df,
                lookup_df_unique,  # Use same deduplicated Lookup for consistency
                left_on=main_keys,
                right_on=lookup_keys,
                how='left',
                indicator=True
            )

            # Reject = original main rows that had no Lookup match
            reject_indices = main_with_lookup_indicator['_merge'] == 'left_only'
            reject = main_df[reject_indices].copy()  # Use original main_df, not merged data
            main_out = joined

            # SCHEMA FILTERING: Apply output schema filtering based on component's schema definition
            if hasattr(self, 'schema') and 'output' in self.schema and self.schema['output']:
                output_schema_columns = [col['name'] for col in self.schema['output']]
                logger.debug(f"[{self.id}] Filtering output columns based on schema: {output_schema_columns}")
                # Only keep columns that exist in both the DataFrame and the schema
                available_columns = [col for col in output_schema_columns if col in main_out.columns]
                if available_columns != output_schema_columns:
                    missing_columns = set(output_schema_columns) - set(available_columns)
                    logger.warning(f"[{self.id}] Missing schema columns in joined result: {missing_columns}")
                main_out = main_out[available_columns]
                logger.debug(f"[{self.id}] Output columns after schema filtering: {list(main_out.columns)}")

            # REJECT SCHEMA FILTERING: Apply reject schema filtering for reject output
            if hasattr(self, 'schema') and 'reject' in self.schema and self.schema['reject']:
                reject_schema_columns = [col['name'] for col in self.schema['reject']]
                logger.debug(f"[{self.id}] Filtering reject columns based on schema: {reject_schema_columns}")
                logger.debug(f"[{self.id}] Reject columns before filtering: {list(reject.columns)}")
                logger.debug(f"[{self.id}] Reject data shape before filtering: {reject.shape}")

                # Only keep columns that exist in the reject DataFrame
                base_reject_columns = [col for col in reject_schema_columns if col in reject.columns]
                if base_reject_columns:
                    reject = reject[base_reject_columns]
                    logger.debug(f"[{self.id}] Reject columns after base filtering: {list(reject.columns)}")

                # Add missing error columns if they're defined in the reject schema
                error_columns = [col for col in reject_schema_columns if col not in reject.columns]
                logger.debug(f"[{self.id}] Missing error columns to add: {error_columns}")
                for error_col in error_columns:
                    if error_col in ['errorCode', 'errorMessage']:
                        # Add default error information for join rejects
                        if error_col == 'errorCode':
                            reject[error_col] = 'JOIN_REJECT'
                        elif error_col == 'errorMessage':
                            reject[error_col] = 'Row rejected by Join component - no lookup match'
                    else:
                        # Add other missing columns with None/empty values
                        reject[error_col] = None
                    logger.debug(f"[{self.id}] Added column '{error_col}' to reject output")

                # Reorder columns to match schema order
                reject = reject.reindex(columns=reject_schema_columns, fill_value=None)
                logger.debug(f"[{self.id}] Reject columns after schema filtering: {list(reject.columns)}")
                logger.debug(f"[{self.id}] Final reject data shape: {reject.shape}")
            else:
                logger.debug(f"[{self.id}] No reject schema defined or schema not available")

            # Filter output columns to match Talend output if OUTPUT_COLUMNS is set
            if output_columns:
                logger.debug(f"[{self.id}] Filtering output columns: {output_columns}")
                # Only keep columns that exist in the DataFrame
                available_columns = [col for col in output_columns if col in main_out.columns]
                if available_columns != output_columns:
                    missing_columns = set(output_columns) - set(available_columns)
                    logger.warning(f"[{self.id}] Missing output columns: {missing_columns}")
                main_out = main_out[available_columns]

            # Update statistics and log results
            main_out_rows = len(main_out)
            reject_rows = len(reject)

            logger.info(f"[{self.id}] Join operation complete: "
                         f"input={main_rows} rows, joined={main_out_rows} rows, rejected={reject_rows} rows")

            self._update_stats(main_rows, main_out_rows, reject_rows)

            logger.info(f"[{self.id}] Processing complete")
            return {'main': main_out, 'reject': reject}

        except Exception as e:
            error_msg = f"Join failed: {str(e)}"
            logger.error(f"[{self.id}] {error_msg}")

            if die_on_error:
                raise ComponentExecutionError(self.id, error_msg, e) from e
            else:
                logger.warning(f"[{self.id}] Graceful degradation: returning empty main and full main as reject")
                self._update_stats(main_rows, 0, main_rows)
                return {'main': pd.DataFrame(), 'reject': main_df}

    def validate_config(self) -> bool:
        """
        Validate component configuration.

        Returns:
            bool: True if configuration is valid, False otherwise

        Note:
            This method maintains backward compatibility. The preferred method
            is _validate_config() which returns detailed error messages.
        """
        join_keys = self.config.get('JOIN_KEY', [])

        if not join_keys or not isinstance(join_keys, list):
            logger.error(f"[{self.id}] Configuration error: JOIN_KEY is required and must be a list.")
            return False

        for k in join_keys:
            if 'main' not in k or 'lookup' not in k:
                logger.error(f"[{self.id}] Configuration error: Each JOIN_KEY entry must have 'main' and 'lookup'.")
                return False

        logger.debug(f"[{self.id}] Configuration validation passed")
        return True
