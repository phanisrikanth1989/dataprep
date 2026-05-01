"""Engine component for LogRow (tLogRow).

Logs rows flowing through the pipeline to the console for debugging and
monitoring. All output goes through ``logger.info()`` -- the Python equivalent
of Talend's default Log4J routing. The component is a pure pass-through:
every input row appears unchanged on the ``main`` output.

Config keys consumed (16 total):
  basic_mode             (bool, default True)  -- MODE radio; sep-delimited one line per row
  table_print            (bool, default False) -- MODE radio; bordered ASCII table
  vertical               (bool, default False) -- MODE radio; key-value pairs per row
  print_unique           (bool, default True)  -- TITLE_PRINT radio; unique name as section
                                                  title in vertical mode
  print_label            (bool, default False) -- TITLE_PRINT radio; label as section title
                                                  in vertical mode
  print_unique_label     (bool, default False) -- TITLE_PRINT radio; unique+label as title
  fieldseparator         (str,  default "|")   -- field delimiter for basic mode
  print_header           (bool, default False) -- include column-names header line before
                                                  data rows (basic mode)
  print_unique_name      (bool, default False) -- prefix each row line with [component_id]
  print_colnames         (bool, default False) -- prefix each value with "colname=" in
                                                  basic mode (e.g. id=1|name=Alice)
  use_fixed_length       (bool, default False) -- pad / truncate values to widths from
                                                  the lengths list
  lengths                (list, default [])    -- per-column widths; parallel to schema
                                                  columns order
  print_content_with_log4j (bool, default True) -- DEFERRED: route through Log4J vs
                                                   System.out; we always use logger.info
  max_rows               (int or str, default 100) -- max rows to display;
                                                       accepts ${context.X} references
  tstatcatcher_stats     (bool, default False) -- framework: tStatCatcher statistics
  label                  (str,  default "")    -- framework: component label on canvas
"""
import logging
from typing import Any, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)

# ---- module-level constants ----
_DEFAULT_SEPARATOR = "|"
_DEFAULT_MAX_ROWS = 100


