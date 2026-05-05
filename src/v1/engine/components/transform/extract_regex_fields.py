"""ExtractRegexFields engine component.

Talend equivalent: tExtractRegexFields

Applies a regular expression with capture groups to a source column and maps
each capture group by position to an output schema column.

Config keys (all resolved by BaseComponent before _process is called):
    field            (str, required)       -- source column name
    regex            (str, required)       -- regex with capture groups
    die_on_error     (bool, default True)  -- raise on error vs REJECT
    check_fields_num (bool, default False) -- reject on group count mismatch
    tstatcatcher_stats (bool, default False) -- framework
    label            (str, default "")    -- framework

GlobalMap variables set:
    NB_LINE / NB_LINE_OK / NB_LINE_REJECT via _update_stats()
"""
import logging
import re
from typing import Any, Dict, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, DataValidationError

logger = logging.getLogger(__name__)


@REGISTRY.register("ExtractRegexFields", "tExtractRegexFields")
class ExtractRegexFields(BaseComponent):
    """Applies a regex to a source column and maps capture groups to output columns.

    The source column (named by ``field``) is matched against ``regex``.
    Capture groups are mapped by position to the output schema columns that are
    *not* present in the input DataFrame (same position-based convention as
    ExtractDelimitedFields).

    Rows that do not match the regex are sent to REJECT with errorCode
    ``NO_MATCH``.  When ``check_fields_num=True`` and the capture group count
    does not match the expected column count, rows are rejected with errorCode
    ``FIELD_COUNT_MISMATCH``.
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
        if "regex" not in self.config:
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'regex'"
            )
        for bool_key, default in (
            ("die_on_error", True),
            ("check_fields_num", False),
        ):
            val = self.config.get(bool_key, default)
            if not isinstance(val, bool):
                raise ConfigurationError(
                    f"[{self.id}] Config '{bool_key}' must be a boolean"
                )

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Apply regex to source column and extract capture groups.

        Args:
            input_data: Input DataFrame containing the source column.

        Returns:
            Dict with ``main`` (matched rows) and ``reject`` (unmatched rows).
        """
        if input_data is None or input_data.empty:
            self._update_stats(0, 0, 0)
            return {"main": pd.DataFrame(), "reject": pd.DataFrame()}

        field = self.config.get("field", "")
        regex_str = self.config.get("regex", "")
        die_on_error = self.config.get("die_on_error", True)
        check_fields_num = self.config.get("check_fields_num", False)

        # ---- content-validate (Rule 12: deferred to _process) ----
        if not field:
            raise DataValidationError(
                f"[{self.id}] Config 'field' is empty -- no source column specified"
            )
        if not regex_str:
            raise DataValidationError(
                f"[{self.id}] Config 'regex' is empty"
            )
        try:
            pattern = re.compile(regex_str)
        except re.error as exc:
            raise DataValidationError(
                f"[{self.id}] Config 'regex' is not a valid regular expression: {exc}"
            ) from exc

        # ---- select source column ----
        if field in input_data.columns:
            src_col = field
        else:
            if die_on_error:
                raise DataValidationError(
                    f"[{self.id}] Source column {field!r} not found in input"
                )
            logger.warning(
                "[%s] Source column %r not found; using first column", self.id, field
            )
            src_col = input_data.columns[0]

        # ---- determine extracted columns ----
        output_schema = getattr(self, "output_schema", None) or []
        input_col_set = set(input_data.columns.tolist())

        if output_schema:
            all_out_cols = [c["name"] for c in output_schema]
            extracted_col_names = [
                c["name"] for c in output_schema if c["name"] not in input_col_set
            ]
        else:
            all_out_cols = list(input_data.columns)
            extracted_col_names = []

        num_expected = len(extracted_col_names)

        rows_in = len(input_data)
        main_rows: list = []
        reject_rows: list = []

        for _, row in input_data.iterrows():
            value = row[src_col]

            try:
                is_null = pd.isna(value)
            except (TypeError, ValueError):
                is_null = False

            if is_null:
                reject_row = dict(row)
                reject_row["errorCode"] = "NULL_SOURCE"
                reject_row["errorMessage"] = f"Source column {src_col!r} is null"
                reject_rows.append(reject_row)
                continue

            str_value = str(value)
            match = pattern.search(str_value)

            if match is None:
                if die_on_error:
                    raise DataValidationError(
                        f"[{self.id}] Regex did not match row value: {str_value!r}"
                    )
                reject_row = dict(row)
                reject_row["errorCode"] = "NO_MATCH"
                reject_row["errorMessage"] = f"Regex did not match: {str_value!r}"
                reject_rows.append(reject_row)
                continue

            groups = list(match.groups())

            if check_fields_num and len(groups) != num_expected:
                if die_on_error:
                    raise DataValidationError(
                        f"[{self.id}] Expected {num_expected} groups, got {len(groups)}"
                    )
                reject_row = dict(row)
                reject_row["errorCode"] = "FIELD_COUNT_MISMATCH"
                reject_row["errorMessage"] = (
                    f"Expected {num_expected} capture groups, got {len(groups)}"
                )
                reject_rows.append(reject_row)
                continue

            out_row = dict(row)
            for i, col_name in enumerate(extracted_col_names):
                out_row[col_name] = groups[i] if i < len(groups) else None
            main_rows.append(out_row)

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
