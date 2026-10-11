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


def test_folder_is_copied_with_everything_in_it(tmp_path):
    both(copy(enable_copy_directory=True, source_derectory="src", destination="copy/of"), FILES, tmp_path)
    after = tree(tmp_path / "v2")
    assert after["copy/of/one.txt"] == b"1" and after["copy/of/deep/two.txt"] == b"2" and "src/one.txt" in after
    both(copy(enable_copy_directory=True, source_directory="src", destination="there"), FILES, tmp_path / "b")
    assert tree(tmp_path / "b" / "v2")["there/one.txt"] == b"1" and tree(tmp_path / "b" / "v2")["there/a.txt"] == b"old"


def test_folder_is_moved_when_its_source_is_to_be_taken_away(tmp_path):
    both(copy(enable_copy_directory=True, source_derectory="src", destination="moved", remove_file=True), FILES, tmp_path)
    after = tree(tmp_path / "v2")
    assert "src/" not in after and after["moved/deep/two.txt"] == b"2"


def test_other_spellings_of_v1(tmp_path):
    both(copy(source="a.txt", destination="out", rename=True, new_name="c.txt"), FILES, tmp_path)
    assert tree(tmp_path / "v2")["out/c.txt"] == b"new"


def test_what_talend_leaves_in_globalmap_after_a_copy(tmp_path):
    result = on_v2(job([copy(filename="a.txt", destination="out")], []), filled(tmp_path, FILES))
    held = {key: value for key, value in result.global_map.items() if key.startswith("cp_") and "NB_LINE" not in key}
    assert held == {"cp_DESTINATION_FILEPATH": os.path.join("out", "a.txt"), "cp_DESTINATION_FILENAME": "a.txt",
                    "cp_SOURCE_DIRECTORY": "", "cp_DESTINATION_DIRECTORY": "out"}
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
    ({"filename": "a.txt", "destination": "out", "rename": True, "destination_rename": ""}, "destination_rename"),
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
