"""File unarchive: an archive unpacked into a folder, all of it or none."""
import bz2
import errno
import gzip
import io
import logging
import lzma
import os
import random
import shutil
import stat
import struct
import subprocess
import tarfile
import time
import zipfile

import pytest

from src.v2 import load_job
from src.v2.components.file import file_unarchive
from src.v2.errors import JobRefusedError
from tests.v2.components.kit import job

from .test_file_actions_kit import action, filled, on_v2, tree

try:
    from compression import zstd
except ImportError:  # before Python 3.14
    zstd = None

needs_zstd = pytest.mark.skipif(zstd is None, reason="Zstandard is in the standard library from Python 3.14")
LONG_AGO = 1_700_000_000
HELD = {"a.csv": b"a;1\n", "sub/b.txt": b"bee", "sub/deep/c.csv": b"c;3\n"}
UNPACKED = {"a.csv": b"a;1\n", "sub/": None, "sub/b.txt": b"bee", "sub/deep/": None, "sub/deep/c.csv": b"c;3\n"}


def unarchive(kind="FileUnarchive", **config):
    return action("open", kind, **config)


def zip_of(entries, **more):
    """The bytes of a zip archive of these entries; a name that ends in / is a folder."""
    packed = io.BytesIO()
    with zipfile.ZipFile(packed, "w", zipfile.ZIP_DEFLATED) as held:
        for name, data in entries.items():
            info = zipfile.ZipInfo(name, date_time=time.localtime(LONG_AGO)[:6])
            info.external_attr = (0o40755 if name.endswith("/") else 0o100644) << 16
            held.writestr(info, data or b"")
        for name, data in more.items():
            held.writestr(name, data)
    return packed.getvalue()


def tar_of(entries, how="w", extra=()):
    """The bytes of a tar archive of these entries, and of the members given ready-made."""
    packed = io.BytesIO()
    with tarfile.open(fileobj=packed, mode=how) as held:
        for name, data in entries.items():
            member = tarfile.TarInfo(name.rstrip("/"))
            member.mtime, member.mode = LONG_AGO, 0o644
            if name.endswith("/"):
                member.type, member.mode = tarfile.DIRTYPE, 0o755
                held.addfile(member)
            else:
                member.size = len(data)
                held.addfile(member, io.BytesIO(data))
        for member, data in extra:
            held.addfile(member, io.BytesIO(data) if data is not None else None)
    return packed.getvalue()


def member(name, **fields):
    made = tarfile.TarInfo(name)
    made.mtime = LONG_AGO
    for field, value in fields.items():
        setattr(made, field, value)
    return made


def ran(tmp_path, files, **config):
    """Run one unarchive in a folder of these files; returns how it ended and the folder."""
    folder = filled(tmp_path, files)
    return on_v2(job([unarchive(**config)], []), folder), folder


def refusals(made):
    with pytest.raises(JobRefusedError) as refused:
        load_job(made)
    return [(refusal.key, refusal.reason) for refusal in refused.value.report]


# ------------------------------------------------------------------
# Every kind of archive, told from what it holds
# ------------------------------------------------------------------

@pytest.mark.parametrize("name, packed", [
    ("in.zip", zip_of(HELD)), ("in.dat", zip_of(HELD)), ("in.tar", tar_of(HELD)), ("in.tar.gz", tar_of(HELD, "w:gz")),
    ("in.zip.txt", tar_of(HELD, "w:gz")), ("in.tar.bz2", tar_of(HELD, "w:bz2")), ("in.tar.xz", tar_of(HELD, "w:xz")),
], ids=["zip", "zip under another name", "tar", "tar.gz", "tar.gz under another name", "tar.bz2", "tar.xz"])
def test_archive_is_unpacked_into_the_folder_with_the_paths_and_the_times_of_its_entries(tmp_path, name, packed):
    result, folder = ran(tmp_path, {name: packed, "out/was_there.txt": b"stays"}, zipfile=name, directory="out")
    assert result.status == "success", result.error
    assert tree(folder / "out") == dict(UNPACKED, **{"was_there.txt": b"stays"})
    assert (folder / name).read_bytes() == packed
    assert int(os.stat(folder / "out/sub/b.txt").st_mtime) == LONG_AGO
    assert sorted(path.name for path in (folder / "out").iterdir()) == ["a.csv", "sub", "was_there.txt"]


def test_compressed_file_that_holds_a_zip_is_unpacked_as_the_one_file_it_is(tmp_path):
    # Not compressed at all: the zip stands in the file byte for byte, and Python would take the file for a zip.
    inner = zip_of(HELD)
    packed = gzip.compress(inner, compresslevel=0)
    assert zipfile.is_zipfile(io.BytesIO(packed))
    result, folder = ran(tmp_path, {"in.zip.gz": packed}, zipfile="in.zip.gz", directory="out")
    assert result.status == "success", result.error
    assert tree(folder / "out") == {"in.zip": inner}


def test_tar_that_holds_a_zip_is_unpacked_as_the_tar_it_is(tmp_path):
    inner = zip_of(HELD)
    result, folder = ran(tmp_path, {"in.tar": tar_of({"inner.zip": inner})}, zipfile="in.tar", directory="out")
    assert result.status == "success", result.error
    assert tree(folder / "out") == {"inner.zip": inner}


@needs_zstd
def test_tar_with_zstandard(tmp_path):
    result, folder = ran(tmp_path, {"in.tar.zst": tar_of(HELD, "w:zst")}, zipfile="in.tar.zst", directory="out")
    assert result.status == "success", result.error
    assert tree(folder / "out") == UNPACKED


@pytest.mark.parametrize("name, pack", [("a.csv.gz", gzip.compress), ("a.csv.bz2", bz2.compress), ("a.csv.xz", lzma.compress)])
def test_one_file_compressed_by_itself_loses_the_ending_of_its_name_and_has_the_time_of_the_archive(tmp_path, name, pack):
    folder = filled(tmp_path, {name: pack(b"a;1\n")})
    os.utime(folder / name, (LONG_AGO, LONG_AGO))
    result = on_v2(job([unarchive(zipfile=name, directory="out")], []), folder)
    assert result.status == "success", result.error
    assert tree(folder / "out") == {"a.csv": b"a;1\n"}
    assert int(os.stat(folder / "out/a.csv").st_mtime) == LONG_AGO


@needs_zstd
def test_one_file_compressed_with_zstandard(tmp_path):
    result, folder = ran(tmp_path, {"a.csv.zst": zstd.compress(b"a;1\n")}, zipfile="a.csv.zst", directory="out")
    assert result.status == "success" and tree(folder / "out") == {"a.csv": b"a;1\n"}


