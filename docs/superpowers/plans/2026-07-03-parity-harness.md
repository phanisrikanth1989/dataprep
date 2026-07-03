# Parity Harness + Oracle (deterministic agent-facing tools) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Build the deterministic, agent-facing tool layer the native subagents call via terminal: agent-facing CLIs for the plan-1/2 tools, plus a parity harness + multi-signal oracle (`run_and_validate`) and an independent reference matcher that decide PASS/FAIL by running a job through the real engine and diffing actual-vs-expected — never LLM judgment.

**Architecture:** `run_and_validate` runs a job **in-process** via `ETLEngine(dict).execute()`, harvests the run signals (status, `global_map` NB_LINE*, per-component status, dropped-unknown components, produced output **files**, reject flows), then an oracle diffs actual output files against committed **golden** expected data (composite-key or bag comparison) and checks cardinality invariants. `reference_matcher` recomputes the Phase-A match independently (pure pandas) as the oracle-of-oracle. A synthesized golden Phase-A recon job (two-source tMap exact-match -> matched + one-sided break) is the integration fixture, exercised through the **real Java bridge**.

**Tech Stack:** Python 3.12, `pandas` (installed), `ETLEngine` (`src/v1/engine/engine.py`), `pytest` + `@pytest.mark.java`.

## Global Constraints

- **Python 3.12+.** ASCII-only in all code and logs (RHEL-clean).
- **No new third-party dependency** — pandas/engine env only.
- **Native-first:** every tool has a `python -m agents.tools.<name>` CLI and emits **JSON** (agents invoke via terminal, read results as files).
- **Test the real Java bridge:** the tMap golden-job end-to-end test is `@pytest.mark.java` and takes the session `java_bridge` fixture (`tests/v1/engine/conftest.py:332-397`), which `pytest.skip`s if the JAR/JVM is unavailable. Mock-only tMap tests are not acceptable for the golden run.
- **Determinism today:** golden jobs pin dates via a fixed `id_Date` context var and avoid Java `TalendDate.getCurrentDate()`/random (the Java-bridge frozen-clock injection is deferred to the engine backlog). No `datetime.now`-style calls in new code paths that touch output data.
- **Phase A only** (one-sided exact match + one-sided no-match break). Tolerance / bidirectional / netting (Phases B-D), held-out sampling, and mutation-row generation are a documented **plan-3b**, out of scope here.
- **Two `execute()` return shapes** must both be tolerated (use `.get()`): success = `{status, execution_time, components_executed(int), components_failed(int), component_stats, job_aborted, job_name, global_map}`; exception = `{job_name, status:"error", error, execution_time:0, components_executed, components_failed, component_stats}` (no `global_map`/`job_aborted`).
- Public functions/classes carry docstrings; per-module `logging.getLogger(__name__)`.

## File Structure

- `agents/tools/extract_doc.py` — MODIFY: add `to_dict()` + a `main()`/`__main__` CLI (single JSON artifact).
- `agents/tools/validate_config.py` — MODIFY: add `main()`/`__main__` CLI.
- `agents/tools/reference_matcher.py` — CREATE: `match_phase_a(...)`, pure pandas.
- `agents/tools/run_and_validate.py` — CREATE: `run_job_capture(...) -> RunResult`, `check(...) -> dict`, `main()`/`__main__` CLI.
- `tests/fixtures/recon/golden_phase_a/` — CREATE: `job.json`, `main.csv`, `lookup.csv`, `matched_expected.csv`, `reject_expected.csv`, `README.md`.
- Tests under `tests/agents/tools/`.

---

### Task 1: `extract_doc` CLI (agent-facing adapter)

**Files:**
- Modify: `agents/tools/extract_doc.py`
- Test: `tests/agents/tools/test_extract_doc_cli.py`

**Interfaces:**
- Consumes: `extract_doc(path, raise_on_error) -> ExtractResult`, `ConformanceError` (existing).
- Produces: `to_dict(result: ExtractResult) -> dict`; `main(argv: list[str] | None = None) -> int`. CLI: `python -m agents.tools.extract_doc <path.docx> [--out FILE] [--no-raise]`. Emits ONE JSON object with all `ExtractResult` fields (schema+rules+sample+expected+keys+facts+conformance). Exit 0 = conformant, 1 = non-conformant (with `--no-raise`), 2 = conformance error raised.

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/tools/test_extract_doc_cli.py
import json
from dataclasses import dataclass, field

import agents.tools.extract_doc as ed


