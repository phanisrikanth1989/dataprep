"""What the log says at DEBUG, and that saying it costs nothing at INFO."""
import json
import logging
import os

import polars as pl

from .kit import job, run


def debug_lines(caplog, job_config, level=logging.DEBUG, **kwargs):
    """Run a job; returns (the DEBUG lines it logged, how it ended)."""
    caplog.set_level(level, logger="src.v2")
    caplog.clear()
    result = run(job_config, **kwargs)
    return [record.getMessage() for record in caplog.records if record.levelno == logging.DEBUG], result


def added(tmp_path, source=None, **more):
    """rows -> add -> save, the rows read from a file when one is given."""
    reads = ("in", "from_file", {"path": source}) if source else ("in", "rows", {"data": {"n": [1, 2, 3]}})
    components = [reads, ("add", "add", {"amount": "${context.step}"}),
                  ("out", "save", {"path": str(tmp_path) + "/${context.name}"})]
    flows = [("r1", "in", "add", "flow"), ("r2", "add", "out", "flow")]
    return job(components, flows, context={"step": 5, "name": "o.csv"}, **more)


def test_debug_shows_the_config_of_each_component_with_context_values_put_in(caplog, tmp_path):
    lines, result = debug_lines(caplog, added(tmp_path))
    assert result.status == "success"
    assert '[add] config: {"amount": 5, "column": "n"}' in lines
    assert "[out] config: " + json.dumps({"path": str(tmp_path / "o.csv")}) in lines


def test_debug_shows_the_columns_each_component_hands_on_with_their_types(caplog, tmp_path):
    components = [("in", "rows", {"data": {"n": [1, 5], "name": ["a", "b"]}}), ("split", "split", {"limit": 2}),
                  ("out", "save", {"path": str(tmp_path / "o.csv")}), ("low", "save", {"path": str(tmp_path / "low.csv")})]
    flows = [("r1", "in", "split", "flow"), ("r2", "split", "out", "flow"), ("r3", "split", "low", "reject")]
    lines, result = debug_lines(caplog, job(components, flows))
    assert result.status == "success"
    assert "[in] output main: n Int64, name String" in lines
    assert "[split] output main: n Int64, name String" in lines
    assert "[split] output reject: n Int64, name String" in lines
    assert not [line for line in lines if line.startswith("[out] output")]


def test_debug_shows_the_plan_polars_is_given_for_each_output(caplog, tmp_path):
    source = tmp_path / "in.csv"
    source.write_text("n\n1\n2\n")
    lines, result = debug_lines(caplog, added(tmp_path, source=str(source)))
    assert result.status == "success"
    (plan,) = [line for line in lines if line.startswith("[t] plan of output out:\n")]
    # The whole plan, down to the file it starts from, on lines of its own.
    assert str(source) in plan and len(plan.splitlines()) > 3


def test_debug_shows_the_plan_of_what_a_component_asked_to_know(caplog, tmp_path):
    components = [("in", "rows", {"data": {"n": [1, 2]}}), ("guard", "guard", {}),
                  ("out", "save", {"path": str(tmp_path / "o.csv")})]
    flows = [("r1", "in", "guard", "flow"), ("r2", "guard", "out", "flow")]
    lines, _ = debug_lines(caplog, job(components, flows))
    assert len([line for line in lines if line.startswith("[t] plan of what guard asked to know:\n")]) == 1


def test_debug_shows_the_plan_of_the_rows_a_component_is_handed(caplog, tmp_path):
    components = [("in", "rows", {"data": {"n": [1, 2]}}), ("peek", "peek", {}),
                  ("out", "save", {"path": str(tmp_path / "o.csv")})]
    flows = [("r1", "in", "peek", "flow"), ("r2", "peek", "out", "flow")]
    lines, _ = debug_lines(caplog, job(components, flows))
    assert len([line for line in lines if line.startswith("[t] plan of the rows peek is handed:\n")]) == 1


def test_debug_shows_the_temporary_file_each_output_is_written_to(caplog, tmp_path):
    lines, result = debug_lines(caplog, added(tmp_path))
    assert result.status == "success"
    (line,) = [line for line in lines if line.startswith("[out] writing to the temporary file ")]
    temp = line.removeprefix("[out] writing to the temporary file ")
    assert os.path.dirname(temp) == str(tmp_path) and os.path.basename(temp).startswith(".o.csv.out.v2tmp")
    assert not os.path.exists(temp)


