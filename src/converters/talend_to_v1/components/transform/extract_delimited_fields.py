"""Converter for Talend tExtractDelimitedFields component.

tExtractDelimitedFields splits a single input field into multiple output columns
using a configurable field separator.  It supports advanced separator options
(thousands / decimal), optional trimming, and field count / date validation.

Config mapping (13 params total):
  FIELD                -> field (str, PREV_COLUMN_LIST, default "")
  IGNORE_SOURCE_NULL   -> ignore_source_null (bool, default True)
  FIELDSEPARATOR       -> fieldseparator (str, default ";")
  DIE_ON_ERROR         -> die_on_error (bool, default False)
  ADVANCED_SEPARATOR   -> advanced_separator (bool, default False)
  THOUSANDS_SEPARATOR  -> thousands_separator (str, default ",")
  DECIMAL_SEPARATOR    -> decimal_separator (str, default ".")
  TRIM                 -> trim (bool, default False)
  CHECK_FIELDS_NUM     -> check_fields_num (bool, default False)
  CHECK_DATE           -> check_date (bool, default False)
  TSTATCATCHER_STATS   -> tstatcatcher_stats (bool, framework, default False)
  LABEL                -> label (str, framework, default "")

Phantom params removed (not in _java.xml):
  - ROWSEPARATOR     - does not exist in tExtractDelimitedFields
  - REMOVE_EMPTY_ROW - does not exist in tExtractDelimitedFields
  - TRIMALL          - correct XML name is TRIM (not TRIMALL)
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register("tExtractDelimitedFields")
class ExtractDelimitedFieldsConverter(ComponentConverter):
    """Convert a Talend tExtractDelimitedFields node to v1 ExtractDelimitedFields."""

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
        config["field"] = self._get_str(node, "FIELD", "")
        config["ignore_source_null"] = self._get_bool(node, "IGNORE_SOURCE_NULL", True)
        config["fieldseparator"] = self._get_str(node, "FIELDSEPARATOR", ";")
        config["die_on_error"] = self._get_bool(node, "DIE_ON_ERROR", False)

        # ---- 2. Advanced parameters ----
        config["advanced_separator"] = self._get_bool(node, "ADVANCED_SEPARATOR", False)
        config["thousands_separator"] = self._get_str(node, "THOUSANDS_SEPARATOR", ",")
        config["decimal_separator"] = self._get_str(node, "DECIMAL_SEPARATOR", ".")
        config["trim"] = self._get_bool(node, "TRIM", False)
        config["check_fields_num"] = self._get_bool(node, "CHECK_FIELDS_NUM", False)
        config["check_date"] = self._get_bool(node, "CHECK_DATE", False)

        # ---- 3. Framework parameters (ALWAYS LAST) ----
        config["tstatcatcher_stats"] = self._get_bool(node, "TSTATCATCHER_STATS", False)
        config["label"] = self._get_str(node, "LABEL", "")

        # ---- 4. Validation warnings ----
        if not config["fieldseparator"]:
            warnings.append(
                "FIELDSEPARATOR is empty -- extraction may not split correctly"
            )

        # ---- 5. Schema: transform passthrough ----
        schema_cols = self._parse_schema(node)
        schema = {"input": schema_cols, "output": schema_cols}

        # ---- 6. Engine gap needs_review entries ----
        # Engine reads 'field_separator' but converter outputs 'fieldseparator' per D-38
        needs_review.append({
            "issue": "Engine reads 'field_separator' but converter outputs 'fieldseparator' per D-38 -- config key mismatch",
            "component": node.component_id,
            "severity": "engine_gap",
        })
        # ---- 7. Build component wrapper ----
        component = self._build_component_dict(
            node=node,
            type_name="ExtractDelimitedFields",
            config=config,
            schema=schema,
        )

        # ---- 8. Return ----
        return ComponentResult(
            component=component,
            warnings=warnings,
            needs_review=needs_review,
        )
