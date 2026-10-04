#!/usr/bin/env python3
"""Generate and validate component documentation blocks.

Populates <!-- GENERATED: features --> and <!-- GENERATED: benchmarks -->
blocks in v2 component docs from SUPPORTED_FEATURES introspection and
committed benchmark baselines.

Validates required doc headings per D-21.

Usage:
    python scripts/gen_component_doc.py <component_doc.md>
    python scripts/gen_component_doc.py --validate-only <component_doc.md>
    python scripts/gen_component_doc.py --all

Pre-commit hook and CI gate (dual enforcement per D-19).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.v2.components.capabilities import FeatureSupport, Support, get_supported_features  # noqa: E402
from src.v2.components.registry import REGISTRY  # noqa: E402

BASELINES_DIR = PROJECT_ROOT / "tests" / "v2" / "benchmark" / "baselines"
DOCS_DIR = PROJECT_ROOT / "docs" / "v2" / "components"

# Required headings per D-21
REQUIRED_HEADINGS = [
    "Purpose",
    "When to Use",
    "Configuration",
    "Example",
    "Supported Features",
    "Unsupported Features",
    "Performance",
    "Talend Differences",
]

# Markers for generated content
FEATURES_START = "<!-- GENERATED: features -->"
FEATURES_END = "<!-- /GENERATED: features -->"
BENCHMARKS_START = "<!-- GENERATED: benchmarks -->"
BENCHMARKS_END = "<!-- /GENERATED: benchmarks -->"


def generate_features_table(component_class) -> str:
    """Generate markdown table from SUPPORTED_FEATURES dict."""
    features = get_supported_features(component_class)
    if not features:
        return "_No features declared._\n"

    lines = ["| Feature | Support | Note |", "|---------|---------|------|"]
    for name, fs in sorted(features.items()):
        note = fs.note.replace("|", "\\|") if fs.note else ""
        lines.append(f"| `{name}` | {fs.support.value} | {note} |")

    return "\n".join(lines) + "\n"


def generate_benchmarks_table(component_name: str) -> str:
    """Generate markdown table from committed baseline JSON."""
    baseline_path = BASELINES_DIR / f"{component_name}.json"
    if not baseline_path.exists():
        return "_No benchmark baseline committed yet._\n"

    baseline = json.loads(baseline_path.read_text())
    v2_ms = baseline["v2_median_ns"] / 1_000_000
    raw_ms = baseline["raw_polars_median_ns"] / 1_000_000
    ratio = baseline.get("ratio", 0)

    lines = [
        "| Metric | v2 Component | Raw Polars | Ratio |",
        "|--------|-------------|------------|-------|",
        f"| Median | {v2_ms:.2f} ms | {raw_ms:.2f} ms | {ratio:.2f}x |",
        f"| Polars version | {baseline.get('polars_version', 'N/A')} | | |",
        f"| Runs | {baseline.get('n_runs', 'N/A')} | | |",
    ]
    return "\n".join(lines) + "\n"


def validate_headings(content: str, doc_path: str) -> List[str]:
    """Check that all required headings are present. Return list of errors."""
    errors = []
    headings_found = set()
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("#"):
            # Strip markdown heading markers and whitespace
            heading_text = re.sub(r"^#+\s*", "", line)
            headings_found.add(heading_text)

    for required in REQUIRED_HEADINGS:
        if not any(required.lower() in h.lower() for h in headings_found):
            errors.append(f"{doc_path}: missing required heading '{required}'")

    return errors


def update_generated_blocks(content: str, component_class, component_name: str) -> str:
    """Replace content between GENERATED markers with fresh output."""
    # Update features block
    features_table = generate_features_table(component_class)
    content = _replace_block(content, FEATURES_START, FEATURES_END, features_table)

    # Update benchmarks block
    benchmarks_table = generate_benchmarks_table(component_name)
    content = _replace_block(content, BENCHMARKS_START, BENCHMARKS_END, benchmarks_table)

    return content


def _replace_block(content: str, start_marker: str, end_marker: str, new_content: str) -> str:
    """Replace content between start and end markers."""
    pattern = re.escape(start_marker) + r".*?" + re.escape(end_marker)
    replacement = f"{start_marker}\n{new_content}{end_marker}"
    result = re.sub(pattern, replacement, content, flags=re.DOTALL)
    return result


def _infer_component_name(doc_path: Path) -> str:
    """Infer component registry name from doc path stem."""
    return doc_path.stem  # e.g., filter_columns.md -> filter_columns


def process_doc(doc_path: Path, validate_only: bool = False) -> List[str]:
    """Process a single component doc. Returns list of errors."""
    errors = []

    if not doc_path.exists():
        return [f"{doc_path}: file not found"]

    content = doc_path.read_text()
    component_name = _infer_component_name(doc_path)

    # Validate headings (always)
    errors.extend(validate_headings(content, str(doc_path)))

    if validate_only:
        # Check if generated blocks are stale
        component_class_type = REGISTRY.get(component_name)
        if component_class_type is not None:
            updated = update_generated_blocks(content, component_class_type, component_name)
            if updated != content:
                errors.append(
                    f"{doc_path}: GENERATED blocks are stale. "
                    f"Run: python scripts/gen_component_doc.py {doc_path}"
                )
        return errors

    # Generate and update
    component_class_type = REGISTRY.get(component_name)
    if component_class_type is None:
        errors.append(f"{doc_path}: component '{component_name}' not found in REGISTRY")
        return errors

    updated = update_generated_blocks(content, component_class_type, component_name)
    if updated != content:
        doc_path.write_text(updated)

    return errors


def discover_docs() -> List[Path]:
    """Find all component doc markdown files."""
    if not DOCS_DIR.exists():
        return []
    return sorted(DOCS_DIR.rglob("*.md"))


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point for doc generation and validation."""
    parser = argparse.ArgumentParser(description="Generate/validate component doc blocks")
    parser.add_argument("docs", nargs="*", help="Doc file paths (or --all)")
    parser.add_argument("--all", action="store_true", help="Process all component docs")
    parser.add_argument("--validate-only", action="store_true", help="Check for stale blocks without updating")
    args = parser.parse_args(argv)

    # Ensure components are imported to populate REGISTRY
    _ensure_components_imported()

    doc_paths: List[Path] = []
    if args.all:
        doc_paths = discover_docs()
    else:
        doc_paths = [Path(d) for d in args.docs]

    if not doc_paths:
        return 0

    all_errors: List[str] = []
    for doc_path in doc_paths:
        errors = process_doc(doc_path, validate_only=args.validate_only)
        all_errors.extend(errors)

    if all_errors:
        for err in all_errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    return 0


def _ensure_components_imported():
    """Import component packages to trigger REGISTRY side effects."""
    try:
        import src.v2.components.transform  # noqa: F401
    except ImportError:
        pass
    try:
        import src.v2.components.file  # noqa: F401
    except ImportError:
        pass
    try:
        import src.v2.components.aggregate  # noqa: F401
    except ImportError:
        pass
    try:
        import src.v2.components.python  # noqa: F401
    except ImportError:
        pass
    try:
        import src.v2.components.utility  # noqa: F401
    except ImportError:
        pass


if __name__ == "__main__":
    sys.exit(main())
