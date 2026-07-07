"""Deterministic parity harness: run a job through the real engine, harvest
signals, and (Task 5) diff actual output against golden expected data.

This module runs a job config IN-PROCESS through ``ETLEngine`` (no subprocess)
and harvests the run's signals into a ``RunResult``. The engine's ``execute()``
returns two different dict shapes -- a success shape (with ``global_map`` and
``job_aborted``) and an exception shape (which has neither) -- so every field is
read with ``.get()``. The ACTUAL output is read back from the produced FILES,
not from in-memory flows (which the engine clears per subjob). Dropped
components are the config ids whose component ``type`` is not registered -- the
exact rule the fail-open engine uses to silently skip a component
(engine.py:192-194). This is NOT "absent from ``component_stats``": a known-type
component that simply never ran (e.g. one in an untriggered conditional subjob)
is legitimately missing from ``component_stats`` yet is NOT dropped.
"""
from __future__ import annotations

import copy
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# FileOutput component type aliases (engine registers both the camelCase and the
# Talend t-prefixed name for the same class).
_FILE_OUTPUT_TYPES = {"FileOutputDelimited", "tFileOutputDelimited"}

# Registered FileOutput WRITERS whose produced files the readback does NOT harvest
# (only the delimited family is read back). A declared output pointing at one of
# these yields actual=None; check() reports a clear "delimited only" reason rather
# than the generic "no actual output" diff (#2/#9).
_NON_DELIMITED_OUTPUT_TYPES = {
    "FileOutputPositional", "tFileOutputPositional",
    "FileOutputExcel", "tFileOutputExcel",
    "FileOutputXML", "tFileOutputXML",
    "AdvancedFileOutputXML", "tAdvancedFileOutputXML",
}


def _output_component_ids(job: dict) -> set:
    """Ids of every FileOutput-family writer -- the assembler binds each terminal
    FileOutput's id to its Expected-Output name, so this is the set of valid
    graded-output ids."""
    writers = _FILE_OUTPUT_TYPES | _NON_DELIMITED_OUTPUT_TYPES
    return {c.get("id") for c in job.get("components", []) if c.get("type") in writers}

# ---------------------------------------------------------------------------
# I-1 (SECURITY): fail-closed egress / side-effecting pre-execution gate.
# ---------------------------------------------------------------------------
# ``run_job_capture`` executes the job IN-PROCESS during the deterministic oracle
# run -- BEFORE any human gate -- so a component that performs a real-world SIDE
# EFFECT (email sent, DB row written/executed, file pushed over FTP/HTTP, remote
# command run, message published) would fire for real, and could still pass GREEN
# because the side effect is not one of the diffed outputs. The harness therefore
# REFUSES to run any job that declares such a component TYPE.
#
# Matching is case-insensitive on the registered TYPE name and covers both the
# camelCase and the Talend ``t``-prefixed spelling. It is DENY-BY-INTENT: an
# explicit known-type set plus a few PRECISE substrings, chosen so NO enrichment-
# safe LOCAL writer (FileOutputDelimited/Positional/Excel/XML, FileCopy,
# FileArchive/Unarchive, ...) is ever matched -- there is deliberately no bare
# "output" substring. Local DB READERS / CONNECTIONS (OracleInput/OracleConnection,
# MSSqlInput) are NOT denied; only WRITES / EXECS are.
_EGRESS_DENY_TYPES = {
    # email
    "sendmailcomponent", "tsendmail",
    # DB writes / execs -- Oracle
    "oracleoutput", "toracleoutput", "oraclerow", "toraclerow",
    "oraclesp", "toraclesp", "oraclebulkexec", "toraclebulkexec",
    # DB writes / execs -- MSSql
    "mssqloutput", "tmssqloutput", "mssqlrow", "tmssqlrow", "mssqlsp", "tmssqlsp",
    # DB writes -- MySQL
    "mysqloutput", "tmysqloutput",
    # network transfer / remote fetch
    "ftpput", "tftpput", "ftpget", "tftpget", "filefetch", "tfilefetch",
    "httprequest", "thttprequest", "restclient", "trestclient",
    "soap", "tsoap", "sendsms", "tsendsms",
    # system / remote execution
    "system", "tsystem", "ssh", "tssh",
    # messaging
    "jms", "tjms", "kafka", "tkafka",
}
# Precise substrings: any TYPE whose lowercased name CONTAINS one of these is
# denied. Covers family variants (any ``*BulkExec``, ``tJMSInput``/``tJMSOutput``,
# ``tKafkaInput``/``tKafkaOutput``, ``tFTPGet``/``tFTPPut``) without enumerating
# every spelling. Each is chosen so no enrichment-safe writer name contains it.
_EGRESS_DENY_SUBSTR = (
    "sendmail", "ftp", "httprequest", "restclient", "soap", "tsystem", "tssh",
    "bulkexec", "sendsms", "jms", "kafka",
    "oracleoutput", "oraclerow", "oraclesp",
    "mssqloutput", "mssqlrow", "mssqlsp", "mysqloutput",
)


