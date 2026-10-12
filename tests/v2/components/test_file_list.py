"""File list: a loop over the files of a folder."""
import copy
import json
import logging
import os
import time
from pathlib import Path

import pytest

from src.v2 import load_job, run_job
from src.v2.components.file.file_list import pattern_of
from src.v2.errors import JobRefusedError
from tests.v2.components.kit import flow, job, writer

from .test_file_actions_kit import filled

SAMPLE = Path(__file__).parents[2] / "talend_xml_samples" / "converted_jsons" / "Job_tFileList_0.1.json"
LONG_AGO = 1_700_000_000
FILES = {"in/b.txt": b"bb", "in/a.csv": b"a", "in/c.CSV": b"ccc", "in/.hidden.csv": b"h", "in/empty/": None,
         "in/sub/d.csv": b"dddd", "in/sub/deep/e.csv": b"e", "in/.dot/f.csv": b"f"}
SEEN = ("CURRENT_FILE", "CURRENT_FILEPATH", "CURRENT_FILEDIRECTORY", "CURRENT_FILEEXTENSION", "NB_FILE")


def file_list(kind="FileList", **config):
    return {"id": "list", "type": kind, "config": config, "inputs": [], "outputs": ["it"],
            "schema": {"input": [], "output": []}}


def listing(kind="FileList", **config):
    """file list -iterate-> one row of what the pass has in globalMap -> seen.csv, which every pass adds to."""
    columns = ", ".join(f"{name}:str" for name in SEEN)
    gen = {"id": "gen", "type": "FixedFlowInput", "inputs": [], "outputs": ["row1"],
           "config": {"nb_rows": 1, "values_config": [{"schema_column": name, "value": f'globalMap.get("list_{name}")'}
                                                      for name in SEEN]},
           "schema": {"input": [], "output": [{"name": name, "type": "str", "nullable": True} for name in SEEN]}}
    out = writer(columns, path="seen.csv", inputs=("row1",), append=True, include_header=False)
    made = job([file_list(kind, **config), gen, out], [flow("row1", "gen", "out")])
    made["flows"].append({"name": "it", "from": "list", "to": "gen", "type": "iterate"})
    return made


def ran(tmp_path, made, files=FILES):
    folder = filled(tmp_path, files)
    for name in files:
        os.utime(folder / name, (LONG_AGO, LONG_AGO))
    previous = os.getcwd()
    os.chdir(folder)
    try:
        result = run_job(made)
    finally:
        os.chdir(previous)
    seen = folder / "seen.csv"
    rows = [tuple(line.split(";")) for line in seen.read_text().splitlines()] if seen.exists() else []
    return result, rows, os.path.realpath(folder)


def names(tmp_path, there=FILES, **config):
    """The names a file list finds among the files there are, in the order of its passes."""
    result, rows, _ = ran(tmp_path, listing(directory="in", **config), there)
    assert result.status == "success", result.error
    return [row[0] for row in rows]


def refusals(made):
    with pytest.raises(JobRefusedError) as refused:
        load_job(made)
    return [(refusal.key, refusal.reason) for refusal in refused.value.report]


# ------------------------------------------------------------------
# The passes and what each has
# ------------------------------------------------------------------

def test_files_of_the_folder_one_pass_each_sorted_by_path_with_talends_entries(tmp_path):
    result, rows, folder = ran(tmp_path, listing(directory="in"))
    assert result.status == "success", result.error
    assert rows == [("a.csv", f"{folder}/in/a.csv", f"{folder}/in", "csv", "1"),
                    ("b.txt", f"{folder}/in/b.txt", f"{folder}/in", "txt", "2"),
                    ("c.CSV", f"{folder}/in/c.CSV", f"{folder}/in", "CSV", "3")]
    assert result.global_map["list_NB_FILE"] == 3 and result.global_map["list_CURRENT_ITERATION"] == 3
    assert result.summary()["loops"] == {"list": {"items": 3, "passes": 3}}


def test_name_without_a_dot_has_no_extension_and_the_last_dot_counts(tmp_path):
    result, rows, _ = ran(tmp_path, listing(directory="in"), {"in/README": b"x", "in/a.tar.gz": b"y"})
    assert [(row[0], row[3]) for row in rows] == [("README", ""), ("a.tar.gz", "gz")]


def test_folder_with_a_dot_in_its_name_has_no_extension(tmp_path):
    result, rows, _ = ran(tmp_path, listing(directory="in", list_mode="BOTH"), {"in/data.d/": None, "in/a.csv": b"x"})
    assert [(row[0], row[3]) for row in rows] == [("a.csv", "csv"), ("data.d", "")]


