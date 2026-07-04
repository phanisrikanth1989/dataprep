"""tFlowToIterate engine component -- iterates each row of an input DataFrame.

Converter JSON keys -> engine config keys (2 params per Talaxie tFlowToIterate_java.xml):

    DEFAULT_MAP (bool, default true)  -> default_map (bool)
        When true: per-row, per-column globalMap.put("<inputFlow>.<col>", value)
        Key uses the upstream FLOW connection name (e.g. "row1.filepath").

    MAP (TABLE: list of dicts)        -> map_entries (list[dict])
        Consumed only when default_map=False. Each entry:
            { "key": "<user-defined globalMap key>", "value": "<input column name>" }
        When false: per-row, per-entry globalMap.put(entry["key"], row[entry["value"]])
        User-defined keys are written verbatim -- NO prefix.

GlobalMap variables:
    DEFAULT_MAP=true  mode:  {inputFlow}.{col}           -- one key per input column, per iteration
    DEFAULT_MAP=false mode:  {entry["key"]}              -- one key per map_entries entry, per iteration
    {cid}_CURRENT_ITERATION  (int, 1-based)              -- set by BaseIterateComponent.get_next_iteration_context
    {cid}_NB_LINE            (int)                       -- written by _update_global_map after finalize

    After all iterations the last-row values for each per-row key persist (D-F6).
    pd.NA values are coerced to None before globalMap.put (RESEARCH.md Section 8 / Risk 10.2).

Statistics:
    NB_LINE        = total input rows (set in finalize())
    NB_LINE_OK     = NB_LINE
    NB_LINE_REJECT = 0

Memory note (T-10-01): df.to_dict('records') materialises all rows in memory. For very
large DataFrames this may apply memory pressure. Streaming support is deferred to Phase 12+.
"""
import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional

import pandas as pd

from ...base_iterate_component import BaseIterateComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Typed item produced per iteration
# ------------------------------------------------------------------

@dataclass
class FlowToIterateItem:
    """Typed item produced by FlowToIterate per iteration (D-A4).

    Attributes:
        row:   Dict of column->value for one input row (from to_dict('records')).
        index: 1-based iteration counter for this row.
    """
    row: Dict[str, Any]
    index: int


# ------------------------------------------------------------------
# Component
# ------------------------------------------------------------------

