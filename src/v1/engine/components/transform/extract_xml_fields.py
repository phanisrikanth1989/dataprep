"""ExtractXMLField engine component.

Talend equivalent: tExtractXMLField

Processes XML data stored in a DataFrame column, applying an XPath loop
query to iterate over XML nodes and extracting field values using per-column
XPath expressions from the ``mapping`` config table.

Config keys (all resolved by BaseComponent before _process is called):
    xmlfield         (str, default 'line')   -- column containing XML data
    loop_query       (str, required)         -- XPath to select repeated nodes
    mapping          (list, required)        -- [{query, nodecheck}, ...]
    limit            (str, default "")       -- max nodes per input row (empty=no limit)
    die_on_error     (bool, default False)   -- raise on parse error vs REJECT
    ignore_ns        (bool, default False)   -- strip XML namespaces
    tstatcatcher_stats (bool, default False) -- framework
    label            (str, default "")      -- framework

Mapping entries from the converter have the form ``{"query": str, "nodecheck": bool}``.
Output column names are taken from ``output_schema`` by index (BASED_ON_SCHEMA=true
means mapping[i] aligns with output_schema[i]).

GlobalMap variables set:
    NB_LINE / NB_LINE_OK / NB_LINE_REJECT via _update_stats()
"""
import logging
from typing import Any, Dict, Optional

import pandas as pd
from lxml import etree

from ...base_component import BaseComponent
from ...component_registry import REGISTRY
from ...exceptions import ConfigurationError, DataValidationError

logger = logging.getLogger(__name__)


