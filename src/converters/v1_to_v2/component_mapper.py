"""Map V1 component types and configs to V2 equivalents."""
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .expression_mapper import (
    ExpressionResult,
    convert_date_pattern,
    translate_expression,
)

# V1 Talend type IDs -> V2 type names
_TYPE_MAP = {
    "id_String": "string",
    "id_Integer": "integer",
    "id_Long": "integer",
    "id_Float": "float",
    "id_Double": "float",
    "id_Boolean": "boolean",
    "id_Date": "date",
    "id_BigDecimal": "str",
}


@dataclass
class ComponentResult:
    """Result of mapping a single V1 component."""

    component: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)
    expressions_needing_review: List[Dict[str, str]] = field(default_factory=list)


def _convert_type(v1_type: str) -> str:
    """Convert a V1 Talend type ID to a V2 type name."""
    return _TYPE_MAP.get(v1_type, v1_type.lower())


def _convert_schema(
    schema_cols: List[Dict], component_id: str
) -> List[Dict[str, Any]]:
    """Convert V1 schema columns to V2 format.

    Keeps only ``name``, ``type``, and (when present) ``date_pattern``.
    Drops V1-only fields like ``nullable``, ``precision``, ``scale``.
    """
    result = []
    for col in schema_cols:
        v2_col: Dict[str, Any] = {
            "name": col["name"],
            "type": _convert_type(col.get("type", "id_String")),
        }
        # Convert date pattern if present
        java_pattern = col.get("date_pattern")
        if java_pattern:
            v2_col["date_pattern"] = convert_date_pattern(java_pattern)
        result.append(v2_col)
    return result


# ---------------------------------------------------------------------------
# Individual component mappers
# ---------------------------------------------------------------------------


def _map_file_input_delimited(v1: Dict) -> ComponentResult:
    cfg = v1.get("config", {})
    v2_config: Dict[str, Any] = {"path": cfg.get("filepath", "")}
    warnings: List[str] = []

    if "delimiter" in cfg:
        v2_config["delimiter"] = cfg["delimiter"]
    if "encoding" in cfg:
        v2_config["encoding"] = cfg["encoding"]

    header_rows = cfg.get("header_rows")
    if header_rows is not None:
        v2_config["has_header"] = header_rows > 0
    elif "has_header" in cfg:
        v2_config["has_header"] = cfg["has_header"]

    if cfg.get("skip_rows"):
        v2_config["skip_rows"] = cfg["skip_rows"]
    if "die_on_error" in cfg:
        v2_config["die_on_error"] = cfg["die_on_error"]

    # text_enclosure -> quote_char
    text_enclosure = cfg.get("text_enclosure")
    if text_enclosure is not None:
        v2_config["quote_char"] = text_enclosure

    # escape_char warning (V2 only supports quote_char)
    escape_char = cfg.get("escape_char")
    if escape_char is not None:
        if text_enclosure is not None and escape_char != text_enclosure:
            warnings.append(
                f"Component '{v1['id']}': escape_char ('{escape_char}') differs from "
                f"text_enclosure ('{text_enclosure}'). V2 only supports quote_char -- "
                f"escape_char is dropped"
            )
        elif text_enclosure is None:
            warnings.append(
                f"Component '{v1['id']}': escape_char ('{escape_char}') is set but "
                f"text_enclosure is not. V2 has no standalone escape_char -- "
                f"escape_char is dropped"
            )

    # footer_rows
    footer = cfg.get("footer_rows")
    if footer is not None and footer > 0:
        v2_config["footer_rows"] = footer

    # limit — V1/Talend treats limit=0 as unlimited, V2 treats limit=0 as zero rows.
    # Only map positive values; omit 0 so V2 defaults to null (unlimited).
    limit = cfg.get("limit")
    if limit is not None and limit > 0:
        v2_config["limit"] = limit

    # remove_empty_rows -> skip_empty_rows
    remove_empty = cfg.get("remove_empty_rows")
    if remove_empty is not None:
        v2_config["skip_empty_rows"] = remove_empty

    # trim_all
    trim_all = cfg.get("trim_all")
    if trim_all is not None:
        v2_config["trim_all"] = trim_all

    # Schema: use output schema for sources
    schema_cols = (v1.get("schema") or {}).get("output", [])
    if schema_cols:
        v2_config["schema"] = _convert_schema(schema_cols, v1["id"])

    return ComponentResult(
        component={"id": v1["id"], "type": "file_input_delimited", "config": v2_config},
        warnings=warnings,
    )