def _fake_result(ok=True):
    return ed.ExtractResult(
        sources_schema={"ledger": [ed.ColumnSpec("txn_id", "string", False, True)]},
        rules=[{"id": "R1", "kind": "match", "description": "join on txn_id"}],
        sample_input={"ledger": [{"txn_id": "1"}]},
        expected_output={"matched": [{"txn_id": "1"}]},
        output_keys={"matched": ["txn_id"]},
        derived_facts={"ledger": {"txn_id": {"unique": True}}},
        conformance=ed.ConformanceReport(ok=ok),
    )


def test_to_dict_roundtrips_all_fields():
    d = ed.to_dict(_fake_result())
    assert d["sources_schema"]["ledger"][0]["name"] == "txn_id"
    assert d["rules"][0]["id"] == "R1"
    assert d["output_keys"]["matched"] == ["txn_id"]
    assert d["conformance"]["ok"] is True
    json.dumps(d)  # must be JSON-serializable


def test_cli_writes_json_and_exit_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(ed, "extract_doc", lambda path, raise_on_error=True: _fake_result(ok=True))
    out = tmp_path / "r.json"
    rc = ed.main(["ignored.docx", "--out", str(out)])
    assert rc == 0
    payload = json.loads(out.read_text())
    assert payload["rules"][0]["kind"] == "match"


def test_cli_conformance_error_exit_two(tmp_path, monkeypatch):
    def _raise(path, raise_on_error=True):
        raise ed.ConformanceError(ed.ConformanceReport(ok=False, missing_blocks=["Sample Input"]))
    monkeypatch.setattr(ed, "extract_doc", _raise)
    out = tmp_path / "r.json"
    rc = ed.main(["bad.docx", "--out", str(out)])
    assert rc == 2
    assert json.loads(out.read_text())["conformance"]["missing_blocks"] == ["Sample Input"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_extract_doc_cli.py -v`
Expected: FAIL — `AttributeError: module 'agents.tools.extract_doc' has no attribute 'to_dict'` / `main`.

- [ ] **Step 3: Write minimal implementation**

Append to `agents/tools/extract_doc.py`:
```python
def to_dict(result: "ExtractResult") -> dict:
    """Serialize an ExtractResult (incl. nested dataclasses) to a JSON-able dict."""
    from dataclasses import asdict
    return asdict(result)


def main(argv=None) -> int:
    """CLI: extract a requirements .docx to one JSON artifact (all fields)."""
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description="Extract a recon requirements .docx to JSON.")
    parser.add_argument("path", help="path to the requirements .docx")
    parser.add_argument("--out", help="write JSON here (default: stdout)")
    parser.add_argument("--no-raise", action="store_true",
                        help="do not raise on a non-conformant doc; emit it with conformance.ok=false")
    args = parser.parse_args(argv)

    def _emit(payload):
        text = json.dumps(payload, indent=2)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(text)
        else:
            sys.stdout.write(text + "\n")

    try:
        result = extract_doc(args.path, raise_on_error=not args.no_raise)
    except ConformanceError as exc:
        from dataclasses import asdict
        _emit({"ok": False, "conformance": asdict(exc.report)})
        return 2
    _emit(to_dict(result))
    return 0 if result.conformance.ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_extract_doc_cli.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add agents/tools/extract_doc.py tests/agents/tools/test_extract_doc_cli.py
git commit -m "feat(agents): extract_doc agent-facing CLI (single JSON artifact)"
```

---

### Task 2: `validate_config` CLI (agent-facing adapter)

**Files:**
- Modify: `agents/tools/validate_config.py`
- Test: `tests/agents/tools/test_validate_config_cli.py`

**Interfaces:**
- Consumes: `validate_config(component_type, config, strict) -> list` (existing).
- Produces: `main(argv=None) -> int`. CLI: `python -m agents.tools.validate_config --type T --config FILE.json [--loose]`. Prints `{"type","valid","errors"}`; exit 0 = valid, 1 = errors, 2 = usage/load error.

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/tools/test_validate_config_cli.py
import json

import agents.tools.validate_config as vc


def _write(tmp_path, obj):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(obj))
    return str(p)


def test_cli_valid_filterrows_exit_zero(tmp_path, capsys):
    cfg = _write(tmp_path, {"conditions": [{"column": "amt", "operator": ">", "value": "0"}]})
    rc = vc.main(["--type", "FilterRows", "--config", cfg])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["valid"] is True and out["errors"] == []


def test_cli_invalid_reports_errors_exit_one(tmp_path, capsys):
    cfg = _write(tmp_path, {"bogus_key": 1, "conditions": []})
    rc = vc.main(["--type", "FilterRows", "--config", cfg])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1 and out["valid"] is False and any("bogus_key" in e for e in out["errors"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_validate_config_cli.py -v`
Expected: FAIL — `AttributeError: module 'agents.tools.validate_config' has no attribute 'main'`.

- [ ] **Step 3: Write minimal implementation**

