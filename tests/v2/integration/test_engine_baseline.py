"""
Phase 1.1 probe tests (D-09 #1, #4): engine baseline behavior checks.

These two tests are the authoritative runtime probes for:

1. **D-09 #1 — Multi-output barrier materialization strategy.**
   Runs a multi-output job through ``PyETLEngine(config).execute()`` and asserts
   that every output is produced. ALSO reads ``src/v2/engine.py`` source to
   determine whether ``pl.collect_all(...)`` is used for the barrier materialization
   path. If absent, the test still passes (the job *runs*), but emits a
   ``pytest.warns`` marker that references PITFALLS #3 / SUMMARY §7 Open Q #1
   so downstream audit tasks can trace the finding. This is the authoritative
   answer to SUMMARY §7 Open Q #1.

2. **D-09 #4 — Streaming engine kwarg end-to-end.**
   Runs a minimal ``csv → filter → csv`` pipeline with ``streaming=True`` and
   asserts the job completes and the output file exists. ALSO greps ``src/v2/``
   for any legacy ``.collect(streaming=...)`` call sites (Phase 1 D-10
   regression guard: the old API must not reappear).

Any finding produced here is recorded in
``.planning/phases/01.1-v2-engine-baseline-expression-layer-execution-layer-baseline/01.1-AUDIT-streaming-pitfalls-map.md``
with an ID of the form ``AUD-STRM-NN`` or ``AUD-ENG-NN``.
"""
from __future__ import annotations

import re
from pathlib import Path

import polars as pl
import pytest

from src.v2.engine import PyETLEngine


# --------------------------------------------------------------------------
# Helper: locate the live src/v2/engine.py regardless of cwd
# --------------------------------------------------------------------------

def _engine_source_path() -> Path:
    """Return the absolute path to src/v2/engine.py as shipped in this checkout."""
    from src.v2 import engine as _engine_module
    return Path(_engine_module.__file__).resolve()


# --------------------------------------------------------------------------
# Probe test D-09 #1: pl.collect_all usage on multi-output barriers
# --------------------------------------------------------------------------

