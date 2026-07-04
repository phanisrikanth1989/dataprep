"""
ExtractJSONFields - extract fields from a JSON string column using JSONPath.

Talend equivalent: tExtractJSONFields

Config keys consumed by this engine component:
  read_by            (str)  "JSONPATH" or "XPATH". Default: "JSONPATH".
                            XPATH mode is handled as best-effort JSONPath.
  jsonfield          (str)  Name of the JSON source column. Defaults to first column.
  json_loop_query    (str)  JSONPath loop expression used when read_by=JSONPATH.
  loop_query         (str)  Loop expression used when read_by=XPATH.
  mapping_4_jsonpath (list) [{schema_column, query}] JSONPATH mode column mappings.
  mapping            (list) [{schema_column, query, nodecheck, isarray}] XPATH mode.
  use_loop_as_root   (bool) True (default): mapping queries run against the loop item.
                            False: mapping queries run against the full JSON document.
  die_on_error       (bool) Raise on error instead of routing to REJECT. Default: False.
"""
import json
import logging
from typing import Any, Dict, List, Optional

import pandas as pd
from jsonpath_ng import parse as jsonpath_parse

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ComponentExecutionError, ConfigurationError

logger = logging.getLogger(__name__)

# REJECT error codes
_ERR_NO_JSON = "NO_JSON"
_ERR_PARSE = "PARSE_ERROR"


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _try_compile(query: str, component_id: str):
    """Compile a JSONPath expression string. Returns None on parse failure."""
    try:
        return jsonpath_parse(query)
    except Exception as exc:
        logger.warning("[%s] Cannot compile JSONPath '%s': %s", component_id, query, exc)
        return None


def _is_null(value: Any) -> bool:
    """Return True when *value* is None, NaN, pd.NA, or pd.NaT.

    Non-scalar containers (list, dict, ndarray) are never null. ``pd.isna``
    can either raise ``TypeError`` (some shapes) or return an array that
    breaks ``bool()`` with a ``ValueError`` (multi-element list / ndarray) --
    both arise only for non-scalar input and both mean "not null".
    """
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _build_reject_row(
    row: pd.Series,
    original_json: str,
    code: str,
    msg: str,
) -> Dict[str, Any]:
    """Build a REJECT output row with Talend-standard error columns."""
    reject = dict(row)
    reject["errorJSONField"] = original_json
    reject["errorCode"] = code
    reject["errorMessage"] = msg
    return reject