@REGISTRY.register("ExtractXMLField", "tExtractXMLField")
class ExtractXMLField(BaseComponent):
    """Extracts fields from an XML column using XPath queries.

    Parses the XML value in the column named by ``xmlfield``, applies
    ``loop_query`` to select nodes, then maps each node's values to output
    columns via the per-column XPath expressions in ``mapping``.

    Output column names are reconciled with ``output_schema`` by position
    (BASED_ON_SCHEMA=true guarantees index alignment between mapping and schema).
    """

    # Error codes for REJECT output
    _ERR_NO_XML = "NO_XML"
    _ERR_NODECHECK = "NODECHECK_FAIL"
    _ERR_PARSE = "PARSE_ERROR"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Check key presence and container types only (Rule 12)."""
        mapping = self.config.get("mapping", [])
        if not isinstance(mapping, list):
            raise ConfigurationError(
                f"[{self.id}] Config 'mapping' must be a list"
            )
        for bool_key, default in (
            ("die_on_error", False),
            ("ignore_ns", False),
        ):
            val = self.config.get(bool_key, default)
            if not isinstance(val, bool):
                raise ConfigurationError(
                    f"[{self.id}] Config '{bool_key}' must be a boolean"
                )

    def _process(self, input_data: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Extract XML fields using XPath queries.

        Args:
            input_data: Input DataFrame with an XML column.

        Returns:
            Dict with ``main`` (extracted rows DataFrame) and
            ``reject`` (failed rows DataFrame).
        """
        if input_data is None or input_data.empty:
            self._update_stats(0, 0, 0)
            return {"main": pd.DataFrame(), "reject": pd.DataFrame()}

        # ---- resolved config ----
        xmlfield = self.config.get("xmlfield", "line")
        loop_query = self.config.get("loop_query", "")
        mapping = self.config.get("mapping", [])
        limit_raw = self.config.get("limit", "")
        die_on_error = self.config.get("die_on_error", False)
        ignore_ns = self.config.get("ignore_ns", False)

        # Coerce limit in _process (may be context-var string -- Rule 12).
        # limit_specified=True means a non-empty value was given.
        # Talend limit=0 means "read nothing"; empty/absent means unlimited.
        limit_specified = bool(limit_raw and str(limit_raw).strip())
        try:
            limit = int(limit_raw) if limit_specified else None
        except (ValueError, TypeError):
            limit = None

        # ---- reconcile mapping with output_schema by index ----
        output_schema = getattr(self, "output_schema", None) or []
        resolved_mapping: list = []
        for i, m in enumerate(mapping):
            # Prefer explicit schema_column from converter (stride-3 MAPPING),
            # fall back to index-aligned output_schema, then synthetic name.
            explicit_col = m.get("schema_column") or ""
            col_name = (
                explicit_col
                or (output_schema[i]["name"] if i < len(output_schema) else None)
                or f"field_{i + 1}"
            )
            resolved_mapping.append({
                "schema_column": col_name,
                "query": m.get("query", ""),
                "nodecheck": bool(m.get("nodecheck", False)),
            })

        # Validate source column exists (fall back to 'line')
        src_col = xmlfield if xmlfield in input_data.columns else "line"

        rows_in = len(input_data)
        main_rows: list = []
        reject_rows: list = []
        rows_ok = 0
        rows_reject = 0

        for _, row in input_data.iterrows():
            xml_string = row.get(src_col, None)

            try:
                is_null = pd.isna(xml_string)
            except (TypeError, ValueError):
                is_null = False

            if is_null:
                reject_rows.append(
                    self._make_reject_row(row, xml_string, self._ERR_NO_XML, "No XML data")
                )
                rows_reject += 1
                continue

            try:
                # Security: disable DTD, entity resolution, and network access
                # to prevent XXE attacks and DTD-bomb memory exhaustion.
                parser = etree.XMLParser(
                    recover=True,
                    resolve_entities=False,
                    load_dtd=False,
                    no_network=True,
                )
                root = etree.fromstring(str(xml_string).encode("utf-8"), parser=parser)

                # Namespace stripping -- uses iter() (lxml 5.x compatible, not getiterator())
                if ignore_ns:
                    for elem in root.iter():
                        if callable(elem.tag):
                            continue
                        i = elem.tag.find("}")
                        if i >= 0:
                            elem.tag = elem.tag[i + 1:]

                nodes = root.xpath(loop_query)
                if not isinstance(nodes, list):
                    nodes = [nodes] if nodes is not None else []
                # Talend limit=0 means "read nothing"; None/absent means unlimited.
                if limit is not None:
                    nodes = nodes[:limit]

                for node in nodes:
                    out_row: dict = {}
                    node_ok = True

                    for m in resolved_mapping:
                        col = m["schema_column"]
                        query = m["query"]
                        nodecheck = m["nodecheck"]
                        value = None

                        # Empty query = passthrough: copy value from input row
                        # (Talend behavior when QUERY is blank in the MAPPING table).
                        if not query:
                            out_row[col] = row.get(col, None)
                            continue

                        if nodecheck:
                            try:
                                check_result = node.xpath(query)
                                if not check_result:
                                    node_ok = False
                                    break
                            except Exception:
                                node_ok = False
                                break

                        try:
                            result = node.xpath(query)
                            if isinstance(result, list):
                                value = result[0] if result else None
                                if hasattr(value, "text"):
                                    value = value.text
                            else:
                                value = result
                        except Exception:
                            value = None

                        out_row[col] = value

                    if node_ok:
                        main_rows.append(out_row)
                        rows_ok += 1
                    else:
                        reject_rows.append(
                            self._make_reject_row(
                                row, xml_string, self._ERR_NODECHECK, "Node check failed"
                            )
                        )
                        rows_reject += 1

            except Exception as exc:
                logger.warning("[%s] XML parse error: %s", self.id, exc)
                if die_on_error:
                    raise DataValidationError(
                        f"[{self.id}] XML parsing failed: {exc}"
                    ) from exc
                reject_rows.append(
                    self._make_reject_row(row, xml_string, self._ERR_PARSE, str(exc))
                )
                rows_reject += 1

        main_df = pd.DataFrame(main_rows) if main_rows else pd.DataFrame()
        reject_df = pd.DataFrame(reject_rows) if reject_rows else pd.DataFrame()

        self._update_stats(rows_in, rows_ok, rows_reject)
        logger.info(
            "[%s] done: in=%d ok=%d reject=%d",
            self.id,
            rows_in,
            rows_ok,
            rows_reject,
        )
        return {"main": main_df, "reject": reject_df}

    @staticmethod
    def _make_reject_row(
        row: pd.Series, xml_string: Any, code: str, msg: str
    ) -> Dict[str, Any]:
        """Build a reject row dict with error detail columns."""
        reject_row = {k: row.get(k, None) for k in row.index}
        reject_row["errorXMLField"] = xml_string
        reject_row["errorCode"] = code
        reject_row["errorMessage"] = msg
        return reject_row