def _map_file_output_delimited(v1: Dict) -> ComponentResult:
    cfg = v1.get("config", {})
    v2_config: Dict[str, Any] = {"path": cfg.get("filepath", "")}
    warnings: List[str] = []

    if "delimiter" in cfg:
        v2_config["delimiter"] = cfg["delimiter"]
    if "include_header" in cfg:
        v2_config["has_header"] = cfg["include_header"]
    if "append" in cfg:
        v2_config["append"] = cfg["append"]

    # row_separator -> line_terminator
    if "row_separator" in cfg:
        v2_config["line_terminator"] = cfg["row_separator"]

    # text_enclosure -> quote_char; csv_option -> quote_style
    text_enclosure = cfg.get("text_enclosure")
    if text_enclosure is not None:
        v2_config["quote_char"] = text_enclosure
    if cfg.get("csv_option"):
        v2_config["quote_style"] = "always"

    # delete_empty_file passthrough
    if "delete_empty_file" in cfg:
        v2_config["delete_empty_file"] = cfg["delete_empty_file"]

    # Unsupported key warnings
    unsupported_keys = {"encoding", "split", "split_every"}
    for key in sorted(unsupported_keys):
        if key in cfg:
            warnings.append(
                f"Component '{v1['id']}': '{key}' is not supported "
                f"in V2 FileOutputDelimited -- dropped"
            )

    return ComponentResult(
        component={"id": v1["id"], "type": "file_output_delimited", "config": v2_config},
        warnings=warnings,
    )


def _map_file_input_full_row(v1: Dict) -> ComponentResult:
    """Map tFileInputFullRow -> file_input_full_row."""
    config = v1.get("config", {})
    schema = v1.get("schema", {})
    input_schema = schema.get("input", [])

    v2_schema = _convert_schema(input_schema, v1["id"])

    v2_config: Dict[str, Any] = {
        "path": config.get("filepath", ""),
        "schema": v2_schema,
    }

    header = config.get("header", 0)
    if header:
        v2_config["header_rows"] = header

    footer = config.get("footer", 0)
    if footer is not None:
        v2_config["footer_rows"] = footer

    limit = config.get("limit", 0)
    if limit and limit > 0:
        v2_config["limit"] = limit

    encoding = config.get("encoding")
    if encoding:
        v2_config["encoding"] = encoding

    return ComponentResult(
        component={
            "id": v1["id"],
            "type": "file_input_full_row",
            "config": v2_config,
        },
        warnings=[],
        expressions_needing_review=[],
    )


