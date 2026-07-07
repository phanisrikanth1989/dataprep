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
from pathlib import Path

logger = logging.getLogger(__name__)

_SEP = ";"


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
        header = _header_for(source, rows, schema)
        fname = f"{source}.csv"
        _write_csv(root / fname, header, rows)
        written.append(fname)
    logger.info("[materialize_golden] wrote %d input CSV(s) to %s", len(written), root)
    return written
