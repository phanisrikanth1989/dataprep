"""Deterministic materialization of an extract_doc.json into the exact input CSVs
and golden answer key the harness needs.

The LLM never touches this: it copies the extracted data verbatim into files.
Input CSVs go to the work-dir ROOT (the harness anchors a relative
``filepath: "x.csv"`` there); the ``<out>_expected.csv`` answer key + manifest
go under ``golden/``. All CSVs are RFC-4180 double-quoted so a value containing
the ';' separator round-trips (the configurator pairs this with ``csv_option:
true`` on the delimited I/O).
"""
from __future__ import annotations

import csv
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_SEP = ";"


def _safe_name(name: str) -> str:
    """Fail-closed on an untrusted source/output NAME before it becomes a filename.

    The name comes verbatim from a requirements-doc H2 subheading, so a crafted doc
    could set it to an absolute path, ``..``, or a path with separators and write the
    materialized CSV outside the work dir. This mirrors run_and_validate's frozen
    path-jail: require a single safe filename component, else raise (the whole
    materialize refuses, before any harness run or human gate)."""
    if (not name) or name in (".", "..") or os.path.isabs(name) or os.path.basename(name) != name:
        raise ValueError(
            f"unsafe source/output name from the requirements doc "
            f"(must be a single filename component): {name!r}"
        )
    return name


def _jailed(root, fname: str) -> Path:
    """Resolve ``fname`` under ``root`` and confirm it stays inside root (defense in
    depth on top of _safe_name), so a materialized file can never escape work_dir."""
    root_real = Path(os.path.realpath(root))
    target = root_real / fname
    if not target.resolve().is_relative_to(root_real):
        raise ValueError(f"materialize path escapes work_dir: {fname!r}")
    return target


def _write_csv(path, header, rows):
    """Write an RFC-4180 (QUOTE_MINIMAL) ';'-delimited CSV: header then row dicts."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, delimiter=_SEP, quotechar='"',
                            quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        writer.writerow(header)
        for row in rows:
            writer.writerow([row.get(col, "") for col in header])


def _header_for(name, rows, schema):
    """Header = first row's keys (the literal table header); fall back to the
    declared schema column names when there are no data rows."""
    if rows:
        return list(rows[0].keys())
    return [c["name"] for c in schema.get(name, []) if isinstance(c, dict) and c.get("name")]


def materialize_inputs(extract: dict, work_dir) -> list[str]:
    """Write one ``<source>.csv`` per sample_input source at the work-dir ROOT.

    Returns the written filenames. The file name is the input-side naming
    contract: the configurator authors each FileInputDelimited ``filepath`` as
    exactly ``<source-name>.csv`` (a bare relative path anchored to the root)."""
    root = Path(work_dir)
    root.mkdir(parents=True, exist_ok=True)
    sample = extract.get("sample_input", {})
    schema = extract.get("sources_schema", {})
    written = []
    for source, rows in sample.items():
        _safe_name(source)
        header = _header_for(source, rows, schema)
        fname = f"{source}.csv"
        _write_csv(_jailed(root, fname), header, rows)
        written.append(fname)
    logger.info("[materialize_golden] wrote %d input CSV(s) to %s", len(written), root)
    return written


def materialize_expected(extract: dict, work_dir) -> dict:
    """Write the golden answer key under ``golden/`` and return the manifest dict.

    Per expected output: ``graded`` is True iff it has >=1 data row (a declared-
    empty header-only output is ``graded: false``). A graded output gets a
    ``<name>_expected.csv``; an ungraded one gets no CSV (nothing to diff). The
    manifest carries NO ``component`` key -- run_and_validate derives the id
    deterministically from the FileOutput whose id == the output name."""
    gdir = Path(work_dir) / "golden"
    gdir.mkdir(parents=True, exist_ok=True)
    expected = extract.get("expected_output", {})
    output_keys = extract.get("output_keys", {})
    outputs = {}
    for name, rows in expected.items():
        _safe_name(name)
        graded = len(rows) > 0
        outputs[name] = {"keys": output_keys.get(name, []), "sep": _SEP, "graded": graded}
        if graded:
            _write_csv(_jailed(gdir, f"{name}_expected.csv"), list(rows[0].keys()), rows)
    manifest = {"outputs": outputs}
    (gdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info("[materialize_golden] wrote manifest with %d output(s) to %s", len(outputs), gdir)
    return manifest


def materialize_golden(extract: dict, work_dir) -> dict:
    """Materialize input CSVs + the golden answer key and echo the tier.

    Deterministic: it writes the exact extracted data; no model is involved."""
    inputs = materialize_inputs(extract, work_dir)
    manifest = materialize_expected(extract, work_dir)
    return {"tier": extract.get("tier", "build"), "inputs": inputs, "outputs": manifest["outputs"]}


def main(argv=None) -> int:
    """CLI: extract_doc.json + work dir -> input CSVs (root) + golden/ answer key."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Materialize input CSVs + golden answer key from an extract_doc.json.")
    parser.add_argument("--extract-doc", required=True, help="path to extract_doc.json")
    parser.add_argument("--work-dir", required=True, help="work dir (job.json parent); inputs land at its root")
    parser.add_argument("--out", help="write the result JSON here (default: stdout)")
    args = parser.parse_args(argv)

    def _emit(payload):
        text = json.dumps(payload, indent=2)
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text + "\n")

    try:
        extract = json.loads(Path(args.extract_doc).read_text(encoding="utf-8"))
        result = materialize_golden(extract, args.work_dir)
    except (OSError, ValueError) as exc:
        _emit({"error": str(exc)})
        return 2
    _emit(result)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
