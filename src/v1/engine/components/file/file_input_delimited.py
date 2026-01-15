"""
tFileInputDelimited component - Read delimited files
"""
import pandas as pd
import os
from typing import Dict, Any, Optional, Iterator
from decimal import Decimal
import logging
import csv  # Add this import at the top of the file
from ...base_component import BaseComponent, ExecutionMode

logger = logging.getLogger(__name__)


class FileInputDelimited(BaseComponent):
    """
    Read delimited files (CSV, TSV, etc.).
    Equivalent to Talend's tFileInputDelimited component.
    """

    def _build_dtype_dict(self) -> Optional[Dict[str, str]]:
        """
        Build dtype dictionary from output schema for pd.read_csv()

        Returns:
            Dict mapping column names to pandas dtypes, or None if no schema
        """
        if not self.output_schema:
            return None

        # Type mapping from Talend to pandas dtype strings
        type_mapping = {
            'id_String': 'object',
            'id_Integer': 'Int64', #Nullable integer
            'id_Long': 'Int64',
            'id_Float': 'float64',
            'id_Double': 'float64',
            'id_Boolean': 'bool', # read as object and convert later
            'id_Date': 'object', # read as object and convert later
            'id_BigDecimal': 'object',
            # Simple type names
            'str': 'object',
            'int': 'Int64',
            'long': 'Int64',
            'float': 'float64',
            'double': 'float64',
            'bool': 'bool',
            'date': 'object',
            'Decimal': 'object'
        }

        dtype_dict = {}
        for col_def in self.output_schema:
            col_name = col_def['name']
            col_type = col_def.get('type', 'id_String')
            pandas_type = type_mapping.get(col_type, 'object')
            dtype_dict[col_name] = pandas_type

        return dtype_dict

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Read delimited file and return as DataFrame
        """
        # Get configuration with proper type conversion
        filepath = self.config.get('filepath', '')
        delimiter = self.config.get('delimiter', ',')
        row_separator = self.config.get('row_separator', None)
        encoding = self.config.get('encoding', 'UTF-8')

        # Convert numeric parameters to int to avoid string/int comparison issues
        try:
            header_rows = int(self.config.get('header_rows', 0))
        except (ValueError, TypeError):
            header_rows = 0

        try:
            footer_rows = int(self.config.get('footer_rows', 0))
        except (ValueError, TypeError):
            footer_rows = 0

        limit = self.config.get('limit', '')
        remove_empty_rows = self.config.get('remove_empty_rows', False)
        text_enclosure = self.config.get('text_enclosure', '"')
        escape_char = self.config.get('escape_char', '\\')
        trim_all = self.config.get('trim_all', False)
        die_on_error = self.config.get('die_on_error', True)

        # Handle special case: no delimiter and no row separator, read entire file as single string    
        if delimiter in [None, '', '""'] and row_separator in [None, '', '""']:
            try:
                with open(filepath, 'r', encoding=encoding) as f:
                    file_content = f.read()
                #Use first column from output schema or default to 'doc'
                if self.output_schema and len(self.output_schema) > 0:
                    column_name = self.output_schema[0]['name']
                else:
                    column_name = 'doc'
                df = pd.DataFrame([{column_name: file_content}])
                self._update_stats(1, 1, 0)
                logger.info(f"Component {self.id}: Read entire file as single string from {filepath}")
                logger.debug(f"Component {self.id}: XML as string , Dataframe shape {df.shape}")
                return {'main': df}

            except Exception as e:
                if die_on_error:
                    raise
                return {'main': pd.DataFrame()}

        return {'main': pd.DataFrame()}
