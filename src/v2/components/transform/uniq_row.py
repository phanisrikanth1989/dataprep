"""UniqRow component for v2 engine.

Deduplicates rows based on key columns with per-column case sensitivity.
Equivalent of Talend tUniqRow.

Config mapping:
  key_columns: list[dict] -- [{column, case_sensitive}, ...] (required)
  keep: str -- 'first'/'last'/'none'/'any' (default 'first')
  maintain_order: bool -- preserve input row order (default True)
  duplicate_output: bool -- emit duplicate rows on 'duplicate' output (default False)
  only_once: bool -- only first duplicate per key to duplicate output (default False)
"""
import logging
from enum import Enum
from typing import ClassVar, Dict, List

import polars as pl

from ..base import TransformComponent
from ..capabilities import FeatureSupport, Support
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


class UniqRowFeature(str, Enum):
    """Talend tUniqRow features mapped to v2 support levels."""

    dedup = "dedup"
    per_column_case_sensitivity = "per_column_case_sensitivity"
    keep_modes = "keep_modes"
    keep_any = "keep_any"
    only_once_each_duplicated_key = "only_once_each_duplicated_key"
    maintain_order = "maintain_order"
    unique_duplicate_outputs = "unique_duplicate_outputs"
    is_virtual_component = "is_virtual_component"
    buffer_size = "buffer_size"
    temp_directory = "temp_directory"
    change_hash_bigdecimal = "change_hash_bigdecimal"
    tstatcatcher_stats = "tstatcatcher_stats"
    label = "label"


