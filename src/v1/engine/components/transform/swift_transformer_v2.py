"""
TSwiftDataTransformer component - Transform SWIFT pipe-delimited data based on configuration mappings
Integrates swift_data_transformer.py functionality into ETL engine

Optimized version (v2):
- Pre-built lookup indexes (dict-based) for O(1) normal matching
- Pre-compiled regex patterns for lookup regex matching
- Pre-compiled Python expressions (code objects) for eval
- Pre-categorized fields by type and lookup dependency
- Batch dict conversion instead of iterrows()
- DRY config extraction via single helper (_apply_config)
- Removed duplicate _load_lookup_files method
- Fixed unbalanced parenthesis in log message
"""

import pandas as pd
import yaml
import json
import logging
import re
import os
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from ...base_component import BaseComponent

logger = logging.getLogger(__name__)

# Pre-compiled SWIFT regex patterns (class-level, compiled once)
_BALANCE_RE = re.compile(r'^([CD])(\d{6})([A-Z]{3})([\d,\.]+)')
_MOVEMENT_RE = re.compile(r'^(\d{6})(\d{4})?([DC])(\d+[.,]?\d*)([A-Z]?)([^/]*)?//(.*)?')

# Shared safe builtins for python_expression evaluation
_SAFE_BUILTINS = {
    '__import__': __import__,
    'str': str, 'int': int, 'float': float, 'len': len,
    'bool': bool, 'list': list, 'dict': dict,
    'min': min, 'max': max, 'abs': abs,
    'round': round, 'sum': sum, 'any': any, 'all': all,
}

_EVAL_GLOBALS_TEMPLATE = {
    're': re,
    'datetime': datetime,
    'str': str, 'int': int, 'float': float, 'len': len,
    'bool': bool, 'list': list, 'dict': dict,
    'min': min, 'max': max, 'abs': abs,
    'round': round, 'sum': sum, 'any': any, 'all': all,
    '__builtins__': _SAFE_BUILTINS,
}

# Date formats for parsing, with optional slice lengths
_DATE_FORMATS = [
    ('%Y%m%d', 8), ('%y%m%d', 6),
    ('%Y-%m-%d', None), ('%d-%m-%Y', None), ('%d%m%y', 6),
]