def test_one_compressed_file_whose_name_does_not_say_so_fails_the_job(tmp_path):
    result, folder = ran(tmp_path, {"data": gzip.compress(b"x")}, zipfile="data", directory="out")
    assert (result.status, result.error) == (
        "failed", "'data' is one file compressed with gzip, and its name does not end in .gz: there is no name to "
                  "unpack it under")
    assert not (folder / "out").exists()


@pytest.mark.parametrize("data", [b"just text\n", b""])
def test_file_that_is_no_archive_fails_the_job(tmp_path, data):
    result, folder = ran(tmp_path, {"in.zip": data}, zipfile="in.zip", directory="out")
    assert (result.status, result.error) == (
        "failed", "'in.zip' is no archive v2 can unpack: it is neither a zip nor a tar archive, nor one file "
                  "compressed with gzip, bzip2, xz or Zstandard")
    assert not (folder / "out").exists()


ZEROS_FIRST = b"\x00" * 1024 + b"REAL PAYLOAD\n" * 100


@pytest.mark.parametrize("name, pack", [("dump.bin.gz", gzip.compress), ("dump.bin.bz2", bz2.compress),
                                        ("dump.bin.xz", lzma.compress), ("dump.tar.gz", gzip.compress)])
def test_one_compressed_file_that_starts_with_zero_bytes_is_unpacked_as_the_file_it_is(tmp_path, name, pack):
    result, folder = ran(tmp_path, {name: pack(ZEROS_FIRST)}, zipfile=name, directory="out")
    assert result.status == "success", result.error
    assert tree(folder / "out") == {name.rsplit(".", 1)[0]: ZEROS_FIRST}
    assert result.global_map["open_NB_FILE"] == 1


@pytest.mark.parametrize("name, data", [("dump.bin", ZEROS_FIRST), ("dump.tar", ZEROS_FIRST), ("zeros.bin", b"\x00" * 10240)],
                         ids=["zero bytes and then others", "the same under the name of a tar", "zero bytes and nothing else"])
def test_file_that_starts_with_zero_bytes_and_is_no_archive_fails_the_job(tmp_path, name, data):
    result, folder = ran(tmp_path, {name: data}, zipfile=name, directory="out")
    assert (result.status, result.error) == (
        "failed", f"'{name}' is no archive v2 can unpack: it is neither a zip nor a tar archive, nor one file "
                  "compressed with gzip, bzip2, xz or Zstandard")
    assert not (folder / "out").exists()


@pytest.mark.parametrize("name, packed", [
    ("empty.tar", tar_of({})), ("empty.tar.gz", tar_of({}, "w:gz")), ("empty.tgz", gzip.compress(tar_of({}))),
    ("EMPTY.TAR.XZ", tar_of({}, "w:xz")),
], ids=["tar", "tar.gz", "tgz", "tar.xz in capitals"])
def test_tar_with_no_entries_is_told_by_its_name_and_unpacks_to_nothing(tmp_path, name, packed):
    result, folder = ran(tmp_path, {name: packed}, zipfile=name, directory="out")
    assert result.status == "success", result.error
    assert tree(folder / "out") == {} and result.global_map["open_NB_FILE"] == 0


def test_archive_compressed_in_a_way_this_python_does_not_read_fails_the_job_and_says_which(tmp_path, monkeypatch):
    monkeypatch.setattr(file_unarchive, "_PACKED", tuple(
        (magic, name, None if name == "Zstandard" else opener, ending) for magic, name, opener, ending in file_unarchive._PACKED))
    result, folder = ran(tmp_path, {"in.tar.zst": b"\x28\xb5\x2f\xfd" + b"x" * 40}, zipfile="in.tar.zst", directory="out")
    assert result.status == "failed" and not (folder / "out").exists()
    assert result.error.startswith("'in.tar.zst' is compressed with Zstandard, which Python reads from 3.14 on, and this is Python 3.")


def test_archive_with_no_entries_unpacks_to_nothing(tmp_path):
    result, folder = ran(tmp_path, {"in.zip": zip_of({})}, zipfile="in.zip", directory="out")
    assert result.status == "success", result.error
    assert tree(folder / "out") == {} and result.global_map["open_NB_FILE"] == 0
    assert "open_CURRENT_FILE" not in result.global_map


# ------------------------------------------------------------------
# Where the files land
# ------------------------------------------------------------------

def test_folder_is_made_with_the_folders_above_it(tmp_path):
    result, folder = ran(tmp_path, {"in.zip": zip_of(HELD)}, zipfile="in.zip", directory="made/deep/out")
    assert result.status == "success" and tree(folder / "made/deep/out") == UNPACKED


@pytest.mark.parametrize("name, root", [
    ("data.zip", "data"), ("data.tar.gz", "data"), ("data.v2.tgz", "data.v2"), ("Data.TAR.GZ", "Data"), ("data", "data")])
def test_rootname_unpacks_under_a_folder_named_after_the_archive(tmp_path, name, root):
    packed = tar_of(HELD, "w:gz") if "gz" in name.lower() else zip_of(HELD)
    result, folder = ran(tmp_path, {"in/" + name: packed}, zipfile="in/" + name, directory="out", rootname=True)
    assert result.status == "success", result.error
    assert sorted(path.name for path in (folder / "out").iterdir()) == [root]
    assert tree(folder / "out" / root) == UNPACKED


@pytest.mark.parametrize("key", ["extractpath", "extract_path"])
def test_without_their_paths_the_files_land_in_the_folder_itself(tmp_path, key):
    packed = zip_of(dict(HELD, **{"empty/": None}))
    result, folder = ran(tmp_path, {"in.zip": packed}, zipfile="in.zip", directory="out", **{key: False})
    assert result.status == "success", result.error
    assert tree(folder / "out") == {"a.csv": b"a;1\n", "b.txt": b"bee", "c.csv": b"c;3\n"}


def test_two_files_of_one_name_without_their_paths_fail_the_job(tmp_path):
    packed = tar_of({"one/a.csv": b"1", "two/a.csv": b"2"})
    result, folder = ran(tmp_path, {"in.tar": packed, "out/kept.txt": b"k"}, zipfile="in.tar", directory="out", extractpath=False)
    assert (result.status, result.error) == (
        "failed", "'one/a.csv' and 'two/a.csv' of 'in.tar' would both be 'a.csv' with their folders dropped: nothing "
                  "is unpacked")
    assert tree(folder / "out") == {"kept.txt": b"k"}


def test_folder_the_archive_names_is_made_also_when_it_holds_nothing(tmp_path):
    for at, packed in enumerate((zip_of({"empty/": None, "a.csv": b"x"}), tar_of({"empty/": None, "a.csv": b"x"}))):
        result, folder = ran(tmp_path / str(at), {"in.arc": packed}, zipfile="in.arc", directory="out")
        assert result.status == "success", result.error
        assert tree(folder / "out") == {"a.csv": b"x", "empty/": None}


