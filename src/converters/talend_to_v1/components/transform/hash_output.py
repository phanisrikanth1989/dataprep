"""Converter for Talend tHashOutput component.

tHashOutput stores incoming data in an in-memory hash structure so that
downstream components (typically tHashInput) can look up rows by key.
No v1 engine implementation exists -- all config keys are engine_gap.

Config mapping (10 params total -- 8 unique + 2 framework):
    LINK_WITH                      -> link_with                      (bool, default False)
    LIST                           -> list                           (str, default "")
    DATA_WRITE_MODEL               -> data_write_model               (CLOSED_LIST: MEMORY/PERSISTENT, default "MEMORY")
    BASE_FILE_PATH                 -> base_file_path                 (str, default "")
    MEMORY_HEAP_MAX_SIZE           -> memory_heap_max_size           (str, default "2")
    KEYS_MANAGEMENT                -> keys_management                (CLOSED_LIST: KEEP_FIRST/KEEP_LAST/KEEP_ALL, default "KEEP_ALL")
    APPEND                         -> append                         (bool, default True)
    HASH_KEY_FROM_INPUT_CONNECTOR  -> hash_key_from_input_connector  (bool, hidden show=false, default False)
    TSTATCATCHER_STATS             -> tstatcatcher_stats             (bool, framework, default False)
    LABEL                          -> label                          (str, framework, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tHashOutput")
class HashOutputConverter(ComponentConverter):
    """Convert a Talend tHashOutput node into a v1 tHashOutput component.

    No v1 engine exists for this component. All params are extracted
    explicitly with correct types and defaults per _java.xml. A single
    consolidated needs_review entry is emitted per D-84/D-27.

    Schema is passthrough: input equals output.
    """

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []
        needs_review: List[Dict[str, Any]] = []

        # ---- 1. Core parameters ----
        config: Dict[str, Any] = {}
        config["link_with"] = self._get_bool(node, "LINK_WITH", False)
        config["list"] = self._get_str(node, "LIST", "")
        config["data_write_model"] = self._get_str(node, "DATA_WRITE_MODEL", "MEMORY")
        config["base_file_path"] = self._get_str(node, "BASE_FILE_PATH", "")
        config["memory_heap_max_size"] = self._get_str(node, "MEMORY_HEAP_MAX_SIZE", "2")
        config["keys_management"] = self._get_str(node, "KEYS_MANAGEMENT", "KEEP_ALL")
        config["append"] = self._get_bool(node, "APPEND", True)
        config["hash_key_from_input_connector"] = self._get_bool(
            node, "HASH_KEY_FROM_INPUT_CONNECTOR", False
        )

        # ---- 2. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 3. Schema (passthrough: input == output) ----
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        # ---- 4. Consolidated needs_review (no engine -- D-84/D-27) ----
        needs_review.append({
            "issue": (
                "No v1 engine implementation exists for tHashOutput -- "
                "all config keys are unread by the engine"
            ),
            "component": node.component_id,
            "severity": "engine_gap",
        })

        # ---- 5. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="tHashOutput",
            config=config,
            schema=schema,
        )

        # ---- 6. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
