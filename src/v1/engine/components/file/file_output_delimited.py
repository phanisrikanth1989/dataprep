"""Engine component for FileOutputDelimited (tFileOutputDelimited).

Writes DataFrame data to delimited text files with configurable formatting,
encoding, and output options. Sink component -- receives input data and writes
to disk. Returns original input DataFrame as 'main' (passthrough contract).

Config keys consumed (25 total):
  filepath            (str, required)        -- output file path
  fieldseparator      (str, default ";")     -- field delimiter character
  row_separator       (str, default "\\n")   -- row separator for non-CSV mode
  encoding            (str, default "ISO-8859-15") -- file encoding
  include_header      (bool, default False)  -- write column names as first row
  append              (bool, default False)  -- append to existing file
  csv_option          (bool, default False)  -- enable CSV quoting mode
  escape_char         (str, default '"')     -- escape character in CSV mode
  text_enclosure      (str, default '"')     -- quote character in CSV mode
  os_line_separator   (bool, default True)   -- use os.linesep as row separator
  csvrowseparator     (str, default "LF")    -- row separator in CSV mode (LF/CR/CRLF)
  create_directory    (bool, default True)   -- create parent directories
  split               (bool, default False)  -- split output into multiple files
  split_every         (str, default "1000")  -- rows per split file
  delete_empty_file   (bool, default False)  -- delete file if no data written
  file_exist_exception (bool, default True)  -- raise if file exists in non-append mode
  die_on_error        (bool, default False)  -- fail on errors vs continue
  compress            (bool, default False)  -- [DEFERRED] ZIP compression
  usestream           (bool, default False)  -- [DEFERRED] Java OutputStream mode
  row_mode            (bool, default False)  -- [DEFERRED] per-row flush mode
  flushonrow          (bool, default False)  -- [DEFERRED] flush every N rows
  advanced_separator  (bool, default False)  -- [DEFERRED] numeric formatting
  thousands_separator (str, default ",")     -- [DEFERRED] thousands grouping
  decimal_separator   (str, default ".")     -- [DEFERRED] decimal point
  streamname          (str, default "outputStream") -- [DEFERRED] stream variable name

Phase 7.1 fixes applied:
- CR-06: multi-char + csv_option=True silently uses first char (Talend behavior); context vars deferred to _process
- CR-09 / ENG-CR-06: working copy used for file write; original input_data returned as main
- ENG-WR-04: _apply_date_patterns receives working copy only; original never mutated
- ENG-WR-05: non-CSV branch uses escapechar=None (Talend raw concatenation)
- ENG-WR-11: all bool config flags parsed via _bool() helper (handles JSON 'true'/'false')
- ENG-IN-04: empty-input CSV-mode header uses _enclose_field per column
"""
import csv
import logging
import os
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ComponentExecutionError, ConfigurationError, FileOperationError

logger = logging.getLogger(__name__)

# Deferred feature flags that log a warning when enabled
_DEFERRED_FEATURES = {
    "compress": "ZIP compression",
    "usestream": "OutputStream mode",
    "row_mode": "per-row flush mode",
    "flushonrow": "flush-on-row buffering",
    "advanced_separator": "Advanced numeric separators",
}

# D-06: Java expression marker -- if filepath or streamname starts with this,
# the value needs Java bridge evaluation (operator-bearing expression that
# ContextManager cannot resolve purely as a context variable substitution).
_JAVA_MARKER = "{{java}}"

# CSV row separator closed-list mapping
_CSV_ROW_SEPARATORS = {
    "LF": "\n",
    "CR": "\r",
    "CRLF": "\r\n",
}


