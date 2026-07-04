"""ExtractDelimitedFields engine component.

Talend equivalent: tExtractDelimitedFields

Splits a single delimited source column into multiple output columns by
index position.  The extraction is **position-based**: token[0] goes to
the first output-schema column that is absent from the input DataFrame,
token[1] to the second, and so on.  Column names are irrelevant; only
schema position matters.

Config keys (all resolved by BaseComponent before _process is called):
    field               (str,  required)       -- source column to split
    fieldseparator      (str,  default ";")    -- delimiter character
    ignore_source_null  (bool, default True)   -- skip null source rows
    die_on_error        (bool, default False)  -- raise on row error vs REJECT
    advanced_separator  (bool, default False)  -- numeric separator conversion
    thousands_separator (str,  default ",")   -- thousands sep (adv. mode)
    decimal_separator   (str,  default ".")   -- decimal sep (adv. mode)
    trim                (bool, default False)  -- strip whitespace from tokens
    check_fields_num    (bool, default False)  -- reject on token count mismatch
    check_date          (bool, default False)  -- validate date columns (stub)
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

# Talend type identifiers for numeric columns (advanced_separator applies to these)
_NUMERIC_TYPES = frozenset({
    "id_Integer", "id_Float", "id_Double", "id_Long",
    "id_Short", "id_BigDecimal", "id_Byte",
})


@REGISTRY.register("ExtractDelimitedFields", "tExtractDelimitedFields")
class ExtractDelimitedFields(BaseComponent):
    """Splits a delimited source column into multiple output columns by position.

    The source column (named by ``field``) is split by ``fieldseparator``.
    Extracted output columns are those in ``output_schema`` that are *not*
    already present in the input DataFrame; they receive split tokens in
    schema order.  Passthrough columns are copied from the input row.
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Check key presence and container types only (Rule 12)."""
        if "field" not in self.config:
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'field'"
            )
        for bool_key, default in (
            ("ignore_source_null", True),
            ("die_on_error", False),
            ("advanced_separator", False),
            ("trim", False),
            ("check_fields_num", False),
            ("check_date", False),
        ):
            val = self.config.get(bool_key, default)
            if not isinstance(val, bool):
                raise ConfigurationError(
                    f"[{self.id}] Config '{bool_key}' must be a boolean"
                )

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Split source column and assign tokens to output columns by position.

        Args:
            input_data: Input DataFrame.

        Returns:
            Dict with ``main`` (processed rows DataFrame) and
            ``reject`` (failed rows DataFrame).
        """
        if input_data is None or input_data.empty:
            self._update_stats(0, 0, 0)
            return {"main": pd.DataFrame(), "reject": pd.DataFrame()}

        # ---- resolved config ----
        field = self.config.get("field", "")
        separator = self.config.get("fieldseparator", ";")
        ignore_source_null = self.config.get("ignore_source_null", True)
        die_on_error = self.config.get("die_on_error", False)
        advanced_sep = self.config.get("advanced_separator", False)
        thousands_sep = self.config.get("thousands_separator", ",")
        decimal_sep = self.config.get("decimal_separator", ".")
        trim = self.config.get("trim", False)
        check_fields_num = self.config.get("check_fields_num", False)

        # ---- content-validate (Rule 12: deferred to _process) ----
        if not field:
            raise DataValidationError(
                f"[{self.id}] Config 'field' is empty -- no source column to split"
            )
        if field not in input_data.columns:
            raise DataValidationError(
                f"[{self.id}] Source column {field!r} not found in input DataFrame"
            )

        # Strip surrounding quotes from separator (Talend may emit e.g. \",\")
        sep = separator.strip('"').strip("'") if separator else ";"

        # ---- determine extracted vs passthrough columns ----
        output_schema = getattr(self, "output_schema", None) or []
        input_col_set = set(input_data.columns.tolist())

        if output_schema:
            all_out_cols = [c["name"] for c in output_schema]
            extracted_info = [
                (c["name"], c.get("type", ""))
                for c in output_schema
                if c["name"] not in input_col_set
            ]
        else:
            all_out_cols = list(input_data.columns)
            extracted_info = []

        extracted_col_names = [name for name, _ in extracted_info]
        extracted_col_types = [typ for _, typ in extracted_info]
        num_extracted = len(extracted_col_names)

        rows_in = len(input_data)
        main_rows: list = []
        reject_rows: list = []

        for _, row in input_data.iterrows():
            value = row[field]

            # ---- null handling ----
            # Scalar source-column values (str / NaN / None) never make
            # pd.isna() raise -- defensive try/except removed per D-C5
            # (Phase 14 Plan 14-05).
            is_null = pd.isna(value)

            if is_null:
                if ignore_source_null:
                    logger.debug("[%s] Skipping null source row", self.id)
                    continue
                reject_row = dict(row)
                reject_row["errorCode"] = "NULL_SOURCE"
                reject_row["errorMessage"] = f"Source column {field!r} is null"
                reject_rows.append(reject_row)
                continue

            tokens = str(value).split(sep)
            if trim:
                tokens = [t.strip() for t in tokens]

            # ---- check_fields_num ----
            if check_fields_num and len(tokens) != num_extracted:
                if die_on_error:
                    raise DataValidationError(
                        f"[{self.id}] Expected {num_extracted} tokens, got {len(tokens)}"
                    )
                reject_row = dict(row)
                reject_row["errorCode"] = "FIELD_COUNT_MISMATCH"
                reject_row["errorMessage"] = (
                    f"Expected {num_extracted} tokens, got {len(tokens)}"
                )
                reject_rows.append(reject_row)
                continue

            # ---- advanced separator: normalize numeric tokens ----
            if advanced_sep and (thousands_sep or decimal_sep):
                normalized: list = []
                for i, tok in enumerate(tokens):
                    col_type = extracted_col_types[i] if i < len(extracted_col_types) else ""
                    if col_type in _NUMERIC_TYPES:
                        if thousands_sep:
                            tok = tok.replace(thousands_sep, "")
                        if decimal_sep and decimal_sep != ".":
                            tok = tok.replace(decimal_sep, ".")
                    normalized.append(tok)
                tokens = normalized

            # ---- build output row ----
            out_row = dict(row)  # passthrough: all input columns
            for i, col_name in enumerate(extracted_col_names):
                out_row[col_name] = tokens[i] if i < len(tokens) else None
            main_rows.append(out_row)

        if main_rows:
            main_df = pd.DataFrame(main_rows)
            if all_out_cols:
                # Every column in all_out_cols is guaranteed to be in
                # main_df.columns by construction (input cols via dict(row),
                # extracted cols always assigned -- None when token absent).
                # Backfill loop unreachable for realistic input; removed per
                # D-C5 in Phase 14 Plan 14-05.
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

