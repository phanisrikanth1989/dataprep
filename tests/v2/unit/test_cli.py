"""The command line: python -m src.v2 job.json [--context_param K=V] [--check]."""
import json

import pytest

from src.v2.cli import main


def job_file(tmp_path, **changes):
    made = {
        "job_name": "cli",
        "context": {"Default": {"sep": {"value": ";", "type": "str"}, "out": {"value": "out.csv", "type": "str"}}},
        "components": [
            {"id": "in", "type": "FileInputDelimited",
             "config": {"filepath": str(tmp_path / "in.csv"), "fieldseparator": "context.sep", "encoding": "UTF-8"},
             "schema": {"output": [{"name": "a", "type": "int"}, {"name": "b", "type": "str"}]}},
            {"id": "out", "type": "FileOutputDelimited",
             "config": {"filepath": str(tmp_path) + "/${context.out}", "encoding": "UTF-8", "file_exist_exception": False}},
        ],
        "flows": [{"name": "row1", "from": "in", "to": "out", "type": "flow"}],
    }
    made.update(changes)
    path = tmp_path / "job.json"
    path.write_text(json.dumps(made))
    (tmp_path / "in.csv").write_text("1;x\n2;y\n")
    return str(path)


def test_job_that_finishes_exits_zero_and_prints_a_summary(tmp_path, capsys):
    assert main([job_file(tmp_path)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "success" and summary["rows"] == {"out": 2}
    assert (tmp_path / "out.csv").read_text() == "1;x\n2;y\n"


def test_context_values_can_be_given_on_the_command_line(tmp_path):
    assert main([job_file(tmp_path), "--context_param", "out=other.csv", "--context_param", " sep = ; "]) == 0
    assert (tmp_path / "other.csv").exists()


def test_job_that_fails_exits_one(tmp_path, capsys):
    path = job_file(tmp_path)
    (tmp_path / "in.csv").unlink()
    assert main([path]) == 1
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "failed" and summary["failed_component"] == "in"


def test_job_v2_will_not_run_exits_two_and_prints_the_refusal_report(tmp_path, capsys):
    path = job_file(tmp_path, flows=[{"name": "row1", "from": "in", "to": "nowhere", "type": "flow"}])
    assert main([path]) == 2
    captured = capsys.readouterr()
    assert "cannot run on v2" in captured.err and "nowhere" in captured.err
    assert not (tmp_path / "out.csv").exists()


def test_check_only_loads_the_job(tmp_path, capsys):
    assert main([job_file(tmp_path), "--check"]) == 0
    assert "nothing refused" in capsys.readouterr().out
    assert not (tmp_path / "out.csv").exists()


@pytest.mark.parametrize("argument", ["no_equals_sign", "=value"])
def test_malformed_context_value_exits_two(tmp_path, capsys, argument):
    assert main([job_file(tmp_path), "--context_param", argument]) == 2
    assert "KEY=VALUE" in capsys.readouterr().err


def test_job_file_that_is_not_there_exits_two(tmp_path, capsys):
    assert main([str(tmp_path / "nope.json")]) == 2
    assert "nope.json" in capsys.readouterr().err


def test_unknown_log_level_is_a_usage_error(tmp_path, capsys):
    assert main([job_file(tmp_path), "--log-level", "loud"]) == 2
    assert "LOUD" in capsys.readouterr().err.upper()


@pytest.mark.parametrize("content", ["[]", '"a job"', "7", "null"])
def test_job_config_that_is_not_an_object_is_refused(tmp_path, capsys, content):
    path = tmp_path / "job.json"
    path.write_text(content)
    assert main([str(path)]) == 2
    assert "expected an object" in capsys.readouterr().err
