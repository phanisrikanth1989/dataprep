"""ConvertType engine component.

Talend equivalent: tConvertType

Converts column data types within a data flow. Supports two modes:

* AUTOCAST -- attempt type inference on every column that is not listed in
  the manual mapping table.
* MANUALTABLE -- explicit column-to-column type coercion list where each
  entry maps ``input_column`` (source column name) to ``output_column``
  (target column name with the destination type carried by the output schema).

Both modes can be active simultaneously. Empty strings may optionally be
converted to null (pd.NA) before casting. Rows that fail conversion are
routed to the REJECT flow when ``dieonerror=False``, otherwise an exception
is raised.

Config keys (resolved by BaseComponent before _process is called):
    autocast        (bool, default False) -- enable pandas type inference
    manualtable     (list[dict], default [])
                    -- list of {"input_column": str, "output_column": str}
    emptytonull     (bool, default False) -- replace "" with pd.NA before casting
    dieonerror      (bool, default False) -- raise on first failure vs reject routing

GlobalMap variables set:
    {id}_NB_LINE / NB_LINE_OK / NB_LINE_REJECT via _update_stats()
"""
import logging
from typing import Any, Dict, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, DataValidationError

logger = logging.getLogger(__name__)

# Talend type name -> pandas dtype string used in output_schema
_TALEND_TO_PANDAS: dict[str, str] = {
    "int": "int64",
    "integer": "int64",
    "long": "int64",
    "short": "int64",
    "byte": "int64",
    "float": "float64",
    "double": "float64",
    "big_decimal": "float64",
    "bigdecimal": "float64",
    "boolean": "bool",
    "bool": "bool",
    "string": "object",
    "str": "object",
    "date": "datetime64[ns]",
    "datetime": "datetime64[ns]",
    "timestamp": "datetime64[ns]",
    "object": "object",
}


def _coerce_series(series: pd.Series, target_dtype: str, col_name: str) -> pd.Series:
    """Attempt to coerce *series* to *target_dtype*.

    Returns the coerced Series on success, or raises ValueError / TypeError
    so the caller can decide how to handle the failure.
    """
    dtype_lower = target_dtype.lower()

    if "datetime" in dtype_lower or dtype_lower == "date":
        return pd.to_datetime(series, errors="raise")
    if dtype_lower in ("bool", "boolean"):
        # Accept "true"/"false" strings as well
        if series.dtype == object:
            return series.map(lambda v: str(v).strip().lower() == "true" if pd.notna(v) else pd.NA)
        return series.astype(bool)
    if "int" in dtype_lower:
        return pd.to_numeric(series, errors="raise").astype("Int64")
    if "float" in dtype_lower or "double" in dtype_lower or "decimal" in dtype_lower:
        return pd.to_numeric(series, errors="raise")
    if dtype_lower in ("object", "str", "string"):
        return series.astype(str).where(series.notna(), other=pd.NA)
    # Generic fallback
    return series.astype(target_dtype)


