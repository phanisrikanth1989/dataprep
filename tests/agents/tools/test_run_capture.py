"""Tests for the parity-harness engine-run capture (Task 4).

Uses a bridge-free FileInputDelimited -> FileOutputDelimited passthrough job
(no tMap, no {{java}}), so no JVM is required.

Job-shape note:
    The engine reads component schemas as ``schema['output']`` /
    ``schema['input']`` (see engine.py:205-206), routes data through *named*
    flows whose ``type`` maps to a result key (``flow`` -> ``main``; see
    output_router.py:22-23 and the hard ``flow['name']`` lookup at line 75),
    and builds subjobs from each component's ``subjob_id`` field
    (engine.py:251-260). A flat-list ``schema`` or a nameless ``type:"main"``
    flow does NOT run on the real engine, so _passthrough_job uses the proven
    dict-config shape from tests/v1/engine/test_full_pipeline.py. The RunResult
    behaviour under test (output file captured into ``outputs[id]``; an
    unknown-type component surfaced in ``dropped_components``) is unchanged.
"""
import uuid
from pathlib import Path

import pandas as pd

from agents.tools.run_and_validate import RunResult, run_job_capture


def _passthrough_job(in_csv, out_csv):
    return {
        "job_name": "passthrough",
        "components": [
            {"id": "in1", "type": "FileInputDelimited",
             "config": {"filepath": str(in_csv), "fieldseparator": ",", "header_rows": 1,
                        "die_on_error": False},
             "inputs": [], "outputs": ["f1"],
             "schema": {"input": [], "output": [
                 {"name": "cc", "type": "str", "nullable": True, "key": False},
                 {"name": "amt", "type": "str", "nullable": True, "key": False}]},
             "subjob_id": "subjob_1", "is_subjob_start": True},
            {"id": "out1", "type": "FileOutputDelimited",
             "config": {"filepath": str(out_csv), "fieldseparator": ",", "include_header": True,
                        "file_exist_exception": False, "create_directory": True},
             "inputs": ["f1"], "outputs": [],
             "schema": {"input": [
                 {"name": "cc", "type": "str", "nullable": True, "key": False},
                 {"name": "amt", "type": "str", "nullable": True, "key": False}], "output": []},
             "subjob_id": "subjob_1", "is_subjob_start": False},
        ],
        "flows": [{"name": "f1", "from": "in1", "to": "out1", "type": "flow"}],
    }


def test_capture_reads_output_file_and_stats(tmp_path):
    in_csv = tmp_path / "in.csv"
    in_csv.write_text("cc,amt\nUS,10\nUK,20\n")
    out_csv = tmp_path / "out.csv"
    rr = run_job_capture(_passthrough_job(in_csv, out_csv), tmp_path)
    assert isinstance(rr, RunResult)
    assert rr.status == "success"
    assert rr.dropped_components == []
    assert set(rr.outputs["out1"]["cc"]) == {"US", "UK"}


def test_capture_detects_dropped_unknown_component(tmp_path):
    in_csv = tmp_path / "in.csv"
    in_csv.write_text("cc,amt\nUS,10\n")
    job = _passthrough_job(in_csv, tmp_path / "out.csv")
    job["components"].append({"id": "ghost", "type": "tNotARealComponent", "config": {}, "schema": []})
    rr = run_job_capture(job, tmp_path)
    assert "ghost" in rr.dropped_components


def test_dropped_is_by_unregistered_type_not_missing_stats():
    from agents.tools.run_and_validate import _dropped_components
    comps = [
        {"id": "a", "type": "FileInputDelimited"},        # registered -> NOT dropped
        {"id": "b", "type": "FilterRows"},                # registered -> NOT dropped
        {"id": "ghost", "type": "tNotARealComponent"},    # unregistered -> dropped
    ]
    assert _dropped_components(comps) == ["ghost"]


