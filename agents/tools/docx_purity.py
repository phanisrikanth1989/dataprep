"""Deterministic pre-branch purity scan: does this docx have content outside the
template parser's lossless envelope? Trip -> the orchestrator routes to the
real-BRD normalizer (or pauses for human opt-in). Never modifies extract_doc."""
from __future__ import annotations

import zipfile
from pathlib import Path

from docx import Document

from agents.tools.extract_doc import REQUIRED_BLOCKS, _read_sections, extract_doc


def scan_purity(path: str) -> dict:
    """Scan a .docx for content the template parser would silently drop.

    Detects four trip signals: inline images (``word/media/``), embedded/OLE
    objects (``word/embeddings/``), heading-less content (the two REQUIRED_BLOCKS
    are not both present as H1s), and a conformance failure. The conformance flag
    is a trip signal only -- never a completeness check.

    Args:
        path: Filesystem path to the ``.docx`` to scan.

    Returns:
        A dict with ``has_images``, ``has_embeds``, ``has_headingless_content``,
        ``conformance_fail`` (all bool), and ``tripped`` (the OR of the four).
    """
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
    has_images = any(n.startswith("word/media/") for n in names)
    has_embeds = any(n.startswith("word/embeddings/") for n in names)
    sections = _read_sections(Document(path))
    has_headingless = not all(b in sections for b in REQUIRED_BLOCKS)
    result = extract_doc(path, raise_on_error=False)
    conformance_fail = not result.conformance.ok
    tripped = has_images or has_embeds or has_headingless or conformance_fail
    return {
        "has_images": has_images,
        "has_embeds": has_embeds,
        "has_headingless_content": has_headingless,
        "conformance_fail": conformance_fail,
        "tripped": tripped,
    }


def main(argv=None) -> int:
    """CLI: scan a .docx and print/write the purity dict as JSON; exit 0."""
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(
        description="Scan a .docx for content outside the template parser's lossless envelope."
    )
    parser.add_argument("path", help="path to the .docx to scan")
    parser.add_argument("--out", help="write JSON here (default: stdout)")
    args = parser.parse_args(argv)

    result = scan_purity(args.path)
    text = json.dumps(result, indent=2)
    if args.out:
        # Create the parent dir if missing (matches extract_doc.main) so a
        # first-command write into a fresh agents/work/<job>/ never fails.
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
