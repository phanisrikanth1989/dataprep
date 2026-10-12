"""Flow to iterate: a loop over the rows of a flow."""
import copy
import datetime
import json
import logging
import os
from decimal import Decimal
from pathlib import Path

import pytest

from src.v2 import load_job, run_job
from src.v2.components.iterate import flow_to_iterate
from src.v2.errors import JobRefusedError
from tests.v2.components.kit import columns, flow, job, reader, writer

from .test_file_actions_kit import filled

SAMPLE = Path(__file__).parents[2] / "talend_xml_samples" / "converted_jsons" / "Job_tFlowToIterate_0.1.json"
ROWS = "id:int, path:str, amount:Decimal#2, day:datetime@%Y-%m-%d"
DATA = b"1;a.csv;10.5;2024-01-31\n2;b.csv;;\n3;;7;2024-02-01\n"


def looping(kind="FlowToIterate", **config):
    return {"id": "each", "type": kind, "config": config, "inputs": ["row1"], "outputs": ["it"],
            "schema": {"input": columns(ROWS), "output": []}}


def looped(seen, kind="FlowToIterate", schema=ROWS, **config):
    """rows -> flow to iterate -iterate-> one row of what the pass has in globalMap -> seen.csv, which every pass adds to.

    `seen` is the globalMap keys the body writes down, one a column.
    """
    gen = {"id": "gen", "type": "FixedFlowInput", "inputs": [], "outputs": ["row2"],
           "config": {"nb_rows": 1, "values_config": [{"schema_column": f"c{at}", "value": f'globalMap.get("{key}")'}
                                                      for at, key in enumerate(seen)]},
           "schema": {"input": [], "output": [{"name": f"c{at}", "type": "str", "nullable": True} for at in range(len(seen))]}}
    out = writer(", ".join(f"c{at}:str" for at in range(len(seen))), path="seen.csv", inputs=("row2",), append=True,
                 include_header=False)
    made = job([reader(schema), looping(kind, **config), gen, out], [flow("row1", "in", "each"), flow("row2", "gen", "out")])
    made["flows"].append({"name": "it", "from": "each", "to": "gen", "type": "iterate"})
    return made


def ran(tmp_path, made, data=DATA, files=None):
    folder = filled(tmp_path, dict(files or {}, **{"in.csv": data}))
    previous = os.getcwd()
    os.chdir(folder)
    try:
        result = run_job(made)
    finally:
        os.chdir(previous)
    seen = folder / "seen.csv"
    return result, [tuple(line.split(";")) for line in seen.read_text().splitlines()] if seen.exists() else []


@pytest.fixture
def put_away(monkeypatch):
    """The scratch files of rows that were put away while the test ran, each removed as the component removes it."""
    gone, really = [], flow_to_iterate._removed
    monkeypatch.setattr(flow_to_iterate, "_removed", lambda path: (gone.append(path), really(path)))
    return gone


def refusals(made):
    with pytest.raises(JobRefusedError) as refused:
        load_job(made)
    return [(refusal.key, refusal.reason) for refusal in refused.value.report]


# ------------------------------------------------------------------
# A pass for each row
# ------------------------------------------------------------------

def test_pass_for_each_row_in_order_with_every_column_under_the_name_of_the_flow(tmp_path):
    result, rows = ran(tmp_path, looped(["row1.id", "row1.path", "row1.amount", "each_CURRENT_ITERATION"]))
    assert result.status == "success", result.error
    assert rows == [("1", "a.csv", "10.50", "1"), ("2", "b.csv", "", "2"), ("3", "", "7.00", "3")]
    assert result.summary()["loops"] == {"each": {"items": 3, "passes": 3}}
    assert result.global_map["each_NB_LINE"] == 3


def test_value_keeps_its_type_and_a_missing_one_is_nothing(tmp_path):
    result, _ = ran(tmp_path, looped(["row1.id"]), b"7;x.csv;1.5;2024-01-31\n")
    held = {key: value for key, value in result.global_map.items() if key.startswith("row1.")}
    assert held == {"row1.id": 7, "row1.path": "x.csv", "row1.amount": Decimal("1.50"),
                    "row1.day": datetime.datetime(2024, 1, 31)}
    result, _ = ran(tmp_path / "missing", looped(["row1.id"]), b"7;;;\n")
    assert (result.global_map["row1.amount"], result.global_map["row1.day"], result.global_map["row1.path"]) == (None, None, "")


def test_entries_the_job_names_itself_when_the_default_is_off(tmp_path):
    made = looped(["file", "n"], default_map=False, map_entries=[{"key": "file", "value": "path"}, {"key": "n", "value": "id"}])
    result, rows = ran(tmp_path, made)
    assert result.status == "success", result.error
    assert rows == [("a.csv", "1"), ("b.csv", "2"), ("", "3")]
    assert not [key for key in result.global_map if key.startswith("row1.")]