def _is_egress_type(comp_type) -> bool:
    """True if a component TYPE is side-effecting/egress and must not auto-run.

    Case-insensitive; matches an explicit known-type set or a precise substring.
    Enrichment-safe local writers (FileOutput*, FileCopy, FileArchive, ...) are
    never matched -- guarded by test."""
    if not isinstance(comp_type, str) or not comp_type:
        return False
    t = comp_type.strip().lower()
    if t in _EGRESS_DENY_TYPES:
        return True
    return any(sub in t for sub in _EGRESS_DENY_SUBSTR)


# ---------------------------------------------------------------------------
# C1 (SECURITY): SwiftTransformer external config_file -> unsurfaced code.
# ---------------------------------------------------------------------------
# SwiftTransformer/tSwiftDataTransformer eval() their python_expression fields with
# ``__import__`` present in builtins (a full escape). surface_code_cells only walks
# the INLINE ``transform_config``; when the transform is loaded from an EXTERNAL
# ``config_file`` (YAML/JSON) those code fields are never surfaced to the human gate.
# The harness fail-closes: a Swift component declaring a non-empty ``config_file`` is
# refused so the gate is never silently blind. Registered under both spellings.
_SWIFT_TRANSFORMER_TYPES = {"swifttransformer", "tswiftdatatransformer"}

# I-nested (SECURITY): a tRunJob/RunJob runs a CHILD job nested in-process, so every
# child component bypasses the egress gate, path-jail, code surfacing and human gate.
# Refuse it; the child job must be reviewed/run on its own.
_NESTED_JOB_TYPES = {"runjob", "trunjob"}


def _is_swift_transformer_type(comp_type) -> bool:
    """True if a component TYPE is a SwiftTransformer (either spelling), case-insensitive."""
    return isinstance(comp_type, str) and comp_type.strip().lower() in _SWIFT_TRANSFORMER_TYPES


def _is_nested_job_type(comp_type) -> bool:
    """True if a component TYPE is a nested-job runner (RunJob/tRunJob), case-insensitive."""
    return isinstance(comp_type, str) and comp_type.strip().lower() in _NESTED_JOB_TYPES


def _swift_declares_config_file(component) -> bool:
    """True when a component config declares a non-empty ``config_file`` string.

    ``config_file`` WINS over an inline ``transform_config`` in the engine
    (see SwiftTransformer._ensure_config_loaded), so its mere presence means the
    transform code is loaded externally and cannot be surfaced -- refuse it."""
    cfg = component.get("config")
    if not isinstance(cfg, dict):
        return False
    cf = cfg.get("config_file")
    return isinstance(cf, str) and cf.strip() != ""


@dataclass
class RunResult:
    """Signals harvested from one engine run of a job.

    Attributes:
        status: Engine run status ("success" or "error").
        job_aborted: True when a tDie/abort short-circuited the job. Absent from
            the engine's exception shape, so defaults to False.
        error: Error string from the engine, or None on success.
        global_map: Talend-compatible globalMap stats (NB_LINE, etc.). Absent
            from the engine's exception shape, so defaults to empty.
        component_stats: Per-component execution stats keyed by component id.
        dropped_components: Component ids whose type is unregistered
            (engine-skipped).
        outputs: Actual output DataFrames read back from each FileOutput
            component's file, keyed by output-component id.
        raw_stats: The unmodified stats dict returned by ``ETLEngine.execute()``.
    """
    status: str
    job_aborted: bool = False
    error: str | None = None
    global_map: dict = field(default_factory=dict)
    component_stats: dict = field(default_factory=dict)
    dropped_components: list = field(default_factory=list)
    outputs: dict = field(default_factory=dict)
    raw_stats: dict = field(default_factory=dict)


def _header_enabled(value) -> bool:
    """True when ``include_header`` is on, matching FileOutputDelimited._bool.

    JSON configs may carry booleans as the strings ``"true"``/``"false"``, and
    Python's ``bool("false")`` is ``True`` -- so a naive truthiness check would
    mis-read a headerless file whose config said ``"false"``. Coerce the same way
    the engine does so the readback agrees with how the file was actually WRITTEN.
    """
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    return bool(value)


