"""Answer-key harness: run a job on v1 and on v2 and compare what they wrote.

v1's output for a job is the answer key. It is produced by running v1 at test
time and is never stored. A test hands over a job config and its input files;
each engine runs in its own fresh folder with the inputs copied in and the
working directory set there, so job configs use relative paths and the same
text can be run by hand. What is compared: whether the job finished, which
files it wrote, and their bytes.

Usage::

    from tests.v2.answer_key import assert_matches_v1

    def test_filter_keeps_matching_rows(tmp_path):
        assert_matches_v1(JOB, {"in.csv": b"id;name\\n1;a\\n"}, tmp_path)

A job whose v1 form needs Java carries two job configs, v1's and its v2
rewrite (``v2_job=``), and is skipped on a machine without the Java bridge.
"""
from __future__ import annotations

import copy
import functools
import os
import shutil
import subprocess
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Union

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
BRIDGE_JAR = REPO_ROOT / "src" / "v1" / "java_bridge" / "java" / "target" / "java-bridge-with-dependencies.jar"

Job = Dict[str, Any]
Inputs = Mapping[str, Union[Path, bytes]]
Runner = Callable[[Job], None]


@dataclass
class JobRun:
    """What one engine did with one job.

    Attributes:
        succeeded: Whether the job finished.
        error: Why it did not, empty when it did.
        files: Every file the job wrote or changed, as a path relative to its
            folder (forward slashes) mapped to the file's bytes.
        folder: Where it ran, kept for inspection after a failure.
    """

    succeeded: bool
    error: str
    files: Dict[str, bytes]
    folder: Path


# ------------------------------------------------------------------
# Runners
# ------------------------------------------------------------------

def run_v1(job: Job) -> None:
    """Run a job on v1, in process. Raises when the job does not finish."""
    from src.v1.engine.engine import ETLEngine

    with warnings.catch_warnings():
        # v1's own deprecation warnings are not this suite's to report.
        warnings.simplefilter("ignore")
        result = ETLEngine(job).execute()
    status = result.get("status")
    if status != "success":
        raise RuntimeError(f"v1 ended with status {status!r}: {result.get('error', '')}")


def run_v2(job: Job) -> None:
    """Run a job on v2, in process. Raises when the job does not finish."""
    from src.v2 import run_job as v2_run_job

    v2_run_job(job).raise_for_status()


# ------------------------------------------------------------------
# Running and comparing
# ------------------------------------------------------------------

def run_job(job: Job, inputs: Inputs, folder: Path, runner: Runner) -> JobRun:
    """Run a job in a fresh folder holding its inputs.

    Args:
        job: The job config. The runner gets its own copy.
        inputs: File name inside the folder, mapped to a path to copy from or
            to the bytes to write.
        folder: The folder to create and run in.
        runner: Runs the job; raises when it does not finish.
    """
    folder = Path(folder)
    folder.mkdir(parents=True)
    for name, source in inputs.items():
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(source, bytes):
            target.write_bytes(source)
        else:
            shutil.copyfile(source, target)
    before = _read_tree(folder)

    succeeded, error = True, ""
    previous = os.getcwd()
    os.chdir(folder)
    try:
        runner(copy.deepcopy(job))
    except Exception as exc:  # noqa: BLE001 -- any failure means "did not finish"
        succeeded, error = False, f"{type(exc).__name__}: {exc}"
    finally:
        os.chdir(previous)

    after = _read_tree(folder)
    written = {name: data for name, data in after.items() if before.get(name) != data}
    return JobRun(succeeded=succeeded, error=error, files=written, folder=folder)