def test_file_of_the_archive_where_a_folder_is_fails_the_job_before_anything_is_moved(tmp_path):
    packed = zip_of({"a.csv": b"x", "sub": b"a file named as the folder is"})
    result, folder = ran(tmp_path, {"in.zip": packed, "out/sub/kept.txt": b"k"}, zipfile="in.zip", directory="out")
    assert (result.status, result.error) == (
        "failed", "'sub' of 'in.zip' is a file, and 'out/sub' is a folder: nothing is unpacked")
    assert tree(folder / "out") == {"sub/": None, "sub/kept.txt": b"k"}


def test_entry_with_a_time_no_clock_shows_is_unpacked_all_the_same(tmp_path):
    raw = bytearray(zip_of({"a.csv": b"x"}))
    struct.pack_into("<HH", raw, 10, 0xFFFF, 0xFFFF)
    struct.pack_into("<HH", raw, raw.find(b"PK\x01\x02") + 12, 0xFFFF, 0xFFFF)
    result, folder = ran(tmp_path, {"in.zip": bytes(raw)}, zipfile="in.zip", directory="out")
    assert result.status == "success", result.error
    assert tree(folder / "out") == {"a.csv": b"x"}


def test_name_written_with_a_dot_for_the_folder_itself_is_the_same_name_without(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="src.v2")
    packed = tar_of({"./a.csv": b"first", "a.csv": b"second", "./sub/./b.txt": b"bee"})
    result, folder = ran(tmp_path, {"in.tar": packed}, zipfile="in.tar", directory="out", printout=True)
    assert result.status == "success", result.error
    assert tree(folder / "out") == {"a.csv": b"second", "sub/": None, "sub/b.txt": b"bee"}
    assert result.global_map["open_NB_FILE"] == 2
    said = [record.getMessage() for record in caplog.records if record.getMessage().startswith("[open] unpacked '")]
    assert said == ["[open] unpacked 'out/a.csv'", "[open] unpacked 'out/sub/b.txt'"]


def test_file_that_is_there_is_written_over_and_the_last_of_two_entries_of_one_name_stays(tmp_path):
    packed = tar_of({"a.csv": b"first"}, extra=[(member("a.csv", size=6), b"second")])
    result, folder = ran(tmp_path, {"in.tar": packed, "out/a.csv": b"of an earlier run"}, zipfile="in.tar", directory="out")
    assert result.status == "success", result.error
    assert tree(folder / "out") == {"a.csv": b"second"} and result.global_map["open_NB_FILE"] == 1


# ------------------------------------------------------------------
# Names that would do harm
# ------------------------------------------------------------------

@pytest.mark.parametrize("packed, named", [
    (zip_of({"ok.txt": b"x"}, **{"../evil.txt": b"e"}), "../evil.txt"),
    (zip_of({"ok.txt": b"x"}, **{"sub/../../evil.txt": b"e"}), "sub/../../evil.txt"),
    (zip_of({"ok.txt": b"x"}, **{"sub\\..\\..\\evil.txt": b"e"}), "sub\\..\\..\\evil.txt"),
    (tar_of({"ok.txt": b"x", "../evil.txt": b"e"}), "../evil.txt"),
], ids=["zip", "zip, further in", "zip, backslashes", "tar"])
def test_name_that_climbs_out_of_the_folder_fails_the_job_and_nothing_is_unpacked(tmp_path, packed, named):
    result, folder = ran(tmp_path, {"in/in.arc": packed, "in/out/kept.txt": b"k"}, zipfile="in/in.arc", directory="in/out")
    assert result.status == "failed"
    assert result.error == (
        f"'in/in.arc' names '{named}', which would land outside the folder it is unpacked to: nothing is unpacked")
    assert tree(folder) == {"in/": None, "in/in.arc": packed, "in/out/": None, "in/out/kept.txt": b"k"}


@pytest.mark.parametrize("packed", [zip_of({}, **{"/abs/a.txt": b"x", "win\\b.txt": b"y"}),
                                    tar_of({"/abs/a.txt": b"x", "./win/b.txt": b"y"})], ids=["zip", "tar"])
def test_name_that_starts_at_the_root_lands_in_the_folder(tmp_path, packed):
    result, folder = ran(tmp_path, {"in.arc": packed}, zipfile="in.arc", directory="out")
    assert result.status == "success", result.error
    assert tree(folder / "out") == {"abs/": None, "abs/a.txt": b"x", "win/": None, "win/b.txt": b"y"}


def test_links_and_what_is_no_file_are_left_out_and_named(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="src.v2")
    link = zipfile.ZipInfo("z_link")
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    packed = io.BytesIO()
    with zipfile.ZipFile(packed, "w") as held:
        held.writestr("a.csv", b"x")
        held.writestr(link, "/etc/passwd")
    result, folder = ran(tmp_path, {"in.zip": packed.getvalue()}, zipfile="in.zip", directory="out")
    assert result.status == "success", result.error
    assert tree(folder / "out") == {"a.csv": b"x"}
    extra = [(member("inside", type=tarfile.SYMTYPE, linkname="a.csv"), None),
             (member("outside", type=tarfile.SYMTYPE, linkname="/etc/passwd"), None),
             (member("pipe", type=tarfile.FIFOTYPE), None), (member("same", type=tarfile.LNKTYPE, linkname="a.csv"), None)]
    result, folder = ran(tmp_path / "tar", {"in.tar": tar_of({"a.csv": b"x"}, extra=extra)}, zipfile="in.tar", directory="out")
    assert result.status == "success", result.error
    assert tree(folder / "out") == {"a.csv": b"x", "same": b"x"}
    assert [record.getMessage() for record in caplog.records] == [
        "[open] 1 link or special file in 'in.zip' is left out; the first: 'z_link'",
        "[open] 3 links or special files in 'in.tar' are left out; the first: 'inside'"]


def test_second_name_for_a_link_or_a_special_file_is_left_out_with_it_and_nothing_outside_is_touched(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="src.v2")
    folder = filled(tmp_path, {"elsewhere/victim.cfg": b"owner-only\n"})
    victim = folder / "elsewhere/victim.cfg"
    os.chmod(victim, 0o600)
    os.utime(victim, (LONG_AGO - 1000, LONG_AGO - 1000))
    extra = [(member("s", type=tarfile.SYMTYPE, linkname=str(victim)), None),
             (member("h", type=tarfile.LNKTYPE, linkname="s", mode=0o777), None),
             (member("p", type=tarfile.FIFOTYPE), None),
             (member("data.csv", type=tarfile.LNKTYPE, linkname="p", mode=0o644), None),
             (member("again.csv", type=tarfile.LNKTYPE, linkname="data.csv", mode=0o644), None)]
    (folder / "in.tar").write_bytes(tar_of({"a.csv": b"x"}, extra=extra))
    result = on_v2(job([unarchive(zipfile="in.tar", directory="out")], []), folder)
    assert result.status == "success", result.error
    # By name first: a pipe that had been planted would keep whoever reads it waiting.
    assert os.listdir(folder / "out") == ["a.csv"]
    assert tree(folder / "out") == {"a.csv": b"x"}
    assert (stat.S_IMODE(os.stat(victim).st_mode), int(os.stat(victim).st_mtime)) == (0o600, LONG_AGO - 1000)
    assert result.global_map["open_NB_FILE"] == 1
    assert [record.getMessage() for record in caplog.records] == [
        "[open] 5 links or special files in 'in.tar' are left out; the first: 's'"]


