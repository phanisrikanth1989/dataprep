
"""
FileOutputPositional component - Write fixed-width (positional) files.

Talend equivalent: tFileOutputPositional
"""
import gzip
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, ComponentExecutionError, FileOperationError

logger = logging.getLogger(__name__)

# Normalise single-letter KEEP aliases to full Talend words.
_KEEP_ALIAS: dict[str, str] = {
    'A': 'ALL',
    'L': 'LEFT',
    'M': 'MIDDLE',
    'R': 'RIGHT',
    'C': 'LEFT',   # Legacy alias used by old engine code -- maps to LEFT (first N chars)
}

# Normalise full-word / mixed ALIGN aliases to canonical uppercase short form.
_ALIGN_ALIAS: dict[str, str] = {
    'LEFT':   'L',
    'RIGHT':  'R',
    'CENTER': 'C',
    'CENTRE': 'C',
}


@REGISTRY.register("FileOutputPositional", "tFileOutputPositional")
class FileOutputPositional(BaseComponent):
    """
    Write fixed-width (positional) files with configurable column formatting.

    This component creates fixed-width files where each column is written at a
    specific position with defined width, padding, and alignment. Supports
    compression, headers, and various data type formatting.

    Configuration:
        filepath (str): Output file path. Required.
        formats (list): Column format definitions with size, padding, alignment. Required.
        row_separator (str): Row separator string. Default: '\\n'
        append (bool): Append to existing file. Default: False
        include_header (bool): Include header row with column names. Default: False
        compress (bool): Use gzip compression. Default: False
        encoding (str): File encoding. Default: 'ISO-8859-15'
        create (bool): Create directory if not exists. Default: True
        flushonrow (bool): Flush after each row group. Default: False
        flushonrow_num (int): Number of rows per flush. Default: 1
        delete_empty_file (bool): Delete file if no data written. Default: False

    Inputs:
        main: DataFrame with data to write to positional file

    Outputs:
        main: Same DataFrame as input (pass-through)

    Statistics:
        NB_LINE: Total rows processed
        NB_LINE_OK: Rows successfully written
        NB_LINE_REJECT: Rows that failed (usually 0)

    Notes:
        - Supports LEFT, RIGHT, and CENTER alignment.
        - KEEP controls overflow truncation: ALL (no truncation), LEFT (keep
          first N chars), MIDDLE (keep middle N chars), RIGHT (keep last N chars).
        - Creates directories automatically if needed.
        - Supports escape sequences in row_separator.
    """

    # ------------------------------------------------------------------
    # Class constants
    # ------------------------------------------------------------------

    DEFAULT_ROW_SEPARATOR = '\n'
    DEFAULT_ENCODING = 'ISO-8859-15'
    DEFAULT_APPEND = False
    DEFAULT_INCLUDE_HEADER = False
    DEFAULT_COMPRESS = False
    DEFAULT_CREATE = True
    DEFAULT_FLUSH_ON_ROW = False
    DEFAULT_FLUSH_ON_ROW_NUM = 1
    DEFAULT_DELETE_EMPTY_FILE = False
    DEFAULT_PADDING_CHAR = ' '
    DEFAULT_ALIGN = 'L'
    DEFAULT_KEEP = 'ALL'
    DEFAULT_PRECISION = 8

    VALID_ALIGNMENTS = ['L', 'R', 'C']
    VALID_KEEP_OPTIONS = ['ALL', 'LEFT', 'MIDDLE', 'RIGHT']
    NUMERIC_TYPES = [
        'float', 'double', 'decimal','Decimal',  
        'id_Float', 'id_Double', 'id_BigDecimal',
    ]
    INTEGER_TYPES = [
        'int', 'long', 'integer',
        'id_Integer', 'id_Long',
    ]

    # ------------------------------------------------------------------
    # Configuration validation
    # ------------------------------------------------------------------

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Tracks whether _process() has already written the first chunk during
        # a streaming execute() call.  Set to True after the first successful
        # write so that subsequent chunks open the file in append mode instead
        # of overwriting it.  Cleared by reset() so iterate loops start fresh.
        self._streaming_write_started: bool = False

    def reset(self) -> None:
        """Reset component state for re-execution (iterate support)."""
        super().reset()
        self._streaming_write_started = False

    def _validate_config(self) -> None:
        """Validate structural shape of required config keys.

        Raises:
            ConfigurationError: If required keys are absent or have the
                wrong container type. Content checks (size values, enum
                membership) are deferred to _process() so that unresolved
                ``${context.X}`` references are accepted here.
        """
        if not self.config.get('filepath'):
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'filepath'"
            )

        formats = self.config.get('formats')
        if not formats:
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'formats'"
            )
        if not isinstance(formats, list):
            raise ConfigurationError(
                f"[{self.id}] Config 'formats' must be a list"
            )
        if len(formats) == 0:
            raise ConfigurationError(
                f"[{self.id}] Config 'formats' cannot be empty"
            )
        for i, fmt in enumerate(formats):
            if not isinstance(fmt, dict):
                raise ConfigurationError(
                    f"[{self.id}] formats[{i}] must be a dict"
                )
            if not (fmt.get('schema_column') or fmt.get('SCHEMA_COLUMN')):
                raise ConfigurationError(
                    f"[{self.id}] formats[{i}] missing 'schema_column'"
                )
            # Check key presence only -- value 0 is falsy but structurally present;
            # range validation (> 0) is deferred to _process content checks.
            if 'size' not in fmt and 'SIZE' not in fmt:
                raise ConfigurationError(
                    f"[{self.id}] formats[{i}] missing 'size'"
                )

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Write DataFrame to a fixed-width positional file.

        Args:
            input_data: DataFrame to write. None or empty triggers
                delete_empty_file logic.

        Returns:
            Dict with 'main' key containing the original input DataFrame
            (pass-through sink contract).

        Raises:
            ConfigurationError: If required configuration is invalid.
            FileOperationError: If file I/O fails.
        """
        logger.info("[%s] Positional file output started", self.id)

        # ---- 1. Read and resolve configuration -------------------------
        filepath = self.config.get('filepath', '')
        row_separator = self.config.get('row_separator', self.DEFAULT_ROW_SEPARATOR)
        append = self.config.get('append', self.DEFAULT_APPEND)
        # Streaming mode: after the first chunk is written, force append so
        # subsequent chunks do not overwrite the file.  _streaming_write_started
        # is owned entirely by this component and is reset between execute() calls.
        if self._streaming_write_started:
            append = True
        include_header = self.config.get('include_header', self.DEFAULT_INCLUDE_HEADER)
        compress = self.config.get('compress', self.DEFAULT_COMPRESS)
        encoding = self.config.get('encoding', self.DEFAULT_ENCODING)
        create = self.config.get('create', self.DEFAULT_CREATE)
        # Converter emits 'flushonrow' / 'flushonrow_num'; engine config may
        # also use 'flush_on_row' / 'flush_on_row_num' -- accept both.
        # Use explicit None checks so that falsy values (0, False) are honoured.
        _fr = self.config.get('flushonrow')
        flush_on_row = _fr if _fr is not None else self.config.get('flush_on_row', self.DEFAULT_FLUSH_ON_ROW)
        _frn = self.config.get('flushonrow_num')
        flush_on_row_num_raw = _frn if _frn is not None else self.config.get('flush_on_row_num', self.DEFAULT_FLUSH_ON_ROW_NUM)
        delete_empty_file = self.config.get('delete_empty_file', self.DEFAULT_DELETE_EMPTY_FILE)
        formats = self.config.get('formats', [])

        # ---- 2. Content validation (deferred from _validate_config) ----
        if not filepath:
            raise ConfigurationError(
                f"[{self.id}] Config 'filepath' must not be empty"
            )
        if not formats or not isinstance(formats, list):
            raise ConfigurationError(
                f"[{self.id}] Config 'formats' must be a non-empty list"
            )

        try:
            flush_on_row_num = int(flush_on_row_num_raw)
        except (ValueError, TypeError) as exc:
            raise ConfigurationError(
                f"[{self.id}] Config 'flushonrow_num' must be an integer"
            ) from exc
        if flush_on_row_num <= 0:
            raise ConfigurationError(
                f"[{self.id}] Config 'flushonrow_num' must be positive"
            )

        # Validate each format entry content and normalise values
        for i, fmt in enumerate(formats):
            size_raw = fmt.get('size') or fmt.get('SIZE')
            try:
                size_int = int(size_raw)
            except (ValueError, TypeError) as exc:
                raise ConfigurationError(
                    f"[{self.id}] formats[{i}] 'size' must be an integer, got {size_raw!r}"
                ) from exc
            if size_int <= 0:
                raise ConfigurationError(
                    f"[{self.id}] formats[{i}] 'size' must be positive, got {size_int}"
                )

            raw_align = (fmt.get('align') or fmt.get('ALIGN') or self.DEFAULT_ALIGN).upper()
            norm_align = _ALIGN_ALIAS.get(raw_align, raw_align)
            if norm_align not in self.VALID_ALIGNMENTS:
                raise ConfigurationError(
                    f"[{self.id}] formats[{i}] 'align' must be one of "
                    f"{self.VALID_ALIGNMENTS + list(_ALIGN_ALIAS)}, got {raw_align!r}"
                )

            raw_keep = (fmt.get('keep') or fmt.get('KEEP') or self.DEFAULT_KEEP).upper()
            norm_keep = _KEEP_ALIAS.get(raw_keep, raw_keep)
            if norm_keep not in self.VALID_KEEP_OPTIONS:
                raise ConfigurationError(
                    f"[{self.id}] formats[{i}] 'keep' must be one of "
                    f"{self.VALID_KEEP_OPTIONS + list(_KEEP_ALIAS)}, got {raw_keep!r}"
                )

        # ---- 3. Empty input handling ------------------------------------
        if input_data is None or (hasattr(input_data, 'empty') and input_data.empty):
            logger.info("[%s] Empty input received", self.id)
            # Precedence mirrors tFileOutputDelimited so the two sinks behave the
            # same on 0 rows:
            #   append            -> no-op (don't clobber a file an earlier
            #                        component wrote to the same path)
            #   delete_empty_file -> remove an existing file
            #   include_header    -> write a header-only file (0 data rows)
            #   otherwise         -> write nothing
            if append:
                logger.debug(
                    "[%s] Empty input with append=True; leaving '%s' untouched",
                    self.id, filepath,
                )
            elif delete_empty_file:
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                        logger.info("[%s] Deleted empty output file: %s", self.id, filepath)
                    except OSError as exc:
                        logger.warning("[%s] Could not delete file %s: %s", self.id, filepath, exc)
            elif include_header:
                # Reuse the normal writer with an empty frame: it emits the header
                # row and zero data rows, so we don't duplicate file/compress logic.
                if isinstance(row_separator, str):
                    row_separator = row_separator.encode('utf-8').decode('unicode_escape')
                self._write_positional_file(
                    pd.DataFrame(), filepath, formats, row_separator,
                    append, include_header, compress, encoding, create,
                    flush_on_row, flush_on_row_num,
                )
            self._update_stats(0, 0, 0)
            return {'main': pd.DataFrame()}

        # ---- 4. Decode escape sequences in row_separator ---------------
        if isinstance(row_separator, str):
            row_separator = row_separator.encode('utf-8').decode('unicode_escape')

        # ---- 5. Write file ---------------------------------------------
        data = input_data.fillna('')
        rows_in = len(data)
        logger.debug("[%s] Processing %d rows", self.id, rows_in)

        try:
            rows_written = self._write_positional_file(
                data, filepath, formats, row_separator,
                append, include_header, compress, encoding,
                create, flush_on_row, flush_on_row_num,
            )
        except (ConfigurationError, FileOperationError):
            raise
        except OSError as exc:
            raise FileOperationError(
                f"[{self.id}] I/O error writing {filepath}: {exc}"
            ) from exc
        except Exception as exc:
            raise ComponentExecutionError(
                self.id,
                f"Unexpected error writing positional file {filepath}: {exc}",
                exc,
            ) from exc

        # ---- 6. Post-write empty-file cleanup --------------------------
        if delete_empty_file and os.path.exists(filepath):
            if os.path.getsize(filepath) == 0:
                os.remove(filepath)
                logger.info("[%s] Deleted zero-byte output file: %s", self.id, filepath)

        self._update_stats(rows_in, rows_written, 0)
        logger.info(
            "[%s] Positional file output complete: %d rows written to %s",
            self.id, rows_written, filepath,
        )

        # Mark that the file now exists with content so the next streaming chunk
        # appends instead of overwriting.
        self._streaming_write_started = True

        return {'main': input_data}

    # ------------------------------------------------------------------
    # File writing
    # ------------------------------------------------------------------

    def _write_positional_file(
        self,
        data: pd.DataFrame,
        filepath: str,
        formats: List[Dict],
        row_separator: str,
        append: bool,
        include_header: bool,
        compress: bool,
        encoding: str,
        create: bool,
        flush_on_row: bool,
        flush_on_row_num: int,
    ) -> int:
        """Write *data* to *filepath* as a fixed-width text file.

        Returns:
            Number of data rows written.
        """
        # BUG-FOP-003: mode must honour both compress AND append flags.
        if compress:
            mode = 'ab' if append else 'wb'
        else:
            mode = 'a' if append else 'w'

        if create:
            directory = os.path.dirname(filepath)
            if directory and not os.path.exists(directory):
                logger.debug("[%s] Creating directory: %s", self.id, directory)
                os.makedirs(directory, exist_ok=True)

        # Build schema_map ONCE here -- not inside per-row formatting (PERF-FOP-002)
        schema = self.input_schema or []
        schema_map = {col['name']: col for col in schema}

        # Pre-compute normalised column format specs
        col_formats, col_names, col_types = self._prepare_column_formats(formats, schema_map)

        # Vectorise all column formatting (PERF-FOP-001 / PERF-FOP-003)
        formatted_cols = self._format_columns(data, col_names, col_formats, col_types, schema_map)

        # Concatenate columns into complete row strings
        row_strings = self._build_row_strings(formatted_cols, row_separator)

        file_handle = None
        try:
            if compress:
                logger.debug("[%s] Opening compressed file: %s", self.id, filepath)
                file_handle = gzip.open(filepath, mode)
            else:
                logger.debug("[%s] Opening file: %s", self.id, filepath)
                file_handle = open(filepath, mode, encoding=encoding)

            if include_header:
                logger.debug("[%s] Writing header row", self.id)
                header = self._format_header_row(col_names, col_formats, row_separator)
                if compress:
                    file_handle.write(header.encode(encoding))
                else:
                    file_handle.write(header)

            row_count = 0
            for line in row_strings:
                if compress:
                    file_handle.write(line.encode(encoding))
                else:
                    file_handle.write(line)
                row_count += 1
                if flush_on_row and (row_count % flush_on_row_num == 0):
                    file_handle.flush()

            file_handle.flush()
            file_handle.close()
            file_handle = None
            return row_count

        finally:
            if file_handle is not None:
                try:
                    file_handle.close()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Format preparation
    # ------------------------------------------------------------------

    def _prepare_column_formats(
        self,
        formats: List[Dict],
        schema_map: Dict[str, Dict],
    ) -> Tuple[List[Dict], List[str], List[str]]:
        """Build normalised column format specs from config *formats*.

        Args:
            formats: Raw format list from component config.
            schema_map: Mapping of column name -> schema entry (for type info).

        Returns:
            Tuple (col_formats, col_names, col_types).
        """
        col_formats: List[Dict] = []
        col_names: List[str] = []
        col_types: List[str] = []

        for fmt in formats:
            col = fmt.get('schema_column') or fmt.get('SCHEMA_COLUMN')
            size = int(fmt.get('size') or fmt.get('SIZE'))

            pad = fmt.get('padding_char') or fmt.get('PADDING_CHAR') or self.DEFAULT_PADDING_CHAR
            # Strip surrounding single-quotes (e.g. "' '")
            if isinstance(pad, str) and len(pad) == 3 and pad[0] == "'" and pad[-1] == "'":
                pad = pad[1]
            pad = pad or self.DEFAULT_PADDING_CHAR

            raw_align = (fmt.get('align') or fmt.get('ALIGN') or self.DEFAULT_ALIGN).upper()
            align = _ALIGN_ALIAS.get(raw_align, raw_align)   # Normalise LEFT->L, CENTER->C, etc.

            raw_keep = (fmt.get('keep') or fmt.get('KEEP') or self.DEFAULT_KEEP).upper()
            keep = _KEEP_ALIAS.get(raw_keep, raw_keep)        # Normalise A->ALL, C->LEFT, etc.

            col_names.append(col)
            col_formats.append({'size': size, 'pad': pad, 'align': align, 'keep': keep})
            col_types.append(schema_map.get(col, {}).get('type', 'str'))

        return col_formats, col_names, col_types

    # ------------------------------------------------------------------
    # Vectorised column formatting
    # ------------------------------------------------------------------

    def _format_columns(
        self,
        data: pd.DataFrame,
        col_names: List[str],
        col_formats: List[Dict],
        col_types: List[str],
        schema_map: Dict[str, Dict],
    ) -> List[pd.Series]:
        """Return one fixed-width-formatted Series per column."""
        formatted: List[pd.Series] = []

        for i, col in enumerate(col_names):
            fmt = col_formats[i]
            col_type = col_types[i]
            size = fmt['size']
            keep = fmt['keep']
            align = fmt['align']
            pad = fmt['pad']
            schema_entry = schema_map.get(col, {})

            # Source data as strings (missing columns become empty string)
            if col in data.columns:
                series: pd.Series = data[col].fillna('').astype(str)
            else:
                series = pd.Series([''] * len(data), index=data.index, dtype='object')

            # Type-specific value formatting
            if col_type in self.NUMERIC_TYPES:
                precision = schema_entry.get('precision', self.DEFAULT_PRECISION)
                def _fmt_float(v: str, _p: int = precision) -> str:
                    if v == '' or v == 'None':
                        return ''
                    try:
                        return f'{float(v):.{_p}f}'
                    except (ValueError, TypeError):
                        return v
                series = series.apply(_fmt_float)
            elif col_type in self.INTEGER_TYPES:
                def _fmt_int(v: str) -> str:
                    if v == '' or v == 'None':
                        return ''
                    try:
                        return str(int(float(v)))
                    except (ValueError, TypeError):
                        return v
                series = series.apply(_fmt_int)

            # KEEP: truncate when value exceeds column width
            if keep == 'LEFT':
                series = series.str[:size]
            elif keep == 'RIGHT':
                series = series.apply(
                    lambda s, _sz=size: s[max(0, len(s) - _sz):] if len(s) > _sz else s
                )
            elif keep == 'MIDDLE':
                def _keep_middle(s: str, _sz: int = size) -> str:
                    if len(s) <= _sz:
                        return s
                    start = (len(s) - _sz) // 2
                    return s[start:start + _sz]
                series = series.apply(_keep_middle)
            # ALL: no truncation -- value may overflow column width

            # Alignment / padding
            # str.ljust/rjust/center return value unchanged when len(val) >= size
            if align == 'R':
                series = series.str.rjust(size, pad)
            elif align == 'C':
                series = series.str.center(size, pad)
            else:  # 'L' (default)
                series = series.str.ljust(size, pad)

            # Pad/truncate to exactly 'size' chars for fixed-width output, EXCEPT
            # under KEEP=ALL where Talend tFileOutputPositional intentionally lets
            # the value overflow the column width (no truncation). LEFT/MIDDLE/RIGHT
            # were already clamped to <= size above, so this guard only spares ALL.
            if keep != 'ALL':
                series = series.str[:size]

            formatted.append(series)

        return formatted

    def _build_row_strings(
        self,
        formatted_cols: List[pd.Series],
        row_separator: str,
    ) -> List[str]:
        """Concatenate formatted column series into complete row strings."""
        if not formatted_cols:
            return []
        combined = formatted_cols[0].copy()
        for col_series in formatted_cols[1:]:
            combined = combined + col_series
        combined = combined + row_separator
        return combined.tolist()

    # ------------------------------------------------------------------
    # Header row
    # ------------------------------------------------------------------

    def _format_header_row(
        self,
        col_names: List[str],
        col_formats: List[Dict],
        row_separator: str,
    ) -> str:
        """Return the formatted header row string."""
        parts: List[str] = []
        for i, col in enumerate(col_names):
            fmt = col_formats[i]
            size = fmt['size']
            pad = fmt['pad']
            align = fmt['align']
            val = str(col)[:size]  # Truncate header name if longer than column width
            if align == 'R':
                val = val.rjust(size, pad)
            elif align == 'C':
                val = val.center(size, pad)
            else:
                val = val.ljust(size, pad)
            parts.append(val)
        return ''.join(parts) + row_separator