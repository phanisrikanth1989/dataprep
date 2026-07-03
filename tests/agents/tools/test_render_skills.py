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