@REGISTRY.register("FileOutputDelimited", "tFileOutputDelimited")
class FileOutputDelimited(BaseComponent):
    """tFileOutputDelimited engine implementation.

    Writes DataFrame data to delimited text files with configurable
    field/row separators, encoding, quoting, file splitting, and
    directory creation. Supports Talend-compatible defaults and
    FILE_EXIST_EXCEPTION safety check.

    This is a sink component: input_data is written to disk and then
    returned UNCHANGED as 'main'. The write path operates on a copy
    to preserve passthrough integrity (CR-09 / ENG-CR-06).

    Config keys:
        filepath: Output file path (required).
        fieldseparator: Field delimiter (default ";").
        encoding: File encoding (default "ISO-8859-15").
        include_header: Write header row (default False).
        append: Append to existing file (default False).
        csv_option: Enable CSV quoting mode (default False).
        split: Split output into multiple files (default False).
        split_every: Rows per split file (default "1000").
        file_exist_exception: Raise if file exists (default True).

    Note on non-CSV escaping (ENG-WR-05 / T-7.1-03-02):
        Non-CSV mode uses escapechar=None, matching Talend's raw string
        concatenation. If a value contains the field separator, the output
        will be ambiguous -- this is the caller's responsibility, matching
        Talend tFileOutputDelimited non-CSV behavior.
    """

    # ------------------------------------------------------------------
    # Streaming state
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

    # ------------------------------------------------------------------
    # Bool helper (ENG-WR-11)
    # ------------------------------------------------------------------

    @staticmethod
    def _bool(v: Any) -> bool:
        """Coerce a config value to bool, handling JSON string 'true'/'false'.

        JSON configs may carry boolean values as the strings "true" or "false"
        rather than Python True/False. Python's built-in bool("false") == True,
        which causes silent mis-routing. This helper normalises both forms.

        Args:
            v: Config value -- may be bool, int, or string.

        Returns:
            True if v is truthy and not the string literal 'false'/'0'/'no'.
        """
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes")
        return bool(v)

    # ------------------------------------------------------------------
    # Java Expression Resolution (D-06)
    # ------------------------------------------------------------------

    def _resolve_java_expr_param(self, value: str, name: str) -> str:
        """Evaluate a {{java}}-marked parameter via the Java bridge.

        If ``value`` starts with the ``{{java}}`` marker, strip the prefix and
        send the bare expression to the bridge for context-free evaluation.
        Uses a 1-row placeholder DataFrame because the bridge API is
        DataFrame-shaped and the expression has no row context.

        If ``value`` does not start with the marker, return it unchanged.

        Args:
            value: Config parameter value, possibly prefixed with ``{{java}}``.
            name: Parameter name (used in error messages).

        Returns:
            Evaluated string when marker is present; original value otherwise.

        Raises:
            ConfigurationError: If marker present but Java bridge is unavailable.
            ComponentExecutionError: If bridge evaluation raises.
        """
        if not isinstance(value, str) or not value.startswith(_JAVA_MARKER):
            return value

        if self.java_bridge is None:
            raise ConfigurationError(
                f"[{self.id}] Param '{name}' has value {value!r} requiring "
                f"Java bridge evaluation but Java bridge is unavailable. "
                f"Either start the bridge (java_config.enabled=true) or "
                f"remove the Java expression from the job config."
            )

        expr = value[len(_JAVA_MARKER):]
        # Pass a 1-row placeholder DataFrame with a dummy column; Arrow IPC
        # serialization requires at least one column (zero-column DFs don't
        # survive the round-trip).
        placeholder = pd.DataFrame([{"__placeholder__": 1}])
        try:
            eval_result = self.java_bridge.execute_tmap_preprocessing(
                df=placeholder,
                expressions={"__param__": expr},
                main_table_name="__none__",
                lookup_table_names=[],
                schema={},
            )
        except Exception as exc:
            raise ComponentExecutionError(
                self.id,
                f"Failed to evaluate '{name}' expression {expr!r}: "
                f"{type(exc).__name__}: {exc}",
                cause=exc,
            ) from exc

        if "__param__" not in eval_result or not len(eval_result["__param__"]):
            raise ComponentExecutionError(
                self.id,
                f"Bridge returned no result for '{name}' expression: {expr!r}",
            )
        return str(eval_result["__param__"][0])

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate component configuration.

        Raises:
            ConfigurationError: If filepath is missing.

        Note:
            Multi-character fieldseparator validation is intentionally deferred
            to _process() after context variable resolution.  Validating here
            would incorrectly measure unresolved context references such as
            ``context.OP_DELIMITER`` as multi-character strings.
        """
        if not self.config.get("filepath"):
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'filepath'"
            )

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Write DataFrame to delimited file(s) and pass through original input.

        Sink contract: the ORIGINAL input_data is returned as 'main' unchanged.
        All file writing operates on a working copy (df_out). This preserves
        passthrough integrity for downstream components that continue processing
        after this sink.

        Args:
            input_data: Input DataFrame from upstream component, or None.

        Returns:
            dict with 'main' (original input_data, unchanged) and 'reject' (None).

        Raises:
            FileOperationError: If file write fails or file exists when
                file_exist_exception is True.
        """
        # ---- Coerce all bool flags first (ENG-WR-11) ----
        csv_option = self._bool(self.config.get("csv_option", False))
        include_header = self._bool(self.config.get("include_header", False))
        append = self._bool(self.config.get("append", False))
        # Streaming mode: after the first chunk is written, force append so
        # subsequent chunks do not overwrite the file.  _streaming_write_started
        # is owned entirely by this component and is reset between execute() calls.
        if self._streaming_write_started:
            append = True
        create_directory = self._bool(self.config.get("create_directory", True))
        split = self._bool(self.config.get("split", False))
        delete_empty_file = self._bool(self.config.get("delete_empty_file", False))
        file_exist_exception = self._bool(self.config.get("file_exist_exception", True))
        os_line_separator = self._bool(self.config.get("os_line_separator", True))

        # ---- Read non-bool config values ----
        filepath = self.config.get("filepath", "")
        streamname = self.config.get("streamname", "outputStream")
        fieldseparator = self.config.get("fieldseparator", ";")
        row_separator = self.config.get("row_separator", "\\n")
        encoding = self.config.get("encoding", "ISO-8859-15")
        escape_char = self.config.get("escape_char", '"')
        text_enclosure = self.config.get("text_enclosure", '"')
        csvrowseparator = self.config.get("csvrowseparator", "LF")
        split_every = self.config.get("split_every", "1000")

        # ---- D-06: Honor {{java}} marker on expression-bearing string params ----
        # Context resolution (ContextManager.resolve_dict) already ran in execute()
        # and substituted plain context.var references. If filepath or streamname
        # still carry the {{java}} marker after context resolution, they contain
        # operator-bearing Java expressions (concatenation, ternaries, method calls)
        # that need bridge evaluation.
        filepath = self._resolve_java_expr_param(filepath, "filepath")
        streamname = self._resolve_java_expr_param(streamname, "streamname")

        # ---- Warn on deferred features (ENG-WR-11: use _bool) ----
        for flag, description in _DEFERRED_FEATURES.items():
            if self._bool(self.config.get(flag, False)):
                logger.warning(
                    f"[{self.id}] {description} ('{flag}') is not yet "
                    f"implemented. Config flag will be ignored."
                )

        # ---- Resolve filepath ----
        resolved_path = Path(filepath)

        # ---- Create directory ----
        if create_directory:
            resolved_path.parent.mkdir(parents=True, exist_ok=True)

        # ---- FILE_EXIST_EXCEPTION check ----
        if file_exist_exception and not append and resolved_path.exists():
            raise FileOperationError(
                f"[{self.id}] File already exists: '{filepath}'. "
                f"Set file_exist_exception=false or append=true to allow writing."
            )

        # ---- Build working copy for file write; original passes through (CR-09) ----
        # input_data is NEVER modified. df_out is the copy we write to disk.
        if input_data is not None and not input_data.empty:
            df_out = input_data.copy()
            # Apply date pattern formatting on the copy only (ENG-WR-04).
            # _apply_date_patterns receives a copy and returns the same copy with
            # datetime columns replaced by formatted strings. original is untouched.
            df_out = self._apply_date_patterns(df_out)
            # Apply Decimal precision formatting (schema precision -> fixed decimal places).
            df_out = self._format_decimal_columns(df_out)
            # Apply boolean casing (Python True/False -> Talend true/false).
            df_out = self._apply_boolean_format(df_out)
        else:
            df_out = input_data if input_data is not None else pd.DataFrame()

        # ---- Handle empty input ----
        if df_out is None or df_out.empty:
            self._handle_empty_input(
                resolved_path=resolved_path,
                encoding=encoding,
                fieldseparator=fieldseparator,
                include_header=include_header,
                delete_empty_file=delete_empty_file,
                os_line_separator=os_line_separator,
                csv_option=csv_option,
                csvrowseparator=csvrowseparator,
                row_separator=row_separator,
                text_enclosure=text_enclosure,
                escape_char=escape_char,
                input_data=input_data,
                append=append,
            )
            # Set globalMap variables
            if self.global_map:
                self.global_map.put(f"{self.id}_FILE_NAME", str(resolved_path))
                self.global_map.put(f"{self.id}_NB_LINE", 0)
            # CR-09: return ORIGINAL input_data, not df_out
            return {"main": input_data, "reject": None}

        # ---- Determine effective line separator ----
        effective_line_sep = self._resolve_line_separator(
            os_line_separator, csv_option, csvrowseparator, row_separator
        )

        # ---- Unescape field separator ----
        field_sep = _unescape_separator(fieldseparator)
        # Talend behavior: csv_option=True with multi-char delimiter → use first character only.
        # Python's csv module requires a single-char delimiter; Talend silently truncates.
        # Non-CSV raw mode supports multi-char natively via manual concatenation.
        if csv_option and len(field_sep) > 1:
            logger.warning(
                f"[{self.id}] Multi-character fieldseparator '{field_sep}' with csv_option=True: "
                f"using first character '{field_sep[0]}' (Talend behavior)"
            )
            field_sep = field_sep[0]

        # ---- Talend append-header rule: write header only on first write ----
        # When append=True, Talend writes the header only if the file does not
        # yet exist or is empty. Subsequent iterations append data rows only.
        if append and include_header and resolved_path.exists() and resolved_path.stat().st_size > 0:
            include_header = False

        # ---- SPLIT mode ----
        if split:
            rows_per_file = _safe_int(split_every, 1000)
            total_written = self._write_split(
                df_out, filepath, rows_per_file, field_sep,
                effective_line_sep, encoding, include_header, csv_option,
                text_enclosure, escape_char, append,
            )
        else:
            # ---- Write single file ----
            self._write_file(
                df_out, str(resolved_path), field_sep,
                effective_line_sep, encoding, include_header, csv_option,
                text_enclosure, escape_char, append,
            )
            total_written = len(df_out)

        # ---- Set globalMap variables ----
        if self.global_map:
            self.global_map.put(f"{self.id}_FILE_NAME", str(resolved_path))
            self.global_map.put(f"{self.id}_NB_LINE", total_written)

        logger.info(
            f"[{self.id}] Write complete: {total_written} rows to '{filepath}'"
        )

        # Mark that the file now exists with content so the next streaming chunk
        # appends instead of overwriting.
        self._streaming_write_started = True

        # CR-09 fix: return ORIGINAL input_data, NOT df_out (which has date-formatted cols)
        return {"main": input_data, "reject": None}

    # ------------------------------------------------------------------
    # Date Pattern Formatting
    # ------------------------------------------------------------------

    def _apply_date_patterns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Format datetime columns according to per-column ``date_pattern``.

        Mutates the passed DataFrame in place (callers MUST pass a copy).
        Walks ``self.input_schema`` and, for each column declared as a
        datetime with a ``date_pattern``, converts the column to a string
        formatted with that pattern. NaT values become empty strings to
        match Talend.

        Args:
            df: Working copy DataFrame to format in place.

        Returns:
            The same DataFrame with datetime columns replaced by formatted strings.
        """
        schema = getattr(self, "input_schema", None) or []
        if not schema:
            return df

        for col in schema:
            if not isinstance(col, dict):
                continue
            name = col.get("name")
            if not name or name not in df.columns:
                continue
            col_type = (col.get("type") or "").lower()
            pattern = col.get("date_pattern") or ""
            if not pattern or col_type not in ("date", "datetime"):
                continue
            series = df[name]
            if not pd.api.types.is_datetime64_any_dtype(series):
                # pd.to_datetime(errors="coerce") is contractually non-raising:
                # invalid values become NaT instead of triggering an exception.
                # Plan 14-08 (D-C5 STALE-FOD-001): the previously-pragmaed
                # `except Exception` catch-all here was defensive-only and
                # unreachable; deleted to honour the project rule "fix the
                # source, no fallbacks".
                series = pd.to_datetime(series, format=pattern, errors="coerce")
            formatted = series.dt.strftime(pattern)
            df[name] = formatted.where(series.notna(), "")
        return df

    def _format_decimal_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Format Decimal/BigDecimal columns to schema-defined precision.

        Talend tFileOutputDelimited writes BigDecimal values with exactly
        ``precision`` decimal places (e.g. precision=4 → "250.5000").
        Arrow deserializes these as Python decimal.Decimal with full internal
        precision, so without this step they render as "250.500000000000000000".

        When ``precision`` is -1 or absent for a ``decimal``/``bigdecimal``
        column, Talend outputs the value's natural precision (e.g. "13345.67",
        not "13345.670000000000000000").  This branch normalises the value by
        stripping trailing zeros.

        Args:
            df: Working copy DataFrame to format in place.

        Returns:
            The same DataFrame with Decimal columns replaced by fixed-point strings.
        """
        import decimal as _decimal
        import math

        schema = getattr(self, "input_schema", None) or []
        if not schema:
            return df

        for col in schema:
            if not isinstance(col, dict):
                continue
            name = col.get("name")
            if not name or name not in df.columns:
                continue
            col_type = (col.get("type") or "").lower()
            # Talend parity: 'precision' on float/double columns is schema
            # metadata only -- the value is written with its natural repr,
            # NOT rounded/zero-padded. Only Decimal/BigDecimal (and the
            # generic numeric aliases) get precision-driven formatting.
            if col_type not in ("decimal", "bigdecimal", "numeric", "number"):
                continue
            precision = col.get("precision")
            use_fixed = precision is not None and int(precision) >= 0  # type: ignore[arg-type]

            if use_fixed:
                p = int(precision)  # type: ignore[arg-type]

                def _fmt(x, _p=p):
                    if x is None:
                        return ""
                    try:
                        if isinstance(x, float) and math.isnan(x):
                            return ""
                        return f"{x:.{_p}f}"
                    except (TypeError, ValueError):
                        return str(x) if x is not None else ""

                df[name] = df[name].map(_fmt)

            elif col_type in ("decimal", "bigdecimal"):
                # No precision set — strip Arrow's scale-18 trailing zeros.
                def _fmt_natural(x):
                    if x is None:
                        return ""
                    try:
                        if isinstance(x, float) and math.isnan(x):
                            return ""
                        d = _decimal.Decimal(str(x))
                        return f"{d.normalize():f}"
                    except (TypeError, ValueError, _decimal.InvalidOperation):
                        return str(x) if x is not None else ""

                df[name] = df[name].map(_fmt_natural)

        return df

    def _apply_boolean_format(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert Python bool columns to lowercase Talend-style strings.

        Talend writes booleans as ``true``/``false`` (Java/lowercase).
        pandas serialises Python booleans as ``True``/``False`` (capitalised).
        This method converts schema-declared bool columns to lowercase strings
        before the DataFrame is passed to any CSV writer.

        Args:
            df: Working copy DataFrame to format in place.

        Returns:
            The same DataFrame with bool columns replaced by lowercase strings.
        """
        schema = getattr(self, "input_schema", None) or []
        if not schema:
            return df

        for col in schema:
            if not isinstance(col, dict):
                continue
            name = col.get("name")
            if not name or name not in df.columns:
                continue
            col_type = (col.get("type") or "").lower()
            if col_type not in ("bool", "boolean"):
                continue

            def _fmt_bool(x):
                if x is None:
                    return ""
                if isinstance(x, bool):
                    return "true" if x else "false"
                s = str(x).strip().lower()
                if s in ("true", "false"):
                    return s
                if s in ("", "nan", "none", "null"):
                    return ""
                return s

            df[name] = df[name].map(_fmt_bool)
        return df

    # ------------------------------------------------------------------
    # Empty Input Handling
    # ------------------------------------------------------------------

    def _handle_empty_input(
        self,
        resolved_path: Path,
        encoding: str,
        fieldseparator: str,
        include_header: bool,
        delete_empty_file: bool,
        os_line_separator: bool,
        csv_option: bool,
        csvrowseparator: str,
        row_separator: str,
        text_enclosure: str,
        escape_char: str,
        append: bool = False,
        input_data: Optional[pd.DataFrame] = None,
    ) -> None:
        """Handle empty or None input data.

        Writes header-only file (or empty file) as appropriate. Does NOT
        return a result dict -- caller is responsible for return value.

        Args:
            resolved_path: Resolved output file path.
            encoding: File encoding.
            fieldseparator: Field delimiter.
            include_header: Whether to write header row.
            delete_empty_file: Whether to delete file if no data.
            os_line_separator: Whether to use OS line separator.
            csv_option: Whether CSV mode is enabled (ENG-IN-04).
            csvrowseparator: CSV row separator value.
            row_separator: Row separator string.
            text_enclosure: Quote character for CSV mode (ENG-IN-04).
            escape_char: Escape character for CSV mode (ENG-IN-04).
            input_data: The empty DataFrame (may have column names), or None.
            append: When True, leave the existing file untouched. Talend
            parity: tFileOutputDelimited with append=true and 0 rows is
            a no-op (the file is neither truncated nor a header-only
            file is written, since prior writers may already have
            populated it).
        """

        # Append-mode no-op (Talend parity): a downstream writer with
        # append=true and 0 rows must NOT touch the file -- otherwise it
        # silently wipes content written by an earlier component pointing
        # at the same path. write_text/write_bytes both open in truncating
        # mode, so we have to short-circuit before either is reached.
        if append:
            logger.debug(
                f"[{self.id}] Empty input with append=True; leaving file "
                f"'{resolved_path}' untouched"
            )
            return

        if delete_empty_file:
            if resolved_path.exists():
                resolved_path.unlink()
                logger.info(f"[{self.id}] Deleted empty file: '{resolved_path}'")
            return

        effective_line_sep = self._resolve_line_separator(
            os_line_separator, csv_option, csvrowseparator, row_separator
        )
        field_sep = _unescape_separator(fieldseparator)
        if csv_option and len(field_sep) > 1:
            field_sep = field_sep[0]

        if include_header:
            # Use DataFrame columns first (empty DF retains column names),
            # fall back to schema attributes
            if input_data is not None and len(input_data.columns) > 0:
                columns = input_data.columns.tolist()
            else:
                columns = self._get_header_columns()
            if columns:
                # ENG-IN-04: apply _enclose_field in CSV mode
                if csv_option:
                    header_fields = [
                        self._enclose_field(str(c), text_enclosure, escape_char)
                        for c in columns
                    ]
                else:
                    header_fields = [str(c) for c in columns]
                header_line = field_sep.join(header_fields) + effective_line_sep
                resolved_path.write_text(header_line, encoding=encoding)
                logger.info(
                    f"[{self.id}] Wrote header-only file with "
                    f"{len(columns)} columns"
                )
            else:
                # No schema info available -- write empty file
                resolved_path.write_bytes(b"")
        else:
            # Write empty file (0 bytes)
            resolved_path.write_bytes(b"")

    # ------------------------------------------------------------------
    # File Writing
    # ------------------------------------------------------------------

    def _write_file(
        self,
        df: pd.DataFrame,
        filepath: str,
        field_sep: str,
        line_sep: str,
        encoding: str,
        include_header: bool,
        csv_option: bool,
        text_enclosure: str,
        escape_char: str,
        append: bool,
    ) -> None:
        """Write DataFrame to a single delimited file.

        Args:
            df: Working copy DataFrame to write (callers MUST pass a copy).
            filepath: Output file path.
            field_sep: Field delimiter character (already unescaped).
            line_sep: Line separator string.
            encoding: File encoding.
            include_header: Whether to write header row.
            csv_option: Whether to use CSV quoting mode.
            text_enclosure: Quote character for CSV mode.
            escape_char: Escape character for CSV mode.
            append: Whether to append to existing file.
        """
        mode = "a" if append else "w"

        try:
            if csv_option:
                # CSV quoting mode: field_sep is guaranteed single-char here
                # (multi-char was pre-truncated to first char in _process/_handle_empty_input).
                self._write_csv_mode(
                    df, filepath, field_sep, line_sep, encoding,
                    include_header, text_enclosure, escape_char, mode,
                )
            else:
                # Non-CSV mode (ANY separator length): raw string concatenation,
                # matching Talend tFileOutputDelimited. ENG-WR-12: routed through
                # _write_raw_mode for every separator length.
                #
                # The old single-char path used df.to_csv(quoting=QUOTE_NONE,
                # escapechar=None), which Python's csv writer rejects whenever a
                # value contains the separator or a newline -- raising
                # "_csv.Error: need to escape, but no escapechar set". That is the
                # opposite of the intended "raw mode": Talend writes the value
                # verbatim (ambiguous, but no crash). Raw concatenation does that
                # and also preserves literal backslashes (ENG-WR-05).
                self._write_raw_mode(
                    df, filepath, field_sep, line_sep, encoding,
                    include_header, csv_option, text_enclosure,
                    escape_char, mode,
                )
        except FileOperationError:
            raise
        except Exception as e:
            raise FileOperationError(
                f"[{self.id}] Failed to write file '{filepath}': {e}"
            ) from e

    def _write_csv_mode(
        self,
        df: pd.DataFrame,
        filepath: str,
        field_sep: str,
        line_sep: str,
        encoding: str,
        include_header: bool,
        text_enclosure: str,
        escape_char: str,
        mode: str,
    ) -> None:
        """Write DataFrame using Python csv.writer for RFC4180 compliance.

        Args:
            df: DataFrame to write.
            filepath: Output file path.
            field_sep: Field delimiter.
            line_sep: Line separator.
            encoding: File encoding.
            include_header: Whether to write header.
            text_enclosure: Quote character.
            escape_char: Escape character.
            mode: File open mode ('w' or 'a').
        """
        doublequote = (escape_char == text_enclosure)
        esc = escape_char if not doublequote else None

        with open(filepath, mode, newline="", encoding=encoding) as f:
            writer = csv.writer(
                f,
                delimiter=field_sep,
                quotechar=text_enclosure,
                escapechar=esc,
                doublequote=doublequote,
                quoting=csv.QUOTE_ALL,
                lineterminator=line_sep,
            )
            if include_header:
                writer.writerow(list(df.columns))
            for row in df.itertuples(index=False, name=None):
                writer.writerow(row)

    def _write_raw_mode(
        self,
        df: pd.DataFrame,
        filepath: str,
        field_sep: str,
        line_sep: str,
        encoding: str,
        include_header: bool,
        csv_option: bool,
        text_enclosure: str,
        escape_char: str,
        mode: str,
    ) -> None:
        """Write DataFrame with manual row joining for multi-char delimiters.

        Used when field_sep is longer than 1 character, since both
        pandas to_csv and csv.writer only accept single-char delimiters.
        Matches Talend's raw string concatenation behaviour.

        Args:
            df: DataFrame to write.
            filepath: Output file path.
            field_sep: Field delimiter (may be multi-char).
            line_sep: Line separator string.
            encoding: File encoding.
            include_header: Whether to write header row.
            csv_option: Whether to apply CSV quoting.
            text_enclosure: Quote character for CSV quoting.
            escape_char: Escape character for CSV quoting.
            mode: File open mode ('w' or 'a').
        """
        with open(filepath, mode, encoding=encoding, newline="") as f:
            if include_header:
                if csv_option:
                    header_fields = [
                        self._enclose_field(str(c), text_enclosure, escape_char)
                        for c in df.columns
                    ]
                else:
                    header_fields = [str(c) for c in df.columns]
                f.write(field_sep.join(header_fields))
                f.write(line_sep)

            for row in df.itertuples(index=False, name=None):
                if csv_option:
                    values = [
                        self._enclose_field(self._raw_str(v), text_enclosure, escape_char)
                        for v in row
                    ]
                else:
                    values = [self._raw_str(v) for v in row]
                f.write(field_sep.join(values))
                f.write(line_sep)

    @staticmethod
    def _raw_str(value: Any) -> str:
        """Stringify a value for raw (non-CSV) output.

        Nulls (None / NaN / NaT / pd.NA) render as an empty string -- matching
        Talend tFileOutputDelimited and the previous single-char ``to_csv``
        behaviour. Every other value uses ``str()``.

        Args:
            value: Cell value from the DataFrame row.

        Returns:
            Empty string for nulls; ``str(value)`` otherwise.
        """
        if value is None:
            return ""
        try:
            if pd.isna(value):
                return ""
        except (TypeError, ValueError):
            # pd.isna raises on array-like values; those are non-null scalars here.
            pass
        return str(value)

    @staticmethod
    def _enclose_field(value: str, text_enclosure: str, escape_char: str) -> str:
        """Enclose a field value in text_enclosure (QUOTE_ALL).

        Talend csv_option=true always wraps every field. Any occurrence of
        the enclosure character inside the value is escaped first.

        Args:
            value: Field value string.
            text_enclosure: Quote character.
            escape_char: Escape character.

        Returns:
            Enclosed field string.
        """
        if escape_char == text_enclosure:
            escaped = value.replace(
                text_enclosure, text_enclosure + text_enclosure
            )
        else:
            escaped = value.replace(
                text_enclosure, escape_char + text_enclosure
            )
        return text_enclosure + escaped + text_enclosure

    def _write_split(
        self,
        df: pd.DataFrame,
        filepath: str,
        rows_per_file: int,
        field_sep: str,
        line_sep: str,
        encoding: str,
        include_header: bool,
        csv_option: bool,
        text_enclosure: str,
        escape_char: str,
        append: bool,
    ) -> int:
        """Write DataFrame split across multiple files.

        Files are named: {stem}{index}{suffix} (e.g., output0.csv, output1.csv).

        Args:
            df: DataFrame to write.
            filepath: Base output file path.
            rows_per_file: Maximum rows per split file.
            field_sep: Field delimiter.
            line_sep: Line separator.
            encoding: File encoding.
            include_header: Whether to write header.
            csv_option: Whether to use CSV quoting mode.
            text_enclosure: Quote character.
            escape_char: Escape character.
            append: Whether to append to existing file.

        Returns:
            Total number of rows written.
        """
        total_written = 0

        for i in range(0, len(df), rows_per_file):
            chunk = df.iloc[i : i + rows_per_file]
            chunk_index = i // rows_per_file
            split_path = _split_filename(filepath, chunk_index)

            self._write_file(
                chunk, split_path, field_sep, line_sep, encoding,
                include_header, csv_option, text_enclosure, escape_char,
                append,
            )
            total_written += len(chunk)
            logger.debug(
                f"[{self.id}] Split file {chunk_index}: "
                f"{len(chunk)} rows to '{split_path}'"
            )

        return total_written

    # ------------------------------------------------------------------
    # Line Separator Resolution
    # ------------------------------------------------------------------

    def _resolve_line_separator(
        self,
        os_line_separator: bool,
        csv_option: bool,
        csvrowseparator: str,
        row_separator: str,
    ) -> str:
        """Determine the effective line separator.

        Args:
            os_line_separator: Whether to use OS line separator.
            csv_option: Whether CSV mode is enabled.
            csvrowseparator: CSV row separator value (LF/CR/CRLF).
            row_separator: Raw row separator string.

        Returns:
            Effective line separator string.
        """
        if os_line_separator:
            return os.linesep
        elif csv_option:
            return _resolve_csv_row_separator(csvrowseparator)
        else:
            return _unescape_separator(row_separator)

    # ------------------------------------------------------------------
    # Header Column Resolution
    # ------------------------------------------------------------------

    def _get_header_columns(self) -> list[str]:
        """Get header column names from output schema or input schema.

        Returns:
            List of column names, or empty list if no schema available.
        """
        # Try output_schema (set by engine)
        _output_schema = getattr(self, "output_schema", None)
        if _output_schema:
            return [col["name"] for col in _output_schema]

        # Try input_schema (set by engine)
        _input_schema = getattr(self, "input_schema", None)
        if _input_schema:
            return [col["name"] for col in _input_schema]

        return []


# ------------------------------------------------------------------
# Module-Level Helpers
# ------------------------------------------------------------------


def _unescape_separator(sep: str) -> str:
    """Convert escaped separator strings to actual characters.

    Args:
        sep: Separator string, possibly containing escape sequences.

    Returns:
        Unescaped separator string.
    """
    replacements = {
        "\\n": "\n",
        "\\r": "\r",
        "\\t": "\t",
        "\\r\\n": "\r\n",
    }
    # Try longest match first
    if sep in replacements:
        return replacements[sep]
    return sep


def _split_filename(filepath: str, index: int) -> str:
    """Generate split filename: {stem}{index}{suffix}.

    Args:
        filepath: Base file path.
        index: Split file index (0-based).

    Returns:
        Split file path string.
    """
    p = Path(filepath)
    return str(p.with_name(f"{p.stem}{index}{p.suffix}"))


def _resolve_csv_row_separator(csvrowseparator: str) -> str:
    """Convert CSV row separator closed-list value to actual characters.

    Args:
        csvrowseparator: One of "LF", "CR", "CRLF" or a raw string.

    Returns:
        Actual line separator characters.
    """
    result = _CSV_ROW_SEPARATORS.get(csvrowseparator)
    if result is not None:
        return result
    # Fall back to unescape for raw values
    return _unescape_separator(csvrowseparator)


def _safe_int(value: str, default: int) -> int:
    """Safely parse a string to int with a default fallback.

    Args:
        value: String to parse.
        default: Default value if parsing fails.

    Returns:
        Parsed integer or default.
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return default