def test_collect_all_multi_output_barrier(tmp_path: Path):
    """
    Probe (D-09 #1, PITFALLS #3, SUMMARY §7 Open Q #1).

    Runs a multi-output map job (main + unmatched reject) through
    ``PyETLEngine(config).execute()`` and verifies that every output is
    produced with the expected row counts. Additionally reads the live
    ``src/v2/engine.py`` source and records whether ``pl.collect_all(...)``
    is used for multi-output barrier materialization.

    If ``pl.collect_all`` is absent, this test does NOT fail — the pipeline
    *runs correctly*, it just pays the per-output collect cost described in
    PITFALLS #3. The absence is recorded as a warning so downstream audit
    tasks can trace it, and as a finding in 01.1-AUDIT-streaming-pitfalls-map.md.
    """
    # -------------------------------------------------------------------
    # 1. Build deterministic input CSV
    # -------------------------------------------------------------------
    src_csv = tmp_path / "src.csv"
    src_csv.write_text(
        "id,amount\n"
        "1,200\n"
        "2,75\n"
        "3,30\n"
        "4,150\n"
    )

    main_out = tmp_path / "high.csv"
    low_out = tmp_path / "low.csv"
    reject_out = tmp_path / "unmatched.csv"

    # -------------------------------------------------------------------
    # 2. Multi-output topology: file_input -> map (3 outputs) -> 3 sinks
    #
    # The map component emits main + low + unmatched (filter-reject), so
    # the engine MUST materialize at the map barrier because
    # `len(result) > 1`. This is the exact hot path PITFALLS #3 asks about.
    # Pattern borrowed from tests/v2/integration/test_map_reject_flows.py
    # (TestFilterRejectIntegration) per CONTEXT.md code_context guidance.
    # -------------------------------------------------------------------
    config = {
        "name": "probe_collect_all_multi_output",
        "streaming": False,
        "components": [
            {
                "id": "input",
                "type": "file_input_delimited",
                "config": {
                    "path": str(src_csv),
                    "schema": [
                        {"name": "id", "type": "integer"},
                        {"name": "amount", "type": "integer"},
                    ],
                },
            },
            {
                "id": "transform",
                "type": "map",
                "config": {
                    "filter_reject_output": "unmatched",
                    "outputs": [
                        {
                            "name": "high",
                            "filter": "amount > 100",
                            "columns": [
                                {"name": "id", "expression": "id"},
                                {"name": "amount", "expression": "amount"},
                            ],
                        },
                        {
                            "name": "low",
                            "filter": "amount <= 50",
                            "columns": [
                                {"name": "id", "expression": "id"},
                                {"name": "amount", "expression": "amount"},
                            ],
                        },
                        {
                            "name": "unmatched",
                            "columns": [
                                {"name": "id", "expression": "id"},
                                {"name": "amount", "expression": "amount"},
                            ],
                        },
                    ],
                },
            },
            {"id": "write_high", "type": "file_output_delimited", "config": {"path": str(main_out)}},
            {"id": "write_low", "type": "file_output_delimited", "config": {"path": str(low_out)}},
            {"id": "write_reject", "type": "file_output_delimited", "config": {"path": str(reject_out)}},
        ],
        "flows": [
            {"source": "input", "target": "transform"},
            {"source": "transform", "target": "write_high", "output": "high"},
            {"source": "transform", "target": "write_low", "output": "low"},
            {"source": "transform", "target": "write_reject", "output": "unmatched"},
        ],
    }

    # -------------------------------------------------------------------
    # 3. Execute through the real engine entry point
    # -------------------------------------------------------------------
    engine = PyETLEngine(config)
    result = engine.execute()

    assert result["status"] == "success", f"multi-output job failed: {result}"
    assert "components" in result, "result missing components stats"

    # Verify the transform barrier actually fanned out to three outputs
    transform_stats = result["components"]["transform"]
    assert transform_stats.get("barrier") is True, (
        "transform should be a barrier (len(outputs) > 1) — "
        "if this fails the whole multi-output contract is broken"
    )
    rows_out = transform_stats.get("rows_out", {})
    assert set(rows_out.keys()) == {"high", "low", "unmatched"}, (
        f"expected 3 named outputs, got {rows_out}"
    )
    assert rows_out["high"] == 2, f"high branch: {rows_out}"
    assert rows_out["low"] == 1, f"low branch: {rows_out}"
    assert rows_out["unmatched"] == 1, f"unmatched branch: {rows_out}"

    # Verify all three sinks actually wrote files and row counts match
    assert main_out.exists() and len(pl.read_csv(main_out)) == 2
    assert low_out.exists() and len(pl.read_csv(low_out)) == 1
    assert reject_out.exists() and len(pl.read_csv(reject_out)) == 1

    # -------------------------------------------------------------------
    # 4. Source-level check: does engine.py use pl.collect_all?
    #    This is the authoritative answer to SUMMARY §7 Open Q #1.
    #    Recorded in 01.1-AUDIT-streaming-pitfalls-map.md, not asserted here.
    # -------------------------------------------------------------------
    engine_src = _engine_source_path().read_text()
    uses_collect_all = bool(re.search(r"\bcollect_all\s*\(", engine_src))

    if not uses_collect_all:
        import warnings

        warnings.warn(
            "PITFALLS #3 / SUMMARY §7 Open Q #1: "
            "src/v2/engine.py does NOT use pl.collect_all(...) for multi-output "
            "barriers. Per-LazyFrame .collect() is used at src/v2/engine.py "
            "around line 431 (the `df = data.collect(**self._collect_kwargs)` "
            "call inside _execute_component). Recorded as AUD-STRM finding / "
            "AUD-ENG finding in 01.1-AUDIT-streaming-pitfalls-map.md.",
            stacklevel=1,
        )


# --------------------------------------------------------------------------
# Probe test D-09 #4: streaming engine kwarg end-to-end
# --------------------------------------------------------------------------