def test_log_names_a_pass_by_the_path_below_the_folder(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="src.v2")
    ran(tmp_path, listing(directory="in", include_subdirs=True, files=[{"filemask": "d.*"}]))
    assert "[list] item 1 of 1: sub/d.csv" in [record.getMessage() for record in caplog.records]


def test_folder_given_in_full_and_with_a_slash_at_its_end(tmp_path):
    folder = os.path.realpath(filled(tmp_path, FILES))
    result, rows, _ = ran(tmp_path, listing(directory=f"{folder}/in/"))
    assert [row[1] for row in rows] == [f"{folder}/in/a.csv", f"{folder}/in/b.txt", f"{folder}/in/c.CSV"]


def test_no_file_no_pass(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="src.v2")
    result, rows, _ = ran(tmp_path, listing(directory="in/empty"))
    assert result.status == "success" and rows == [] and result.global_map["list_NB_FILE"] == 0
    assert "[list] no item: what it leads to is not run" in [record.getMessage() for record in caplog.records]


def test_no_file_fails_the_job_when_that_is_an_error(tmp_path):
    result, rows, _ = ran(tmp_path, listing(directory="in/empty", error=True))
    assert (result.status, result.error, rows) == ("failed", "No file found in directory in/empty", [])


# ------------------------------------------------------------------
# Which names
# ------------------------------------------------------------------

@pytest.mark.parametrize("masks, found", [
    (["*.csv"], ["a.csv"]), (["*.csv", "*.txt"], ["a.csv", "b.txt"]), (["?.csv"], ["a.csv"]), (["[ab].*"], ["a.csv", "b.txt"]),
    (["[!a]*"], ["b.txt", "c.CSV"]), (["[^a]*"], ["b.txt", "c.CSV"]), (["a\\.csv"], ["a.csv"]), (["a"], []),
    (["*"], ["a.csv", "b.txt", "c.CSV"]), ([], ["a.csv", "b.txt", "c.CSV"]), ([".*"], [".hidden.csv"]),
], ids=["one", "two", "one character", "a set", "not in a set", "not in a set, the other way", "an escaped dot",
        "the whole name has to fit", "every name", "no mask", "a mask that starts with a dot"])
def test_mask_says_which_names(tmp_path, masks, found):
    assert names(tmp_path, files=[{"filemask": mask} for mask in masks]) == found


@pytest.mark.parametrize("insensitive", ["NO", "no", False, "false"])
def test_capitals_and_small_letters_are_told_apart_unless_asked_otherwise(tmp_path, insensitive):
    assert names(tmp_path, files=[{"filemask": "*.csv"}], case_sensitive=insensitive) == ["a.csv", "c.CSV"]
    assert names(tmp_path / "apart", files=[{"filemask": "*.csv"}], case_sensitive="YES") == ["a.csv"]


def test_mask_as_a_regular_expression(tmp_path):
    assert names(tmp_path, glob_expressions=False, files=[{"filemask": r"[a-c]\.(csv|txt)"}]) == ["a.csv", "b.txt"]


def test_names_that_fit_an_exclude_mask_are_left_out(tmp_path):
    assert names(tmp_path, exclude_file=True, exclude_filemask="*.txt, c*") == ["a.csv"]
    assert names(tmp_path / "off", exclude_file=False, exclude_filemask="*.txt") == ["a.csv", "b.txt", "c.CSV"]


def test_names_that_start_with_a_dot_and_files_v2_is_still_writing_are_left_out(tmp_path):
    files = dict(FILES, **{"in/.out.csv.w.v2tmp123": b"half", "in/z.csv": b"z"})
    assert names(tmp_path, files) == ["a.csv", "b.txt", "c.CSV", "z.csv"]
    assert names(tmp_path / "dots", files, files=[{"filemask": ".*"}]) == [".hidden.csv"]


def test_subfolders_are_gone_into_when_asked_and_a_folder_that_starts_with_a_dot_is_not(tmp_path):
    result, rows, folder = ran(tmp_path, listing(directory="in", include_subdirs=True, files=[{"filemask": "*.csv"}]))
    assert [row[1][len(folder) + 1:] for row in rows] == ["in/a.csv", "in/sub/d.csv", "in/sub/deep/e.csv"]
    assert rows[1][2] == f"{folder}/in/sub"


