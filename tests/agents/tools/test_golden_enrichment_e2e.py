"""Live-bridge end-to-end for the golden ENRICHMENT job.

Runs the committed golden job
(``tests/fixtures/recon/golden_enrichment/job.json``) through the real engine +
live Java bridge via ``run_job_capture`` and asserts the parity harness
(``check``) PASSES on the golden and FAILS on a mutated expectation. The golden
is a two-source tMap LEFT_OUTER_JOIN enrichment: the driving ``source`` rows are
each augmented with the lookup ``name`` column; ALL source rows survive, and a
row with no lookup match (``FR``/``DE``) keeps a null (empty) ``name`` -- there
is NO reject/break output. A ``ConvertType`` casts ``amt`` from string to numeric
(``"10.50"`` -> ``"10.5"``) and a ``SortRow`` orders the output by ``cc``.

The ``enriched_expected.csv`` was engine-captured (run once over the live bridge,
then frozen byte-for-byte from the produced file -- see the fixture
``README.md``); it is not hand-authored.

Marked ``@pytest.mark.java``: it needs a real JVM. The session ``java_bridge``
fixture (re-exported via this package's ``conftest.py``) skips the test when the
JAR/JVM is unavailable; where the coverage gate runs (JVM present) it MUST pass.
"""
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from agents.tools.run_and_validate import check, run_job_capture

pytestmark = [pytest.mark.java, pytest.mark.integration]

# tests/agents/tools/<this file> -> parents[3] is the repo root.
_GOLDEN = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "recon" / "golden_enrichment"


def _manifest_outputs() -> dict:
    return json.loads((_GOLDEN / "manifest.json").read_text(encoding="utf-8"))["outputs"]


def _prepare(tmp_path: Path) -> dict:
    """Copy the golden inputs into tmp and rewrite every input+output filepath onto tmp."""
    for f in ("source.csv", "lookup.csv"):
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
    """Harness PASSES on the golden, and the engine output shows the enrichment semantics."""
    job = _prepare(tmp_path)
    rr = run_job_capture(job, tmp_path)
    output_map, keys = _output_map_and_keys()
    rep = check(rr, _expected(), output_map=output_map, keys=keys)
    assert rep["passed"] is True, rep["reasons"]

    # Enrichment semantics on the live-captured output (read back as strings):
    #  - ALL source rows survive the LEFT-join enrichment (nothing dropped/rejected),
    #  - the output is sorted by the key (SortRow),
    #  - the lookup 'name' column is ADDED: matched rows enriched, unmatched carry
    #    an empty name (null lookup columns -- NOT a break/reject),
    #  - ConvertType cast 'amt' from string to numeric ("10.50" -> "10.5").
    enriched = rr.outputs["out_enriched"]
    assert enriched["cc"].tolist() == ["DE", "FR", "UK", "US"]  # kept-all + sorted asc
    name_by_cc = dict(zip(enriched["cc"], enriched["name"]))
    assert name_by_cc["US"] == "United States"
    assert name_by_cc["UK"] == "United Kingdom"
    assert name_by_cc["FR"] == "" and name_by_cc["DE"] == ""  # unmatched -> null enrichment
    amt_by_cc = dict(zip(enriched["cc"], enriched["amt"]))
    assert amt_by_cc["US"] == "10.5" and amt_by_cc["DE"] == "40.0"  # str -> numeric cast


def test_harness_fails_on_mutated_expected(java_bridge, tmp_path):
    """Corrupting the expected enrichment must make the harness FAIL (guards against false-green)."""
    job = _prepare(tmp_path)
    rr = run_job_capture(job, tmp_path)
    bad = _expected()
    bad["enriched"].loc[0, "name"] = "CORRUPT"  # corrupt expected -> harness must catch the mismatch
    output_map, keys = _output_map_and_keys()
    rep = check(rr, bad, output_map=output_map, keys=keys)
    assert rep["passed"] is False
    # Fail for the RIGHT reason: the corrupted 'enriched' output diff -- not an
    # incidental engine error (the golden run itself is proven clean above).
    assert any("enriched" in reason for reason in rep["reasons"]), rep["reasons"]
    assert rep["engine"]["status"] == "success"
