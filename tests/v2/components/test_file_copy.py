"""File copy: against v1 for what is in the folder afterwards, and to Talend's rule where v1 differs."""
import os

import pytest

from src.v2 import load_job
from src.v2.errors import JobRefusedError
from tests.v2.components.kit import job

from .test_file_actions_kit import action, both, filled, on_v2, tree

FILES = {"a.txt": b"new", "src/": None, "src/one.txt": b"1", "src/deep/two.txt": b"2", "there/": None, "there/a.txt": b"old"}


def copy(kind="FileCopy", **config):
    return action("cp", kind, **config)


def test_file_is_copied_into_the_folder_under_its_own_name(tmp_path):
    _, result = both(copy(filename="a.txt", destination="out"), FILES, tmp_path)
    assert tree(tmp_path / "v2")["out/a.txt"] == b"new" and (tmp_path / "v2" / "a.txt").exists()
    assert result.status == "success"


def test_file_is_copied_under_another_name_when_asked(tmp_path):
    both(copy(filename="a.txt", destination="out", rename=True, destination_rename="b.txt"), FILES, tmp_path)
    assert tree(tmp_path / "v2")["out/b.txt"] == b"new" and "out/a.txt" not in tree(tmp_path / "v2")
    both(copy(filename="a.txt", destination="out", rename=False, destination_rename="b.txt"), FILES, tmp_path / "b")
    assert "out/a.txt" in tree(tmp_path / "b" / "v2")


def test_file_that_is_there_is_written_over(tmp_path):
    both(copy(filename="a.txt", destination="there"), FILES, tmp_path)
    assert tree(tmp_path / "v2")["there/a.txt"] == b"new"


def test_source_is_taken_away_when_asked(tmp_path):
    both(copy(filename="a.txt", destination="out", remove_file=True), FILES, tmp_path)
    assert "a.txt" not in tree(tmp_path / "v2") and tree(tmp_path / "v2")["out/a.txt"] == b"new"


def test_folder_is_copied_with_everything_in_it_under_its_own_name_as_in_talend(tmp_path):
    # v1 puts what the folder holds straight into the destination.
    result = on_v2(job([copy(enable_copy_directory=True, source_derectory="src", destination="copy/of")], []), filled(tmp_path, FILES))
    after = tree(tmp_path)
    assert result.status == "success"
    assert after["copy/of/src/one.txt"] == b"1" and after["copy/of/src/deep/two.txt"] == b"2" and "src/one.txt" in after
    assert result.global_map["cp_SOURCE_DIRECTORY"] == "src" and result.global_map["cp_DESTINATION_DIRECTORY"] == "copy/of"
    assert result.global_map["cp_NB_LINE_OK"] == 1


def test_folder_copy_writes_over_what_is_there_and_makes_what_is_missing_whatever_is_switched_off(tmp_path):
    files = dict(FILES, **{"there/src/": None, "there/src/one.txt": b"old", "there/src/kept.txt": b"k"})
    made = job([copy(enable_copy_directory=True, source_directory="src", destination="there", replace_file=False,
                     create_directory=False, rename=True)], [])
    assert on_v2(made, filled(tmp_path, files)).status == "success"
    after = tree(tmp_path)
    assert after["there/src/one.txt"] == b"1" and after["there/src/kept.txt"] == b"k" and after["there/a.txt"] == b"old"
    made = job([copy(enable_copy_directory=True, source_directory="src", destination="far/off", create_directory=False)], [])
    assert on_v2(made, filled(tmp_path / "b", FILES)).status == "success" and "far/off/src/one.txt" in tree(tmp_path / "b")


def test_source_folder_is_never_taken_away_as_in_talend(tmp_path):
    # v1 deletes the folder it copied.
    made = job([copy(enable_copy_directory=True, source_derectory="src", destination="moved", remove_file=True)], [])
    assert on_v2(made, filled(tmp_path, FILES)).status == "success"
    after = tree(tmp_path)
    assert after["src/deep/two.txt"] == b"2" and after["moved/src/deep/two.txt"] == b"2"


@pytest.mark.parametrize("destination", ["src", "src/", "src/copy", "src/deep/er", "./src/x/../y"])
def test_folder_is_not_copied_into_itself(tmp_path, destination):
    # v1 fills the folder with copies of itself until a path is too long, or, with the source to be taken away,
    # deletes everything.
    made = job([copy(enable_copy_directory=True, source_derectory="src", destination=destination, remove_file=True, failon=True)], [])
    result = on_v2(made, filled(tmp_path, FILES))
    assert result.status == "failed"
    assert result.error == f"'{destination}' is in the folder 'src' that is to be copied, or is that folder: nothing is copied"
    assert tree(tmp_path) == tree(filled(tmp_path.parent / (tmp_path.name + "_ref"), FILES))


