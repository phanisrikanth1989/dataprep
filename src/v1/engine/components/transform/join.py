"""Engine component for Join (tJoin).

Joins main input with lookup input using key columns.
Matching rows go to main output; non-matching rows go to reject output.

Config keys consumed (4 total):
  use_inner_join   (bool, default False)    -- True for inner join, False for left outer
  join_key         (list[dict])             -- [{input_column, lookup_column}, ...]
  use_lookup_cols  (bool, default False)    -- include lookup columns in output
  lookup_cols      (list[dict])             -- [{output_column, lookup_column}, ...]
"""
import logging
from typing import Any, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import (
    ComponentExecutionError,
    ConfigurationError,
    DataValidationError,
)

logger = logging.getLogger(__name__)

# Sentinel value used to prevent null keys from matching during merge.
# Null keys must never match (SQL/Talend semantics). We replace NaN with
# this sentinel before merge, then reclassify any matched row whose key
# columns contain the sentinel as unmatched.
_NULL_SENTINEL = "__DATAPREP_NULL_SENTINEL__"


@REGISTRY.register("Join", "tJoin")
class Join(BaseComponent):
    """tJoin engine implementation.

    Joins two input DataFrames (main and lookup) on configurable key columns.
    Supports inner and left outer join modes with first-match deduplication
    on the lookup side. Null keys never match (SQL/Talend semantics).

    Config keys:
        use_inner_join: True for inner join, False for left outer (default False).
        join_key: List of key mappings [{input_column, lookup_column}, ...].
        use_lookup_cols: Whether to include lookup columns in output (default False).
        lookup_cols: Lookup columns to include [{output_column, lookup_column}, ...].
    """

    # ------------------------------------------------------------------
    # Configuration Validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate component configuration.

        Raises:
            ConfigurationError: If join_key is missing, empty, or malformed.
        """
        join_key = self.config.get("join_key")
        if not join_key:
            raise ConfigurationError(
                f"[{self.id}] Missing or empty required config key 'join_key'"
            )
        if not isinstance(join_key, list):
            raise ConfigurationError(
                f"[{self.id}] Config 'join_key' must be a list, got {type(join_key).__name__}"
            )
        for i, mapping in enumerate(join_key):
            if not isinstance(mapping, dict):
                raise ConfigurationError(
                    f"[{self.id}] join_key[{i}] must be a dict, got {type(mapping).__name__}"
                )
            if "input_column" not in mapping or not isinstance(mapping["input_column"], str):
                raise ConfigurationError(
                    f"[{self.id}] join_key[{i}] missing or invalid 'input_column' (must be str)"
                )
            if "lookup_column" not in mapping or not isinstance(mapping["lookup_column"], str):
                raise ConfigurationError(
                    f"[{self.id}] join_key[{i}] missing or invalid 'lookup_column' (must be str)"
                )

    # ------------------------------------------------------------------
    # Input Resolution
    # ------------------------------------------------------------------

    def _resolve_inputs(
        self, input_data: Any
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Resolve main and lookup DataFrames from input_data.

        The OutputRouter delivers a dict keyed by flow name. If the dict
        already has 'main' and 'lookup' keys, use them directly. Otherwise
        map via ``self.inputs`` (first = main, second = lookup).

        Args:
            input_data: Dict from OutputRouter (flow_name -> DataFrame).

        Returns:
            Tuple of (main_df, lookup_df).

        Raises:
            ConfigurationError: If exactly two non-None inputs are not available.
        """
        if not isinstance(input_data, dict):
            raise ConfigurationError(
                f"[{self.id}] Expected dict input_data, got {type(input_data).__name__}"
            )

        # Try direct 'main'/'lookup' keys first
        if "main" in input_data and "lookup" in input_data:
            main_df = input_data["main"]
            lookup_df = input_data["lookup"]
        elif hasattr(self, "inputs") and isinstance(self.inputs, list) and len(self.inputs) >= 2:
            main_df = input_data.get(self.inputs[0])
            lookup_df = input_data.get(self.inputs[1])
        else:
            # Last resort: take first two values in insertion order
            values = [v for v in input_data.values() if v is not None]
            if len(values) >= 2:
                main_df = values[0]
                lookup_df = values[1]
            else:
                raise ConfigurationError(
                    f"[{self.id}] Requires exactly 2 inputs (main + lookup), "
                    f"got keys: {list(input_data.keys())}"
                )

        if main_df is None or lookup_df is None:
            raise ConfigurationError(
                f"[{self.id}] Both main and lookup inputs must be non-None"
            )
        if not isinstance(main_df, pd.DataFrame) or not isinstance(lookup_df, pd.DataFrame):
            raise ConfigurationError(
                f"[{self.id}] Both inputs must be DataFrames"
            )

        return main_df, lookup_df

    # ------------------------------------------------------------------
    # Core Processing
    # ------------------------------------------------------------------

    def _process(self, input_data: Any = None) -> dict:
        """Join main and lookup DataFrames.

        Args:
            input_data: Dict of flow_name -> DataFrame from OutputRouter.

        Returns:
            Dict with 'main' (joined rows) and 'reject' (unmatched main rows
            or None if empty).
        """
        main_df, lookup_df = self._resolve_inputs(input_data)
        main_row_count = len(main_df)

        # -- Read config --
        use_inner_join = self.config.get("use_inner_join", False)
        join_key = self.config["join_key"]
        use_lookup_cols = self.config.get("use_lookup_cols", False)
        lookup_cols = self.config.get("lookup_cols", [])
        case_sensitive = self.config.get("case_sensitive", True)

        main_key_cols = [k["input_column"] for k in join_key]
        lookup_key_cols = [k["lookup_column"] for k in join_key]

        logger.info(
            f"[{self.id}] Join started: main={main_row_count} rows, "
            f"lookup={len(lookup_df)} rows, mode={'inner' if use_inner_join else 'left outer'}"
        )

        try:
            # -- First-match dedup on lookup (Pitfall 7) --
            lookup_deduped = lookup_df.drop_duplicates(subset=lookup_key_cols, keep="first")

            # -- Prepare merge copies with sentinel for null keys (D-03, JOIN-08) --
            merge_main = main_df.copy()
            merge_lookup = lookup_deduped.copy()

            # Case-insensitive handling (future-proof, only if explicitly False)
            if not case_sensitive:
                for col in main_key_cols:
                    if col in merge_main.columns:
                        merge_main[col] = merge_main[col].astype(str).str.lower()
                for col in lookup_key_cols:
                    if col in merge_lookup.columns:
                        merge_lookup[col] = merge_lookup[col].astype(str).str.lower()

            # Replace NaN in key columns with sentinel so they don't match
            for col in main_key_cols:
                if col in merge_main.columns:
                    merge_main[col] = merge_main[col].fillna(_NULL_SENTINEL)
            for col in lookup_key_cols:
                if col in merge_lookup.columns:
                    merge_lookup[col] = merge_lookup[col].fillna(_NULL_SENTINEL)

            # -- Single-pass merge with indicator --
            merged = pd.merge(
                merge_main,
                merge_lookup,
                left_on=main_key_cols,
                right_on=lookup_key_cols,
                how="left",
                indicator=True,
                suffixes=("", "_lookup"),
            )

            # -- Classify rows --
            matched = merged["_merge"] == "both"
            unmatched = merged["_merge"] == "left_only"

            # Sentinel filtering: null keys must not match even if both sides have sentinel
            for col in main_key_cols:
                if col in merged.columns:
                    sentinel_mask = merged[col] == _NULL_SENTINEL
                    # Move sentinel-matched rows from matched to unmatched
                    matched = matched & ~sentinel_mask
                    unmatched = unmatched | sentinel_mask

            # -- Build main output --
            if use_inner_join:
                main_out = merged[matched].copy()
            else:
                main_out = merged.copy()

            # -- Build reject output (unmatched main rows only) --
            reject_rows = merged[unmatched].copy()

            # -- Determine columns to keep --
            original_main_cols = list(main_df.columns)

            # INCLUDE_LOOKUP toggle (D-05, JOIN-04)
            if use_lookup_cols and lookup_cols:
                # Keep main columns + specified lookup output columns
                keep_cols = list(original_main_cols)
                for lc in lookup_cols:
                    out_col = lc.get("output_column", "")
                    lk_col = lc.get("lookup_column", "")
                    # The merged column name: if it collides with main, it has _lookup suffix
                    if lk_col in main_out.columns:
                        source_col = lk_col
                    elif lk_col + "_lookup" in main_out.columns:
                        source_col = lk_col + "_lookup"
                    else:
                        source_col = None

                    if source_col and source_col not in keep_cols:
                        # Rename if output_column differs from source
                        if out_col and out_col != source_col:
                            main_out = main_out.rename(columns={source_col: out_col})
                            if source_col in reject_rows.columns:
                                reject_rows = reject_rows.rename(columns={source_col: out_col})
                            keep_cols.append(out_col)
                        else:
                            keep_cols.append(source_col)
                    elif out_col and out_col not in keep_cols:
                        # Column may already be named correctly
                        if out_col in main_out.columns:
                            keep_cols.append(out_col)

                # Filter to only keep_cols that exist
                main_out = main_out[[c for c in keep_cols if c in main_out.columns]]
            else:
                # No lookup columns: keep only original main columns
                main_out = main_out[[c for c in original_main_cols if c in main_out.columns]]

            # Reject always contains only original main columns
            reject_rows = reject_rows[[c for c in original_main_cols if c in reject_rows.columns]]

            # -- Drop merge artifacts --
            if "_merge" in main_out.columns:
                main_out = main_out.drop(columns=["_merge"])
            if "_merge" in reject_rows.columns:
                reject_rows = reject_rows.drop(columns=["_merge"])

            # -- Restore NaN from sentinel in output --
            main_out = main_out.replace(_NULL_SENTINEL, pd.NA)
            reject_rows = reject_rows.replace(_NULL_SENTINEL, pd.NA)

            # -- Drop duplicate lookup key columns that differ from main keys --
            for mk, lk in zip(main_key_cols, lookup_key_cols):
                if mk != lk and lk in main_out.columns:
                    main_out = main_out.drop(columns=[lk], errors="ignore")
                lk_suffixed = lk + "_lookup"
                if lk_suffixed in main_out.columns:
                    main_out = main_out.drop(columns=[lk_suffixed], errors="ignore")

            # -- Reject schema (D-08, JOIN-03) --
            reject_schema = getattr(self, "reject_schema", [])
            if reject_schema and not reject_rows.empty:
                schema_cols = [col["name"] for col in reject_schema]
                # Add errorCode and errorMessage
                if "errorCode" in schema_cols:
                    reject_rows["errorCode"] = "JOIN_REJECT"
                if "errorMessage" in schema_cols:
                    reject_rows["errorMessage"] = "No matching lookup row"
                # Reindex to match schema column order
                reject_rows = reject_rows.reindex(columns=schema_cols)

            # -- ERROR_MESSAGE globalMap (D-06, JOIN-05) --
            if self.global_map and not reject_rows.empty:
                self.global_map.put(
                    f"{self.id}_ERROR_MESSAGE",
                    f"Join produced {len(reject_rows)} rejected rows"
                )

            # -- Stats --
            reject_count = len(reject_rows)
            main_out_count = len(main_out)
            self._update_stats(main_row_count, main_out_count, reject_count)

            logger.info(
                f"[{self.id}] Join complete: input={main_row_count}, "
                f"output={main_out_count}, reject={reject_count}"
            )

            return {
                "main": main_out,
                "reject": reject_rows if not reject_rows.empty else None,
            }

        except (ConfigurationError, DataValidationError):
            raise
        except Exception as exc:
            error_msg = f"Join failed: {exc}"
            logger.error(f"[{self.id}] {error_msg}")

            # Set ERROR_MESSAGE in globalMap
            if self.global_map:
                self.global_map.put(f"{self.id}_ERROR_MESSAGE", str(exc))

            die_on_error = self.config.get("die_on_error", True)
            if die_on_error:
                raise ComponentExecutionError(self.id, error_msg, exc) from exc

            # Graceful degradation: empty main, full main as reject
            logger.warning(
                f"[{self.id}] Graceful degradation: empty main, full main as reject"
            )
            self._update_stats(main_row_count, 0, main_row_count)
            return {"main": pd.DataFrame(), "reject": main_df}