# ---------------------------------------------------------------------------
# I3: FileOutput filepaths are jailed to work_dir. A path that resolves OUTSIDE
# work_dir (absolute-outside, '..'-escape, or symlink-escape) is refused BEFORE
# the engine runs, so nothing is ever written outside the jail.
# ---------------------------------------------------------------------------
def test_capture_rejects_output_escaping_work_dir(tmp_path):
    in_csv = tmp_path / "in.csv"
    in_csv.write_text("cc,amt\nUS,10\n")
    escape = Path("/tmp") / f"escape_{uuid.uuid4().hex}.csv"  # absolute, outside tmp_path
    assert not escape.exists()
    rr = run_job_capture(_passthrough_job(in_csv, escape), tmp_path)
    assert rr.status == "error"
    assert "escapes" in (rr.error or "")
    assert not escape.exists()  # jail refused the run: nothing written outside work_dir


def test_capture_rejects_dotdot_output_escape(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    in_csv = work / "in.csv"
    in_csv.write_text("cc,amt\nUS,10\n")
    escape = work / ".." / f"escape_{uuid.uuid4().hex}.csv"  # '..' climbs out of work
    landing = Path(escape).resolve()
    assert not landing.exists()
    rr = run_job_capture(_passthrough_job(in_csv, escape), work)
    assert rr.status == "error"
    assert "escapes" in (rr.error or "")
    assert not landing.exists()


def test_capture_allows_output_inside_work_dir(tmp_path):
    in_csv = tmp_path / "in.csv"
    in_csv.write_text("cc,amt\nUS,10\nUK,20\n")
    out_csv = tmp_path / "out.csv"  # inside the jail
    rr = run_job_capture(_passthrough_job(in_csv, out_csv), tmp_path)
    assert rr.status == "success"
    assert set(rr.outputs["out1"]["cc"]) == {"US", "UK"}


# ---------------------------------------------------------------------------
# I1: RELATIVE paths are anchored to work_dir, NOT the process CWD. The skill
# teaches relative paths; the CLI runs from the workspace root (CWD != work_dir).
# A correct job with a relative input+output must therefore run under work_dir.
# ---------------------------------------------------------------------------
def _strict_passthrough_job(in_path, out_path):
    """Passthrough whose output OMITS file_exist_exception (engine default True),
    so a naive re-run over an existing output would raise -- the harness must
    pre-delete declared outputs to stay idempotent (I2)."""
    job = _passthrough_job(in_path, out_path)
    job["components"][1]["config"].pop("file_exist_exception", None)
    return job


def test_relative_paths_anchored_to_work_dir_not_cwd(tmp_path):
    (tmp_path / "in.csv").write_text("cc,amt\nUS,10\nUK,20\n")
    # RELATIVE input+output. CWD is the repo root (pytest never chdirs into
    # tmp_path), proving CWD != work_dir.
    assert Path.cwd() != tmp_path
    rr = run_job_capture(_passthrough_job("in.csv", "out.csv"), tmp_path)
    assert rr.status == "success", rr.error
    assert (tmp_path / "out.csv").exists()  # written UNDER work_dir, not CWD
    assert set(rr.outputs["out1"]["cc"]) == {"US", "UK"}


# ---------------------------------------------------------------------------
# I2: FileOutputDelimited defaults file_exist_exception=True; a re-run over an
# existing output raises -> engine status "failed". The harness pre-deletes the
# declared outputs under work_dir so a re-run starts clean and stays green.
# ---------------------------------------------------------------------------
def test_rerun_over_existing_output_is_idempotent(tmp_path):
    (tmp_path / "in.csv").write_text("cc,amt\nUS,10\n")
    job = _strict_passthrough_job("in.csv", "out.csv")
    rr1 = run_job_capture(job, tmp_path)
    assert rr1.status == "success", rr1.error
    assert (tmp_path / "out.csv").exists()
    rr2 = run_job_capture(job, tmp_path)  # output now already exists
    assert rr2.status == "success", rr2.error


# ---------------------------------------------------------------------------
# C1: the jail is default-deny across ALL writers, not a FileOutput-only
# allowlist. A non-FileOutput writer (FileCopy) writing to an ABSOLUTE path
# outside work_dir is refused before the engine runs; a relative one under
# work_dir is anchored and allowed.
# ---------------------------------------------------------------------------
def _filecopy_job(source, destination):
    return {
        "job_name": "copyjob",
        "components": [
            {"id": "cp1", "type": "FileCopy",
             "config": {"filename": str(source), "destination": str(destination),
                        "replace_file": True, "create_directory": False},
             "inputs": [], "outputs": [], "schema": {"input": [], "output": []},
             "subjob_id": "sj1", "is_subjob_start": True},
        ],
        "flows": [],
    }


def test_rejects_non_fileoutput_writer_escaping_absolute_path(tmp_path):
    (tmp_path / "src.txt").write_text("hello", encoding="utf-8")
    escape = Path("/tmp") / f"escape_{uuid.uuid4().hex}.txt"  # absolute, outside tmp_path
    assert not escape.exists()
    rr = run_job_capture(_filecopy_job("src.txt", escape), tmp_path)
    assert rr.status == "error"
    assert "escapes" in (rr.error or "")
    assert not escape.exists()  # jail refused the run: nothing written outside work_dir


def test_allows_relative_non_fileoutput_writer_under_work_dir(tmp_path):
    (tmp_path / "src.txt").write_text("hello", encoding="utf-8")
    rr = run_job_capture(_filecopy_job("src.txt", "dst.txt"), tmp_path)  # both relative
    assert rr.status == "success", rr.error
    assert (tmp_path / "dst.txt").read_text(encoding="utf-8") == "hello"


def test_default_deny_catches_escape_in_unmanifested_key(tmp_path):
    # C1 completeness: an absolute path outside work_dir living in a config key that
    # is NOT in _PATH_CONFIG_KEYS is still refused by the recursive default-deny scan
    # -- the jail is not limited to the known path keys.
    escape = Path("/tmp") / f"escape_{uuid.uuid4().hex}"
    job = {
        "job_name": "j",
        "components": [
            {"id": "x", "type": "FilterRows",
             "config": {"some_unmapped_path": str(escape)},  # not a manifest key
             "inputs": [], "outputs": [], "schema": {"input": [], "output": []},
             "subjob_id": "sj1", "is_subjob_start": True},
        ],
        "flows": [],
    }
    rr = run_job_capture(job, tmp_path)
    assert rr.status == "error"
    assert "escapes" in (rr.error or "")


# ---------------------------------------------------------------------------
# I-1 (SECURITY): side-effecting / egress component TYPES are REFUSED before the
# engine runs. run_job_capture executes the job IN-PROCESS during the oracle run
# -- BEFORE any human gate -- so a tSendMail / tOracleOutput / FTP / tSystem etc.
# would fire its real side effect (email sent, DB row written, network egress) and
# could still pass GREEN (the side effect is not a diffed output). The harness
# fail-closes on such a TYPE and never constructs the engine. Enrichment-safe
# LOCAL writers (FileOutputDelimited, FileCopy, ...) are explicitly NOT denied.
# ---------------------------------------------------------------------------
def _sendmail_job():
    return {
        "job_name": "mail",
        "components": [
            {"id": "m1", "type": "tSendMail",
             "config": {"to": "ops@example.com", "subject": "hi", "body": "x"},
             "inputs": [], "outputs": [], "schema": {"input": [], "output": []},
             "subjob_id": "sj1", "is_subjob_start": True},
        ],
        "flows": [],
    }


def test_egress_component_denied_before_engine_runs(tmp_path):
    rr = run_job_capture(_sendmail_job(), tmp_path)
    assert rr.status == "error"
    err = rr.error or ""
    assert "egress" in err and "not permitted" in err
    assert rr.raw_stats == {}  # engine never constructed/executed


def test_egress_gate_denies_known_side_effecting_types():
    from agents.tools.run_and_validate import _is_egress_type
    for t in ["tSendMail", "SendMailComponent", "OracleOutput", "tOracleOutput",
              "tOracleRow", "OracleSP", "OracleBulkExec", "tOracleBulkExec",
              "tMSSqlOutput", "tMSSqlRow", "tMSSqlSP", "MysqlOutput", "tMysqlOutput",
              "tFTPPut", "tFTPGet", "tFileFetch", "tHttpRequest", "tRESTClient",
              "tSOAP", "tSystem", "tSSH", "tJMSOutput", "tKafkaInput", "tSendSMS"]:
        assert _is_egress_type(t) is True, t


def test_egress_gate_does_not_deny_enrichment_safe_writers():
    from agents.tools.run_and_validate import _is_egress_type
    for t in ["FileOutputDelimited", "tFileOutputDelimited", "FileOutputPositional",
              "tFileOutputPositional", "FileOutputExcel", "FileOutputXML",
              "AdvancedFileOutputXML", "FileCopy", "tFileCopy", "FileArchive",
              "FileUnarchive", "FileInputDelimited", "Map", "ConvertType", "SortRow",
              "FilterRows", "OracleInput", "OracleConnection", "OracleClose",
              "OracleCommit", "OracleRollback", "MSSqlInput", "MSSqlConnection",
              "SwiftTransformer", "SwiftBlockFormatter"]:
        assert _is_egress_type(t) is False, t


def test_fileoutput_only_job_not_denied_as_egress(tmp_path):
    # Guard the false-match: a job whose only writer is FileOutputDelimited runs.
    in_csv = tmp_path / "in.csv"
    in_csv.write_text("cc,amt\nUS,10\n")
    rr = run_job_capture(_passthrough_job(in_csv, tmp_path / "out.csv"), tmp_path)
    assert rr.status == "success", rr.error


# ---------------------------------------------------------------------------
# #2: the default-deny path scan is KEY-NAME-AWARE. A string value under a config
# key that does NOT denote a filesystem path (e.g. a FilterRows condition ``value``)
# is a DATA literal, not a write path -- an absolute-path data literal must NOT
# false-refuse the job. Manifest path keys stay hard-jailed.
# ---------------------------------------------------------------------------
def _filterrows_passthrough(in_csv, out_csv, literal, operator="!="):
    cols = [{"name": "cc", "type": "str", "nullable": True, "key": False},
            {"name": "amt", "type": "str", "nullable": True, "key": False}]
    return {
        "job_name": "filter_passthrough",
        "components": [
            {"id": "in1", "type": "FileInputDelimited",
             "config": {"filepath": str(in_csv), "fieldseparator": ",", "header_rows": 1,
                        "die_on_error": False},
             "inputs": [], "outputs": ["f1"],
             "schema": {"input": [], "output": cols},
             "subjob_id": "subjob_1", "is_subjob_start": True},
            {"id": "flt", "type": "FilterRows",
             "config": {"conditions": [{"column": "cc", "function": "", "operator": operator,
                                        "value": literal}],
                        "logical_op": "&&", "use_advanced": False, "advanced_cond": ""},
             "inputs": ["f1"], "outputs": ["f2"],
             "schema": {"input": cols, "output": cols},
             "subjob_id": "subjob_1", "is_subjob_start": False},
            {"id": "out1", "type": "FileOutputDelimited",
             "config": {"filepath": str(out_csv), "fieldseparator": ",", "include_header": True,
                        "file_exist_exception": False, "create_directory": True},
             "inputs": ["f2"], "outputs": [],
             "schema": {"input": cols, "output": []},
             "subjob_id": "subjob_1", "is_subjob_start": False},
        ],
        "flows": [{"name": "f1", "from": "in1", "to": "flt", "type": "flow"},
                  {"name": "f2", "from": "flt", "to": "out1", "type": "flow"}],
    }


def test_absolute_path_data_literal_in_condition_not_refused(tmp_path):
    in_csv = tmp_path / "in.csv"
    in_csv.write_text("cc,amt\nUS,10\nUK,20\n")
    job = _filterrows_passthrough(in_csv, tmp_path / "out.csv", "/mnt/nas/list.csv")
    rr = run_job_capture(job, tmp_path)
    assert "escapes" not in (rr.error or ""), rr.error   # data literal, NOT a path escape
    assert rr.status == "success", rr.error
    assert set(rr.outputs["out1"]["cc"]) == {"US", "UK"}  # rows pass through the filter


def test_jail_scan_skips_data_literal_under_nonpath_key(tmp_path):
    from agents.tools.run_and_validate import _anchor_and_jail_paths
    job = {"components": [
        {"id": "flt", "type": "FilterRows",
         "config": {"conditions": [{"column": "p", "operator": "==",
                                    "value": "/mnt/nas/list.csv"}]}},
    ]}
    assert _anchor_and_jail_paths(job, tmp_path) is None  # data literal, not refused


def test_jail_scan_still_flags_absolute_under_pathish_key(tmp_path):
    from agents.tools.run_and_validate import _anchor_and_jail_paths
    escape = "/tmp/escape_pathish.csv"
    job = {"components": [
        {"id": "x", "type": "FilterRows", "config": {"output_path": escape}},  # 'path' token
    ]}
    assert _anchor_and_jail_paths(job, tmp_path) == escape


# ---------------------------------------------------------------------------
# #4: SwiftBlockFormatter's input_file/output_file are in the jail manifest. A
# SwiftBlockFormatter writing output_file to an ABSOLUTE path outside work_dir is
# refused before the engine runs.
# ---------------------------------------------------------------------------
def test_swift_block_formatter_in_path_manifest():
    from agents.tools.run_and_validate import _PATH_CONFIG_KEYS
    assert _PATH_CONFIG_KEYS["SwiftBlockFormatter"] == ["input_file", "output_file"]
    assert _PATH_CONFIG_KEYS["tSwiftBlockFormatter"] == ["input_file", "output_file"]


def test_swift_block_formatter_output_file_jailed(tmp_path):
    escape = Path("/tmp") / f"escape_{uuid.uuid4().hex}.txt"  # absolute, outside tmp_path
    assert not escape.exists()
    job = {
        "job_name": "swift",
        "components": [
            {"id": "sw1", "type": "SwiftBlockFormatter",
             "config": {"input_file": "in.swift", "output_file": str(escape),
                        "layout": {"block4_20": "S"}, "pipe_fields": ["messagetype"]},
             "inputs": [], "outputs": [], "schema": {"input": [], "output": []},
             "subjob_id": "sj1", "is_subjob_start": True},
        ],
        "flows": [],
    }
    rr = run_job_capture(job, tmp_path)
    assert rr.status == "error"
    assert "escapes" in (rr.error or "")
    assert not escape.exists()  # jail refused the run: nothing written outside work_dir


# ---------------------------------------------------------------------------
# C1 (SECURITY): a SwiftTransformer/tSwiftDataTransformer that loads its
# transform_config from an EXTERNAL config_file eval()s python_expression fields
# (with __import__ in builtins -> full escape) that surface_code_cells cannot
# read -> unsurfaced RCE past the human gate. The harness fail-closes: an external
# config_file is refused BEFORE the engine runs; inline transform_config (which the
# gate CAN surface) is required.
# ---------------------------------------------------------------------------
def _swift_config_file_job(comp_type="SwiftTransformer", config_file="swift_map.yaml"):
    return {
        "job_name": "swift",
        "components": [
            {"id": "sw1", "type": comp_type,
             "config": {"config_file": config_file, "output_file": "out.pipe"},
             "inputs": [], "outputs": [], "schema": {"input": [], "output": []},
             "subjob_id": "sj1", "is_subjob_start": True},
        ],
        "flows": [],
    }


def test_swift_config_file_refused_before_engine_runs(tmp_path):
    # config_file is a RELATIVE path INSIDE work_dir -- the refusal is about the
    # external-config MECHANISM (unsurfaceable code), not the path location.
    rr = run_job_capture(_swift_config_file_job(), tmp_path)
    assert rr.status == "error"
    err = rr.error or ""
    assert "config_file" in err and "inline transform_config required" in err
    assert rr.raw_stats == {}  # engine never constructed/executed


def test_swift_config_file_alias_also_refused(tmp_path):
    rr = run_job_capture(_swift_config_file_job(comp_type="tSwiftDataTransformer"), tmp_path)
    assert rr.status == "error"
    assert "inline transform_config required" in (rr.error or "")
    assert rr.raw_stats == {}


def test_swift_inline_transform_config_not_refused_as_config_file(tmp_path):
    # A Swift with only an inline transform_config (no config_file) IS the
    # surfaceable path; it must NOT be refused on C1 config_file grounds, whatever
    # else the engine does with a source-less component.
    job = {
        "job_name": "swift_inline",
        "components": [
            {"id": "sw1", "type": "SwiftTransformer",
             "config": {"transform_config": {"output_fields": [
                 {"name": "A", "type": "constant", "value": "x"}]}},
             "inputs": [], "outputs": [], "schema": {"input": [], "output": []},
             "subjob_id": "sj1", "is_subjob_start": True},
        ],
        "flows": [],
    }
    rr = run_job_capture(job, tmp_path)
    assert "config_file" not in (rr.error or "")


# ---------------------------------------------------------------------------
# I-nested (SECURITY): a tRunJob/RunJob runs a CHILD job nested in-process, so
# every child component bypasses the egress gate, path-jail, code surfacing and
# human gate. The harness fail-closes: any RunJob/tRunJob (case-insensitive)
# refuses the run before the engine is constructed.
# ---------------------------------------------------------------------------
def _runjob_job(comp_type="tRunJob"):
    return {
        "job_name": "parent",
        "components": [
            {"id": "rj1", "type": comp_type,
             "config": {"job": "child_job", "context_name": "Default"},
             "inputs": [], "outputs": [], "schema": {"input": [], "output": []},
             "subjob_id": "sj1", "is_subjob_start": True},
        ],
        "flows": [],
    }


def test_nested_runjob_refused_before_engine_runs(tmp_path):
    rr = run_job_capture(_runjob_job(), tmp_path)
    assert rr.status == "error"
    err = rr.error or ""
    assert "tRunJob" in err and "not permitted" in err
    assert rr.raw_stats == {}  # engine never constructed/executed


def test_nested_runjob_camelcase_alias_refused(tmp_path):
    rr = run_job_capture(_runjob_job(comp_type="RunJob"), tmp_path)
    assert rr.status == "error"
    assert "not permitted" in (rr.error or "")
    assert rr.raw_stats == {}


# ---------------------------------------------------------------------------
# I-configblocks (SECURITY): top-level python_config.routines_dir and
# java_config.libraries/routines/routine_jars name FILESYSTEM code-load paths that
# the component path-jail never touched. A value escaping work_dir loads code from
# outside the sandbox before any human review. They are jailed the same way: a
# value that LOOKS like a path (absolute, or contains os.sep) must resolve inside
# work_dir. A dotted routine NAME (routines.TalendDate) is not a path -> skipped,
# so golden/example jobs (whose routines are all dotted) still run.
# ---------------------------------------------------------------------------
def test_python_config_routines_dir_escape_refused(tmp_path):
    job = {"job_name": "j", "components": [],
           "python_config": {"enabled": True, "routines_dir": "/etc"}}
    rr = run_job_capture(job, tmp_path)
    assert rr.status == "error"
    assert "config path escapes work_dir" in (rr.error or "")
    assert rr.raw_stats == {}  # engine never constructed/executed


def test_config_block_jail_refuses_escaping_routines_dir(tmp_path):
    from agents.tools.run_and_validate import _jail_config_blocks
    job = {"python_config": {"routines_dir": "/etc"}}
    assert _jail_config_blocks(job, tmp_path) == "/etc"


def test_config_block_jail_refuses_dotdot_routines_dir(tmp_path):
    from agents.tools.run_and_validate import _jail_config_blocks
    esc = "../../../../etc"
    job = {"python_config": {"routines_dir": esc}}
    assert _jail_config_blocks(job, tmp_path) == esc


def test_config_block_jail_refuses_escaping_java_library(tmp_path):
    from agents.tools.run_and_validate import _jail_config_blocks
    job = {"java_config": {"libraries": ["/opt/evil.jar"]}}
    assert _jail_config_blocks(job, tmp_path) == "/opt/evil.jar"


def test_config_block_jail_skips_dotted_java_routines(tmp_path):
    # Dotted Talend routine NAMES are not filesystem paths -> never refused (golden).
    from agents.tools.run_and_validate import _jail_config_blocks
    job = {"java_config": {"enabled": True, "libraries": [],
                           "routines": ["routines.TalendDate", "routines.StringHandling",
                                        "routines.DataOperation"]}}
    assert _jail_config_blocks(job, tmp_path) is None


def test_config_block_jail_allows_relative_inside_work_dir(tmp_path):
    from agents.tools.run_and_validate import _jail_config_blocks
    job = {"python_config": {"routines_dir": "src/python_routines"}}
    assert _jail_config_blocks(job, tmp_path) is None  # relative, non-escaping
