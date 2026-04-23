"""Engine component for FileOutputDelimited (tFileOutputDelimited).

Writes DataFrame data to delimited text files with configurable formatting,
encoding, and output options. Sink component -- receives input data and writes
to disk.

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
"""
import csv
import logging
import os
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, FileOperationError

logger = logging.getLogger(__name__)

# Deferred feature flags that log a warning when enabled
_DEFERRED_FEATURES = {
    "compress": "ZIP compression",
    "usestream": "OutputStream mode",
    "row_mode": "per-row flush mode",
    "flushonrow": "flush-on-row buffering",
    "advanced_separator": "Advanced numeric separators",
}

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
    """

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate component configuration.

        Raises:
            ConfigurationError: If filepath is missing.
        """
        if not self.config.get("filepath"):
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'filepath'"
            )

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Write DataFrame to delimited file(s).

        Args:
            input_data: Input DataFrame from upstream component, or None.

        Returns:
            dict with 'main' (pass-through of input) and 'reject' (None).

        Raises:
            FileOperationError: If file write fails or file exists when
                file_exist_exception is True.
        """
        # ---- Read config values ----
        filepath = self.config.get("filepath", "")
        fieldseparator = self.config.get("fieldseparator", ";")
        row_separator = self.config.get("row_separator", "\\n")
        encoding = self.config.get("encoding", "ISO-8859-15")
        include_header = self.config.get("include_header", False)
        append = self.config.get("append", False)
        csv_option = self.config.get("csv_option", False)
        escape_char = self.config.get("escape_char", '"')
        text_enclosure = self.config.get("text_enclosure", '"')
        os_line_separator = self.config.get("os_line_separator", True)
        csvrowseparator = self.config.get("csvrowseparator", "LF")
        create_directory = self.config.get("create_directory", True)
        split = self.config.get("split", False)
        split_every = self.config.get("split_every", "1000")
        delete_empty_file = self.config.get("delete_empty_file", False)
        file_exist_exception = self.config.get("file_exist_exception", True)

        # ---- Warn on deferred features ----
        for flag, description in _DEFERRED_FEATURES.items():
            if self.config.get(flag, False):
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

        # ---- Validate input against output schema ----
        output_schema = getattr(self, "output_schema", None)
        if input_data is not None and not input_data.empty and output_schema:
            input_data = self.validate_schema(input_data, output_schema)

        # ---- Apply per-column date_pattern from input schema ----
        # Talend writes datetime columns using the SimpleDateFormat pattern
        # declared on the output component's schema. The converter has
        # already translated Java tokens (e.g. yyyyMMdd) to Python strftime
        # tokens (e.g. %Y%m%d), so we just call .dt.strftime here.
        if input_data is not None and not input_data.empty:
            input_data = self._apply_date_patterns(input_data)

        # ---- Handle empty input ----
        if input_data is None or input_data.empty:
            return self._handle_empty_input(
                resolved_path, encoding, fieldseparator,
                include_header, delete_empty_file, os_line_separator,
                csv_option, csvrowseparator, row_separator,
                input_data,
            )

        # ---- Determine effective line separator ----
        effective_line_sep = self._resolve_line_separator(
            os_line_separator, csv_option, csvrowseparator, row_separator
        )

        # ---- Unescape field separator ----
        field_sep = _unescape_separator(fieldseparator)

        # ---- SPLIT mode ----
        if split:
            rows_per_file = _safe_int(split_every, 1000)
            total_written = self._write_split(
                input_data, filepath, rows_per_file, field_sep,
                effective_line_sep, encoding, include_header, csv_option,
                text_enclosure, escape_char, append,
            )
        else:
            # ---- Write single file ----
            self._write_file(
                input_data, str(resolved_path), field_sep,
                effective_line_sep, encoding, include_header, csv_option,
                text_enclosure, escape_char, append,
            )
            total_written = len(input_data)

        # ---- Set globalMap variables ----
        if self.global_map:
            self.global_map.put(f"{self.id}_FILE_NAME", str(resolved_path))
            self.global_map.put(f"{self.id}_NB_LINE", total_written)

        logger.info(
            f"[{self.id}] Write complete: {total_written} rows to '{filepath}'"
        )

        return {"main": input_data, "reject": None}

    # ------------------------------------------------------------------
    # Date Pattern Formatting
    # ------------------------------------------------------------------

    def _apply_date_patterns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Format datetime columns according to per-column ``date_pattern``.

        Walks ``self.input_schema`` (set by the engine from the component's
        ``schema.input``) and, for each column declared as a datetime with a
        ``date_pattern``, converts the column to a string formatted with
        that pattern. NaT values become empty strings to match Talend.

        Returns the (possibly modified) DataFrame; the original is not
        mutated.
        """
        schema = getattr(self, "input_schema", None) or []
        if not schema:
            return df

        modified = False
        new_df = df
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
                try:
                    series = pd.to_datetime(series, errors="coerce")
                except Exception:  # pragma: no cover - defensive
                    logger.warning(
                        f"[{self.id}] Column '{name}' could not be coerced "
                        f"to datetime; skipping date_pattern formatting."
                    )
                    continue
            if not modified:
                new_df = df.copy()
                modified = True
            formatted = series.dt.strftime(pattern)
            new_df[name] = formatted.where(series.notna(), "")
        return new_df

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
        input_data: Optional[pd.DataFrame] = None,
    ) -> dict:
        """Handle empty or None input data.

        Args:
            resolved_path: Resolved output file path.
            encoding: File encoding.
            fieldseparator: Field delimiter.
            include_header: Whether to write header row.
            delete_empty_file: Whether to delete empty file.
            os_line_separator: Whether to use OS line separator.
            csv_option: Whether CSV mode is enabled.
            csvrowseparator: CSV row separator value.
            row_separator: Row separator string.
            input_data: The empty DataFrame (may have column names), or None.

        Returns:
            dict with 'main' (None or empty DataFrame) and 'reject' (None).
        """
        if delete_empty_file:
            # Do not create file; delete if exists
            if resolved_path.exists():
                resolved_path.unlink()
                logger.info(f"[{self.id}] Deleted empty file: '{resolved_path}'")
            return {"main": None, "reject": None}

        effective_line_sep = self._resolve_line_separator(
            os_line_separator, csv_option, csvrowseparator, row_separator
        )
        field_sep = _unescape_separator(fieldseparator)

        if include_header:
            # Use DataFrame columns first (empty DF retains column names),
            # fall back to schema attributes
            if input_data is not None and len(input_data.columns) > 0:
                columns = input_data.columns.tolist()
            else:
                columns = self._get_header_columns()
            if columns:
                header_line = field_sep.join(columns) + effective_line_sep
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

        # Set globalMap variables
        if self.global_map:
            self.global_map.put(f"{self.id}_FILE_NAME", str(resolved_path))
            self.global_map.put(f"{self.id}_NB_LINE", 0)

        return {"main": None, "reject": None}

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
            df: DataFrame to write.
            filepath: Output file path.
            field_sep: Field delimiter character.
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
            if len(field_sep) > 1:
                # Multi-char delimiter: pandas and csv module only accept
                # single-char delimiters. Fall back to manual row joining
                # to match Talend's raw string concatenation behaviour.
                self._write_raw_mode(
                    df, filepath, field_sep, line_sep, encoding,
                    include_header, csv_option, text_enclosure,
                    escape_char, mode,
                )
            elif csv_option:
                self._write_csv_mode(
                    df, filepath, field_sep, line_sep, encoding,
                    include_header, text_enclosure, escape_char, mode,
                )
            else:
                df.to_csv(
                    filepath,
                    sep=field_sep,
                    header=include_header,
                    index=False,
                    encoding=encoding,
                    quoting=csv.QUOTE_NONE,
                    lineterminator=line_sep,
                    mode=mode,
                    escapechar="\\",
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
                f.write(field_sep.join(str(c) for c in df.columns))
                f.write(line_sep)

            for row in df.itertuples(index=False, name=None):
                if csv_option:
                    values = [
                        self._enclose_field(str(v), text_enclosure, escape_char)
                        for v in row
                    ]
                else:
                    values = [str(v) for v in row]
                f.write(field_sep.join(values))
                f.write(line_sep)

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
        if hasattr(self, "output_schema") and self.output_schema:
            return [col["name"] for col in self.output_schema]

        # Try input_schema (set by engine)
        if hasattr(self, "input_schema") and self.input_schema:
            return [col["name"] for col in self.input_schema]

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