Append to `agents/tools/validate_config.py`:
```python
def main(argv=None) -> int:
    """CLI: validate a component config JSON file against its curated schema."""
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description="Validate a component config against its schema.")
    parser.add_argument("--type", required=True, help="component type (or alias)")
    parser.add_argument("--config", required=True, help="path to a JSON file holding the component config dict")
    parser.add_argument("--loose", action="store_true", help="strict=False (skip the unknown-key check)")
    args = parser.parse_args(argv)
    try:
        with open(args.config, encoding="utf-8") as fh:
            config = json.load(fh)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"cannot read config {args.config!r}: {exc}\n")
        return 2
    errors = validate_config(args.type, config, strict=not args.loose)
    sys.stdout.write(json.dumps({"type": args.type, "valid": not errors, "errors": errors}) + "\n")
    return 0 if not errors else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_validate_config_cli.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add agents/tools/validate_config.py tests/agents/tools/test_validate_config_cli.py
git commit -m "feat(agents): validate_config agent-facing CLI"
```

---

### Task 3: `reference_matcher` — independent Phase-A matcher (oracle-of-oracle)

**Files:**
- Create: `agents/tools/reference_matcher.py`
- Test: `tests/agents/tools/test_reference_matcher.py`

**Interfaces:**
- Produces: `match_phase_a(main: pd.DataFrame, lookup: pd.DataFrame, keys: list[str], on_multi: str = "first") -> dict` returning `{"matched": pd.DataFrame, "breaks": pd.DataFrame, "stats": {"n_matched": int, "n_break_no_match": int, "n_break_multi": int}}`. Pure pandas, no engine. Semantics (Talend-parity, Phase A): equality inner-join of `main` to `lookup` on `keys`; a main row with **no** lookup match -> `breaks` with `break_reason="no_match"`; a main row matching **>1** lookup row is handled by `on_multi`: `"first"` (UNIQUE_MATCH-like: keep first lookup match, 1 matched row), `"all"` (ALL_MATCHES: fan-out to N matched rows), `"break"` (duplicate-disposition: 1 `breaks` row with `break_reason="multi_match"`, not matched). `breaks` carries the MAIN columns + `break_reason`; `matched` carries main columns + lookup non-key columns.

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/tools/test_reference_matcher.py
import pandas as pd

from agents.tools.reference_matcher import match_phase_a


def _main():
    return pd.DataFrame({"cc": ["US", "UK", "FR"], "amt": [10, 20, 30]})


def test_exact_match_and_one_sided_break():
    lookup = pd.DataFrame({"cc": ["US", "UK"], "name": ["United States", "United Kingdom"]})
    r = match_phase_a(_main(), lookup, keys=["cc"])
    assert r["stats"] == {"n_matched": 2, "n_break_no_match": 1, "n_break_multi": 0}
    assert set(r["matched"]["cc"]) == {"US", "UK"}
    assert list(r["breaks"]["cc"]) == ["FR"]
    assert list(r["breaks"]["break_reason"]) == ["no_match"]


def test_on_multi_first_keeps_one():
    lookup = pd.DataFrame({"cc": ["US", "US", "UK"], "name": ["A", "B", "United Kingdom"]})
    r = match_phase_a(_main(), lookup, keys=["cc"], on_multi="first")
    assert r["stats"]["n_matched"] == 2 and r["stats"]["n_break_multi"] == 0
    assert list(r["matched"].loc[r["matched"]["cc"] == "US", "name"]) == ["A"]


def test_on_multi_all_fans_out():
    lookup = pd.DataFrame({"cc": ["US", "US", "UK"], "name": ["A", "B", "United Kingdom"]})
    r = match_phase_a(_main(), lookup, keys=["cc"], on_multi="all")
    assert r["stats"]["n_matched"] == 3  # US x2 + UK x1


