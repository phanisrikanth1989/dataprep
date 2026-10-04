"""File output (delimited) component for v2 engine.

Writes delimited files (CSV, TSV, etc.) by collecting a LazyFrame and
writing to disk via Polars ``DataFrame.write_csv()``.  Restructured
onto the v2 Component Standard (Phase 8, COMP-06) with
SUPPORTED_FEATURES declaration, single canonical registry name,
append-mode header suppression, delete-empty-file, error-if-exists,
and schema-based column selection/ordering.

Config mapping:
  path: str              -- Output file path (supports ${context.var} placeholders)
  delimiter: str          -- Field delimiter (default: ',')
  line_terminator: str    -- Row separator (default: '\\n')
  has_header: bool        -- Write header row (default: True)
  append: bool            -- Append to existing file (default: False)
  null_value: str         -- String to write for nulls (default: '')
  quote_char: str         -- Quote character, single char (default: '"')
  quote_style: str        -- Quoting strategy (default: 'necessary')
  datetime_format: str    -- Format for datetime columns (optional)
  date_format: str        -- Format for date columns (optional)
  delete_empty_file: bool -- Skip writing if 0 data rows (default: False)
  error_if_exists: bool   -- Raise error if output file exists (default: False)
  schema: list            -- Column selection/ordering/type validation (optional)
  label: str              -- Component label for display (optional)
"""
import logging
from enum import Enum
from pathlib import Path
from typing import ClassVar, Dict, List

import polars as pl

from ..base import SinkComponent
from ..capabilities import FeatureSupport, Support
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Feature support declaration (D-05 through D-28)
# ------------------------------------------------------------------

class FileOutputDelimitedFeature(str, Enum):
    """Talend tFileOutputDelimited features mapped to v2 support levels."""

    # FULL
    filename = "filename"
    fieldseparator = "fieldseparator"
    rowseparator = "rowseparator"
    append = "append"
    includeheader = "includeheader"
    create_dir = "create_dir"
    csv_option = "csv_option"
    delete_emptyfile = "delete_emptyfile"
    file_exist_exception = "file_exist_exception"
    csvrowseparator = "csvrowseparator"
    label = "label"
    schema_selection = "schema_selection"
    null_value = "null_value"
    datetime_format = "datetime_format"
    date_format = "date_format"
    # PARTIAL
    escape_char = "escape_char"
    # UNSUPPORTED
    compress = "compress"
    split_every = "split_every"
    advanced_separator = "advanced_separator"
    encoding_non_utf8 = "encoding_non_utf8"
    # NOT_PLANNED
    usestream = "usestream"
    flushonrow = "flushonrow"
    row_mode = "row_mode"
    os_line_separator = "os_line_separator"
    tstatcatcher_stats = "tstatcatcher_stats"


# ------------------------------------------------------------------
# Component
# ------------------------------------------------------------------

_VALID_QUOTE_STYLES = {"necessary", "always", "never", "non_numeric"}