def _map_file_input_excel(v1: Dict) -> ComponentResult:
    cfg = v1.get("config", {})
    warnings: List[str] = []
    v2_config: Dict[str, Any] = {"path": cfg.get("filepath", "")}

    # Sheet selection
    if cfg.get("all_sheets"):
        v2_config["all_sheets"] = True
    elif "sheetlist" in cfg:
        sheets = []
        for entry in cfg["sheetlist"]:
            sheet_name = entry.get("sheetname", "")
            if not sheet_name:
                warnings.append(f"Component '{v1['id']}': sheetlist entry missing 'sheetname' -- skipped")
                continue
            sheet_entry = {"name": sheet_name}
            if entry.get("use_regex"):
                sheet_entry["regex"] = True
            sheets.append(sheet_entry)
        if sheets:
            v2_config["sheets"] = sheets
    elif "sheet_name" in cfg:
        v2_config["sheet"] = cfg["sheet_name"]

    # Header
    if cfg.get("header_rows") is not None:
        v2_config["has_header"] = cfg["header_rows"] > 0

    # Footer — V1 footer=0 means no footer, only map positive
    footer = cfg.get("footer")
    if footer is None:
        footer = cfg.get("footer_rows")
    if footer is not None and footer > 0:
        v2_config["footer_rows"] = footer

    # Limit — V1 limit=0 means unlimited, only map positive
    limit = cfg.get("limit")
    if limit is not None and limit > 0:
        v2_config["limit"] = limit

    # Column range
    first_col = cfg.get("first_column")
    if first_col is not None:
        v2_config["first_column"] = first_col
    last_col = cfg.get("last_column")
    if last_col is not None:
        v2_config["last_column"] = last_col

    # Trim
    if cfg.get("trimall") or cfg.get("trim_all"):
        v2_config["trim_all"] = True

    # Skip rows
    skip_rows = cfg.get("skip_rows")
    if skip_rows is not None and skip_rows > 0:
        v2_config["skip_rows"] = skip_rows

    # Skip empty rows
    if cfg.get("stopread_on_emptyrow") or cfg.get("skip_empty_rows"):
        v2_config["skip_empty_rows"] = True

    # Die on error
    if "die_on_error" in cfg:
        v2_config["die_on_error"] = cfg["die_on_error"]

    # Warn on unsupported features
    unsupported = {
        "password": "password-protected Excel files",
        "generation_mode": "generation mode (event/user mode)",
        "advanced_separator": "advanced number separators",
        "read_real_value": "read real values for numbers",
        "no_validate": "cell validation skip",
        "convert_date": "date-to-string conversion",
    }
    for key, desc in unsupported.items():
        if cfg.get(key):
            warnings.append(
                f"Component '{v1['id']}': {desc} is not supported in V2 -- ignored"
            )

    # Schema
    schema_cols = (v1.get("schema") or {}).get("output", [])
    if schema_cols:
        v2_config["schema"] = _convert_schema(schema_cols, v1["id"])

    return ComponentResult(
        component={"id": v1["id"], "type": "file_input_excel", "config": v2_config},
        warnings=warnings,
    )


def _condition_to_expr(cond: Dict) -> str:
    """Convert a single V1 filter condition to a V2 expression fragment."""
    col = cond["column"]
    op = cond.get("operator", "==")
    val = cond.get("value")

    if op == "is_null":
        return f"{col} == null"
    if op == "is_not_null":
        return f"{col} != null"

    # Quote string values
    if isinstance(val, str):
        return f"{col} {op} '{val}'"
    return f"{col} {op} {val}"


def _map_filter_rows(v1: Dict) -> ComponentResult:
    cfg = v1.get("config", {})
    conditions = cfg.get("conditions", [])
    logical_op = cfg.get("logical_operator", "AND")

    # Advanced condition mode (pass-through with expression translation)
    if cfg.get("use_advanced") and cfg.get("advanced_condition"):
        expr_result = translate_expression(cfg["advanced_condition"])
        v2_config: Dict[str, Any] = {
            "condition": expr_result.expression,
            "reject_output": True,
        }
        warnings: List[str] = []
        exprs_review: List[Dict] = []
        if expr_result.needs_review:
            warnings.append(
                f"Component '{v1['id']}': advanced condition needs review -- "
                f"{expr_result.review_reason}"
            )
            exprs_review.append(
                {
                    "component": v1["id"],
                    "field": "condition",
                    "expression": cfg["advanced_condition"],
                }
            )
        return ComponentResult(
            component={"id": v1["id"], "type": "filter", "config": v2_config},
            warnings=warnings,
            expressions_needing_review=exprs_review,
        )

    # Standard condition-list mode
    parts = [_condition_to_expr(c) for c in conditions]
    condition = f" {logical_op} ".join(parts) if parts else "true"

    return ComponentResult(
        component={
            "id": v1["id"],
            "type": "filter",
            "config": {"condition": condition, "reject_output": True},
        }
    )


