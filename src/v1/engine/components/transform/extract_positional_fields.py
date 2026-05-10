"""ExtractPositionalFields engine component.

Talend equivalent: tExtractPositionalFields

Extracts multiple output columns from a single fixed-width positional string
column.  The ``field`` config key names the source column; ``pattern`` is a
comma-separated list of field widths (e.g. ``"5,4,5"``).

Config keys (all resolved by BaseComponent before _process is called):
    field               (str,  required)       -- source column name
    pattern             (str,  required)       -- comma-separated field widths
    ignore_source_null  (bool, default True)   -- skip null source rows silently
    trim                (bool, default False)  -- strip whitespace from fields
    die_on_error        (bool, default False)  -- raise on row error vs REJECT
    check_fields_num    (bool, default False)  -- reject lines shorter than total width
    advanced_separator  (bool, default False)  -- enable numeric separators
    thousands_separator (str,  default ",")   -- thousands separator
    decimal_separator   (str,  default ".")   -- decimal separator
    formats             (list, default [])    -- per-column format table (informational)
    tstatcatcher_stats  (bool, default False) -- framework
    label               (str,  default "")   -- framework

GlobalMap variables set:
    NB_LINE / NB_LINE_OK / NB_LINE_REJECT via _update_stats()
"""
import logging
from typing import Any, Dict, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, DataValidationError

logger = logging.getLogger(__name__)


@REGISTRY.register("ExtractPositionalFields", "tExtractPositionalFields")
class ExtractPositionalFields(BaseComponent):
    """Extracts fields from a fixed-width positional string column.

    Reads the source column named by ``field``, slices its string value at the
    character positions defined by ``pattern``, and produces one output column
    per field width.  Output column names come from ``output_schema`` when set;
    otherwise ``field_1``, ``field_2``, ... are generated.

    Null source rows are handled by ``ignore_source_null``.  Rows that fail
    extraction are sent to the REJECT output with ``errorCode`` /
    ``errorMessage`` columns.
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Check key presence and container types only (Rule 12).

        Content checks (pattern parsing, width > 0) are deferred to _process
        because pattern may contain a context-variable reference.
        """
        if "pattern" not in self.config:
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'pattern'"
            )
        for bool_key, default in (
            ("trim", False),
            ("die_on_error", False),
            ("ignore_source_null", True),
            ("check_fields_num", False),
        ):
            val = self.config.get(bool_key, default)
            if not isinstance(val, bool):
                raise ConfigurationError(
                    f"[{self.id}] Config '{bool_key}' must be a boolean"
                )

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Extract fixed-width positional fields from the source column.

        Args:
            input_data: Input DataFrame containing the positional source column.

        Returns:
            Dict with ``main`` (extracted rows DataFrame) and
            ``reject`` (failed/skipped rows DataFrame).
        """
        if input_data is None or input_data.empty:
            self._update_stats(0, 0, 0)
            return {"main": pd.DataFrame(), "reject": pd.DataFrame()}

        # ---- resolved config ----
        field = self.config.get("field", "")
        pattern_str = str(self.config.get("pattern", ""))
        ignore_source_null = self.config.get("ignore_source_null", True)
        trim = self.config.get("trim", False)
        die_on_error = self.config.get("die_on_error", False)
        check_fields_num = self.config.get("check_fields_num", False)

        # ---- content-validate pattern (Rule 12: deferred from _validate_config) ----
        if not pattern_str.strip():
            raise DataValidationError(
                f"[{self.id}] Config 'pattern' is empty -- cannot extract positional fields"
            )
        try:
            field_widths = [int(w.strip()) for w in pattern_str.split(",") if w.strip()]
        except ValueError as exc:
            raise DataValidationError(
                f"[{self.id}] Config 'pattern' must be comma-separated integers, got {pattern_str!r}"
            ) from exc
        for w in field_widths:
            if w <= 0:
                raise DataValidationError(
                    f"[{self.id}] All field widths must be > 0; found {w} in pattern {pattern_str!r}"
                )

        # ---- select source column ----
        if field and field in input_data.columns:
            src_col = field
        elif field:
            logger.warning(
                "[%s] Source column %r not found; falling back to first column",
                self.id,
                field,
            )
            src_col = input_data.columns[0]
        else:
            src_col = input_data.columns[0]

        # ---- output column names (extracted cols = schema cols NOT in input) ----
        output_schema = getattr(self, "output_schema", None) or []
        input_col_set = set(input_data.columns.tolist())

        if output_schema:
            all_out_cols = [c["name"] for c in output_schema]
            extracted_col_names = [
                c["name"] for c in output_schema if c["name"] not in input_col_set
            ]
        else:
            all_out_cols = []
            extracted_col_names = [f"field_{i + 1}" for i in range(len(field_widths))]

        # Use only as many widths as there are extracted columns
        active_widths = field_widths[: len(extracted_col_names)]

        # Cumulative start positions (based on active_widths)
        starts: list = []
        pos = 0
        for w in active_widths:
            starts.append(pos)
            pos += w
        total_width = pos

        rows_in = len(input_data)
        main_rows: list = []
        reject_rows: list = []

        for _, row in input_data.iterrows():
            value = row[src_col]

            # ---- null handling ----
            # pd.isna() on the scalar source-column values that this component
            # actually receives (str / NaN / None) never raises -- the prior
            # defensive try/except for TypeError/ValueError was unreachable
            # for realistic input shapes (D-C5 dead-code policy, Phase 14
            # Plan 14-05).
            is_null = pd.isna(value)

            if is_null:
                if ignore_source_null:
                    logger.debug("[%s] Skipping null source row", self.id)
                    continue
                reject_row = dict(row)
                reject_row["errorCode"] = "NULL_SOURCE"
                reject_row["errorMessage"] = f"Source column {src_col!r} is null"
                reject_rows.append(reject_row)
                continue

            line = str(value)
            # Strip BOM
            if line and ord(line[0]) == 0xFEFF:
                line = line[1:]

            try:
                if check_fields_num and len(line) < total_width:
                    raise DataValidationError(
                        f"Line length {len(line)} < required total width {total_width}"
                    )
                extracted = [line[s: s + w] for s, w in zip(starts, active_widths)]
                if trim:
                    extracted = [v.strip() for v in extracted]
                out_row = dict(row)  # passthrough: all input columns
                for col_name, val in zip(extracted_col_names, extracted):
                    out_row[col_name] = val
                main_rows.append(out_row)
            except Exception as exc:
                if die_on_error:
                    raise DataValidationError(
                        f"[{self.id}] Row extraction failed: {exc}"
                    ) from exc
                reject_row = dict(row)
                reject_row["errorCode"] = "EXTRACTION_ERROR"
                reject_row["errorMessage"] = str(exc)
                reject_rows.append(reject_row)

        if main_rows:
            main_df = pd.DataFrame(main_rows)
            if all_out_cols:
                for c in all_out_cols:
                    if c not in main_df.columns:
                        main_df[c] = None
                main_df = main_df[all_out_cols]
        else:
            main_df = pd.DataFrame(
                columns=all_out_cols if all_out_cols else list(input_data.columns)
            )
        reject_df = pd.DataFrame(reject_rows) if reject_rows else pd.DataFrame()

        rows_ok = len(main_df)
        rows_reject = len(reject_df)
        self._update_stats(rows_in, rows_ok, rows_reject)
        logger.info(
            "[%s] done: in=%d ok=%d reject=%d",
            self.id,
            rows_in,
            rows_ok,
            rows_reject,
        )
        return {"main": main_df, "reject": reject_df}