@REGISTRY.register("file_output_delimited")
class FileOutputDelimited(SinkComponent):
    """Write data to delimited files (CSV, TSV, etc.).

    Collects the LazyFrame and writes to disk via Polars write_csv.

    Config options:
        path: str - Output path (supports ${context.var} placeholders)
        delimiter: str - Field delimiter (default: ',')
        line_terminator: str - Row separator (default: '\\n'). Supports '\\r\\n', '\\r'.
        has_header: bool - Write header row (default: True)
        append: bool - Append to existing file (default: False).
            Header is suppressed when appending to an existing file.
        null_value: str - String to write for nulls (default: '')
        quote_char: str - Quote character, single char (default: '"')
        quote_style: str - Quoting strategy (default: 'necessary').
            One of: 'necessary', 'always', 'never', 'non_numeric'.
        datetime_format: str - Format for datetime columns (optional)
        date_format: str - Format for date columns (optional)
        delete_empty_file: bool - Skip writing if 0 data rows (default: False)
        error_if_exists: bool - Raise error if output file exists (default: False).
            Cannot be combined with append=True.
        schema: list - Column selection, ordering, and type validation (optional).
            When defined, only schema columns are written, in schema order.
        label: str - Component label for display/debugging (optional).
    """

    SUPPORTED_FEATURES: ClassVar[Dict[str, FeatureSupport]] = {
        FileOutputDelimitedFeature.filename: FeatureSupport(
            support=Support.FULL,
            note="File path with ${context.var} placeholder substitution",
        ),
        FileOutputDelimitedFeature.fieldseparator: FeatureSupport(
            support=Support.FULL,
            note="Single-byte field delimiter passed to Polars separator parameter",
        ),
        FileOutputDelimitedFeature.rowseparator: FeatureSupport(
            support=Support.FULL,
            note="Line terminator passed to Polars line_terminator parameter",
        ),
        FileOutputDelimitedFeature.append: FeatureSupport(
            support=Support.FULL,
            note="Append mode with header suppression when appending to existing file",
        ),
        FileOutputDelimitedFeature.includeheader: FeatureSupport(
            support=Support.FULL,
            note="Polars include_header parameter on write_csv",
        ),
        FileOutputDelimitedFeature.create_dir: FeatureSupport(
            support=Support.FULL,
            note="Auto-create parent directories via Path.mkdir(parents=True)",
        ),
        FileOutputDelimitedFeature.csv_option: FeatureSupport(
            support=Support.FULL,
            note="quote_char + quote_style mapped from TEXT_ENCLOSURE and CSV_OPTION",
        ),
        FileOutputDelimitedFeature.delete_emptyfile: FeatureSupport(
            support=Support.FULL,
            note="Skip writing when 0 data rows",
        ),
        FileOutputDelimitedFeature.file_exist_exception: FeatureSupport(
            support=Support.FULL,
            note="Raise FileExistsError when output file exists and append=False",
        ),
        FileOutputDelimitedFeature.csvrowseparator: FeatureSupport(
            support=Support.FULL,
            note="CLOSED_LIST row separator mapped to line_terminator when CSV_OPTION=true",
        ),
        FileOutputDelimitedFeature.label: FeatureSupport(
            support=Support.FULL,
            note="Component label for display/debugging",
        ),
        FileOutputDelimitedFeature.schema_selection: FeatureSupport(
            support=Support.FULL,
            note="Schema-based column selection and ordering on write",
        ),
        FileOutputDelimitedFeature.null_value: FeatureSupport(
            support=Support.FULL,
            note="Polars null_value parameter on write_csv",
        ),
        FileOutputDelimitedFeature.datetime_format: FeatureSupport(
            support=Support.FULL,
            note="Polars datetime_format parameter on write_csv",
        ),
        FileOutputDelimitedFeature.date_format: FeatureSupport(
            support=Support.FULL,
            note="Polars date_format parameter on write_csv",
        ),
        FileOutputDelimitedFeature.escape_char: FeatureSupport(
            support=Support.PARTIAL,
            note="Polars uses RFC4180 quote doubling; custom escape characters not supported",
        ),
        FileOutputDelimitedFeature.compress: FeatureSupport(
            support=Support.UNSUPPORTED,
            note="Polars cannot write ZIP-compressed CSV; use gzip post-processing",
        ),
        FileOutputDelimitedFeature.split_every: FeatureSupport(
            support=Support.UNSUPPORTED,
            note="Polars has no native file splitting; split post-processing",
        ),
        FileOutputDelimitedFeature.advanced_separator: FeatureSupport(
            support=Support.UNSUPPORTED,
            note="Locale-aware numeric formatting (THOUSANDS_SEPARATOR, DECIMAL_SEPARATOR) not available in Polars",
        ),
        FileOutputDelimitedFeature.encoding_non_utf8: FeatureSupport(
            support=Support.UNSUPPORTED,
            note="Polars writes UTF-8 only; pre-convert or transcode downstream",
        ),
        FileOutputDelimitedFeature.usestream: FeatureSupport(
            support=Support.NOT_PLANNED,
            note="Java OutputStream sink has no Python equivalent",
        ),
        FileOutputDelimitedFeature.flushonrow: FeatureSupport(
            support=Support.NOT_PLANNED,
            note="Polars manages write buffering internally",
        ),
        FileOutputDelimitedFeature.row_mode: FeatureSupport(
            support=Support.NOT_PLANNED,
            note="Polars manages write buffering internally",
        ),
        FileOutputDelimitedFeature.os_line_separator: FeatureSupport(
            support=Support.NOT_PLANNED,
            note="v2 uses explicit line_terminator config",
        ),
        FileOutputDelimitedFeature.tstatcatcher_stats: FeatureSupport(
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
            errors.append("FileOutputDelimited requires 'path' in config")

        # Delimiter length validation
        delimiter = self.config.get("delimiter", ",")
        if delimiter not in ("\\t",) and len(delimiter) != 1:
            errors.append(
                f"FileOutputDelimited 'delimiter' must be a single character "
                f"(got '{delimiter}')"
            )

        quote_char = self.config.get("quote_char")
        if quote_char is not None and len(quote_char) != 1:
            errors.append(
                f"FileOutputDelimited 'quote_char' must be a single character (got '{quote_char}')"
            )

        quote_style = self.config.get("quote_style")
        if quote_style is not None and quote_style not in _VALID_QUOTE_STYLES:
            errors.append(
                f"FileOutputDelimited 'quote_style' must be one of {sorted(_VALID_QUOTE_STYLES)} "
                f"(got '{quote_style}')"
            )

        if self.config.get("append") and self.config.get("error_if_exists"):
            errors.append(
                "FileOutputDelimited cannot have both 'append' and 'error_if_exists' enabled"
            )

        line_terminator = self.config.get("line_terminator")
        if line_terminator is not None and line_terminator == "":
            errors.append("FileOutputDelimited 'line_terminator' must be non-empty")

        # Append-path-is-directory validation
        if self.config.get("append"):
            path_str = self.config.get("path", "")
            if path_str and not path_str.startswith("${"):
                resolved = Path(self.resolve_context(path_str))
                if resolved.exists() and resolved.is_dir():
                    errors.append(
                        f"FileOutputDelimited 'path' points to a directory, not a file "
                        f"(got '{resolved}'). When append=True, path must be an existing "
                        f"file or a new file path."
                    )

        return errors

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def consume(self, inputs: Dict[str, pl.LazyFrame]) -> None:
        """Collect LazyFrame and write to delimited file."""
        data = inputs.get("main")
        if data is None:
            return

        # Collect if lazy
        if isinstance(data, pl.LazyFrame):
            data = data.collect(**self._collect_kwargs)
        elif not isinstance(data, pl.DataFrame):
            raise TypeError(
                f"FileOutputDelimited expected LazyFrame or DataFrame, got {type(data)}"
            )

        # Schema-based column selection and ordering
        schema_config = self.config.get("schema")
        if schema_config:
            column_names = [col["name"] for col in schema_config]
            missing = [c for c in column_names if c not in data.columns]
            if missing:
                raise ValueError(
                    f"FileOutputDelimited schema columns not found in data: {missing}"
                )
            data = data.select(column_names)

        # Validate output schema if defined
        self._validate_output_schema(data)

        # Resolve path
        path = Path(self.resolve_context(self.config.get("path", "")))

        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Check error_if_exists
        if self.config.get("error_if_exists", False) and path.exists():
            raise FileExistsError(
                f"FileOutputDelimited: output file already exists: {path}"
            )

        # Check delete_empty_file
        if self.config.get("delete_empty_file", False) and len(data) == 0:
            logger.info(f"Skipping empty file (delete_empty_file=true): {path}")
            return

        # Build write options
        delimiter = self.config.get("delimiter", ",")
        include_header = self.config.get("has_header", True)
        null_value = self.config.get("null_value", "")
        datetime_fmt = self.config.get("datetime_format", None)
        date_fmt = self.config.get("date_format", None)
        line_terminator = self.config.get("line_terminator", "\n")
        quote_char = self.config.get("quote_char", '"')
        quote_style = self.config.get("quote_style", "necessary")

        # Handle tab delimiter
        if delimiter in ("\\t",):
            delimiter = "\t"

        # Handle append mode
        append = self.config.get("append", False)

        logger.info(f"Writing {len(data)} rows to: {path}")

        if append and path.exists():
            # Append to existing file -- suppress header
            csv_bytes = data.write_csv(
                None,  # write to string
                separator=delimiter,
                include_header=False,
                null_value=null_value,
                datetime_format=datetime_fmt,
                date_format=date_fmt,
                line_terminator=line_terminator,
                quote_char=quote_char,
                quote_style=quote_style,
            )
            with open(path, "ab") as f:
                f.write(csv_bytes.encode("utf-8"))
        else:
            # Normal write (or append to non-existent file = create)
            data.write_csv(
                path,
                separator=delimiter,
                include_header=include_header,
                null_value=null_value,
                datetime_format=datetime_fmt,
                date_format=date_fmt,
                line_terminator=line_terminator,
                quote_char=quote_char,
                quote_style=quote_style,
            )

        logger.info(f"Successfully wrote {len(data)} rows to: {path}")