def _read_output(component: dict):
    """Read a FileOutput component's produced file back into a DataFrame.

    Reads every field as a string (``dtype=str``, ``keep_default_na=False``) so
    the captured output is compared textually against golden data in Task 5,
    with no pandas type inference. A missing or unreadable file yields None --
    that absence is itself a signal, not a crash.

    Header handling MUST match how the engine wrote the file. FileOutputDelimited
    defaults ``include_header=False`` (engine default), so a headerless file's
    first line is DATA, not column names -- reading it with pandas' default
    ``header=0`` would eat the first data row and mislabel the columns, and a keyed
    diff would then ``KeyError`` on a key that "vanished". When the header is off,
    read with ``header=None`` and ASSIGN column names from the sink's DECLARED input
    columns (a FileOutput writes its INPUT schema); with no declared schema names,
    fall back to ``header=None`` with pandas' default integer columns.

    Args:
        component: A component config dict with a ``config.filepath``, an optional
            ``config.fieldseparator`` (defaults to ";"), an optional
            ``config.include_header`` (defaults False -- the engine default), and a
            ``schema.input`` column list used to name headerless columns.

    Returns:
        A DataFrame of the file's contents, or None if the file is missing or
        cannot be parsed.
    """
    cfg = component.get("config", {})
    path = cfg.get("filepath")
    if not path or not Path(path).exists():
        return None
    sep = cfg.get("fieldseparator", ";")
    header_on = _header_enabled(cfg.get("include_header", False))
    try:
        if header_on:
            return pd.read_csv(path, sep=sep, dtype=str, keep_default_na=False)
        names = [c["name"] for c in component.get("schema", {}).get("input", [])
                 if isinstance(c, dict) and c.get("name")]
        if names:
            return pd.read_csv(path, sep=sep, dtype=str, keep_default_na=False,
                               header=None, names=names)
        return pd.read_csv(path, sep=sep, dtype=str, keep_default_na=False, header=None)
    except Exception as exc:  # a malformed/empty output file is a signal, not a crash
        logger.warning("[run_and_validate] could not read output %s: %s", path, exc)
        return None


def _dropped_components(components: list) -> list:
    """Config ids whose component TYPE is not registered -- the engine silently
    skips these (engine.py:192-194). A known-type component that simply did not
    run (e.g. an untriggered conditional subjob) has a registered type and is
    NOT dropped."""
    from src.v1.engine.component_registry import REGISTRY
    return [c.get("id") for c in components if REGISTRY.get(c.get("type")) is None]


# Path-config manifest: for each engine component TYPE (registered under both the
# camelCase and the Talend ``t``-prefixed spelling), the config keys that hold a
# FILESYSTEM path. Used to (a) anchor RELATIVE paths under work_dir so the engine
# reads/writes there regardless of the process CWD, and (b) jail ABSOLUTE paths to
# work_dir. Keys are the exact ones each component reads from ``self.config``. The
# earlier jail only covered the FileOutput* family, so ~8 other writers (FileCopy,
# FileTouch, ChangeFileEncoding, PivotToColumnsDelimited, SwiftTransformer,
# FileArchive/Unarchive) could write OUTSIDE work_dir with no check -- this closes
# that gap by naming their write keys too.
_PATH_CONFIG_KEYS = {
    # ---- File INPUT (readers) ----
    "FileInputDelimited": ["filepath"], "tFileInputDelimited": ["filepath"],
    "FileInputExcel": ["filepath"], "tFileInputExcel": ["filepath"],
    "FileInputPositional": ["filepath"], "tFileInputPositional": ["filepath"],
    "FileInputXML": ["filepath"], "tFileInputXML": ["filepath"],
    "FileInputFullRowComponent": ["filename"], "tFileInputFullRow": ["filename"],
    "FileInputJSON": ["filename"], "tFileInputJSON": ["filename"],
    "FileInputMSXML": ["filename"], "tFileInputMSXML": ["filename"],
    "FileInputProperties": ["filename"], "tFileInputProperties": ["filename"],
    "FileInputRaw": ["filename"], "tFileInputRaw": ["filename"],
    # ---- File OUTPUT (writers) ----
    "FileOutputDelimited": ["filepath"], "tFileOutputDelimited": ["filepath"],
    "FileOutputPositional": ["filepath"], "tFileOutputPositional": ["filepath"],
    "FileOutputExcel": ["filename"], "tFileOutputExcel": ["filename"],
    "FileOutputXML": ["filename"], "tFileOutputXML": ["filename"],
    "AdvancedFileOutputXML": ["filename"], "tAdvancedFileOutputXML": ["filename"],
    # ---- Other WRITERS the FileOutput-only jail missed (C1) ----
    "FileCopy": ["filename", "source_derectory", "source_directory", "source", "destination"],
    "tFileCopy": ["filename", "source_derectory", "source_directory", "source", "destination"],
    "FileTouch": ["filename", "FILENAME"], "tFileTouch": ["filename", "FILENAME"],
    "ChangeFileEncoding": ["infile_name", "outfile_name"],
    "tChangeFileEncoding": ["infile_name", "outfile_name"],
    "PivotToColumnsDelimited": ["filename"], "tPivotToColumnsDelimited": ["filename"],
    "SwiftTransformer": ["config_file", "output_file"],
    "tSwiftDataTransformer": ["config_file", "output_file"],
    "SwiftBlockFormatter": ["input_file", "output_file"],
    "tSwiftBlockFormatter": ["input_file", "output_file"],
    "FileArchive": ["source", "target"], "FileArchiveComponent": ["source", "target"],
    "tFileArchive": ["source", "target"],
    "FileUnarchive": ["zipfile", "directory"], "FileUnarchiveComponent": ["zipfile", "directory"],
    "tFileUnarchive": ["zipfile", "directory"],
    # ---- File-operation components (walkers / deleters / probes) ----
    "FileDelete": ["path", "PATH", "directory", "DIRECTORY", "filename", "FILENAME"],
    "tFileDelete": ["path", "PATH", "directory", "DIRECTORY", "filename", "FILENAME"],
    "FileExistComponent": ["file_name", "file_path", "FILE_NAME"],
    "FileExist": ["file_name", "file_path", "FILE_NAME"],
    "tFileExist": ["file_name", "file_path", "FILE_NAME"],
    "FileList": ["DIRECTORY", "directory"], "tFileList": ["DIRECTORY", "directory"],
    "FileProperties": ["filename"], "tFileProperties": ["filename"],
    "FileRowCount": ["filename"], "tFileRowCount": ["filename"],
}

