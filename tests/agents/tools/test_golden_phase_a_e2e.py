"""Live-bridge end-to-end for the golden Phase-A recon job (parity-harness Task 6).

Runs the committed golden job
(``tests/fixtures/recon/golden_phase_a/job.json``) through the real engine +
live Java bridge via ``run_job_capture`` and asserts the parity harness
(``check``) PASSES on the golden and FAILS on a mutated expectation. The golden
is a two-source tMap exact-match recon: main rows ``US``/``UK`` match the lookup
and land in ``matched.csv``; ``FR``/``DE`` have no lookup and land in
``reject.csv`` as one-sided breaks (tMap ``inner_join_reject`` output).

The ``*_expected.csv`` were engine-captured and cross-verified against the
independent ``reference_matcher.match_phase_a`` oracle (see the fixture
``README.md``); ``test_harness_passes_on_golden`` re-asserts that oracle-of-oracle
agreement on every live run so the golden can never silently drift from the
independent matcher.

Marked ``@pytest.mark.java``: it needs a real JVM. The session ``java_bridge``
fixture (re-exported via this package's ``conftest.py``) skips the test when the
JAR/JVM is unavailable; where the coverage gate runs (JVM present) it MUST pass.
"""
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from agents.tools.reference_matcher import match_phase_a
from agents.tools.run_and_validate import check, run_job_capture

pytestmark = [pytest.mark.java, pytest.mark.integration]

# tests/agents/tools/<this file> -> parents[3] is the repo root.
_GOLDEN = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "recon" / "golden_phase_a"


def _manifest_outputs() -> dict:
    return json.loads((_GOLDEN / "manifest.json").read_text(encoding="utf-8"))["outputs"]


def _prepare(tmp_path: Path) -> dict:
    """Copy the golden inputs into tmp and rewrite every input+output filepath onto tmp."""
    for f in ("main.csv", "lookup.csv"):
        shutil.copy(_GOLDEN / f, tmp_path / f)
    job = json.loads((_GOLDEN / "job.json").read_text(encoding="utf-8"))
    for comp in job["components"]:
        cfg = comp.get("config", {})
        ctype = comp["type"]
        if ctype.endswith("FileInputDelimited") or ctype.endswith("FileOutputDelimited"):
            cfg["filepath"] = str(tmp_path / Path(cfg["filepath"]).name)
    return job


def _expected() -> dict:
    exp = {}
    for name, spec in _manifest_outputs().items():
        exp[name] = pd.read_csv(
            _GOLDEN / f"{name}_expected.csv",
            sep=spec.get("sep", ";"), dtype=str, keep_default_na=False,
        )
    return exp


def _output_map_and_keys():
    outs = _manifest_outputs()
    output_map = {name: spec["component"] for name, spec in outs.items()}
    keys = {name: spec.get("keys") for name, spec in outs.items()}
    return output_map, keys


def test_harness_passes_on_golden(java_bridge, tmp_path):
    """Harness PASSES on the golden, and the engine partition equals the independent matcher."""
    job = _prepare(tmp_path)
    rr = run_job_capture(job, tmp_path)
    output_map, keys = _output_map_and_keys()
    rep = check(rr, _expected(), output_map=output_map, keys=keys)
    assert rep["passed"] is True, rep["reasons"]

    # Oracle-of-oracle: the engine's matched/break partition must equal the
    # independent reference matcher's, and be exactly the expected key sets.
    main_df = pd.read_csv(_GOLDEN / "main.csv", sep=";", dtype=str, keep_default_na=False)
    lookup_df = pd.read_csv(_GOLDEN / "lookup.csv", sep=";", dtype=str, keep_default_na=False)
    ref = match_phase_a(main_df, lookup_df, keys=["cc"])
    assert set(rr.outputs["out_matched"]["cc"]) == set(ref["matched"]["cc"]) == {"US", "UK"}
    assert set(rr.outputs["out_reject"]["cc"]) == set(ref["breaks"]["cc"]) == {"FR", "DE"}


def test_harness_fails_on_mutated_expected(java_bridge, tmp_path):
    """Corrupting the expected matched keys must make the harness FAIL (guards against false-green)."""
    job = _prepare(tmp_path)
    rr = run_job_capture(job, tmp_path)
    bad = _expected()
    bad["matched"].loc[0, "cc"] = "ZZ"  # corrupt expected -> harness must catch the mismatch
    output_map, keys = _output_map_and_keys()
    rep = check(rr, bad, output_map=output_map, keys=keys)
    assert rep["passed"] is False
    # Fail for the RIGHT reason: the corrupted 'matched' output diff -- not an
    # incidental engine error (the golden run itself is proven clean above).
    assert any("matched" in reason for reason in rep["reasons"]), rep["reasons"]
    assert rep["engine"]["status"] == "success"
