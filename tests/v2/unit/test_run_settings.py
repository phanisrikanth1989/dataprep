"""How a job is run, said in its job config: the ``run`` block.

The block holds what the command line could say too. The command line (or
whoever calls ``run_job``) wins over the block, and the block over the
default.
"""
import json
import logging

import pytest

from src.v2 import load_job, run_job
from src.v2.cli import main
from src.v2.engine import logging_from
from src.v2.errors import ConfigurationError, JobRefusedError
from tests.v2.answer_key import run_v1
from tests.v2.components.kit import flow, job, reader, writer

from .test_cli import job_file, summary_of

IDS = "id:int, amount:int"
COUNTS = {"in": {"NB_LINE": 2, "NB_LINE_OK": 2, "NB_LINE_REJECT": 0},
          "out": {"NB_LINE": 2, "NB_LINE_OK": 2, "NB_LINE_REJECT": 0}}


def copying(tmp_path, **run):
    """file -> file with full paths, and a ``run`` block when anything is given for it."""
    (tmp_path / "in.csv").write_bytes(b"id;amount\n1;10\n2;20\n")
    made = job([reader(IDS, path=str(tmp_path / "in.csv"), header_rows=1),
                writer(IDS, path=str(tmp_path / "out.csv"), inputs=("row1",))], [flow("row1", "in", "out")])
    if run:
        made["run"] = run
    return made


def refusals(made, **kwargs):
    with pytest.raises(JobRefusedError) as caught:
        load_job(made, **kwargs) if not kwargs.get("run") else run_job(made, **kwargs)
    return [(refusal.key, refusal.reason) for refusal in caught.value.report]


# ------------------------------------------------------------------
# The block
# ------------------------------------------------------------------

def test_row_counts_can_be_asked_for_in_the_job_config(tmp_path):
    assert run_job(copying(tmp_path, row_counts=True)).counts == COUNTS
    assert run_job(copying(tmp_path)).counts == {}


