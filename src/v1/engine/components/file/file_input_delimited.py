"""Engine component for FileInputDelimited (tFileInputDelimited).

Reads a character-delimited flat file and outputs rows as a DataFrame.
Supports field/row separators, CSV RFC4180 mode, header/footer skipping,
per-column trim, field count validation, date validation, and REJECT flow.

Config keys consumed (25 total):
  filepath           (str, required)          -- absolute file path
  fieldseparator     (str, default ";")       -- field delimiter character
  row_separator      (str, default "\\n")     -- row delimiter
  encoding           (str, default "ISO-8859-15") -- file encoding
  header_rows        (int, default 0)         -- header rows to skip
  footer_rows        (int, default 0)         -- footer rows to skip
  limit              (str, default "")        -- max rows to read (empty=no limit)
  remove_empty_row   (bool, default True)     -- remove empty rows
  csv_option         (bool, default False)    -- enable RFC4180 CSV mode
  csv_row_separator  (str, default "\\n")     -- row separator for CSV mode
  escape_char        (str, default '"')       -- escape char (CSV mode)
  text_enclosure     (str, default '"')       -- quote char (CSV mode)
  trim_all           (bool, default False)    -- trim all string columns
  trim_select        (list, default [])       -- per-column trim settings
  check_fields_num   (bool, default False)    -- validate row field count
  check_date         (bool, default False)    -- validate date patterns
  die_on_error       (bool, default False)    -- halt on error
  uncompress         (bool, default False)    -- deferred: compressed reading
  split_record       (bool, default False)    -- deferred: multi-line fields
  random             (bool, default False)    -- deferred: random sampling
  nb_random          (int, default 10)        -- deferred: random sample size
  advanced_separator (bool, default False)    -- deferred: numeric separators
  enable_decode      (bool, default False)    -- deferred: hex/octal decode
  decode_cols        (list, default [])       -- deferred: columns to decode
  tstatcatcher_stats (bool, default False)    -- framework: stat collection
"""
import csv
import logging
import os
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, FileOperationError

logger = logging.getLogger(__name__)

# ---- Module-level constants ----

# Machine-readable reject error codes.
# Downstream consumers can depend on these exact strings.
_ERROR_FIELD_COUNT = "FIELD_COUNT"
_ERROR_TYPE_CONVERSION = "TYPE_CONVERSION"
_ERROR_DATE_FORMAT = "DATE_FORMAT"

# Rows per validation chunk to limit peak memory during row-level validation.
_VALIDATION_CHUNK_SIZE = 50000

# Deferred feature flags and their descriptions (D-21).
_DEFERRED_FEATURES = {
    "uncompress": "Compressed file reading",
    "split_record": "Multi-line field support",
    "random": "Random line sampling",
    "advanced_separator": "Advanced numeric separators",
    "enable_decode": "Hex/octal number decoding",
}