def test_time_of_the_files_of_a_folder_is_kept_only_when_asked(tmp_path):
    folder = filled(tmp_path, FILES)
    os.utime(folder / "src" / "one.txt", (1_000_000_000, 1_000_000_000))
    on_v2(job([copy(enable_copy_directory=True, source_derectory="src", destination="kept", preserve_last_modified_time=True)], []), folder)
    on_v2(job([copy(enable_copy_directory=True, source_derectory="src", destination="fresh")], []), folder)
    assert int((folder / "kept" / "src" / "one.txt").stat().st_mtime) == 1_000_000_000
    assert int((folder / "fresh" / "src" / "one.txt").stat().st_mtime) > 1_700_000_000


def test_folder_copy_that_fails_half_way_says_which_file_and_how_many(tmp_path):
    folder = filled(tmp_path, dict(FILES, **{"src/locked.txt": b"x"}))
    (folder / "src" / "locked.txt").chmod(0o000)
    os.symlink("nowhere", folder / "src" / "broken")
    try:
        result = on_v2(job([copy(enable_copy_directory=True, source_derectory="src", destination="out")], []), folder)
    finally:
        (folder / "src" / "locked.txt").chmod(0o644)
    assert result.status == "success" and result.global_map["cp_NB_LINE_REJECT"] == 1
    said = result.global_map["cp_ERROR_MESSAGE"]
    assert said.startswith("2 files of 'src' could not be copied; the first: '") and "[" not in said
    assert (folder / "out" / "src" / "one.txt").read_bytes() == b"1" and (folder / "src" / "one.txt").exists()


def test_other_spellings_of_v1(tmp_path):
    both(copy(source="a.txt", destination="out", rename=True, new_name="c.txt"), FILES, tmp_path)
    assert tree(tmp_path / "v2")["out/c.txt"] == b"new"


def test_what_talend_leaves_in_globalmap_after_a_copy(tmp_path):
    result = on_v2(job([copy(filename="a.txt", destination="out")], []), filled(tmp_path, FILES))
    held = {key: value for key, value in result.global_map.items() if key.startswith("cp_") and "NB_LINE" not in key}
    assert held == {"cp_DESTINATION_FILEPATH": os.path.join("out", "a.txt"), "cp_DESTINATION_FILENAME": "a.txt",
                    "cp_SOURCE_DIRECTORY": None, "cp_DESTINATION_DIRECTORY": "out"}
    made = dict(job([copy(filename="a.txt", destination="out")], []), run={"row_counts": True})
    assert on_v2(made, filled(tmp_path / "b", FILES)).counts["cp"] == {"NB_LINE": 1, "NB_LINE_OK": 1, "NB_LINE_REJECT": 0}


def test_file_that_is_there_and_not_to_be_replaced_is_left_and_no_fault_as_in_talend(tmp_path):
    # v1 fails the job here.
    made = job([copy(filename="a.txt", destination="there", replace_file=False, remove_file=True)], [])
    result = on_v2(made, filled(tmp_path, FILES))
    assert result.status == "success"
    after = tree(tmp_path)
    assert after["there/a.txt"] == b"old" and after["a.txt"] == b"new"


def test_time_the_file_was_changed_is_kept_only_when_asked(tmp_path):
    folder = filled(tmp_path, FILES)
    os.utime(folder / "a.txt", (1_000_000_000, 1_000_000_000))
    on_v2(job([copy(filename="a.txt", destination="kept", preserve_last_modified_time=True)], []), folder)
    on_v2(job([copy(filename="a.txt", destination="fresh")], []), folder)
    assert int((folder / "kept" / "a.txt").stat().st_mtime) == 1_000_000_000
    assert int((folder / "fresh" / "a.txt").stat().st_mtime) > 1_700_000_000


def test_copy_that_fails_goes_on_unless_the_job_is_to_fail_as_in_talend(tmp_path):
    # v1 fails the job unless `die_on_error` is written and off.
    result = on_v2(job([copy(filename="nope.txt", destination="out")], []), filled(tmp_path, FILES))
    assert result.status == "success"
    assert result.global_map["cp_ERROR_MESSAGE"] == "'nope.txt' is not there, or is no file"
    assert "out/" not in tree(tmp_path)
    for at, config in enumerate(({"failon": True}, {"fail_on_error": True}, {"die_on_error": True})):
        result = on_v2(job([copy(filename="nope.txt", destination="out", **config)], []), filled(tmp_path / str(at), FILES))
        assert result.status == "failed" and result.failed_component == "cp"
        assert result.error == "'nope.txt' is not there, or is no file"


def test_folder_that_is_not_there_is_not_made_when_told_not_to(tmp_path):
    result = on_v2(job([copy(filename="a.txt", destination="out/deep", create_directory=False, failon=True)], []),
                   filled(tmp_path, FILES))
    assert result.status == "failed" and result.error == "the folder 'out/deep' is not there, and is not to be made"


def test_folder_as_the_source_of_a_file_copy_and_a_file_as_the_source_of_a_folder_copy(tmp_path):
    result = on_v2(job([copy(filename="src", destination="out", failon=True)], []), filled(tmp_path, FILES))
    assert result.error == "'src' is not there, or is no file"
    result = on_v2(job([copy(enable_copy_directory=True, source_derectory="a.txt", destination="out", failon=True)], []),
                   filled(tmp_path / "b", FILES))
    assert result.error == "'a.txt' is not there, or is no folder"