# FileOutput-family target files eligible for idempotent PRE-deletion (map TYPE ->
# the single config key holding the produced file). FileOutputDelimited defaults
# ``file_exist_exception=True``, so a stale target from a prior run would raise on
# re-run; deleting a confirmed-inside-work_dir target first keeps re-runs green (I2).
_OUTPUT_FILE_TARGET_KEY = {
    "FileOutputDelimited": "filepath", "tFileOutputDelimited": "filepath",
    "FileOutputPositional": "filepath", "tFileOutputPositional": "filepath",
    "FileOutputExcel": "filename", "tFileOutputExcel": "filename",
    "FileOutputXML": "filename", "tFileOutputXML": "filename",
    "AdvancedFileOutputXML": "filename", "tAdvancedFileOutputXML": "filename",
}


def _jail_value(value: str, root: Path) -> str | None:
    """Jail one path VALUE to ``root``; return the value to STORE, or None if it escapes.

    A RELATIVE value is ANCHORED -- ``(root / value).resolve()`` -- so the engine
    reads/writes it UNDER work_dir regardless of the process CWD (fixes I1); the
    anchored result must still be inside root, so a ``../..`` anchor that climbs out
    is refused. An ABSOLUTE value is kept as-authored, but its ``realpath`` (which
    collapses ``..`` and follows symlinks) must be inside ``realpath(root)``, else it
    is refused -- an absolute-outside, ``..``-escape, or symlink-escape is blocked.
    """
    if os.path.isabs(value):
        resolved = Path(os.path.realpath(value))
        return value if resolved.is_relative_to(root) else None
    resolved = (root / value).resolve()
    return str(resolved) if resolved.is_relative_to(root) else None


def _looks_like_path(value: str) -> bool:
    """Conservative path sniff for the default-deny fallback: an ABSOLUTE path, or a
    value carrying a ``..`` traversal SEGMENT plus a separator. Deliberately narrow so
    plain expression strings (``source_flow.cc``, ``amount / 100``, date patterns like
    ``dd/MM/yyyy``) are NOT flagged -- only isabs or ``..``-traversal values are."""
    if os.path.isabs(value):
        return True
    return os.sep in value and ".." in value.split(os.sep)


# Config-KEY name tokens that plausibly denote a FILESYSTEM path. The default-deny
# catch-all (``_scan_escaping_path``) only jails a string value whose KEY name is
# path-denoting -- so a DATA literal that happens to be an absolute path but lives
# under a value/expression/condition key (e.g. a FilterRows condition ``value``,
# ``expression``, ``filter``, ``columns``, ``array``) is NOT false-refused (#2).
# Manifest keys (``_PATH_CONFIG_KEYS``) stay hard-jailed regardless.
_PATH_KEY_TOKENS = ("path", "file", "dir", "folder", "destination",
                    "outfile", "infile", "target", "archive")
# Every exact key name that appears anywhere in the manifest -- such a key denotes a
# path even if it carries no token (e.g. ``source``, ``zipfile``, ``source_derectory``).
_PATH_KEY_NAMES = {k for keys in _PATH_CONFIG_KEYS.values() for k in keys}


def _key_denotes_path(key) -> bool:
    """True when a config KEY NAME plausibly holds a filesystem path -- a token match
    (``path``/``file``/``dir``/...) or an exact manifest key name. Value/expression/
    condition keys (``value``, ``conditions``, ``expression``, ...) return False, so a
    data literal under them is not treated as a write path (#2)."""
    if not isinstance(key, str) or not key:
        return False
    if key in _PATH_KEY_NAMES:
        return True
    k = key.lower()
    return any(tok in k for tok in _PATH_KEY_TOKENS)


