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
    assert out["curated"] is True   # curated type was strictly checked


def test_cli_uncurated_type_reports_curated_false(tmp_path, capsys):
    # A real but non-curated component: advisory only -> valid, but curated=False
    # so the agent knows it was NOT strictly checked.
    # (tPython/PythonComponent is registered but intentionally has no curated schema.)
    cfg = _write(tmp_path, {"python_code": "df['x']=1", "anything": 2})
    rc = vc.main(["--type", "tPython", "--config", cfg])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["valid"] is True and out["errors"] == []
    assert out["curated"] is False


def test_cli_invalid_reports_errors_exit_one(tmp_path, capsys):
    cfg = _write(tmp_path, {"bogus_key": 1, "conditions": []})
    rc = vc.main(["--type", "FilterRows", "--config", cfg])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1 and out["valid"] is False and any("bogus_key" in e for e in out["errors"])


def test_non_dict_config_returns_two_no_crash(tmp_path, capsys):
    import json
    p = tmp_path / "cfg.json"; p.write_text(json.dumps([1, 2, 3]))
    rc = vc.main(["--type", "FilterRows", "--config", str(p)])   # must NOT raise
    assert rc == 2


def test_missing_config_file_returns_two(tmp_path):
    rc = vc.main(["--type", "FilterRows", "--config", str(tmp_path / "nope.json")])
    assert rc == 2


def test_loose_skips_unknown_key(tmp_path, capsys):
    import json
    p = tmp_path / "cfg.json"; p.write_text(json.dumps({"bogus_key": 1, "conditions": []}))
    rc = vc.main(["--type", "FilterRows", "--config", str(p), "--loose"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["valid"] is True
