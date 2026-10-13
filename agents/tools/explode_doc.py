"""Exploder: inventory the FULL docx block stream into stable handles + jailed extraction."""
from __future__ import annotations

import csv
import logging
import os
import zipfile
from pathlib import Path, PurePosixPath

from docx import Document
from docx.table import Table

from agents.tools.docx_purity import scan_purity
from agents.tools.extract_doc import _iter_block_items, _table_records
from agents.tools.materialize_golden import _jailed, _safe_name

logger = logging.getLogger(__name__)

# Decompression bound (fail-closed zip-bomb guard): checked against ZipInfo.file_size
# BEFORE extracting -- cap total extracted bytes, per-entry size, and member count.
MAX_EXTRACT_BYTES = 50 * 1024 * 1024
MAX_ENTRY_BYTES = 25 * 1024 * 1024
MAX_MEMBERS = 500

# The docx zip subtrees the exploder pulls embedded binaries from.
_MEDIA_PREFIX = "word/media/"
_EMBED_PREFIX = "word/embeddings/"


def _dedup_headers(header: list[str]) -> list[str]:
    """Disambiguate a header row so no column is silently dropped (blank -> col_<i>; dup -> _<n>)."""
    seen, out = {}, []
    for i, h in enumerate(header):
        name = h.strip() or f"col_{i}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 1
        out.append(name)
    return out


def _inventory_blocks(doc) -> list[dict]:
    """Walk the full block stream into ordered handles: one table:N per table, grouped para:N prose ranges."""
    blocks: list[dict] = []
    table_idx = 0
    para_idx = 0
    pending = None  # {"start": int, "end": int, "texts": list[str]} for the current prose run

    def _flush_pending() -> None:
        """Emit the accumulated consecutive-paragraph run as one para:N block-range handle."""
        nonlocal pending, para_idx
        if pending is None:
            return
        blocks.append(
            {
                "id": f"para:{para_idx}",
                "type": "prose",
                "block_start": pending["start"],
                "block_end": pending["end"],
                "text": "\n".join(pending["texts"]),
            }
        )
        para_idx += 1
        pending = None

    for i, block in enumerate(_iter_block_items(doc)):
        if isinstance(block, Table):
            _flush_pending()
            # Reuse _table_records for header + data-row count; store the EXACT cell
            # matrix ourselves (dict(zip(header, r)) would collapse duplicate columns).
            header, records = _table_records(block)
            matrix = [[cell.text.strip() for cell in row.cells] for row in block.rows]
            blocks.append(
                {
                    "id": f"table:{table_idx}",
                    "type": "table",
                    "block_start": i,
                    "block_end": i,
                    "columns": _dedup_headers(header),
                    "n_rows": len(records),
                    "cells": matrix,
                }
            )
            table_idx += 1
        else:  # Paragraph
            if pending is None:
                pending = {"start": i, "end": i, "texts": []}
            pending["end"] = i
            text = block.text.strip()
            if text:
                pending["texts"].append(text)
    _flush_pending()

    logger.debug(
        "[explode_doc] inventoried %d handles: %d tables, %d prose groups",
        len(blocks), table_idx, para_idx,
    )
    return blocks


# ------------------------------------------------------------------
# Jailed extraction: images + embedded objects + sibling data files.
# ------------------------------------------------------------------
def _safe_basename(member: str) -> str:
    """Reduce an untrusted zip-member name to a validated bare basename (raises on empty/./..)."""
    base = PurePosixPath(member.replace("\\", "/")).name  # no separators by construction
    return _safe_name(base)  # RAISES on empty/./.. via materialize_golden's fail-closed validator


def _unique_basename(basename: str, used: set) -> str:
    """Return basename (or a deterministically index-suffixed variant) not already in used; records it."""
    candidate = basename
    stem, suffix = PurePosixPath(basename).stem, PurePosixPath(basename).suffix
    n = 0
    while candidate in used:
        n += 1
        candidate = f"{stem}_{n}{suffix}"
    used.add(candidate)
    return candidate


