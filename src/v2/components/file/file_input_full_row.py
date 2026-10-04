"""File input (full row) component for V2 engine."""
import logging
from typing import List

import polars as pl

from ..base import SourceComponent
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("file_input_full_row", "file_input_full")
class FileInputFullRow(SourceComponent):
    """
    Read a text file line by line, outputting each line as a single string column.

    Replicates Talend's tFileInputFullRow. No field parsing — each raw line
    becomes one record. Downstream components handle field extraction.

    Config options:
        path: str - Path to file (supports ${context.var} placeholders)
        schema: list - Single-column schema, e.g. [{"name": "line", "type": "string"}]
        row_separator: str - Line boundary character (default: '\\n')
        header_rows: int - Rows to skip at start (default: 0)
        footer_rows: int - Rows to skip at end (default: 0)
        limit: int - Max rows to read (default: None = all)
        skip_empty_rows: bool - Exclude blank lines (default: False)
        encoding: str - File encoding (default: 'utf8')
    """

    def validate(self) -> List[str]:
        """Validate component configuration."""
        errors = []
        if "path" not in self.config:
            errors.append("FileInputFullRow requires 'path' in config")
        schema = self.config.get("schema")
        if not schema:
            errors.append("FileInputFullRow requires 'schema' in config")
        elif len(schema) != 1:
            errors.append(
                "FileInputFullRow schema must have exactly 1 column "
                f"(got {len(schema)})"
            )
        elif schema[0].get("type", "string").lower() not in ("string", "str", "id_string"):
            errors.append(
                "FileInputFullRow schema column must be of type 'string' "
                f"(got '{schema[0].get('type')}')"
            )
        return errors

    def _read(self) -> pl.LazyFrame:
        """Read file line by line, returning each line as a single string column."""
        path = self.resolve_context(self.config.get("path", ""))
        header_rows = self.config.get("header_rows", 0)
        footer_rows = self.config.get("footer_rows", 0)
        limit = self.config.get("limit")
        skip_empty_rows = self.config.get("skip_empty_rows", False)
        encoding = self.config.get("encoding", "utf8")
        schema_config = self.config.get("schema", [{"name": "line", "type": "string"}])
        col_name = schema_config[0]["name"]

        # Check for empty file upfront to avoid Polars NoDataError
        from pathlib import Path
        file_path = Path(path)
        if file_path.exists() and file_path.stat().st_size == 0:
            return pl.DataFrame({col_name: []}, schema={col_name: pl.Utf8}).lazy()

        if footer_rows > 0:
            # Footer skipping requires knowing total rows — read eagerly
            lf = self._read_with_footer(path, header_rows, footer_rows, encoding, col_name)
        else:
            # Lazy path — use scan_csv with null byte separator
            lf = pl.scan_csv(
                path,
                separator="\x00",
                has_header=False,
                skip_rows=header_rows,
                encoding=encoding,
                schema_overrides={"column_1": pl.Utf8},
            )
            # Rename auto-generated column to user's schema column name
            lf = lf.rename({"column_1": col_name})

        if skip_empty_rows:
            lf = lf.filter(
                pl.col(col_name).is_not_null()
                & (pl.col(col_name).str.strip_chars() != "")
            )

        if limit is not None and limit > 0:
            lf = lf.head(limit)

        logger.debug(f"FileInputFullRow scanning: {path}")
        return lf

    def _read_with_footer(
        self, path: str, header_rows: int, footer_rows: int,
        encoding: str, col_name: str,
    ) -> pl.LazyFrame:
        """Read file eagerly to support footer row skipping."""
        df = pl.read_csv(
            path,
            separator="\x00",
            has_header=False,
            skip_rows=header_rows,
            encoding=encoding,
            schema_overrides={"column_1": pl.Utf8},
        )
        df = df.rename({"column_1": col_name})

        if footer_rows > 0 and len(df) > footer_rows:
            df = df.head(len(df) - footer_rows)
        elif footer_rows > 0:
            df = df.head(0)

        return df.lazy()
