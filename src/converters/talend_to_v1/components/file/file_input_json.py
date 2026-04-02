"""Converter for tFileInputJSON -> FileInputJSON."""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tFileInputJSON")
class FileInputJSONConverter(ComponentConverter):
    """Convert a Talend tFileInputJSON node to v1 FileInputJSON.

    Supports three READ_BY modes:
    - JSONPATH (default): uses JSON_LOOP_QUERY + MAPPING_JSONPATH
    - XPATH: uses LOOP_QUERY + MAPPINGXPATH (with NODECHECK)
    - JSONPATH_WITHOUTPUT_LOOP: uses MAPPING (no loop query)
    """

    @staticmethod
    def _parse_mapping(raw: list, include_nodecheck: bool = False) -> list:
        """Parse mapping TABLE from flat elementRef/value pairs.

        Uses "push-on-next-SCHEMA_COLUMN" state machine: accumulates all
        fields (SCHEMA_COLUMN, QUERY, NODECHECK) per row, flushes when the
        next SCHEMA_COLUMN arrives or at end of loop.

        Input (from XML parser):
            [{"elementRef": "SCHEMA_COLUMN", "value": "user_id"},
             {"elementRef": "QUERY", "value": "\"$.id\""},
             {"elementRef": "NODECHECK", "value": "false"},  # only in MAPPINGXPATH
             {"elementRef": "SCHEMA_COLUMN", "value": "username"}, ...]

        Output:
            [{"column": "user_id", "jsonpath": "$.id", "nodecheck": False}, ...]
        """
        if not raw or not isinstance(raw, list):
            return []

        result: list = []
        current: dict = {}

        for entry in raw:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "").strip('"')

            if ref == "SCHEMA_COLUMN":
                # Flush previous row when we hit a new SCHEMA_COLUMN
                if current and "column" in current:
                    result.append(current)
                current = {"column": val, "jsonpath": ""}
                if include_nodecheck:
                    current["nodecheck"] = False
            elif ref == "QUERY":
                current["jsonpath"] = val
            elif ref == "NODECHECK" and include_nodecheck:
                current["nodecheck"] = val.lower() in ("true", "1")

        # Flush the last accumulated row
        if current and "column" in current:
            result.append(current)

        return result

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # Determine read mode
        read_by = self._get_str(node, "READ_BY", "JSONPATH")

        # Extract the active mapping table based on mode
        if read_by == "XPATH":
            mapping = self._parse_mapping(
                node.params.get("MAPPINGXPATH", []), include_nodecheck=True)
        elif read_by == "JSONPATH_WITHOUTPUT_LOOP":
            mapping = self._parse_mapping(
                node.params.get("MAPPING", []))
        else:
            # Default: JSONPATH mode
            mapping = self._parse_mapping(
                node.params.get("MAPPING_JSONPATH", []))

        config: Dict[str, Any] = {
            # Core params
            "filename": self._get_str(node, "FILENAME"),
            "json_loop_query": self._get_str(node, "JSON_LOOP_QUERY"),
            "loop_query": self._get_str(node, "LOOP_QUERY"),
            "read_by": read_by,
            "json_path_version": self._get_str(node, "JSON_PATH_VERSION", "2_1_0"),
            "mapping": mapping,
            "useurl": self._get_bool(node, "USEURL", False),
            "urlpath": self._get_str(node, "URLPATH"),
            "use_loop_as_root": self._get_bool(node, "USE_LOOP_AS_ROOT", True),
            "die_on_error": self._get_bool(node, "DIE_ON_ERROR", False),
            "encoding": self._get_str(node, "ENCODING", "UTF-8"),
            # Advanced params
            "advanced_separator": self._get_bool(node, "ADVANCED_SEPARATOR", False),
            "thousands_separator": self._get_str(node, "THOUSANDS_SEPARATOR", ","),
            "decimal_separator": self._get_str(node, "DECIMAL_SEPARATOR", "."),
            "check_date": self._get_bool(node, "CHECK_DATE", False),
            # Metadata
            "tstatcatcher_stats": self._get_bool(node, "TSTATCATCHER_STATS", False),
            "label": self._get_str(node, "LABEL"),
        }

        # Warn when filename is empty — it is mandatory in Talend
        if not config["filename"]:
            warnings.append("FILENAME is empty — this is a required parameter")

        # Warn when json_loop_query is empty — typically required
        if not config["json_loop_query"] and read_by not in ("JSONPATH_WITHOUTPUT_LOOP", "XPATH"):
            warnings.append("JSON_LOOP_QUERY is empty — this is usually required")

        # Engine-gap warnings
        if read_by == "XPATH":
            warnings.append(
                "READ_BY=XPATH: engine does not support XPath mode for JSON files"
            )
        if read_by == "JSONPATH_WITHOUTPUT_LOOP":
            warnings.append(
                "READ_BY=JSONPATH_WITHOUTPUT_LOOP: engine does not support no-loop mode"
            )
        if config["check_date"]:
            warnings.append(
                "CHECK_DATE=true: engine date validation is non-functional "
                "(schema uses 'date_pattern' key but engine reads 'pattern')"
            )
        if config["useurl"]:
            warnings.append(
                "USEURL=true: engine URL reading is bare-bones "
                "(no timeout, headers, auth)"
            )

        component = self._build_component_dict(
            node=node,
            type_name="FileInputJSON",
            config=config,
            schema={"input": [], "output": self._parse_schema(node)},
        )

        return ComponentResult(component=component, warnings=warnings)
