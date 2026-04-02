"""Converter for tFileInputXML -> FileInputXML.

Critical fixes:
  - Config key `filename` → `filepath` (engine reads `filepath` or `FILENAME`, not `filename`)
  - MAPPING format changed to engine-expected raw triplet format (SCHEMA_COLUMN/QUERY/NODECHECK)
  - Encoding default fixed from UTF-8 to ISO-8859-15
"""
import logging
from typing import Any, Dict, List, Optional

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileInputXML")
class FileInputXMLConverter(ComponentConverter):
    """Convert a Talend tFileInputXML node to v1 FileInputXML."""

    @staticmethod
    def _parse_mapping_for_engine(raw: list) -> list:
        """Parse MAPPING TABLE and output engine-expected raw triplet format.

        The engine's _parse_xml() (lines 449-461) scans for literal labels:
            mapping[i].get("column") == "SCHEMA_COLUMN"
            mapping[i+1].get("column") == "QUERY"
        and skips by 3 (i += 3) to jump over NODECHECK.

        Input (from XML parser):
            [{"elementRef": "SCHEMA_COLUMN", "value": "order_id"},
             {"elementRef": "QUERY", "value": "\"@id\""},
             {"elementRef": "NODECHECK", "value": "false"},
             {"elementRef": "SCHEMA_COLUMN", "value": "customer"}, ...]

        Output (engine-compatible triplet format):
            [{"column": "SCHEMA_COLUMN", "xpath": "order_id"},
             {"column": "QUERY", "xpath": "@id"},
             {"column": "NODECHECK", "xpath": "false"},
             {"column": "SCHEMA_COLUMN", "xpath": "customer"}, ...]

        Uses push-on-next-SCHEMA_COLUMN state machine. NODECHECK defaults
        to "false" if missing (mandatory for engine's i+=3 skip logic).
        """
        if not raw or not isinstance(raw, list):
            return []

        result: list = []
        current_col: Optional[str] = None
        current_query: str = ""
        current_nodecheck: str = "false"

        for entry in raw:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "").strip('"')

            if ref == "SCHEMA_COLUMN":
                # Flush previous row as 3 entries when we hit a new SCHEMA_COLUMN
                if current_col is not None:
                    result.append({"column": "SCHEMA_COLUMN", "xpath": current_col})
                    result.append({"column": "QUERY", "xpath": current_query})
                    result.append({"column": "NODECHECK", "xpath": current_nodecheck})
                current_col = val
                current_query = ""
                current_nodecheck = "false"
            elif ref == "QUERY":
                current_query = val
            elif ref == "NODECHECK":
                current_nodecheck = val if val else "false"

        # Flush the last accumulated row
        if current_col is not None:
            result.append({"column": "SCHEMA_COLUMN", "xpath": current_col})
            result.append({"column": "QUERY", "xpath": current_query})
            result.append({"column": "NODECHECK", "xpath": current_nodecheck})

        return result

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # Parse MAPPING table into engine-expected triplet format
        mapping = self._parse_mapping_for_engine(
            self._get_param(node, "MAPPING", []))

        # Limit: int if non-empty, None if empty/missing
        limit_str = self._get_str(node, "LIMIT")
        limit = int(limit_str) if limit_str and limit_str.isdigit() else None

        config: Dict[str, Any] = {
            # Core params — CRITICAL: key is "filepath" not "filename"
            "filepath": self._get_str(node, "FILENAME"),
            "loop_query": self._get_str(node, "LOOP_QUERY"),
            "mapping": mapping,
            "limit": limit,
            "die_on_error": self._get_bool(node, "DIE_ON_ERROR", False),
            "encoding": self._get_str(node, "ENCODING", "ISO-8859-15"),
            "ignore_ns": self._get_bool(node, "IGNORE_NS", False),
            # Advanced params
            "ignore_dtd": self._get_bool(node, "IGNORE_DTD", False),
            "generation_mode": self._get_str(node, "GENERATION_MODE", "Dom4j"),
            "advanced_separator": self._get_bool(node, "ADVANCED_SEPARATOR", False),
            "thousands_separator": self._get_str(node, "THOUSANDS_SEPARATOR", ","),
            "decimal_separator": self._get_str(node, "DECIMAL_SEPARATOR", "."),
            "check_date": self._get_bool(node, "CHECK_DATE", False),
            "use_separator": self._get_bool(node, "USE_SEPARATOR", False),
            "field_separator": self._get_str(node, "FIELD_SEPARATOR", ","),
            # Metadata
            "tstatcatcher_stats": self._get_bool(node, "TSTATCATCHER_STATS", False),
            "label": self._get_str(node, "LABEL"),
        }

        # Warn when filepath is empty — it is mandatory in Talend
        if not config["filepath"]:
            warnings.append("FILENAME is empty — this is a required parameter")

        # Warn when loop_query is empty — it is required
        if not config["loop_query"]:
            warnings.append("LOOP_QUERY is empty — this is a required parameter")

        # Engine-gap warnings
        if config["generation_mode"] != "Dom4j":
            warnings.append(
                f"GENERATION_MODE={config['generation_mode']}: "
                f"engine only supports Dom4j-style processing"
            )
        if config["advanced_separator"]:
            warnings.append(
                "ADVANCED_SEPARATOR=true: engine does not support "
                "locale-aware number formatting for XML"
            )
        if config["check_date"]:
            warnings.append(
                "CHECK_DATE=true: engine does not validate "
                "date fields for XML input"
            )
        if config["use_separator"]:
            warnings.append(
                "USE_SEPARATOR=true: engine does not support "
                "field separator concatenation for XML"
            )
        if config["ignore_ns"]:
            warnings.append(
                "IGNORE_NS=true: engine does not implement namespace "
                "stripping; namespaces will be auto-qualified in XPath expressions"
            )
        if limit is not None:
            warnings.append(
                f"LIMIT={limit}: engine does not implement row limits "
                f"for XML input; the entire document will be processed"
            )

        component = self._build_component_dict(
            node=node,
            type_name="FileInputXML",
            config=config,
            schema={"input": [], "output": self._parse_schema(node)},
        )

        return ComponentResult(component=component, warnings=warnings)
