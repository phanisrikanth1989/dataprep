# demo/budget_ui/daemon/presenter.py
"""Generic, DATA-FREE transform: parsed artifact -> event payloads.

No I/O. Reads ONLY allowlisted keys; never reads sample_input/expected_output;
never dumps a whole artifact. Unknown shapes emit nothing (fail-closed).
ASCII-only.
"""
from __future__ import annotations

import re

# Exact registered type -> kind. Order-independent (exact match, not substring).
_KIND = {
    "FileInputDelimited": "source", "tFileInputDelimited": "source",
    "FileOutputDelimited": "output", "tFileOutputDelimited": "output",
    "FilterRows": "filter", "FilterRow": "filter", "tFilterRow": "filter", "tFilterRows": "filter",
    "FilterColumns": "filter",
    "Join": "join", "tJoin": "join",
    "Map": "map", "tMap": "map", "PyMap": "map", "XMLMap": "map",
    "SchemaComplianceCheck": "validate", "tSchemaComplianceCheck": "validate",
    "ConvertType": "validate", "tConvertType": "validate",
    "tPythonDataFrame": "derive", "PythonDataFrameComponent": "derive",
    "SortRow": "sort", "tSortRow": "sort",
    "AggregateRow": "aggregate", "tAggregateRow": "aggregate",
}


def _base(path):
    """Basename without a known data extension. Never an absolute path."""
    name = (path or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return re.sub(r"\.(csv|xlsx|xls|json|xml|txt|dat)$", "", name, flags=re.IGNORECASE)


def _derive_col(cfg):
    m = re.search(r"df\[[\"'](\w+)[\"']\]\s*=", cfg.get("python_code", "") or "")
    if m:
        return m.group(1)
    oc = cfg.get("output_columns") or []
    return oc[-1] if oc else "value"


def _humanize_type(t):
    """tOracleInput -> 'Oracle Input'. Never leak the raw component id."""
    t = re.sub(r"^t(?=[A-Z])", "", t or "")
    words = re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z]*|[a-z]+|\d+", t)
    return " ".join(words) if words else (t or "step")


def _fallback_kind(t):
    low = (t or "").lower()
    if "output" in low or low.endswith("write"):
        return "output"
    if "input" in low or "generator" in low or "rowgen" in low:
        return "source"
    return "op"


def classify(component, lookup_name=None):
    """type + config -> {kind, label, sub}. Humanized fallback for unknown types."""
    t = component.get("type", "")
    cfg = component.get("config") or {}
    kind = _KIND.get(t)
    if kind == "source":
        return {"kind": "source", "label": "Read " + _base(cfg.get("filepath")), "sub": "source file"}
    if kind == "output":
        return {"kind": "output", "label": "Write " + _base(cfg.get("filepath")), "sub": "output file"}
    if kind == "filter":
        conds = cfg.get("conditions") or []
        if conds:
            c = conds[0]
            return {"kind": "filter", "label": "Keep %s = %s" % (c.get("column", ""), c.get("value", "")),
                    "sub": "filter rows"}
        return {"kind": "filter", "label": "Select columns", "sub": "projection"}
    if kind in ("join", "map"):
        key = (cfg.get("join_key") or [{}])[0]
        col = key.get("lookup_column") or key.get("input_column") or "key"
        mode = "left join" if cfg.get("use_inner_join") is False else "join"
        return {"kind": kind, "label": "Match " + (lookup_name or "lookup"), "sub": "%s on %s" % (mode, col)}
    if kind == "validate":
        col = next((s for s in cfg.get("schema", []) if s.get("date_pattern")), None) or (cfg.get("schema") or [{}])[0]
        return {"kind": "validate", "label": "Validate " + col.get("name", "schema"),
                "sub": col.get("date_pattern") or "schema check"}
    if kind == "derive":
        return {"kind": "derive", "label": "Compute " + _derive_col(cfg), "sub": "generated code"}
    if kind == "sort":
        c = (cfg.get("criteria") or [{}])[0]
        return {"kind": "sort", "label": "Sort by " + c.get("column", ""),
                "sub": "high to low" if c.get("order") == "desc" else "low to high"}
    if kind == "aggregate":
        return {"kind": "aggregate", "label": "Group and summarize", "sub": "aggregate"}
    # Unknown type: humanized, kind guessed from the name. Never the raw id.
    human = _humanize_type(t)
    return {"kind": _fallback_kind(t), "label": human, "sub": human.lower()}
