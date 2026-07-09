# Demo UI Phase 1 -- Data-Free Presenter + Daemon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the laptop-side pipeline that watches the agents' artifact bus and emits a data-free, business-readable event stream describing the pipeline being built.

**Architecture:** A pure-function module `presenter.py` turns each parsed artifact into data-free event payloads (the generic transform); a thin `daemon.py` polls the work dir by mtime, dispatches new/changed artifacts to `presenter.py`, wraps payloads in an envelope, and posts them via an injectable sender. No network or file I/O in `presenter.py` (fully unit-testable against the real run's artifacts).

**Tech Stack:** Python 3.12+ standard library only for this phase (`json`, `pathlib`, `time`, `re`, `urllib`). No third-party deps. Tests via `pytest`.

**Roadmap:** This is Phase 1 of 3. Phase 2 = FastAPI relay server + fetcher. Phase 3 = React frontend port. Each is a separate plan; this one stands alone and is fully testable without the server or frontend.

## Global Constraints

- **Python 3.12+**; standard library only in this phase (no third-party imports in `presenter.py`/`daemon.py`).
- **ASCII-only** in all code, comments, and strings (RHEL-clean). No emojis/unicode.
- **DATA-FREE (hard):** no `sample_input` or `expected_output` cell value may ever appear in an emitted event. `presenter.py` reads ONLY allowlisted keys; it never reads `sample_input`/`expected_output` and never `json.dumps` a whole artifact into an event. Unknown/unhandled shapes emit nothing (fail-closed).
- **Event envelope:** every event is `{"job": <str>, "seq": <int>, "t": <float>, "type": <str>, ...}`. `presenter.py` returns the payload (`{"type": ..., ...}`); `daemon.py` adds `job`/`seq`/`t`.
- **Event types:** `stage`, `sources`, `rules`, `nodes`, `node_config`, `edges`, `callout`, `gate`, `result`.
- **Laptop-outbound only:** the daemon posts out; it never listens. The sender is injectable so tests capture posts without a network.
- **Stage transitions are driven by ARTIFACT APPEARANCE (deterministic), not by parsing LLM-worded `audit.jsonl` event strings.**

---

## File Structure

- Create `demo/budget_ui/daemon/__init__.py` -- empty package marker.
- Create `demo/budget_ui/daemon/presenter.py` -- the generic artifact -> data-free payload transform (pure functions).
- Create `demo/budget_ui/daemon/daemon.py` -- the watch loop (poll mtimes, dispatch, wrap, post).
- Create `tests/demo_budget_ui/__init__.py` -- empty.
- Create `tests/demo_budget_ui/fixtures/trade_position_demo/` -- copied real artifacts (test fixtures).
- Create `tests/demo_budget_ui/test_presenter.py` -- unit tests for `presenter.py`.
- Create `tests/demo_budget_ui/test_daemon.py` -- unit tests for `daemon.py`.

Responsibilities: `presenter.py` = "what does each artifact mean, value-free" (no I/O). `daemon.py` = "watch, dispatch, wrap, send" (I/O + ordering). Split so the hard/tested logic (presenter) is pure.

---

### Task 1: Scaffold + capture the real run's artifacts as fixtures

**Files:**
- Create: `demo/budget_ui/daemon/__init__.py`, `tests/demo_budget_ui/__init__.py`
- Create: `tests/demo_budget_ui/fixtures/trade_position_demo/` (copied artifacts + one crafted clean report)

- [ ] **Step 1: Create package markers and copy the live artifacts**

Run:
```bash
mkdir -p demo/budget_ui/daemon tests/demo_budget_ui/fixtures/trade_position_demo/golden
touch demo/budget_ui/daemon/__init__.py tests/demo_budget_ui/__init__.py
cp agents/work/trade_position_demo/extract_doc.json \
   agents/work/trade_position_demo/requirement_spec.json \
   agents/work/trade_position_demo/flow_plan.json \
   agents/work/trade_position_demo/job_draft.json \
   agents/work/trade_position_demo/job.json \
   agents/work/trade_position_demo/test_report.json \
   agents/work/trade_position_demo/audit.jsonl \
   tests/demo_budget_ui/fixtures/trade_position_demo/
cp agents/work/trade_position_demo/golden/manifest.json \
   agents/work/trade_position_demo/golden/trade_positions_expected.csv \
   tests/demo_budget_ui/fixtures/trade_position_demo/golden/
```
Expected: files exist under `tests/demo_budget_ui/fixtures/trade_position_demo/`.

- [ ] **Step 2: Craft a clean (passed) test_report fixture for happy-path tests**

The captured `test_report.json` has `passed:false` (the real run failed on float formatting). Create a sibling clean report so happy-path `result` tests have a green fixture. Create `tests/demo_budget_ui/fixtures/trade_position_demo/test_report_passed.json`:
```json
{
  "passed": true,
  "engine": {"status": "success", "dropped": [],
    "global_map": {"trade_positions": {"NB_LINE": 4, "NB_LINE_OK": 4, "NB_LINE_REJECT": 0}}},
  "outputs": {"trade_positions": {"equal": true, "missing": 0, "unexpected": 0, "value_mismatch": 0,
    "unexpected_columns": [], "missing_columns": []}},
  "reasons": [], "graded": 1, "total": 1
}
```

- [ ] **Step 3: Commit**

```bash
git add demo/budget_ui/daemon/__init__.py tests/demo_budget_ui/__init__.py tests/demo_budget_ui/fixtures/
git commit -m "test(demo-ui): scaffold daemon package + capture real-run artifacts as fixtures"
```

---

### Task 2: `classify()` -- generic type -> {kind, label, sub}

**Files:**
- Create: `demo/budget_ui/daemon/presenter.py`
- Test: `tests/demo_budget_ui/test_presenter.py`

**Interfaces:**
- Produces: `classify(component: dict, lookup_name: str | None = None) -> dict` returning `{"kind": str, "label": str, "sub": str}`. `component` is a `job.json`/`flow_plan.json` component dict (`id`, `type`, optional `config`). `kind` is one of `source|filter|join|map|validate|derive|sort|aggregate|output|op`. Unknown types get a humanized fallback, never a raw id.

- [ ] **Step 1: Write the failing tests**

```python
# tests/demo_budget_ui/test_presenter.py
from demo.budget_ui.daemon import presenter as P

def test_classify_curated_types():
    assert P.classify({"id": "in_trades", "type": "FileInputDelimited",
                       "config": {"filepath": "trades.csv"}})["label"] == "Read trades"
    assert P.classify({"id": "f", "type": "FilterRows",
                       "config": {"conditions": [{"column": "status", "operator": "==", "value": "SETTLED"}]}}) \
        == {"kind": "filter", "label": "Keep status = SETTLED", "sub": "filter rows"}
    j = P.classify({"id": "j", "type": "tJoin",
                    "config": {"use_inner_join": False, "join_key": [{"lookup_column": "account_id"}]}},
                   lookup_name="accounts")
    assert j["kind"] == "join" and j["label"] == "Match accounts" and "left join" in j["sub"]
    assert P.classify({"id": "d", "type": "tPythonDataFrame",
                       "config": {"python_code": "df['market_value'] = df['quantity']"}})["label"] == "Compute market_value"
    assert P.classify({"id": "s", "type": "SortRow",
                       "config": {"criteria": [{"column": "market_value", "order": "desc"}]}})["label"] == "Sort by market_value"
    assert P.classify({"id": "o", "type": "FileOutputDelimited",
                       "config": {"filepath": "trade_positions.csv"}})["kind"] == "output"

def test_classify_unknown_type_humanizes_not_raw_id():
    v = P.classify({"id": "src_1", "type": "tOracleInput", "config": {}})
    assert v["kind"] == "source"          # name ends in Input -> source
    assert "Oracle" in v["label"]          # humanized, never the raw id "src_1"
    assert v["label"] != "src_1"

def test_classify_map_family_not_misread_as_simple_join():
    # PyMap/tMap must not fall through to the tJoin branch
    assert P.classify({"id": "m", "type": "PyMap", "config": {}})["kind"] == "map"
    assert P.classify({"id": "m", "type": "tMap", "config": {}})["kind"] == "map"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/demo_budget_ui/test_presenter.py -v`
Expected: FAIL (`ModuleNotFoundError` / `AttributeError: classify`).

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/demo_budget_ui/test_presenter.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add demo/budget_ui/daemon/presenter.py tests/demo_budget_ui/test_presenter.py
git commit -m "feat(demo-ui): generic type->label classify() with humanized fallback"
```

---

### Task 3: Read-side extractors (`ev_sources`, `ev_rules`, `ev_nodes`) + the data-free guard

**Files:**
- Modify: `demo/budget_ui/daemon/presenter.py`
- Test: `tests/demo_budget_ui/test_presenter.py`

**Interfaces:**
- Produces: `ev_sources(extract_doc: dict) -> dict` type `sources`; `ev_rules(requirement_spec: dict) -> dict` type `rules`; `ev_nodes(flow_plan: dict) -> dict` type `nodes`; `assert_data_free(event: dict, forbidden: list[str]) -> None` (raises `AssertionError` if any forbidden value string appears anywhere in the event).

- [ ] **Step 1: Write the failing tests (grounded in the real fixtures)**

```python
# add to tests/demo_budget_ui/test_presenter.py
import json, pathlib
FIX = pathlib.Path(__file__).parent / "fixtures" / "trade_position_demo"
def _load(name): return json.loads((FIX / name).read_text())

def _forbidden_values():
    """Every raw sample/expected cell value in the real extract_doc -- must never leak."""
    doc = _load("extract_doc.json")
    vals = set()
    for rows in list(doc.get("sample_input", {}).values()) + list(doc.get("expected_output", {}).values()):
        for row in rows:
            for v in (row.values() if isinstance(row, dict) else row):
                if isinstance(v, str) and v.strip():
                    vals.add(v)
    return [v for v in vals if v not in ("SETTLED",)]  # SETTLED is also a rule literal (allowed)

def test_ev_sources_lists_sources_and_is_data_free():
    ev = P.ev_sources(_load("extract_doc.json"))
    assert ev["type"] == "sources"
    ids = [n["id"] for n in ev["nodes"]]
    assert set(ids) == {"trades", "accounts", "prices"}
    assert all(n["kind"] == "source" for n in ev["nodes"])
    P.assert_data_free(ev, _forbidden_values())        # e.g. "Gamma Funds", "30200.00", "A999" never appear

def test_ev_rules_counts_and_labels():
    ev = P.ev_rules(_load("requirement_spec.json"))
    assert ev["type"] == "rules" and ev["count"] == 6
    kinds = {i["kind"] for i in ev["items"]}
    assert {"join", "filter", "sort", "derive", "schema_validate"} <= kinds
    P.assert_data_free(ev, _forbidden_values())

def test_ev_nodes_uses_classify_and_is_data_free():
    ev = P.ev_nodes(_load("flow_plan.json"))
    assert ev["type"] == "nodes"
    labels = {n["label"] for n in ev["nodes"]}
    assert "Keep status = SETTLED" in labels and "Compute market_value" in labels
    P.assert_data_free(ev, _forbidden_values())
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/demo_budget_ui/test_presenter.py -k "ev_sources or ev_rules or ev_nodes" -v`
Expected: FAIL (`AttributeError`).

- [ ] **Step 3: Write minimal implementation (append to presenter.py)**

```python
def assert_data_free(event, forbidden):
    """Raise if any forbidden raw value appears anywhere in the event (test guard)."""
    blob = repr(event)
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


def ev_nodes(flow_plan):
    """flow_plan components -> node skeletons (kind + label). Purpose free-text is NOT forwarded."""
    nodes = []
    for c in flow_plan.get("components") or []:
        v = classify(c)
        nodes.append({"id": c.get("id"), "ntype": c.get("type"), **v})
    return {"type": "nodes", "nodes": nodes}
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/demo_budget_ui/test_presenter.py -v`
Expected: PASS (all tests, including the data-free guards over the real values).

- [ ] **Step 5: Commit**

```bash
git add demo/budget_ui/daemon/presenter.py tests/demo_budget_ui/test_presenter.py
git commit -m "feat(demo-ui): data-free sources/rules/nodes extractors + leak guard"
```

---

### Task 4: `ev_node_config`, `ev_edges` (with lookup-name resolution)

**Files:**
- Modify: `demo/budget_ui/daemon/presenter.py`
- Test: `tests/demo_budget_ui/test_presenter.py`

**Interfaces:**
- Produces: `ev_node_config(job: dict) -> dict` type `node_config` (`nodes: [{id, sub}]`); `ev_edges(job: dict) -> dict` type `edges` (`edges: [{from, to, reject}]`). Both resolve each join's lookup name (its FileInput predecessor) from `flows` so the label reads "Match accounts".

- [ ] **Step 1: Write the failing tests**

```python
def test_ev_edges_from_flows_and_marks_reject():
    ev = P.ev_edges(_load("job.json"))
    assert ev["type"] == "edges"
    pairs = {(e["from"], e["to"]) for e in ev["edges"]}
    assert ("filter_settled", "join_accounts") in pairs
    assert ("sort_market_value", "trade_positions") in pairs
    assert all(e.get("reject") is False for e in ev["edges"])  # this job has no reject route
    P.assert_data_free(ev, _forbidden_values())

def test_ev_node_config_fills_business_subs():
    ev = P.ev_node_config(_load("job.json"))
    subs = {n["id"]: n["sub"] for n in ev["nodes"]}
    assert subs["filter_settled"] == "filter rows"
    assert "left join on account_id" in subs["join_accounts"]  # lookup name resolved from flows
    P.assert_data_free(ev, _forbidden_values())
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/demo_budget_ui/test_presenter.py -k "ev_edges or ev_node_config" -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation (append)**

```python
def _lookup_names(job):
    """join id -> the basename of its FileInput lookup predecessor (from flows)."""
    comps = {c.get("id"): c for c in job.get("components") or []}
    out = {}
    for f in job.get("flows") or []:
        src, dst = comps.get(f.get("from")), comps.get(f.get("to"))
        if src and dst and _KIND.get(dst.get("type")) in ("join", "map") \
           and _KIND.get(src.get("type")) == "source":
            out[dst.get("id")] = _base((src.get("config") or {}).get("filepath"))
    return out


def ev_edges(job):
    edges = [{"from": f.get("from"), "to": f.get("to"), "reject": f.get("type") == "reject"}
             for f in job.get("flows") or []]
    return {"type": "edges", "edges": edges}


def ev_node_config(job):
    looks = _lookup_names(job)
    nodes = [{"id": c.get("id"), "sub": classify(c, looks.get(c.get("id")))["sub"]}
             for c in job.get("components") or []]
    return {"type": "node_config", "nodes": nodes}
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/demo_budget_ui/test_presenter.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add demo/budget_ui/daemon/presenter.py tests/demo_budget_ui/test_presenter.py
git commit -m "feat(demo-ui): edges + node_config extractors with lookup-name resolution"
```

---

### Task 5: `ev_callouts` (canned, per-kind) + `ev_gate`

**Files:**
- Modify: `demo/budget_ui/daemon/presenter.py`
- Test: `tests/demo_budget_ui/test_presenter.py`

**Interfaces:**
- Produces: `ev_callouts(job: dict) -> list[dict]` each type `callout` (`{node, text, kind:"rationale"}`) -- CANNED per component kind, never raw LLM purpose text. `ev_gate(job: dict) -> dict | None` type `gate` (`{kind:"code_signoff", node, code, status:"awaiting"}`) when a code-bearing cell exists, else `None`.

- [ ] **Step 1: Write the failing tests**

```python
def test_ev_callouts_are_canned_and_data_free():
    outs = P.ev_callouts(_load("job.json"))
    by_node = {c["node"]: c["text"] for c in outs}
    assert "filter_settled" in by_node and "derive_market_value" in by_node
    assert "sign off" in by_node["derive_market_value"].lower()
    for c in outs:
        P.assert_data_free(c, _forbidden_values())

def test_ev_gate_present_for_code_cell():
    g = P.ev_gate(_load("job.json"))
    assert g["type"] == "gate" and g["node"] == "derive_market_value"
    assert g["status"] == "awaiting" and "market_value" in g["code"]

def test_ev_gate_none_without_code():
    job = {"components": [{"id": "x", "type": "FilterRows", "config": {}}], "flows": []}
    assert P.ev_gate(job) is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/demo_budget_ui/test_presenter.py -k "callouts or gate" -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation (append)**

```python
_CODE_TYPES = {"tPythonDataFrame", "PythonDataFrameComponent", "PyMap",
               "tPythonRow", "tJava", "tJavaRow", "tJavaFlex", "SwiftTransformer"}
_CALLOUT = {
    "filter": "Filter goes first -- it shrinks the lookups.",
    "join": "Matched on a unique key, so no rows fan out.",
    "map": "Enriched via a mapper (multiple lookups in one step).",
    "derive": "This step writes code -- a human signs off before it runs.",
    "sort": "Sorted last so the final order is fixed.",
}


def ev_callouts(job):
    """One canned rationale per node whose kind has one. No LLM prose forwarded."""
    outs = []
    for c in job.get("components") or []:
        text = _CALLOUT.get(_KIND.get(c.get("type")))
        if text:
            outs.append({"type": "callout", "node": c.get("id"), "text": text, "kind": "rationale"})
    return outs


def _code_of(cfg):
    return cfg.get("python_code") or cfg.get("code") or cfg.get("python_expression") or ""


def ev_gate(job):
    for c in job.get("components") or []:
        if c.get("type") in _CODE_TYPES:
            return {"type": "gate", "kind": "code_signoff", "node": c.get("id"),
                    "code": _code_of(c.get("config") or {}), "status": "awaiting"}
    return None
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/demo_budget_ui/test_presenter.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add demo/budget_ui/daemon/presenter.py tests/demo_budget_ui/test_presenter.py
git commit -m "feat(demo-ui): canned per-kind callouts + code-gate event"
```

---

### Task 6: `ev_result` (with fail-closed sample) + `ev_stage`

**Files:**
- Modify: `demo/budget_ui/daemon/presenter.py`
- Test: `tests/demo_budget_ui/test_presenter.py`

**Interfaces:**
- Produces: `ev_result(test_report: dict, tier: str, sample: list | None = None) -> dict` type `result` (`{passed, tier, rows, graded, sample?}`). `sample` is included ONLY if the caller passes it (the daemon passes it fail-closed; see Task 8). `ev_stage(stage: str, status: str) -> dict` type `stage`.

- [ ] **Step 1: Write the failing tests**

```python
def test_ev_result_counts_no_sample_by_default():
    ev = P.ev_result(_load("test_report_passed.json"), tier="verified")
    assert ev["type"] == "result" and ev["passed"] is True
    assert ev["rows"] == 4 and ev["graded"] == "1/1" and ev["tier"] == "verified"
    assert "sample" not in ev                       # fail-closed: no sample unless explicitly given

def test_ev_result_failed_report_is_not_green():
    ev = P.ev_result(_load("test_report.json"), tier="verified")  # the real FAILED report
    assert ev["passed"] is False

def test_ev_result_includes_sample_only_when_provided():
    ev = P.ev_result(_load("test_report_passed.json"), tier="verified",
                     sample=[{"trade_id": "T004", "market_value": "30200.0"}])
    assert ev["sample"][0]["trade_id"] == "T004"

def test_ev_stage():
    assert P.ev_stage("configuring", "active") == {"type": "stage", "stage": "configuring", "status": "active"}
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/demo_budget_ui/test_presenter.py -k "ev_result or ev_stage" -v`
Expected: FAIL.

- [ ] **Step 3: Write minimal implementation (append)**

```python
def ev_result(test_report, tier, sample=None):
    total_rows = 0
    gm = ((test_report.get("engine") or {}).get("global_map") or {})
    for stats in gm.values():
        total_rows = max(total_rows, stats.get("NB_LINE_OK", stats.get("NB_LINE", 0)))
    ev = {"type": "result", "passed": bool(test_report.get("passed")), "tier": tier,
          "rows": total_rows,
          "graded": "%s/%s" % (test_report.get("graded", 0), test_report.get("total", 0))}
    if sample is not None:
        ev["sample"] = sample
    return ev


def ev_stage(stage, status):
    return {"type": "stage", "stage": stage, "status": status}
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/demo_budget_ui/test_presenter.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add demo/budget_ui/daemon/presenter.py tests/demo_budget_ui/test_presenter.py
git commit -m "feat(demo-ui): result event (fail-closed sample) + stage event"
```

---

### Task 7: The daemon watch loop -- dispatch + envelope + inject-able sender

**Files:**
- Create: `demo/budget_ui/daemon/daemon.py`
- Test: `tests/demo_budget_ui/test_daemon.py`

**Interfaces:**
- Consumes: all `presenter.ev_*` functions.
- Produces: `class Daemon(job_id: str, work_dir: str, send, since: float)` with `poll() -> None` (one pass) and `run(interval: float)` (loop). `send(event: dict) -> None` is injected (the real one POSTs; tests capture). Each posted event is the presenter payload wrapped with `job`, `seq` (monotonic), `t`.

- [ ] **Step 1: Write the failing test (drive it from copies of the real fixtures)**

```python
# tests/demo_budget_ui/test_daemon.py
import json, shutil, pathlib, time
from demo.budget_ui.daemon.daemon import Daemon
FIX = pathlib.Path(__file__).parent / "fixtures" / "trade_position_demo"

def test_daemon_emits_ordered_data_free_events(tmp_path):
    work = tmp_path / "job1"; (work / "golden").mkdir(parents=True)
    captured = []
    d = Daemon("job1", str(work), send=captured.append, since=time.time())
    # 1) drop extract_doc -> expect a 'sources' event, envelope-wrapped
    shutil.copy(FIX / "extract_doc.json", work / "extract_doc.json")
    d.poll()
    types = [e["type"] for e in captured]
    assert "sources" in types
    src = next(e for e in captured if e["type"] == "sources")
    assert src["job"] == "job1" and isinstance(src["seq"], int) and "t" in src
    # 2) drop job.json -> expect edges + gate, and 'wiring' stage
    shutil.copy(FIX / "job.json", work / "job.json")
    d.poll()
    types = [e["type"] for e in captured]
    assert "edges" in types and "gate" in types
    assert any(e["type"] == "stage" and e["stage"] == "wiring" for e in captured)
    # data-free across the whole stream
    from tests.demo_budget_ui.test_presenter import _forbidden_values, P
    for e in captured:
        P.assert_data_free(e, _forbidden_values())

def test_daemon_ignores_preexisting_artifacts_before_since(tmp_path):
    work = tmp_path / "job2"; work.mkdir()
    shutil.copy(FIX / "extract_doc.json", work / "extract_doc.json")
    time.sleep(0.01)
    d = Daemon("job2", str(work), send=(cap := []).append, since=time.time())  # since AFTER the file
    d.poll()
    assert cap == []   # pre-existing artifact older than `since` is not replayed

def test_daemon_dedups_unchanged_files(tmp_path):
    work = tmp_path / "job3"; work.mkdir()
    d = Daemon("job3", str(work), send=(cap := []).append, since=time.time() - 1)
    shutil.copy(FIX / "extract_doc.json", work / "extract_doc.json")
    d.poll(); n = len(cap); d.poll()   # second poll, no change
    assert len(cap) == n               # no re-emit
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/demo_budget_ui/test_daemon.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write minimal implementation**

```python
# demo/budget_ui/daemon/daemon.py
"""Watch a job work dir by mtime; dispatch new/changed artifacts to presenter;
wrap payloads in an envelope; send them out (injected sender). ASCII-only.
Stage transitions are keyed off WHICH artifact appeared (deterministic), not
off audit.jsonl event strings. gate:signed is keyed off test_report appearing.
"""
from __future__ import annotations

import json
import os
import time

from . import presenter as P

# artifact filename -> (stage-on-appearance, [extractor callables])
def _dispatch(name, doc, job):
    if name == "extract_doc.json":
        return [P.ev_stage("reading", "done"), P.ev_sources(doc), P.ev_stage("interpreting", "active")]
    if name == "requirement_spec.json":
        return [P.ev_rules(doc), P.ev_stage("designing", "active")]
    if name == "flow_plan.json":
        return [P.ev_nodes(doc), *P.ev_callouts_from_plan(doc), P.ev_stage("designing", "done")]
    if name == "job_draft.json":
        return [P.ev_node_config(doc), P.ev_stage("configuring", "active")]
    if name == "job.json":
        evs = [P.ev_edges(doc), P.ev_stage("wiring", "active")]
        g = P.ev_gate(doc)
        if g:
            evs.append(g)
        evs.extend(P.ev_callouts(doc))
        return evs
    return []


class Daemon:
    def __init__(self, job_id, work_dir, send, since=None):
        self.job_id = job_id
        self.work_dir = work_dir
        self.send = send
        self.since = since if since is not None else time.time()
        self._seen = {}   # filename -> mtime
        self._seq = 0

    def _emit(self, payload):
        if not payload:
            return
        self._seq += 1
        env = {"job": self.job_id, "seq": self._seq, "t": time.time()}
        env.update(payload)
        self.send(env)

    def poll(self):
        try:
            names = os.listdir(self.work_dir)
        except FileNotFoundError:
            return
        for name in sorted(names):
            path = os.path.join(self.work_dir, name)
            if not (name.endswith(".json") and os.path.isfile(path)):
                continue
            try:
                mt = os.path.getmtime(path)
            except OSError:
                continue
            if mt < self.since or self._seen.get(name) == mt:
                continue
            self._seen[name] = mt
            try:
                doc = json.loads(open(path, encoding="utf-8").read())
            except (ValueError, OSError):
                continue   # torn/half-written read: skip this pass, retry next
            if name == "test_report.json":
                self._emit(P.ev_result(doc, tier=doc.get("tier", "verified")))
                self._emit(P.ev_stage("done" if doc.get("passed") else "testing", "done"))
                continue
            for ev in _dispatch(name, doc, self.job_id):
                self._emit(ev)

    def run(self, interval=0.5):
        while True:
            self.poll()
            time.sleep(interval)
```

Note: `_dispatch` references `P.ev_callouts_from_plan`; add a thin alias so flow-plan callouts reuse the canned map keyed by the flow_plan's own components:
```python
# append to presenter.py
def ev_callouts_from_plan(flow_plan):
    return ev_callouts({"components": flow_plan.get("components") or []})
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/demo_budget_ui/test_daemon.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add demo/budget_ui/daemon/daemon.py demo/budget_ui/daemon/presenter.py tests/demo_budget_ui/test_daemon.py
git commit -m "feat(demo-ui): daemon watch loop (since-watermark, dedup, envelope, deterministic stages)"
```

---

### Task 8: Full-run replay test (the whole event stream, end to end, data-free)

**Files:**
- Test: `tests/demo_budget_ui/test_daemon.py`

**Interfaces:**
- Consumes: `Daemon`, all fixtures.

- [ ] **Step 1: Write the failing test**

```python
def test_full_run_replay_is_ordered_and_data_free(tmp_path):
    work = tmp_path / "job"; (work / "golden").mkdir(parents=True)
    cap = []
    d = Daemon("job", str(work), send=cap.append, since=time.time() - 1)
    order = ["extract_doc.json", "requirement_spec.json", "flow_plan.json",
             "job_draft.json", "job.json", "test_report_passed.json"]
    for name in order:
        target = "test_report.json" if name == "test_report_passed.json" else name
        shutil.copy(FIX / name, work / target)
        time.sleep(0.01)
        d.poll()
    types = [e["type"] for e in cap]
    # every expected type appeared, sources before edges before result
    for t in ("sources", "rules", "nodes", "node_config", "edges", "gate", "result"):
        assert t in types, t
    assert types.index("sources") < types.index("edges") < types.index("result")
    assert cap[-1]["type"] == "stage" and cap[-1]["stage"] == "done"
    from tests.demo_budget_ui.test_presenter import _forbidden_values, P
    for e in cap:
        P.assert_data_free(e, _forbidden_values())
    # seq is strictly monotonic
    seqs = [e["seq"] for e in cap]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
```

- [ ] **Step 2: Run to verify it fails, then passes**

Run: `python -m pytest tests/demo_budget_ui/test_daemon.py::test_full_run_replay_is_ordered_and_data_free -v`
Expected: FAIL first if any wiring is off; fix any ordering bug in `_dispatch`, then PASS.

- [ ] **Step 3: Run the whole phase-1 suite**

Run: `python -m pytest tests/demo_budget_ui/ -v`
Expected: PASS (all presenter + daemon tests).

- [ ] **Step 4: Commit**

```bash
git add tests/demo_budget_ui/test_daemon.py
git commit -m "test(demo-ui): full-run event-stream replay is ordered and data-free"
```

---

## Self-Review

- **Spec coverage:** event schema (spec section 8) -> Tasks 2-6; data-free rule (section 7) -> the `assert_data_free` guard threaded through Tasks 3-8; generic classification (guardrail C / section 10) -> Task 2 exact-type + humanized fallback; guardrail 2 (daemon clean start) -> Task 7 `since`; guardrail 4 (degrade, do not lie) -> Task 6 `passed` flag + Task 7 torn-read skip; stage-from-artifact (guardrail 3 direction) -> Task 7 `_dispatch`. Server endpoints (section 9) and the React frontend (section 10 render half) are Phases 2 and 3 -- out of scope here by design.
- **Placeholder scan:** none -- every step has runnable code/commands.
- **Type consistency:** `classify()` return keys (`kind`/`label`/`sub`) are consumed unchanged by `ev_nodes`/`ev_node_config`; `Daemon.send` signature matches the injected `list.append`/POST; envelope keys (`job`/`seq`/`t`/`type`) consistent across Tasks 7-8.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-09-demo-ui-phase1-presenter-daemon.md`. Two execution options:

1. **Subagent-Driven (recommended)** -- I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** -- Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
