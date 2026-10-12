"""What stands at a scratch name before a file is written there."""
import errno
import os

from src.v2 import files, run_job
from tests.v2.components.kit import flow, job, reader, writer


def test_nothing_at_a_scratch_name_is_fine(tmp_path):
    scratch = str(tmp_path / ".out.csv.w.v2tmp1")
    assert files.cleared(scratch) == scratch and not os.path.lexists(scratch)


def test_file_left_at_a_scratch_name_is_removed(tmp_path):
    scratch = tmp_path / ".out.csv.w.v2tmp1"
    scratch.write_bytes(b"half a file of an earlier run")
    assert files.cleared(str(scratch)) == str(scratch) and not os.path.lexists(scratch)


def test_folder_left_at_a_scratch_name_is_removed_with_what_it_holds(tmp_path):
    scratch = tmp_path / ".in.zip.open.v2tmp1"
    (scratch / "new" / "sub").mkdir(parents=True)
    (scratch / "new" / "sub" / "a.csv").write_bytes(b"x")
    assert files.cleared(str(scratch)) == str(scratch) and not os.path.lexists(scratch)


def test_link_left_at_a_scratch_name_is_removed_and_what_it_leads_to_stays(tmp_path):
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "elsewhere" / "victim.cfg").write_bytes(b"keep")
    for number, leads_to in enumerate(["elsewhere/victim.cfg", "elsewhere", "nowhere"]):
        scratch = tmp_path / f".out.csv.w.v2tmp{number}"
        os.symlink(tmp_path / leads_to, scratch)
        assert files.cleared(str(scratch)) == str(scratch) and not os.path.lexists(scratch)
    assert (tmp_path / "elsewhere" / "victim.cfg").read_bytes() == b"keep"


def planted(tmp_path, monkeypatch, stays=False):
    """A job that writes out.csv, with a link to a file elsewhere planted where out.csv is written first."""
    (tmp_path / "in.csv").write_bytes(b"1;a\n2;b\n")
    victim = tmp_path / "victim.cfg"
    victim.write_bytes(b"keep")
    scratch = files.temp_beside(str(tmp_path / "out.csv"), "out")
    os.symlink(victim, scratch)
    if stays:
        really = os.remove
        # As in a folder where only its owner may take a file away, and the link is someone else's.
        monkeypatch.setattr(os, "remove", lambda path, *more, **kept: (_ for _ in ()).throw(
            OSError(errno.EPERM, "Operation not permitted", str(path))) if str(path) == scratch else really(path, *more, **kept))
    made = job([reader("id:int, name:str", path=str(tmp_path / "in.csv"), outputs=("row2",)),
                writer("id:int, name:str", path=str(tmp_path / "out.csv"))], [flow("row2", "in", "out")])
    return made, victim, scratch


def test_output_fails_when_the_link_planted_at_its_scratch_name_cannot_be_taken_away(tmp_path, monkeypatch):
    made, victim, scratch = planted(tmp_path, monkeypatch, stays=True)
    result = run_job(made)
    assert (result.status, result.failed_component) == ("failed", "out")
    assert result.error == f"[Errno 1] Operation not permitted: '{scratch}'"
    assert victim.read_bytes() == b"keep" and not (tmp_path / "out.csv").exists()


def test_output_is_not_written_through_a_link_planted_at_its_scratch_name(tmp_path):
    (tmp_path / "in.csv").write_bytes(b"1;a\n2;b\n")
    victim = tmp_path / "victim.cfg"
    victim.write_bytes(b"keep")
    os.symlink(victim, files.temp_beside(str(tmp_path / "out.csv"), "out"))
    made = job([reader("id:int, name:str", path=str(tmp_path / "in.csv"), outputs=("row2",)),
                writer("id:int, name:str", path=str(tmp_path / "out.csv"))], [flow("row2", "in", "out")])
    result = run_job(made)
    assert result.status == "success", result.error
    assert victim.read_bytes() == b"keep"
    assert (tmp_path / "out.csv").read_bytes() == b"id;name\n1;a\n2;b\n" and not (tmp_path / "out.csv").is_symlink()