@REGISTRY.register("FlowToIterate", "tFlowToIterate")
class FlowToIterate(BaseIterateComponent):
    """tFlowToIterate engine component (Phase 10).

    Iterates each input row, putting per-row variables into globalMap. Per
    Talaxie tFlowToIterate_java.xml: 2 params (DEFAULT_MAP, MAP), 6 connectors,
    2 RETURN vars (NB_LINE AFTER, CURRENT_ITERATION FLOW).

    See module docstring for full config key reference, globalMap variable
    documentation, and statistics contract.
    """

    # ------------------------------------------------------------------
    # Phase 7.1 Rule 12: structural validation only
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate structural config correctness.

        Checks:
        - default_map is a bool (or missing, which defaults to True)
        - map_entries is a list when present
        - self.inputs is non-empty (set by engine from comp_config["inputs"];
          structural check allowed per Phase 7.1 Rule 12)

        Raises:
            ConfigurationError: If any structural constraint is violated.
        """
        # Validate self.inputs (structural: set by engine at startup).
        if not self.inputs:
            raise ConfigurationError(
                f"[{self.id}] tFlowToIterate requires a connected input flow; "
                "self.inputs is empty (engine sets this from comp_config['inputs'])"
            )

        # Validate default_map (bool or absent).
        default_map = self.config.get("default_map", True)
        if not isinstance(default_map, bool):
            raise ConfigurationError(
                f"[{self.id}] Config 'default_map' must be a bool, "
                f"got {type(default_map).__name__!r}"
            )

        # Validate map_entries structure (must be a list if present).
        map_entries = self.config.get("map_entries")
        if map_entries is not None and not isinstance(map_entries, list):
            raise ConfigurationError(
                f"[{self.id}] Config 'map_entries' must be a list, "
                f"got {type(map_entries).__name__!r}"
            )

    # ------------------------------------------------------------------
    # Hook 2: produce iteration items
    # ------------------------------------------------------------------

    def prepare_iterations(
        self, input_data: Optional[pd.DataFrame] = None
    ) -> Iterator[FlowToIterateItem]:
        """Materialise input DataFrame rows into an iterator of FlowToIterateItem.

        Args:
            input_data: Input DataFrame. Must be non-None (D-F1).

        Returns:
            Bounded iterator of FlowToIterateItem, one per input row.

        Raises:
            ConfigurationError: If input_data is None.
        """
        if input_data is None:
            raise ConfigurationError(
                f"[{self.id}] tFlowToIterate requires a non-None input DataFrame"
            )

        if input_data.empty:
            self.total_iterations = 0
            logger.info(
                "[%s] tFlowToIterate iterating 0 input rows (empty DataFrame, default_map=%s)",
                self.id,
                self.config.get("default_map", True),
            )
            return iter([])

        records: List[Dict[str, Any]] = input_data.to_dict("records")
        self.total_iterations = len(records)

        default_map = self.config.get("default_map", True)
        logger.info(
            "[%s] tFlowToIterate iterating %d input rows (default_map=%s)",
            self.id,
            self.total_iterations,
            default_map,
        )

        items = [
            FlowToIterateItem(row=row, index=idx)
            for idx, row in enumerate(records, start=1)
        ]
        return iter(items)

    # ------------------------------------------------------------------
    # Hook 5: write per-row globalMap entries
    # ------------------------------------------------------------------

    def set_iteration_globalmap(self, item: FlowToIterateItem) -> None:
        """Push per-row iteration variables into globalMap (Hook 5).

        DEFAULT_MAP=true:  globalMap.put("{inputFlow}.{col}", value) per column (D-F3).
        DEFAULT_MAP=false: globalMap.put(entry["key"], row[entry["value"]]) per
                           map_entries entry (D-F4). User-defined keys, no prefix.

        pd.NA values are coerced to None before put (RESEARCH Risk 10.2).
        Non-string column names are str()-coerced in key construction (Risk 10.2).

        Args:
            item: FlowToIterateItem for the current row.

        Raises:
            ConfigurationError: If DEFAULT_MAP=true and self.inputs is empty, or if
                DEFAULT_MAP=false and a map_entries value column is not in the row.
        """
        if self.global_map is None:
            return

        default_map = bool(self.config.get("default_map", True))

        if default_map:
            # D-F3: per-column key with input flow prefix.
            if not self.inputs:
                raise ConfigurationError(
                    f"[{self.id}] DEFAULT_MAP=true requires a connected input flow; "
                    "self.inputs is empty"
                )
            flow_prefix = self.inputs[0]
            for col, value in item.row.items():
                # pd.NA -> None for Java bridge compatibility (RESEARCH Risk 10.2).
                safe_value = None if value is pd.NA else value
                # Defensive str() coercion for non-string column names (Risk 10.2).
                self.global_map.put(f"{flow_prefix}.{str(col)}", safe_value)
        else:
            # D-F4: per-entry custom mapping; verbatim user-defined keys.
            map_entries = self.config.get("map_entries", [])
            for entry in map_entries:
                key = entry.get("key", "")
                value_col = entry.get("value", "")
                if value_col not in item.row:
                    raise ConfigurationError(
                        f"[{self.id}] map_entries references column {value_col!r} "
                        f"not in input row (available: {list(item.row.keys())})"
                    )
                raw_value = item.row[value_col]
                safe_value = None if raw_value is pd.NA else raw_value
                self.global_map.put(key, safe_value)

    # ------------------------------------------------------------------
    # Logging hook (D-H3) -- component-specific key info for iteration log lines
    # ------------------------------------------------------------------

    def get_iter_key_info(self, item: "FlowToIterateItem", index: int) -> str:
        """Return component-specific key info for per-iteration log lines (D-H3).

        Args:
            item: FlowToIterateItem for the current iteration.
            index: 1-based iteration index.

        Returns:
            "row_index=<index>" string for use in iteration log lines.
        """
        return f"row_index={index}"

    # ------------------------------------------------------------------
    # Hook 9: finalize -- set NB_LINE stats
    # ------------------------------------------------------------------

    def finalize(self) -> None:
        """Hook 9: set NB_LINE statistics after all iterations complete.

        Sets NB_LINE = total input rows (D-F6: Executor's _update_global_map
        will publish {cid}_NB_LINE from stats["NB_LINE"] after finalize).
        """
        nb_line = max(self.total_iterations, 0)
        self.stats["NB_LINE"] = nb_line
        self.stats["NB_LINE_OK"] = nb_line
        self.stats["NB_LINE_REJECT"] = 0
        logger.info(
            "[%s] tFlowToIterate finalized: NB_LINE=%d", self.id, nb_line
        )