def test_debug_says_whether_a_subjob_may_be_read_a_second_time_and_why(caplog, tmp_path, monkeypatch):
    monkeypatch.delenv("V2_SAFE_READ", raising=False)
    lines, _ = debug_lines(caplog, added(tmp_path))
    assert ("[t] sources may let Polars parse numbers itself in this subjob: "
            "nothing in it needs rows in hand, so it can be read a second time") in lines

    components = [("in", "rows", {"data": {"n": [1, 2]}}), ("peek", "peek", {}),
                  ("out", "save", {"path": str(tmp_path / "p.csv")})]
    flows = [("r1", "in", "peek", "flow"), ("r2", "peek", "out", "flow")]
    lines, _ = debug_lines(caplog, job(components, flows))
    assert ("[t] sources read every column as text in this subjob: "
            "peek may need rows in hand, so the subjob cannot be read a second time") in lines

    monkeypatch.setenv("V2_SAFE_READ", "1")
    lines, _ = debug_lines(caplog, added(tmp_path))
    assert "[t] sources read every column as text in this subjob: V2_SAFE_READ is set" in lines


def test_debug_lines_are_plain_ascii(caplog, tmp_path):
    components = [("in", "rows", {"data": {"café": [1], "n": [2]}}), ("add", "add", {}),
                  ("out", "save", {"path": str(tmp_path / "o.csv")})]
    flows = [("r1", "in", "add", "flow"), ("r2", "add", "out", "flow")]
    lines, result = debug_lines(caplog, job(components, flows))
    assert result.status == "success"
    assert any("caf\\xe9" in line for line in lines)
    assert [line for line in lines if not line.isascii()] == []


def test_debug_lines_are_plain_ascii_whatever_the_names_and_paths_hold(caplog, tmp_path):
    folder = tmp_path / "caf\u00e9"
    folder.mkdir()
    components = [("in", "rows", {"data": {"n": [1]}}), ("s\u00fcd", "add", {}),
                  ("out", "save", {"path": str(folder / "o.csv")})]
    flows = [("r1", "in", "s\u00fcd", "flow"), ("r2", "s\u00fcd", "out", "flow")]
    lines, result = debug_lines(caplog, job(components, flows))
    assert result.status == "success"
    assert any("writing to the temporary file" in line and "caf\\xe9" in line for line in lines)
    assert any(line.startswith("[s\\xfcd] config: ") for line in lines)
    assert [line for line in lines if not line.isascii()] == []


def test_plan_polars_cannot_print_does_not_fail_the_job(caplog, tmp_path, monkeypatch):
    def refuse(frame, *args, **kwargs):
        raise RuntimeError("no plan for you")

    monkeypatch.setattr(pl.LazyFrame, "explain", refuse)
    lines, result = debug_lines(caplog, added(tmp_path))
    assert result.status == "success"
    assert "[t] plan of output out: Polars could not print it (no plan for you)" in lines


def test_nothing_is_put_together_for_debug_lines_when_the_level_is_info(caplog, tmp_path, monkeypatch):
    from src.v2.engine import runner

    asked = []

    def spied(real, name):
        def spy(*args, **kwargs):
            asked.append(name)
            return real(*args, **kwargs)
        return spy

    # What a debug line is made with: Polars printing a plan, a config as JSON, text made plain ASCII.
    monkeypatch.setattr(pl.LazyFrame, "explain", spied(pl.LazyFrame.explain, "plan"))
    monkeypatch.setattr(runner.json, "dumps", spied(runner.json.dumps, "config"))
    monkeypatch.setattr(runner, "ascii_only", spied(runner.ascii_only, "text"))
    lines, result = debug_lines(caplog, added(tmp_path), level=logging.INFO)
    assert result.status == "success" and lines == [] and asked == []
    # The same run at DEBUG does all three: the spies see what INFO was spared.
    lines, _ = debug_lines(caplog, added(tmp_path))
    assert lines and {"plan", "config", "text"} <= set(asked)
