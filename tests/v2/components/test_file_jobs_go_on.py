"""What every file job and the file list do with a fault that is no fault of the job config: the file system says
no, or a name is not in the encoding it has to be in. The job fails in plain words, or goes on when it is not to die."""
import errno
import logging

import pytest

from src.v2 import load_job
from src.v2.components.file import (
    change_file_encoding, file_archive, file_input_raw, file_list, file_properties, file_touch, file_unarchive,
)
from src.v2.errors import JobRefusedError
from tests.v2.components.kit import flow, job, writer

from .test_file_actions_kit import action, filled, on_v2


def source(kind, **config):
    return {"id": "it", "type": kind, "config": config, "inputs": [], "outputs": ["row2"],
            "schema": {"input": [], "output": []}}


# Each with the one step in which it does its work.
JOBS = {
    "file touch": (file_touch.FileTouch, "_touch", lambda die: job([action("it", "FileTouch", filename="x.txt", die_on_error=die)], [])),
    "file properties": (file_properties.FileProperties, "_row", lambda die: job(
        [source("FileProperties", filename="in.csv", die_on_error=die), writer(None)], [flow("row2", "it", "out")])),
    "raw file input": (file_input_raw.FileInputRaw, "_text", lambda die: job(
        [source("FileInputRaw", filename="in.csv", die_on_error=die), writer(None)], [flow("row2", "it", "out")])),
    "change file encoding": (change_file_encoding.ChangeFileEncoding, "_change", lambda die: job(
        [action("it", "ChangeFileEncoding", infile_name="in.csv", outfile_name="o.csv", die_on_error=die)], [])),
    "file archive": (file_archive.FileArchive, "_pack", lambda die: job(
        [action("it", "FileArchive", source="in.csv", target="o.zip", die_on_error=die)], [])),
    "file unarchive": (file_unarchive.FileUnarchive, "_unpack", lambda die: job(
        [action("it", "FileUnarchive", zipfile="in.zip", directory="o", die_on_error=die)], [])),
    "file list": (file_list.FileList, "_found", lambda die: job(
        [action("it", "FileList", directory=".", die_on_error=die)], [])),
}
FAULTS = [
    (OSError(errno.ENOSPC, "No space left on device", "x.bin"), "no space left on device: 'x.bin'"),
    (OSError(errno.EIO, "Input/output error"), "input/output error"),
    (UnicodeEncodeError("utf-8", "caf" + chr(0xDCE9), 3, 4, "surrogates not allowed"),
     "'utf-8' codec can't encode character '\\udce9' in position 3: surrogates not allowed"),
]


@pytest.mark.parametrize("fault, said", FAULTS, ids=["the system says no and names a file", "the system says no", "an encoding"])
@pytest.mark.parametrize("which", JOBS)
def test_fault_that_is_none_of_the_job_config_fails_the_job_in_plain_words(tmp_path, monkeypatch, which, fault, said):
    component, step, made = JOBS[which]
    monkeypatch.setattr(component, step, lambda self, *given: (_ for _ in ()).throw(fault))
    result = on_v2(made(True), filled(tmp_path, {"in.csv": b"x"}))
    assert (result.status, result.error, result.failed_component) == ("failed", said, "it")


@pytest.mark.parametrize("fault, said", FAULTS, ids=["the system says no and names a file", "the system says no", "an encoding"])
@pytest.mark.parametrize("which", JOBS)
def test_job_that_is_not_to_die_goes_on_after_such_a_fault_and_says_why(tmp_path, monkeypatch, caplog, which, fault, said):
    caplog.set_level(logging.WARNING, logger="src.v2")
    component, step, made = JOBS[which]
    monkeypatch.setattr(component, step, lambda self, *given: (_ for _ in ()).throw(fault))
    result = on_v2(made(False), filled(tmp_path, {"in.csv": b"x"}))
    assert result.status == "success", result.error
    assert result.global_map["it_ERROR_MESSAGE"] == said
    assert [record.getMessage() for record in caplog.records][0].startswith(f"[it] {said}; the job goes on")


# ------------------------------------------------------------------
# A file name that a context variable was to give, and that holds nothing
# ------------------------------------------------------------------

NAMED_BY_THE_CONTEXT = {
    "file touch": ("filename", [action("it", "FileTouch", filename="${context.f}")], []),
    "file properties": ("filename", [source("FileProperties", filename="${context.f}"), writer(None)], [flow("row2", "it", "out")]),
    "raw file input": ("filename", [source("FileInputRaw", filename="${context.f}"), writer(None)], [flow("row2", "it", "out")]),
    "change file encoding": ("infile_name", [action("it", "ChangeFileEncoding", infile_name="${context.f}", outfile_name="o.txt")], []),
    "file archive": ("target", [action("it", "FileArchive", source="src", target="${context.f}")], []),
    "file unarchive": ("zipfile", [action("it", "FileUnarchive", zipfile="${context.f}", directory="o")], []),
}


@pytest.mark.parametrize("which", NAMED_BY_THE_CONTEXT)
def test_file_name_from_a_context_variable_that_holds_nothing_refuses_the_job_and_names_the_key(which):
    key, components, flows = NAMED_BY_THE_CONTEXT[which]
    made = dict(job(components, flows), context={"Default": {"f": {"value": None, "type": "str"}}})
    with pytest.raises(JobRefusedError) as refused:
        load_job(made)
    # A value that names a context variable is judged with the context, and its fault is filed under `config`.
    assert [(refusal.key, refusal.reason) for refusal in refused.value.report] == [
        ("config", f"{key}: required config key has no value: '${{context.f}}' holds none")]


def test_file_name_of_nothing_but_blanks_refuses_the_job(tmp_path):
    with pytest.raises(JobRefusedError) as refused:
        load_job(job([action("it", "FileTouch", filename="  ")], []))
    assert [(refusal.key, refusal.reason) for refusal in refused.value.report] == [("filename", "there is no file named")]
