"""File delete: against v1 for what is in the folder afterwards, and to Talend's rule where v1 differs."""
import pytest

from src.v2 import load_job
from src.v2.errors import JobRefusedError
from tests.v2.components.kit import job

from .test_file_actions_kit import action, both, filled, on_v2, tree

FILES = {"a.txt": b"x", "dir/": None, "dir/b.txt": b"y", "dir/deep/c.txt": b"z", "empty/": None}


def delete(kind="FileDelete", **config):
    return action("rm", kind, **config)


@pytest.mark.parametrize("config, gone, status", [
    ({"filename": "a.txt"}, ["a.txt"], "File deleted."),
    ({"folder": True, "directory": "dir"}, ["dir/", "dir/b.txt", "dir/deep/", "dir/deep/c.txt"], "Path deleted."),
    ({"folder": True, "directory": "empty"}, ["empty/"], "Path deleted."),
    ({"folder_file": True, "path": "a.txt"}, ["a.txt"], "File deleted."),
    ({"folder_file": True, "path": "dir"}, ["dir/", "dir/b.txt", "dir/deep/", "dir/deep/c.txt"], "Path deleted."),
    ({"FILENAME": "a.txt"}, ["a.txt"], "File deleted."), ({"path": "a.txt"}, ["a.txt"], "File deleted."),
    ({"is_directory": True, "DIRECTORY": "empty"}, ["empty/"], "Path deleted."),
    ({"is_folder_file": True, "PATH": "a.txt"}, ["a.txt"], "File deleted."),
])
def test_file_or_folder_is_deleted(tmp_path, config, gone, status):
    _, result = both(delete(**config), FILES, tmp_path)
    assert sorted(set(tree(filled(tmp_path / "ref", FILES))) - set(tree(tmp_path / "v2"))) == sorted(gone)
    path = [value for key, value in config.items() if isinstance(value, str)][0]
    assert result.global_map["rm_CURRENT_STATUS"] == status and result.global_map["rm_DELETE_PATH"] == path


def test_it_counts_one_row(tmp_path):
    made = dict(job([delete(filename="a.txt")], []), run={"row_counts": True})
    assert on_v2(made, filled(tmp_path, FILES)).counts["rm"] == {"NB_LINE": 1, "NB_LINE_OK": 1, "NB_LINE_REJECT": 0}


@pytest.mark.parametrize("config, status, said", [
    ({"filename": "nope.txt"}, "File does not exist or is invalid.", "File 'nope.txt' does not exist or is invalid or is not a file."),
    ({"filename": "dir"}, "File does not exist or is invalid.", "File 'dir' does not exist or is invalid or is not a file."),
    ({"folder": True, "directory": "nope"}, "Path does not exist or is invalid.",
     "Directory 'nope' does not exist or is invalid or is not a directory."),
    ({"folder": True, "directory": "a.txt"}, "Path does not exist or is invalid.",
     "Directory 'a.txt' does not exist or is invalid or is not a directory."),
    ({"folder_file": True, "path": "nope"}, "File or path does not exist or is invalid.", "File or path does not exist or is invalid."),
])
def test_nothing_there_to_delete_fails_the_job_unless_told_otherwise_as_in_talend(tmp_path, config, status, said):
    # v1 warns and goes on, whatever `failon` says.
    result = on_v2(job([delete(**config)], []), filled(tmp_path, FILES))
    assert result.status == "failed" and result.failed_component == "rm" and result.error == said
    assert result.global_map["rm_CURRENT_STATUS"] == status and tree(tmp_path) == tree(filled(tmp_path / "ref", FILES))
    _, result = both(delete(failon=False, **config), FILES, tmp_path / "b")
    assert result.status == "success" and result.global_map["rm_CURRENT_STATUS"] == status
    assert result.global_map["rm_ERROR_MESSAGE"] == said
    made = dict(job([delete(fail_on_error=False, **config)], []), run={"row_counts": True})
    assert on_v2(made, filled(tmp_path / "c", FILES)).counts["rm"] == {"NB_LINE": 1, "NB_LINE_OK": 0, "NB_LINE_REJECT": 1}


