"""File input (delimited) component for v2 engine.

Reads delimited files (CSV, TSV, etc.) as LazyFrame via Polars
scan_csv/read_csv.  Restructured onto the v2 Component Standard
(Phase 7, COMP-05) with SUPPORTED_FEATURES declaration, NaN-to-null
normalization, per-column TRIMSELECT, encoding validation, and
ignore_errors wiring for die_on_error=False.

Config mapping:
  path: str              -- File path (supports ${context.var} placeholders)
  delimiter: str          -- Field delimiter (default: ',')
  quote_char: str|None    -- CSV quoting character (default: '"')
  has_header: bool        -- Whether file has a header row (default: True)
  skip_rows: int          -- Rows to skip at start (default: 0)
  footer_rows: int        -- Rows to skip at end (default: 0, triggers eager read)
  limit: int|None         -- Max rows to return (default: None = all)
  skip_empty_rows: bool   -- Filter out all-empty rows (default: False)
  trim_all: bool          -- Strip whitespace from all string columns (default: False)
  trim_columns: list      -- Per-column trim configs [{"column": "col", "trim": "both"|"left"|"right"}]
  encoding: str           -- File encoding (default: 'utf8'; only utf8/utf8-lossy supported)
  die_on_error: bool      -- Crash on bad data (default: True)
  nan_is_null: bool       -- Treat NaN strings as null (default: True)
  eol_char: str|None      -- Custom end-of-line character (default: None = Polars default)
  schema: list            -- Column definitions (required):
      - name: str, type: str, date_pattern: str (for date/datetime)
"""
import logging
from enum import Enum
from typing import ClassVar, Dict, List

import polars as pl

from ..base import SourceComponent
from ..capabilities import FeatureSupport, Support
from ..registry import REGISTRY
from .schema_types import TYPE_MAPPING, DATE_TYPES

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Feature support declaration (D-07 through D-30)
# ------------------------------------------------------------------

class FileInputDelimitedFeature(str, Enum):
    """Talend tFileInputDelimited features mapped to v2 support levels."""

    # FULL
    filename = "filename"
    fieldseparator = "fieldseparator"
    header = "header"
    footer = "footer"
    limit = "limit"
    remove_empty_row = "remove_empty_row"
    die_on_error = "die_on_error"
    trimall = "trimall"
    trimselect = "trimselect"
    rowseparator = "rowseparator"
    schema_typing = "schema_typing"
    reject_flow = "reject_flow"
    label = "label"
    # PARTIAL
    csv_option = "csv_option"
    uncompress = "uncompress"
    # UNSUPPORTED
    advanced_separator = "advanced_separator"
    encoding_non_utf8 = "encoding_non_utf8"
    multi_char_separator = "multi_char_separator"
    # NOT_PLANNED
    random = "random"
    enable_decode = "enable_decode"
    splitrecord = "splitrecord"
    use_header_as_is = "use_header_as_is"
    schema_opt_num = "schema_opt_num"
    check_fields_num = "check_fields_num"
    check_date = "check_date"
    tstatcatcher_stats = "tstatcatcher_stats"


# ------------------------------------------------------------------
# Component
# ------------------------------------------------------------------