@REGISTRY.register("LogRow", "tLogRow")
class LogRow(BaseComponent):
    """tLogRow engine implementation -- pass-through row logger.

    Logs rows flowing through the pipeline to the console for debugging
    and monitoring. Supports three mutually-exclusive display modes:

    * ``basic_mode`` (default True) -- separator-delimited one line per row
    * ``table_print`` (default False) -- bordered ASCII table with headers
    * ``vertical``   (default False) -- key-value pairs one per line per row

    The component is a **pure pass-through**: ``main`` always equals the
    full input DataFrame. ``reject`` is never populated. ``NB_LINE_OK``
    equals the total number of input rows (not the displayed subset).

    Config keys:
        basic_mode: Sep-delimited one line per row (default True -- selected mode)
        table_print: Bordered ASCII table (default False)
        vertical: Key-value pairs per row (default False)
        print_unique: Component unique name as section title in vertical mode (default True)
        print_label: Label as section title in vertical mode (default False)
        print_unique_label: Unique+label as title in vertical mode (default False)
        fieldseparator: Delimiter for basic mode (default "|")
        print_header: Print column names header line in basic mode (default False)
        print_unique_name: Prefix each row line with [component_id] (default False)
        print_colnames: Prefix each value with "colname=" in basic mode (default False)
        use_fixed_length: Pad values to widths from lengths list (default False)
        lengths: Per-column widths parallel to schema columns (default [])
        print_content_with_log4j: DEFERRED -- Log4J vs System.out (default True)
        max_rows: Max rows to display; accepts ${context.X} refs (default 100)
        tstatcatcher_stats: framework (default False)
        label: component label on canvas (default "")
    """

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate configuration.

        No keys are required -- all have safe defaults. ``max_rows``
        numeric validation is intentionally deferred to ``_process()`` so
        that ``${context.MAX_ROWS}`` references are accepted here and
        resolved before the numeric check runs (Rule 12).
        """

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict[str, Any]:
        """Log rows and pass all input through unchanged.

        Args:
            input_data: Input DataFrame from upstream component.

        Returns:
            dict with ``main`` key containing the full unmodified input
            DataFrame. ``reject`` is never populated.
        """
        if input_data is None or input_data.empty:
            return {"main": input_data if input_data is not None else pd.DataFrame()}

        # ---- Deferred max_rows validation (after context resolution) ----
        raw_max = self.config.get("max_rows", _DEFAULT_MAX_ROWS)
        try:
            max_rows = int(raw_max)
        except (ValueError, TypeError) as exc:
            raise ConfigurationError(
                f"[{self.id}] 'max_rows' must be an integer, got: {raw_max!r}"
            ) from exc
        if max_rows < 0:
            raise ConfigurationError(
                f"[{self.id}] 'max_rows' must be non-negative, got: {max_rows}"
            )

        # ---- Deferred feature: print_content_with_log4j=False (System.out) ----
        if not bool(self.config.get("print_content_with_log4j", True)):
            logger.warning(
                "[%s] print_content_with_log4j=False (System.out routing) is not "
                "implemented; output routed through logger.info() (Log4J equivalent)",
                self.id,
            )

        # ---- Display mode (radio group: vertical > table_print > basic_mode) ----
        vertical = bool(self.config.get("vertical", False))
        table_print = bool(self.config.get("table_print", False))
        # basic_mode is the fallback when neither vertical nor table_print is True

        # ---- Shared display options ----
        sep = str(self.config.get("fieldseparator", _DEFAULT_SEPARATOR))
        print_header = bool(self.config.get("print_header", False))
        print_unique_name = bool(self.config.get("print_unique_name", False))
        print_colnames = bool(self.config.get("print_colnames", False))
        use_fixed_length = bool(self.config.get("use_fixed_length", False))
        lengths: list = self.config.get("lengths") or []
        label = str(self.config.get("label", ""))

        # ---- Vertical title group (TITLE_PRINT radio) ----
        print_unique_label = bool(self.config.get("print_unique_label", False))
        print_label_mode = bool(self.config.get("print_label", False))
        # print_unique (default) is active when neither of the above is True

        df_to_log = input_data.head(max_rows)

        if vertical:
            self._log_vertical(
                df_to_log,
                print_label_mode=print_label_mode,
                print_unique_label=print_unique_label,
                label=label,
                use_fixed_length=use_fixed_length,
                lengths=lengths,
            )
        elif table_print:
            self._log_table(
                df_to_log,
                print_unique_name=print_unique_name,
                use_fixed_length=use_fixed_length,
                lengths=lengths,
            )
        else:
            # basic_mode (default when no other mode selected)
            self._log_basic(
                df_to_log,
                sep=sep,
                print_header=print_header,
                print_colnames=print_colnames,
                print_unique_name=print_unique_name,
                use_fixed_length=use_fixed_length,
                lengths=lengths,
            )

        logger.debug(
            "[%s] logged %d/%d rows", self.id, len(df_to_log), len(input_data)
        )

        # Pass through ALL rows -- display limit does not affect the data flow
        return {"main": input_data}

    # ------------------------------------------------------------------
    # Private display helpers -- all output via logger.info()
    # ------------------------------------------------------------------

    def _log_basic(
        self,
        df: pd.DataFrame,
        sep: str,
        print_header: bool,
        print_colnames: bool,
        print_unique_name: bool,
        use_fixed_length: bool,
        lengths: list,
    ) -> None:
        """Emit one ``logger.info()`` line per row in sep-delimited format.

        Args:
            df: Rows to display (already limited to max_rows).
            sep: Field separator string.
            print_header: If True emit column names as first line.
            print_colnames: If True prefix each value with ``colname=``.
            print_unique_name: If True prefix each line with ``[id] ``.
            use_fixed_length: If True pad/truncate values by lengths.
            lengths: Per-column widths parallel to df.columns.
        """
        cols = list(df.columns)
        prefix = f"[{self.id}] " if print_unique_name else ""

        if print_header:
            logger.info("%s%s", prefix, sep.join(str(c) for c in cols))

        for _, row in df.iterrows():
            parts: list[str] = []
            for i, col in enumerate(cols):
                val = "" if pd.isna(row[col]) else str(row[col])
                if use_fixed_length and i < len(lengths):
                    width = int(lengths[i]) if isinstance(lengths[i], (int, float)) else 10
                    val = val[:width].ljust(width)
                parts.append(f"{col}={val}" if print_colnames else val)
            logger.info("%s%s", prefix, sep.join(parts))

    def _log_table(
        self,
        df: pd.DataFrame,
        print_unique_name: bool,
        use_fixed_length: bool,
        lengths: list,
    ) -> None:
        """Emit an ASCII bordered table via ``logger.info()``.

        Column widths are computed from the data slice (max_rows rows)
        unless ``use_fixed_length`` is True, which uses the declared widths.

        Args:
            df: Rows to display (already limited to max_rows).
            print_unique_name: If True emit ``[id]`` title line before table.
            use_fixed_length: If True use declared widths from lengths.
            lengths: Per-column widths parallel to df.columns.
        """
        if df.empty:
            return

        cols = list(df.columns)

        # Column widths: fixed if declared, otherwise computed from the data slice
        if use_fixed_length and lengths:
            col_widths = {
                col: (
                    int(lengths[i])
                    if i < len(lengths) and isinstance(lengths[i], (int, float))
                    else max(len(str(col)), 1)
                )
                for i, col in enumerate(cols)
            }
        else:
            col_widths = {
                col: max(
                    len(str(col)),
                    int(df[col].fillna("").astype(str).str.len().max()),
                    1,
                )
                for col in cols
            }

        def _row_line(values: list[str]) -> str:
            return (
                "|"
                + "|".join(
                    str(v).ljust(col_widths[c]) for c, v in zip(cols, values)
                )
                + "|"
            )

        sep_line = "+" + "+".join("-" * col_widths[c] for c in cols) + "+"

        if print_unique_name:
            logger.info("[%s]", self.id)
        logger.info(sep_line)
        logger.info(_row_line([str(c) for c in cols]))
        logger.info(sep_line)
        for _, row in df.iterrows():
            logger.info(_row_line(["" if pd.isna(v) else str(v) for v in row]))
        logger.info(sep_line)

    def _log_vertical(
        self,
        df: pd.DataFrame,
        print_label_mode: bool,
        print_unique_label: bool,
        label: str,
        use_fixed_length: bool,
        lengths: list,
    ) -> None:
        """Emit key-value pairs per row via ``logger.info()``.

        Title line for each row section is controlled by TITLE_PRINT radio:

        * ``print_unique_label=True`` -- ``[id] label`` (or ``[id]`` if no label)
        * ``print_label_mode=True``   -- ``label`` (or ``[id]`` if label empty)
        * default (print_unique)      -- ``[id]``

        Args:
            df: Rows to display (already limited to max_rows).
            print_label_mode: If True use label as section title.
            print_unique_label: If True use unique+label as section title.
            label: Component label from config (may be empty string).
            use_fixed_length: If True pad/truncate values by lengths.
            lengths: Per-column widths parallel to df.columns.
        """
        cols = list(df.columns)

        if print_unique_label:
            title = f"[{self.id}] {label}".strip() if label else f"[{self.id}]"
        elif print_label_mode:
            title = label if label else f"[{self.id}]"
        else:
            # print_unique (default)
            title = f"[{self.id}]"

        for i, (_, row) in enumerate(df.iterrows(), start=1):
            logger.info("--- %s row %d ---", title, i)
            for j, col in enumerate(cols):
                val = "" if pd.isna(row[col]) else str(row[col])
                if use_fixed_length and j < len(lengths):
                    width = int(lengths[j]) if isinstance(lengths[j], (int, float)) else 10
                    val = val[:width].ljust(width)
                logger.info("  %s: %s", col, val)
