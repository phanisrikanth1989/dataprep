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