def test_second_name_for_a_file_is_a_file_of_its_own(tmp_path):
    extra = [(member("sub/same.csv", type=tarfile.LNKTYPE, linkname="./a.csv"), None)]
    result, folder = ran(tmp_path, {"in.tar": tar_of({"a.csv": b"x;1\n"}, extra=extra)}, zipfile="in.tar", directory="out")
    assert result.status == "success", result.error
    assert tree(folder / "out") == {"a.csv": b"x;1\n", "sub/": None, "sub/same.csv": b"x;1\n"}
    # Not one file under two names: what is later written to the one is not written to the other.
    assert os.stat(folder / "out/a.csv").st_ino != os.stat(folder / "out/sub/same.csv").st_ino
    assert int(os.stat(folder / "out/sub/same.csv").st_mtime) == LONG_AGO
    assert result.global_map["open_NB_FILE"] == 2


def test_last_of_two_tar_entries_of_one_name_stays_with_its_bytes_and_its_permissions(tmp_path):
    packed = tar_of({}, extra=[(member("a.csv", size=5, mode=0o600), b"first"), (member("b.csv", size=1, mode=0o644), b"b"),
                               (member("a.csv", size=6, mode=0o644), b"second")])
    before = os.umask(0o022)
    try:
        result, folder = ran(tmp_path, {"in.tar": packed}, zipfile="in.tar", directory="out")
    finally:
        os.umask(before)
    assert result.status == "success", result.error
    assert tree(folder / "out") == {"a.csv": b"second", "b.csv": b"b"}
    assert stat.S_IMODE(os.stat(folder / "out/a.csv").st_mode) == 0o644
    assert result.global_map["open_NB_FILE"] == 2


def test_link_in_the_folder_that_leads_out_of_it_is_not_written_through(tmp_path):
    folder = filled(tmp_path, {"in.zip": zip_of({"a.csv": b"x", "sub/b.txt": b"y"}), "out/": None, "elsewhere/": None})
    os.symlink("../elsewhere", folder / "out/sub")
    result = on_v2(job([unarchive(zipfile="in.zip", directory="out")], []), folder)
    assert (result.status, result.error) == (
        "failed", "'sub/b.txt' of 'in.zip' would be written through a link that leads out of 'out': nothing is unpacked")
    assert tree(folder / "elsewhere") == {} and not (folder / "out/a.csv").exists()


@pytest.mark.parametrize("mask, modes", [
    (0o022, {"run.sh": 0o755, "open.csv": 0o644, "shut.csv": 0o600, "odd.csv": 0o644}),
    (0o027, {"run.sh": 0o750, "open.csv": 0o640, "shut.csv": 0o600, "odd.csv": 0o640}),
    # Where a new file gets everything, what an entry may not have is still not given.
    (0o000, {"run.sh": 0o755, "open.csv": 0o644, "shut.csv": 0o600, "odd.csv": 0o644}),
])
def test_permissions_that_would_do_harm_are_not_carried_over_nor_more_than_a_new_file_gets_here(tmp_path, mask, modes):
    # `odd.csv` may be run by others and not by its owner: then by none.
    packed = tar_of({}, extra=[(member("run.sh", size=1, mode=0o6777), b"x"), (member("open.csv", size=1, mode=0o666), b"x"),
                               (member("shut.csv", size=1, mode=0o400), b"x"), (member("odd.csv", size=1, mode=0o655), b"x")])
    before = os.umask(mask)
    try:
        result, folder = ran(tmp_path, {"in.tar": packed}, zipfile="in.tar", directory="out")
    finally:
        os.umask(before)
    assert result.status == "success", result.error
    assert {name: stat.S_IMODE(os.stat(folder / "out" / name).st_mode) for name in modes} == modes


# ------------------------------------------------------------------
# All of it or none
# ------------------------------------------------------------------

def damaged_zip():
    good = zip_of({"a.csv": b"first file " * 50, "b.csv": b"second file " * 50})
    raw = bytearray(good)
    second = raw.find(b"PK\x03\x04", 4)
    raw[second + 40] ^= 0xFF
    return bytes(raw)


@pytest.mark.parametrize("name, packed, said", [
    ("in.zip", damaged_zip(), "'in.zip' is damaged: 'b.csv' in it cannot be unpacked"),
    ("in.tar.gz", tar_of({"a.csv": b"x" * 50, "b.csv": os.urandom(200_000)}, "w:gz")[:60_000],
     "'in.tar.gz' is damaged: it ends before its end"),
    ("b.csv.gz", gzip.compress(os.urandom(100_000))[:50_000], "'b.csv.gz' is damaged: it ends before its end"),
], ids=["zip", "tar.gz cut short", "gzip cut short"])
def test_damaged_archive_fails_the_job_and_leaves_the_folder_as_it_was(tmp_path, name, packed, said):
    result, folder = ran(tmp_path, {name: packed, "out/kept.txt": b"k", "out/a.csv": b"of an earlier run"},
                         zipfile=name, directory="out")
    assert result.status == "failed" and result.error.startswith(said), result.error
    assert tree(folder / "out") == {"a.csv": b"of an earlier run", "kept.txt": b"k"}
    assert sorted(path.name for path in (folder / "out").iterdir()) == ["a.csv", "kept.txt"]


# Four files that each take 1536 bytes of a tar: a header of 512 and their 700 bytes filled up to 1024.
FOUR = {"a.csv": b"A" * 700, "b.csv": b"B" * 700, "c.csv": b"C" * 700, "d.csv": b"D" * 700}


def third_header_broken():
    raw = bytearray(tar_of(FOUR))
    raw[1536 * 2 + 10] ^= 0xFF
    return bytes(raw)


@pytest.mark.parametrize("packed, said", [
    (tar_of(FOUR)[:1536 * 2], "it ends before its end"),
    (tar_of(FOUR)[:1536 * 2 + 200], "it ends before its end"),
    (tar_of(FOUR)[:1536 * 2 + 512 + 100], "it ends before its end"),
    (tar_of(FOUR)[:1536 * 4], "it ends before its end"),
    (third_header_broken(), "what follows 'b.csv' in it is no entry"),
], ids=["cut between two entries", "cut inside the header of an entry", "cut inside the bytes of an entry",
        "cut before its end mark", "a header that is not whole"])
