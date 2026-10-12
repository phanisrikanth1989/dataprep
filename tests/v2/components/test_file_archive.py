"""File archive: files packed into one archive."""
import gzip
import io
import logging
import os
import stat
import tarfile
import time
import zipfile

import pytest

from src.v2 import load_job
from src.v2.errors import JobRefusedError
from tests.v2.components.kit import job

from .test_file_actions_kit import action, filled, on_v2, tree

try:
    from compression import zstd
except ImportError:  # before Python 3.14
    zstd = None

needs_zstd = pytest.mark.skipif(zstd is None, reason="Zstandard is in the standard library from Python 3.14")
LONG_AGO = 1_700_000_000
FILES = {"src/a.csv": b"a;1\n", "src/b.txt": b"bee", "src/sub/c.csv": b"c;3\n", "src/sub/deep/d.csv": b"d", "src/empty/": None}
ALL = {"a.csv": b"a;1\n", "b.txt": b"bee", "sub/c.csv": b"c;3\n", "sub/deep/d.csv": b"d"}


def archive(kind="FileArchive", **config):
    return action("pack", kind, **config)


def ran(tmp_path, files=FILES, **config):
    """Run one archive in a folder of these files, each last changed long ago; returns how it ended and the folder."""
    folder = filled(tmp_path, files)
    for name in files:
        os.utime(folder / name, (LONG_AGO, LONG_AGO))
    return on_v2(job([archive(**config)], []), folder), folder


def zipped(path):
    """What a zip archive holds: each entry's name and bytes, in the archive's order."""
    with zipfile.ZipFile(path) as held:
        return {info.filename: held.read(info) for info in held.infolist()}


def tarred(path):
    with tarfile.open(path, "r:*") as held:
        return {member.name: held.extractfile(member).read() for member in held.getmembers()}


def refusals(made):
    with pytest.raises(JobRefusedError) as refused:
        load_job(made)
    return [(refusal.key, refusal.reason) for refusal in refused.value.report]


# ------------------------------------------------------------------
# A folder into a zip
# ------------------------------------------------------------------

def test_files_of_a_folder_are_the_entries_by_their_path_below_it_in_the_order_of_their_names(tmp_path):
    result, folder = ran(tmp_path, source="src", target="out.zip")
    assert result.status == "success", result.error
    assert list(zipped(folder / "out.zip").items()) == list(ALL.items())
    assert tree(folder / "src") == tree(filled(tmp_path / "same", FILES) / "src")


def test_archive_format_is_zip_when_none_is_given_and_written_as_talend_writes_it(tmp_path):
    for at, written in enumerate(("zip", "ZIP")):
        result, folder = ran(tmp_path / str(at), source="src", target="out.zip", archive_format=written)
        assert result.status == "success" and zipfile.is_zipfile(folder / "out.zip")


@pytest.mark.parametrize("key", ["sub_directroy", "include_subdirectories"])
def test_files_of_subfolders_are_left_out_when_asked(tmp_path, key):
    _, folder = ran(tmp_path, source="src", target="out.zip", **{key: False})
    assert zipped(folder / "out.zip") == {"a.csv": b"a;1\n", "b.txt": b"bee"}


def test_one_file_is_an_archive_of_that_file_under_its_name(tmp_path):
    result, folder = ran(tmp_path, source="src/sub/c.csv", target="out.zip")
    assert result.status == "success", result.error
    assert zipped(folder / "out.zip") == {"c.csv": b"c;3\n"}