def _scan_escaping_path(node, root: Path, pathish: bool = False) -> str | None:
    """Recursively scan a config subtree; return the first string that (a) sits under
    a path-denoting KEY and (b) LOOKS like a path yet escapes ``root``, else None.

    This is the default-deny catch-all for any path-bearing key NOT in
    ``_PATH_CONFIG_KEYS`` -- an unmanifested absolute/``..`` write path cannot slip
    past the jail. It is KEY-NAME-AWARE (#2): a string is only path-checked when its
    config key denotes a filesystem path (``_key_denotes_path``), so an absolute-path
    DATA literal under a value/expression/condition key is not false-refused. In a
    dict each value inherits ITS OWN key's path-ness; in a list/tuple items inherit
    the enclosing key's path-ness."""
    if isinstance(node, dict):
        for k, v in node.items():
            hit = _scan_escaping_path(v, root, _key_denotes_path(k))
            if hit is not None:
                return hit
    elif isinstance(node, (list, tuple)):
        for v in node:
            hit = _scan_escaping_path(v, root, pathish)
            if hit is not None:
                return hit
    elif pathish and isinstance(node, str) and node and _looks_like_path(node):
        if not Path(os.path.realpath(node)).is_relative_to(root):
            return node
    return None


def _anchor_and_jail_paths(job: dict, work_dir) -> str | None:
    """Anchor RELATIVE paths under work_dir and JAIL every path to work_dir, in place
    on ``job``. Returns the offending (as-authored) path if any escapes, else None.

    Two layers run per component, in order:
      1. Manifest layer -- each known path key (``_PATH_CONFIG_KEYS``) is anchored
         (relative -> absolute under work_dir) or jail-checked (absolute must be
         inside work_dir). This fixes the FileOutput-only allowlist: every registered
         writer's write key is now jailed.
      2. Default-deny fallback -- EVERY remaining string config value is sniffed with
         ``_looks_like_path``; an absolute or ``..``-traversal value that escapes
         work_dir is refused too, so a path-bearing key absent from the manifest still
         cannot write outside the jail.

    Both work_dir and each absolute path are ``realpath``'d so a symlinked work_dir
    (e.g. macOS ``/tmp`` -> ``/private/tmp``) compares consistently.
    """
    root = Path(os.path.realpath(str(work_dir)))
    for comp in job.get("components", []):
        cfg = comp.get("config")
        if not isinstance(cfg, dict):
            continue
        for key in _PATH_CONFIG_KEYS.get(comp.get("type"), ()):
            val = cfg.get(key)
            if not isinstance(val, str) or not val:
                continue
            jailed = _jail_value(val, root)
            if jailed is None:
                return val
            cfg[key] = jailed
        offending = _scan_escaping_path(cfg, root)
        if offending is not None:
            return offending
    return None


# ---------------------------------------------------------------------------
# I-configblocks (SECURITY): jail top-level java_config / python_config CODE-LOAD
# paths -- the component path-jail never reaches them.
# ---------------------------------------------------------------------------
# ``python_config.routines_dir`` and ``java_config.libraries``/``routines``/
# ``routine_jars`` name FILESYSTEM locations the engine imports CODE from (Python
# routine modules, Java JARs). A value pointing OUTSIDE work_dir (routines_dir=/etc,
# a ``../..`` climb, an absolute JAR path) would load code from beyond the sandbox
# before any human review. Only values that LOOK like a filesystem path are checked;
# a dotted Talend routine NAME (``routines.TalendDate``) carries no separator and is
# not absolute, so it is skipped and golden/example jobs (whose routines are all
# dotted) still run. Values are NOT rewritten -- the engine resolves a code-load path
# against its own CWD and anchoring it into a temp work_dir would break legitimate
# routine loading; the jail's job here is purely to REFUSE an escaping path.
_CONFIG_BLOCK_PATH_FIELDS = {
    "python_config": ("routines_dir",),
    "java_config": ("libraries", "routines", "routine_jars"),
}


def _looks_like_fs_path(value) -> bool:
    """True when a config-block string looks like a FILESYSTEM path: it is absolute,
    or it contains an os separator. A dotted routine name (``routines.TalendDate``)
    has neither, so it is NOT treated as a path (I-configblocks)."""
    return isinstance(value, str) and bool(value) and (os.path.isabs(value) or os.sep in value)


def _config_path_values(job: dict):
    """Yield each string value from the config-block code-load path fields.

    A field may hold a single string (``python_config.routines_dir``) or a list of
    strings (``java_config.libraries``/``routines``/``routine_jars``); both are
    flattened to individual strings. Non-string entries are ignored."""
    for block, fields in _CONFIG_BLOCK_PATH_FIELDS.items():
        cfg = job.get(block)
        if not isinstance(cfg, dict):
            continue
        for field_name in fields:
            val = cfg.get(field_name)
            if isinstance(val, str):
                yield val
            elif isinstance(val, (list, tuple)):
                for item in val:
                    if isinstance(item, str):
                        yield item


def _jail_config_blocks(job: dict, work_dir) -> str | None:
    """Refuse the run if any top-level config-block code-load path escapes work_dir.

    Returns the offending (as-authored) path if one escapes, else None. Only values
    that look like filesystem paths are checked (``_looks_like_fs_path``); dotted
    routine names are skipped. An absolute-outside, ``..``-escape, or symlink-escape
    resolves outside ``realpath(work_dir)`` and is reported."""
    root = Path(os.path.realpath(str(work_dir)))
    for value in _config_path_values(job):
        if _looks_like_fs_path(value) and _jail_value(value, root) is None:
            return value
    return None