@pytest.mark.parametrize("mode, found", [
    ("FILES", ["a.csv", "b.txt", "c.CSV"]), ("DIRECTORIES", ["empty", "sub"]), ("BOTH", ["a.csv", "b.txt", "c.CSV", "empty", "sub"]),
])
def test_files_folders_or_both(tmp_path, mode, found):
    result, rows, _ = ran(tmp_path, listing(directory="in", list_mode=mode))
    assert [row[0] for row in rows] == found
    assert all(row[3] == "" for row in rows if row[0] in ("empty", "sub"))


def test_folders_at_every_depth(tmp_path):
    assert names(tmp_path, list_mode="DIRECTORIES", include_subdirs=True) == ["empty", "sub", "deep"]


# ------------------------------------------------------------------
# The order
# ------------------------------------------------------------------

@pytest.mark.parametrize("config, found", [
    ({}, ["B.csv", "a10.csv", "a2.csv", "sub/a1.csv"]),
    ({"order_by_nothing": True, "order_action_desc": True}, ["B.csv", "a10.csv", "a2.csv", "sub/a1.csv"]),
    ({"order_by_filename": True}, ["B.csv", "sub/a1.csv", "a10.csv", "a2.csv"]),
    ({"order_by_filename": True, "order_action_desc": True}, ["a2.csv", "a10.csv", "sub/a1.csv", "B.csv"]),
    ({"order_by_filesize": True}, ["a2.csv", "sub/a1.csv", "B.csv", "a10.csv"]),
    ({"order_by_filesize": True, "order_action_desc": True}, ["a10.csv", "B.csv", "sub/a1.csv", "a2.csv"]),
    ({"order_by_modifieddate": True}, ["a10.csv", "sub/a1.csv", "a2.csv", "B.csv"]),
    ({"order_by": "ORDER_BY_FILESIZE", "order_action": "ORDER_ACTION_DESC"}, ["a10.csv", "B.csv", "sub/a1.csv", "a2.csv"]),
], ids=["by path", "by path is never turned round", "by name", "by name, down", "by size", "by size, down", "by date",
        "as v1 writes it"])
def test_order(tmp_path, config, found):
    files = {"in/a10.csv": b"1234", "in/a2.csv": b"1", "in/B.csv": b"123", "in/sub/a1.csv": b"12"}
    changed = {"in/a10.csv": 1, "in/sub/a1.csv": 2, "in/a2.csv": 3, "in/B.csv": 4}
    folder = filled(tmp_path, files)
    made = listing(directory="in", include_subdirs=True, **config)
    for name, at in changed.items():
        os.utime(folder / name, (LONG_AGO + at, LONG_AGO + at))
    previous = os.getcwd()
    os.chdir(folder)
    try:
        result = run_job(made)
    finally:
        os.chdir(previous)
    assert result.status == "success", result.error
    root = os.path.realpath(folder) + "/in/"
    assert [line.split(";")[1][len(root):] for line in (folder / "seen.csv").read_text().splitlines()] == found


def test_by_name_folders_come_before_files(tmp_path):
    there = {"in/b.csv": b"", "in/a_dir/": None, "in/c_dir/": None, "in/a.csv": b""}
    assert names(tmp_path, there, list_mode="BOTH", order_by_filename=True) == ["a_dir", "c_dir", "a.csv", "b.csv"]
    down = names(tmp_path / "down", there, list_mode="BOTH", order_by_filename=True, order_action_desc=True)
    assert down == ["b.csv", "a.csv", "c_dir", "a_dir"]


# ------------------------------------------------------------------
# Links, and what is no file
# ------------------------------------------------------------------

def test_link_is_listed_when_it_leads_to_a_file_in_the_folder_and_left_out_and_named_when_it_leads_out(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="src.v2")
    folder = filled(tmp_path, dict(FILES, **{"outside/secret.csv": b"s", "outside/more/x.csv": b"x"}))
    os.symlink("a.csv", folder / "in/inside.csv")
    os.symlink("../outside/secret.csv", folder / "in/out.csv")
    os.symlink("../outside", folder / "in/linked")
    os.symlink("nowhere", folder / "in/broken.csv")
    os.mkfifo(folder / "in/pipe.csv")
    previous = os.getcwd()
    os.chdir(folder)
    try:
        result = run_job(listing(directory="in", include_subdirs=True, files=[{"filemask": "*.csv"}]))
    finally:
        os.chdir(previous)
    assert result.status == "success", result.error
    found = [line.split(";")[0] for line in (folder / "seen.csv").read_text().splitlines()]
    assert found == ["a.csv", "inside.csv", "d.csv", "e.csv"]
    assert [record.getMessage() for record in caplog.records] == [
        "[list] 3 names in 'in' are left out, being links out of the folder or no files; the first: 'in/broken.csv'"]