def test_entry_has_the_time_and_the_name_of_its_file(tmp_path):
    odd = "caf" + chr(233) + " " + chr(0x20AC) + ".csv"
    _, folder = ran(tmp_path, {"src/" + odd: b"x", "src/old.txt": b"y"}, source="src", target="out.zip")
    os.utime(folder / "src/old.txt", (0, 0))
    on_v2(job([archive(source="src", target="out.zip")], []), folder)
    with zipfile.ZipFile(folder / "out.zip") as held:
        named = {info.filename: info for info in held.infolist()}
    assert sorted(named) == sorted([odd, "old.txt"])
    assert named[odd].date_time == time.localtime(LONG_AGO)[:6][:5] + (time.localtime(LONG_AGO)[5] // 2 * 2,)
    # A zip cannot say a time before 1980: the file is archived all the same, as of 1980.
    assert named["old.txt"].date_time[0] == 1980


# ------------------------------------------------------------------
# Which files
# ------------------------------------------------------------------

@pytest.mark.parametrize("mask, taken", [
    (["*.csv"], ["a.csv", "sub/c.csv", "sub/deep/d.csv"]), ("*.csv", ["a.csv", "sub/c.csv", "sub/deep/d.csv"]),
    (["a.*", "*.txt"], ["a.csv", "b.txt"]), (["?.csv"], ["a.csv", "sub/c.csv", "sub/deep/d.csv"]),
    (["[ab].*"], ["a.csv", "b.txt"]), (["*.CSV"], None), (["sub*"], None),
], ids=["one", "as text", "two", "one character", "a set", "other case", "a folder's name"])
def test_mask_says_which_files_by_their_names(tmp_path, mask, taken):
    result, folder = ran(tmp_path, source="src", target="out.zip", all_files=False, mask=mask)
    assert result.status == "success", result.error
    if taken is None:
        assert not (folder / "out.zip").exists()
    else:
        assert list(zipped(folder / "out.zip")) == taken


def test_mask_is_not_looked_at_while_all_files_are_taken(tmp_path):
    _, folder = ran(tmp_path, source="src", target="out.zip", all_files=True, mask=["*.csv"])
    assert list(zipped(folder / "out.zip")) == list(ALL)


def test_no_file_to_take_writes_no_archive_and_takes_away_the_one_that_was_there(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="src.v2")
    files = dict(FILES, **{"out.zip": b"of an earlier run"})
    result, folder = ran(tmp_path, files, source="src", target="out.zip", all_files=False, mask=["*.nope"])
    assert result.status == "success", result.error
    assert not (folder / "out.zip").exists() and result.global_map["pack_NB_FILE"] == 0
    assert [record.getMessage() for record in caplog.records] == [
        "[pack] no file of 'src' is taken: no archive is written, and 'out.zip', which was there, is taken away"]


def test_archive_in_the_folder_it_is_made_of_does_not_hold_itself(tmp_path):
    result, folder = ran(tmp_path, source="src", target="src/out.zip")
    assert result.status == "success", result.error
    assert list(zipped(folder / "src/out.zip")) == list(ALL)
    assert on_v2(job([archive(source="src", target="src/out.zip")], []), folder).status == "success"
    assert list(zipped(folder / "src/out.zip")) == list(ALL)


def test_links_and_what_is_no_file_are_left_out_and_named(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="src.v2")
    folder = filled(tmp_path, dict(FILES, **{"outside/secret.txt": b"s"}))
    os.symlink("../outside/secret.txt", folder / "src/link.txt")
    os.symlink("../outside", folder / "src/linked")
    os.mkfifo(folder / "src/pipe")
    result = on_v2(job([archive(source="src", target="out.zip")], []), folder)
    assert result.status == "success", result.error
    assert list(zipped(folder / "out.zip")) == list(ALL)
    assert [record.getMessage() for record in caplog.records] == [
        "[pack] 3 links or special files of 'src' are left out of the archive; the first: 'src/link.txt'"]


# ------------------------------------------------------------------
# The other kinds of archive
# ------------------------------------------------------------------

@pytest.mark.parametrize("written, name", [("tgz", "out.tar.gz"), ("TAR_GZIP", "out.tgz"), ("tar", "out.tar")])
def test_tar_archive_holds_the_same_entries(tmp_path, written, name):
    result, folder = ran(tmp_path, source="src", target=name, archive_format=written)
    assert result.status == "success", result.error
    assert list(tarred(folder / name).items()) == list(ALL.items())
    opened = (folder / name).read_bytes()[:2]
    assert (opened == b"\x1f\x8b") is (written != "tar")


def test_tar_entry_says_nothing_of_who_owns_the_file_and_has_its_time_in_whole_seconds(tmp_path):
    _, folder = ran(tmp_path, source="src", target="out.tgz", archive_format="tgz")
    with tarfile.open(folder / "out.tgz") as held:
        members = held.getmembers()
    assert {(m.uid, m.gid, m.uname, m.gname, m.mtime, m.isfile()) for m in members} == {(0, 0, "", "", LONG_AGO, True)}
    assert members[0].mode == stat.S_IMODE(os.stat(folder / "src/a.csv").st_mode)


@pytest.mark.parametrize("written, name", [("zip", "out.zip"), ("tgz", "out.tgz"), ("tar", "out.tar"), ("gzip", "a.csv.gz")])
def test_same_files_give_the_same_bytes_whenever_and_wherever_they_are_archived(tmp_path, written, name):
    config = dict(source="src", source_file="src/a.csv", target=name, archive_format=written)
    _, one = ran(tmp_path / "one", **config)
    _, two = ran(tmp_path / "two" / "deeper", **config)
    assert (one / name).read_bytes() == (two / name).read_bytes()


def test_gzip_header_of_a_tgz_has_no_time_and_no_name_in_it(tmp_path):
    _, folder = ran(tmp_path, source="src", target="out.tgz", archive_format="tgz")
    written = (folder / "out.tgz").read_bytes()
    # After the two bytes that say gzip and the one that says how: the flags (a name would set one), then the time.
    assert written[3] == 0 and written[4:8] == b"\x00\x00\x00\x00"


def test_gzip_is_one_file_compressed_with_its_name_and_time_in_the_header(tmp_path):
    result, folder = ran(tmp_path, source_file="src/a.csv", target="packed/a.csv.gz", archive_format="gzip", mkdir=True)
    assert result.status == "success", result.error
    written = (folder / "packed/a.csv.gz").read_bytes()
    assert gzip.decompress(written) == b"a;1\n"
    assert int.from_bytes(written[4:8], "little") == LONG_AGO and written[10:16] == b"a.csv\x00"
    assert result.global_map["pack_NB_FILE"] == 1


def test_gzip_of_a_folder_fails_the_job_and_says_what_to_use(tmp_path):
    result, folder = ran(tmp_path, source_file="src", target="out.gz", archive_format="gzip")
    assert (result.status, result.error) == (
        "failed", "'src' is a folder, and a gzip archive holds one file: use zip or tgz for a folder")
    assert not (folder / "out.gz").exists()


@needs_zstd
def test_tar_with_zstandard_and_one_file_with_zstandard(tmp_path):
    result, folder = ran(tmp_path, source="src", target="out.tar.zst", archive_format="tar.zst")
    assert result.status == "success", result.error
    assert list(tarred(folder / "out.tar.zst").items()) == list(ALL.items())
    result, folder = ran(tmp_path / "one", source_file="src/a.csv", target="a.csv.zst", archive_format="zst")
    assert result.status == "success", result.error
    assert zstd.decompress((folder / "a.csv.zst").read_bytes()) == b"a;1\n"


def test_zstandard_is_refused_where_python_has_none(monkeypatch):
    from src.v2.components.file import file_archive
    monkeypatch.setattr(file_archive, "zstd", None)
    monkeypatch.setattr(file_archive.sys, "version_info", (3, 12, 4))
    assert refusals(job([archive(source="src", target="out.tar.zst", archive_format="tar.zst")], [])) == [
        ("archive_format", "tar.zst needs Zstandard, which Python has from 3.14; this is Python 3.12")]


# ------------------------------------------------------------------
# How hard it is compressed
# ------------------------------------------------------------------

def test_level_0_stores_and_a_higher_level_makes_a_smaller_archive(tmp_path):
    files = {"src/big.txt": b"the same line again and again\n" * 20_000}
    sizes = {}
    for level in (0, "1", 9):
        _, folder = ran(tmp_path / str(level), files, source="src", target="out.zip", level=level)
        with zipfile.ZipFile(folder / "out.zip") as held:
            info = held.infolist()[0]
        assert info.compress_type == (zipfile.ZIP_STORED if level == 0 else zipfile.ZIP_DEFLATED)
        assert held.filename and zipped(folder / "out.zip") == {"big.txt": files["src/big.txt"]}
        sizes[level] = info.compress_size
    assert sizes[0] == len(files["src/big.txt"]) and sizes[0] > sizes["1"] > sizes[9]


def test_level_is_4_when_none_is_given_and_compression_level_is_v1s_name_for_it():
    assert load_job(job([archive(source="a", target="b")], [])).components["pack"].config["level"] == 4
    assert load_job(job([archive(source="a", target="b", compression_level="9")], [])).components["pack"].config["level"] == 9


@pytest.mark.parametrize("written, level, said", [
    ("zip", 10, "level: 10 is no level a zip archive is compressed at; give 0 to 9"),
    ("tgz", -1, "level: -1 is no level a tgz archive is compressed at; give 0 to 9"),
    ("zip", "fast", "level: 'fast' is no whole number"),
])
def test_level_that_is_none_refuses_the_job(written, level, said):
    made = job([archive(source="a", target="b", archive_format=written, level=level)], [])
    assert [f"{key}: {reason}" for key, reason in refusals(made)] == [said]


# ------------------------------------------------------------------
# Where it is written
# ------------------------------------------------------------------

def test_folder_of_the_archive_has_to_be_there_unless_it_is_to_be_made(tmp_path):
    result, folder = ran(tmp_path, source="src", target="made/deep/out.zip")
    assert (result.status, result.error) == ("failed", "the folder 'made/deep' is not there, and is not to be made")
    assert not (folder / "made").exists()
    result, folder = ran(tmp_path / "again", source="src", target="made/deep/out.zip", mkdir=True)
    assert result.status == "success" and list(zipped(folder / "made/deep/out.zip")) == list(ALL)


def test_archive_that_is_written_over_keeps_its_permissions(tmp_path):
    folder = filled(tmp_path, dict(FILES, **{"out.zip": b"of an earlier run"}))
    os.chmod(folder / "out.zip", 0o640)
    assert on_v2(job([archive(source="src", target="out.zip")], []), folder).status == "success"
    assert stat.S_IMODE(os.stat(folder / "out.zip").st_mode) == 0o640 and list(zipped(folder / "out.zip")) == list(ALL)


def test_archive_that_is_there_is_written_over_unless_it_is_not_to_be(tmp_path):
    files = dict(FILES, **{"out.zip": b"of an earlier run"})
    result, folder = ran(tmp_path, files, source="src", target="out.zip")
    assert result.status == "success" and list(zipped(folder / "out.zip")) == list(ALL)
    result, folder = ran(tmp_path / "again", files, source="src", target="out.zip", overwrite=False)
    assert (result.status, result.error) == ("failed", "'out.zip' is there, and is not to be written over")
    assert (folder / "out.zip").read_bytes() == b"of an earlier run"


def test_failure_on_the_way_leaves_the_archive_that_was_there_and_nothing_beside_it(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root may read everything")
    folder = filled(tmp_path, dict(FILES, **{"out.zip": b"of an earlier run"}))
    os.chmod(folder / "src/b.txt", 0o000)
    result = on_v2(job([archive(source="src", target="out.zip")], []), folder)
    assert (result.status, result.error) == ("failed", "'src/b.txt' cannot be read: permission denied")
    assert (folder / "out.zip").read_bytes() == b"of an earlier run"
    assert sorted(path.name for path in folder.iterdir()) == ["out.zip", "src"]


def test_folder_that_cannot_be_looked_into_fails_the_job_and_is_not_passed_over(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root may read everything")
    folder = filled(tmp_path, FILES)
    os.chmod(folder / "src/sub", 0o000)
    try:
        result = on_v2(job([archive(source="src", target="out.zip")], []), folder)
    finally:
        os.chmod(folder / "src/sub", 0o700)
    assert (result.status, result.error) == ("failed", "'src/sub' cannot be read: permission denied")
    assert not (folder / "out.zip").exists()


@pytest.mark.parametrize("config", [
    dict(source="pipe", target="out.zip"), dict(source_file="pipe", target="out.gz", archive_format="gzip")])
def test_source_that_is_neither_a_file_nor_a_folder_fails_the_job_and_is_never_opened(tmp_path, config):
    folder = filled(tmp_path, {})
    os.mkfifo(folder / "pipe")
    result = on_v2(job([archive(**config)], []), folder)
    assert (result.status, result.error) == (
        "failed", "'pipe' is neither a file nor a folder: there is nothing to archive")


def test_nothing_to_archive_fails_the_job(tmp_path):
    result, folder = ran(tmp_path, source="nope", target="out.zip")
    assert (result.status, result.error) == ("failed", "'nope' is not there: there is nothing to archive")
    assert not (folder / "out.zip").exists()


def test_archive_that_cannot_be_written_fails_the_job_in_plain_words(tmp_path):
    result, folder = ran(tmp_path, dict(FILES, **{"taken/": None}), source="src", target="taken")
    assert (result.status, result.error) == ("failed", "'taken' cannot be written: it is a folder")
    if os.geteuid() == 0:
        return
    os.chmod(folder / "taken", 0o500)
    try:
        result = on_v2(job([archive(source="src", target="taken/out.zip")], []), folder)
    finally:
        os.chmod(folder / "taken", 0o700)
    assert (result.status, result.error) == ("failed", "'taken/out.zip' cannot be written: permission denied")
    assert sorted(path.name for path in (folder / "taken").iterdir()) == []


def test_archive_that_cannot_be_written_is_said_before_any_file_is_read(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root may read everything")
    folder = filled(tmp_path, dict(FILES, **{"taken/": None}))
    os.chmod(folder / "src/a.csv", 0o000)
    result = on_v2(job([archive(source="src", target="taken")], []), folder)
    assert (result.status, result.error) == ("failed", "'taken' cannot be written: it is a folder")


def test_job_that_is_not_to_die_goes_on_and_says_why(tmp_path):
    made = dict(job([archive(source="nope", target="out.zip", die_on_error=False)], []), run={"row_counts": True})
    result = on_v2(made, filled(tmp_path, FILES))
    assert result.status == "success", result.error
    assert result.global_map["pack_ERROR_MESSAGE"] == "'nope' is not there: there is nothing to archive"
    assert result.counts["pack"] == {"NB_LINE": 1, "NB_LINE_OK": 0, "NB_LINE_REJECT": 1}


# ------------------------------------------------------------------
# What it leaves
# ------------------------------------------------------------------

def test_what_is_left_in_globalmap_and_said_in_the_log(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="src.v2")
    folder = filled(tmp_path, FILES)
    made = dict(job([archive(source="src", target="packed/out.zip", mkdir=True)], []), run={"row_counts": True})
    result = on_v2(made, folder)
    assert result.counts["pack"] == {"NB_LINE": 1, "NB_LINE_OK": 1, "NB_LINE_REJECT": 0}
    held = {key: value for key, value in result.global_map.items() if key.startswith("pack_ARCHIVE") or key == "pack_NB_FILE"}
    assert held == {"pack_ARCHIVE_FILEPATH": "packed/out.zip", "pack_ARCHIVE_FILENAME": "out.zip", "pack_NB_FILE": 4}
    size = (folder / "packed/out.zip").stat().st_size
    assert f"[pack] packed 4 files of 'src' into 'packed/out.zip' (zip), {size} bytes" in [r.getMessage() for r in caplog.records]


def test_paths_from_the_context(tmp_path):
    made = job([archive(source="${context.dir}", target="${context.dir}.zip")], [])
    made["context"] = {"Default": {"dir": {"value": "src", "type": "str"}}}
    folder = filled(tmp_path, FILES)
    assert on_v2(made, folder).status == "success" and list(zipped(folder / "src.zip")) == list(ALL)


# ------------------------------------------------------------------
# What is refused, and the names it goes by
# ------------------------------------------------------------------

def test_what_the_converter_writes_is_taken(tmp_path):
    result, folder = ran(
        tmp_path, source="src", source_file="", sub_directroy=True, target="out.zip", mkdir=False, archive_format="zip",
        level="4", all_files=True, mask=[], encoding="ISO-8859-15", overwrite=True, encrypt_files=False,
        encrypt_method="ZIP4J_STANDARD", aes_key_strength="AES256", password="", zip64_mode="ASNEEDED",
        use_sync_flush=False, tstatcatcher_stats=False, label="")
    assert result.status == "success", result.error
    assert list(zipped(folder / "out.zip")) == list(ALL)


def test_encryption_is_refused_and_says_why():
    assert refusals(job([archive(source="a", target="b", encrypt_files=True)], [])) == [
        ("encrypt_files", "v2 writes no encrypted archive: Python cannot write one. Encrypt the archive with a tool "
                          "made for it after the job has written it")]


@pytest.mark.parametrize("config, said", [
    ({"source": "a"}, "target: required config key is missing"),
    ({"source": "a", "target": " "}, "target: there is no archive named"),
    ({"target": "b"}, "source: there is nothing named to archive"),
    ({"source": "a", "target": "b", "archive_format": "gzip"}, "source_file: there is no file named to compress"),
    ({"source": "a", "target": "b", "all_files": False}, "mask: `all_files` is off and no mask is given: no file would be taken"),
    ({"source": "a", "target": "b", "archive_format": "rar"},
     "archive_format: 'rar' is no kind of archive v2 writes; use one of zip, gzip, tgz, tar, tar.zst, zst"),
    ({"source": "a", "target": "b", "nope": 1}, "nope: unknown config key"),
])
def test_what_cannot_be_done_refuses_the_job(config, said):
    assert [f"{key}: {reason}" for key, reason in refusals(job([archive(**config)], []))] == [said]


@pytest.mark.parametrize("kind", ["file_archive", "FileArchive", "FileArchiveComponent", "tFileArchive"])
def test_every_name_of_it(tmp_path, kind):
    result, folder = ran(tmp_path, kind=kind, source="src", target="out.zip")
    assert result.status == "success" and list(zipped(folder / "out.zip")) == list(ALL)