@REGISTRY.register("ExtractJSONFields", "tExtractJSONFields")
class ExtractJSONFields(BaseComponent):
    """Extract fields from a JSON string column using JSONPath queries.

    Reads the JSON value from the column named by ``jsonfield`` (defaults to
    the first column if unset), applies a loop query to iterate over nodes,
    then maps each node's values to output columns via JSONPath expressions.

    Mode dispatch (``read_by``):

    - ``JSONPATH``: uses ``json_loop_query`` and ``mapping_4_jsonpath``.
    - ``XPATH``: uses ``loop_query`` and ``mapping`` (processed as JSONPath,
      best-effort; native XPath not natively supported).

    ``use_loop_as_root=True`` (default): mapping queries are evaluated against
    each loop item. ``False``: mapping queries run against the full document.

    Empty ``query`` in a mapping entry means passthrough -- the value is
    copied from the matching input column.
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate structural config (key presence and container shape only).

        Note:
            Content checks (non-empty loop query, non-empty mapping list) are
            intentionally deferred to _process() after context variable
            resolution (Rule 12 of MANUAL_COMPONENT_AUTHORING.md).
        """
        mapping = self.config.get("mapping")
        if mapping is not None and not isinstance(mapping, list):
            raise ConfigurationError(
                f"[{self.id}] Config 'mapping' must be a list, "
                f"got {type(mapping).__name__}"
            )
        mapping_jp = self.config.get("mapping_4_jsonpath")
        if mapping_jp is not None and not isinstance(mapping_jp, list):
            raise ConfigurationError(
                f"[{self.id}] Config 'mapping_4_jsonpath' must be a list, "
                f"got {type(mapping_jp).__name__}"
            )
        die_on_error = self.config.get("die_on_error", False)
        if not isinstance(die_on_error, bool):
            raise ConfigurationError(
                f"[{self.id}] Config 'die_on_error' must be a boolean, "
                f"got {type(die_on_error).__name__}"
            )

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Extract JSON fields from each input row.

        Args:
            input_data: DataFrame containing a JSON string column.

        Returns:
            ``{'main': pd.DataFrame, 'reject': pd.DataFrame}``
        """
        if input_data is None or input_data.empty:
            return {"main": pd.DataFrame(), "reject": pd.DataFrame()}

        rows_in = len(input_data)
        die_on_error: bool = self.config.get("die_on_error", False)
        use_loop_as_root: bool = self.config.get("use_loop_as_root", True)

        # ---- Mode dispatch: choose loop query and mapping table ----
        read_by: str = self.config.get("read_by", "JSONPATH").upper()
        if read_by == "JSONPATH":
            loop_query: str = self.config.get("json_loop_query", "")
            mapping: List[Dict[str, Any]] = self.config.get("mapping_4_jsonpath") or []
        else:
            # XPATH mode: best-effort JSONPath
            loop_query = self.config.get("loop_query", "")
            mapping = self.config.get("mapping") or []
            if loop_query:
                logger.warning(
                    "[%s] read_by=XPATH is not natively supported; "
                    "attempting JSONPath evaluation on loop_query='%s'",
                    self.id, loop_query,
                )

        # ---- Resolve source column ----
        jsonfield: str = self.config.get("jsonfield", "")
        json_col = (
            jsonfield
            if jsonfield and jsonfield in input_data.columns
            else input_data.columns[0]
        )

        # ---- Pre-compile all JSONPath expressions once ----
        loop_expr = _try_compile(loop_query, self.id) if loop_query else None
        col_exprs: Dict[str, Any] = {}
        for m in mapping:
            q = m.get("query", "")
            if q and q not in col_exprs:
                col_exprs[q] = _try_compile(q, self.id)

        # ---- Process each input row ----
        main_output: List[Dict[str, Any]] = []
        reject_output: List[Dict[str, Any]] = []

        for _, row in input_data.iterrows():
            raw_val = row[json_col]
            original_str = str(raw_val) if not _is_null(raw_val) else ""

            # Guard NaN / None
            if _is_null(raw_val):
                if die_on_error:
                    raise ComponentExecutionError(
                        self.id,
                        f"{_ERR_NO_JSON}: column '{json_col}' is null",
                    )
                reject_output.append(
                    _build_reject_row(
                        row, "", _ERR_NO_JSON, f"column '{json_col}' is null"
                    )
                )
                continue

            # Parse JSON string (skip if already a dict/list from upstream)
            json_data = raw_val
            if not isinstance(json_data, (dict, list)):
                try:
                    json_data = json.loads(str(raw_val))
                except (json.JSONDecodeError, TypeError, ValueError) as exc:
                    if die_on_error:
                        raise ComponentExecutionError(
                            self.id, f"{_ERR_PARSE}: {exc}"
                        ) from exc
                    reject_output.append(
                        _build_reject_row(row, original_str, _ERR_PARSE, str(exc))
                    )
                    continue

            # Apply loop query
            if loop_expr is not None:
                try:
                    loop_items = [m.value for m in loop_expr.find(json_data)]
                except Exception as exc:
                    if die_on_error:
                        raise ComponentExecutionError(
                            self.id, f"{_ERR_PARSE}: loop query error: {exc}"
                        ) from exc
                    reject_output.append(
                        _build_reject_row(
                            row, original_str, _ERR_PARSE, f"loop query error: {exc}"
                        )
                    )
                    continue

                if not loop_items:
                    # No matches → 0 output rows (Talend parity: no fallback to root)
                    continue
            else:
                loop_items = [json_data]

            # Extract fields for each loop item
            for item in loop_items:
                context = item if use_loop_as_root else json_data
                out_row: Dict[str, Any] = {}

                for m in mapping:
                    col = m.get("schema_column") or m.get("column") or ""
                    if not col:
                        continue
                    query = m.get("query", "")
                    if not query:
                        # Passthrough: copy value from matching input column
                        out_row[col] = row.get(col, None)
                        continue
                    expr = col_exprs.get(query)
                    if expr is None:
                        out_row[col] = ""
                        continue
                    try:
                        matches = [match.value for match in expr.find(context)]
                    except Exception as exc:
                        logger.warning(
                            "[%s] JSONPath '%s' on col '%s' failed: %s",
                            self.id, query, col, exc,
                        )
                        out_row[col] = ""
                        continue

                    if not matches:
                        out_row[col] = ""
                    elif len(matches) == 1:
                        v = matches[0]
                        out_row[col] = json.dumps(v) if isinstance(v, (list, dict)) else v
                    else:
                        out_row[col] = json.dumps(matches)

                main_output.append(out_row)

        main_df = pd.DataFrame(main_output)
        reject_df = pd.DataFrame(reject_output)
        rows_out = len(main_df)
        rows_rejected = len(reject_df)

        self._update_stats(rows_in, rows_out, rows_rejected)
        logger.info(
            "[%s] done: in=%d, out=%d, reject=%d",
            self.id, rows_in, rows_out, rows_rejected,
        )
        return {"main": main_df, "reject": reject_df}
