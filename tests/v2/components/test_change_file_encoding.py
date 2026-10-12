"""Change file encoding: a file's text written in another encoding."""
import json
import logging
import os
from pathlib import Path

import pytest

from src.v2 import files, load_job
from src.v2.errors import ConfigurationError, JobRefusedError
from tests.v2.components.kit import job

from .test_file_actions_kit import action, filled, on_v2, tree

SAMPLE = Path(__file__).parents[2] / "talend_xml_samples" / "converted_jsons" / "Job_tChangeFileEncoding_0.1.json"
TEXT = "id;name\r\n1;caf\u00e9\n2;5 \u20ac\n"


def change(kind="ChangeFileEncoding", **config):
    return action("turn", kind, **config)


def ran(tmp_path, files_there, **config):
    """Run one change in a folder of these files; returns how it ended and the folder."""
    folder = filled(tmp_path, files_there)
    return on_v2(job([change(**config)], []), folder), folder


def refusals(made):
    with pytest.raises(JobRefusedError) as refused:
        load_job(made)
    return [(refusal.key, refusal.reason) for refusal in refused.value.report]


# ------------------------------------------------------------------
# The text in another encoding
# ------------------------------------------------------------------

def test_text_is_written_in_the_other_encoding_with_its_line_ends_as_they_were(tmp_path):
    result, folder = ran(tmp_path, {"in.csv": TEXT.encode("utf-8")}, use_inencoding=True, inencoding="UTF-8",
                         infile_name="in.csv", outfile_name="out.csv", encoding="ISO-8859-15")
    assert result.status == "success", result.error
    assert tree(folder) == {"in.csv": TEXT.encode("utf-8"), "out.csv": TEXT.encode("iso-8859-15")}


def test_the_other_way_round(tmp_path):
    result, folder = ran(tmp_path, {"in.csv": TEXT.encode("iso-8859-15")}, use_inencoding=True, inencoding="ISO-8859-15",
                         infile_name="in.csv", outfile_name="out.csv", encoding="UTF-8")
    assert result.status == "success", result.error
    assert (folder / "out.csv").read_bytes() == TEXT.encode("utf-8")


def test_input_is_read_as_utf_8_when_its_encoding_is_not_to_be_used(tmp_path):
    result, folder = ran(tmp_path, {"in.csv": TEXT.encode("utf-8")}, use_inencoding=False, inencoding="ISO-8859-15",
                         infile_name="in.csv", outfile_name="out.csv", encoding="UTF-16LE")
    assert result.status == "success", result.error
    assert (folder / "out.csv").read_bytes() == TEXT.encode("utf-16-le")


def test_output_is_iso_8859_15_when_no_encoding_is_given(tmp_path):
    _, folder = ran(tmp_path, {"in.csv": TEXT.encode("utf-8")}, infile_name="in.csv", outfile_name="out.csv")
    assert (folder / "out.csv").read_bytes() == TEXT.encode("iso-8859-15")


@pytest.mark.parametrize("read_as, data", [
    ("UTF-8", b"\xef\xbb\xbf" + TEXT.encode("utf-8")), ("UTF-16", TEXT.encode("utf-16")),
    ("UTF-16BE", ("\ufeff" + TEXT).encode("utf-16-be")),
], ids=["utf-8", "utf-16", "utf-16be"])
def test_byte_order_mark_of_the_input_is_not_carried_over(tmp_path, read_as, data):
    _, folder = ran(tmp_path, {"in.csv": data}, use_inencoding=True, inencoding=read_as, infile_name="in.csv",
                    outfile_name="out.csv", encoding="UTF-8")
    assert (folder / "out.csv").read_bytes() == TEXT.encode("utf-8")


@pytest.mark.parametrize("written_as, starts", [("UTF-16", TEXT.encode("utf-16")[:2]), ("utf-8-sig", b"\xef\xbb\xbf")])
def test_output_starts_with_a_byte_order_mark_where_its_encoding_has_one(tmp_path, written_as, starts):
    _, folder = ran(tmp_path, {"in.csv": TEXT.encode("utf-8")}, infile_name="in.csv", outfile_name="out.csv",
                    encoding=written_as)
    written = (folder / "out.csv").read_bytes()
    assert written.startswith(starts) and written.decode(written_as) == TEXT


