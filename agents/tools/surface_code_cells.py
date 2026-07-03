"""Deterministically surface every code-bearing config cell of a job.json (human-gate, I-2).

The orchestrator's human gate must show a human the EXACT code a job will run
before the job is trusted -- and the harness has already EXECUTED that code
(including unsandboxed ``python_dataframe`` bodies with full Python builtins) by
the time the gate is reached. LLM prose is not a guarantee, so this module walks
the job config deterministically and returns one entry per code cell, verbatim,
so the gate can display it (and hash/sign it) without paraphrase.

Component facts are code-verified against ``src/v1/engine/components/transform/``:

- ``PythonDataFrameComponent`` / ``tPythonDataFrame`` exec ``python_code`` with a
  namespace that carries no ``__builtins__`` key, so CPython injects the REAL
  builtins -> the body runs UNSANDBOXED (filesystem / network / process access).
- ``PythonComponent`` / ``PythonRowComponent`` exec ``python_code`` under a curated
  safe-builtins whitelist -> sandboxed.
- ``JavaComponent`` / ``JavaRowComponent`` carry ``java_code``; ``JavaFlexComponent``
  carries ``code_start`` / ``code_main`` / ``code_end`` -> run via the Java bridge.
- Any component may carry the deferred-Java marker ``{{java}}`` in a free-form
  string cell (e.g. a tMap output-column ``expression``); those are surfaced too.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ---- code-verified component facts ----------------------------------------
_PYTHON_CODE_KEY = "python_code"
_JAVA_CODE_KEYS = ("java_code", "code_start", "code_main", "code_end")
_JAVA_MARKER = "{{java}}"

# python_dataframe runs with FULL builtins -> unsandboxed.
_PY_DATAFRAME_TYPES = frozenset({"PythonDataFrameComponent", "tPythonDataFrame"})
# python / python-row run under a hardened whitelist -> sandboxed.
_PY_SANDBOXED_TYPES = frozenset({
    "PythonComponent", "tPython", "tPythonComponent",
    "PythonRowComponent", "tPythonRow",
})
# java bridge components -> sandboxed (relative to unsandboxed python_dataframe).
_JAVA_TYPES = frozenset({
    "JavaComponent", "tJava",
    "JavaFlexComponent", "JavaFlex", "tJavaFlex",
    "JavaRowComponent", "tJavaRow",
})


def _is_code_str(value) -> bool:
    """True when ``value`` is a non-blank string worth surfacing."""
    return isinstance(value, str) and value.strip() != ""


def _walk_markers(obj, path: str, out: list) -> None:
    """Collect (json_path, string) for every string bearing the ``{{java}}`` marker."""
    if isinstance(obj, str):
        if _JAVA_MARKER in obj:
            out.append((path, obj))
    elif isinstance(obj, dict):
        for key, value in obj.items():
            child = f"{path}.{key}" if path else str(key)
            _walk_markers(value, child, out)
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            _walk_markers(value, f"{path}[{index}]", out)


def surface_code_cells(job_config: dict) -> list:
    """Return every code-bearing config cell of a job, verbatim, for human review.

    Args:
        job_config: a parsed ``job.json`` (the runnable job envelope).

    Returns:
        A deterministically ordered list of cells, one per code-bearing field::

            {"component": <id>, "type": <component type>,
             "field": <config key or json path>, "code": <verbatim string>,
             "unsandboxed": <bool>}

        Cells are deduped by (component, field) -- an explicit code-key match wins
        over a generic ``{{java}}`` marker match on the same field -- and ordered
        with unsandboxed cells first, then by component id, then field.
    """
    components = job_config.get("components") if isinstance(job_config, dict) else None
    if not isinstance(components, list):
        return []

    cells: list = []
    seen: set = set()

    def add(cid, ctype, field, value, unsandboxed) -> None:
        if not _is_code_str(value):
            return
        key = (cid, field)
        if key in seen:          # explicit rule is collected first -> it wins
            return
        seen.add(key)
        cells.append({
            "component": cid,
            "type": ctype,
            "field": field,
            "code": value,
            "unsandboxed": unsandboxed,
        })

    for comp in components:
        if not isinstance(comp, dict):
            continue
        cid = comp.get("id")
        ctype = comp.get("type")
        config = comp.get("config")
        if not isinstance(config, dict):
            config = {}

        # 1. explicit, code-verified code keys (collected first so they win dedup)
        if ctype in _PY_DATAFRAME_TYPES:
            add(cid, ctype, _PYTHON_CODE_KEY, config.get(_PYTHON_CODE_KEY), True)
        elif ctype in _PY_SANDBOXED_TYPES:
            add(cid, ctype, _PYTHON_CODE_KEY, config.get(_PYTHON_CODE_KEY), False)
        elif ctype in _JAVA_TYPES:
            for code_key in _JAVA_CODE_KEYS:
                add(cid, ctype, code_key, config.get(code_key), False)

        # 2. generic: any free-form {{java}} marker anywhere in the config tree
        markers: list = []
        _walk_markers(config, "", markers)
        for field_path, code in markers:
            add(cid, ctype, field_path, code, False)

    cells.sort(key=lambda c: (not c["unsandboxed"], str(c["component"]), str(c["field"])))
    logger.debug("[surface_code_cells] surfaced %d code cell(s)", len(cells))
    return cells


def main(argv=None) -> int:
    """CLI: extract code-bearing cells from a job.json for the human gate."""
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(
        description="Surface every code-bearing config cell of a job.json for human review.")
    parser.add_argument("--job", required=True, help="path to the runnable job.json")
    parser.add_argument("--out", default=None, help="optional path to write the JSON cells to")
    args = parser.parse_args(argv)

    try:
        with open(args.job, encoding="utf-8") as fh:
            job = json.load(fh)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"cannot read job {args.job!r}: {exc}\n")
        return 2
    if not isinstance(job, dict):
        sys.stderr.write(f"job in {args.job!r} is not a JSON object\n")
        return 2

    cells = surface_code_cells(job)
    payload = json.dumps(cells, indent=2)
    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(payload + "\n")
        except OSError as exc:
            sys.stderr.write(f"cannot write {args.out!r}: {exc}\n")
            return 2
    else:
        sys.stdout.write(payload + "\n")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
