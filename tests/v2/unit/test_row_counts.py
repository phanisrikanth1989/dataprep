"""Row counts of every component, taken when a run asks for them."""
import logging

import polars as pl

from src.v2.components.base import Source
from src.v2.job.keys import Key

from .kit import REGISTRY, job, lines, run


class Padded(Source):
    """Rows written in the config with one more row put after them, less the first few of the lot."""

    names = ("padded",)
    keys = (Key("data", type=dict, required=True), Key("skip", type=int, default=0))

    def read(self):
        both = pl.concat([pl.LazyFrame(self.config["data"]), pl.LazyFrame({"n": [0]})])
        return {"main": both.slice(self.config["skip"], None)}


REGISTRY.register(Padded)


def split_job(tmp_path):
    """Four rows; two leave the split by main and are written, two by reject and are written elsewhere."""
    components = [("in", "rows", {"data": {"n": [1, 5, 2, 9]}}), ("split", "split", {"limit": 2}),
                  ("kept", "save", {"path": str(tmp_path / "kept.csv")}),
                  ("low", "save", {"path": str(tmp_path / "low.csv")})]
    flows = [("r1", "in", "split", "flow"), ("r2", "split", "kept", "flow"), ("r3", "split", "low", "reject")]
    return job(components, flows)


def counts(line, ok, reject):
    return {"NB_LINE": line, "NB_LINE_OK": ok, "NB_LINE_REJECT": reject}


COUNTED = {"in": counts(4, 4, 0), "split": counts(4, 2, 2), "kept": counts(2, 2, 0), "low": counts(2, 2, 0)}


def count_lines(caplog):
    return [record.getMessage() for record in caplog.records
            if record.levelno == logging.INFO and " NB_LINE:" in record.getMessage()]


def test_run_that_asks_for_row_counts_counts_every_component(tmp_path):
    result = run(split_job(tmp_path), row_counts=True)
    assert result.status == "success"
    assert result.counts == COUNTED


def test_row_counts_asked_for_are_in_global_map_as_well(tmp_path):
    result = run(split_job(tmp_path), row_counts=True)
    for component_id, counted in COUNTED.items():
        for stat, rows in counted.items():
            assert result.global_map[f"{component_id}_{stat}"] == rows


def test_each_component_has_a_line_with_its_counts_once_its_subjob_has_finished(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="src.v2")
    run(split_job(tmp_path), row_counts=True)
    assert count_lines(caplog) == [
        "[in] NB_LINE:4 OK:4 REJECT:0",
        "[split] NB_LINE:4 OK:2 REJECT:2",
        "[kept] NB_LINE:2 OK:2 REJECT:0",
        "[low] NB_LINE:2 OK:2 REJECT:0",
    ]
    said = [record.getMessage() for record in caplog.records]
    assert said.index("[low] wrote 2 row(s) to " + str(tmp_path / "low.csv")) < said.index("[in] NB_LINE:4 OK:4 REJECT:0")


def test_run_that_does_not_ask_counts_nothing_more_than_before(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="src.v2")
    result = run(split_job(tmp_path))
    assert result.status == "success"
    assert result.counts == {} and count_lines(caplog) == []
    assert result.global_map == {"kept_NB_LINE": 2, "low_NB_LINE": 2}


def test_asking_for_row_counts_changes_nothing_that_is_written(tmp_path):
    (tmp_path / "plain").mkdir()
    (tmp_path / "counted").mkdir()
    run(split_job(tmp_path / "plain"))
    run(split_job(tmp_path / "counted"), row_counts=True)
    for name in ("kept.csv", "low.csv"):
        assert lines(tmp_path / "counted" / name) == lines(tmp_path / "plain" / name)


def test_components_of_every_subjob_that_ran_are_counted(tmp_path):
    components = [("a", "rows", {"data": {"n": [1, 2, 3]}}), ("a_out", "save", {"path": str(tmp_path / "a.csv")}),
                  ("b", "rows", {"data": {"n": [7]}}), ("b_out", "save", {"path": str(tmp_path / "b.csv")}),
                  ("never", "rows", {"data": {"n": [0]}}), ("never_out", "save", {"path": str(tmp_path / "n.csv")})]
    flows = [("r1", "a", "a_out", "flow"), ("r2", "b", "b_out", "flow"), ("r3", "never", "never_out", "flow")]
    triggers = [{"type": "OnSubjobOk", "from": "a", "to": "b"},
                {"type": "RunIf", "from": "a", "to": "never", "condition": "false"}]
    result = run(job(components, flows, triggers=triggers), row_counts=True)
    assert result.status == "success"
    assert result.counts == {"a": counts(3, 3, 0), "a_out": counts(3, 3, 0), "b": counts(1, 1, 0), "b_out": counts(1, 1, 0)}


def test_subjob_that_failed_has_no_row_counts(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="src.v2")
    components = [("in", "rows", {"data": {"n": [1, -2]}}), ("guard", "guard", {}),
                  ("out", "save", {"path": str(tmp_path / "o.csv")}),
                  ("fine", "rows", {"data": {"n": [1]}}), ("fine_out", "save", {"path": str(tmp_path / "f.csv")})]
    flows = [("r1", "in", "guard", "flow"), ("r2", "guard", "out", "flow"), ("r3", "fine", "fine_out", "flow")]
    result = run(job(components, flows), row_counts=True)
    assert result.status == "failed" and result.failed_component == "guard"
    assert result.counts == {"fine": counts(1, 1, 0), "fine_out": counts(1, 1, 0)}
    assert count_lines(caplog) == ["[fine] NB_LINE:1 OK:1 REJECT:0", "[fine_out] NB_LINE:1 OK:1 REJECT:0"]


def test_component_that_is_handed_rows_is_counted_too(tmp_path):
    components = [("in", "rows", {"data": {"n": [1, 2, 3]}}), ("peek", "peek", {}),
                  ("out", "save", {"path": str(tmp_path / "o.csv")})]
    flows = [("r1", "in", "peek", "flow"), ("r2", "peek", "out", "flow")]
    result = run(job(components, flows), row_counts=True)
    assert result.counts == {"in": counts(3, 3, 0), "peek": counts(3, 3, 0), "out": counts(3, 3, 0)}


def test_rows_cut_from_the_front_of_two_frames_put_together_are_counted_right(tmp_path):
    # Polars 1.44 gets the number of such rows wrong when asked for it outright: it counts each frame
    # on its own and then cuts the list of counts. The engine's count must not be taken in by that.
    components = [("in", "padded", {"data": {"n": [1, 2, 3, 4]}, "skip": 2}),
                  ("out", "save", {"path": str(tmp_path / "o.csv")})]
    result = run(job(components, [("r1", "in", "out", "flow")]), row_counts=True)
    assert result.status == "success" and lines(tmp_path / "o.csv") == ["n", "3", "4", "0"]
    assert result.counts == {"in": counts(3, 3, 0), "out": counts(3, 3, 0)}