def test_empty_file_is_an_empty_file(tmp_path):
    result, folder = ran(tmp_path, {"in.csv": b""}, infile_name="in.csv", outfile_name="out.csv", encoding="UTF-8")
    assert result.status == "success" and (folder / "out.csv").read_bytes() == b""


# ------------------------------------------------------------------
# Where it is written
# ------------------------------------------------------------------

def test_file_can_be_written_over_itself(tmp_path):
    result, folder = ran(tmp_path, {"in.csv": TEXT.encode("utf-8")}, infile_name="in.csv", outfile_name="in.csv",
                         encoding="ISO-8859-15")
    assert result.status == "success", result.error
    assert tree(folder) == {"in.csv": TEXT.encode("iso-8859-15")}


def test_folder_of_the_output_is_made_unless_it_is_not_to_be(tmp_path):
    result, folder = ran(tmp_path, {"in.csv": b"x"}, infile_name="in.csv", outfile_name="deep/er/out.csv")
    assert result.status == "success" and (folder / "deep/er/out.csv").read_bytes() == b"x"
    result, folder = ran(tmp_path / "again", {"in.csv": b"x"}, infile_name="in.csv", outfile_name="deep/er/out.csv",
                         create=False)
    assert (result.status, result.error) == ("failed", "the folder 'deep/er' is not there, and is not to be made")
    assert tree(folder) == {"in.csv": b"x"}


def test_file_that_is_there_is_written_over_and_keeps_its_permissions(tmp_path):
    folder = filled(tmp_path, {"in.csv": b"new", "out.csv": b"old"})
    os.chmod(folder / "out.csv", 0o640)
    result = on_v2(job([change(infile_name="in.csv", outfile_name="out.csv")], []), folder)
    assert result.status == "success", result.error
    assert (folder / "out.csv").read_bytes() == b"new" and os.stat(folder / "out.csv").st_mode & 0o777 == 0o640


# ------------------------------------------------------------------
# What cannot be read or written: the job fails and the output is as it was
# ------------------------------------------------------------------

def test_byte_that_is_no_character_fails_the_job_and_says_where(tmp_path):
    data = b"one\ntwo\nthr\xe9e\n"
    result, folder = ran(tmp_path, {"in.csv": data, "out.csv": b"as it was"}, infile_name="in.csv", outfile_name="out.csv")
    assert result.status == "failed"
    assert result.error == "'in.csv' is not written in UTF-8: byte 12 of it, on line 3, is no character there"
    assert tree(folder) == {"in.csv": data, "out.csv": b"as it was"}


def test_character_the_output_cannot_hold_fails_the_job_and_says_where(tmp_path):
    data = "one\ntwo \u20ac\n".encode("utf-8")
    result, folder = ran(tmp_path, {"in.csv": data, "out.csv": b"as it was"}, infile_name="in.csv", outfile_name="out.csv",
                         encoding="ISO-8859-1")
    assert result.status == "failed"
    assert result.error == r"'in.csv' holds '\u20ac' on line 2, which ISO-8859-1 cannot write"
    assert tree(folder) == {"in.csv": data, "out.csv": b"as it was"}


def test_input_cut_short_inside_a_character_fails_the_job(tmp_path):
    result, _ = ran(tmp_path, {"in.csv": "ab\u20ac".encode("utf-8")[:-1]}, infile_name="in.csv", outfile_name="out.csv")
    assert result.error == "'in.csv' is not written in UTF-8: byte 3 of it, on line 1, is no character there"


def test_file_that_is_not_there_and_a_folder_fail_the_job(tmp_path):
    result, folder = ran(tmp_path, {"dir/": None}, infile_name="nope.csv", outfile_name="out.csv")
    assert (result.status, result.error) == ("failed", "File not found: 'nope.csv'")
    result, _ = ran(tmp_path, {}, infile_name="dir", outfile_name="out.csv")
    assert (result.status, result.error) == ("failed", "'dir' cannot be read: it is a folder")
    assert tree(folder) == {"dir/": None}