@REGISTRY.register("FileInputDelimited", "tFileInputDelimited")
class FileInputDelimited(BaseComponent):
    """tFileInputDelimited engine implementation.

    Reads a character-delimited flat file and outputs rows as a DataFrame.
    Supports semicolon (default), comma, tab, and custom delimiters.
    Provides REJECT flow for rows failing validation (field count, type
    conversion, date format).

    Config keys:
        filepath: Input file path (required).
        fieldseparator: Field delimiter (default ";").
        encoding: File encoding (default "ISO-8859-15").
        csv_option: Enable RFC4180 CSV mode (default False).
        check_fields_num: Validate row field count (default False).
        check_date: Validate date patterns (default False).
        trim_select: Per-column trim overrides (default []).
        trim_all: Trim all string columns (default False).
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
        """Read delimited file and return as DataFrame with optional REJECT flow.

        Args:
            input_data: Not used (source component).

        Returns:
            dict with 'main' (DataFrame) and 'reject' (DataFrame or None).

        Raises:
            FileOperationError: If file not found or read fails.
        """
        # ---- 1. Read config values (D-04, D-05) ----
        filepath = self.config.get("filepath", "")
        field_separator = self.config.get("fieldseparator", ";")
        row_separator = self.config.get("row_separator", "\\n")
        encoding = self.config.get("encoding", "ISO-8859-15")
        header_rows = int(self.config.get("header_rows", 0))
        footer_rows = int(self.config.get("footer_rows", 0))
        limit = self.config.get("limit", "")
        remove_empty_row = self.config.get("remove_empty_row", True)
        csv_option = self.config.get("csv_option", False)
        csv_row_separator = self.config.get("csv_row_separator", "\\n")
        escape_char = self.config.get("escape_char", '"')
        text_enclosure = self.config.get("text_enclosure", '"')
        trim_all = self.config.get("trim_all", False)
        trim_select = self.config.get("trim_select", [])
        check_fields_num = self.config.get("check_fields_num", False)
        check_date = self.config.get("check_date", False)
        die_on_error = self.config.get("die_on_error", False)

        # ---- 2. Warn on deferred features (D-21) ----
        for flag, description in _DEFERRED_FEATURES.items():
            if self.config.get(flag, False):
                logger.warning(
                    f"[{self.id}] {description} ('{flag}') is not yet "
                    f"implemented. Config flag will be ignored."
                )

        # ---- 3. Resolve filepath ----
        resolved_path = Path(filepath)
        if not resolved_path.exists():
            raise FileOperationError(
                f"[{self.id}] File not found: '{filepath}'"
            )

        # ---- 4. Set pre-execution globalMap variables (D-15) ----
        if self.global_map:
            self.global_map.put(f"{self.id}_FILENAME", str(resolved_path))
            self.global_map.put(f"{self.id}_ENCODING", encoding)

        # ---- 5. Unescape separators ----
        field_separator = self._unescape_separator(field_separator)
        row_separator = self._unescape_separator(row_separator)
        csv_row_separator = self._unescape_separator(csv_row_separator)

        # ---- 6. Read file ----
        schema_cols = (
            [col["name"] for col in self.output_schema]
            if self.output_schema
            else None
        )
        expected_col_count = len(self.output_schema) if self.output_schema else None

        if csv_option:
            df = self._read_csv_mode(
                filepath=str(resolved_path),
                field_separator=field_separator,
                encoding=encoding,
                header_rows=header_rows,
                footer_rows=footer_rows,
                text_enclosure=text_enclosure,
                escape_char=escape_char,
                schema_cols=schema_cols,
            )
        else:
            df = self._read_standard_mode(
                filepath=str(resolved_path),
                field_separator=field_separator,
                encoding=encoding,
                header_rows=header_rows,
                footer_rows=footer_rows,
                schema_cols=schema_cols,
            )

        logger.info(
            f"[{self.id}] Read {len(df)} raw rows from '{resolved_path.name}'"
        )

        # ---- 7. Apply limit ----
        if limit and str(limit).strip():
            try:
                limit_val = int(limit)
                if limit_val > 0:
                    df = df.head(limit_val)
            except (ValueError, TypeError):
                logger.warning(
                    f"[{self.id}] Invalid limit value '{limit}', ignoring"
                )

        # ---- 8. Remove empty rows ----
        if remove_empty_row:
            df = df.dropna(how="all")
            # Also drop rows where all columns are empty string
            mask = df.apply(
                lambda row: not all(
                    str(v).strip() == "" for v in row
                ),
                axis=1,
            )
            if not mask.empty:
                df = df[mask].reset_index(drop=True)

        # ---- 9. Apply TRIMSELECT / trim_all (D-11) ----
        df = self._apply_trim(df, trim_all, trim_select)

        # ---- 10. Validation and type conversion ----
        needs_row_validation = check_fields_num or check_date
        main_df, reject_df = self._validate_and_convert(
            df=df,
            check_fields_num=check_fields_num,
            check_date=check_date,
            expected_col_count=expected_col_count,
            needs_row_validation=needs_row_validation,
        )

        # ---- 11. Schema validation on good rows ----
        if self.output_schema and not main_df.empty:
            main_df = self.validate_schema(main_df, self.output_schema)

        # ---- 12. Return result ----
        return {"main": main_df, "reject": reject_df}

    # ------------------------------------------------------------------
    # File Reading Methods
    # ------------------------------------------------------------------

    def _read_standard_mode(
        self,
        filepath: str,
        field_separator: str,
        encoding: str,
        header_rows: int,
        footer_rows: int,
        schema_cols: Optional[list[str]],
    ) -> pd.DataFrame:
        """Read file using pandas (csv_option=False, no quoting).

        Args:
            filepath: Resolved file path.
            field_separator: Field delimiter.
            encoding: File encoding.
            header_rows: Number of header rows to skip.
            footer_rows: Number of footer rows to skip.
            schema_cols: Column names from schema, or None.

        Returns:
            DataFrame with all columns as string dtype.
        """
        read_params: dict[str, Any] = {
            "filepath_or_buffer": filepath,
            "sep": field_separator,
            "header": None,
            "skiprows": header_rows if header_rows > 0 else None,
            "skipfooter": footer_rows if footer_rows > 0 else 0,
            "encoding": encoding,
            "quoting": csv.QUOTE_NONE,
            "dtype": str,
            "keep_default_na": False,
        }

        if footer_rows > 0:
            read_params["engine"] = "python"

        if schema_cols:
            read_params["names"] = schema_cols

        try:
            df = pd.read_csv(**read_params)
        except Exception as e:
            raise FileOperationError(
                f"[{self.id}] Failed to read file '{filepath}': {e}"
            ) from e

        return df

    def _read_csv_mode(
        self,
        filepath: str,
        field_separator: str,
        encoding: str,
        header_rows: int,
        footer_rows: int,
        text_enclosure: str,
        escape_char: str,
        schema_cols: Optional[list[str]],
    ) -> pd.DataFrame:
        """Read file using Python csv.reader for RFC4180 compliance (csv_option=True).

        Uses deque-based sliding window for footer skipping to avoid loading
        the entire file into memory before discarding footer rows.

        Args:
            filepath: Resolved file path.
            field_separator: Field delimiter.
            encoding: File encoding.
            header_rows: Number of header rows to skip.
            footer_rows: Number of footer rows to skip.
            text_enclosure: Quote character.
            escape_char: Escape character.
            schema_cols: Column names from schema, or None.

        Returns:
            DataFrame with all columns as string dtype.
        """
        try:
            with open(filepath, "r", encoding=encoding, newline="") as f:
                # Configure csv.reader for RFC4180
                reader_kwargs: dict[str, Any] = {
                    "delimiter": field_separator,
                    "quotechar": text_enclosure,
                }
                if escape_char == text_enclosure:
                    reader_kwargs["doublequote"] = True
                else:
                    reader_kwargs["escapechar"] = escape_char
                    reader_kwargs["doublequote"] = False

                reader = csv.reader(f, **reader_kwargs)

                # Skip header rows
                for _ in range(header_rows):
                    try:
                        next(reader)
                    except StopIteration:
                        break

                # Read rows with deque-based footer skipping
                if footer_rows > 0:
                    rows: list[list[str]] = []
                    buffer: deque[list[str]] = deque(maxlen=footer_rows)
                    for row in reader:
                        if len(buffer) == footer_rows:
                            rows.append(buffer[0])
                        buffer.append(row)
                    # Rows remaining in buffer are footer rows -- discarded
                else:
                    rows = list(reader)

        except FileNotFoundError as e:
            raise FileOperationError(
                f"[{self.id}] File not found: '{filepath}'"
            ) from e
        except Exception as e:
            raise FileOperationError(
                f"[{self.id}] Failed to read file '{filepath}': {e}"
            ) from e

        if not rows:
            columns = schema_cols or []
            return pd.DataFrame(columns=columns).astype(str)

        df = pd.DataFrame(rows, dtype=str)
        if schema_cols and len(df.columns) == len(schema_cols):
            df.columns = schema_cols
        elif schema_cols:
            logger.warning(
                f"[{self.id}] Schema expects {len(schema_cols)} columns "
                f"but file has {len(df.columns)} columns per row"
            )

        return df

    # ------------------------------------------------------------------
    # Trim
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_trim(
        df: pd.DataFrame,
        trim_all: bool,
        trim_select: list[dict],
    ) -> pd.DataFrame:
        """Apply per-column or global trim to string columns.

        trim_select overrides trim_all when non-empty.

        Args:
            df: Input DataFrame (all string columns at this point).
            trim_all: Trim all string columns.
            trim_select: List of {column, trim} dicts.

        Returns:
            DataFrame with trimmed columns.
        """
        if not df.empty and trim_select:
            for entry in trim_select:
                col_name = entry.get("column", "")
                should_trim = entry.get("trim", False)
                if should_trim and col_name in df.columns:
                    df[col_name] = df[col_name].astype(str).str.strip()
        elif not df.empty and trim_all:
            obj_cols = df.select_dtypes(include=["object", "str"]).columns
            for col in obj_cols:
                df[col] = df[col].astype(str).str.strip()

        return df

    # ------------------------------------------------------------------
    # Validation and Type Conversion
    # ------------------------------------------------------------------

    def _validate_and_convert(
        self,
        df: pd.DataFrame,
        check_fields_num: bool,
        check_date: bool,
        expected_col_count: Optional[int],
        needs_row_validation: bool,
    ) -> tuple[pd.DataFrame, Optional[pd.DataFrame]]:
        """Validate rows and convert types. Route failures to reject.

        Fast path: When no row-level validation flags are set, uses vectorized
        type conversion directly (no per-row iteration).

        Chunked path: When validation is needed, processes in chunks of
        _VALIDATION_CHUNK_SIZE rows to limit peak memory.

        Args:
            df: Input DataFrame (string dtype).
            check_fields_num: Validate field count per row.
            check_date: Validate date patterns.
            expected_col_count: Expected number of columns from schema.
            needs_row_validation: Whether row-by-row validation is needed.

        Returns:
            Tuple of (main_df, reject_df or None).
        """
        if df.empty:
            return df, None

        if not self.output_schema:
            # No schema -- return as-is, no validation possible
            return df, None

        if not needs_row_validation:
            # Fast path: vectorized type conversion, no per-row iteration
            return self._fast_path_convert(df)

        # Chunked validation path
        return self._chunked_validate(
            df=df,
            check_fields_num=check_fields_num,
            check_date=check_date,
            expected_col_count=expected_col_count,
        )

    def _fast_path_convert(
        self, df: pd.DataFrame
    ) -> tuple[pd.DataFrame, Optional[pd.DataFrame]]:
        """Vectorized type conversion without per-row validation.

        Attempts column-wide conversion. If a column fails, falls back to
        per-row conversion for that column only, routing failures to reject.

        Args:
            df: Input DataFrame (string dtype).

        Returns:
            Tuple of (main_df, reject_df or None).
        """
        if not self.output_schema:
            return df, None

        result = df.copy()
        reject_rows: list[dict] = []

        for col_def in self.output_schema:
            col_name = col_def.get("name", "")
            col_type = col_def.get("type", "str")

            if col_name not in result.columns or col_type == "str":
                continue

            try:
                result[col_name] = self._vectorized_convert(
                    result[col_name], col_type
                )
            except (ValueError, TypeError):
                # Fall back to per-row conversion for this column
                good_mask = pd.Series(True, index=result.index)
                for idx in result.index:
                    val = result.at[idx, col_name]
                    try:
                        self._convert_value(str(val), col_def)
                    except (ValueError, TypeError):
                        good_mask[idx] = False
                        row_dict = {
                            c: str(result.at[idx, c]) for c in result.columns
                        }
                        row_dict["errorCode"] = _ERROR_TYPE_CONVERSION
                        row_dict["errorMessage"] = (
                            f"Cannot convert '{val}' to {col_type} for "
                            f"column '{col_name}' - Line: {idx + 1}"
                        )
                        reject_rows.append(row_dict)

                # Keep only good rows for continued processing
                bad_indices = ~good_mask
                if bad_indices.any():
                    result = result[good_mask].copy()

        reject_df = pd.DataFrame(reject_rows) if reject_rows else None
        return result, reject_df

    @staticmethod
    def _vectorized_convert(
        series: pd.Series, col_type: str
    ) -> pd.Series:
        """Convert a pandas Series to the target type vectorized.

        Args:
            series: Input Series (string values).
            col_type: Target type string.

        Returns:
            Converted Series.

        Raises:
            ValueError: If conversion fails for any value.
        """
        if col_type in ("int", "long"):
            return pd.to_numeric(series, errors="raise")
        elif col_type in ("float", "double"):
            return pd.to_numeric(series, errors="raise").astype(float)
        elif col_type in ("bool",):
            return series.map(
                {"true": True, "false": False, "True": True, "False": False,
                 "1": True, "0": False}
            )
        elif col_type == "datetime":
            return pd.to_datetime(series, errors="raise")
        return series

    def _chunked_validate(
        self,
        df: pd.DataFrame,
        check_fields_num: bool,
        check_date: bool,
        expected_col_count: Optional[int],
    ) -> tuple[pd.DataFrame, Optional[pd.DataFrame]]:
        """Process DataFrame in chunks, validating each row.

        Args:
            df: Input DataFrame (string dtype).
            check_fields_num: Validate field count.
            check_date: Validate date patterns.
            expected_col_count: Expected column count.

        Returns:
            Tuple of (main_df, reject_df or None).
        """
        good_chunks: list[pd.DataFrame] = []
        reject_chunks: list[pd.DataFrame] = []
        schema_cols = [col["name"] for col in self.output_schema]

        for start in range(0, len(df), _VALIDATION_CHUNK_SIZE):
            end = min(start + _VALIDATION_CHUNK_SIZE, len(df))
            chunk = df.iloc[start:end]

            chunk_good: list[dict] = []
            chunk_reject: list[dict] = []

            for row_idx, row in enumerate(chunk.itertuples(index=False)):
                line_num = start + row_idx + 1
                row_values = list(row)
                row_dict = {}
                for i, col_name in enumerate(chunk.columns):
                    if i < len(row_values):
                        row_dict[col_name] = row_values[i]

                rejected = False

                # a. CHECK_FIELDS_NUM (FILD-06)
                if check_fields_num and expected_col_count is not None:
                    non_empty = sum(
                        1 for v in row_values
                        if str(v).strip() != ""
                    )
                    if non_empty != expected_col_count:
                        reject_row = {
                            c: str(row_dict.get(c, "")) for c in schema_cols
                            if c in row_dict
                        }
                        reject_row["errorCode"] = _ERROR_FIELD_COUNT
                        reject_row["errorMessage"] = (
                            f"Field count mismatch: expected "
                            f"{expected_col_count}, got {non_empty} "
                            f"- Line: {line_num}"
                        )
                        chunk_reject.append(reject_row)
                        rejected = True

                if rejected:
                    continue

                # b. CHECK_DATE first (FILD-07) + c. Type conversion (FILD-03)
                converted_row: dict[str, Any] = {}
                for col_def in self.output_schema:
                    col_name = col_def.get("name", "")
                    if col_name not in row_dict:
                        continue

                    raw_val = str(row_dict[col_name])

                    # Date validation BEFORE type conversion so datetime
                    # columns that fail pattern get DATE_FORMAT, not
                    # TYPE_CONVERSION.
                    if (
                        check_date
                        and col_def.get("date_pattern")
                        and col_def.get("type") == "datetime"
                        and raw_val.strip()
                    ):
                        if not self._validate_date(
                            raw_val, col_def["date_pattern"]
                        ):
                            reject_row = {
                                c: str(row_dict.get(c, ""))
                                for c in schema_cols
                                if c in row_dict
                            }
                            reject_row["errorCode"] = _ERROR_DATE_FORMAT
                            reject_row["errorMessage"] = (
                                f"Date '{raw_val}' does not match pattern "
                                f"'{col_def['date_pattern']}' for column "
                                f"'{col_name}' - Line: {line_num}"
                            )
                            chunk_reject.append(reject_row)
                            rejected = True
                            break

                    # Type conversion
                    try:
                        converted_row[col_name] = self._convert_value(
                            raw_val, col_def
                        )
                    except (ValueError, TypeError):
                        reject_row = {
                            c: str(row_dict.get(c, "")) for c in schema_cols
                            if c in row_dict
                        }
                        reject_row["errorCode"] = _ERROR_TYPE_CONVERSION
                        reject_row["errorMessage"] = (
                            f"Cannot convert '{raw_val}' to "
                            f"{col_def.get('type', 'str')} for column "
                            f"'{col_name}' - Line: {line_num}"
                        )
                        chunk_reject.append(reject_row)
                        rejected = True
                        break

                if not rejected:
                    chunk_good.append(converted_row)

            # Convert chunk lists to DataFrames immediately
            if chunk_good:
                good_chunks.append(pd.DataFrame(chunk_good))
            if chunk_reject:
                reject_chunks.append(pd.DataFrame(chunk_reject))

        # Concatenate all chunks
        if good_chunks:
            main_df = pd.concat(good_chunks, ignore_index=True)
        else:
            main_df = pd.DataFrame(columns=schema_cols)

        if reject_chunks:
            reject_df = pd.concat(reject_chunks, ignore_index=True)
        else:
            reject_df = None

        return main_df, reject_df

    # ------------------------------------------------------------------
    # Static Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _unescape_separator(sep: str) -> str:
        """Convert escaped separator strings to actual characters.

        Args:
            sep: Separator string, possibly with escape sequences.

        Returns:
            Unescaped separator string.
        """
        mapping = {
            "\\n": "\n",
            "\\r\\n": "\r\n",
            "\\r": "\r",
            "\\t": "\t",
        }
        return mapping.get(sep, sep)

    @staticmethod
    def _convert_value(value: str, col_schema: dict) -> Any:
        """Convert a string value to the target type per schema.

        Args:
            value: Raw string value from file.
            col_schema: Schema dict with 'type' key.

        Returns:
            Converted value.

        Raises:
            ValueError: If conversion fails.
        """
        col_type = col_schema.get("type", "str")
        stripped = value.strip()

        if col_type == "str":
            return value

        # Handle empty values for non-string types
        if stripped == "":
            if col_schema.get("nullable", True):
                return None
            raise ValueError(f"Empty value for non-nullable column")

        if col_type in ("int", "long"):
            return int(float(stripped))
        elif col_type in ("float", "double"):
            return float(stripped)
        elif col_type == "bool":
            lower = stripped.lower()
            if lower in ("true", "1", "yes"):
                return True
            elif lower in ("false", "0", "no"):
                return False
            raise ValueError(f"Cannot convert '{value}' to bool")
        elif col_type == "datetime":
            pattern = col_schema.get("date_pattern", "")
            if pattern:
                return datetime.strptime(stripped, pattern)
            return pd.to_datetime(stripped)
        elif col_type == "Decimal":
            from decimal import Decimal
            return Decimal(stripped)
        elif col_type == "object":
            return value

        return value

    @staticmethod
    def _validate_date(value: str, pattern: str) -> bool:
        """Check whether a date string matches the given pattern.

        Args:
            value: Date string to validate.
            pattern: strptime-compatible date pattern.

        Returns:
            True if valid, False otherwise.
        """
        try:
            datetime.strptime(value.strip(), pattern)
            return True
        except (ValueError, TypeError):
            return False
