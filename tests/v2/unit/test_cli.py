"""The command line: python -m src.v2 job.json [--context_param K=V] [--check]."""
import json
import logging

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


def summary_of(standard_output):
    """The JSON summary: the last thing on standard output, after the log lines."""
    lines = standard_output.splitlines()
    start = max(index for index, line in enumerate(lines) if line == "{")
    return json.loads("\n".join(lines[start:]))


def missing_file_job(tmp_path):
    """A job that finishes with a warning: a positional reader whose file is not there reads no rows."""
    made = {
        "job_name": "warned",
        "components": [
            {"id": "in", "type": "FileInputPositional",
             "config": {"filepath": str(tmp_path / "not_there.txt"), "pattern": "3,3", "encoding": "UTF-8"},
             "schema": {"output": [{"name": "a", "type": "str"}, {"name": "b", "type": "str"}]}},
            {"id": "out", "type": "FileOutputDelimited",
             "config": {"filepath": str(tmp_path / "out.csv"), "encoding": "UTF-8", "file_exist_exception": False}},
        ],
        "flows": [{"name": "row1", "from": "in", "to": "out", "type": "flow"}],
    }
    path = tmp_path / "warned.json"
    path.write_text(json.dumps(made))
    return str(path)


def test_job_that_finishes_exits_zero_and_prints_a_summary(tmp_path, capsys):
    assert main([job_file(tmp_path)]) == 0
    summary = summary_of(capsys.readouterr().out)
    assert summary["status"] == "success" and summary["rows"] == {"out": 2}
    assert (tmp_path / "out.csv").read_text() == "1;x\n2;y\n"


# ------------------------------------------------------------------
# Where the log goes
# ------------------------------------------------------------------

def test_log_lines_go_to_standard_output_with_the_summary_last(tmp_path, capsys):
    assert main([job_file(tmp_path)]) == 0
    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    logged = [line for line in lines if " INFO src.v2.engine.runner - " in line]
    assert any("[cli] starting" in line for line in logged) and any("[cli] success" in line for line in logged)
    # Nothing follows the summary: it starts after the last log line and ends the output.
    assert lines.index("{") > lines.index(logged[-1]) and lines[-1] == "}"


def test_clean_run_leaves_standard_error_empty(tmp_path, capsys):
    assert main([job_file(tmp_path)]) == 0
    assert capsys.readouterr().err == ""


def test_errors_go_to_standard_error(tmp_path, capsys):
    path = job_file(tmp_path)
    (tmp_path / "in.csv").unlink()
    assert main([path]) == 1
    captured = capsys.readouterr()
    assert " ERROR src.v2.engine.runner - [cli] failed at in" in captured.err
    assert "failed at in" not in captured.out
    assert summary_of(captured.out)["status"] == "failed"


def test_warnings_go_to_standard_error_also_when_the_job_finishes(tmp_path, capsys):
    assert main([missing_file_job(tmp_path)]) == 0
    captured = capsys.readouterr()
    assert " WARNING " in captured.err and "input file not found" in captured.err
    assert "input file not found" not in captured.out
    assert "[warned] starting" in captured.out and "[warned] starting" not in captured.err


def test_log_level_decides_which_lines_are_written(tmp_path, capsys):
    assert main([job_file(tmp_path), "--log-level", "warning"]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["status"] == "success"
    assert captured.err == ""


def test_command_leaves_logging_as_it_found_it(tmp_path, capsys):
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    assert main([job_file(tmp_path)]) == 0
    assert root.handlers == handlers and root.level == level
    # A second run in the same process writes each line once.
    capsys.readouterr()
    assert main([job_file(tmp_path)]) == 0
    assert capsys.readouterr().out.count("[cli] starting") == 1


# ------------------------------------------------------------------
# The summary in a file
# ------------------------------------------------------------------

def test_summary_is_written_to_a_file_as_well_when_asked(tmp_path, capsys):
    target = tmp_path / "run.json"
    assert main([job_file(tmp_path), "--summary", str(target)]) == 0
    written = json.loads(target.read_text())
    assert written == summary_of(capsys.readouterr().out)
    assert written["status"] == "success" and written["rows"] == {"out": 2}


def test_summary_file_of_a_job_that_failed_says_so(tmp_path):
    path, target = job_file(tmp_path), tmp_path / "run.json"
    (tmp_path / "in.csv").unlink()
    assert main([path, "--summary", str(target)]) == 1
    written = json.loads(target.read_text())
    assert written["status"] == "failed" and written["failed_component"] == "in"


def test_summary_file_that_cannot_be_written_stops_the_command_before_the_job_runs(tmp_path, capsys):
    target = tmp_path / "no_such_folder" / "run.json"
    assert main([job_file(tmp_path), "--summary", str(target)]) == 2
    assert "--summary" in capsys.readouterr().err
    assert not (tmp_path / "out.csv").exists()


def test_job_that_was_not_run_leaves_the_summary_file_alone(tmp_path):
    target = tmp_path / "run.json"
    target.write_text("from an earlier run")
    path = job_file(tmp_path, flows=[{"name": "row1", "from": "in", "to": "nowhere", "type": "flow"}])
    assert main([path, "--summary", str(target)]) == 2
    assert main([job_file(tmp_path), "--check", "--summary", str(target)]) == 0
    assert target.read_text() == "from an earlier run"


def test_context_values_can_be_given_on_the_command_line(tmp_path):
    assert main([job_file(tmp_path), "--context_param", "out=other.csv", "--context_param", " sep = ; "]) == 0
    assert (tmp_path / "other.csv").exists()


def test_job_that_fails_exits_one(tmp_path, capsys):
    path = job_file(tmp_path)
    (tmp_path / "in.csv").unlink()
    assert main([path]) == 1
    summary = summary_of(capsys.readouterr().out)
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
