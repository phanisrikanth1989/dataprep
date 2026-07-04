"""Engine component for SchemaComplianceCheck (tSchemaComplianceCheck).

Validates input rows against a declared schema, routing rows that fail any
check to the reject output with errorCode and errorMessage details.
Checks performed (per column, per row):
  - Nullability: non-nullable columns must not be null/empty
  - Type coercion: numeric/bool/datetime values must be parseable
  - String length: str columns with max_length > 0 must not exceed the limit
  - Date format: datetime columns with strict_date_check=True and date_pattern
                 must match the declared pattern

Config keys consumed (15 total):
  schema                      (list[dict], required) -- column definitions from FLOW schema.
                                                         Each entry: name(str), type(str),
                                                         nullable(bool), length(int), date_pattern(str)
  check_all                   (bool, default True)   -- check all schema columns
  customer                    (bool, default False)  -- deferred: customer-defined checks
  check_another               (bool, default False)  -- check only columns listed in checkcols
  checkcols                   (list[dict], default []) -- per-column overrides when check_another=True
                                                          each entry: column, selected_type,
                                                          date_pattern, nullable, max_length
  sub_string                  (bool, default False)  -- deferred: substring match for length
  strict_date_check           (bool, default False)  -- enforce date_pattern on datetime columns
  all_empty_are_null          (bool, default True)   -- treat empty string "" as null
  fast_date_check             (bool, default False)  -- deferred: relaxed date parsing
  ignore_timezone             (bool, default False)  -- deferred: ignore timezone in datetime
  empty_null_table            (list[dict], default []) -- per-column empty-as-null overrides
                                                          each entry: column, empty_is_null
  check_string_by_byte_length (bool, default False)  -- use byte length for str length check
  charset                     (str, default "")      -- charset for byte-length encoding (default UTF-8)
  tstatcatcher_stats          (bool, default False)  -- framework
  label                       (str, default "")      -- framework
"""
import logging
from typing import Optional

import numpy as np
import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)


# Error code emitted on reject rows -- matches Talend's tSchemaComplianceCheck default
_REJECT_ERROR_CODE = 8

# Python type strings that require numeric coercion check (after converter type_mapping.py)
_NUMERIC_TYPES = frozenset({"int", "float", "Decimal"})

# Python type strings that require date-format check
_DATE_TYPES = frozenset({"datetime"})

# Deferred feature flags -- logged as WARNING when enabled but not yet implemented
_DEFERRED_FEATURES = {
    "customer": "Customer-defined check mode",
    "sub_string": "Substring match for length check",
    "fast_date_check": "Fast (relaxed) date parsing",
    "ignore_timezone": "Timezone-ignorant datetime comparison",
}

# Java SimpleDateFormat token -> Python strptime token (longest-match order)
_JAVA_DATE_TOKENS = [
    ("yyyy", "%Y"), ("yy", "%y"),
    ("MM", "%m"), ("dd", "%d"),
    ("HH", "%H"), ("hh", "%I"),
    ("mm", "%M"), ("SSS", "%f"),
    ("ss", "%S"), ("a", "%p"),
]


def _java_to_strptime(java_pattern: str) -> str:
    """Convert a Java SimpleDateFormat pattern to a Python strptime format string.

    Args:
        java_pattern: Java SimpleDateFormat pattern, e.g. ``"yyyy-MM-dd"``.

    Returns:
        Equivalent Python strptime format string, e.g. ``"%Y-%m-%d"``.
    """
    result = java_pattern
    for token, replacement in _JAVA_DATE_TOKENS:
        result = result.replace(token, replacement)
    return result