def test_job_config_with_a_run_block_still_runs_on_v1(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_v1(copying(tmp_path, row_counts=True, log_level="DEBUG"))["out"]["NB_LINE"] == 2


def test_key_the_block_does_not_know_refuses_the_job(tmp_path):
    assert refusals(copying(tmp_path, loud=True)) == [("run.loud", "unknown config key")]


@pytest.mark.parametrize("setting, value, said", [
    ("row_counts", "yes", "expected true or false"),
    ("log_level", "LOUD", "is not a log level"),
    ("summary_file", 5, "expected text"),
    ("trace", "on", "expected true or false"),
])
def test_value_of_the_wrong_kind_refuses_the_job(tmp_path, setting, value, said):
    (key, reason), = refusals(copying(tmp_path, **{setting: value}))
    assert key == f"run.{setting}" and said in reason


def test_log_level_may_be_written_in_any_case(tmp_path):
    assert load_job(copying(tmp_path, log_level="debug")).run.log_level == "DEBUG"


def test_context_variable_is_not_read_in_a_run_setting(tmp_path):
    (key, reason), = refusals(copying(tmp_path, summary_file="${context.logs}/s.json"))
    assert key == "run.summary_file" and "context" in reason


# ------------------------------------------------------------------
# The caller of run_job wins over the block
# ------------------------------------------------------------------

def test_callers_settings_win_over_the_job_configs(tmp_path):
    assert run_job(copying(tmp_path, row_counts=False), run={"row_counts": True}).counts == COUNTS
    assert run_job(copying(tmp_path, row_counts=True), run={"row_counts": False}).counts == {}


def test_setting_the_caller_leaves_out_is_the_job_configs(tmp_path):
    assert run_job(copying(tmp_path, row_counts=True), run={"log_level": "INFO"}).counts == COUNTS
    assert run_job(copying(tmp_path, row_counts=True), run={}).counts == COUNTS


def test_row_counts_argument_still_works_and_wins(tmp_path):
    assert run_job(copying(tmp_path), row_counts=True).counts == COUNTS
    assert run_job(copying(tmp_path, row_counts=False), row_counts=True, run={"row_counts": False}).counts == COUNTS
    assert run_job(copying(tmp_path, row_counts=True), row_counts=False, run={"row_counts": True}).counts == {}


def test_key_the_caller_gives_that_is_not_known_refuses_the_job(tmp_path):
    assert refusals(copying(tmp_path), run={"loud": True}) == [("run.loud", "unknown config key")]


def test_run_settings_of_the_caller_that_are_no_object_refuse_the_job(tmp_path):
    assert refusals(copying(tmp_path), run="row_counts") == [("run", "expected an object, got 'row_counts'")]
    assert not (tmp_path / "out.csv").exists()


def test_log_level_is_in_force_while_the_job_runs_and_put_back_after(tmp_path, caplog):
    engine_log = logging.getLogger("src.v2")
    before = engine_log.level
    caplog.set_level(logging.DEBUG)
    engine_log.setLevel(logging.WARNING)
    try:
        run_job(copying(tmp_path, log_level="DEBUG"))
        assert any(record.levelno == logging.DEBUG and record.name.startswith("src.v2") for record in caplog.records)
        assert engine_log.level == logging.WARNING
        caplog.clear()
        run_job(copying(tmp_path))
        assert not any(record.name.startswith("src.v2") and record.levelno < logging.WARNING for record in caplog.records)
    finally:
        engine_log.setLevel(before)


def test_runs_at_once_share_the_lowest_level_and_leave_the_logger_as_it_was(tmp_path):
    engine_log = logging.getLogger("src.v2")
    before = engine_log.level
    first, second = logging_from("DEBUG"), logging_from("WARNING")
    first.__enter__()
    second.__enter__()
    assert engine_log.level == logging.DEBUG
    # The first to start is the first to end: the other's level is then in force, not the first one's.
    first.__exit__(None, None, None)
    assert engine_log.level == logging.WARNING
    second.__exit__(None, None, None)
    assert engine_log.level == before


def test_logger_is_put_back_when_what_ran_under_a_level_raises():
    engine_log = logging.getLogger("src.v2")
    before = engine_log.level
    with pytest.raises(RuntimeError):
        with logging_from("DEBUG"):
            raise RuntimeError("stopped")
    assert engine_log.level == before


def test_level_that_is_none_is_said_when_a_job_is_loaded_with_it(tmp_path):
    with pytest.raises(ConfigurationError, match="'LOUD' is not a log level"):
        load_job(copying(tmp_path), log_level="LOUD")


def with_a_routine(tmp_path, made):
    """A job config that loads one routine, which the engine says at INFO as it loads the job."""
    folder = tmp_path / "routines"
    folder.mkdir(exist_ok=True)
    (folder / "fees.py").write_text("def twice(value):\n    return value * 2\n")
    made["python_config"] = {"enabled": True, "routines_dir": str(folder)}
    return made


def test_job_configs_level_is_in_force_while_the_job_loads_too(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    run_job(with_a_routine(tmp_path, copying(tmp_path)))
    assert "Loaded routine Fees" in caplog.text
    caplog.clear()
    run_job(with_a_routine(tmp_path, copying(tmp_path, log_level="WARNING")))
    assert not [record for record in caplog.records if record.name.startswith("src.v2")]
    caplog.clear()
    # What the caller asks wins while the job loads as well.
    run_job(with_a_routine(tmp_path, copying(tmp_path, log_level="WARNING")), run={"log_level": "INFO"})
    assert "Loaded routine Fees" in caplog.text


def test_run_job_writes_the_summary_file_it_is_asked_for(tmp_path):
    target = tmp_path / "summary.json"
    result = run_job(copying(tmp_path, summary_file=str(target)))
    assert json.loads(target.read_text()) == result.summary()
    assert result.summary()["status"] == "success" and result.summary()["rows"] == {"out": 2}


def test_summary_file_that_cannot_be_opened_stops_run_job_before_the_job_runs(tmp_path):
    with pytest.raises(ConfigurationError, match="summary_file"):
        run_job(copying(tmp_path, summary_file=str(tmp_path / "no_such_folder" / "summary.json")))
    assert not (tmp_path / "out.csv").exists()


def test_summary_is_what_the_command_prints(tmp_path):
    assert sorted(run_job(copying(tmp_path)).summary()) == [
        "counts", "duration_s", "error", "failed_component", "failures", "job_name", "rows", "status",
    ]


def test_run_says_at_its_start_which_settings_are_on_and_who_asked(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="src.v2")
    run_job(copying(tmp_path, row_counts=True), run={"log_level": "INFO"})
    said = [record.getMessage() for record in caplog.records if "run settings" in record.getMessage()]
    assert said == ["[t] run settings: log level INFO (asked by the caller), row counts (job config)"]
    caplog.clear()
    run_job(copying(tmp_path))
    assert not [record for record in caplog.records if "run settings" in record.getMessage()]


# ------------------------------------------------------------------
# The command line wins over the block
# ------------------------------------------------------------------

def block(tmp_path, **run):
    return job_file(tmp_path, run=run)


def levels_of(standard_output):
    """The level of every log line on standard output."""
    return {line.split()[2] for line in standard_output.splitlines() if line[:4].isdigit() and " - " in line}


def test_command_reads_the_log_level_from_the_job_config(tmp_path, capsys):
    assert main([block(tmp_path, log_level="DEBUG")]) == 0
    assert "DEBUG" in levels_of(capsys.readouterr().out)
    assert main([block(tmp_path)]) == 0
    assert levels_of(capsys.readouterr().out) == {"INFO"}


def test_command_writes_from_the_job_configs_level_while_it_loads_the_job_too(tmp_path, capsys):
    def loading(**run):
        path = block(tmp_path, **run)
        made = with_a_routine(tmp_path, json.loads((tmp_path / "job.json").read_text()))
        (tmp_path / "job.json").write_text(json.dumps(made))
        return path

    assert main([loading()]) == 0
    assert "Loaded routine Fees" in capsys.readouterr().out
    assert main([loading(log_level="WARNING")]) == 0
    assert levels_of(capsys.readouterr().out) == set()
    assert main([loading(log_level="WARNING"), "--log-level", "INFO"]) == 0
    assert "Loaded routine Fees" in capsys.readouterr().out


def test_command_lines_log_level_wins(tmp_path, capsys):
    assert main([block(tmp_path, log_level="DEBUG"), "--log-level", "WARNING"]) == 0
    out = capsys.readouterr().out
    assert " DEBUG " not in out and " INFO " not in out and summary_of(out)["status"] == "success"


def test_command_reads_row_counts_from_the_job_config_and_can_turn_them_off(tmp_path, capsys):
    assert main([block(tmp_path, row_counts=True)]) == 0
    assert summary_of(capsys.readouterr().out)["counts"] != {}
    assert main([block(tmp_path, row_counts=True), "--no-row-counts"]) == 0
    assert summary_of(capsys.readouterr().out)["counts"] == {}


def test_command_writes_the_summary_file_the_job_config_names(tmp_path, capsys):
    target = tmp_path / "from_config.json"
    assert main([block(tmp_path, summary_file=str(target))]) == 0
    assert json.loads(target.read_text()) == summary_of(capsys.readouterr().out)


def test_command_lines_summary_file_wins(tmp_path, capsys):
    named, given = tmp_path / "from_config.json", tmp_path / "from_flag.json"
    assert main([block(tmp_path, summary_file=str(named)), "--summary", str(given)]) == 0
    assert given.exists() and not named.exists()


def test_command_line_that_names_no_summary_file_turns_off_the_job_configs(tmp_path, capsys):
    named = tmp_path / "from_config.json"
    assert main([block(tmp_path, summary_file=str(named), row_counts=True), "--summary", ""]) == 0
    assert not named.exists()
    said = [line.split(" - ", 1)[1] for line in capsys.readouterr().out.splitlines() if "run settings" in line]
    assert said == ["[cli] run settings: row counts (job config)"]


def test_summary_file_of_the_job_config_that_cannot_be_opened_is_said_as_such(tmp_path, capsys):
    assert main([block(tmp_path, summary_file=str(tmp_path / "no_such_folder" / "s.json"))]) == 2
    assert "run.summary_file" in capsys.readouterr().err


def test_command_says_which_settings_came_from_where(tmp_path, capsys):
    assert main([block(tmp_path, row_counts=True), "--log-level", "INFO"]) == 0
    assert "run settings: log level INFO (command line), row counts (job config)" in capsys.readouterr().out