@pytest.mark.parametrize("name, pack", [("in.tar", bytes), ("in.tar.gz", gzip.compress), ("in.tar.bz2", bz2.compress),
                                        ("in.tar.xz", lzma.compress)])
def test_tar_that_is_cut_short_or_broken_in_the_middle_unpacks_nothing(tmp_path, name, pack, packed, said):
    result, folder = ran(tmp_path, {name: pack(packed), "out/kept.txt": b"k"}, zipfile=name, directory="out")
    assert (result.status, result.error) == ("failed", f"'{name}' is damaged: {said}; nothing is unpacked")
    assert tree(folder / "out") == {"kept.txt": b"k"}


def with_check(data):
    return zstd.compress(data, options={zstd.CompressionParameter.checksum_flag: 1})


@pytest.mark.parametrize("name, pack", [
    ("in.tar.gz", gzip.compress), ("in.tar.bz2", bz2.compress), ("in.tar.xz", lzma.compress),
    pytest.param("in.tar.zst", with_check, marks=needs_zstd),
])
def test_compressed_tar_with_one_bit_changed_is_never_unpacked_in_part(tmp_path, name, pack):
    drawn = random.Random(7)
    files = {f"f{number:02d}.csv": "".join(f"{number};{row};{drawn.random()}\n" for row in range(200)).encode()
             for number in range(20)}
    packed = pack(tar_of(files))
    ended = set()
    for trial in range(30):
        raw = bytearray(packed)
        raw[drawn.randrange(40, len(raw) - 40)] ^= 1 << drawn.randrange(8)
        result, folder = ran(tmp_path / str(trial), {name: bytes(raw)}, zipfile=name, directory="out")
        ended.add(result.status)
        if result.status == "success":
            assert tree(folder / "out") == files
        else:
            assert result.error.startswith(f"'{name}' is damaged: ") and result.error.endswith("; nothing is unpacked")
            assert not (folder / "out").exists()
    assert "failed" in ended


def test_tar_with_one_byte_more_than_its_check_sum_allows_fails_the_job(tmp_path):
    raw = bytearray(tar_of(FOUR, "w:gz"))
    raw[-6] ^= 0xFF
    result, folder = ran(tmp_path, {"in.tar.gz": bytes(raw), "out/kept.txt": b"k"}, zipfile="in.tar.gz", directory="out")
    assert result.status == "failed"
    assert result.error.startswith("'in.tar.gz' is damaged: CRC check failed") and result.error.endswith("; nothing is unpacked")
    assert tree(folder / "out") == {"kept.txt": b"k"}


def test_what_stands_after_the_end_of_a_tar_is_not_unpacked_and_is_said(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="src.v2")
    joined = tar_of({"a.csv": b"a"}) + tar_of({"b.csv": b"b"})
    for name, packed in (("in.tar", joined), ("in.tar.gz", gzip.compress(joined))):
        result, folder = ran(tmp_path / name, {name: packed}, zipfile=name, directory="out")
        assert result.status == "success", result.error
        assert tree(folder / "out") == {"a.csv": b"a"}
    assert [record.getMessage() for record in caplog.records] == [
        f"[open] '{name}' goes on after its end, and what stands there is not unpacked: it may be more than one archive "
        "joined" for name in ("in.tar", "in.tar.gz")]


@pytest.mark.parametrize("name, packed", [
    ("in.tar", tar_of({"a.csv": b"x"}, extra=[(member(".", size=1), b"y")])),
    ("in.zip", zip_of({"a.csv": b"x"}, **{".": b"y"})),
], ids=["tar", "zip"])
def test_file_without_a_name_in_an_archive_fails_the_job(tmp_path, name, packed):
    result, folder = ran(tmp_path, {name: packed, "out/kept.txt": b"k"}, zipfile=name, directory="out")
    assert (result.status, result.error) == (
        "failed", f"'{name}' is damaged: it holds a file without a name; nothing is unpacked")
    assert tree(folder / "out") == {"kept.txt": b"k"}


def test_tar_entry_with_a_time_no_clock_shows_is_unpacked_all_the_same(tmp_path):
    packed = tar_of({}, extra=[(member("a.csv", size=1, mtime=float(2 ** 70)), b"x")])
    result, folder = ran(tmp_path, {"in.tar": packed}, zipfile="in.tar", directory="out")
    assert result.status == "success", result.error
    assert tree(folder / "out") == {"a.csv": b"x"}


# ------------------------------------------------------------------
# The files moved to their places, all of them or none
# ------------------------------------------------------------------

def test_failure_while_the_files_are_moved_puts_back_what_was_moved(tmp_path):
    packed = zip_of({"a.csv": b"NEW", "new/n.csv": b"n", "deep/er/": None, "b/c.csv": b"c"})
    result, folder = ran(tmp_path, {"in.zip": packed, "out/a.csv": b"of an earlier run", "out/b": b"a file named b"},
                         zipfile="in.zip", directory="out")
    assert (result.status, result.error) == (
        "failed", "'in.zip' cannot be unpacked into 'out': file exists: 'out/b'; nothing is unpacked")
    assert tree(folder / "out") == {"a.csv": b"of an earlier run", "b": b"a file named b"}
    assert sorted(os.listdir(folder / "out")) == ["a.csv", "b"]