def test_on_multi_break_flags_duplicate():
    lookup = pd.DataFrame({"cc": ["US", "US", "UK"], "name": ["A", "B", "United Kingdom"]})
    r = match_phase_a(_main(), lookup, keys=["cc"], on_multi="break")
    assert r["stats"] == {"n_matched": 1, "n_break_no_match": 1, "n_break_multi": 1}
    assert set(r["breaks"].loc[r["breaks"]["break_reason"] == "multi_match", "cc"]) == {"US"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_reference_matcher.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agents.tools.reference_matcher'`.

- [ ] **Step 3: Write minimal implementation**

```python
# agents/tools/reference_matcher.py
"""Independent Phase-A exact-match reference matcher (the oracle-of-oracle).

Recomputes the recon match with pure pandas so the engine's output can be
cross-checked against a second, independent implementation.
"""
from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

_VALID_ON_MULTI = ("first", "all", "break")


def match_phase_a(main: pd.DataFrame, lookup: pd.DataFrame, keys: list, on_multi: str = "first") -> dict:
    """Compute Phase-A {matched, breaks, stats} independently of the engine.

    Args:
        main: left/driving rows.
        lookup: reference rows.
        keys: equality join key columns (present in both frames).
        on_multi: how to treat a main row matching >1 lookup row -- "first"
            (keep first), "all" (fan-out), or "break" (flag as multi_match break).

    Returns:
        {"matched": DataFrame, "breaks": DataFrame (with break_reason), "stats": {...}}.
    """
    if on_multi not in _VALID_ON_MULTI:
        raise ValueError(f"on_multi must be one of {_VALID_ON_MULTI}, got {on_multi!r}")
    main_cols = list(main.columns)
    lookup_extra = [c for c in lookup.columns if c not in keys]

    # count lookup matches per key tuple
    counts = lookup.groupby(keys, dropna=False).size().rename("_n").reset_index()
    m = main.merge(counts, on=keys, how="left")
    n = m["_n"].fillna(0).astype(int)

    no_match = m[n == 0]
    multi = m[n > 1]
    single = m[n == 1]

    break_frames = [no_match[main_cols].assign(break_reason="no_match")]
    matched_seed = single

    if on_multi == "break":
        break_frames.append(multi[main_cols].assign(break_reason="multi_match"))
        n_break_multi = len(multi)
    else:
        matched_seed = m[n >= 1] if on_multi == "all" else pd.concat([single, multi], ignore_index=True)
        n_break_multi = 0

    # join matched_seed to lookup for the carried lookup columns
    if on_multi == "all":
        matched = matched_seed[main_cols].merge(lookup, on=keys, how="inner")
    else:
        # first-match: one lookup row per key
        first_lookup = lookup.drop_duplicates(subset=keys, keep="first")
        matched = matched_seed[main_cols].merge(first_lookup, on=keys, how="inner")

    breaks = pd.concat(break_frames, ignore_index=True) if break_frames else pd.DataFrame(columns=main_cols + ["break_reason"])
    stats = {
        "n_matched": int(len(matched)),
        "n_break_no_match": int(len(no_match)),
        "n_break_multi": int(n_break_multi),
    }
    logger.debug("[reference_matcher] %s", stats)
    return {"matched": matched.reset_index(drop=True), "breaks": breaks.reset_index(drop=True), "stats": stats}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_reference_matcher.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add agents/tools/reference_matcher.py tests/agents/tools/test_reference_matcher.py
git commit -m "feat(agents): independent Phase-A reference matcher (oracle-of-oracle)"
```

---

### Task 4: `run_and_validate` — engine-run capture

**Files:**
- Create: `agents/tools/run_and_validate.py`
- Test: `tests/agents/tools/test_run_capture.py`

**Interfaces:**
- Consumes: `from src.v1.engine.engine import ETLEngine`.
- Produces: `RunResult` dataclass and `run_job_capture(job_config: dict, work_dir) -> RunResult`. `RunResult` fields: `status: str`, `job_aborted: bool`, `error: str | None`, `global_map: dict`, `component_stats: dict`, `dropped_components: list[str]`, `outputs: dict[str, "pd.DataFrame"]` (keyed by output-component id), `raw_stats: dict`. `run_job_capture` deep-copies the job, runs `ETLEngine(job).execute()` (tolerating a raised exception by producing a `status="error"` result), computes `dropped_components` as config ids absent from `component_stats`, and reads each `FileOutput*` component's `filepath` back into a DataFrame using that component's `fieldseparator`.

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/tools/test_run_capture.py
import pandas as pd

from agents.tools.run_and_validate import RunResult, run_job_capture


def _passthrough_job(in_csv, out_csv):
    return {
        "job_name": "passthrough",
        "components": [
            {"id": "in1", "type": "FileInputDelimited",
             "config": {"filepath": str(in_csv), "fieldseparator": ",", "header_rows": 1},
             "schema": [{"name": "cc", "type": "string"}, {"name": "amt", "type": "string"}]},
            {"id": "out1", "type": "FileOutputDelimited",
             "config": {"filepath": str(out_csv), "fieldseparator": ",", "include_header": True,
                        "file_exist_exception": False},
             "schema": [{"name": "cc", "type": "string"}, {"name": "amt", "type": "string"}]},
        ],
        "flows": [{"from": "in1", "to": "out1", "type": "main"}],
    }


def test_capture_reads_output_file_and_stats(tmp_path):
    in_csv = tmp_path / "in.csv"
    in_csv.write_text("cc,amt\nUS,10\nUK,20\n")
    out_csv = tmp_path / "out.csv"
    rr = run_job_capture(_passthrough_job(in_csv, out_csv), tmp_path)
    assert isinstance(rr, RunResult)
    assert rr.status == "success"
    assert rr.dropped_components == []
    assert set(rr.outputs["out1"]["cc"]) == {"US", "UK"}


def test_capture_detects_dropped_unknown_component(tmp_path):
    in_csv = tmp_path / "in.csv"
    in_csv.write_text("cc,amt\nUS,10\n")
    job = _passthrough_job(in_csv, tmp_path / "out.csv")
    job["components"].append({"id": "ghost", "type": "tNotARealComponent", "config": {}, "schema": []})
    rr = run_job_capture(job, tmp_path)
    assert "ghost" in rr.dropped_components
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_run_capture.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agents.tools.run_and_validate'`.

- [ ] **Step 3: Write minimal implementation**

```python
# agents/tools/run_and_validate.py
"""Deterministic parity harness: run a job through the real engine, harvest
signals, and (Task 5) diff actual output against golden expected data."""
from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_FILE_OUTPUT_TYPES = {"FileOutputDelimited", "tFileOutputDelimited"}


@dataclass
class RunResult:
    """Signals harvested from one engine run of a job."""
    status: str
    job_aborted: bool = False
    error: str | None = None
    global_map: dict = field(default_factory=dict)
    component_stats: dict = field(default_factory=dict)
    dropped_components: list = field(default_factory=list)
    outputs: dict = field(default_factory=dict)
    raw_stats: dict = field(default_factory=dict)


def _read_output(component: dict):
    cfg = component.get("config", {})
    path = cfg.get("filepath")
    if not path or not Path(path).exists():
        return None
    sep = cfg.get("fieldseparator", ";")
    try:
        return pd.read_csv(path, sep=sep, dtype=str, keep_default_na=False)
    except Exception as exc:  # a malformed/empty output file is a signal, not a crash
        logger.warning("[run_and_validate] could not read output %s: %s", path, exc)
        return None


def run_job_capture(job_config: dict, work_dir) -> RunResult:
    """Run a job through ETLEngine and harvest its run signals into a RunResult."""
    from src.v1.engine.engine import ETLEngine

    job = copy.deepcopy(job_config)
    try:
        engine = ETLEngine(job)
        stats = engine.execute()
    except Exception as exc:  # constructor/other hard failure -> uniform error result
        logger.warning("[run_and_validate] engine raised: %s", exc)
        return RunResult(status="error", error=str(exc))

    component_stats = stats.get("component_stats", {})
    config_ids = [c.get("id") for c in job.get("components", [])]
    dropped = [cid for cid in config_ids if cid and cid not in component_stats]

    outputs = {}
    for comp in job.get("components", []):
        if comp.get("type") in _FILE_OUTPUT_TYPES:
            df = _read_output(comp)
            if df is not None:
                outputs[comp["id"]] = df

    return RunResult(
        status=stats.get("status", "error"),
        job_aborted=bool(stats.get("job_aborted", False)),
        error=stats.get("error"),
        global_map=stats.get("global_map", {}),
        component_stats=component_stats,
        dropped_components=dropped,
        outputs=outputs,
        raw_stats=stats,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_run_capture.py -v`
Expected: PASS (2 tests). (Bridge-free: this job has no tMap/`{{java}}`.)

- [ ] **Step 5: Commit**

```bash
git add agents/tools/run_and_validate.py tests/agents/tools/test_run_capture.py
git commit -m "feat(agents): parity-harness engine-run capture (RunResult)"
```

---

### Task 5: `run_and_validate` — the oracle + CLI

**Files:**
- Modify: `agents/tools/run_and_validate.py`
- Test: `tests/agents/tools/test_oracle.py`

**Interfaces:**
- Consumes: `RunResult`, `run_job_capture` (Task 4).
- Produces: `diff_frames(actual: pd.DataFrame | None, expected: pd.DataFrame, keys: list | None) -> dict`; `check(run_result: RunResult, expected: dict[str, pd.DataFrame], output_map: dict[str, str], keys: dict[str, list]) -> dict`; `main(argv=None) -> int`. `check` returns a `test_report` dict `{"passed": bool, "engine": {...}, "outputs": {name: diff}, "reasons": [...]}`: fails if `status != "success"`, any `component_stats[id].get("status")=="error"`, `dropped_components` non-empty, or any output diff is non-empty. `diff_frames` compares by composite `keys` when given (reports `missing`/`unexpected`/`value_mismatch` counts), else bag/multiset comparison of whole rows. `output_map` maps an expected-output name -> the producing component id in `run_result.outputs`. CLI: `python -m agents.tools.run_and_validate --job JOB.json --golden-dir DIR [--out REPORT.json]` where `DIR` holds `<name>_expected.csv` files and a `manifest.json` (`{"outputs": {name: {"component": id, "keys": [...], "sep": ","}}}`).

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/tools/test_oracle.py
import pandas as pd

from agents.tools.run_and_validate import RunResult, check, diff_frames


def test_diff_keyed_detects_missing_and_mismatch():
    exp = pd.DataFrame({"cc": ["US", "UK"], "name": ["A", "B"]})
    act = pd.DataFrame({"cc": ["US"], "name": ["X"]})
    d = diff_frames(act, exp, keys=["cc"])
    assert d["missing"] == 1  # UK absent from actual
    assert d["value_mismatch"] == 1  # US name X != A


def test_diff_bag_when_no_keys():
    exp = pd.DataFrame({"v": ["a", "b"]})
    assert diff_frames(pd.DataFrame({"v": ["b", "a"]}), exp, keys=None)["equal"] is True
    assert diff_frames(pd.DataFrame({"v": ["a"]}), exp, keys=None)["equal"] is False


def _rr(outputs, status="success", dropped=None, comp_err=None):
    cs = {"c": {"status": "error"}} if comp_err else {}
    return RunResult(status=status, outputs=outputs, dropped_components=dropped or [], component_stats=cs)


def test_check_passes_on_exact_match():
    exp = {"matched": pd.DataFrame({"cc": ["US"]})}
    rr = _rr({"out1": pd.DataFrame({"cc": ["US"]})})
    rep = check(rr, exp, output_map={"matched": "out1"}, keys={"matched": ["cc"]})
    assert rep["passed"] is True


def test_check_fails_on_dropped_component():
    exp = {"matched": pd.DataFrame({"cc": ["US"]})}
    rr = _rr({"out1": pd.DataFrame({"cc": ["US"]})}, dropped=["ghost"])
    rep = check(rr, exp, output_map={"matched": "out1"}, keys={"matched": ["cc"]})
    assert rep["passed"] is False
    assert any("dropped" in r for r in rep["reasons"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_oracle.py -v`
Expected: FAIL — `ImportError: cannot import name 'check'`.

- [ ] **Step 3: Write minimal implementation**

Append to `agents/tools/run_and_validate.py`:
```python
def _bag(df: pd.DataFrame):
    return sorted(tuple(str(v) for v in row) for row in df.itertuples(index=False, name=None))


def diff_frames(actual, expected, keys):
    """Diff an actual output frame vs expected: keyed diff, or bag equality if keys is None."""
    if actual is None:
        return {"equal": False, "missing": int(len(expected)), "unexpected": 0, "value_mismatch": 0,
                "reason": "no actual output"}
    if not keys:
        a, e = _bag(actual), _bag(expected)
        return {"equal": a == e, "actual_rows": len(actual), "expected_rows": len(expected)}
    exp = expected.astype(str).set_index(keys, drop=False)
    act = actual.astype(str).set_index(keys, drop=False)
    missing = exp.index.difference(act.index)
    unexpected = act.index.difference(exp.index)
    common = exp.index.intersection(act.index)
    cols = [c for c in expected.columns if c not in keys]
    mismatch = 0
    for idx in common:
        er, ar = exp.loc[[idx]].iloc[0], act.loc[[idx]].iloc[0]
        if any(er.get(c) != ar.get(c) for c in cols):
            mismatch += 1
    return {"equal": len(missing) == 0 and len(unexpected) == 0 and mismatch == 0,
            "missing": int(len(missing)), "unexpected": int(len(unexpected)), "value_mismatch": int(mismatch)}


def check(run_result, expected, output_map, keys) -> dict:
    """Multi-signal PASS/FAIL: engine status + no dropped/errored components + per-output diffs."""
    reasons = []
    if run_result.status != "success":
        reasons.append(f"engine status={run_result.status!r}" + (f": {run_result.error}" if run_result.error else ""))
    if run_result.dropped_components:
        reasons.append(f"dropped (unknown-type) components: {run_result.dropped_components}")
    errored = [cid for cid, s in run_result.component_stats.items() if isinstance(s, dict) and s.get("status") == "error"]
    if errored:
        reasons.append(f"components errored: {errored}")

    out_diffs = {}
    for name, exp_df in expected.items():
        comp_id = output_map.get(name)
        actual = run_result.outputs.get(comp_id) if comp_id else None
        d = diff_frames(actual, exp_df, keys.get(name))
        out_diffs[name] = d
        if not d.get("equal", False):
            reasons.append(f"output {name!r} differs: {d}")

    return {
        "passed": not reasons,
        "engine": {"status": run_result.status, "dropped": run_result.dropped_components,
                   "global_map": run_result.global_map},
        "outputs": out_diffs,
        "reasons": reasons,
    }


def main(argv=None) -> int:
    """CLI: run a job, diff against a golden dir, emit test_report.json."""
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description="Run a job and validate its output vs golden data.")
    parser.add_argument("--job", required=True, help="path to the job.json")
    parser.add_argument("--golden-dir", required=True, help="dir with <name>_expected.csv + manifest.json")
    parser.add_argument("--out", help="write test_report JSON here (default: stdout)")
    args = parser.parse_args(argv)

    with open(args.job, encoding="utf-8") as fh:
        job = json.load(fh)
    gdir = Path(args.golden_dir)
    manifest = json.loads((gdir / "manifest.json").read_text(encoding="utf-8"))
    expected, output_map, keys = {}, {}, {}
    for name, spec in manifest["outputs"].items():
        sep = spec.get("sep", ",")
        expected[name] = pd.read_csv(gdir / f"{name}_expected.csv", sep=sep, dtype=str, keep_default_na=False)
        output_map[name] = spec["component"]
        keys[name] = spec.get("keys")

    run_result = run_job_capture(job, gdir)
    report = check(run_result, expected, output_map, keys)
    text = json.dumps(report, indent=2, default=str)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text + "\n")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_oracle.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add agents/tools/run_and_validate.py tests/agents/tools/test_oracle.py
git commit -m "feat(agents): multi-signal oracle + run_and_validate CLI (test_report.json)"
```

---

### Task 6: Golden Phase-A recon job + live-bridge end-to-end

**Files:**
- Create: `tests/fixtures/recon/golden_phase_a/{job.json, main.csv, lookup.csv, manifest.json, matched_expected.csv, reject_expected.csv, README.md}`
- Test: `tests/agents/tools/test_golden_phase_a_e2e.py`

**Interfaces:**
- Consumes: `run_job_capture`, `check` (Tasks 4-5); the session `java_bridge` fixture (`tests/v1/engine/conftest.py`).
- Produces: a committed, code-verified Phase-A golden recon job (two-source tMap exact match -> `matched` file + `reject` file) and its `@pytest.mark.java` end-to-end test asserting the harness PASSES on the golden and FAILS on a mutation.

- [ ] **Step 1: Author the golden job + inputs, capture expected**

Model the job on `tests/fixtures/jobs/transform/05_4/inner_reject.json` but with **FileOutputDelimited** sinks. Author `main.csv` (`;`-delimited, header `cc;amt`): rows `US;10`, `UK;20`, `FR;30`, `DE;40`. Author `lookup.csv` (header `cc;name`): `US;United States`, `UK;United Kingdom` (so US/UK match; FR/DE break). Write `job.json`: `tFileInputDelimited` (main) + `tFileInputDelimited` (lookup) -> `tMap` (INNER-join semantics on `cc`, main output `matched` with columns `cc,amt,name`; a reject output `reject` with `is_reject: true` carrying `cc,amt`) -> `FileOutputDelimited` `out_matched` (filepath `matched.csv`) + `FileOutputDelimited` `out_reject` (filepath `reject.csv`). Set `java_config.enabled: true` with the routines list copied from the 05_4 fixture. Use absolute-relative filepaths the test will rewrite to `tmp_path` (the test mutates filepaths before running; the committed `job.json` uses placeholder relative paths under the fixture dir).

Capture expected: run the job once (in a scratch `python -c` or a throwaway) via the harness against `tmp`, then **freeze** the produced `matched.csv` -> `matched_expected.csv` and `reject.csv` -> `reject_expected.csv`, and hand-verify against `reference_matcher.match_phase_a(main, lookup, keys=["cc"])` (matched = {US,UK}; breaks = {FR,DE}). Write `manifest.json`:
```json
{"outputs": {
  "matched": {"component": "out_matched", "keys": ["cc"], "sep": ";"},
  "reject":  {"component": "out_reject",  "keys": ["cc"], "sep": ";"}}}
```
Write `README.md` documenting: source (05_4-derived), the pinned determinism (no dates/random), and that `*_expected.csv` were engine-captured + reference-matcher-verified on <commit>.

- [ ] **Step 2: Write the failing test**

```python
# tests/agents/tools/test_golden_phase_a_e2e.py
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from agents.tools.run_and_validate import check, run_job_capture

pytestmark = [pytest.mark.java, pytest.mark.integration]

_GOLDEN = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "recon" / "golden_phase_a"


def _prepare(tmp_path):
    """Copy the golden fixture into tmp and rewrite filepaths onto tmp."""
    for f in ("main.csv", "lookup.csv"):
        shutil.copy(_GOLDEN / f, tmp_path / f)
    job = json.loads((_GOLDEN / "job.json").read_text())
    for comp in job["components"]:
        cfg = comp.get("config", {})
        if comp["type"].endswith("FileInputDelimited"):
            cfg["filepath"] = str(tmp_path / Path(cfg["filepath"]).name)
        if comp["type"].endswith("FileOutputDelimited"):
            cfg["filepath"] = str(tmp_path / Path(cfg["filepath"]).name)
    return job


def _expected():
    exp = {}
    for name in ("matched", "reject"):
        exp[name] = pd.read_csv(_GOLDEN / f"{name}_expected.csv", sep=";", dtype=str, keep_default_na=False)
    return exp


def test_harness_passes_on_golden(java_bridge, tmp_path):
    job = _prepare(tmp_path)
    rr = run_job_capture(job, tmp_path)
    rep = check(rr, _expected(), output_map={"matched": "out_matched", "reject": "out_reject"},
                keys={"matched": ["cc"], "reject": ["cc"]})
    assert rep["passed"] is True, rep["reasons"]


def test_harness_fails_on_mutated_expected(java_bridge, tmp_path):
    job = _prepare(tmp_path)
    rr = run_job_capture(job, tmp_path)
    bad = _expected()
    bad["matched"].loc[0, "cc"] = "ZZ"  # corrupt expected -> harness must catch the mismatch
    rep = check(rr, bad, output_map={"matched": "out_matched", "reject": "out_reject"},
                keys={"matched": ["cc"], "reject": ["cc"]})
    assert rep["passed"] is False
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/agents/tools/test_golden_phase_a_e2e.py -v -m java`
Expected: FAIL first because the fixture files don't exist yet / filepaths mismatch; iterate on `job.json` (component types, flow `from`/`to`, tMap output names, `is_reject`) until the golden captures and both tests pass. If the JVM/JAR is unavailable the test SKIPS (via `java_bridge`), which is acceptable in that environment but must PASS where the gate runs.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/agents/tools/test_golden_phase_a_e2e.py -v -m java`
Expected: PASS (2 tests) — harness PASSES on the golden, FAILS on the mutation. Also run the whole tool suite: `python -m pytest tests/agents/tools/ -v` (all green).

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/recon/golden_phase_a tests/agents/tools/test_golden_phase_a_e2e.py
git commit -m "test(agents): golden Phase-A recon job + live-bridge harness e2e"
```

---

## Self-Review

**1. Spec coverage:** run-engine + read stats/reject/skipped + diff vs real expected (spec §8.1-8.3) — Tasks 4,5. Membership-exact partition (matched vs break as separate outputs, each diffed) — Tasks 5,6. Composite-key + bag comparison (§8.2 tail) — Task 5 `diff_frames`. Invariants-by-cardinality foundation (row counts via `global_map`, dropped detection) — Tasks 4,5 (full cardinality invariant set = plan-3b). Independent reference matcher (§8.2.4 oracle-of-oracle) — Task 3. Reading engine failure signals incl. dropped-unknown (§8.3) — Task 4. Determinism via pinned context date, no Java clock (§8.4, deferred parts noted) — Global Constraints + Task 6. Native-first CLIs (pivot) — Tasks 1,2,5. Real Java bridge for tMap (CLAUDE.md) — Task 6.

**2. Placeholder scan:** no TBD/TODO; every code step has complete code. Task 6 Step 1 is an authoring+capture step (bounded by 05_4 as the structural template + the reference-matcher cross-check as the acceptance oracle), not a placeholder.

**3. Type consistency:** `RunResult` fields, `run_job_capture(job_config, work_dir)`, `diff_frames(actual, expected, keys)`, `check(run_result, expected, output_map, keys)`, `match_phase_a(main, lookup, keys, on_multi)`, and the `manifest.json` shape are consistent across Tasks 3-6. `to_dict`/`main` names consistent with Tasks 1-2.

## plan-3b DROPPED (reconciliation is TLM's job, not this tool's)
Plan-3b's reconciliation extensions -- tolerance / bidirectional / netting / waterfall signals (Phases B-D), held-out sampling, automated mutation-row generation, the full cardinality invariant battery (sum reconciliation, both-side accounting), predicate-consistency on `break_code`, and the duplicate-key-break golden job -- are **DROPPED**. This tool does data ENRICHMENT/prep; the actual reconciliation (matching / breaking / tolerance / netting) happens downstream in **SmartStream TLM** (see `docs/superpowers/specs/2026-07-03-enrichment-scope-correction.md`). The harness's **enrichment validation is KEPT**: diff the produced output against the expected output (`diff_frames`) plus the engine-signal checks (status, dropped-unknown components, per-component errors, `global_map` NB_LINE*) in `check` -- component-agnostic, which is exactly what enrichment validation needs.
