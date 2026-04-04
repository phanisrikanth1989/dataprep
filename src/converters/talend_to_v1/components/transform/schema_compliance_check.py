"""Converter for Talend tSchemaComplianceCheck component.

tSchemaComplianceCheck validates incoming rows against a schema definition,
checking types, lengths, nullability, and date formats.  The schema is
extracted from the FLOW metadata.  Four original boolean flags plus seven
additional parameters (CUSTOMER, CHECK_ANOTHER, FAST_DATE_CHECK,
IGNORE_TIMEZONE, CHECK_STRING_BY_BYTE_LENGTH, CHARSET, and two TABLEs --
CHECKCOLS and EMPTY_NULL_TABLE) control the checking behaviour.

Config mapping (15 params total):
  CHECK_ALL                    -> check_all (bool, default True)
  CUSTOMER                     -> customer (bool, default False)
  CHECK_ANOTHER                -> check_another (bool, default False)
  CHECKCOLS                    -> checkcols (list of dicts, stride-5 TABLE)
  SUB_STRING                   -> sub_string (bool, default False)
  STRICT_DATE_CHECK            -> strict_date_check (bool, default False)
  ALL_EMPTY_ARE_NULL           -> all_empty_are_null (bool, default True)
  FAST_DATE_CHECK              -> fast_date_check (bool, default False)
  IGNORE_TIMEZONE              -> ignore_timezone (bool, default False)
  EMPTY_NULL_TABLE             -> empty_null_table (list of dicts, stride-2 TABLE)
  CHECK_STRING_BY_BYTE_LENGTH  -> check_string_by_byte_length (bool, default False)
  CHARSET                      -> charset (str, default "")
  TSTATCATCHER_STATS           -> tstatcatcher_stats (bool, default False)
  LABEL                        -> label (str, default "")
"""
import logging
from typing import Any, Dict, List

from ..base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# CHECKCOLS TABLE constants (BASED_ON_SCHEMA stride-5)
# ------------------------------------------------------------------
_CHECKCOLS_FIELDS = ("SCHEMA_COLUMN", "SELECTED_TYPE", "DATEPATTERN", "NULLABLE", "MAX_LENGTH")
_CHECKCOLS_GROUP_SIZE = len(_CHECKCOLS_FIELDS)  # 5

# ------------------------------------------------------------------
# EMPTY_NULL_TABLE constants (BASED_ON_SCHEMA stride-2)
# ------------------------------------------------------------------
_EMPTY_NULL_FIELDS = ("SCHEMA_COLUMN", "EMPTY_NULL")
_EMPTY_NULL_GROUP_SIZE = len(_EMPTY_NULL_FIELDS)  # 2