def test_streaming_engine_kwarg_e2e(tmp_path: Path):
    """
    Probe (D-09 #4, PITFALLS #5).

    Minimal ``csv → filter → csv`` pipeline run with ``streaming=True``.
    Asserts the job completes, the output CSV exists and has the filtered
    rows, and that no legacy ``.collect(streaming=...)`` call site exists
    in ``src/v2/`` (Phase 1 D-10 regression guard).
    """
    # -------------------------------------------------------------------
    # 1. Build a 10-row input CSV
    # -------------------------------------------------------------------
    src_csv = tmp_path / "src.csv"
    src_csv.write_text(
        "id,amount\n"
        + "\n".join(f"{i},{i * 10}" for i in range(1, 11))
        + "\n"
    )
    out_csv = tmp_path / "out.csv"

    # -------------------------------------------------------------------
    # 2. Minimal streaming pipeline: file_input -> filter -> file_output
    # -------------------------------------------------------------------
    config = {
        "name": "probe_streaming_e2e",
        "streaming": True,
        "components": [
            {
                "id": "input",
                "type": "file_input_delimited",
                "config": {
                    "path": str(src_csv),
                    "schema": [
                        {"name": "id", "type": "integer"},
                        {"name": "amount", "type": "integer"},
                    ],
                },
            },
            {
                "id": "filter_big",
                "type": "filter",
                "config": {"condition": "amount > 20"},
            },
            {
                "id": "write",
                "type": "file_output_delimited",
                "config": {"path": str(out_csv)},
            },
        ],
        "flows": [
            {"source": "input", "target": "filter_big"},
            {"source": "filter_big", "target": "write"},
        ],
    }

    engine = PyETLEngine(config)
    # Sanity: the engine should have picked up streaming=True from config
    assert engine.streaming is True
    assert engine._collect_kwargs == {"engine": "streaming"}, (
        f"expected _collect_kwargs to thread engine='streaming' when "
        f"streaming=True; got {engine._collect_kwargs}"
    )

    result = engine.execute()
    assert result["status"] == "success", f"streaming job failed: {result}"
    assert out_csv.exists(), f"output csv not created: {out_csv}"

    out_df = pl.read_csv(out_csv)
    # amount > 20 keeps rows with amount in {30,40,50,60,70,80,90,100} → 8 rows
    assert len(out_df) == 8, f"expected 8 rows, got {len(out_df)}: {out_df}"
    assert sorted(out_df["id"].to_list()) == [3, 4, 5, 6, 7, 8, 9, 10]

    # -------------------------------------------------------------------
    # 3. Phase 1 D-10 regression guard: no legacy .collect(streaming=...) form
    #    should exist anywhere under src/v2/. If it reappears, the guard fires.
    # -------------------------------------------------------------------
    v2_root = _engine_source_path().parent.parent  # src/v2/
    legacy_pattern = re.compile(r"\.collect\s*\(\s*streaming\s*=")
    legacy_hits: list[str] = []
    for py_file in v2_root.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if legacy_pattern.search(line):
                legacy_hits.append(f"{py_file}:{lineno}: {line.strip()}")

    assert not legacy_hits, (
        "Phase 1 D-10 regression: legacy .collect(streaming=...) call site(s) "
        "found in src/v2/. The canonical form is "
        ".collect(**self._collect_kwargs) where _collect_kwargs carries "
        "{'engine': 'streaming'} when streaming is on.\n"
        + "\n".join(legacy_hits)
    )


# --------------------------------------------------------------------------
# AUD-REG-01 regression: global REGISTRY rejects duplicate registration
# (Phase 1.1 Tier 1 fix — PITFALLS #7 prevention rule)
# --------------------------------------------------------------------------

def test_aud_reg_01_bug_integration():
    """
    AUD-REG-01 integration regression (Phase 1.1 Tier 1 fix).

    Exercises the global REGISTRY — the one populated by engine.py's
    `# noqa: F401` component-subpackage import chain — to confirm that
    attempting to register a DIFFERENT class under an existing alias
    raises ValueError, NOT silent overwrite. This is the user-visible
    contract: the engine's component-creation path at
    ``PyETLEngine._create_components`` depends on the registry being
    authoritative; a silent overwrite would let two classes with the
    same alias coexist ambiguously and make debugging impossible.

    Uses ``file_input`` (a known-registered built-in) as the collision
    target, then restores the registry to its original state so
    subsequent tests are unaffected. PITFALLS #7 prevention rule.
    """
    from src.v2.components.base import TransformComponent
    from src.v2.components.registry import REGISTRY

    # Importing PyETLEngine triggers the full registration chain.
    _ = PyETLEngine  # noqa: F401 — referenced so engine module import runs

    # Sanity: the global registry has the expected built-in
    incumbent = REGISTRY.get("file_input_delimited")
    assert incumbent is not None, (
        "test setup failure: REGISTRY should have 'file_input_delimited' after "
        "importing PyETLEngine (engine.py triggers subpackage imports)"
    )

    # Snapshot the registry so we can restore it after the test regardless
    # of whether the decorator raises or succeeds.
    snapshot = dict(REGISTRY._registry)

    try:
        with pytest.raises(ValueError) as exc_info:
            @REGISTRY.register("file_input_delimited")
            class HijackerComp(TransformComponent):
                def apply(self, inputs):
                    return inputs

        # Error message must point at both classes (traceable)
        msg = str(exc_info.value).lower()
        assert "file_input_delimited" in msg
        assert "hijackercomp" in msg

        # Crucially: the incumbent must NOT have been overwritten
        assert REGISTRY.get("file_input_delimited") is incumbent, (
            "AUD-REG-01 violated: REGISTRY.get('file_input_delimited') was silently "
            "overwritten by HijackerComp even though ValueError was raised"
        )
    finally:
        # Restore the registry to its pre-test state
        REGISTRY._registry.clear()
        REGISTRY._registry.update(snapshot)