def _map_sort_row(v1: Dict) -> ComponentResult:
    cfg = v1.get("config", {})
    v2_columns = []
    for key in cfg.get("sort_keys", []):
        order = "asc" if key.get("ascending", True) else "desc"
        v2_columns.append(
            {
                "name": key["column"],
                "order": order,
            }
        )

    return ComponentResult(
        component={
            "id": v1["id"],
            "type": "sort_row",
            "config": {"columns": v2_columns},
        }
    )


def _map_aggregate_row(v1: Dict) -> ComponentResult:
    cfg = v1.get("config", {})
    v2_aggs = []
    for op in cfg.get("operations", []):
        agg_entry = {
            "name": op.get("output_column", op.get("input_column")),
            "column": op.get("input_column", "*"),
            "function": op.get("function", "sum"),
        }
        # Map Talend IGNORE_NULL to V2 ignore_nulls
        if "ignore_null" in op:
            agg_entry["ignore_nulls"] = bool(op["ignore_null"])
        v2_aggs.append(agg_entry)

    return ComponentResult(
        component={
            "id": v1["id"],
            "type": "aggregate",
            "config": {
                "group_by": cfg.get("group_by", []),
                "aggregations": v2_aggs,
            },
        }
    )


def _map_unique_row(v1: Dict) -> ComponentResult:
    cfg = v1.get("config", {})
    key_cols = cfg.get("key_columns", [])
    if not key_cols:
        # Backward compat: old v1 format used "distinct_key" list
        distinct_keys = cfg.get("distinct_key", [])
        key_cols = [{"column": col, "case_sensitive": True} for col in distinct_keys]
    return ComponentResult(
        component={
            "id": v1["id"],
            "type": "uniq_row",
            "config": {
                "key_columns": key_cols,
                "keep": cfg.get("keep", cfg.get("duplicate_action", "first")),
            },
        }
    )


def _map_filter_columns(v1: Dict) -> ComponentResult:
    cfg = v1.get("config", {})
    return ComponentResult(
        component={
            "id": v1["id"],
            "type": "filter_columns",
            "config": {"columns": cfg.get("columns", [])},
        }
    )


def _map_unite(v1: Dict) -> ComponentResult:
    return ComponentResult(
        component={"id": v1["id"], "type": "unite", "config": {}}
    )


def _map_python_row(v1: Dict) -> ComponentResult:
    cfg = v1.get("config", {})
    return ComponentResult(
        component={
            "id": v1["id"],
            "type": "python_row",
            "config": {"code": cfg.get("python_code", "")},
        }
    )


def _map_python_dataframe(v1: Dict) -> ComponentResult:
    cfg = v1.get("config", {})
    return ComponentResult(
        component={
            "id": v1["id"],
            "type": "python_dataframe",
            "config": {"code": cfg.get("python_code", "")},
        }
    )


def _map_python_code(v1: Dict) -> ComponentResult:
    cfg = v1.get("config", {})
    return ComponentResult(
        component={
            "id": v1["id"],
            "type": "python_code",
            "config": {"code": cfg.get("python_code", "")},
        }
    )


# ---------------------------------------------------------------------------
# tMap mapper (complex — handles lookups, variables, outputs, filters)
# ---------------------------------------------------------------------------


def _translate_map_expression(
    expr_str: str, component_id: str, column_name: str
) -> tuple:
    """Translate a tMap column expression.

    Returns (translated, col_dict_extra, warnings, review_items).
    """
    result = translate_expression(expr_str)
    translated = result.expression

    extra: Dict[str, Any] = {}
    warnings: List[str] = []
    review_items: List[Dict] = []

    if result.needs_review:
        extra["_review"] = True
        warnings.append(
            f"Component '{component_id}', column '{column_name}': "
            f"expression needs review -- {result.review_reason}"
        )
        review_items.append(
            {
                "component": component_id,
                "column": column_name,
                "expression": expr_str,
            }
        )

    return translated, extra, warnings, review_items


