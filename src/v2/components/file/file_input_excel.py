"""File input (Excel) component for V2 engine."""
import logging
import re
from typing import List

import polars as pl

from ..base import SourceComponent
from ..registry import REGISTRY
from .schema_types import TYPE_MAPPING, DATE_TYPES

logger = logging.getLogger(__name__)


@REGISTRY.register("file_input_excel")
class FileInputExcel(SourceComponent):
    """
    Read Excel files (.xlsx, .xls, .xlsb) as DataFrame.

    Excel files are always read eagerly (no lazy scanning). The base class
    wraps the result as LazyFrame for downstream processing.

    Supports multi-sheet reading: all sheets, specific sheets by name/index,
    or sheets matching a regex pattern. When reading multiple sheets, per-sheet
    operations (column range, skip_rows, footer_rows, limit) are applied
    independently to each sheet before concatenation.

    Config options:
        path: str - Path to Excel file (supports ${context.var} placeholders)
        sheet: str|int - Single sheet by name or 0-based index (default: first sheet)
        all_sheets: bool - Read all sheets (default: False)
        sheets: list - Sheet selection list, each entry has:
            - name: str - Sheet name (exact match)
            - index: int - Sheet 0-based index
            - regex: bool - Treat name as regex pattern (default: False)
        has_header: bool - Whether first row is a header (default: True)
        skip_rows: int - Rows to skip after header (default: 0)
        footer_rows: int - Rows to skip at end of each sheet (default: 0)
        limit: int|None - Max rows per sheet (default: None = all). 0 = zero rows.
        first_column: int|None - First column to read, 1-based (default: None = 1)
        last_column: int|None - Last column to read, 1-based inclusive (default: None = all)
        skip_empty_rows: bool - Filter out all-empty rows (default: False).
            Note: whitespace-only fields are treated as empty for Excel.
        trim_all: bool - Strip whitespace from all string columns (default: False)
        die_on_error: bool - Crash on bad data (default: True). False routes to reject.
        schema: list - Column definitions (required):
            - name: str - Column name (applied positionally, overrides file header)
            - type: str - Column type (string, integer, float, boolean, date, datetime, decimal)
            - date_pattern: str - Required for date/datetime columns
    """

    def validate(self) -> List[str]:
        """Validate component configuration."""
        errors = []
        if "path" not in self.config:
            errors.append("FileInputExcel requires 'path' in config")

        schema_config = self.config.get("schema")
        if not schema_config:
            errors.append("FileInputExcel requires 'schema' in config")
        else:
            for col in schema_config:
                col_type = col.get("type", "string").lower()
                if col_type in DATE_TYPES and not col.get("date_pattern"):
                    errors.append(
                        f"Schema column '{col['name']}' has type '{col_type}' "
                        f"but no 'date_pattern' specified"
                    )

        footer_rows = self.config.get("footer_rows")
        if footer_rows is not None and footer_rows < 0:
            errors.append(f"FileInputExcel 'footer_rows' must be >= 0 (got {footer_rows})")

        limit = self.config.get("limit")
        if limit is not None and limit < 0:
            errors.append(f"FileInputExcel 'limit' must be >= 0 (got {limit})")

        first_column = self.config.get("first_column")
        if first_column is not None and first_column < 1:
            errors.append(f"FileInputExcel 'first_column' must be >= 1 (got {first_column})")

        last_column = self.config.get("last_column")
        if last_column is not None and last_column < 1:
            errors.append(f"FileInputExcel 'last_column' must be >= 1 (got {last_column})")
        if first_column is not None and last_column is not None and last_column < first_column:
            errors.append("FileInputExcel 'last_column' must be >= 'first_column'")

        # Sheet config conflicts
        sheet = self.config.get("sheet")
        sheets = self.config.get("sheets")
        all_sheets = self.config.get("all_sheets", False)
        if sheet is not None and sheets is not None:
            errors.append("Cannot specify both 'sheet' and 'sheets'")
        if sheet is not None and all_sheets:
            errors.append("Cannot specify both 'sheet' and 'all_sheets'")
        if sheets is not None and all_sheets:
            errors.append("Cannot specify both 'sheets' and 'all_sheets'")

        if sheets:
            for i, entry in enumerate(sheets):
                if "name" not in entry and "index" not in entry:
                    errors.append(f"Sheet entry {i} must have 'name' or 'index'")
                if entry.get("regex", False) and "name" in entry:
                    try:
                        re.compile(entry["name"])
                    except re.error as e:
                        errors.append(
                            f"Sheet entry {i} has invalid regex pattern "
                            f"'{entry['name']}': {e}"
                        )

        return errors

    def _read_sheets(self, path: str, has_header: bool) -> pl.DataFrame:
        """Read one or more sheets, apply per-sheet pipeline, concatenate.

        Sheet resolution priority: all_sheets > sheets > sheet > default.
        """
        sheets_config = self.config.get("sheets")
        all_sheets = self.config.get("all_sheets", False)
        sheet = self.config.get("sheet")

        read_kwargs = {"source": path, "has_header": has_header}

        if all_sheets:
            sheet_dict = pl.read_excel(**read_kwargs, sheet_id=0)
            if not sheet_dict:
                return pl.DataFrame()
            return pl.concat([self._apply_per_sheet(df) for df in sheet_dict.values()])

        if sheets_config:
            resolved_names = self._resolve_sheet_names(path, sheets_config)
            if not resolved_names:
                raise ValueError("No sheets matched the given sheets config")
            dfs = []
            for name in resolved_names:
                df = pl.read_excel(**read_kwargs, sheet_name=name)
                dfs.append(self._apply_per_sheet(df))
            return pl.concat(dfs) if len(dfs) > 1 else dfs[0]

        if sheet is not None:
            if isinstance(sheet, int):
                read_kwargs["sheet_id"] = sheet + 1  # Polars uses 1-based sheet_id
            else:
                read_kwargs["sheet_name"] = sheet
            return self._apply_per_sheet(pl.read_excel(**read_kwargs))

        # Default: first sheet
        return self._apply_per_sheet(pl.read_excel(**read_kwargs))

    def _apply_per_sheet(self, df: pl.DataFrame) -> pl.DataFrame:
        """Apply per-sheet operations: column range, skip_rows, footer, limit."""
        # Column range
        first_column = self.config.get("first_column")
        last_column = self.config.get("last_column")
        if first_column is not None or last_column is not None:
            start = (first_column or 1) - 1
            if start >= len(df.columns):
                raise ValueError(
                    f"FileInputExcel: first_column ({first_column}) "
                    f"exceeds sheet column count ({len(df.columns)})"
                )
            end = last_column
            df = df.select(df.columns[start:end])

        # Skip rows
        skip_rows = self.config.get("skip_rows", 0)
        if skip_rows > 0:
            df = df.slice(skip_rows)

        # Footer
        footer_rows = self.config.get("footer_rows", 0)
        if footer_rows > 0:
            keep = max(len(df) - footer_rows, 0)
            df = df.head(keep)

        # Limit
        limit = self.config.get("limit")
        if limit is not None:
            df = df.head(limit)

        return df

    def _resolve_sheet_names(self, path: str, sheets_config: list) -> List[str]:
        """Resolve sheets config entries to concrete sheet names."""
        workbook_sheet_names = None  # Lazy-load only if needed

        resolved = []
        for entry in sheets_config:
            if "index" in entry:
                if workbook_sheet_names is None:
                    workbook_sheet_names = self._get_sheet_names(path)
                idx = entry["index"]
                if 0 <= idx < len(workbook_sheet_names):
                    resolved.append(workbook_sheet_names[idx])
                else:
                    raise ValueError(
                        f"Sheet index {idx} out of range "
                        f"(workbook has {len(workbook_sheet_names)} sheets)"
                    )
            elif "name" in entry:
                if entry.get("regex", False):
                    if workbook_sheet_names is None:
                        workbook_sheet_names = self._get_sheet_names(path)
                    pattern = re.compile(entry["name"])
                    matches = [s for s in workbook_sheet_names if pattern.fullmatch(s)]
                    if not matches:
                        raise ValueError(
                            f"No sheets matched regex '{entry['name']}'"
                        )
                    resolved.extend(matches)
                else:
                    resolved.append(entry["name"])

        return resolved

    @staticmethod
    def _get_sheet_names(path: str) -> List[str]:
        """List sheet names from an Excel workbook using fastexcel (calamine)."""
        import fastexcel
        reader = fastexcel.read_excel(path)
        return reader.sheet_names

    def _read(self) -> pl.DataFrame:
        """Read Excel file and return as DataFrame.

        Per-sheet pipeline (in _apply_per_sheet):
          column range -> skip_rows -> footer -> limit

        Post-concat pipeline (below):
          1. rename columns from schema
          2. skip_empty_rows
          3. trim_all
          4. type casting
        """
        path = self.resolve_context(self.config.get("path", ""))
        has_header = self.config.get("has_header", True)
        skip_empty = self.config.get("skip_empty_rows", False)
        trim_all = self.config.get("trim_all", False)
        schema_config = self.config.get("schema", [])

        logger.info(f"Reading Excel file: {path}")

        # Read sheet(s) with per-sheet pipeline
        df = self._read_sheets(path, has_header)

        # --- Post-concat pipeline ---

        # 1. Rename columns positionally from schema
        if schema_config:
            column_names = [col["name"] for col in schema_config]
            if len(df.columns) < len(column_names):
                raise ValueError(
                    f"FileInputExcel: schema defines {len(column_names)} columns "
                    f"but data only has {len(df.columns)} columns"
                )
            rename_map = {
                df.columns[i]: column_names[i]
                for i in range(len(column_names))
            }
            df = df.rename(rename_map)
            df = df.select(column_names)

        # 2. skip_empty_rows
        # Excel preserves whitespace in cells unlike CSV, so whitespace-only
        # cells are treated as empty (strip before comparing).
        if skip_empty and schema_config:
            schema_names = [col["name"] for col in schema_config]
            non_empty_cond = pl.lit(False)
            for col_name in schema_names:
                non_empty_cond = non_empty_cond | (
                    pl.col(col_name).is_not_null()
                    & (pl.col(col_name).cast(pl.Utf8).str.strip_chars() != "")
                )
            df = df.filter(non_empty_cond)

        # 3. trim_all
        if trim_all and schema_config:
            trim_exprs = []
            for col in schema_config:
                col_type = col.get("type", "string").lower()
                pl_type = TYPE_MAPPING.get(col_type, pl.Utf8)
                if pl_type == pl.Utf8 or col_type in DATE_TYPES:
                    trim_exprs.append(
                        pl.col(col["name"]).cast(pl.Utf8).str.strip_chars().alias(col["name"])
                    )
            if trim_exprs:
                df = df.with_columns(trim_exprs)

        # 4. Type casting (die_on_error=true only)
        die_on_error = self.config.get("die_on_error", True)
        if die_on_error and schema_config:
            casts = []
            date_exprs = []
            for col_def in schema_config:
                col_name = col_def["name"]
                col_type = col_def.get("type", "string").lower()
                if col_name not in df.columns:
                    continue
                if col_type in DATE_TYPES:
                    date_pattern = col_def.get("date_pattern")
                    if date_pattern:
                        if col_type == "datetime":
                            date_exprs.append(
                                pl.col(col_name).cast(pl.Utf8).str.to_datetime(date_pattern).alias(col_name)
                            )
                        else:
                            date_exprs.append(
                                pl.col(col_name).cast(pl.Utf8).str.to_date(date_pattern).alias(col_name)
                            )
                else:
                    target_type = TYPE_MAPPING.get(col_type, pl.Utf8)
                    if df[col_name].dtype != target_type:
                        casts.append(
                            pl.col(col_name).cast(target_type).alias(col_name)
                        )
            if casts:
                df = df.with_columns(casts)
            if date_exprs:
                df = df.with_columns(date_exprs)

        logger.info(f"Read {len(df)} rows from Excel: {path}")
        return df