class SwiftTransformer(BaseComponent):
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

        # Store config file path for later resolution during execution
        self.config_file = self.config.get('config_file')
        self.inline_config = self.config.get('transform_config', {})
        self.transform_config: Optional[Dict[str, Any]] = None

        # Pre-computed acceleration structures (populated by _apply_config)
        self.input_fields: List = []
        self.output_fields: List = []
        self.output_layout: List[str] = []
        self.field_mappings: Dict = {}
        self.transformations: Dict = {}
        self.output_fields_map: Dict[str, Dict] = {}
        self.lookups_config: List = []
        self.lookup_data: Dict[str, Dict] = {}

        # Fields that need recomputation after lookups
        self._lookup_dependent_fields: List[Tuple[str, Dict]] = []
        # Pre-compiled Python expressions  {field_name: code_object}
        self._compiled_expressions: Dict[str, Any] = {}

        # Try to load config eagerly if possible (no context vars needed)
        if not self.config_file and not self.inline_config:
            self._apply_config(self._get_default_transform_config())
        elif not self.config_file and self.inline_config:
            # Inline config doesn't need context resolution — try eagerly
            self._apply_config(self.inline_config)
        else:
            logger.info(f"Component {self.id}: Config will be loaded at execution time (external file)")

    # ------------------------------------------------------------------
    # Configuration loading (single DRY method)
    # ------------------------------------------------------------------

    def _apply_config(self, config: Dict[str, Any]) -> None:
        """
        Extract all configuration sections and build acceleration structures.
        This is the single source of truth for config extraction — avoids
        the duplication that existed in the original code.
        """
        self.transform_config = config
        self.input_fields = config.get('input_fields', [])
        self.output_fields = config.get('output_fields', [])
        self.output_layout = config.get('output_layout', [])
        self.field_mappings = config.get('field_mappings', {})
        self.transformations = config.get('transformations', {})

        # Quick-access map: field_name -> field_config
        self.output_fields_map = {f['name']: f for f in self.output_fields}

        # Derive layout from output_fields if not specified
        if not self.output_layout:
            self.output_layout = [f['name'] for f in self.output_fields]

        # Pre-categorize lookup-dependent fields for multi-pass processing
        self._lookup_dependent_fields = [
            (name, field) for name, field in self.output_fields_map.items()
            if field.get('depends_on_lookup', False)
        ]

        # Pre-compile Python expressions into code objects
        self._compiled_expressions = {}
        for field in self.output_fields:
            if field.get('type') == 'python_expression':
                expr = field.get('python_expression', '')
                if expr:
                    try:
                        self._compiled_expressions[field['name']] = compile(
                            expr, f"<field:{field['name']}>", 'eval'
                        )
                    except SyntaxError as e:
                        logger.warning(
                            f"Component {self.id}: Failed to compile expression for {field['name']}: {e}"
                        )

        # Load lookups with pre-built indexes
        self.lookups_config = config.get('lookups', [])
        self.lookup_data = {}
        self._load_lookup_files()

        logger.info(
            f"Component {self.id}: Initialized transformer with "
            f"{len(self.output_layout)} output fields ({len(self.output_fields)} defined)"
        )

    def _ensure_config_loaded(self) -> None:
        """Ensure config is loaded at execution time when context is available."""
        if self.transform_config is not None:
            return

        if self.config_file:
            config = self._load_external_config(self.config_file)
        elif self.inline_config:
            config = self.inline_config
        else:
            config = self._get_default_transform_config()

        if not config:
            raise ValueError(f"Component {self.id}: No valid transformation configuration available")

        self._apply_config(config)

    def _load_lookup_files(self) -> None:
        """
        Load all lookup files into memory and pre-build indexes.
        
        For 'normal' match_type: builds a dict index keyed on lookup_key for O(1) lookups.
        For 'regex' match_type: pre-compiles all regex patterns from the lookup rows.
        """
        for lookup in self.lookups_config:
            lookup_name = lookup.get('name', '')
            lookup_file = lookup.get('file', '')

            if not lookup_file:
                logger.warning(f"Component {self.id}: Lookup {lookup_name} has no file specified")
                continue

            resolved_lookup_file = lookup_file  # fallback for error message
            try:
                resolved_lookup_file = self.context_manager.resolve_string(lookup_file)
                lookup_file_path = os.path.normpath(resolved_lookup_file)

                delimiter = ',' if lookup_file_path.endswith('.csv') else '|'
                lookup_df = pd.read_csv(
                    lookup_file_path, delimiter=delimiter, dtype=str, keep_default_na=False
                )

                lookup_key = lookup.get('lookup_key', '')
                match_type = lookup.get('match_type', 'normal')

                if match_type == 'regex':
                    # Pre-compile regex patterns from lookup rows
                    compiled_patterns: List[Tuple[Any, Any]] = []
                    for _, lrow in lookup_df.iterrows():
                        raw_pattern = str(lrow.get(lookup_key, ''))
                        if not raw_pattern:
                            compiled_patterns.append((None, lrow))
                            continue

                        # Convert simple wildcard patterns to regex
                        special_chars = {'.', '^', '$', '+', '[', ']', '(', ')', '{', '}', '|', '\\'}
                        if ('*' in raw_pattern or '?' in raw_pattern) and \
                                not any(c in raw_pattern for c in special_chars):
                            regex_str = '^' + raw_pattern.replace('*', '.*').replace('?', '.') + '$'
                        else:
                            regex_str = raw_pattern

                        try:
                            compiled_patterns.append((re.compile(regex_str), lrow))
                        except re.error:
                            # Invalid regex — keep as literal fallback
                            compiled_patterns.append((None, lrow))

                    self.lookup_data[lookup_name] = {
                        'data': lookup_df,
                        'config': lookup,
                        'index': None,
                        'compiled_patterns': compiled_patterns,
                    }
                else:
                    # Build dict index for O(1) lookups (first match wins)
                    index: Dict[str, Any] = {}
                    if lookup_key in lookup_df.columns:
                        for _, lrow in lookup_df.iterrows():
                            key_val = str(lrow[lookup_key])
                            if key_val not in index:
                                index[key_val] = lrow

                    self.lookup_data[lookup_name] = {
                        'data': lookup_df,
                        'config': lookup,
                        'index': index,
                        'compiled_patterns': None,
                    }

                logger.info(
                    f"Component {self.id}: Loaded lookup {lookup_name} "
                    f"with {len(lookup_df)} rows from {lookup_file_path}"
                )

            except Exception as e:
                logger.error(
                    f"Component {self.id}: Error loading lookup file {resolved_lookup_file}: {e}"
                )

    def _load_external_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from external YAML or JSON file."""
        resolved_path = None
        try:
            resolved_path = os.path.normpath(self.context_manager.resolve_string(config_path))
            with open(resolved_path, 'r', encoding='utf-8') as f:
                if resolved_path.endswith(('.yaml', '.yml')):
                    config = yaml.safe_load(f)
                else:
                    config = json.load(f)
            logger.info(f"Component {self.id}: Loaded external config from {resolved_path}")
            return config
        except Exception as e:
            display_path = resolved_path or config_path
            logger.error(f"Component {self.id}: Error loading config {display_path}: {e}")
            raise ValueError(f"Failed to load transformation config: {e}")

    # ------------------------------------------------------------------
    # Main processing entry point
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Transform SWIFT pipe-delimited data to business format."""
        try:
            self._ensure_config_loaded()

            if input_data is None or input_data.empty:
                logger.warning(f"Component {self.id}: No input data provided")
                self._update_stats(0, 0, 0)
                return {'main': pd.DataFrame()}

            row_count = len(input_data)
            logger.info(f"Component {self.id}: Processing {row_count} input rows")

            transformed_df = self._transform_rows(input_data)

            output_file = self.config.get('output_file')
            if output_file:
                self._write_output_file(transformed_df, output_file)

            self._update_stats(row_count, len(transformed_df), 0)
            logger.info(f"Component {self.id}: Transformed {row_count} rows to {len(transformed_df)} rows")
            return {'main': transformed_df}

        except Exception as e:
            error_msg = f"Error transforming SWIFT data: {e}"
            if self.config.get('die_on_error', True):
                raise RuntimeError(error_msg)
            else:
                logger.error(f"Component {self.id}: {error_msg}")
                self._update_stats(0, 0, 1)
                return {'main': pd.DataFrame()}

    # ------------------------------------------------------------------
    # Row transformation (hot path — optimized)
    # ------------------------------------------------------------------

    def _transform_rows(self, input_df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform input DataFrame to output format.

        Uses dict-based row iteration (much faster than iterrows) and multi-pass
        processing for lookup-dependent fields.
        """
        output_layout = self.output_layout
        output_fields_map = self.output_fields_map
        has_lookups = bool(self.lookup_data)
        has_dependent_fields = bool(self._lookup_dependent_fields)
        skip_errors = self.config.get('skip_error_rows', False)

        # Pre-compute ordered field list once
        ordered_fields = list(output_fields_map.items())

        # Convert all rows to list of dicts at once — much faster than iterrows()
        input_records = input_df.to_dict('records')
        input_columns = set(input_df.columns)

        transformed_rows: List[Dict[str, Any]] = []
        empty_row = {fn: '' for fn in output_layout}

        for row_dict in input_records:
            try:
                # Pass 1: compute all output fields in order
                working_row: Dict[str, Any] = {}
                for field_name, output_field in ordered_fields:
                    working_row[field_name] = self._get_field_value(
                        output_field, row_dict, input_columns, working_row
                    )

                if has_lookups:
                    # Apply first-tier lookups (depends_on_lookup=False)
                    self._apply_lookups(working_row, depends_on_lookup=False)

                    if has_dependent_fields:
                        # Pass 2: recompute lookup-dependent fields after first-tier lookups
                        for field_name, output_field in self._lookup_dependent_fields:
                            working_row[field_name] = self._get_field_value(
                                output_field, row_dict, input_columns, working_row
                            )

                        # Apply second-tier lookups (depends_on_lookup=True)
                        self._apply_lookups(working_row, depends_on_lookup=True)

                        # Pass 3: recompute dependent fields after second-tier lookups
                        for field_name, output_field in self._lookup_dependent_fields:
                            working_row[field_name] = self._get_field_value(
                                output_field, row_dict, input_columns, working_row
                            )

                # Build final output row from layout
                transformed_rows.append(
                    {fn: working_row.get(fn, '') for fn in output_layout}
                )

            except Exception as e:
                logger.error(f"Component {self.id}: Error transforming row: {e}")
                if skip_errors:
                    continue
                transformed_rows.append(empty_row.copy())

        return pd.DataFrame(transformed_rows, columns=output_layout)

    # ------------------------------------------------------------------
    # Field value resolution
    # ------------------------------------------------------------------

    def _get_field_value(
        self,
        output_field: Dict[str, Any],
        row_dict: Dict[str, Any],
        input_columns: set,
        working_row: Dict[str, Any],
    ) -> str:
        """
        Get value for an output field based on mapping configuration.

        Args:
            output_field: Field configuration from YAML.
            row_dict: Original input row as a dict.
            input_columns: Set of column names in input (for fast membership checks).
            working_row: Dict of previously computed fields.
        """
        field_name = output_field['name']
        mapping_type = output_field.get('type', 'direct')
        source = output_field.get('source', '')
        default_value = output_field.get('default', '')

        try:
            if mapping_type == 'direct':
                value = self._resolve_direct(source, row_dict, input_columns, default_value)

            elif mapping_type == 'constant':
                value = output_field.get('value', default_value)

            elif mapping_type == 'parsed':
                value = self._parse_field_value(output_field, row_dict, input_columns)

            elif mapping_type == 'calculated':
                value = self._calculate_field_value(output_field, row_dict, input_columns)

            elif mapping_type == 'transformation':
                raw = self._resolve_direct(source, row_dict, input_columns, '')
                value = self._apply_field_transformation(output_field, raw, row_dict, input_columns)

            elif mapping_type == 'python_expression':
                value = self._evaluate_python_expression(output_field, row_dict, working_row)

            elif mapping_type == 'placeholder':
                value = default_value

            else:
                value = default_value

            # Post-processing
            if 'post_process' in output_field:
                value = self._post_process_value(value, output_field['post_process'])

            # Guard against None / NaN strings
            if value is None or (isinstance(value, str) and value.lower() == 'nan'):
                return default_value

            return str(value)

        except Exception as e:
            logger.warning(f"Component {self.id}: Error processing field {field_name}: {e}")
            return default_value

    @staticmethod
    def _resolve_direct(source: str, row_dict: Dict, input_columns: set, default: str) -> str:
        """Resolve a direct field mapping from the input row dict."""
        if source in input_columns:
            val = row_dict.get(source)
            if val is not None and not (isinstance(val, float) and val != val):  # NaN check
                s = str(val).strip()
                return default if s.lower() == 'nan' else s
        return default

    # ------------------------------------------------------------------
    # Lookups (optimized with pre-built indexes)
    # ------------------------------------------------------------------

    def _apply_lookups(self, output_row: Dict[str, Any], depends_on_lookup: bool = False) -> None:
        """
        Apply lookups to the output row (mutates in place).

        Uses pre-built dict indexes for normal matching (O(1)) and
        pre-compiled regex patterns for regex matching.
        """
        for lookup_name, lookup_info in self.lookup_data.items():
            try:
                config = lookup_info['config']

                # Filter by tier
                if config.get('depends_on_lookup', False) != depends_on_lookup:
                    continue

                main_key = config.get('main_key', '')
                lookup_key = config.get('lookup_key', '')
                columns = config.get('columns', [])
                match_type = config.get('match_type', 'normal')

                main_value = str(output_row.get(main_key, '') or '')
                if not main_value:
                    continue

                matched_row = None

                if match_type == 'regex':
                    compiled_patterns = lookup_info.get('compiled_patterns') or []
                    for compiled_re, lrow in compiled_patterns:
                        if compiled_re is not None:
                            if compiled_re.search(main_value):
                                matched_row = lrow
                                break
                        else:
                            # Literal fallback for patterns that failed to compile
                            raw = str(lrow.get(lookup_key, ''))
                            if raw == main_value:
                                matched_row = lrow
                                break
                else:
                    # O(1) dict lookup instead of DataFrame filtering
                    index = lookup_info.get('index')
                    if index is not None:
                        matched_row = index.get(main_value)

                # If match found, copy columns to output_row
                if matched_row is not None:
                    lookup_df = lookup_info['data']
                    source_columns = config.get('source_columns')
                    if source_columns is None:
                        source_columns = [c for c in lookup_df.columns if c != lookup_key]

                    for i, target_col in enumerate(columns):
                        if i < len(source_columns):
                            src_col = source_columns[i]
                            # Works for both pd.Series (has .index) and dict
                            if hasattr(matched_row, 'index'):
                                if src_col in matched_row.index:
                                    output_row[target_col] = str(matched_row[src_col])
                            elif src_col in matched_row:
                                output_row[target_col] = str(matched_row[src_col])

            except Exception as e:
                logger.warning(f"Component {self.id}: Error applying lookup {lookup_name}: {e}")

    # ------------------------------------------------------------------
    # Parsed fields
    # ------------------------------------------------------------------

    def _parse_field_value(self, output_field: Dict[str, Any], row_dict: Dict, input_columns: set) -> str:
        """Parse specific value from input field using regex, position, or split."""
        source = output_field.get('source', '')
        parse_config = output_field.get('parse_config', {})
        default_value = output_field.get('default', '')

        if source not in input_columns:
            return default_value

        raw = row_dict.get(source)
        if raw is None or (isinstance(raw, float) and raw != raw):
            return default_value
        source_value = str(raw)

        if 'regex' in parse_config:
            match = re.search(parse_config['regex'], source_value)
            if match:
                return match.group(parse_config.get('group', 1))

        elif 'position' in parse_config:
            pos = parse_config['position']
            return source_value[pos.get('start', 0):pos.get('end', len(source_value))]

        elif 'split' in parse_config:
            sp = parse_config['split']
            parts = source_value.split(sp.get('delimiter', ','))
            idx = sp.get('index', 0)
            if 0 <= idx < len(parts):
                return parts[idx]

        return default_value

    # ------------------------------------------------------------------
    # Calculated fields
    # ------------------------------------------------------------------

    def _calculate_field_value(self, output_field: Dict[str, Any], row_dict: Dict, input_columns: set) -> str:
        """Calculate field value using formula or logic."""
        calc_config = output_field.get('calc_config', {})
        calc_type = calc_config.get('type', '')

        if calc_type == 'concatenate':
            separator = calc_config.get('separator', '')
            values = []
            for f in calc_config.get('fields', []):
                if f in input_columns:
                    v = row_dict.get(f)
                    if v is not None and not (isinstance(v, float) and v != v):
                        values.append(str(v))
            return separator.join(values)

        elif calc_type == 'conditional':
            cf = calc_config.get('condition_field', '')
            if cf in input_columns:
                return (
                    calc_config.get('true_value', '')
                    if str(row_dict.get(cf, '')) == calc_config.get('condition_value', '')
                    else calc_config.get('false_value', '')
                )

        elif calc_type == 'date_extraction':
            sf = calc_config.get('source_field', '')
            if sf in input_columns:
                v = row_dict.get(sf)
                if v is not None and not (isinstance(v, float) and v != v):
                    return self._extract_date_component(str(v), calc_config.get('component', 'date'))

        return output_field.get('default', '')

    # ------------------------------------------------------------------
    # Python expression evaluation (pre-compiled code objects)
    # ------------------------------------------------------------------

    def _evaluate_python_expression(
        self,
        output_field: Dict[str, Any],
        row_dict: Dict[str, Any],
        working_row: Dict[str, Any],
    ) -> str:
        """
        Evaluate a Python expression using a pre-compiled code object.

        'input_row' and 'computed' are available inside expressions.
        """
        field_name = output_field.get('name', 'unknown')
        default_value = output_field.get('default', '')

        code_obj = self._compiled_expressions.get(field_name)
        if code_obj is None:
            return default_value

        try:
            local_ns = {'input_row': row_dict, 'computed': working_row}
            result = eval(code_obj, _EVAL_GLOBALS_TEMPLATE, local_ns)
            return default_value if result is None else str(result)
        except Exception as e:
            logger.warning(f"Component {self.id}: Error evaluating expression for {field_name}: {e}")
            return default_value

    # ------------------------------------------------------------------
    # SWIFT-specific parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_date_component(date_value: str, component: str) -> str:
        """Extract specific component from date value."""
        parsed_date = None
        for fmt, min_len in _DATE_FORMATS:
            try:
                snippet = date_value[:min_len] if min_len and len(date_value) >= min_len else date_value
                parsed_date = datetime.strptime(snippet, fmt)
                break
            except ValueError:
                continue

        if parsed_date is None:
            return date_value

        return {
            'year': str(parsed_date.year),
            'month': str(parsed_date.month).zfill(2),
            'day': str(parsed_date.day).zfill(2),
            'date': parsed_date.strftime('%Y-%m-%d'),
            'time': parsed_date.strftime('%H:%M:%S'),
        }.get(component, date_value)

    def _apply_field_transformation(
        self,
        output_field: Dict[str, Any],
        source_value: str,
        row_dict: Dict[str, Any],
        input_columns: set,
    ) -> str:
        """Apply field-specific transformation."""
        transform_config = output_field.get('transform_config', {})
        transform_type = transform_config.get('type', '')

        if transform_type == 'balance_parse':
            return self._parse_balance_field(source_value, transform_config)
        elif transform_type == 'movement_parse':
            return self._parse_movement_field(source_value, transform_config, row_dict, input_columns)
        elif transform_type == 'lookup':
            return transform_config.get('lookup_table', {}).get(
                source_value, transform_config.get('default', source_value)
            )
        elif transform_type == 'format':
            ft = transform_config.get('format_type', 'upper')
            if ft == 'upper':
                return source_value.upper()
            elif ft == 'lower':
                return source_value.lower()
            elif ft == 'trim':
                return source_value.strip()
        return source_value

    @staticmethod
    def _parse_balance_field(balance_value: str, config: Dict[str, Any]) -> str:
        """Parse SWIFT balance field and extract specific component."""
        if not balance_value:
            return ''
        extract = config.get('extract', 'amount')
        m = _BALANCE_RE.match(balance_value.strip())
        if not m:
            return balance_value
        sign, date, currency = m.group(1), m.group(2), m.group(3)
        amount_raw = m.group(4).replace(',', '')
        return {
            'sign': 'C' if sign == 'C' else 'D',
            'date': date,
            'currency': currency,
            'amount': amount_raw,
            'full_text': f"{sign} {date} {currency} {amount_raw}",
        }.get(extract, balance_value)

    @staticmethod
    def _parse_movement_field(
        movement_value: str, config: Dict[str, Any],
        row_dict: Dict[str, Any], input_columns: set,
    ) -> str:
        """Parse SWIFT movement entry (field 61) and extract specific component."""
        if not movement_value:
            return ''
        extract = config.get('extract', 'amount')
        m = _MOVEMENT_RE.match(movement_value.strip())
        if not m:
            return movement_value
        entry_date = m.group(1)
        return {
            'entry_date': entry_date,
            'value_date': m.group(2) or entry_date,
            'debit_credit': m.group(3),
            'amount': m.group(4).replace(',', ''),
            'transaction_code': m.group(5) or '',
            'reference': (m.group(6) or '').strip(),
            'narrative': (m.group(7) or '') if m.lastindex and m.lastindex >= 7 else '',
        }.get(extract, movement_value)

    # ------------------------------------------------------------------
    # Post-processing
    # ------------------------------------------------------------------

    @staticmethod
    def _post_process_value(value: str, pp: Dict[str, Any]) -> str:
        """Apply post-processing to field value."""
        pt = pp.get('type', '')
        if pt == 'truncate':
            return value[:pp.get('max_length', 100)]
        elif pt == 'pad':
            length = pp.get('length', 10)
            pad_char = pp.get('pad_char', ' ')
            if pp.get('side', 'right') == 'left':
                return value.ljust(length, pad_char)
            else:
                return value.rjust(length, pad_char)
        elif pt == 'replace':
            return value.replace(pp.get('old', ''), pp.get('new', ''))
        return value

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def _write_output_file(self, output_df: pd.DataFrame, file_path: str) -> None:
        """Write transformed data to output file."""
        try:
            delimiter = self.config.get('delimiter', '|')
            encoding = self.config.get('output_encoding', 'utf-8')
            include_header = self.config.get('include_header', True)

            output_dir = os.path.dirname(file_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            # Replace NaN / sentinel strings in one pass
            output_df = output_df.fillna('').replace({'nan': '', 'NaN': '', 'None': ''})

            output_df.to_csv(
                file_path, sep=delimiter, encoding=encoding,
                index=False, header=include_header, na_rep='',
            )
            logger.info(f"Component {self.id}: Output written to {file_path}")
        except Exception as e:
            logger.error(f"Component {self.id}: Error writing output file: {e}")
            raise

    # ------------------------------------------------------------------
    # Default config
    # ------------------------------------------------------------------

    @staticmethod
    def _get_default_transform_config() -> Dict[str, Any]:
        """Get default transformation configuration for SWIFT data."""
        return {
            "transformer": {"name": "SWIFT to Business Format", "version": "1.0"},
            "input_fields": [
                "message_type", "sender_bic", "receiver_bic", "transaction_ref",
                "account_number", "opening_balance", "closing_balance",
                "transaction_data", "transaction_details",
            ],
            "output_fields": [
                {"name": "SIDE", "type": "constant", "value": "RECV", "default": "RECV"},
                {"name": "TERMID", "type": "direct", "source": "sender_bic", "default": ""},
                {"name": "DESTID", "type": "direct", "source": "receiver_bic", "default": ""},
                {"name": "OURREF", "type": "direct", "source": "transaction_ref", "default": ""},
                {"name": "THEIRREF", "type": "direct", "source": "transaction_ref", "default": ""},
                {"name": "SUBACC", "type": "direct", "source": "account_number", "default": ""},
                {
                    "name": "CURRENCY", "type": "transformation", "source": "opening_balance",
                    "transform_config": {"type": "balance_parse", "extract": "currency"},
                    "default": "USD",
                },
                {
                    "name": "AMOUNT", "type": "transformation", "source": "transaction_data",
                    "transform_config": {"type": "movement_parse", "extract": "amount"},
                    "default": "0.00",
                },
                {
                    "name": "VALUEDATE", "type": "transformation", "source": "transaction_data",
                    "transform_config": {"type": "movement_parse", "extract": "value_date"},
                    "default": "",
                },
            ],
        }
