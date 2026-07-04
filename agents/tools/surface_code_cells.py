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
- ``PyMap`` eval()s LLM-authored Python per row for its join keys, variables, and
  output columns/filters under a hardened whitelist -- but the namespace still
  exposes ``pd`` / ``np`` / ``re``, so every expression/filter is surfaced
  (sandboxed=True relative to python_dataframe). No Talend alias.
- ``SwiftTransformer`` / ``tSwiftDataTransformer`` eval() ``python_expression``
  config fields with ``__import__`` present in ``__builtins__`` -> full escape ->
  UNSANDBOXED. The key can nest, so it is surfaced via a recursive key walk.
- ``RowGenerator`` / ``tRowGenerator`` eval()s each ``values[].array`` string
  (an LLM-authored per-row expression) in a ``{"__builtins__": {}, "random": ...}``
  namespace -- restricted but object-graph-escapable, so every ``array`` string is
  surfaced (sandboxed=True relative to python_dataframe, same treatment as PyMap).
- ``RunIf`` triggers live in the job's ``triggers[]`` (NOT ``components[]``); each
  carries a ``condition`` expression that ``TriggerManager`` eval()s in a restricted
  (object-graph-escapable) namespace, so every RunIf ``condition`` is surfaced too.
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
# SwiftTransformer per-field Python expression key (recursive; may nest).
_SWIFT_PY_EXPR_KEY = "python_expression"

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
# PyMap evaluates LLM-authored Python per-row via eval() under a hardened
# whitelist -- BUT the namespace still exposes pd / np / re, so its join,
# variable, and output expressions are surfaced for review (sandboxed=True
# relative to python_dataframe). No Talend alias -- registered as "PyMap" only.
_PY_MAP_TYPES = frozenset({"PyMap"})
# SwiftTransformer eval()s python_expression fields with __import__ present in
# __builtins__ -> full escape -> UNSANDBOXED (pending an engine harden).
_SWIFT_TYPES = frozenset({"SwiftTransformer", "tSwiftDataTransformer"})
# RowGenerator eval()s each values[].array string in a restricted-but-escapable
# {"__builtins__": {}, "random": ...} namespace -> surfaced (sandboxed=True,
# same treatment as PyMap; the namespace is object-graph-escapable, not a jail).
_ROW_GENERATOR_TYPES = frozenset({"RowGenerator", "tRowGenerator"})
# RunIf trigger type match is case-insensitive (see _runif_cells).
_RUN_IF_TYPE = "runif"


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


def _walk_named_key(obj, path: str, target_key: str, out: list) -> None:
    """Collect (json_path, string) for every string under a key == ``target_key``.

    Recurses the full config tree (dicts and lists) so a key can sit at any
    depth -- e.g. SwiftTransformer's ``python_expression`` nested under
    ``transform_config.output_fields[i]``. Only string values are collected;
    the walk still descends into non-string values in case a matching key
    itself holds further nested structures.
    """
    if isinstance(obj, dict):
        for key, value in obj.items():
            child = f"{path}.{key}" if path else str(key)
            if key == target_key and isinstance(value, str):
                out.append((child, value))
            _walk_named_key(value, child, target_key, out)
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            _walk_named_key(value, f"{path}[{index}]", target_key, out)