@REGISTRY.register("SchemaComplianceCheck", "tSchemaComplianceCheck")
class SchemaComplianceCheck(BaseComponent):
    """tSchemaComplianceCheck engine implementation.

    Validates input rows against the declared FLOW schema.  Each row is
    checked column-by-column; any violation routes the row to the reject
    output with an ``errorCode`` (8) and a semicolon-delimited
    ``errorMessage``.  Valid rows are passed unchanged on the main output.

    Checks performed:
        - **Nullability**: non-nullable columns must not be null or empty.
        - **Type coercion**: numeric (int/float/Decimal) and bool columns
          must be parseable.  datetime columns are validated when
          ``strict_date_check=True`` and ``date_pattern`` is set.
        - **String length**: str columns with a positive ``length``
          constraint must not exceed that limit (by character count or, when
          ``check_string_by_byte_length=True``, by byte count).

    Config keys:
        schema: Column definitions (required). Each entry must have 'name'
            and 'type' (Python type string from the converter).
        check_all: When True (default), check all schema columns.
        check_another: When True, check only the columns listed in checkcols.
        checkcols: Per-column override entries (used with check_another=True).
        all_empty_are_null: Treat empty strings as null (default True).
        empty_null_table: Per-column overrides for empty-as-null behaviour.
        strict_date_check: Enforce date_pattern on datetime columns.
        check_string_by_byte_length: Use byte length for string length checks.
        charset: Charset for byte-length encoding (default "utf-8").
    """

    # ------------------------------------------------------------------
    # Configuration validation (Rule 2 / Rule 12: structure only)
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate that ``schema`` is present and structurally correct.

        Only key presence and container shape are checked here, as required
        by Rule 12.  Content checks (valid type strings, range constraints,
        etc.) happen inside ``_process()`` after context-variable resolution.

        Raises:
            ConfigurationError: If ``schema`` is missing, not a list, or
                contains entries that are not dicts with ``name`` and ``type``
                keys present.
        """
        schema = self.config.get("schema")
        if schema is None:
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'schema'"
            )
        if not isinstance(schema, list):
            raise ConfigurationError(
                f"[{self.id}] Config 'schema' must be a list, "
                f"got {type(schema).__name__}"
            )
        for i, col in enumerate(schema):
            if not isinstance(col, dict):
                raise ConfigurationError(
                    f"[{self.id}] schema[{i}] must be a dict, "
                    f"got {type(col).__name__}"
                )
            if "name" not in col:
                raise ConfigurationError(
                    f"[{self.id}] schema[{i}] missing required key 'name'"
                )
            if "type" not in col:
                raise ConfigurationError(
                    f"[{self.id}] schema[{i}] missing required key 'type'"
                )

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> dict:
        """Validate input rows and route violations to the reject output.

        Args:
            input_data: Input DataFrame to validate.

        Returns:
            dict with keys:

            - ``'main'``: rows that passed all checks (columns unchanged).
            - ``'reject'``: rows that failed at least one check, with extra
              columns ``'errorCode'`` (int) and ``'errorMessage'`` (str).
        """
        if input_data is None or input_data.empty:
            logger.info("[%s] Empty input — nothing to validate", self.id)
            return {"main": pd.DataFrame(), "reject": pd.DataFrame()}

        # ---- Read resolved config ----
        schema: list = self.config.get("schema", [])
        check_another: bool = self.config.get("check_another", False)
        checkcols_cfg: list = self.config.get("checkcols", [])
        all_empty_are_null: bool = self.config.get("all_empty_are_null", True)
        empty_null_table: list = self.config.get("empty_null_table", [])
        check_string_by_byte_length: bool = self.config.get("check_string_by_byte_length", False)
        charset: str = (self.config.get("charset") or "utf-8").strip() or "utf-8"
        strict_date_check: bool = self.config.get("strict_date_check", False)

        # Warn about deferred features if enabled
        for flag, description in _DEFERRED_FEATURES.items():
            if self.config.get(flag, False):
                logger.warning(
                    "[%s] '%s' (%s) is not yet implemented — flag ignored",
                    self.id, flag, description,
                )

        # ---- Per-column empty-as-null override map: {col_name: bool} ----
        # IMPORTANT: empty_null_table is only active when all_empty_are_null=False.
        # In Talend's UI the EMPTY_NULL_TABLE field is show="false" (hidden) while
        # ALL_EMPTY_ARE_NULL is checked.  Talend always emits EMPTY_NULL_TABLE rows
        # for every schema column defaulting EMPTY_NULL to "false".  If we consulted
        # those overrides while all_empty_are_null=True they would silently cancel
        # the global setting for every column.
        if all_empty_are_null:
            # Global flag wins — per-column table is irrelevant.
            empty_null_overrides: dict = {}
        else:
            empty_null_overrides = {
                entry["column"]: entry["empty_is_null"]
                for entry in empty_null_table
                if isinstance(entry, dict) and "column" in entry and "empty_is_null" in entry
            }

        # ---- Determine which schema columns are active ----
        if check_another and checkcols_cfg:
            checkcols_map: dict = {
                entry["column"]: entry
                for entry in checkcols_cfg
                if isinstance(entry, dict) and "column" in entry
            }
            active_schema = [col for col in schema if col["name"] in checkcols_map]
        else:
            # check_all (default): validate every schema column
            checkcols_map = {}
            active_schema = list(schema)

        # ---- Vectorized violation detection ----
        # Each element of violation_parts is a pd.Series[str]:
        #   "" → no violation for that (row, check)
        #   non-empty → violation description "col_name:reason"
        violation_parts: list = []

        for col_def in active_schema:
            col_name: str = col_def["name"]
            col_type: str = col_def.get("type", "str")

            # Apply checkcols overrides when check_another=True
            override = checkcols_map.get(col_name, {})
            is_nullable: bool = override.get("nullable", col_def.get("nullable", True))
            max_length: int = col_def.get("length", -1)
            date_pattern: str = col_def.get("date_pattern", "")

            # Skip columns absent from the input (Talend is tolerant)
            if col_name not in input_data.columns:
                logger.debug(
                    "[%s] Schema column '%s' not in input — skipping",
                    self.id, col_name,
                )
                continue

            series: pd.Series = input_data[col_name]

            # ---- Build null/empty mask ----
            is_null: pd.Series = series.isna()
            col_empty_is_null: bool = empty_null_overrides.get(col_name, all_empty_are_null)
            if col_empty_is_null:
                is_null = is_null | (series.astype(str).str.strip() == "")

            not_null: pd.Series = ~is_null

            # ---- Check 1: Nullability ----
            if not is_nullable:
                viol = np.where(is_null, f"{col_name}:cannot be null", "")
                violation_parts.append(
                    pd.Series(viol, index=input_data.index, dtype=object)
                )

            # ---- Check 2: Type coercion (non-null values only) ----
            if col_type in _NUMERIC_TYPES:
                coerced = pd.to_numeric(series.where(not_null), errors="coerce")
                type_viol_mask: pd.Series = not_null & coerced.isna()
                viol = np.where(type_viol_mask, f"{col_name}:invalid type", "")
                violation_parts.append(
                    pd.Series(viol, index=input_data.index, dtype=object)
                )

            elif col_type == "bool":
                bool_strs = series.where(not_null).fillna("").astype(str).str.lower()
                valid_bool: pd.Series = bool_strs.isin(
                    {"true", "false", "1", "0", "yes", "no", ""}
                ) | is_null
                viol = np.where(
                    not_null & ~valid_bool, f"{col_name}:invalid type", ""
                )
                violation_parts.append(
                    pd.Series(viol, index=input_data.index, dtype=object)
                )

            elif col_type in _DATE_TYPES and strict_date_check and date_pattern:
                fmt = _java_to_strptime(date_pattern)
                parsed = pd.to_datetime(
                    series.where(not_null), format=fmt, errors="coerce"
                )
                date_viol_mask: pd.Series = not_null & parsed.isna()
                viol = np.where(
                    date_viol_mask, f"{col_name}:invalid date format", ""
                )
                violation_parts.append(
                    pd.Series(viol, index=input_data.index, dtype=object)
                )

            # ---- Check 3: String length (str columns with positive max_length) ----
            if col_type == "str" and isinstance(max_length, int) and max_length > 0:
                str_series = series.where(not_null).fillna("").astype(str)
                if check_string_by_byte_length:
                    try:
                        lengths: pd.Series = str_series.str.encode(charset).str.len()
                    except LookupError:
                        logger.warning(
                            "[%s] Unknown charset '%s' for byte-length check; "
                            "falling back to character length",
                            self.id, charset,
                        )
                        lengths = str_series.str.len()
                else:
                    lengths = str_series.str.len()
                len_viol_mask: pd.Series = not_null & (lengths > max_length)
                viol = np.where(
                    len_viol_mask, f"{col_name}:exceed max length", ""
                )
                violation_parts.append(
                    pd.Series(viol, index=input_data.index, dtype=object)
                )

        # ---- Combine violation messages per row ----
        if not violation_parts:
            logger.info(
                "[%s] No checkable columns found — all %d rows pass",
                self.id, len(input_data),
            )
            return {"main": input_data.copy(), "reject": pd.DataFrame()}

        violation_matrix = pd.concat(violation_parts, axis=1)
        row_errors: pd.Series = violation_matrix.apply(
            lambda row: ";".join(v for v in row if v), axis=1
        )

        rejected_mask: pd.Series = row_errors.str.len() > 0
        main_df = input_data.loc[~rejected_mask].reset_index(drop=True)
        reject_rows = input_data.loc[rejected_mask].copy().reset_index(drop=True)

        if not reject_rows.empty:
            reject_rows["errorCode"] = _REJECT_ERROR_CODE
            reject_rows["errorMessage"] = row_errors.loc[rejected_mask].reset_index(drop=True)

        n_valid = len(main_df)
        n_rejected = len(reject_rows)
        logger.info(
            "[%s] Validation complete: in=%d, valid=%d, rejected=%d",
            self.id, len(input_data), n_valid, n_rejected,
        )
        if n_rejected > 0:
            logger.info("[%s] %d row(s) rejected due to schema violations", self.id, n_rejected)

        return {
            "main": main_df,
            "reject": reject_rows if not reject_rows.empty else pd.DataFrame(),
        }
