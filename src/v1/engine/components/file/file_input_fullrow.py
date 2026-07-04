"""Engine component for FileInputFullRowComponent (tFileInputFullRow).

Reads each row of a file as a single string value. Every line becomes one
output record; the column name is taken from the schema definition (default
"line" matching Talend's schema default).

Config keys consumed (9 unique + 2 framework):
  filename           (str, required)               -- path to the input file
  row_separator      (str, default "\\n")          -- row boundary character(s)
  header_rows        (int, default 0)              -- header lines to skip
  footer_rows        (int, default 0)              -- footer lines to skip
  limit              (str, default "")             -- max rows; "" or "0" = unlimited
  remove_empty_row   (bool, default True)          -- drop strictly-empty ("") lines
  encoding           (str, default "ISO-8859-15")  -- file encoding (Talend default)
  random             (bool, default False)         -- random line extraction mode
  nb_random          (int, default 10)             -- number of random lines
  tstatcatcher_stats (bool, default False)         -- framework flag, no runtime effect
  label              (str, default "")             -- designer label, no runtime effect

Talend parity notes:
  - remove_empty_row tests line == "" strictly; whitespace-only lines are kept.
  - limit "0" is treated as unlimited (same as "").
  - random mode uses random.sample() without replacement.
  - Output column name comes from output_schema[0]["name"] when defined; falls
    back to "line" (matches Talend schema default column name).
  - DIE_ON_ERROR is NOT a Talend parameter for this component (_java.xml
    confirms its absence); the engine always propagates errors via
    FileOperationError / ConfigurationError.
"""
import logging
import random as _random_mod
from typing import Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, FileOperationError

logger = logging.getLogger(__name__)

# Normalise two-char JSON escape sequences to real characters.
# The converter emits e.g. "\\n" (backslash + n); engine must decode that.
_ESCAPE_MAP = {"\\n": "\n", "\\r": "\r", "\\t": "\t"}


@REGISTRY.register("FileInputFullRowComponent", "tFileInputFullRow")
class FileInputFullRowComponent(BaseComponent):
    """tFileInputFullRow engine implementation.

    Reads a text file and emits one row per line into a single-column
    DataFrame. Supports header/footer skipping, empty-row removal, row
    limiting, and random line extraction.

    Config keys:
        filename: Absolute path to the input file (required).
        row_separator: Line boundary. Supports ``\\n``, ``\\r``, ``\\t``
            escape sequences (default ``"\\n"``).
        header_rows: Number of lines to skip at the start (default 0).
        footer_rows: Number of lines to skip at the end (default 0).
        limit: Maximum rows to return; ``""`` or ``"0"`` = unlimited (default ``""``).
        remove_empty_row: Drop strictly-empty lines when True (default True).
        encoding: File encoding, e.g. ``"ISO-8859-15"`` (default ``"ISO-8859-15"``).
        random: When True, return a random sample instead of sequential lines
            (default False).
        nb_random: Sample size when ``random`` is True (default 10).
    """

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate structural config before expression resolution.

        Only checks key presence — content checks (file existence, limit
        numeric value) are deferred to ``_process()`` per Rule 12.

        Raises:
            ConfigurationError: If ``filename`` is absent or empty.
        """
        if not self.config.get("filename"):
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'filename'"
            )

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Read each line of the file as a single string.

        Args:
            input_data: Ignored. This is a source component with no
                data-flow input.

        Returns:
            dict with ``main`` key containing a single-column DataFrame.

        Raises:
            ConfigurationError: If ``filename`` resolves to an empty string.
            FileOperationError: If the file cannot be opened or read.
        """
        filename: str = self.config.get("filename", "")
        row_separator: str = self.config.get("row_separator", "\\n")
        header_rows: int = int(self.config.get("header_rows", 0) or 0)
        footer_rows: int = int(self.config.get("footer_rows", 0) or 0)
        limit_raw: str = str(self.config.get("limit", "") or "")
        remove_empty_row: bool = bool(self.config.get("remove_empty_row", True))
        encoding: str = self.config.get("encoding", "ISO-8859-15") or "ISO-8859-15"
        use_random: bool = bool(self.config.get("random", False))
        nb_random: int = int(self.config.get("nb_random", 10) or 10)

        # Post-resolution guard (Rule 12: defer content checks to _process)
        if not filename:
            raise ConfigurationError(
                f"[{self.id}] 'filename' resolved to an empty string"
            )

        # Decode literal escape sequences (e.g. "\\n" -> "\n")
        for escaped, real in _ESCAPE_MAP.items():
            row_separator = row_separator.replace(escaped, real)

        # Parse limit: "" and "0" both mean unlimited (Talend parity)
        limit: Optional[int] = None
        if limit_raw and limit_raw != "0":
            try:
                limit = int(limit_raw)
            except ValueError:
                raise ConfigurationError(
                    f"[{self.id}] 'limit' must be a numeric string, got {limit_raw!r}"
                )

        logger.info(
            f"[{self.id}] Reading file={filename!r} encoding={encoding!r} "
            f"sep={row_separator!r} header={header_rows} footer={footer_rows} "
            f"limit={limit} remove_empty={remove_empty_row} "
            f"random={use_random} nb_random={nb_random}"
        )

        # ---- Read file ----
        try:
            with open(filename, "r", encoding=encoding, newline="") as fh:
                content = fh.read()
        except FileNotFoundError as exc:
            raise FileOperationError(
                f"[{self.id}] File not found: {filename!r}"
            ) from exc
        except (OSError, UnicodeDecodeError) as exc:
            raise FileOperationError(
                f"[{self.id}] Failed to read {filename!r}: {exc}"
            ) from exc

        # ---- Split into lines ----
        # When row_separator is "\n" normalise \r\n first so Windows files
        # work correctly.  For custom separators, split verbatim.
        if row_separator == "\n":
            content = content.replace("\r\n", "\n").replace("\r", "\n")
        lines = content.split(row_separator)

        total_read = len(lines)
        logger.debug(f"[{self.id}] Raw line count after split: {total_read}")

        # ---- Header / footer skipping ----
        if header_rows > 0:
            lines = lines[header_rows:]
        if footer_rows > 0 and len(lines) >= footer_rows:
            lines = lines[:-footer_rows]
        elif footer_rows > 0:
            lines = []

        # ---- Remove strictly-empty lines (Talend: line == "", not strip()) ----
        if remove_empty_row:
            before = len(lines)
            lines = [ln for ln in lines if ln != ""]
            logger.debug(
                f"[{self.id}] Removed {before - len(lines)} empty lines"
            )

        # ---- Limit or random sampling ----
        if use_random:
            sample_size = min(nb_random, len(lines))
            lines = _random_mod.sample(lines, sample_size)
            logger.debug(
                f"[{self.id}] Random sample: {sample_size} lines selected"
            )
        elif limit is not None:
            lines = lines[:limit]
            logger.debug(f"[{self.id}] Limit applied: kept {len(lines)} lines")

        # ---- Determine output column name from schema (Talend default: "line") ----
        col_name = "line"
        output_schema = getattr(self, "output_schema", None)
        if output_schema:
            col_name = output_schema[0].get("name", "line")

        # ---- Build output DataFrame ----
        df = pd.DataFrame({col_name: lines})

        rows_ok = len(df)
        self._update_stats(total_read, rows_ok, 0)

        logger.info(f"[{self.id}] Complete: {rows_ok} rows from {filename!r}")

        return {"main": df}
