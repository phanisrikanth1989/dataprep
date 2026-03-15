"""
ExtractXMLField - Extracts fields from XML data in DataFrame columns using XPath queries.

Talend equivalent: tExtractXMLField

This component processes XML data stored in DataFrame columns, applying XPath queries
to extract specific fields and create structured output. Supports namespace handling,
node validation, and comprehensive error handling with reject outputs.
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd
from lxml import etree

from ...base_component import BaseComponent
from ...exceptions import ComponentExecutionError, ConfigurationError

logger = logging.getLogger(__name__)


class ExtractXMLField(BaseComponent):
    """
    Extracts fields from XML data in a DataFrame column using XPath queries.

    Processes XML content stored in a specified DataFrame column, applying an XPath
    loop query to iterate over XML nodes and extracting field values using relative
    XPath expressions. Supports optional node validation, namespace handling, and
    row limiting.

    Configuration:
        xml_field (str): Name of the column containing XML data. Default: 'line'
        loop_query (str): XPath query to loop over nodes. Default: ''
        mapping (list): List of extraction mappings with keys:
            - schema_column: Output column name
            - query: XPath query relative to loop_query
            - nodecheck: Optional XPath to check node existence
        limit (int): Maximum number of rows to extract per XML. Default: 0 (no limit)
        die_on_error (bool): Whether to stop on parsing errors. Default: False
        ignore_ns (bool): Ignore XML namespaces during parsing. Default: False
        output_schema (list): Output schema definition for validation. Default: []
        reject_schema (list): Reject output schema definition. Default: []

    Inputs:
        main: DataFrame containing XML data in specified column

    Outputs:
        main: DataFrame with extracted fields as columns
        reject: Rows that failed extraction with error details

    Statistics:
        NB_LINE: Total rows processed
        NB_LINE_OK: Rows successfully processed
        NB_LINE_REJECT: Rows that failed processing

    Example configuration:
        {
            "xml_field": "xml_data",
            "loop_query": "//Employee",
            "mapping": [
                {"schema_column": "name", "query": "./Name/text()"},
                {"schema_column": "salary", "query": "./Salary/text()", "nodecheck": "/Salary"}
            ],
            "limit": 100,
            "die_on_error": False,
            "ignore_ns": True
        }

    Notes:
        - Empty XML fields are sent to reject output with error code 'NO_XML'
        - Failed node checks send rows to reject with code 'NODECHECK_FAIL'
        - XML parsing errors send rows to reject with code 'PARSE_ERROR'
        - When die_on_error=True, parsing errors will terminate component execution
    """

    # Class constants
    DEFAULT_XML_FIELD = 'line'
    DEFAULT_LOOP_QUERY = ''
    DEFAULT_LIMIT = 0

    # Error codes for reject output
    ERROR_NO_XML = 'NO_XML'
    ERROR_NODECHECK_FAIL = 'NODECHECK_FAIL'
    ERROR_PARSE_ERROR = 'PARSE_ERROR'

    def _validate_config(self) -> List[str]:
        """
        Validate component configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # xml_field validation
        if 'xml_field' in self.config:
            xml_field = self.config['xml_field']
            if not isinstance(xml_field, str) or not xml_field.strip():
                errors.append("Config 'xml_field' must be a non-empty string")

        # loop_query validation
        if 'loop_query' in self.config:
            loop_query = self.config['loop_query']
            if not isinstance(loop_query, str):
                errors.append("Config 'loop_query' must be a string")

        # mapping validation
        if 'mapping' in self.config:
            mapping = self.config['mapping']
            if not isinstance(mapping, list):
                errors.append("Config 'mapping' must be a list")
            else:
                for i, m in enumerate(mapping):
                    if not isinstance(m, dict):
                        errors.append(f"Config 'mapping[{i}]' must be a dictionary")
                        continue
                    if 'schema_column' not in m:
                        errors.append(f"Config 'mapping[{i}]' missing required 'schema_column'")
                    if 'query' not in m:
                        errors.append(f"Config 'mapping[{i}]' missing required 'query'")

        # limit validation
        if 'limit' in self.config:
            limit = self.config['limit']
            if not isinstance(limit, (int, str)):
                errors.append("Config 'limit' must be an integer or string")
            elif isinstance(limit, str) and limit.strip() and not limit.isdigit():
                errors.append("Config 'limit' must be a valid integer")

        # Boolean field validation
        for field in ['die_on_error', 'ignore_ns']:
            if field in self.config and not isinstance(self.config[field], bool):
                errors.append(f"Config '{field}' must be a boolean")

        # Schema validation
        for schema_field in ['output_schema', 'reject_schema']:
            if schema_field in self.config:
                schema = self.config[schema_field]
                if not isinstance(schema, list):
                    errors.append(f"Config '{schema_field}' must be a list")

        return errors

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Process XML data and extract fields using XPath queries.

        Iterates through each row in the input DataFrame, parses XML content from
        the specified column, applies the loop query to find nodes, and extracts
        field values using the configured mapping. Handles parsing errors and
        node validation failures by routing them to reject output.

        Args:
            input_data: Input DataFrame with XML data. If None or empty, returns empty result.

        Returns:
            Dictionary containing:
                - 'main': DataFrame with extracted fields
                - 'reject': DataFrame with rows that failed processing

        Raises:
            ComponentExecutionError: If die_on_error=True and XML parsing fails
            ConfigurationError: If configuration validation fails
        """
        # Validate configuration
        config_errors = self._validate_config()
        if config_errors:
            error_msg = f"Configuration validation failed: {'; '.join(config_errors)}"
            logger.error(f"[{self.id}] {error_msg}")
            raise ConfigurationError(error_msg)

        # Handle empty input
        if not isinstance(input_data, pd.DataFrame) or input_data.empty:
            logger.warning(f"[{self.id}] Empty input received")
            self._update_stats(0, 0, 0)
            return {'main': pd.DataFrame(), 'reject': pd.DataFrame()}

        rows_in = len(input_data)
        logger.info(f"[{self.id}] Processing started: {rows_in} rows")

        # Get configuration with defaults
        xml_field = self.config.get('xml_field', self.DEFAULT_XML_FIELD)
        loop_query = self.config.get('loop_query', self.DEFAULT_LOOP_QUERY)
        mapping = self.config.get('mapping', [])
        limit = int(self.config.get('limit', self.DEFAULT_LIMIT))
        die_on_error = self.config.get('die_on_error', False)
        ignore_ns = self.config.get('ignore_ns', False)
        output_schema = self.config.get('output_schema', [])
        reject_schema = self.config.get('reject_schema', [])

        main_output = []
        reject_output = []
        rows_read = 0
        rows_ok = 0
        rows_reject = 0

        try:
            for idx, row in input_data.iterrows():
                xml_string = row.get(xml_field, None)
                if xml_string is None:
                    reject_output.append(self._make_reject_row(row, xml_string, self.ERROR_NO_XML, 'No XML data'))
                    rows_reject += 1
                    continue
                try:
                    parser = etree.XMLParser(ns_clean=ignore_ns, recover=True)
                    root = etree.fromstring(xml_string.encode('utf-8'), parser=parser)
                    if ignore_ns:
                        for elem in root.getiterator():
                            if not hasattr(elem.tag, 'find'): continue
                            i = elem.tag.find('}')
                            if i >= 0:
                                elem.tag = elem.tag[i+1:]
                    nodes = root.xpath(loop_query)
                    if not isinstance(nodes, list):
                        nodes = [nodes]
                    if limit:
                        nodes = nodes[:limit]
                    for node in nodes:
                        out_row = {}
                        node_ok = True
                        for m in mapping:
                            col = m.get('schema_column')
                            query = m.get('query')
                            nodecheck = m.get('nodecheck')
                            value = None
                            if nodecheck:
                                try:
                                    check_result = node.xpath(nodecheck)
                                    if not check_result:
                                        node_ok = False
                                        break
                                except Exception as e:
                                    node_ok = False
                                    break
                            try:
                                result = node.xpath(query)
                                if isinstance(result, list):
                                    value = result[0] if result else None
                                    if hasattr(value, 'text'):
                                        value = value.text
                                else:
                                    value = result
                            except Exception as e:
                                value = None
                            out_row[col] = value
                        if node_ok:
                            main_output.append(out_row)
                            rows_ok += 1
                        else:
                            reject_output.append(self._make_reject_row(row, xml_string, self.ERROR_NODECHECK_FAIL, 'Node check failed'))
                            rows_reject += 1
                except Exception as e:
                    logger.error(f"[{self.id}] Error parsing XML row: {e}")
                    if die_on_error:
                        raise ComponentExecutionError(self.id, f"XML parsing failed: {e}", e)
                    reject_output.append(self._make_reject_row(row, xml_string, self.ERROR_PARSE_ERROR, str(e)))
                    rows_reject += 1
                rows_read += 1

            # Create output DataFrames
            main_df = pd.DataFrame(main_output)
            reject_df = pd.DataFrame(reject_output)

            # Apply schema validation if configured
            if output_schema:
                main_df = self._validate_schema(main_df, output_schema)
            if reject_schema:
                reject_df = self._validate_schema(reject_df, reject_schema)

            # Update statistics and log completion
            self._update_stats(rows_read, rows_ok, rows_reject)
            logger.info(f"[{self.id}] Processing complete: "
                        f"in={rows_in}, out={rows_ok}, rejected={rows_reject}")

            return {'main': main_df, 'reject': reject_df}

        except Exception as e:
            if isinstance(e, (ComponentExecutionError, ConfigurationError)):
                raise
            logger.error(f"[{self.id}] Processing failed: {e}")
            raise ComponentExecutionError(self.id, f"Processing failed: {e}", e)

    def _make_reject_row(self, row: pd.Series, xml_string: Any, code: str, msg: str) -> Dict[str, Any]:
        """
        Create a reject row with error details.

        Takes the original row data and adds error information fields for
        debugging and error tracking purposes.

        Args:
            row: Original row data from input DataFrame
            xml_string: XML content that failed processing
            code: Error code indicating failure type
            msg: Human-readable error message

        Returns:
            Dictionary containing original row data plus error fields:
                - errorXMLField: The XML content that failed
                - errorCode: Error type code
                - errorMessage: Error description
        """
        reject_row = {k: row.get(k, None) for k in row.index}
        reject_row['errorXMLField'] = xml_string
        reject_row['errorCode'] = code
        reject_row['errorMessage'] = msg
        return reject_row