def _map_tmap(v1: Dict) -> ComponentResult:
    cfg = v1.get("config", {})
    comp_id = v1["id"]
    all_warnings: List[str] = []
    all_review: List[Dict] = []
    v2_config: Dict[str, Any] = {}

    # --- Lookups ---
    inputs_cfg = cfg.get("inputs", {})
    v1_lookups = inputs_cfg.get("lookups", [])
    if v1_lookups:
        v2_lookups = []
        for lk in v1_lookups:
            v2_lk: Dict[str, Any] = {"name": lk["name"]}

            # Join keys
            v2_keys = []
            for jk in lk.get("join_keys", []):
                v2_keys.append(
                    {
                        "main": jk.get("main_column", ""),
                        "lookup": jk.get("lookup_column", ""),
                    }
                )
            if v2_keys:
                v2_lk["keys"] = v2_keys

            # Join type
            jt = lk.get("join_type", "LEFT").lower()
            v2_lk["join_type"] = jt

            # Match mode
            mm = lk.get("match_mode", "UNIQUE").lower()
            match_mode_map = {
                "unique_match": "unique", "unique": "unique",
                "first_match": "first", "first": "first",
                "last_match": "last", "last": "last",
                "all_matches": "all", "all": "all",
            }
            v2_lk["match_mode"] = match_mode_map.get(mm, "unique")

            v2_lookups.append(v2_lk)
        v2_config["lookups"] = v2_lookups

    # --- Variables ---
    v1_vars = cfg.get("variables", [])
    if v1_vars:
        v2_vars = []
        for v in v1_vars:
            expr_str = v.get("expression", "")
            translated, extra, warns, reviews = _translate_map_expression(
                expr_str, comp_id, f"var.{v['name']}"
            )
            all_warnings.extend(warns)
            all_review.extend(reviews)
            var_def: Dict[str, Any] = {"name": v["name"], "expression": translated}
            var_def.update(extra)
            v2_vars.append(var_def)
        v2_config["variables"] = v2_vars

    # --- Outputs ---
    v1_outputs = cfg.get("outputs", [])
    v2_outputs = []
    for out in v1_outputs:
        v2_out: Dict[str, Any] = {"name": out.get("name", "main")}

        # Output filter
        if out.get("activate_filter") and out.get("filter"):
            filter_expr = out["filter"]
            filter_result = translate_expression(filter_expr)
            v2_out["filter"] = filter_result.expression
            if filter_result.needs_review:
                all_warnings.append(
                    f"Component '{comp_id}', output '{out['name']}' filter: "
                    f"needs review -- {filter_result.review_reason}"
                )
                all_review.append(
                    {
                        "component": comp_id,
                        "column": f"_filter_{out['name']}",
                        "expression": filter_expr,
                    }
                )

        # Columns
        v2_cols = []
        for col in out.get("columns", []):
            expr_str = col.get("expression", col["name"])
            translated, extra, warns, reviews = _translate_map_expression(
                expr_str, comp_id, col["name"]
            )
            all_warnings.extend(warns)
            all_review.extend(reviews)
            col_def: Dict[str, Any] = {"name": col["name"], "expression": translated}
            col_def.update(extra)
            v2_cols.append(col_def)

        v2_out["columns"] = v2_cols
        v2_outputs.append(v2_out)

    v2_config["outputs"] = v2_outputs

    # die_on_error
    die_on_error = cfg.get("die_on_error", True)
    if not die_on_error:
        v2_config["die_on_error"] = False

    return ComponentResult(
        component={"id": comp_id, "type": "map", "config": v2_config},
        warnings=all_warnings,
        expressions_needing_review=all_review,
    )


# ---------------------------------------------------------------------------
# Unsupported component handler
# ---------------------------------------------------------------------------


def _map_unsupported(v1: Dict, suggestion: Optional[str] = None) -> ComponentResult:
    """Mark a component as unsupported."""
    v1_type = v1.get("type", "unknown")
    comp_id = v1["id"]

    msg = f"Component '{comp_id}' ({v1_type}) is unsupported in V2"
    if suggestion:
        msg += f" -- rewrite as {suggestion}"

    # Preserve original config so the human can see what was there
    v2_config = dict(v1.get("config", {}))
    v2_config["_unsupported"] = True
    v2_config["_original_type"] = v1_type

    return ComponentResult(
        component={"id": comp_id, "type": v1_type.lower(), "config": v2_config},
        warnings=[msg],
    )