def test_no_row_no_pass(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="src.v2")
    result, rows = ran(tmp_path, looped(["row1.id"]), b"")
    assert result.status == "success" and rows == [] and result.global_map["each_NB_LINE"] == 0
    assert "[each] no item: what it leads to is not run" in [record.getMessage() for record in caplog.records]


def test_body_reads_the_file_a_row_names(tmp_path):
    body = [reader("n:int", component_id="one", path='{{java}}((String)globalMap.get("row1.path"))', outputs=("row2",)),
            writer("n:int", path="all.csv", inputs=("row2",), append=True, include_header=False)]
    made = job([reader(ROWS), looping(), *body], [flow("row1", "in", "each"), flow("row2", "one", "out")])
    made["flows"].append({"name": "it", "from": "each", "to": "one", "type": "iterate"})
    folder = filled(tmp_path, {"in.csv": b"1;a.csv;;\n2;b.csv;;\n", "a.csv": b"10\n11\n", "b.csv": b"20\n"})
    previous = os.getcwd()
    os.chdir(folder)
    try:
        result = run_job(made)
    finally:
        os.chdir(previous)
    assert result.status == "success", result.error
    assert (folder / "all.csv").read_bytes() == b"10\n11\n20\n" and result.rows["out"] == 3


def test_log_names_a_pass_by_the_number_of_its_row(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="src.v2")
    ran(tmp_path, looped(["row1.id"]))
    said = [record.getMessage() for record in caplog.records if record.getMessage().startswith("[each] item")]
    assert said == ["[each] item 1 of 3: row 1", "[each] item 2 of 3: row 2", "[each] item 3 of 3: row 3"]


# ------------------------------------------------------------------
# Many rows, and the scratch file they wait in
# ------------------------------------------------------------------

def test_rows_are_taken_from_their_scratch_file_a_piece_at_a_time_and_the_file_is_gone_afterwards(
        tmp_path, monkeypatch, put_away, caplog):
    caplog.set_level(logging.INFO, logger="src.v2")
    monkeypatch.setattr(flow_to_iterate, "_PIECE", 4)
    data = b"".join(b"%d;f%d.csv;;\n" % (number, number) for number in range(1, 12))
    result, rows = ran(tmp_path, looped(["row1.id", "row1.path"]), data)
    assert result.status == "success", result.error
    assert rows == [(str(number), f"f{number}.csv") for number in range(1, 12)]
    assert len(put_away) == 1 and not os.path.exists(put_away[0])
    assert "[each] item 11 of 11: row 11" in [record.getMessage() for record in caplog.records]


def test_row_is_taken_from_the_scratch_file_when_its_pass_is_due_and_not_before(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="src.v2")
    really = flow_to_iterate._rows

    def told(path, entries):
        for named, held in really(path, entries):
            logging.getLogger("src.v2").info(f"took {named}")
            yield named, held

    monkeypatch.setattr(flow_to_iterate, "_rows", told)
    ran(tmp_path, looped(["row1.id"]))
    said = [record.getMessage() for record in caplog.records if "row " in record.getMessage()]
    assert said == ["took row 1", "[each] item 1 of 3: row 1", "took row 2", "[each] item 2 of 3: row 2",
                    "took row 3", "[each] item 3 of 3: row 3"]


def test_scratch_file_is_gone_when_a_pass_fails_and_when_nothing_loops_over_the_rows(tmp_path, put_away):
    body = [reader("n:int", component_id="one", path='{{java}}((String)globalMap.get("row1.path"))', outputs=("row2",)),
            writer("n:int", path="all.csv", inputs=("row2",))]
    made = job([reader(ROWS), looping(), *body], [flow("row1", "in", "each"), flow("row2", "one", "out")])
    made["flows"].append({"name": "it", "from": "each", "to": "one", "type": "iterate"})
    result, _ = ran(tmp_path, made)
    assert result.status == "failed" and result.failures["each"].startswith("its loop stopped at item 1 of 3 (row 1): one failed: ")
    alone = job([reader(ROWS), looping()], [flow("row1", "in", "each")])
    result, _ = ran(tmp_path / "alone", alone)
    assert result.status == "success" and result.global_map["each_NB_LINE"] == 3
    assert len(put_away) == 2 and not [path for path in put_away if os.path.exists(path)]