def test_folder_with_something_in_it_stays_when_it_is_not_to_go_with_what_it_holds(tmp_path):
    _, result = both(delete(folder=True, directory="dir", recursive=False, failon=False), FILES, tmp_path)
    assert "dir/b.txt" in tree(tmp_path / "v2") and result.global_map["rm_CURRENT_STATUS"] == "No path deleted."
    result = on_v2(job([delete(folder=True, directory="dir", recursive=False)], []), filled(tmp_path / "b", FILES))
    assert result.status == "failed" and result.error == "Directory 'dir' can not be deleted: it is not empty"
    _, result = both(delete(folder=True, directory="empty", recursive=False), FILES, tmp_path / "c")
    assert "empty/" not in tree(tmp_path / "c" / "v2")


def test_file_or_folder_that_cannot_be_deleted(tmp_path):
    folder = filled(tmp_path, FILES)
    (folder / "dir").chmod(0o555)   # nothing in it can be taken away
    try:
        result = on_v2(job([delete(filename="dir/b.txt", failon=False)], []), folder)
        assert result.status == "success" and result.global_map["rm_CURRENT_STATUS"] == "No file deleted."
        assert result.global_map["rm_ERROR_MESSAGE"] == "File 'dir/b.txt' can not be deleted: permission denied"
        result = on_v2(job([delete(folder=True, directory="dir")], []), folder)
        assert result.status == "failed" and result.global_map["rm_CURRENT_STATUS"] == "No path deleted."
        assert result.error == "Directory 'dir' can not be deleted: permission denied"
    finally:
        (folder / "dir").chmod(0o755)


def test_path_from_the_context(tmp_path):
    made = job([delete(filename="${context.name}.txt")], [])
    made["context"] = {"Default": {"name": {"value": "a", "type": "str"}}}
    assert on_v2(made, filled(tmp_path, FILES)).status == "success" and "a.txt" not in tree(tmp_path)


@pytest.mark.parametrize("config, key", [
    ({}, "filename"), ({"filename": ""}, "filename"), ({"folder": True, "filename": "a.txt"}, "directory"),
    ({"folder_file": True, "filename": "a.txt"}, "path"), ({"filename": "a", "nope": 1}, "nope"),
])
def test_what_cannot_be_read_refuses_the_job(config, key):
    with pytest.raises(JobRefusedError) as refused:
        load_job(job([delete(**config)], []))
    assert [refusal.key for refusal in refused.value.report] == [key]


def test_both_v1_names_and_v2s_own(tmp_path):
    for at, kind in enumerate(("file_delete", "FileDelete", "tFileDelete")):
        on_v2(job([delete(kind=kind, filename="a.txt")], []), filled(tmp_path / str(at), FILES))
        assert "a.txt" not in tree(tmp_path / str(at))


# ------------------------------------------------------------------
# What an independent review found (ticket 85)
# ------------------------------------------------------------------

import logging
import os


@pytest.mark.parametrize("config", [
    {"folder": True, "directory": "lnk"}, {"folder": True, "directory": "lnk/"}, {"folder_file": True, "path": "lnk"},
    {"folder_file": True, "path": "lnk/"}, {"filename": "lnk"},
])
def test_link_to_a_folder_is_taken_away_and_the_folder_it_leads_to_is_never_touched(tmp_path, config):
    # v1 deletes what the folder holds when the path ends in a slash, and fails otherwise; Talend empties it.
    folder = filled(tmp_path, FILES)
    os.symlink("dir", folder / "lnk")
    result = on_v2(job([delete(**config)], []), folder)
    after = tree(folder)
    assert after["dir/b.txt"] == b"y" and after["dir/deep/c.txt"] == b"z"
    assert result.status == "success" and not os.path.lexists(folder / "lnk")
    assert result.global_map["rm_CURRENT_STATUS"] == ("File deleted." if "filename" in config else "Path deleted.")


def test_link_to_a_file_and_a_link_to_nothing_are_taken_away_alone(tmp_path):
    folder = filled(tmp_path, FILES)
    os.symlink("a.txt", folder / "to_file")
    os.symlink("nowhere", folder / "broken")
    assert on_v2(job([delete(filename="to_file")], []), folder).status == "success"
    assert on_v2(job([delete(folder_file=True, path="broken")], []), folder).status == "success"
    assert (folder / "a.txt").read_bytes() == b"x" and not os.path.lexists(folder / "to_file") and not os.path.lexists(folder / "broken")