def test_folder_that_cannot_be_looked_into_fails_the_job_and_is_not_passed_over(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root may read everything")
    folder = filled(tmp_path, FILES)
    os.chmod(folder / "in/sub", 0o000)
    previous = os.getcwd()
    os.chdir(folder)
    try:
        result = run_job(listing(directory="in", include_subdirs=True))
    finally:
        os.chdir(previous)
        os.chmod(folder / "in/sub", 0o700)
    assert (result.status, result.error) == ("failed", "'in/sub' cannot be looked into: permission denied")


# ------------------------------------------------------------------
# The folder, files still arriving, and the cap
# ------------------------------------------------------------------

@pytest.mark.parametrize("directory, said", [
    ("nope", "the folder 'nope' is not there"), ("in/a.csv", "'in/a.csv' is no folder"),
])
def test_folder_that_is_not_there_fails_the_job(tmp_path, directory, said):
    result, rows, _ = ran(tmp_path, listing(directory=directory))
    assert (result.status, result.error, rows) == ("failed", said, [])


def test_job_that_is_not_to_die_goes_on_with_no_pass_and_says_why(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="src.v2")
    result, rows, _ = ran(tmp_path, listing(directory="nope", die_on_error=False))
    assert result.status == "success" and rows == []
    assert result.global_map["list_ERROR_MESSAGE"] == "the folder 'nope' is not there"
    assert [record.getMessage() for record in caplog.records] == ["[list] the folder 'nope' is not there; the job goes on"]


def test_file_changed_too_lately_is_left_for_a_later_run_and_counted(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="src.v2")
    folder = filled(tmp_path, {"in/old.csv": b"o", "in/new.csv": b"n"})
    os.utime(folder / "in/old.csv", (LONG_AGO, LONG_AGO))
    now = time.time()
    os.utime(folder / "in/new.csv", (now, now))
    previous = os.getcwd()
    os.chdir(folder)
    try:
        result = run_job(listing(directory="in", min_age_seconds=3600))
    finally:
        os.chdir(previous)
    assert result.status == "success", result.error
    assert (folder / "seen.csv").read_text().split(";")[0] == "old.csv" and result.global_map["list_NB_FILE"] == 1
    assert "[list] 1 file in 'in' changed less than 3600 seconds ago and is left for a later run" in [
        record.getMessage() for record in caplog.records]


def test_more_files_than_the_cap_fail_the_job_before_the_first_pass(tmp_path):
    result, rows, _ = ran(tmp_path, listing(directory="in", max_items=2))
    assert (result.status, rows) == ("failed", [])
    assert result.error == "3 items, and a loop may have 2 by `max_items`: none is run"


# ------------------------------------------------------------------
# Masks
# ------------------------------------------------------------------

@pytest.mark.parametrize("mask, fits, does_not", [
    ("*.csv", ["a.csv", ".csv", "a.b.csv"], ["a.csvx", "a_csv", "a.CSV"]),
    ("a?c", ["abc", "a.c"], ["ac", "abbc"]),
    ("[a-c]x", ["ax", "cx"], ["dx", "x"]),
    ("[!a-c]x", ["dx"], ["ax"]), ("[^a-c]x", ["dx"], ["ax"]),
    (r"a\*b", ["a*b"], ["axb"]), (r"a\?b", ["a?b"], ["axb"]), (r"\[a]", ["[a]"], ["a"]),
    ("a+b(1).txt", ["a+b(1).txt"], ["aab1.txt", "a+b(1)_txt"]),
    ("[ab", ["[ab"], ["a", "b"]), ("x[]]y", ["x]y"], ["xy"]),
], ids=["star", "question mark", "a range", "not, with !", "not, with ^", "escaped star", "escaped question mark",
        "escaped bracket", "signs that mean something elsewhere", "a bracket never closed", "a bracket in a set"])
def test_pattern_is_talends_own(mask, fits, does_not):
    pattern = pattern_of(mask, glob=True, apart=True)
    assert [name for name in fits if not pattern.fullmatch(name)] == []
    assert [name for name in does_not if pattern.fullmatch(name)] == []


# ------------------------------------------------------------------
# A converted job, what is refused, and the names it goes by
# ------------------------------------------------------------------

def test_converted_sample_job_runs_once_its_java_is_written_in_python(tmp_path):
    sample = json.loads(SAMPLE.read_text())
    made = copy.deepcopy(sample)
    by_id = {component["id"]: component for component in made["components"]}
    by_id["tFileList_1"]["config"]["directory"] = "data"
    by_id["tFileOutputDelimited_1"]["config"]["filepath"] = "merge.dat"
    for column in by_id["tMap_1"]["config"]["outputs"][0]["columns"]:
        column["expression"] = column["expression"].replace("{{java}}", "")
    names_of = [column["name"] for column in by_id["tFileInputDelimited_1"]["schema"]["output"]]
    line = ";".join("1" for _ in names_of)
    folder = filled(tmp_path, {"data/batch_1.csv": (line + "\n").encode(), "data/batch_2.csv": (line + "\n" + line + "\n").encode(),
                               "data/other.csv": b"x\n"})
    previous = os.getcwd()
    os.chdir(folder)
    try:
        result = run_job(made)
    finally:
        os.chdir(previous)
    assert result.status == "success", result.error
    assert result.summary()["loops"] == {"tFileList_1": {"items": 2, "passes": 2}}
    assert result.rows == {"tFileOutputDelimited_1": 3}
    assert len((folder / "merge.dat").read_text().splitlines()) == 4


def test_names_v1s_engine_reads_and_what_the_converter_writes(tmp_path):
    made = listing(DIRECTORY="in", LIST_MODE="FILES", INCLUDSUBDIR=False, CASE_SENSITIVE="YES", ERROR=False, GLOBEXPRESSIONS=True,
                   FILES=[{"FILEMASK": "*.csv"}], IFEXCLUDE=False, EXCLUDEFILEMASK="*.txt", FORMAT_FILEPATH_TO_SLASH=False)
    result, rows, _ = ran(tmp_path, made)
    assert result.status == "success" and [row[0] for row in rows] == ["a.csv"]
    made = listing(directory="in", list_mode="FILES", include_subdirs=False, case_sensitive="YES", error=False,
                   glob_expressions=True, files=[{"filemask": "*.csv"}], order_by_nothing=True, order_by_filename=False,
                   order_by_filesize=False, order_by_modifieddate=False, order_action_asc=True, order_action_desc=False,
                   exclude_file=False, exclude_filemask="*.txt", format_filepath_to_slash=False, tstatcatcher_stats=False,
                   label="")
    result, rows, _ = ran(tmp_path / "converter", made)
    assert result.status == "success" and [row[0] for row in rows] == ["a.csv"]


@pytest.mark.parametrize("config, said", [
    ({}, "directory: required config key is missing"), ({"directory": " "}, "directory: there is no folder named"),
    ({"directory": "in", "nope": 1}, "nope: unknown config key"),
    ({"directory": "in", "list_mode": "LINKS"}, "list_mode: 'LINKS' is not allowed; use one of 'FILES', 'DIRECTORIES', 'BOTH'"),
    ({"directory": "in", "glob_expressions": False, "files": [{"filemask": "a(b"}]},
     "files[0].filemask: 'a(b' is no regular expression Python reads: missing ), unterminated subpattern at position 1"),
    ({"directory": "in", "min_age_seconds": -1}, "min_age_seconds: -1.0 seconds is no age; give 0 or more"),
    ({"directory": "in", "case_sensitive": "MAYBE"}, "case_sensitive: 'MAYBE' is neither YES nor NO"),
    ({"directory": "in", "order_by_filename": True, "order_by_filesize": True},
     "order_by_filesize: files are listed in one order, and `order_by_filename` is on as well"),
])
def test_what_cannot_be_done_refuses_the_job(config, said):
    assert [f"{key}: {reason}" for key, reason in refusals(job([file_list(**config)], []))] == [said]


def test_mask_from_the_context_that_is_no_regular_expression_refuses_the_job_too():
    made = listing(directory="in", glob_expressions=False, files=[{"filemask": "${context.mask}"}])
    made["context"] = {"Default": {"mask": {"value": "a(b", "type": "str"}}}
    assert refusals(made) == [
        ("files[0].filemask", "'a(b' is no regular expression Python reads: missing ), unterminated subpattern at position 1")]


@pytest.mark.parametrize("kind", ["file_list", "FileList", "tFileList"])
def test_every_name_of_it(tmp_path, kind):
    result, rows, _ = ran(tmp_path, listing(kind=kind, directory="in"))
    assert result.status == "success" and len(rows) == 3