@REGISTRY.register("file_input_delimited")
class FileInputDelimited(SourceComponent):
    """Read delimited files (CSV, TSV, etc.) as LazyFrame.

    Uses Polars scan_csv for lazy evaluation.  Falls back to eager
    read_csv only when footer_rows > 0 (must know total row count).

    Config options:
        path: str - Path to file (supports ${context.var} placeholders)
        delimiter: str - Field delimiter (default: ',')
        quote_char: str|None - CSV quoting character (default: '"'). None disables quoting.
        has_header: bool - Whether file has a header row (default: True)
        skip_rows: int - Number of rows to skip at start (default: 0)
        footer_rows: int - Number of rows to skip at end (default: 0). Triggers eager read.
        limit: int|None - Max rows to return (default: None = all). 0 = zero rows.
        skip_empty_rows: bool - Filter out all-empty rows (default: False)
        trim_all: bool - Strip whitespace from all string columns (default: False)
        trim_columns: list - Per-column trim configs:
            [{"column": "col_name", "trim": "both"|"left"|"right"}]
        encoding: str - File encoding (default: 'utf8'; only 'utf8' or 'utf8-lossy' accepted)
        die_on_error: bool - Crash on bad data (default: True). False routes to reject.
        nan_is_null: bool - Treat NaN strings as null (default: True).
            When True, 'NaN', 'nan', 'NAN' strings are read as null by Polars.
            Set to False only if NaN is a legitimate data value in your file.
        eol_char: str|None - Custom end-of-line character (default: None = Polars \\n).
        schema: list - Column definitions (required):
            - name: str - Column name (applied positionally, overrides file header)
            - type: str - Column type (string, integer, float, boolean, date, datetime, decimal)
            - date_pattern: str - Required for date/datetime columns
    """

    SUPPORTED_FEATURES: ClassVar[Dict[str, FeatureSupport]] = {
        FileInputDelimitedFeature.filename: FeatureSupport(
            support=Support.FULL,
            note="File path with ${context.var} placeholder substitution",
        ),
        FileInputDelimitedFeature.fieldseparator: FeatureSupport(
            support=Support.FULL,
            note="Single-byte field delimiter passed to Polars separator parameter",
        ),
        FileInputDelimitedFeature.header: FeatureSupport(
            support=Support.FULL,
            note="has_header + skip_rows for multi-row headers",
        ),
        FileInputDelimitedFeature.footer: FeatureSupport(
            support=Support.FULL,
            note="footer_rows triggers eager read path (must count total rows)",
        ),
        FileInputDelimitedFeature.limit: FeatureSupport(
            support=Support.FULL,
            note="n_rows parameter on scan_csv; limit=0 returns zero rows",
        ),
        FileInputDelimitedFeature.remove_empty_row: FeatureSupport(
            support=Support.FULL,
            note="Filter rows where all fields are null or empty string",
        ),
        FileInputDelimitedFeature.die_on_error: FeatureSupport(
            support=Support.FULL,
            note="True=crash on bad data; False=route to reject via SourceComponent._validate_schema()",
        ),
        FileInputDelimitedFeature.trimall: FeatureSupport(
            support=Support.FULL,
            note="Strip whitespace from all string/date columns via str.strip_chars()",
        ),
        FileInputDelimitedFeature.trimselect: FeatureSupport(
            support=Support.FULL,
            note="Per-column trim via str.strip_chars()/strip_chars_start()/strip_chars_end()",
        ),
        FileInputDelimitedFeature.rowseparator: FeatureSupport(
            support=Support.FULL,
            note="Mapped to Polars eol_char parameter (single-byte only)",
        ),
        FileInputDelimitedFeature.schema_typing: FeatureSupport(
            support=Support.FULL,
            note="schema_overrides built from config schema; never Polars inference",
        ),
        FileInputDelimitedFeature.reject_flow: FeatureSupport(
            support=Support.FULL,
            note="die_on_error=False + SourceComponent._validate_schema() splits main/reject",
        ),
        FileInputDelimitedFeature.label: FeatureSupport(
            support=Support.FULL,
            note="Component label for display/debugging",
        ),
        FileInputDelimitedFeature.csv_option: FeatureSupport(
            support=Support.PARTIAL,
            note="quote_char supported; ESCAPE_CHAR separate from TEXT_ENCLOSURE not supported",
        ),
        FileInputDelimitedFeature.uncompress: FeatureSupport(
            support=Support.PARTIAL,
            note="gzip (.gz) auto-detected by Polars; ZIP archives unsupported",
        ),
        FileInputDelimitedFeature.advanced_separator: FeatureSupport(
            support=Support.UNSUPPORTED,
            note="Locale-aware numeric parsing (THOUSANDS_SEPARATOR, DECIMAL_SEPARATOR) not available in Polars",
        ),
        FileInputDelimitedFeature.encoding_non_utf8: FeatureSupport(
            support=Support.UNSUPPORTED,
            note="Only utf8 and utf8-lossy supported; pre-convert non-UTF-8 files",
        ),
        FileInputDelimitedFeature.multi_char_separator: FeatureSupport(
            support=Support.UNSUPPORTED,
            note="Polars requires single-byte field separator",
        ),
        FileInputDelimitedFeature.random: FeatureSupport(
            support=Support.NOT_PLANNED,
            note="Use downstream sampling expressions instead",
        ),
        FileInputDelimitedFeature.enable_decode: FeatureSupport(
            support=Support.NOT_PLANNED,
            note="Hex/octal decoding has no Polars native support",
        ),
        FileInputDelimitedFeature.splitrecord: FeatureSupport(
            support=Support.NOT_PLANNED,
            note="Polars quote_char handles embedded newlines per RFC4180",
        ),
        FileInputDelimitedFeature.use_header_as_is: FeatureSupport(
            support=Support.NOT_PLANNED,
            note="Polars reads headers natively; no Studio UI hook needed",
        ),
        FileInputDelimitedFeature.schema_opt_num: FeatureSupport(
            support=Support.NOT_PLANNED,
            note="Talend Studio UI feature; not applicable to engine execution",
        ),
        FileInputDelimitedFeature.check_fields_num: FeatureSupport(
            support=Support.NOT_PLANNED,
            note="Polars truncate_ragged_lines has different semantics; not mapped",
        ),
        FileInputDelimitedFeature.check_date: FeatureSupport(
            support=Support.NOT_PLANNED,
            note="Date validation handled by schema typing via date_pattern",
        ),
        FileInputDelimitedFeature.tstatcatcher_stats: FeatureSupport(
            support=Support.NOT_PLANNED,
            note="tStatCatcher is a v1/Talend concept; use Python logging instead",
        ),
    }

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> List[str]:
        """Validate component configuration."""
        errors = []
        if "path" not in self.config:
            errors.append("FileInputDelimited requires 'path' in config")
        schema_config = self.config.get("schema")
        if not schema_config:
            errors.append("FileInputDelimited requires 'schema' in config")
        else:
            for col in schema_config:
                col_type = col.get("type", "string").lower()
                if col_type in DATE_TYPES and not col.get("date_pattern"):
                    errors.append(
                        f"Schema column '{col['name']}' has type '{col_type}' "
                        f"but no 'date_pattern' specified"
                    )
        delimiter = self.config.get("delimiter", ",")
        if delimiter not in ("\\t",) and len(delimiter) != 1:
            errors.append(
                f"FileInputDelimited 'delimiter' must be a single byte "
                f"(got '{delimiter}'). Polars does not support multi-char separators."
            )
        quote_char = self.config.get("quote_char", '"')
        if quote_char is not None and len(quote_char) != 1:
            errors.append(
                f"FileInputDelimited 'quote_char' must be a single character or null "
                f"(got '{quote_char}')"
            )
        footer_rows = self.config.get("footer_rows")
        if footer_rows is not None and footer_rows < 0:
            errors.append(
                f"FileInputDelimited 'footer_rows' must be >= 0 (got {footer_rows})"
            )
        limit = self.config.get("limit")
        if limit is not None and limit < 0:
            errors.append(
                f"FileInputDelimited 'limit' must be >= 0 (got {limit})"
            )
        # Encoding validation (D-01, D-02)
        encoding = self.config.get("encoding", "utf8")
        if encoding not in ("utf8", "utf8-lossy"):
            errors.append(
                f"FileInputDelimited encoding must be 'utf8' or 'utf8-lossy' "
                f"(got '{encoding}'). Non-UTF-8 encodings are unsupported; "
                f"pre-convert file to UTF-8."
            )
        eol_char = self.config.get("eol_char")
        if eol_char is not None and len(eol_char) != 1:
            errors.append(
                f"FileInputDelimited 'eol_char' must be a single byte "
                f"(got '{eol_char}' length={len(eol_char)}). "
                f"Polars does not support multi-byte line endings."
            )
        return errors

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def _read(self):
        """Read delimited file and return as LazyFrame or DataFrame."""
        path = self.resolve_context(self.config.get("path", ""))
        delimiter = self.config.get("delimiter", ",")
        quote_char = self.config.get("quote_char", '"')
        has_header = self.config.get("has_header", True)
        skip_rows = self.config.get("skip_rows", 0)
        footer_rows = self.config.get("footer_rows", 0)
        limit = self.config.get("limit")
        skip_empty_rows = self.config.get("skip_empty_rows", False)
        trim_all = self.config.get("trim_all", False)
        encoding = self.config.get("encoding", "utf8")
        schema_config = self.config.get("schema", [])

        # Handle tab delimiter
        if delimiter in ("\\t",):
            delimiter = "\t"

        # Build schema overrides from config (NEVER Polars inference)
        die_on_error = self.config.get("die_on_error", True)
        schema_overrides = {}
        new_columns = []
        date_columns = []  # (col_name, col_type, date_pattern) for lazy parsing

        if die_on_error:
            # Default: let Polars cast types directly (crash on failure)
            # Date/datetime columns: read as Utf8, then parse lazily
            for col in schema_config:
                col_type = col.get("type", "string").lower()
                if col_type in DATE_TYPES:
                    # CSV can't scan dates natively -- read as string first
                    schema_overrides[col["name"]] = pl.Utf8
                    date_pattern = col.get("date_pattern")
                    if date_pattern:
                        date_columns.append((col["name"], col_type, date_pattern))
                else:
                    pl_type = TYPE_MAPPING.get(col_type, TYPE_MAPPING.get(col["type"], pl.Utf8))
                    if pl_type:
                        schema_overrides[col["name"]] = pl_type
                new_columns.append(col["name"])
        else:
            # Safe mode: read everything as strings, base class validates later
            for col in schema_config:
                schema_overrides[col["name"]] = pl.Utf8
                new_columns.append(col["name"])

        # ---- Build csv_kwargs ----
        csv_kwargs = dict(
            separator=delimiter,
            quote_char=quote_char,
            has_header=has_header,
            skip_rows=skip_rows,
            encoding=encoding,
            schema_overrides=schema_overrides if schema_overrides else None,
        )

        # NaN-to-null normalization (D-05, D-06)
        nan_is_null = self.config.get("nan_is_null", True)
        if nan_is_null:
            csv_kwargs["null_values"] = ["NaN", "nan", "NAN"]

        # eol_char support (D-14)
        eol_char = self.config.get("eol_char")
        if eol_char:
            csv_kwargs["eol_char"] = eol_char

        # ignore_errors wiring for CSV parse errors
        # When die_on_error=False, parse-level errors become nulls which
        # _validate_schema() then detects and routes to the reject output.
        if not die_on_error:
            csv_kwargs["ignore_errors"] = True

        # ---- Read data ----
        if footer_rows > 0:
            # Eager path: need total row count to skip footer
            df = pl.read_csv(path, **csv_kwargs)
            if len(df) > footer_rows:
                df = df.head(len(df) - footer_rows)
            else:
                df = df.head(0)
            # Apply limit after footer slicing
            if limit is not None:
                df = df.head(limit)
            data = df
        else:
            # Lazy path: scan_csv
            if limit is not None and limit == 0:
                # Talend behavior: limit=0 means zero rows
                data = pl.scan_csv(path, **csv_kwargs).head(0)
            elif limit is not None and limit > 0:
                data = pl.scan_csv(path, n_rows=limit, **csv_kwargs)
            else:
                data = pl.scan_csv(path, **csv_kwargs)

        # Always rename columns to schema names (positional mapping)
        if new_columns:
            if isinstance(data, pl.DataFrame):
                existing = data.columns
            else:
                existing = data.collect_schema().names()
            rename_map = {old: new for old, new in zip(existing, new_columns)}
            data = data.rename(rename_map)

        # Skip empty rows: filter out rows where ALL fields are null or empty string
        if skip_empty_rows:
            schema_names = [col["name"] for col in schema_config]
            non_empty_cond = pl.lit(False)
            for col_name in schema_names:
                non_empty_cond = non_empty_cond | (
                    pl.col(col_name).is_not_null()
                    & (pl.col(col_name).cast(pl.Utf8) != "")
                )
            data = data.filter(non_empty_cond)

        # Trim all string columns
        if trim_all:
            trim_exprs = []
            for col in schema_config:
                col_type = col.get("type", "string").lower()
                # Trim string-type columns (including date columns still Utf8 at this point)
                pl_type = TYPE_MAPPING.get(col_type, pl.Utf8)
                if pl_type == pl.Utf8 or col_type in DATE_TYPES:
                    trim_exprs.append(
                        pl.col(col["name"]).str.strip_chars().alias(col["name"])
                    )
            if trim_exprs:
                data = data.with_columns(trim_exprs)

        # Per-column TRIMSELECT (D-13)
        trim_columns = self.config.get("trim_columns")
        if trim_columns and not trim_all:  # trim_all already covers everything
            trim_exprs = []
            for tc in trim_columns:
                col_name = tc.get("column", "")
                trim_type = tc.get("trim", "both")
                if trim_type == "left":
                    trim_exprs.append(pl.col(col_name).str.strip_chars_start().alias(col_name))
                elif trim_type == "right":
                    trim_exprs.append(pl.col(col_name).str.strip_chars_end().alias(col_name))
                else:  # "both" or default
                    trim_exprs.append(pl.col(col_name).str.strip_chars().alias(col_name))
            if trim_exprs:
                data = data.with_columns(trim_exprs)

        # Parse date/datetime columns lazily (stays in query plan)
        if date_columns:
            date_exprs = []
            for col_name, col_type, fmt in date_columns:
                if col_type == "datetime":
                    date_exprs.append(
                        pl.col(col_name).str.to_datetime(fmt).alias(col_name)
                    )
                else:
                    # 'date' and 'id_Date' both map to pl.Date
                    date_exprs.append(
                        pl.col(col_name).str.to_date(fmt).alias(col_name)
                    )
            data = data.with_columns(date_exprs)

        logger.debug(f"FileInputDelimited scanning: {path}")
        return data