def test_link_inside_a_folder_goes_with_it_and_what_it_leads_to_stays(tmp_path):
    folder = filled(tmp_path, dict(FILES, **{"keep/k.txt": b"k"}))
    os.symlink("../keep", folder / "dir" / "to_keep")
    assert on_v2(job([delete(folder=True, directory="dir")], []), folder).status == "success"
    assert tree(folder)["keep/k.txt"] == b"k" and "dir/" not in tree(folder)


@pytest.mark.parametrize("config", [
    {"folder": True, "directory": "."}, {"folder_file": True, "path": "dir/.."}, {"folder": True, "directory": ".."},
    {"folder_file": True, "path": "./"},
])
def test_folder_the_job_runs_in_is_never_deleted(tmp_path, config):
    # v1 and Talend empty it, and then say that nothing was deleted.
    folder = filled(tmp_path / "work", FILES)
    result = on_v2(job([delete(**config)], []), folder)
    assert result.status == "failed" and result.global_map["rm_CURRENT_STATUS"] == "No path deleted."
    assert result.error == f"Directory '{config.get('directory') or config['path']}' is the folder the job runs in, or one it lies in: it is not deleted"
    assert tree(folder) == tree(filled(tmp_path / "ref", FILES))


def test_folder_deleted_only_in_part_says_so(tmp_path):
    folder = filled(tmp_path, dict(FILES, **{"dir/locked/x.txt": b"x"}))
    (folder / "dir" / "locked").chmod(0o555)
    try:
        result = on_v2(job([delete(folder=True, directory="dir", failon=False)], []), folder)
    finally:
        (folder / "dir" / "locked").chmod(0o755)
    assert result.global_map["rm_CURRENT_STATUS"] == "No path deleted."
    assert result.global_map["rm_ERROR_MESSAGE"].startswith("Directory 'dir' can not be deleted: permission denied: '")
    assert result.global_map["rm_ERROR_MESSAGE"].endswith("; some of what it held is gone")
    assert "dir/b.txt" not in tree(folder) and tree(folder)["dir/locked/x.txt"] == b"x"


def test_either_way_takes_a_file_for_a_file(tmp_path):
    folder = filled(tmp_path, FILES)
    os.symlink("dir", folder / "lnk")
    result = on_v2(job([delete(folder_file=True, path="a.txt")], []), folder)
    assert result.global_map["rm_CURRENT_STATUS"] == "File deleted."


def test_filename_and_directory_win_over_path_which_only_stands_in_for_them(tmp_path):
    on_v2(job([delete(filename="a.txt", path="dir/b.txt", directory="empty")], []), filled(tmp_path, FILES))
    assert "a.txt" not in tree(tmp_path) and "dir/b.txt" in tree(tmp_path) and "empty/" in tree(tmp_path)
    on_v2(job([delete(folder=True, filename="a.txt", path="dir", directory="empty")], []), filled(tmp_path / "b", FILES))
    assert "empty/" not in tree(tmp_path / "b") and "dir/" in tree(tmp_path / "b") and "a.txt" in tree(tmp_path / "b")


def test_delete_that_does_not_fail_the_job_warns(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="src.v2"):
        on_v2(job([delete(filename="nope.txt", failon=False)], []), filled(tmp_path, FILES))
    assert [record.getMessage() for record in caplog.records] == [
        "[rm] File 'nope.txt' does not exist or is invalid or is not a file.; the job goes on"]


def test_v1s_die_on_error_is_taken():
    load_job(job([delete(filename="a.txt", die_on_error=False)], []))


def test_link_to_a_file_is_no_folder_and_a_link_that_cannot_be_taken_away_says_so(tmp_path):
    folder = filled(tmp_path, dict(FILES, **{"box/": None}))
    os.symlink("a.txt", folder / "to_file")
    os.symlink("../dir", folder / "box" / "lnk")
    result = on_v2(job([delete(folder=True, directory="to_file", failon=False)], []), folder)
    assert result.global_map["rm_CURRENT_STATUS"] == "Path does not exist or is invalid." and os.path.lexists(folder / "to_file")
    (folder / "box").chmod(0o555)
    try:
        result = on_v2(job([delete(folder=True, directory="box/lnk", failon=False)], []), folder)
    finally:
        (folder / "box").chmod(0o755)
    assert result.global_map["rm_CURRENT_STATUS"] == "No path deleted."
    assert result.global_map["rm_ERROR_MESSAGE"] == "Directory 'box/lnk' can not be deleted: permission denied: 'box/lnk'"
    assert tree(folder)["dir/b.txt"] == b"y"
