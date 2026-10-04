"""File output (Parquet) component for V2 engine."""
import logging
from pathlib import Path
from typing import Dict, List

import polars as pl

from ..base import SinkComponent
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("file_output_parquet")
class FileOutputParquet(SinkComponent):
    """
    Write data to Parquet files.

    Collects the LazyFrame and writes to Parquet format.

    Config options:
        path: str - Output path (supports ${context.var} placeholders)
        compression: str - Compression codec: 'zstd', 'lz4', 'snappy', 'gzip', 'none'
                          (default: 'zstd')
        row_group_size: int - Number of rows per row group (optional)
    """

    def validate(self) -> List[str]:
        """Validate component configuration."""
        errors = []
        if "path" not in self.config:
            errors.append("FileOutputParquet requires 'path' in config")
        compression = self.config.get("compression", "zstd")
        valid = ["zstd", "lz4", "snappy", "gzip", "none", "uncompressed"]
        if compression not in valid:
            errors.append(
                f"FileOutputParquet compression must be one of: {valid}"
            )
        return errors

    def consume(self, inputs: Dict[str, pl.LazyFrame]) -> None:
        """Collect LazyFrame and write to Parquet file."""
        data = inputs.get("main")
        if data is None:
            return

        # Collect if lazy
        if isinstance(data, pl.LazyFrame):
            data = data.collect(**self._collect_kwargs)
        elif not isinstance(data, pl.DataFrame):
            raise TypeError(
                f"FileOutputParquet expected LazyFrame or DataFrame, got {type(data)}"
            )

        # Validate output schema if defined
        self._validate_output_schema(data)

        # Resolve path
        path = Path(self.resolve_context(self.config.get("path", "")))

        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Get options
        compression = self.config.get("compression", "zstd")
        row_group_size = self.config.get("row_group_size", None)

        # Handle 'none' compression
        if compression == "none":
            compression = "uncompressed"

        logger.info(f"Writing {len(data)} rows to Parquet: {path}")

        data.write_parquet(
            path,
            compression=compression,
            row_group_size=row_group_size,
        )

        logger.info(f"Successfully wrote Parquet ({compression}): {path}")