@REGISTRY.register("uniq_row", "unique_row", "unique", "deduplicate")
class UniqRow(TransformComponent):
    """Deduplicate rows based on key columns with per-column case sensitivity.

    Config:
        key_columns: list[dict] -- Each dict has 'column' (str) and
            'case_sensitive' (bool, default True).  Required.
        keep: str -- Which row to keep per duplicate group: 'first'
            (default), 'last', 'none', or 'any' (v2-only).
        maintain_order: bool -- Preserve input row order (default True).
        duplicate_output: bool -- When True, emit duplicate rows on the
            'duplicate' output key (default False).  Enables barrier mode.
        only_once: bool -- When True with duplicate_output, emit only the
            first duplicate per key group (default False).

    Example:
        {"key_columns": [{"column": "id", "case_sensitive": true}]}
        {"key_columns": [{"column": "name", "case_sensitive": false}],
         "keep": "last", "duplicate_output": true, "only_once": true}
    """

    SUPPORTED_FEATURES: ClassVar[Dict[str, FeatureSupport]] = {
        UniqRowFeature.dedup: FeatureSupport(
            support=Support.FULL,
            note="Core deduplication based on key columns via Polars unique()",
        ),
        UniqRowFeature.per_column_case_sensitivity: FeatureSupport(
            support=Support.FULL,
            note=(
                "Each key column has independent case_sensitive flag; "
                "case-insensitive keys lowercased via str.to_lowercase() (vectorized Rust)"
            ),
        ),
        UniqRowFeature.keep_modes: FeatureSupport(
            support=Support.FULL,
            note="Talend keep='first'/'last'/'none' mapped directly to Polars unique() keep parameter",
        ),
        UniqRowFeature.keep_any: FeatureSupport(
            support=Support.FULL,
            note=(
                "v2-only: keep='any' gives Polars optimizer freedom when caller "
                "does not need deterministic first-seen behavior"
            ),
        ),
        UniqRowFeature.only_once_each_duplicated_key: FeatureSupport(
            support=Support.FULL,
            note=(
                "When enabled, only first duplicate per key emitted to "
                "duplicate output (group_by + head(1))"
            ),
        ),
        UniqRowFeature.maintain_order: FeatureSupport(
            support=Support.FULL,
            note=(
                "Default True preserves input row order (Talend-compatible). "
                "Set False for streaming-eligible unstable dedup."
            ),
        ),
        UniqRowFeature.unique_duplicate_outputs: FeatureSupport(
            support=Support.FULL,
            note=(
                "Dual named outputs: 'unique' (first-seen rows) and "
                "'duplicate' (subsequent occurrences)"
            ),
        ),
        UniqRowFeature.is_virtual_component: FeatureSupport(
            support=Support.UNSUPPORTED,
            note=(
                "Disk-based processing has no Polars equivalent. "
                "Lazy evaluation + streaming is v2's answer to large data."
            ),
        ),
        UniqRowFeature.buffer_size: FeatureSupport(
            support=Support.UNSUPPORTED,
            note="Accessory to IS_VIRTUAL_COMPONENT; not applicable in v2.",
        ),
        UniqRowFeature.temp_directory: FeatureSupport(
            support=Support.UNSUPPORTED,
            note="Accessory to IS_VIRTUAL_COMPONENT; not applicable in v2.",
        ),
        UniqRowFeature.change_hash_bigdecimal: FeatureSupport(
            support=Support.NOT_PLANNED,
            note=(
                "Polars Decimal dtype has limited trailing-zero normalization. "
                "No native support."
            ),
        ),
        UniqRowFeature.tstatcatcher_stats: FeatureSupport(
            support=Support.NOT_PLANNED,
            note="tStatCatcher is a v1/Talend concept; use Python logging instead",
        ),
        UniqRowFeature.label: FeatureSupport(
            support=Support.FULL,
            note="Component label for display/debugging",
        ),
    }

    # ---- post-init ----

    def _post_init(self) -> None:
        """Cache key-column config for apply()."""
        key_columns = self.config.get("key_columns", [])
        self._keep = self.config.get("keep", "first")
        self._maintain_order = self.config.get("maintain_order", True)
        self._duplicate_output = self.config.get("duplicate_output", False)
        self._only_once = self.config.get("only_once", False)

        # Build subset list and case-insensitive column map
        self._subset: List[str] = [kc["column"] for kc in key_columns if "column" in kc]
        self._case_insensitive_cols: List[str] = [
            kc["column"]
            for kc in key_columns
            if "column" in kc and not kc.get("case_sensitive", True)
        ]
        self._temp_col_map: Dict[str, str] = {}
        if self._case_insensitive_cols:
            self._temp_col_map = {
                col: f"__uniq_lower_{col}" for col in self._case_insensitive_cols
            }

    # ---- barrier ----

    @property
    def is_barrier(self) -> bool:
        """UniqRow is a barrier when duplicate output is enabled (two outputs)."""
        return self._duplicate_output

    # ---- validation ----

    def validate(self) -> List[str]:
        """Validate component configuration."""
        errors: List[str] = []
        key_columns = self.config.get("key_columns", [])
        if not key_columns:
            errors.append("UniqRow requires 'key_columns' in config")
        for entry in key_columns:
            if "column" not in entry:
                errors.append("Each key_columns entry must have a 'column' key")
        if self._keep not in ("first", "last", "none", "any"):
            errors.append(
                f"UniqRow 'keep' must be 'first', 'last', 'none', or 'any', "
                f"got '{self._keep}'"
            )
        return errors

    # ---- apply ----

    def apply(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        """Deduplicate input rows based on key columns."""
        data = inputs.get("main")
        if data is None:
            return {}

        if isinstance(data, pl.DataFrame):
            data = data.lazy()

        # Build dedup subset, adding temp lowercased columns for case-insensitive keys
        if self._case_insensitive_cols:
            data = data.with_columns(
                [
                    pl.col(col).str.to_lowercase().alias(self._temp_col_map[col])
                    for col in self._case_insensitive_cols
                ]
            )
            dedup_subset = [
                self._temp_col_map.get(col, col) for col in self._subset
            ]
        else:
            dedup_subset = self._subset if self._subset else None

        logger.debug(
            "UniqRow %s: dedup on %s, keep=%s, duplicate_output=%s",
            self.component_id,
            self._subset or "all",
            self._keep,
            self._duplicate_output,
        )

        if not self._duplicate_output:
            # Single output path -- fully lazy
            unique_frame = data.unique(
                subset=dedup_subset,
                keep=self._keep,
                maintain_order=self._maintain_order,
            )
            if self._case_insensitive_cols:
                unique_frame = unique_frame.drop(list(self._temp_col_map.values()))
            return {"unique": unique_frame}

        # ---- Barrier path: need both unique and duplicate frames ----
        # Strategy: add row index, find unique row indices, anti-join for duplicates
        _ROW_NR = "__uniq_row_nr"
        indexed = data.with_row_index(_ROW_NR)

        unique_indexed = indexed.unique(
            subset=dedup_subset,
            keep=self._keep,
            maintain_order=self._maintain_order,
        )
        unique_nrs = unique_indexed.select(_ROW_NR)

        duplicate_indexed = indexed.join(unique_nrs, on=_ROW_NR, how="anti")

        # Apply only_once: keep only first duplicate per key group
        if self._only_once and dedup_subset:
            duplicate_indexed = duplicate_indexed.unique(
                subset=dedup_subset,
                keep="first",
                maintain_order=self._maintain_order,
            )

        # Drop helper columns (row nr + temp lowercase cols)
        drop_cols = [_ROW_NR]
        if self._case_insensitive_cols:
            drop_cols.extend(self._temp_col_map.values())

        unique_frame = unique_indexed.drop(drop_cols)
        duplicate_frame = duplicate_indexed.drop(drop_cols)

        return {"unique": unique_frame, "duplicate": duplicate_frame}
