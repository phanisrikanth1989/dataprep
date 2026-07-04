"""Engine component for FileRowCount (tFileRowCount).

Opens a file and counts its rows using a configurable separator and encoding.
Result is published to globalMap as ``{id}_COUNT``. Produces no data flow output.

Config keys consumed (4 unique + 2 framework):
  filename           (str, required)              -- path to the file to count
  row_separator      (str, default "\\n")         -- row boundary character(s)
  ignore_empty_row   (bool, default False)         -- skip whitespace-only rows
  encoding           (str, default "ISO-8859-15") -- file encoding (Talend default)
  tstatcatcher_stats (bool, default False)         -- framework flag, no runtime effect
  label              (str, default "")             -- designer label, no runtime effect
"""
import logging
from typing import Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, FileOperationError

logger = logging.getLogger(__name__)

# Normalise literal escape sequences stored as two-char strings in JSON config.
# The converter emits e.g. "\\n" (backslash + n); engine must turn that into "\n".
_ESCAPE_MAP = {"\\n": "\n", "\\r": "\r", "\\t": "\t"}


@REGISTRY.register("FileRowCount", "tFileRowCount")
class FileRowCount(BaseComponent):
    """tFileRowCount engine implementation.

    Counts rows in a file and stores the result in globalMap as
    ``{id}_COUNT``. No data flow output is produced; downstream
    components connect via trigger and read the count from globalMap.

    Config keys:
        filename: Absolute path to the target file.
        row_separator: Row boundary character(s). Supports escape sequences.
        ignore_empty_row: When True, whitespace-only lines are excluded.
        encoding: File encoding. Defaults to ISO-8859-15 (Talend default).
    """

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate structural config before expression resolution.

        Only checks key presence — content checks (file existence, encoding
        validity) are deferred to ``_process()`` per Rule 12.

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
        """Count rows in the configured file.

        Args:
            input_data: Ignored. This is a standalone utility component
                with no data flow input.

        Returns:
            dict with ``main`` key set to ``None`` (no data flow output).

        Raises:
            ConfigurationError: If ``filename`` resolves to an empty string.
            FileOperationError: If the file cannot be opened or read
                (not found, permission denied, encoding error, I/O error).
        """
        filename: str = self.config.get("filename", "")
        row_separator: str = self.config.get("row_separator", "\\n")
        ignore_empty_row: bool = self.config.get("ignore_empty_row", False)
        encoding: str = self.config.get("encoding", "ISO-8859-15")

        # Post-resolution guard: filename may have been a context variable
        if not filename:
            raise ConfigurationError(
                f"[{self.id}] 'filename' resolved to an empty string"
            )

        # Normalise literal escape sequences (e.g. "\\n" -> "\n")
        for escaped, real in _ESCAPE_MAP.items():
            row_separator = row_separator.replace(escaped, real)

        logger.info(
            f"[{self.id}] Counting rows: file={filename!r}, encoding={encoding!r}, "
            f"separator={row_separator!r}, ignore_empty={ignore_empty_row}"
        )

        try:
            rows_in, rows_out, rows_rejected = _count_rows(
                filename, row_separator, ignore_empty_row, encoding
            )
        except (OSError, UnicodeDecodeError) as exc:
            raise FileOperationError(
                f"[{self.id}] Failed to read '{filename}': {exc}"
            ) from exc

        logger.info(
            f"[{self.id}] Complete: in={rows_in}, out={rows_out}, "
            f"rejected={rows_rejected}"
        )

        self._update_stats(rows_in, rows_out, rows_rejected)

        if self.global_map:
            self.global_map.put(f"{self.id}_COUNT", rows_out)
            self.global_map.put(f"{self.id}_NB_LINE", rows_in)
            self.global_map.put(f"{self.id}_NB_LINE_OK", rows_out)
            self.global_map.put(f"{self.id}_NB_LINE_REJECT", rows_rejected)

        return {"main": None}


# ------------------------------------------------------------------
# Module-level helper (pure function — independently testable)
# ------------------------------------------------------------------

def _count_rows(
    filename: str,
    row_separator: str,
    ignore_empty_row: bool,
    encoding: str,
) -> tuple[int, int, int]:
    """Read *filename* and return ``(rows_in, rows_out, rows_rejected)``.

    Uses Python's native line iteration for the common separators ``\\n``,
    ``\\r``, and ``\\r\\n`` (handled transparently by universal newline mode).
    For custom separators the file is read in full and split.

    Args:
        filename: Absolute path to the file.
        row_separator: Row boundary string (already normalised — no escapes).
        ignore_empty_row: When True, whitespace-only segments are not counted.
        encoding: File encoding passed to ``open()``.

    Returns:
        Tuple ``(rows_in, rows_out, rows_rejected)`` where:
            - ``rows_in``      -- total lines/segments found in the file.
            - ``rows_out``     -- lines/segments included in the count.
            - ``rows_rejected`` -- whitespace-only lines excluded
              (always 0 when *ignore_empty_row* is False).

    Raises:
        OSError: On file-not-found, permission denied, or generic I/O failure.
        UnicodeDecodeError: When the file cannot be decoded with *encoding*.
    """
    rows_in = 0
    rows_out = 0
    rows_rejected = 0

    if row_separator in ("\n", "\r\n", "\r"):
        # Fast path: Python's universal newline mode handles all three.
        with open(filename, "r", encoding=encoding) as fh:
            for line in fh:
                rows_in += 1
                if ignore_empty_row and not line.strip():
                    rows_rejected += 1
                else:
                    rows_out += 1
    else:
        # Custom separator: read the whole file and split.
        # Trailing empty segment produced by a file that ends with the
        # separator is discarded (mirrors Python file-iteration behaviour).
        with open(filename, "r", encoding=encoding, newline="") as fh:
            content = fh.read()
        segments = content.split(row_separator)
        if segments and segments[-1] == "":
            segments = segments[:-1]
        for segment in segments:
            rows_in += 1
            if ignore_empty_row and not segment.strip():
                rows_rejected += 1
            else:
                rows_out += 1

    return rows_in, rows_out, rows_rejected