@pytest.mark.parametrize("config, key", [
    ({"destination": "out"}, "filename"), ({"filename": "a.txt"}, "destination"), ({"filename": "a.txt", "destination": ""}, "destination"),
    ({"enable_copy_directory": True, "destination": "out"}, "source_derectory"),
    ({"filename": "a.txt", "destination": "out", "nope": 1}, "nope"),
])
def test_what_cannot_be_read_refuses_the_job(config, key):
    with pytest.raises(JobRefusedError) as refused:
        load_job(job([copy(**config)], []))
    assert [refusal.key for refusal in refused.value.report] == [key]


def test_both_v1_names_and_v2s_own(tmp_path):
    for at, kind in enumerate(("file_copy", "FileCopy", "tFileCopy")):
        on_v2(job([copy(kind=kind, filename="a.txt", destination="out")], []), filled(tmp_path / str(at), FILES))
        assert tree(tmp_path / str(at))["out/a.txt"] == b"new"


# ------------------------------------------------------------------
# What an independent review found (ticket 85)
# ------------------------------------------------------------------

def test_what_talend_leaves_in_globalmap_is_left_whatever_becomes_of_the_copy(tmp_path):
    made = job([copy(filename="sub/nope.txt", destination="out/", rename=True, destination_rename="deep/b.txt")], [])
    result = on_v2(made, filled(tmp_path, FILES))
    held = {key: value for key, value in result.global_map.items() if key.startswith("cp_D") or key.startswith("cp_S")}
    assert held == {"cp_DESTINATION_FILEPATH": os.path.join("out", "deep", "b.txt"), "cp_DESTINATION_FILENAME": "b.txt",
                    "cp_SOURCE_DIRECTORY": "sub", "cp_DESTINATION_DIRECTORY": os.path.join("out", "deep")}
    result = on_v2(job([copy(filename="a.txt", destination="out")], []), filled(tmp_path / "b", FILES))
    assert result.global_map["cp_SOURCE_DIRECTORY"] is None


def test_new_name_of_nothing_but_blanks_is_talends_own(tmp_path):
    for at, given in enumerate(("  ", "")):
        on_v2(job([copy(filename="a.txt", destination="out", rename=True, destination_rename=given)], []), filled(tmp_path / str(at), FILES))
        assert tree(tmp_path / str(at))["out/NewName.temp"] == b"new"


def test_file_copied_onto_itself_is_left_as_it_is(tmp_path):
    folder = filled(tmp_path, FILES)
    os.symlink(folder / "a.txt", folder / "there" / "link.txt")
    for config in ({"destination": "."}, {"destination": "there", "rename": True, "destination_rename": "link.txt"}):
        result = on_v2(job([copy(filename="a.txt", remove_file=True, failon=True, **config)], []), folder)
        assert result.status == "success" and (folder / "a.txt").read_bytes() == b"new"


def test_destination_that_is_a_file_is_no_folder_to_copy_into(tmp_path):
    # v1 writes over that file with the source.
    result = on_v2(job([copy(filename="src/one.txt", destination="a.txt", failon=True)], []), filled(tmp_path, FILES))
    assert result.status == "failed" and result.error == "'a.txt' is a file, not a folder to copy into"
    assert (tmp_path / "a.txt").read_bytes() == b"new"


def test_copy_the_system_refuses_says_which_file_and_why(tmp_path, caplog):
    folder = filled(tmp_path, FILES)
    (folder / "there").chmod(0o555)
    try:
        with caplog.at_level("WARNING", logger="src.v2"):
            result = on_v2(job([copy(filename="src/one.txt", destination="there")], []), folder)
    finally:
        (folder / "there").chmod(0o755)
    assert result.status == "success" and result.global_map["cp_NB_LINE_OK"] == 0 and result.global_map["cp_NB_LINE_REJECT"] == 1
    said = f"the copy failed: permission denied: '{os.path.join('there', 'one.txt')}'"
    assert result.global_map["cp_ERROR_MESSAGE"] == said
    assert [record.getMessage() for record in caplog.records] == [f"[cp] {said}; the job goes on"]


def test_move_whose_source_cannot_be_taken_away_says_so_and_the_copy_is_there(tmp_path):
    folder = filled(tmp_path, FILES)
    (folder / "src").chmod(0o555)
    try:
        result = on_v2(job([copy(filename="src/one.txt", destination="out", remove_file=True, failon=True)], []), folder)
    finally:
        (folder / "src").chmod(0o755)
    assert result.status == "failed" and (folder / "out" / "one.txt").read_bytes() == b"1"
    assert result.error == "the file was copied, and the source 'src/one.txt' could not be taken away: permission denied"




def test_folder_copy_into_what_is_a_file_fails_in_plain_words(tmp_path):
    made = job([copy(enable_copy_directory=True, source_derectory="src", destination="a.txt", failon=True)], [])
    result = on_v2(made, filled(tmp_path, FILES))
    assert result.status == "failed" and result.error.startswith("the copy failed: ") and "'" in result.error
    assert "[" not in result.error and (tmp_path / "a.txt").read_bytes() == b"new"