def test_output_that_cannot_be_written_fails_the_job_in_plain_words(tmp_path):
    result, folder = ran(tmp_path, {"in.csv": b"x", "dir/": None}, infile_name="in.csv", outfile_name="dir")
    assert (result.status, result.error) == ("failed", "'dir' cannot be written: it is a folder")
    assert tree(folder) == {"dir/": None, "in.csv": b"x"}
    if os.geteuid() == 0:
        return
    os.chmod(folder / "dir", 0o500)
    try:
        result = on_v2(job([change(infile_name="in.csv", outfile_name="dir/out.csv")], []), folder)
    finally:
        os.chmod(folder / "dir", 0o700)
    assert (result.status, result.error) == ("failed", "'dir/out.csv' cannot be written: permission denied")
    assert tree(folder) == {"dir/": None, "in.csv": b"x"}


def test_input_that_cannot_be_opened_fails_the_job_in_plain_words(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root may read everything")
    folder = filled(tmp_path, {"in.csv": b"x"})
    os.chmod(folder / "in.csv", 0o000)
    result = on_v2(job([change(infile_name="in.csv", outfile_name="out.csv")], []), folder)
    assert (result.status, result.error) == ("failed", "'in.csv' cannot be read: permission denied")
    assert sorted(path.name for path in folder.iterdir()) == ["in.csv"]


# ------------------------------------------------------------------
# Piece by piece
# ------------------------------------------------------------------

def test_file_longer_than_one_piece_is_written_whole_whatever_the_pieces_cut_through(tmp_path, monkeypatch):
    text = "".join(f"{row};caf\u00e9 \u20ac {row}\r\n" for row in range(200))
    for size in (1, 2, 3, 5, 7, 64):
        monkeypatch.setattr(files, "_CHUNK", size)
        result, folder = ran(tmp_path / str(size), {"in.csv": text.encode("utf-8")}, infile_name="in.csv",
                             outfile_name="out.csv", encoding="UTF-16")
        assert result.status == "success", result.error
        assert (folder / "out.csv").read_bytes() == text.encode("utf-16")


@pytest.mark.parametrize("written_as", ["iso2022_jp", "hz"])
def test_encoding_that_has_to_be_told_the_text_has_ended_is_written_whole(tmp_path, monkeypatch, written_as):
    # These switch between character sets as they go, and a file has to end switched back.
    text = "ab\u3042\u3044" if written_as != "hz" else "ab\u4e2d\u6587"
    for size in (2, 64):
        monkeypatch.setattr(files, "_CHUNK", size)
        _, folder = ran(tmp_path / str(size), {"in.csv": text.encode("utf-8")}, infile_name="in.csv",
                        outfile_name="out.csv", encoding=written_as)
        assert (folder / "out.csv").read_bytes() == text.encode(written_as)


def test_mark_is_left_out_at_the_start_of_the_file_only(tmp_path, monkeypatch):
    text = "\ufeffab\ufeffcd\ufeff\n"
    for size in (1, 2, 3, 4, 5, 64):
        monkeypatch.setattr(files, "_CHUNK", size)
        _, folder = ran(tmp_path / str(size), {"in.csv": text.encode("utf-8")}, infile_name="in.csv",
                        outfile_name="out.csv", encoding="UTF-8")
        assert (folder / "out.csv").read_bytes() == text[1:].encode("utf-8")


def test_fault_is_said_in_plain_ascii_by_the_function_itself(tmp_path):
    (tmp_path / "in.csv").write_bytes("5 \u20ac".encode("utf-8"))
    with pytest.raises(ConfigurationError) as fault:
        files.transcode(str(tmp_path / "in.csv"), str(tmp_path / "out.csv"), "UTF-8", "ISO-8859-1")
    assert str(fault.value).isascii() and r"holds '\u20ac' on line 1" in str(fault.value)


@pytest.mark.parametrize("size", [1, 2, 3, 4, 5, 6, 7, 8, 64])
def test_place_of_a_fault_is_right_whatever_the_pieces_cut_through(tmp_path, monkeypatch, size):
    monkeypatch.setattr(files, "_CHUNK", size)
    data = "a\u20ac\nb\u00e9\n".encode("utf-8") + b"c\xe2\x82\n"
    result, _ = ran(tmp_path, {"in.csv": data}, infile_name="in.csv", outfile_name="out.csv", encoding="UTF-8")
    assert result.error == "'in.csv' is not written in UTF-8: byte 11 of it, on line 3, is no character there"
    result, _ = ran(tmp_path, {"in.csv": "ab\ncd\n\u0142\n".encode("utf-8")}, infile_name="in.csv", outfile_name="out.csv",
                    encoding="ISO-8859-1")
    assert result.error == r"'in.csv' holds '\u0142' on line 3, which ISO-8859-1 cannot write"


# ------------------------------------------------------------------
# What it leaves
# ------------------------------------------------------------------

def test_what_is_left_in_globalmap_and_said_in_the_log(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="src.v2")
    folder = filled(tmp_path, {"in.csv": "caf\u00e9".encode("utf-8")})
    made = dict(job([change(infile_name="in.csv", outfile_name="out.csv", use_inencoding=True, inencoding="UTF-8")], []),
                run={"row_counts": True})
    result = on_v2(made, folder)
    assert result.counts["turn"] == {"NB_LINE": 1, "NB_LINE_OK": 1, "NB_LINE_REJECT": 0}
    assert result.global_map["turn_FILENAME"] == "out.csv"
    assert "[turn] wrote 'in.csv' (UTF-8) as 'out.csv' (ISO-8859-15), 4 bytes" in [r.getMessage() for r in caplog.records]


def test_paths_from_the_context(tmp_path):
    made = job([change(infile_name="${context.dir}/in.csv", outfile_name="${context.dir}/out.csv")], [])
    made["context"] = {"Default": {"dir": {"value": "dir", "type": "str"}}}
    folder = filled(tmp_path, {"dir/in.csv": b"x"})
    assert on_v2(made, folder).status == "success" and (folder / "dir/out.csv").read_bytes() == b"x"


# ------------------------------------------------------------------
# What is refused, and the names it goes by
# ------------------------------------------------------------------

def test_component_of_the_converted_sample_job_loads_as_it_is():
    # The sample has a tJava beside it, which v2 does not run; the component itself is taken as the converter wrote it.
    sample = json.loads(SAMPLE.read_text())
    found = [c for c in sample["components"] if c["type"] == "tChangeFileEncoding"]
    assert len(found) == 1 and found[0]["config"]["buffersize"] == "8192"
    alone = dict(found[0], inputs=[], outputs=[])
    assert load_job(job([alone], [])).components[alone["id"]].config["encoding"] == "ISO-8859-15"


@pytest.mark.parametrize("config, key", [
    ({"outfile_name": "b"}, "infile_name"), ({"infile_name": "a"}, "outfile_name"),
    ({"infile_name": " ", "outfile_name": "b"}, "infile_name"), ({"infile_name": "a", "outfile_name": ""}, "outfile_name"),
    ({"infile_name": "a", "outfile_name": "b", "encoding": "nope"}, "encoding"),
    ({"infile_name": "a", "outfile_name": "b", "inencoding": "nope"}, "inencoding"),
    ({"infile_name": "a", "outfile_name": "b", "nope": 1}, "nope"),
])
def test_what_cannot_be_read_refuses_the_job(config, key):
    assert [key for key, _ in refusals(job([change(**config)], []))] == [key]


@pytest.mark.parametrize("kind", ["change_file_encoding", "ChangeFileEncoding", "tChangeFileEncoding"])
def test_every_name_of_it(tmp_path, kind):
    result, folder = ran(tmp_path, {"in.csv": b"x"}, kind=kind, infile_name="in.csv", outfile_name="out.csv")
    assert result.status == "success" and (folder / "out.csv").read_bytes() == b"x"
