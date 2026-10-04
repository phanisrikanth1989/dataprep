"""Converter for tFileInputExcel."""
from __future__ import annotations

from typing import Any, Dict, List

from .base import ComponentConverter, ComponentResult, TalendConnection, TalendNode
from .registry import REGISTRY
from .utils import _parse_table_rows
from .file_input import convert_path_expression, _safe_int
from ..type_mapping import convert_schema

# Parameters that V2 does not support — warn if present
_UNSUPPORTED_PARAMS = {
    "PASSWORD": "Polars read_excel does not support password-protected files",
    "GENERATION_MODE": "V2 always uses calamine engine",
    "READ_REAL_VALUE": "Not applicable with calamine engine",
    "NOVALIDATE_ON_CELL": "Not applicable with calamine engine",
    "CONVERTDATETOSTRING": "V2 handles date types via schema date_pattern",
    "THOUSANDS_SEPARATOR": "Not supported in V2",
    "WITH_FORMAT": "Not supported in V2",
}


@REGISTRY.register("tFileInputExcel")
class FileInputExcelConverter(ComponentConverter):
    """Converts tFileInputExcel to V2 file_input_excel."""

    def convert(
        self,
        node: TalendNode,
        connections: list[TalendConnection],
        context: dict,
    ) -> ComponentResult:
        params = node.params
        warnings: List[str] = []

        config: Dict[str, Any] = {
            "path": convert_path_expression(params.get("FILENAME", "")),
        }

        # --- Sheet selection (priority: ALL_SHEETS > SHEETLIST > SHEETNAME) ---
        all_sheets = params.get("ALL_SHEETS", False)
        if all_sheets:
            config["all_sheets"] = True
        else:
            sheets = self._convert_sheet_list(params.get("SHEETLIST", []))
            if sheets:
                config["sheets"] = sheets
            elif "SHEETNAME" in params:
                sheet_val = params["SHEETNAME"]
                # Numeric string -> int for index-based lookup
                try:
                    config["sheet"] = int(sheet_val)
                except (ValueError, TypeError):
                    config["sheet"] = sheet_val

        # --- Header ---
        if "HEADER" in params:
            header_val = _safe_int(params["HEADER"])
            config["has_header"] = header_val > 0
            if header_val > 1:
                warnings.append(
                    f"{node.component_id}: HEADER={header_val} — V2 has_header "
                    f"only supports a single header row; additional rows may "
                    f"need skip_rows"
                )

        # --- Footer ---
        footer = _safe_int(params.get("FOOTER", "0"))
        if footer > 0:
            config["footer_rows"] = footer

        # --- Limit ---
        limit = _safe_int(params.get("LIMIT", "0"))
        if limit > 0:
            config["limit"] = limit

        # --- Column range ---
        first_col = _safe_int(params.get("FIRST_COLUMN", "0"))
        if first_col > 0:
            config["first_column"] = first_col

        last_col = _safe_int(params.get("LAST_COLUMN", "0"))
        if last_col > 0:
            config["last_column"] = last_col

        # --- Boolean flags ---
        if "DIE_ON_ERROR" in params:
            config["die_on_error"] = params["DIE_ON_ERROR"]

        if "TRIMALL" in params:
            config["trim_all"] = params["TRIMALL"]

        if "STOPREAD_ON_EMPTYROW" in params:
            config["skip_empty_rows"] = params["STOPREAD_ON_EMPTYROW"]
            if params["STOPREAD_ON_EMPTYROW"]:
                warnings.append(
                    f"{node.component_id}: STOPREAD_ON_EMPTYROW — Talend stops "
                    f"at the first empty row; V2 skip_empty_rows filters all "
                    f"empty rows but continues reading"
                )

        # --- Schema ---
        flow_schema = node.schema.get("FLOW", [])
        if flow_schema:
            config["schema"] = convert_schema(flow_schema)

        # --- Unsupported parameters ---
        for param_name, reason in _UNSUPPORTED_PARAMS.items():
            if param_name in params:
                warnings.append(
                    f"{node.component_id}: {param_name} is not supported — {reason}"
                )

        return ComponentResult(
            component={
                "id": node.component_id,
                "type": "file_input_excel",
                "config": config,
            },
            flows=self._build_simple_flows(node, connections),
            warnings=warnings,
        )

    @staticmethod
    def _convert_sheet_list(raw_list: list) -> List[Dict[str, Any]]:
        """Convert SHEETLIST TABLE param to V2 sheets config."""
        if not raw_list:
            return []

        rows = _parse_table_rows(raw_list)
        sheets: List[Dict[str, Any]] = []
        for row in rows:
            entry: Dict[str, Any] = {"name": row.get("SHEETNAME", "")}
            if row.get("USE_REGEX", "").lower() == "true":
                entry["regex"] = True
            sheets.append(entry)
        return sheets