def _clean_output_targets(job: dict, work_dir) -> None:
    """Delete any already-existing declared FileOutput target FILE under work_dir
    before the run, so a re-run starts clean (I2). Only paths confirmed inside
    work_dir are removed and only regular files -- directories are never touched.
    Call AFTER ``_anchor_and_jail_paths`` so target keys already hold jailed paths."""
    root = Path(os.path.realpath(str(work_dir)))
    for comp in job.get("components", []):
        key = _OUTPUT_FILE_TARGET_KEY.get(comp.get("type"))
        if not key:
            continue
        val = (comp.get("config") or {}).get(key)
        if not isinstance(val, str) or not val:
            continue
        target = Path(os.path.realpath(val))
        if target.is_relative_to(root) and target.is_file():
            try:
                target.unlink()
            except OSError as exc:  # a non-removable stale target is a warning, not a crash
                logger.warning("[run_and_validate] could not pre-delete output %s: %s", target, exc)


def run_job_capture(job_config: dict, work_dir) -> RunResult:
    """Run a job through ETLEngine and harvest its run signals into a RunResult.

    The job config is deep-copied before running so the caller's dict is never
    mutated by the engine. Any exception raised while constructing or executing
    the engine is tolerated and converted into a uniform ``status="error"``
    result rather than propagating.

    Before running, the deep-copied job is rewritten so the jail root is
    ``work_dir`` (see ``_anchor_and_jail_paths``):
      * RELATIVE path-config values (the shape the skill teaches) are ANCHORED under
        work_dir, so the engine reads/writes them there even though the CLI runs from
        the workspace root (CWD != work_dir) -- a correct relative job is no longer
        false-refused.
      * ABSOLUTE path values must resolve INSIDE work_dir; an absolute-outside,
        ``..``-escape, or symlink-escape is REFUSED with ``status="error"`` and nothing
        is written. The jail is default-deny across ALL registered writers (not just
        the FileOutput* family) plus a catch-all scan of every string config value, so
        an LLM-authored or doc-injected path (e.g. ``~/.ssh/authorized_keys``) is
        blocked before any human review.
    After jailing, any already-existing declared FileOutput target file UNDER
    work_dir is deleted (see ``_clean_output_targets``) so a re-run starts clean
    despite ``file_exist_exception`` defaulting True. Output frames are then read
    back from the SAME rewritten (jailed) filepaths the engine wrote.

    Args:
        job_config: The engine job configuration dict.
        work_dir: The working directory for the run and the path-jail root: relatives
            are anchored under it and every resolved path must live inside it.

    Returns:
        A ``RunResult`` capturing status, globalMap, per-component stats,
        component ids whose type is unregistered (engine-skipped), and the
        actual output DataFrames. If any path escapes work_dir, an error
        ``RunResult`` whose ``error`` names the offending path (and the engine is
        never run).
    """
    from src.v1.engine.engine import ETLEngine

    job = copy.deepcopy(job_config)

    # I-1 (SECURITY): fail-closed on side-effecting / egress component types BEFORE
    # constructing or running the engine -- the in-process oracle run would otherwise
    # fire the real side effect (email / DB-write / network egress) ahead of any human
    # gate, and could still pass GREEN. No engine is constructed when a denied type is
    # present; the offending type is named for human review.
    for comp in job.get("components", []):
        t = comp.get("type")
        if _is_egress_type(t):
            msg = (f"component type '{t}' is side-effecting/egress and is not permitted "
                   f"in the enrichment harness; requires human review before execution")
            logger.warning("[run_and_validate] %s", msg)
            return RunResult(status="error", error=msg)
        # I-nested (SECURITY): a tRunJob/RunJob runs a CHILD job nested in-process,
        # so every child component bypasses the egress gate, path-jail, code
        # surfacing and human gate. Refuse it; the child must be reviewed/run alone.
        if _is_nested_job_type(t):
            msg = ("nested tRunJob child jobs are not permitted in the enrichment "
                   "harness (they bypass the safety nets); review/run the child job "
                   "independently")
            logger.warning("[run_and_validate] %s", msg)
            return RunResult(status="error", error=msg)
        # C1 (SECURITY): a SwiftTransformer loading its transform from an EXTERNAL
        # config_file eval()s python_expression fields (with __import__ in builtins)
        # that surface_code_cells cannot read -> unsurfaced RCE past the human gate.
        # Require an inline transform_config the gate CAN surface.
        if _is_swift_transformer_type(t) and _swift_declares_config_file(comp):
            msg = ("SwiftTransformer config_file loads code the human gate cannot "
                   "surface; inline transform_config required")
            logger.warning("[run_and_validate] %s", msg)
            return RunResult(status="error", error=msg)

    # I-configblocks (SECURITY): jail top-level java_config/python_config code-load
    # paths (routines_dir, JAR libraries/routine_jars) so none escapes work_dir before
    # the engine imports code from it. Dotted routine NAMES are not paths -> skipped.
    cfg_escape = _jail_config_blocks(job, work_dir)
    if cfg_escape is not None:
        msg = f"config path escapes work_dir: {cfg_escape}"
        logger.warning("[run_and_validate] %s", msg)
        return RunResult(status="error", error=msg)

    escaped = _anchor_and_jail_paths(job, work_dir)
    if escaped is not None:
        msg = f"path escapes work_dir: {escaped}"
        logger.warning("[run_and_validate] %s", msg)
        return RunResult(status="error", error=msg)

    _clean_output_targets(job, work_dir)

    try:
        engine = ETLEngine(job)
        stats = engine.execute()
    except Exception as exc:  # constructor/other hard failure -> uniform error result
        logger.warning("[run_and_validate] engine raised: %s", exc)
        return RunResult(status="error", error=str(exc))

    component_stats = stats.get("component_stats", {})
    dropped = _dropped_components(job.get("components", []))

    outputs = {}
    for comp in job.get("components", []):
        if comp.get("type") in _FILE_OUTPUT_TYPES:
            df = _read_output(comp)
            if df is not None:
                outputs[comp["id"]] = df

    return RunResult(
        status=stats.get("status", "error"),
        job_aborted=bool(stats.get("job_aborted", False)),
        error=stats.get("error"),
        global_map=stats.get("global_map", {}),
        component_stats=component_stats,
        dropped_components=dropped,
        outputs=outputs,
        raw_stats=stats,
    )