def test_scratch_file_already_gone_when_the_loop_is_over_is_no_failure(tmp_path, monkeypatch):
    really, gone = flow_to_iterate._rows, []

    def taken_away(path, entries):
        yield from really(path, entries)
        os.remove(path)
        gone.append(path)

    monkeypatch.setattr(flow_to_iterate, "_rows", taken_away)
    result, rows = ran(tmp_path, looped(["row1.id"]))
    assert result.status == "success", result.error
    assert len(rows) == 3 and len(gone) == 1


def test_two_runs_at_once_in_one_process_do_not_share_a_scratch_file(tmp_path, put_away):
    ran(tmp_path / "one", looped(["row1.id"]))
    ran(tmp_path / "two", looped(["row1.id"]))
    assert len(set(put_away)) == 2


def test_more_rows_than_the_cap_fail_the_job_before_the_first_pass(tmp_path, put_away):
    result, rows = ran(tmp_path, looped(["row1.id"], max_items=2))
    assert (result.status, rows) == ("failed", [])
    assert result.error == "3 items, and a loop may have 2 by `max_items`: none is run"
    assert len(put_away) == 1 and not os.path.exists(put_away[0])


# ------------------------------------------------------------------
# A converted job, what is refused, and the names it goes by
# ------------------------------------------------------------------

def test_converted_sample_job_runs_once_its_java_is_written_in_python(tmp_path):
    made = copy.deepcopy(json.loads(SAMPLE.read_text()))
    by_id = {component["id"]: component for component in made["components"]}
    by_id["tFileInputDelimited_1"]["config"]["filepath"] = "input.txt"
    by_id["tFileOutputDelimited_1"]["config"]["filepath"] = "output.dat"
    for column in by_id["tMap_1"]["config"]["outputs"][0]["columns"]:
        # In Python: no mark, and no cast before a lookup.
        column["expression"] = column["expression"].replace("{{java}}", "").replace("(String)", "")
    header = int(by_id["tFileInputDelimited_1"]["config"].get("header_rows") or 0)
    listed = "filepath,filename,dept\n" * header + "one.csv,one,X\ntwo.csv,two,Y\n"
    folder = filled(tmp_path, {"input.txt": listed.encode(), "one.csv": b"id,name,dept,salary\n1,ann,X,10\n",
                               "two.csv": b"id,name,dept,salary\n2,bob,Y,20\n3,cy,Y,30\n"})
    previous = os.getcwd()
    os.chdir(folder)
    try:
        result = run_job(made)
    finally:
        os.chdir(previous)
    assert result.status == "success", result.error
    assert result.summary()["loops"] == {"tFlowToIterate_1": {"items": 2, "passes": 2}}
    assert result.rows["tFileOutputDelimited_1"] == 3


@pytest.mark.parametrize("config, said", [
    ({"default_map": False, "map_entries": [{"key": "k", "value": "nope"}]},
     "map_entries[0].value: there is no column 'nope'; the columns are: id, path, amount, day"),
    ({"default_map": False, "map_entries": []}, "map_entries: `default_map` is off and no entry is given: a pass would have nothing"),
    ({"default_map": False, "map_entries": [{"key": "", "value": "id"}]}, "map_entries[0].key: an entry of globalMap needs a name"),
    ({"nope": 1}, "nope: unknown config key"),
])
def test_what_cannot_be_done_refuses_the_job(config, said):
    assert [f"{key}: {reason}" for key, reason in refusals(looped(["x"], **config))] == [said]


def test_entry_for_a_column_the_flow_does_not_have_fails_the_run_where_no_column_is_declared(tmp_path, put_away):
    made = looped(["file"], default_map=False, map_entries=[{"key": "file", "value": "pth"}])
    made["components"][1]["schema"] = {"input": [], "output": []}
    result, rows = ran(tmp_path, made)
    assert (result.status, rows) == ("failed", [])
    assert result.failures["each"] == "map_entries: there is no column 'pth'; the columns are: id, path, amount, day"
    assert put_away == []


def test_no_flow_to_it_refuses_the_job():
    made = job([dict(looping(), inputs=[])], [])
    assert refusals(made) == [("inputs", "needs 1 input(s), but 0 flows arrive")]


def test_what_the_converter_writes_is_taken(tmp_path):
    made = looped(["row1.id"], kind="tFlowToIterate", default_map=True, map_entries=[], tstatcatcher_stats=False, label="x")
    result, rows = ran(tmp_path, made)
    assert result.status == "success" and [row[0] for row in rows] == ["1", "2", "3"]


@pytest.mark.parametrize("kind", ["flow_to_iterate", "FlowToIterate", "tFlowToIterate"])
def test_every_name_of_it(tmp_path, kind):
    result, rows = ran(tmp_path, looped(["row1.id"], kind=kind))
    assert result.status == "success" and len(rows) == 3