def differences(key: JobRun, actual: JobRun) -> List[str]:
    """List how v2's run differs from v1's. Empty when they match.

    When neither engine finishes, files are not compared: v1 can leave a
    half-written file behind.
    """
    if key.succeeded and not actual.succeeded:
        return [f"v1 finished, v2 did not: {actual.error}"]
    if not key.succeeded and actual.succeeded:
        return [f"v1 did not finish ({key.error}), v2 did"]
    if not key.succeeded:
        return []

    found: List[str] = []
    for name in sorted(set(key.files) | set(actual.files)):
        if name not in actual.files:
            found.append(f"{name}: v1 wrote it, v2 did not")
        elif name not in key.files:
            found.append(f"{name}: v2 wrote it, v1 did not")
        elif key.files[name] != actual.files[name]:
            found.append(_first_difference(name, key.files[name], actual.files[name]))
    return found


def assert_matches_v1(
    job: Job,
    inputs: Inputs,
    work_dir: Path,
    *,
    v2_job: Optional[Job] = None,
    run_v2: Runner = run_v2,
) -> JobRun:
    """Assert that v2 does with a job what v1 does.

    Args:
        job: The job config v1 runs, and v2 too unless ``v2_job`` is given.
        inputs: The job's input files (see ``run_job``).
        work_dir: A fresh folder, normally pytest's ``tmp_path``.
        v2_job: The v2 rewrite of the job, when v1's form cannot run on v2
            (Java expressions rewritten in Python).
        run_v2: The v2 runner. Tests of the harness pass stand-ins.

    Returns:
        v2's run, for any further assertions.
    """
    if needs_bridge(job) and not bridge_available():
        pytest.skip("this job needs v1's Java bridge, which is not available on this machine")

    work_dir = Path(work_dir)
    key = run_job(job, inputs, work_dir / "v1", run_v1)
    actual = run_job(v2_job if v2_job is not None else job, inputs, work_dir / "v2", run_v2)
    found = differences(key, actual)
    if found:
        lines = ["v2 does not match v1:"] + [f"  {item}" for item in found]
        lines += [f"v1 ran in {key.folder}", f"v2 ran in {actual.folder}"]
        raise AssertionError("\n".join(lines))
    return actual


# ------------------------------------------------------------------
# Java bridge
# ------------------------------------------------------------------

def needs_bridge(job: Job) -> bool:
    """Whether running this job on v1 needs the Java bridge."""
    if (job.get("java_config") or {}).get("enabled"):
        return True
    return _holds_java(job.get("components", []))


@functools.lru_cache(maxsize=None)
def bridge_available() -> bool:
    """Whether a working JVM and the built bridge JAR are both present.

    ``java`` is run rather than looked up: macOS ships a stub at
    ``/usr/bin/java`` that exists and fails.
    """
    if not BRIDGE_JAR.exists():
        return False
    try:
        done = subprocess.run(["java", "-version"], capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0


# ------------------------------------------------------------------
# Internals
# ------------------------------------------------------------------

def _holds_java(value: Any) -> bool:
    if isinstance(value, str):
        return value.startswith("{{java}}")
    if isinstance(value, dict):
        return any(_holds_java(item) for item in value.values())
    if isinstance(value, list):
        return any(_holds_java(item) for item in value)
    return False


def _read_tree(folder: Path) -> Dict[str, bytes]:
    return {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in sorted(folder.rglob("*"))
        if path.is_file()
    }


def _count(lines: List[bytes]) -> str:
    return f"{len(lines)} line" if len(lines) == 1 else f"{len(lines)} lines"


def _first_difference(name: str, key: bytes, actual: bytes) -> str:
    key_lines = key.splitlines(keepends=True)
    actual_lines = actual.splitlines(keepends=True)
    index = 0
    while index < min(len(key_lines), len(actual_lines)) and key_lines[index] == actual_lines[index]:
        index += 1
    v1_line = repr(key_lines[index]) if index < len(key_lines) else "(no such line)"
    v2_line = repr(actual_lines[index]) if index < len(actual_lines) else "(no such line)"
    return (
        f"{name}: first difference at line {index + 1}\n"
        f"    v1: {v1_line}\n"
        f"    v2: {v2_line}\n"
        f"    v1 has {_count(key_lines)}, v2 has {_count(actual_lines)}"
    )