def _extract_media(zippath, out_dir) -> list[dict]:
    """Extract word/media images + word/embeddings objects into out_dir under a fail-closed jail + zip-bomb bound."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    handles: list[dict] = []
    used: set = set()
    total = 0
    image_idx = 0
    with zipfile.ZipFile(zippath) as zf:
        members = sorted(
            (info for info in zf.infolist()
             if not info.is_dir()
             and (info.filename.startswith(_MEDIA_PREFIX) or info.filename.startswith(_EMBED_PREFIX))),
            key=lambda info: info.filename,
        )
        if len(members) > MAX_MEMBERS:
            raise ValueError(
                f"[explode_doc] too many embedded members ({len(members)} > {MAX_MEMBERS}); refusing to extract")
        for info in members:
            if info.file_size > MAX_ENTRY_BYTES:
                raise ValueError(
                    f"[explode_doc] embedded member {info.filename!r} exceeds per-entry cap "
                    f"({info.file_size} > {MAX_ENTRY_BYTES})")
            if total + info.file_size > MAX_EXTRACT_BYTES:
                raise ValueError(
                    f"[explode_doc] extraction exceeds total cap ({MAX_EXTRACT_BYTES}); refusing to extract")
            total += info.file_size
            basename = _unique_basename(_safe_basename(info.filename), used)
            target = _jailed(out, basename)  # defense in depth on top of _safe_basename
            with zf.open(info) as src:
                target.write_bytes(src.read())
            if info.filename.startswith(_MEDIA_PREFIX):
                handles.append({"id": f"image:{image_idx}", "type": "image", "path": str(target)})
                image_idx += 1
            else:
                handles.append({"id": f"embed:{basename}", "type": "embed", "path": str(target)})
    logger.debug("[explode_doc] extracted %d media/embed member(s) (%d bytes) to %s", len(handles), total, out)
    return handles


def _resolve_sibling(docx_dir, name) -> Path:
    """Read-jail a sibling reference to inside docx_dir; raise ValueError on absolute/.. escape."""
    if os.path.isabs(name) or ".." in PurePosixPath(name.replace("\\", "/")).parts:
        raise ValueError(f"[explode_doc] sibling reference escapes docx dir: {name!r}")
    base = Path(os.path.realpath(docx_dir))
    target = Path(os.path.realpath(base / name))
    if not target.is_relative_to(base):
        raise ValueError(f"[explode_doc] sibling reference escapes docx dir: {name!r}")
    return target


def _inventory_siblings(docx_dir, out_dir) -> list[dict]:
    """Copy sibling *.csv files from the docx's own directory into out_dir under read+write jails."""
    src_dir = Path(docx_dir)
    handles: list[dict] = []
    if not src_dir.is_dir():
        return handles
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    used: set = set()
    for name in sorted(os.listdir(src_dir)):
        if not name.lower().endswith(".csv"):
            continue
        src = _resolve_sibling(docx_dir, name)  # read-jail; raises on escape
        if not src.is_file():
            continue
        basename = _unique_basename(_safe_basename(name), used)
        target = _jailed(out, basename)  # defense in depth on top of _safe_basename
        target.write_bytes(src.read_bytes())
        handles.append({"id": f"sibling:{basename}", "type": "sibling", "path": str(target)})
    logger.debug("[explode_doc] inventoried %d sibling CSV(s) from %s", len(handles), src_dir)
    return handles


# ------------------------------------------------------------------
# CSV dialect sniff + top-level explode() + CLI.
# ------------------------------------------------------------------
def _sniff_csv_dialect(path) -> dict | None:
    """Sniff a CSV's delimiter/quotechar from a sample; return None when it cannot be sniffed."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace", newline="") as fh:
            sample = fh.read(8192)
    except OSError:
        return None
    if not sample.strip():
        return None
    try:
        dialect = csv.Sniffer().sniff(sample)
    except csv.Error:
        return None  # unsniffable -> null (NOT rung-1 eligible downstream; do not guess)
    return {"delimiter": dialect.delimiter, "quotechar": dialect.quotechar}


def explode(docx_path, out_dir) -> dict:
    """Explode a .docx into one inventory of stable handles (+ jailed media/siblings, CSV dialects, purity)."""
    doc = Document(str(docx_path))
    blocks = _inventory_blocks(doc)
    # Distinct jails: media/embeds under out_dir/, siblings under out_dir/sibling/,
    # so a media basename can never overwrite an identically named sibling file.
    media = _extract_media(docx_path, out_dir)
    siblings = _inventory_siblings(os.path.dirname(os.path.abspath(str(docx_path))), Path(out_dir) / "sibling")
    for handle in siblings:  # every sibling is a .csv by construction
        handle["csv_dialect"] = _sniff_csv_dialect(handle["path"])
    for handle in media:  # dialect only for embedded CSVs (images/xlsx get none)
        if handle["type"] == "embed" and handle["path"].lower().endswith(".csv"):
            handle["csv_dialect"] = _sniff_csv_dialect(handle["path"])
    handles = blocks + media + siblings
    prose_text = "\n".join(b["text"] for b in blocks if b["type"] == "prose" and b["text"])
    purity = scan_purity(str(docx_path))
    logger.info(
        "[explode_doc] %s: %d handle(s) (%d block, %d media/embed, %d sibling)",
        os.path.basename(str(docx_path)), len(handles), len(blocks), len(media), len(siblings),
    )
    return {"handles": handles, "prose_text": prose_text, "purity": purity}


def main(argv=None) -> int:
    """CLI: explode a .docx into stable handles + jailed extraction; write exploder_inventory.json."""
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(
        description="Explode a .docx into stable handles + jailed media/sibling extraction."
    )
    parser.add_argument("docx", help="path to the .docx to explode")
    parser.add_argument("--out-dir", required=True,
                        help="jail dir for extracted media/siblings (e.g. agents/work/<job>/_explode)")
    parser.add_argument("--inventory", required=True,
                        help="write exploder_inventory.json here (e.g. agents/work/<job>/exploder_inventory.json)")
    args = parser.parse_args(argv)

    Path(args.out_dir).mkdir(parents=True, exist_ok=True)
    inventory = explode(args.docx, args.out_dir)
    inv_path = Path(args.inventory)
    inv_path.parent.mkdir(parents=True, exist_ok=True)
    inv_path.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    sys.stdout.write(f"[explode_doc] wrote {len(inventory['handles'])} handle(s) to {args.inventory}\n")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
