"""Deterministic materialization of an extract_doc.json into the exact input CSVs
and golden answer key the harness needs.

The LLM never touches this: it copies the extracted data verbatim into files.
Input CSVs go to the work-dir ROOT (the harness anchors a relative
``filepath: "x.csv"`` there); the ``<out>_expected.csv`` answer key + manifest
go under ``golden/``. Each CSV is written with the delimiter the exploder SNIFFED
for that source (recorded in ``extract_doc`` provenance) -- so the fixture keeps
the real file's separator and the configurator's reader round-trips it -- falling
back to ``;`` only for a table/transcribed source that has no source file. All
CSVs are RFC-4180 double-quoted (the configurator pairs this with ``csv_option:
true``) so a value containing the separator round-trips instead of shifting columns.
"""
from __future__ import annotations

import csv
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Fallback delimiter ONLY when a source carries no sniffed delimiter (a rung-2 Word
# table / rung-3 transcription has no source file). A real CSV source always carries
# its own sniffed delimiter via provenance, so this default is never used for it.
_DEFAULT_SEP = ";"


def _sep_for(name, extract):
    """Delimiter to materialize ``name`` with: the exploder-sniffed delimiter recorded in
    ``extract_doc`` provenance for that source, else ``_DEFAULT_SEP``. This keeps the written
    fixture in the SAME separator the real file used, so the reader/writer config round-trips."""
    prov = (extract.get("provenance") or {}).get(name) or {}
    return prov.get("delimiter") or _DEFAULT_SEP


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


def _write_csv(path, header, rows, sep=_DEFAULT_SEP):
    """Write an RFC-4180 (QUOTE_MINIMAL) CSV with delimiter ``sep``: header then row dicts."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, delimiter=sep, quotechar='"',
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
        _write_csv(_jailed(root, fname), header, rows, _sep_for(source, extract))
        written.append(fname)
    logger.info("[materialize_golden] wrote %d input CSV(s) to %s", len(written), root)
    return written


def materialize_expected(extract: dict, work_dir) -> dict:
    """Write the golden answer key under ``golden/`` and return the manifest dict.

    Per expected output: ``graded`` is True iff it has >=1 data row (a declared-
    empty header-only output is ``graded: false``). A graded output gets a
    ``<name>_expected.csv``; an ungraded one gets no CSV (nothing to diff). The
    manifest carries NO ``component`` key -- run_and_validate derives the id
    deterministically from the FileOutput whose id == the output name.

    Rung-aware tier cap (fail-closed ALLOW-LIST): when a top-level ``provenance``
    key is present (the normalizer path), an output is graded ONLY if its rung is
    "1" or "2". A rung-3 (3a/3b) or LLM-authored output, a missing provenance
    entry, or any unknown/``needs_human`` token all fall to ``graded: false`` -- so
    no transcribed answer key ever lands on disk as gradable, independent of the
    orchestrator LLM. The template path (no ``provenance`` key, via
    ``extract_doc.to_dict``) is unchanged: ``graded`` stays ``len(rows) > 0``."""
    gdir = Path(work_dir) / "golden"
    gdir.mkdir(parents=True, exist_ok=True)
    expected = extract.get("expected_output", {})
    output_keys = extract.get("output_keys", {})
    prov = extract.get("provenance")
    outputs = {}
    for name, rows in expected.items():
        _safe_name(name)
        if prov is None:                                   # template path -> unchanged
            graded = len(rows) > 0
        else:                                              # normalizer path -> fail-closed allow-list
            rung = str(prov.get(name, {}).get("rung"))     # missing entry -> "None" -> not in the set
            graded = len(rows) > 0 and rung in ("1", "2")
        sep = _sep_for(name, extract)
        outputs[name] = {"keys": output_keys.get(name, []), "sep": sep, "graded": graded}
        if graded:
            _write_csv(_jailed(gdir, f"{name}_expected.csv"), list(rows[0].keys()), rows, sep)
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