def _bag(df: pd.DataFrame):
    return sorted(tuple(str(v) for v in row) for row in df.itertuples(index=False, name=None))


def diff_frames(actual, expected, keys):
    """Diff an actual output frame vs expected: keyed diff, or bag equality if keys is None."""
    if actual is None:
        return {"equal": False, "missing": int(len(expected)), "unexpected": 0, "value_mismatch": 0,
                "reason": "no actual output"}
    if not keys:
        # Bag equality must be column-NAME aware, not column-ORDER dependent: a
        # different set of column names is a mismatch even with equal values, and
        # a mere column reorder is not. Canonicalize actual onto expected's column
        # order before bagging so order is irrelevant but names are enforced.
        if set(actual.columns) != set(expected.columns):
            return {"equal": False, "reason": "column set mismatch",
                    "actual_rows": len(actual), "expected_rows": len(expected)}
        a = _bag(actual[list(expected.columns)])
        e = _bag(expected)
        return {"equal": a == e, "actual_rows": len(actual), "expected_rows": len(expected)}
    # A keyed diff needs its key columns present in ACTUAL, else set_index() raises
    # KeyError. A missing key column -- e.g. a headerless output mis-read, or a
    # schema mismatch that dropped the key -- is a clean FAIL, not a crash.
    missing_key_cols = [k for k in keys if k not in actual.columns]
    if missing_key_cols:
        return {"equal": False, "missing": int(len(expected)), "unexpected": 0, "value_mismatch": 0,
                "reason": f"key columns {missing_key_cols} missing from actual output"}
    exp = expected.astype(str).set_index(keys, drop=False)
    act = actual.astype(str).set_index(keys, drop=False)
    if exp.index.has_duplicates or act.index.has_duplicates:
        return {"equal": False, "missing": 0, "unexpected": 0, "value_mismatch": 0,
                "reason": f"declared key {keys} is not unique in expected/actual"}
    # A column present in ACTUAL but not EXPECTED is never value-checked below
    # (the loop iterates expected's columns), so it would silently pass. Flag it.
    extra_cols = [c for c in actual.columns if c not in expected.columns]
    # Symmetric to extra_cols: an EXPECTED column absent from ACTUAL is only caught
    # by the value loop when there are common rows, so the 0-rows case would slip
    # through. Flag it unconditionally.
    missing_cols = [c for c in expected.columns if c not in actual.columns]
    missing = exp.index.difference(act.index)
    unexpected = act.index.difference(exp.index)
    common = exp.index.intersection(act.index)
    cols = [c for c in expected.columns if c not in keys]
    mismatch = 0
    for idx in common:
        er, ar = exp.loc[[idx]].iloc[0], act.loc[[idx]].iloc[0]
        if any(er.get(c) != ar.get(c) for c in cols):
            mismatch += 1
    return {"equal": len(missing) == 0 and len(unexpected) == 0 and mismatch == 0
                     and len(extra_cols) == 0 and len(missing_cols) == 0,
            "missing": int(len(missing)), "unexpected": int(len(unexpected)), "value_mismatch": int(mismatch),
            "unexpected_columns": extra_cols, "missing_columns": missing_cols}