@REGISTRY.register("ConvertType", "tConvertType")
class ConvertType(BaseComponent):
    """Converts column data types within a data flow.

    Supports AUTOCAST (infer types via pandas) and/or MANUALTABLE (explicit
    column pairs). Rows that fail conversion are routed to the REJECT flow
    with ``error_code`` and ``error_message`` columns appended, unless
    ``dieonerror=True`` in which case a DataValidationError is raised.
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Check structural config -- key presence and container types only (Rule 12).

        Raises:
            ConfigurationError: If ``manualtable`` is not a list, or if any
                boolean config field has the wrong type.
        """
        manualtable = self.config.get("manualtable", [])
        if not isinstance(manualtable, list):
            raise ConfigurationError(
                f"[{self.id}] Config 'manualtable' must be a list, "
                f"got {type(manualtable).__name__!r}"
            )
        for bool_key in ("autocast", "emptytonull", "dieonerror"):
            val = self.config.get(bool_key)
            if val is not None and not isinstance(val, bool):
                raise ConfigurationError(
                    f"[{self.id}] Config '{bool_key}' must be a boolean, "
                    f"got {type(val).__name__!r}"
                )

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Perform type conversion on the input DataFrame.

        Args:
            input_data: Input DataFrame from upstream component.

        Returns:
            Dict with 'main' (successfully converted rows) and 'reject'
            (rows that failed conversion with error_code/error_message).

        Raises:
            DataValidationError: If dieonerror=True and any conversion fails.
        """
        if input_data is None or input_data.empty:
            self._update_stats(0, 0, 0)
            return {"main": pd.DataFrame(columns=getattr(self, "_output_columns", [])), "reject": None}

        autocast = bool(self.config.get("autocast", False))
        emptytonull = bool(self.config.get("emptytonull", False))
        dieonerror = bool(self.config.get("dieonerror", False))
        manualtable: list = self.config.get("manualtable", [])

        # Build output schema type map: column_name -> target dtype
        output_schema_types: dict[str, str] = {}
        output_schema = getattr(self, "output_schema", None)
        if output_schema:
            for col_def in self.output_schema:
                col_name = col_def.get("name", "")
                col_type = col_def.get("type", "object")
                if col_name:
                    output_schema_types[col_name] = _TALEND_TO_PANDAS.get(
                        col_type.lower(), col_type
                    )

        df = input_data.copy()

        # Step 1 -- EMPTYTONULL: replace "" with pd.NA across object columns
        if emptytonull:
            for col in df.select_dtypes(include="object").columns:
                df[col] = df[col].replace("", pd.NA)

        # Step 2 -- MANUALTABLE: explicit column-level type coercion
        # Each entry: {"input_column": "src_col", "output_column": "dst_col"}
        # When input_column == output_column this is an in-place cast.
        # The target dtype comes from the output schema for the output_column.
        manual_map: dict[str, str] = {}  # input_col -> output_col
        for entry in manualtable:
            in_col = str(entry.get("input_column", "")).strip()
            out_col = str(entry.get("output_column", "")).strip()
            if in_col:
                manual_map[in_col] = out_col or in_col

        ok_mask = pd.Series(True, index=df.index)
        error_codes: dict[int, str] = {}
        error_messages: dict[int, str] = {}

        for in_col, out_col in manual_map.items():
            if in_col not in df.columns:
                logger.warning("[%s] manualtable: input column %r not in DataFrame -- skipped", self.id, in_col)
                continue
            target_dtype = output_schema_types.get(out_col, output_schema_types.get(in_col, "object"))
            for idx in df[ok_mask].index:
                try:
                    coerced = _coerce_series(df.loc[[idx], in_col], target_dtype, in_col)
                    if in_col != out_col:
                        df.loc[idx, out_col] = coerced.iloc[0]
                        # Leave original column if different name
                    else:
                        df.loc[idx, in_col] = coerced.iloc[0]
                except (ValueError, TypeError, OverflowError) as exc:
                    if dieonerror:
                        raise DataValidationError(
                            f"[{self.id}] Type conversion failed for column {in_col!r} "
                            f"at row {idx}: {exc}"
                        ) from exc
                    ok_mask[idx] = False
                    error_codes[idx] = "CONVERSION_ERROR"
                    error_messages[idx] = (
                        f"Column {in_col!r} -> {out_col!r} ({target_dtype}): {exc}"
                    )

        # Step 3 -- AUTOCAST: infer types on columns NOT in manual_map
        if autocast:
            manual_cols = set(manual_map.keys())
            for col in df.columns:
                if col in manual_cols:
                    continue
                if col in ("error_code", "error_message"):
                    continue
                try:
                    converted = pd.to_numeric(df[col], errors="coerce")
                    # Only apply conversion for cells that parsed successfully
                    valid = converted.notna() | df[col].isna()
                    df.loc[valid, col] = converted[valid]
                except Exception:
                    pass  # autocast is best-effort; never rejects rows

        # Split ok / reject
        reject_df: Optional[pd.DataFrame] = None
        if (~ok_mask).any():
            reject_df = input_data.loc[~ok_mask].copy()
            reject_df["error_code"] = pd.Series(error_codes)
            reject_df["error_message"] = pd.Series(error_messages)
            logger.warning(
                "[%s] %d row(s) failed type conversion and routed to REJECT",
                self.id, (~ok_mask).sum(),
            )

        main_df = df[ok_mask].reset_index(drop=True)
        nb_ok = len(main_df)
        nb_reject = 0 if reject_df is None else len(reject_df)

        logger.info(
            "[%s] ConvertType complete: %d ok, %d rejected",
            self.id, nb_ok, nb_reject,
        )

        self._update_stats(nb_ok + nb_reject, nb_ok, nb_reject)
        return {"main": main_df, "reject": reject_df}