def test_folder_that_may_not_be_written_to_fails_the_job_and_leaves_the_files_that_were_there(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root may write everywhere")
    packed = zip_of({"a.csv": b"NEW", "sub/c.csv": b"c"})
    folder = filled(tmp_path, {"in.zip": packed, "out/a.csv": b"of an earlier run", "out/sub/": None})
    os.chmod(folder / "out/sub", 0o500)
    try:
        result = on_v2(job([unarchive(zipfile="in.zip", directory="out")], []), folder)
    finally:
        os.chmod(folder / "out/sub", 0o700)
    assert (result.status, result.error) == (
        "failed", "'in.zip' cannot be unpacked into 'out': permission denied: 'sub/c.csv'; nothing is unpacked")
    assert tree(folder / "out") == {"a.csv": b"of an earlier run", "sub/": None}


def test_disk_that_fills_up_while_the_archive_is_unpacked_fails_the_job_and_leaves_the_folder_as_it_was(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "copyfileobj", lambda *given: (_ for _ in ()).throw(OSError(errno.ENOSPC, "No space left on device")))
    result, folder = ran(tmp_path, {"in.zip": zip_of(HELD), "out/kept.txt": b"k"}, zipfile="in.zip", directory="out")
    assert (result.status, result.error) == (
        "failed", "'in.zip' cannot be unpacked into 'out': no space left on device; nothing is unpacked")
    assert tree(folder / "out") == {"kept.txt": b"k"} and os.listdir(folder / "out") == ["kept.txt"]


def stopped_at(name, monkeypatch):
    """Make the file of this name fail to land: the move from where it was unpacked to its place."""
    really = os.replace

    def replace(source, target):
        if f"{os.sep}new{os.sep}" in str(source) and os.path.basename(str(target)) == name:
            raise OSError(errno.EIO, "Input/output error", str(source))
        return really(source, target)

    monkeypatch.setattr(os, "replace", replace)


def test_file_that_fails_to_land_where_one_was_leaves_the_one_that_was(tmp_path, monkeypatch):
    stopped_at("c.csv", monkeypatch)
    packed = zip_of({"a.csv": b"NEW A", "c.csv": b"NEW C"})
    result, folder = ran(tmp_path, {"in.zip": packed, "out/a.csv": b"old a", "out/c.csv": b"old c"},
                         zipfile="in.zip", directory="out")
    assert (result.status, result.error) == (
        "failed", "'in.zip' cannot be unpacked into 'out': input/output error: 'c.csv'; nothing is unpacked")
    assert tree(folder / "out") == {"a.csv": b"old a", "c.csv": b"old c"}
    assert sorted(os.listdir(folder / "out")) == ["a.csv", "c.csv"]


def test_file_that_was_there_and_cannot_be_put_back_is_kept_where_it_waits_and_the_job_says_where(tmp_path, monkeypatch):
    really = os.replace

    def replace(source, target):
        landing = f"{os.sep}new{os.sep}" in str(source) and os.path.basename(str(target)) == "c.csv"
        going_back = f"{os.sep}old{os.sep}" in str(source) and os.path.basename(str(target)) == "a.csv"
        if landing or going_back:
            raise OSError(errno.EIO, "Input/output error", str(source))
        return really(source, target)

    monkeypatch.setattr(os, "replace", replace)
    packed = zip_of({"a.csv": b"NEW A", "c.csv": b"NEW C"})
    result, folder = ran(tmp_path, {"in.zip": packed, "out/a.csv": b"old a", "out/c.csv": b"old c"},
                         zipfile="in.zip", directory="out")
    kept = f"out/.in.zip.open.v2tmp{os.getpid()}/old"
    assert (result.status, result.error) == (
        "failed", "'in.zip' cannot be unpacked into 'out': input/output error: 'c.csv'; and 'out' could not be put back "
                  f"as it was (input/output error: '{kept}/0'): the files that were there and are not back are kept in "
                  f"'{kept}'")
    assert tree(folder / kept) == {"0": b"old a"}
    assert sorted(os.listdir(folder / "out")) == [f".in.zip.open.v2tmp{os.getpid()}", "c.csv"]
    assert (folder / "out/c.csv").read_bytes() == b"old c"
    assert not (folder / kept).parent.joinpath("new").exists()


def test_new_file_that_cannot_be_taken_away_again_is_said_and_nothing_else_is_left(tmp_path, monkeypatch):
    stopped_at("c.csv", monkeypatch)
    really = os.remove

    def remove(path, *more, **kept):
        if os.path.basename(str(path)) == "a.csv":
            raise OSError(errno.EIO, "Input/output error", str(path))
        return really(path, *more, **kept)

    monkeypatch.setattr(os, "remove", remove)
    packed = zip_of({"a.csv": b"NEW A", "c.csv": b"NEW C"})
    result, folder = ran(tmp_path, {"in.zip": packed, "out/c.csv": b"old c"}, zipfile="in.zip", directory="out")
    assert (result.status, result.error) == (
        "failed", "'in.zip' cannot be unpacked into 'out': input/output error: 'c.csv'; and 'out' could not be put back "
                  "as it was (input/output error: 'out/a.csv')")
    assert tree(folder / "out") == {"a.csv": b"NEW A", "c.csv": b"old c"}
    assert sorted(os.listdir(folder / "out")) == ["a.csv", "c.csv"]


def test_reader_that_stopped_elsewhere_than_at_the_last_piece_read_is_read_there_again():
    watched = file_unarchive._Watched(io.BytesIO(bytes(range(256)) * 8))
    watched.seek(1024)
    assert watched.read(4) == bytes(range(4)) and watched.tell() == 1028
    assert watched.block_at(1024) == bytes(range(4))
    assert watched.block_at(512) == (bytes(range(256)) * 2)
    assert watched.block_at(2040) == bytes(range(248, 256))


def test_folder_made_for_the_archive_is_taken_away_also_when_the_files_cannot_be_moved_back(tmp_path, monkeypatch):
    stopped_at("c.csv", monkeypatch)
    monkeypatch.setattr(os, "remove", lambda path, *more, **kept: (_ for _ in ()).throw(OSError(errno.EIO, "Input/output error", str(path))))
    packed = zip_of({"a.csv": b"NEW A", "c.csv": b"NEW C"})
    result, folder = ran(tmp_path, {"in.zip": packed}, zipfile="in.zip", directory="made/out")
    assert (result.status, result.error) == (
        "failed", "'in.zip' cannot be unpacked into 'made/out': input/output error: 'c.csv'; nothing is unpacked")
    assert not (folder / "made").exists()


def test_link_planted_where_the_archive_is_unpacked_before_its_files_are_moved_is_not_written_through(tmp_path):
    folder = filled(tmp_path, {"in.zip": zip_of(HELD), "out/": None, "elsewhere/": None})
    os.symlink(folder / "elsewhere", folder / "out" / f".in.zip.open.v2tmp{os.getpid()}")
    result = on_v2(job([unarchive(zipfile="in.zip", directory="out")], []), folder)
    assert result.status == "success", result.error
    assert tree(folder / "out") == UNPACKED and tree(folder / "elsewhere") == {}


def test_archive_that_gives_one_name_to_a_file_and_to_a_folder_fails_the_job_and_names_the_entry(tmp_path):
    packed = zip_of({"a": b"a file", "a/b.txt": b"in a folder of the same name"})
    result, folder = ran(tmp_path, {"in.zip": packed, "out/kept.txt": b"k"}, zipfile="in.zip", directory="out")
    assert (result.status, result.error) == (
        "failed", "'in.zip' cannot be unpacked into 'out': file exists: 'a'; nothing is unpacked")
    assert tree(folder / "out") == {"kept.txt": b"k"}


def test_archive_whose_check_sum_is_wrong_fails_the_job_in_pythons_words_for_it(tmp_path):
    raw = bytearray(gzip.compress(b"line\n" * 1000))
    raw[-6] ^= 0xFF
    result, folder = ran(tmp_path, {"a.csv.gz": bytes(raw)}, zipfile="a.csv.gz", directory="out")
    assert result.status == "failed"
    assert result.error.startswith("'a.csv.gz' is damaged: CRC check failed") and result.error.endswith("; nothing is unpacked")
    assert not (folder / "out").exists()


def test_archive_that_cannot_be_read_fails_the_job_in_plain_words(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root may read everything")
    folder = filled(tmp_path, {"in.zip": zip_of(HELD)})
    os.chmod(folder / "in.zip", 0o000)
    result = on_v2(job([unarchive(zipfile="in.zip", directory="out")], []), folder)
    assert (result.status, result.error) == ("failed", "'in.zip' cannot be read: permission denied")
    assert not (folder / "out").exists()


def test_entry_that_names_the_folder_itself_is_passed_over(tmp_path):
    whole = tar_of({"a.csv": b"x"}, extra=[(member(".", type=tarfile.DIRTYPE, mode=0o755), None)])
    result, folder = ran(tmp_path, {"in.tar": whole}, zipfile="in.tar", directory="out")
    assert result.status == "success" and tree(folder / "out") == {"a.csv": b"x"}
    result, folder = ran(tmp_path / "zip", {"in.zip": zip_of({"/": None, "a.csv": b"x"})}, zipfile="in.zip", directory="out")
    assert result.status == "success" and tree(folder / "out") == {"a.csv": b"x"}


@pytest.mark.parametrize("linkname, said", [
    ("../outside.txt", "'in.tar' holds 'second', which leads out of the folder it is unpacked to: nothing is unpacked"),
    ("not_there.txt", "'in.tar' is damaged: 'second' is a second name for a file that is not in it; nothing is unpacked"),
], ids=["out of the folder", "to nothing"])
def test_second_name_for_a_file_that_is_not_in_the_archive_fails_the_job(tmp_path, linkname, said):
    packed = tar_of({"a.csv": b"x"}, extra=[(member("second", type=tarfile.LNKTYPE, linkname=linkname), None)])
    result, folder = ran(tmp_path, {"in.tar": packed, "out/kept.txt": b"k"}, zipfile="in.tar", directory="out")
    assert (result.status, result.error) == ("failed", said)
    assert tree(folder / "out") == {"kept.txt": b"k"}


def test_folder_made_for_an_archive_that_fails_is_taken_away_again(tmp_path):
    result, folder = ran(tmp_path, {"in.zip": damaged_zip(), "made/": None}, zipfile="in.zip", directory="made/deep/out")
    assert result.status == "failed"
    assert tree(folder / "made") == {}


def test_zip_that_would_not_fit_fails_the_job_before_anything_is_unpacked(tmp_path, monkeypatch):
    usage = shutil.disk_usage(tmp_path)
    monkeypatch.setattr(shutil, "disk_usage", lambda path: usage._replace(free=10))
    result, folder = ran(tmp_path, {"in.zip": zip_of(HELD)}, zipfile="in.zip", directory="out")
    assert (result.status, result.error) == (
        "failed", "'in.zip' unpacks to 11 bytes, and there are 10 bytes free where 'out' is: nothing is unpacked")
    assert not (folder / "out").exists()
    monkeypatch.setattr(shutil, "disk_usage", lambda path: usage._replace(free=11))
    result, folder = ran(tmp_path / "fits", {"in.zip": zip_of(HELD)}, zipfile="in.zip", directory="out")
    assert result.status == "success" and tree(folder / "out") == UNPACKED


def test_archive_that_is_not_there_a_folder_and_a_pipe_fail_the_job(tmp_path):
    folder = filled(tmp_path, {"dir/": None})
    os.mkfifo(folder / "pipe")
    for name, said in (("nope.zip", "File not found: 'nope.zip'"), ("dir", "'dir' cannot be unpacked: it is a folder"),
                       ("pipe", "'pipe' cannot be unpacked: it is no file, but a pipe or a device")):
        result = on_v2(job([unarchive(zipfile=name, directory="out")], []), folder)
        assert (result.status, result.error) == ("failed", said)
    assert not (folder / "out").exists()


def test_folder_that_cannot_be_made_fails_the_job_in_plain_words(tmp_path):
    result, _ = ran(tmp_path, {"in.zip": zip_of(HELD), "taken": b"a file"}, zipfile="in.zip", directory="taken/out")
    assert (result.status, result.error) == ("failed", "the folder 'taken/out' cannot be made: not a directory")


# ------------------------------------------------------------------
# Passwords, and the encoding of names
# ------------------------------------------------------------------

@pytest.fixture
def locked(tmp_path):
    """A zip the system's own zip locked with the password `s3cret`; skipped where there is no such command."""
    (tmp_path / "make").mkdir()
    (tmp_path / "make/a.csv").write_bytes(b"a;1\n")
    try:
        made = subprocess.run(["zip", "-q", "-P", "s3cret", "locked.zip", "a.csv"], cwd=tmp_path / "make", capture_output=True)
    except OSError:
        pytest.skip("no zip command to make a locked archive with")
    if made.returncode:
        pytest.skip("the zip command could not make a locked archive")
    return (tmp_path / "make/locked.zip").read_bytes()


def test_locked_zip_is_unpacked_with_its_password_which_no_log_shows(tmp_path, locked, caplog):
    caplog.set_level(logging.DEBUG, logger="src.v2")
    made = job([unarchive(zipfile="in.zip", directory="out", checkpassword=True, password="${context.word}")], [])
    made["context"] = {"Default": {"word": {"value": "s3cret", "type": "str"}}}
    folder = filled(tmp_path / "run", {"in.zip": locked})
    result = on_v2(made, folder)
    assert result.status == "success", result.error
    assert tree(folder / "out") == {"a.csv": b"a;1\n"}
    assert not [record.getMessage() for record in caplog.records if "s3cret" in record.getMessage()]


@pytest.mark.parametrize("config, said", [
    (dict(checkpassword=True, password="wrong"), "the password does not open 'a.csv' of 'in.zip'"),
    (dict(checkpassword=True), "the password does not open 'a.csv' of 'in.zip'"),
    (dict(password="s3cret"), "'a.csv' of 'in.zip' is locked with a password: give it with `checkpassword` and `password`"),
], ids=["wrong", "none", "not to be used"])
def test_locked_zip_without_its_password_fails_the_job(tmp_path, locked, config, said):
    result, folder = ran(tmp_path / "run", {"in.zip": locked}, zipfile="in.zip", directory="out", **config)
    assert (result.status, result.error) == ("failed", said)
    assert not (folder / "out").exists()


def test_entry_packed_in_a_way_python_cannot_read_fails_the_job_and_says_so(tmp_path):
    raw = bytearray(zip_of({"a.csv": b"hello " * 50}))
    struct.pack_into("<H", raw, 8, 99)
    struct.pack_into("<H", raw, raw.find(b"PK\x01\x02") + 10, 99)
    result, _ = ran(tmp_path, {"in.zip": bytes(raw)}, zipfile="in.zip", directory="out")
    assert (result.status, result.error) == (
        "failed", "'a.csv' of 'in.zip' is packed or locked in a way Python cannot read (AES encryption is one such way)")


def named_in(encoding_of_names):
    """A zip whose one entry is named caf<e acute>.csv in an encoding, with nothing in it saying which."""
    name = ("caf" + chr(233) + ".csv").encode(encoding_of_names)
    raw = zip_of({}, **{"x" * len(name): b"x"})
    return raw.replace(b"x" * len(name), name)


def test_names_are_read_as_utf_8_and_in_another_encoding_when_one_is_given(tmp_path):
    odd = "caf" + chr(233) + ".csv"
    result, folder = ran(tmp_path, {"in.zip": named_in("utf-8")}, zipfile="in.zip", directory="out")
    assert result.status == "success" and sorted(path.name for path in (folder / "out").iterdir()) == [odd]
    result, folder = ran(tmp_path / "latin", {"in.zip": named_in("iso-8859-15")}, zipfile="in.zip", directory="out",
                         use_encoding=True, encording="ISO-8859-15")
    assert result.status == "success" and sorted(path.name for path in (folder / "out").iterdir()) == [odd]


def test_encoding_of_names_is_not_looked_at_unless_it_is_to_be_used(tmp_path):
    odd = "caf" + chr(233) + ".csv"
    result, folder = ran(tmp_path, {"in.zip": named_in("utf-8")}, zipfile="in.zip", directory="out", use_encoding=False,
                         encording="ISO-8859-15")
    assert result.status == "success" and sorted(path.name for path in (folder / "out").iterdir()) == [odd]


def test_names_that_are_not_utf_8_fail_the_job_and_say_what_to_give(tmp_path):
    result, folder = ran(tmp_path, {"in.zip": named_in("iso-8859-15")}, zipfile="in.zip", directory="out")
    assert (result.status, result.error) == (
        "failed", "the names in 'in.zip' are not written in UTF-8: say how they are written with `use_encoding` and "
                  "`encording`")
    assert not (folder / "out").exists()


# ------------------------------------------------------------------
# What it leaves
# ------------------------------------------------------------------

def test_what_is_left_in_globalmap_and_said_in_the_log(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="src.v2")
    folder = filled(tmp_path, {"in.zip": zip_of(HELD)})
    made = dict(job([unarchive(zipfile="in.zip", directory="out")], []), run={"row_counts": True})
    result = on_v2(made, folder)
    assert result.counts["open"] == {"NB_LINE": 1, "NB_LINE_OK": 1, "NB_LINE_REJECT": 0}
    held = {key: value for key, value in result.global_map.items() if key.startswith("open_") and "NB_LINE" not in key}
    assert held == {"open_NB_FILE": 3, "open_CURRENT_FILE": "c.csv",
                    "open_CURRENT_FILEPATH": os.path.join(os.path.realpath(folder), "out/sub/deep/c.csv")}
    said = [record.getMessage() for record in caplog.records if record.getMessage().startswith("[open] unpacked")]
    assert said == ["[open] unpacked 3 files of 'in.zip' (zip) into 'out'"]


def test_printout_says_every_file_in_the_log(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="src.v2")
    ran(tmp_path, {"in.zip": zip_of(HELD)}, zipfile="in.zip", directory="out", printout=True)
    said = [record.getMessage() for record in caplog.records if record.getMessage().startswith("[open]")]
    assert said == ["[open] unpacked 'out/a.csv'", "[open] unpacked 'out/sub/b.txt'", "[open] unpacked 'out/sub/deep/c.csv'",
                    "[open] unpacked 3 files of 'in.zip' (zip) into 'out'"]


def test_job_that_is_not_to_die_goes_on_and_says_why_and_one_that_does_not_say_dies(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="src.v2")
    made = dict(job([unarchive(zipfile="nope.zip", directory="out", die_on_error=False)], []), run={"row_counts": True})
    result = on_v2(made, filled(tmp_path, {}))
    assert result.status == "success", result.error
    assert result.global_map["open_ERROR_MESSAGE"] == "File not found: 'nope.zip'"
    assert result.counts["open"] == {"NB_LINE": 1, "NB_LINE_OK": 0, "NB_LINE_REJECT": 1}
    assert [record.getMessage() for record in caplog.records] == ["[open] File not found: 'nope.zip'; the job goes on"]
    assert on_v2(job([unarchive(zipfile="nope.zip", directory="out")], []), tmp_path).status == "failed"


def test_paths_from_the_context(tmp_path):
    made = job([unarchive(zipfile="${context.name}.zip", directory="${context.name}")], [])
    made["context"] = {"Default": {"name": {"value": "in", "type": "str"}}}
    folder = filled(tmp_path, {"in.zip": zip_of(HELD)})
    assert on_v2(made, folder).status == "success" and tree(folder / "in") == UNPACKED


# ------------------------------------------------------------------
# What is refused, and the names it goes by
# ------------------------------------------------------------------

def test_what_the_converter_writes_is_taken(tmp_path):
    result, folder = ran(
        tmp_path, {"in.zip": zip_of(HELD)}, zipfile="in.zip", directory="out", rootname=False, integrity=True,
        extractpath=True, checkpassword=False, decrypt_method="ZIP4J_DECRYPT", password="", die_on_error=False,
        printout=False, use_encoding=False, encording="UTF-8", tstatcatcher_stats=False, label="")
    assert result.status == "success", result.error
    assert tree(folder / "out") == UNPACKED


@pytest.mark.parametrize("config, said", [
    ({"directory": "out"}, "zipfile: required config key is missing"),
    ({"zipfile": "a.zip"}, "directory: required config key is missing"),
    ({"zipfile": " ", "directory": "out"}, "zipfile: there is no archive named"),
    ({"zipfile": "a.zip", "directory": ""}, "directory: there is no folder named to unpack into"),
    ({"zipfile": "a.zip", "directory": "out", "checkpassword": True, "decrypt_method": "JAVA_DECRYPT"},
     "decrypt_method: JAVA_DECRYPT is a cipher of Talend's own around the whole file, which only Talend reads; v2 "
     "opens a zip locked the standard way"),
    ({"zipfile": "a.zip", "directory": "out", "use_encoding": True, "encording": "nope"}, "encording: unknown encoding: nope"),
    ({"zipfile": "a.zip", "directory": "out", "nope": 1}, "nope: unknown config key"),
])
def test_what_cannot_be_done_refuses_the_job(config, said):
    assert [f"{key}: {reason}" for key, reason in refusals(job([unarchive(**config)], []))] == [said]


@pytest.mark.parametrize("kind", ["file_unarchive", "FileUnarchive", "FileUnarchiveComponent", "tFileUnarchive"])
def test_every_name_of_it(tmp_path, kind):
    result, folder = ran(tmp_path, {"in.zip": zip_of(HELD)}, kind=kind, zipfile="in.zip", directory="out")
    assert result.status == "success" and tree(folder / "out") == UNPACKED
