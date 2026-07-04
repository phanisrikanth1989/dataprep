import json

import pytest

from agents.tools.render_skills import render_config_reference, render_landmines, write_skill
from agents.tools.validate_agents import validate_skill


def test_config_reference_resolves_enum_refs_not_pointers():
    md = render_config_reference()
    assert "FilterRows" in md
    assert "IS_NULL" in md and "==" in md          # live _OPERATOR_MAP values, resolved
    assert "_OPERATOR_MAP" not in md               # the pointer must NOT leak into the skill


def test_landmines_rendered():
    md = render_landmines()
    assert "tmap-operator-noop" in md and "die-on-error-dual-default" in md


def test_write_skill_produces_valid_skill(tmp_path):
    root = tmp_path / "dataprep-recon"
    write_skill(str(root))
    skill_md = (root / "SKILL.md").read_text(encoding="utf-8")
    assert validate_skill(skill_md, "dataprep-recon") == []
    assert (root / "config-reference.md").exists()
    assert (root / "job-envelope.md").exists()


def test_job_envelope_has_json_example():
    from agents.tools.render_skills import render_job_envelope
    md = render_job_envelope()
    assert "```json" in md and '"subjob_id"' in md and '"type": "flow"' in md


def test_keep_enum_renders_json_false():
    from agents.tools.render_skills import render_config_reference
    md = render_config_reference()
    assert "false" in md                     # UniqueRow keep enum includes JSON false
    assert "one of first, last, False" not in md   # not Python False (adjust to your exact separator)


def test_job_envelope_example_carries_java_config():
    """The taught tMap example MUST carry java_config.enabled=true; without it the
    Map component crashes at run time ('NoneType'...compile_tmap_script). Parse the
    example as real JSON (not a string match) so a dropped java_config fails CI."""
    from agents.tools.render_skills import _JOB_ENVELOPE_EXAMPLE_JSON
    payload = json.loads(_JOB_ENVELOPE_EXAMPLE_JSON)          # must be valid JSON
    assert payload["java_config"]["enabled"] is True
    # tMap expressions carry the {{java}} marker (so a dropped block raises the friendly error)
    join = next(c for c in payload["components"] if c["type"] == "Map")
    assert all("{{java}}" in col["expression"]
               for col in join["config"]["outputs"][0]["columns"])


@pytest.mark.java
def test_job_envelope_example_runs_on_real_engine(java_bridge, tmp_path):
    """The taught tMap example must actually RUN through the real engine + live bridge --
    the string-match test above never exercised it, which is how the missing java_config
    (a hard runtime crash) went unnoticed."""
    from agents.tools.render_skills import _JOB_ENVELOPE_EXAMPLE_JSON
    from agents.tools.run_and_validate import run_job_capture
    (tmp_path / "source.csv").write_text("cc\nUS\nFR\n", encoding="utf-8")
    (tmp_path / "countries.csv").write_text("cc;country_name\nUS;United States\n", encoding="utf-8")
    job = json.loads(_JOB_ENVELOPE_EXAMPLE_JSON)
    rr = run_job_capture(job, tmp_path)
    assert rr.status == "success", rr.error
    enriched = rr.outputs["out_enriched"]
    name_by_cc = dict(zip(enriched["cc"], enriched["country_name"]))
    assert name_by_cc["US"] == "United States"   # matched -> lookup column added
    assert name_by_cc["FR"] == ""                 # unmatched source row KEPT (LEFT join), null enrichment
