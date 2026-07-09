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


def assert_data_free(event, forbidden):
    """Raise if any forbidden raw value appears in the event PAYLOAD (test guard).
    Envelope metadata (job/seq/t) is excluded: seq is a climbing int and t is an
    epoch float whose digits can coincidentally contain a short numeric cell like '10'."""
    payload = {k: v for k, v in event.items() if k not in ("job", "seq", "t")}
    blob = repr(payload)
    for v in forbidden:
        assert v not in blob, "data-free violation: %r leaked into event %s" % (v, event.get("type"))


def ev_sources(extract_doc):
    """From sources_schema ONLY (names + column counts). Never touches sample_input/expected_output."""
    schema = extract_doc.get("sources_schema") or {}
    nodes = []
    for name, cols in schema.items():
        n = len(cols) if isinstance(cols, list) else 0
        nodes.append({"id": name, "label": "Read " + name, "kind": "source",
                      "sub": "%d columns" % n})
    return {"type": "sources", "nodes": nodes}


def ev_rules(requirement_spec):
    """Rule id + kind + a short business label. No rule 'description' free text is forwarded."""
    _LABEL = {"join": "add looked-up columns", "filter": "keep matching rows",
              "aggregate": "summarize", "sort": "sort the output",
              "schema_validate": "validate the schema", "derive": "compute a value"}
    items = [{"id": r.get("id"), "kind": r.get("kind"), "label": _LABEL.get(r.get("kind"), "transform")}
             for r in (requirement_spec.get("rules") or [])]
    return {"type": "rules", "count": len(items), "items": items}


_SKELETON = {"source": "Read a source", "filter": "Filter rows", "join": "Match a lookup",
             "map": "Enrich (mapper)", "validate": "Validate", "derive": "Compute a value",
             "sort": "Sort", "aggregate": "Group and summarize", "output": "Write output"}


def skeleton(component):
    """Config-FREE node view for flow_plan.json (which carries only id/type/purpose).
    The business label arrives later from job.json config via ev_node_config."""
    t = component.get("type", "")
    kind = _KIND.get(t) or _fallback_kind(t)
    return {"kind": kind, "label": _SKELETON.get(kind) or _humanize_type(t)}


def ev_nodes(flow_plan):
    """flow_plan components -> node skeletons (kind + config-free label). Purpose text NOT forwarded."""
    nodes = []
    for c in flow_plan.get("components") or []:
        nodes.append({"id": c.get("id"), "ntype": c.get("type"), **skeleton(c)})
    return {"type": "nodes", "nodes": nodes}
