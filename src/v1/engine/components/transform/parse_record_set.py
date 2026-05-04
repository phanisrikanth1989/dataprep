"""ParseRecordSet engine component.

Talend equivalent: tParseRecordSet

In Talend, this component parses a JDBC ResultSet column into individual output
columns. In the Python engine there is no JDBC ResultSet -- the practical
equivalent is an input column that contains a **list of dicts** (or a single dict
for one-row expansion). Each dict's keys are the attribute names referenced in
``attribute_table`` and the values become the output column values.

Typical use-case (Python engine):
  - An upstream component stores a structured object in a single column
    (e.g., a JSON-parsed dict or a database row returned as a dict).
  - ParseRecordSet flattens each dict in that column into a new row with
    the columns named in the output schema.

Config keys (resolved by BaseComponent before _process is called):
    recordset_field     (str, required) -- input column that contains the
                        list-of-dicts (or single dict) to expand
    attribute_table     (list[str], default []) -- ordered list of attribute
                        (key) names to extract from each dict; maps to output
                        schema columns in the same order

GlobalMap variables set:
    {id}_NB_LINE / NB_LINE_OK / NB_LINE_REJECT via _update_stats()
"""
import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, DataValidationError

logger = logging.getLogger(__name__)


@REGISTRY.register("ParseRecordSet", "tParseRecordSet")
class ParseRecordSet(BaseComponent):
    """Expands a list-of-dicts column into individual output rows and columns.

    Each input row with a non-null ``recordset_field`` column is expanded into
    one output row per dict in the list.  When ``recordset_field`` contains a
    single dict it is treated as a one-element list.

    The ``attribute_table`` config lists the dict keys to extract (in order).
    Keys absent from a dict produce null values in the corresponding output column.
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Check structural config -- key presence and container types only (Rule 12).

        Raises:
            ConfigurationError: If ``recordset_field`` is missing/empty, or
                ``attribute_table`` is not a list.
        """
        if not self.config.get("recordset_field"):
            raise ConfigurationError(
                f"[{self.id}] Missing required config key 'recordset_field'"
            )
        attr_table = self.config.get("attribute_table", [])
        if not isinstance(attr_table, list):
            raise ConfigurationError(
                f"[{self.id}] Config 'attribute_table' must be a list, "
                f"got {type(attr_table).__name__!r}"
            )

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Expand the recordset column into individual output rows.

        Args:
            input_data: Input DataFrame containing the recordset column.

        Returns:
            Dict with 'main' (expanded rows) and 'reject' None.

        Raises:
            DataValidationError: If ``recordset_field`` column does not exist
                in the input DataFrame.
        """
        if input_data is None or input_data.empty:
            self._update_stats(0, 0, 0)
            return {"main": pd.DataFrame(), "reject": None}

        recordset_field = str(self.config["recordset_field"]).strip()
        attribute_table: List[str] = self.config.get("attribute_table", [])

        if recordset_field not in input_data.columns:
            raise DataValidationError(
                f"[{self.id}] recordset_field column {recordset_field!r} not found "
                f"in input DataFrame. Available columns: {list(input_data.columns)}"
            )

        logger.info(
            "[%s] ParseRecordSet: expanding column %r using %d attribute(s)",
            self.id, recordset_field, len(attribute_table),
        )

        expanded_rows: list = []
        skipped = 0

        for _, row in input_data.iterrows():
            cell = row[recordset_field]

            # Null / missing recordset -- skip row
            if cell is None or (isinstance(cell, float) and pd.isna(cell)):
                skipped += 1
                logger.debug("[%s] Null recordset at row -- skipped", self.id)
                continue

            # Normalise to list
            if isinstance(cell, dict):
                records: list = [cell]
            elif isinstance(cell, (list, tuple)):
                records = list(cell)
            else:
                # Try JSON string
                try:
                    import json
                    parsed = json.loads(str(cell))
                    records = [parsed] if isinstance(parsed, dict) else list(parsed)
                except Exception:
                    logger.warning(
                        "[%s] Cannot parse recordset value of type %s -- skipped",
                        self.id, type(cell).__name__,
                    )
                    skipped += 1
                    continue

            for record in records:
                if not isinstance(record, dict):
                    logger.warning(
                        "[%s] Record entry is not a dict (type=%s) -- skipped",
                        self.id, type(record).__name__,
                    )
                    skipped += 1
                    continue

                if attribute_table:
                    # Extract only the requested attributes in order
                    out_row = {attr: record.get(attr, pd.NA) for attr in attribute_table}
                else:
                    # No attribute table -- emit all keys from the record
                    out_row = dict(record)

                expanded_rows.append(out_row)

        if expanded_rows:
            main_df = pd.DataFrame(expanded_rows)
        else:
            # Produce an empty DataFrame with the right columns
            cols = attribute_table if attribute_table else []
            main_df = pd.DataFrame(columns=cols)

        nb_line = len(main_df)

        if skipped:
            logger.warning(
                "[%s] %d input row(s) skipped (null or unrecognised recordset value)",
                self.id, skipped,
            )

        logger.info("[%s] ParseRecordSet complete: %d output row(s)", self.id, nb_line)

        self._update_stats(nb_line, nb_line, 0)
        return {"main": main_df, "reject": None}