def check(run_result, expected, output_map, keys, output_types=None) -> dict:
    """Multi-signal PASS/FAIL: engine status + no dropped/errored components + per-output diffs.

    Args:
        output_types: Optional map of output-component id -> component type. When a
            declared output's producing component is a registered but NON-delimited
            FileOutput writer (Positional/Excel/XML), its file is not harvested, so
            the reason is the clearer "not supported for verification (delimited
            only)" rather than the generic no-actual-output diff (#2/#9).
    """
    reasons = []
    # #6: a run with NO expected outputs verifies nothing -- an empty ``expected``
    # would otherwise iterate zero diffs and fall through to passed=True (a hollow
    # oracle). A run that produced/expected nothing must NOT report PASS.
    if not expected:
        reasons.append("no outputs to verify")
    if run_result.status != "success":
        reasons.append(f"engine status={run_result.status!r}" + (f": {run_result.error}" if run_result.error else ""))
    if run_result.dropped_components:
        reasons.append(f"dropped (unknown-type) components: {run_result.dropped_components}")
    errored = [cid for cid, s in run_result.component_stats.items() if isinstance(s, dict) and s.get("status") == "error"]
    if errored:
        reasons.append(f"components errored: {errored}")

    out_diffs = {}
    for name, exp_df in expected.items():
        comp_id = output_map.get(name)
        actual = run_result.outputs.get(comp_id) if comp_id else None
        ctype = output_types.get(comp_id) if output_types else None
        if actual is None and ctype in _NON_DELIMITED_OUTPUT_TYPES:
            d = {"equal": False,
                 "reason": f"output type {ctype} not supported for verification (delimited only)"}
        else:
            d = diff_frames(actual, exp_df, keys.get(name))
        out_diffs[name] = d
        if not d.get("equal", False):
            reasons.append(f"output {name!r} differs: {d}")

    return {
        "passed": not reasons,
        "engine": {"status": run_result.status, "dropped": run_result.dropped_components,
                   "global_map": run_result.global_map},
        "outputs": out_diffs,
        "reasons": reasons,
    }


def main(argv=None) -> int:
    """CLI: run a job, diff against a golden dir, emit test_report.json."""
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description="Run a job and validate its output vs golden data.")
    parser.add_argument("--job", required=True, help="path to the job.json")
    parser.add_argument("--golden-dir", required=True, help="dir with <name>_expected.csv + manifest.json")
    parser.add_argument("--out", help="write test_report JSON here (default: stdout)")
    args = parser.parse_args(argv)

    def _emit(payload: dict) -> None:
        out_text = json.dumps(payload, indent=2, default=str)
        if args.out:
            Path(args.out).write_text(out_text, encoding="utf-8")
        else:
            sys.stdout.write(out_text + "\n")

    # Everything here -- loading job/manifest/golden CSVs AND running+diffing the
    # job -- is wrapped so ANY hard failure (missing/malformed manifest, absent
    # golden dir, a mis-parsed frame whose declared key is absent -> KeyError in
    # diff_frames, etc.) yields a clean exit 2 with an emitted report, never a bare
    # traceback that writes no report. Contract parity with validate_config.
    try:
        with open(args.job, encoding="utf-8") as fh:
            job = json.load(fh)
        gdir = Path(args.golden_dir)
        manifest = json.loads((gdir / "manifest.json").read_text(encoding="utf-8"))
        # An empty/absent outputs map verifies nothing, yet check() would iterate
        # zero outputs and return passed=True -- a false green. Fail hard instead.
        outputs_spec = manifest.get("outputs")
        if not outputs_spec:
            _emit({"passed": False, "error": "manifest declares no outputs to verify"})
            return 2
        expected, output_map, keys = {}, {}, {}
        fo_ids = _output_component_ids(job)
        for name, spec in outputs_spec.items():
            if not spec.get("graded", True):
                continue  # ungraded: run the job but do not read an expected CSV or diff
            if name not in fo_ids:
                _emit({"passed": False,
                       "error": f"graded output '{name}' has no FileOutput component with id == '{name}' in job.json"})
                return 2
            # Default to ';' -- the repo golden convention and what _read_output uses.
            sep = spec.get("sep", ";")
            expected[name] = pd.read_csv(gdir / f"{name}_expected.csv", sep=sep, dtype=str, keep_default_na=False)
            output_map[name] = name  # the Sec 4.4 contract: FileOutput id == output name
            keys[name] = spec.get("keys")
        # Jail job outputs to the JOB FILE's own directory (its sandbox), not the
        # read-only golden dir -- run_job_capture refuses any output escaping it.
        run_result = run_job_capture(job, Path(args.job).parent)
        # id -> type, so check() can name a clearer reason when a declared output is a
        # registered but non-delimited FileOutput writer (unharvested -> actual=None).
        output_types = {c.get("id"): c.get("type") for c in job.get("components", [])}
        report = check(run_result, expected, output_map, keys, output_types=output_types)
        report["graded"] = len(expected)          # graded outputs actually diffed
        report["total"] = len(outputs_spec)        # all declared outputs (graded + ungraded)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        _emit({"passed": False, "error": str(exc)})
        return 2

    _emit(report)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