def _parse_checkcols(raw: Any) -> List[Dict[str, Any]]:
    """Parse CHECKCOLS TABLE into list of per-column check dicts.

    Each group of 5 consecutive elementRef entries maps to one row:
      SCHEMA_COLUMN  -> column (str)
      SELECTED_TYPE  -> selected_type (str)
      DATEPATTERN    -> date_pattern (str)
      NULLABLE       -> nullable (bool)
      MAX_LENGTH     -> max_length (bool)

    Incomplete trailing groups (< 5 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, Any]] = []
    for i in range(0, len(raw), _CHECKCOLS_GROUP_SIZE):
        group = raw[i : i + _CHECKCOLS_GROUP_SIZE]
        if len(group) < _CHECKCOLS_GROUP_SIZE:
            break
        row: Dict[str, Any] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "SCHEMA_COLUMN":
                row["column"] = val.strip('"')
            elif ref == "SELECTED_TYPE":
                row["selected_type"] = val.strip('"')
            elif ref == "DATEPATTERN":
                row["date_pattern"] = val.strip('"')
            elif ref == "NULLABLE":
                row["nullable"] = val.lower() in ("true", "1")
            elif ref == "MAX_LENGTH":
                row["max_length"] = val.lower() in ("true", "1")
        if row:
            result.append(row)
    return result


def _parse_empty_null_table(raw: Any) -> List[Dict[str, Any]]:
    """Parse EMPTY_NULL_TABLE into list of per-column null-handling dicts.

    Each group of 2 consecutive elementRef entries maps to one row:
      SCHEMA_COLUMN  -> column (str)
      EMPTY_NULL     -> empty_is_null (bool)

    Incomplete trailing groups (< 2 entries) are skipped.
    """
    if not raw or not isinstance(raw, list):
        return []
    result: List[Dict[str, Any]] = []
    for i in range(0, len(raw), _EMPTY_NULL_GROUP_SIZE):
        group = raw[i : i + _EMPTY_NULL_GROUP_SIZE]
        if len(group) < _EMPTY_NULL_GROUP_SIZE:
            break
        row: Dict[str, Any] = {}
        for entry in group:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("elementRef", "")
            val = entry.get("value", "")
            if ref == "SCHEMA_COLUMN":
                row["column"] = val.strip('"')
            elif ref == "EMPTY_NULL":
                row["empty_is_null"] = val.lower() in ("true", "1")
        if row:
            result.append(row)
    return result


@REGISTRY.register("tSchemaComplianceCheck")
class SchemaComplianceCheckConverter(ComponentConverter):
    """Convert a Talend tSchemaComplianceCheck node into a v1 SchemaComplianceCheck.

    tSchemaComplianceCheck validates incoming rows against a schema definition,
    checking types, lengths, nullability, and date formats.  The schema is
    extracted from the FLOW metadata.  Fifteen parameters control the checking
    behaviour, including two TABLE params (CHECKCOLS stride-5, EMPTY_NULL_TABLE
    stride-2) that use BASED_ON_SCHEMA auto-population.
    """

    def convert(
        self,
        node: TalendNode,
        connections: List[TalendConnection],
        context: Dict[str, Any],
    ) -> ComponentResult:
        warnings: List[str] = []

        # ------------------------------------------------------------------
        # Parse schema from FLOW metadata (uses converted Python types)
        # ------------------------------------------------------------------
        schema_cols = self._parse_schema(node)

        if not schema_cols:
            warnings.append(
                "No FLOW schema columns found — compliance check has no "
                "schema to validate against"
            )

        # Build config-level schema list with the subset of fields the
        # compliance checker needs: name, type, nullable, length.
        config_schema: List[Dict[str, Any]] = []
        for col in schema_cols:
            entry: Dict[str, Any] = {
                "name": col["name"],
                "type": col["type"],
                "nullable": col["nullable"],
            }
            if "length" in col:
                entry["length"] = col["length"]
            config_schema.append(entry)

        # ------------------------------------------------------------------
        # RADIO MODE params (mutually exclusive in GROUP="MODE")
        # ------------------------------------------------------------------
        check_all = self._get_bool(node, "CHECK_ALL", default=True)
        customer = self._get_bool(node, "CUSTOMER", default=False)
        check_another = self._get_bool(node, "CHECK_ANOTHER", default=False)

        # ------------------------------------------------------------------
        # Boolean configuration flags
        # ------------------------------------------------------------------
        sub_string = self._get_bool(node, "SUB_STRING", default=False)
        strict_date_check = self._get_bool(node, "STRICT_DATE_CHECK", default=False)
        all_empty_are_null = self._get_bool(node, "ALL_EMPTY_ARE_NULL", default=True)

        # ------------------------------------------------------------------
        # Advanced parameters
        # ------------------------------------------------------------------
        fast_date_check = self._get_bool(node, "FAST_DATE_CHECK", default=False)
        ignore_timezone = self._get_bool(node, "IGNORE_TIMEZONE", default=False)
        check_string_by_byte_length = self._get_bool(node, "CHECK_STRING_BY_BYTE_LENGTH", default=False)
        charset = self._get_str(node, "CHARSET", default="")

        # ------------------------------------------------------------------
        # TABLE parameters (BASED_ON_SCHEMA)
        # ------------------------------------------------------------------
        checkcols = _parse_checkcols(node.params.get("CHECKCOLS", []))
        empty_null_table = _parse_empty_null_table(node.params.get("EMPTY_NULL_TABLE", []))

        # ------------------------------------------------------------------
        # Framework parameters (universal Talend Studio injection)
        # ------------------------------------------------------------------
        tstatcatcher_stats = self._get_bool(node, "TSTATCATCHER_STATS", False)
        label = self._get_str(node, "LABEL")

        # ------------------------------------------------------------------
        # Build config dict
        # ------------------------------------------------------------------
        config: Dict[str, Any] = {
            "schema": config_schema,
            "check_all": check_all,
            "customer": customer,
            "check_another": check_another,
            "checkcols": checkcols,
            "sub_string": sub_string,
            "strict_date_check": strict_date_check,
            "all_empty_are_null": all_empty_are_null,
            # Advanced parameters
            "fast_date_check": fast_date_check,
            "ignore_timezone": ignore_timezone,
            "empty_null_table": empty_null_table,
            "check_string_by_byte_length": check_string_by_byte_length,
            "charset": charset,
            # Framework parameters
            "tstatcatcher_stats": tstatcatcher_stats,
            "label": label,
        }

        # ------------------------------------------------------------------
        # Engine gap needs_review entries
        # Engine reads ONLY schema. ALL other params are engine gaps.
        # Framework params (tstatcatcher_stats, label) are exempt per convention.
        # ------------------------------------------------------------------
        needs_review: List[Dict[str, Any]] = []
        _engine_gap_keys = [
            "check_all", "customer", "check_another", "checkcols",
            "sub_string", "strict_date_check", "all_empty_are_null",
            "fast_date_check", "ignore_timezone", "empty_null_table",
            "check_string_by_byte_length", "charset",
        ]
        for key in _engine_gap_keys:
            needs_review.append({
                "issue": f"Engine does not read '{key}' from config",
                "component": node.component_id,
                "severity": "engine_gap",
            })

        # ------------------------------------------------------------------
        # Transform schema: input == output (passthrough from FLOW)
        # ------------------------------------------------------------------
        schema = {"input": schema_cols, "output": schema_cols}

        component = self._build_component_dict(
            node=node,
            type_name="SchemaComplianceCheck",
            config=config,
            schema=schema,
        )

        return ComponentResult(component=component, warnings=warnings, needs_review=needs_review)