def _pymap_cells(config: dict, out: list) -> None:
    """Collect (json_path, expression) for every code-bearing PyMap config field.

    PyMap expressions are plain Python evaluated per-row (``row1['x']``, with
    ``pd`` / ``np`` / ``re`` in scope) and carry no ``{{java}}`` marker, so the
    generic marker walk never surfaces them. The json paths produced here match
    the marker-walk path format exactly, so dedup stays consistent. Blank / non
    string values are tolerated -- ``add`` drops them.
    """
    if not isinstance(config, dict):
        return

    inputs = config.get("inputs")
    if isinstance(inputs, dict):
        main = inputs.get("main")
        if isinstance(main, dict):
            out.append(("inputs.main.filter", main.get("filter")))
        lookups = inputs.get("lookups")
        if isinstance(lookups, list):
            for i, lookup in enumerate(lookups):
                if not isinstance(lookup, dict):
                    continue
                out.append((f"inputs.lookups[{i}].filter", lookup.get("filter")))
                join_keys = lookup.get("join_keys")
                if isinstance(join_keys, list):
                    for j, jk in enumerate(join_keys):
                        if isinstance(jk, dict):
                            out.append((
                                f"inputs.lookups[{i}].join_keys[{j}].expression",
                                jk.get("expression"),
                            ))

    variables = config.get("variables")
    if isinstance(variables, list):
        for i, var in enumerate(variables):
            if isinstance(var, dict):
                out.append((f"variables[{i}].expression", var.get("expression")))

    outputs = config.get("outputs")
    if isinstance(outputs, list):
        for i, output in enumerate(outputs):
            if not isinstance(output, dict):
                continue
            out.append((f"outputs[{i}].filter", output.get("filter")))
            columns = output.get("columns")
            if isinstance(columns, list):
                for j, col in enumerate(columns):
                    if isinstance(col, dict):
                        out.append((
                            f"outputs[{i}].columns[{j}].expression",
                            col.get("expression"),
                        ))


def _runif_cells(job_config: dict, out: list, seen: set) -> None:
    """Surface every RunIf trigger's ``condition`` expression for human review.

    RunIf conditions live in the job-level ``triggers[]`` (NOT ``components[]``)
    and are ``eval()``'d by ``TriggerManager`` in a restricted-but-object-graph-
    escapable namespace, so each non-blank ``condition`` is surfaced
    (unsandboxed=False, same posture as PyMap / RowGenerator).

    The displayed ``component`` is the trigger's source component (its ``from``),
    falling back to the trigger id then ``trigger:<index>``. Dedup keys on the
    trigger's own identity -- NOT on ``(component, field)`` -- so two RunIf
    branches from the SAME source component both surface (the whole point of the
    gate is that no code-bearing cell is dropped).
    """
    triggers = job_config.get("triggers")
    if not isinstance(triggers, list):
        return
    for index, trigger in enumerate(triggers):
        if not isinstance(trigger, dict):
            continue
        ttype = trigger.get("type")
        if not isinstance(ttype, str) or ttype.strip().lower() != _RUN_IF_TYPE:
            continue
        condition = trigger.get("condition")
        if not _is_code_str(condition):
            continue
        tid = trigger.get("id")
        cid = (trigger.get("from") or trigger.get("from_component")
               or tid or f"trigger:{index}")
        key = ("__trigger__", tid if tid is not None else index)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "component": cid,
            "type": ttype,
            "field": "condition",
            "code": condition,
            "unsandboxed": False,
        })


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
    if not isinstance(job_config, dict):
        return []
    components = job_config.get("components")

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

    for comp in components if isinstance(components, list) else []:
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
        elif ctype in _PY_MAP_TYPES:
            # LLM-authored Python expressions; hardened whitelist -> sandboxed.
            pymap_cells: list = []
            _pymap_cells(config, pymap_cells)
            for field_path, code in pymap_cells:
                add(cid, ctype, field_path, code, False)
        elif ctype in _SWIFT_TYPES:
            # python_expression fields eval'd with __import__ -> unsandboxed.
            swift_cells: list = []
            _walk_named_key(config, "", _SWIFT_PY_EXPR_KEY, swift_cells)
            for field_path, code in swift_cells:
                add(cid, ctype, field_path, code, True)
        elif ctype in _ROW_GENERATOR_TYPES:
            # Each values[].array is an LLM-authored per-row eval() expression
            # in a restricted-but-escapable namespace -> surfaced (sandboxed).
            values = config.get("values")
            if isinstance(values, list):
                for i, value in enumerate(values):
                    if isinstance(value, dict):
                        add(cid, ctype, f"values[{i}].array", value.get("array"), False)

        # 2. generic: any free-form {{java}} marker anywhere in the config tree
        markers: list = []
        _walk_markers(config, "", markers)
        for field_path, code in markers:
            add(cid, ctype, field_path, code, False)

    # 3. RunIf trigger conditions live in job-level triggers[], not components[].
    _runif_cells(job_config, cells, seen)

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