def _map_context_load(v1: Dict) -> ComponentResult:
    """Map tContextLoad to context_load."""
    cfg = v1.get("config", {})
    v2_config: Dict[str, Any] = {}

    # Path
    v2_config["path"] = cfg.get("filepath", "")

    # Format and delimiter
    v1_format = cfg.get("format", "properties").lower()
    if v1_format == "csv":
        v2_config["format"] = "delimited"
        v2_config["delimiter"] = cfg.get("csv_separator", ",")
    else:
        v2_config["format"] = "delimited"
        v2_config["delimiter"] = cfg.get("delimiter", "=")

    # Print operations
    if cfg.get("print_operations"):
        v2_config["print_operations"] = True

    # Die on error
    if "error_if_not_exists" in cfg:
        v2_config["die_on_error"] = cfg["error_if_not_exists"]

    return ComponentResult(
        component={"id": v1["id"], "type": "context_load", "config": v2_config},
    )


# ---------------------------------------------------------------------------
# Dispatch tables
# ---------------------------------------------------------------------------

# V1 type -> mapper function
_MAPPERS: Dict[str, Callable] = {
    "tFileInputDelimited": _map_file_input_delimited,
    "FileInputDelimited": _map_file_input_delimited,
    "tFileOutputDelimited": _map_file_output_delimited,
    "FileOutputDelimited": _map_file_output_delimited,
    "tFileInputFullRow": _map_file_input_full_row,
    "FileInputFullRow": _map_file_input_full_row,
    "tFileInputExcel": _map_file_input_excel,
    "FileInputExcel": _map_file_input_excel,
    "tFilterRows": _map_filter_rows,
    "FilterRows": _map_filter_rows,
    "tFilterColumns": _map_filter_columns,
    "FilterColumns": _map_filter_columns,
    "tSortRow": _map_sort_row,
    "SortRow": _map_sort_row,
    "tAggregateRow": _map_aggregate_row,
    "AggregateRow": _map_aggregate_row,
    "tUniqueRow": _map_unique_row,
    "UniqueRow": _map_unique_row,
    "tUniqRow": _map_unique_row,
    "UniqRow": _map_unique_row,
    "tUnqRow": _map_unique_row,
    "tUnite": _map_unite,
    "Unite": _map_unite,
    "tMap": _map_tmap,
    "Map": _map_tmap,
    "tPythonRow": _map_python_row,
    "PythonRowComponent": _map_python_row,
    "tPythonDataFrame": _map_python_dataframe,
    "PythonDataFrameComponent": _map_python_dataframe,
    "tPython": _map_python_code,
    "PythonComponent": _map_python_code,
    "tContextLoad": _map_context_load,
    "ContextLoad": _map_context_load,
}

# Unsupported types with optional V2 suggestions
_UNSUPPORTED: Dict[str, Optional[str]] = {
    "tJavaRow": "python_row",
    "JavaRowComponent": "python_row",
    "tJava": "python_code",
    "JavaComponent": "python_code",
    "tDie": None,
    "tWarn": None,
    "tOracleInput": None,
    "tFileInputPositional": None,
    "Die": None,
    "Warn": None,
    "OracleInput": None,
    "FileInputPositional": None,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def map_component(v1: Dict) -> ComponentResult:
    """Map a V1 component definition to V2 format.

    Parameters
    ----------
    v1 : dict
        A V1 component dict with at least ``id``, ``type``, and ``config`` keys.

    Returns
    -------
    ComponentResult
        The translated V2 component, any warnings, and expressions needing
        manual review.
    """
    v1_type = v1.get("type", "")

    # Check unsupported first
    if v1_type in _UNSUPPORTED:
        return _map_unsupported(v1, _UNSUPPORTED[v1_type])

    # Check supported mappers
    mapper = _MAPPERS.get(v1_type)
    if mapper:
        return mapper(v1)

    # Unknown type -- mark unsupported
    return _map_unsupported(v1)
