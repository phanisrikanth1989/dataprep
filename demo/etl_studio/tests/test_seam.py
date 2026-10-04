"""Seam tripwire (ticket 07 Q11): core/ never imports adapters or anything
vscode-flavored. Kept despite the effort's testing deprioritization -- it is
an alarm, not ceremony.

Runs standalone (no pytest needed):
    python tests/test_seam.py
or under pytest:
    pytest demo/etl_studio/tests/test_seam.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import List

CORE_DIR = Path(__file__).resolve().parent.parent / "core"


def _is_forbidden(module: str) -> bool:
    first = (module or "").split(".")[0]
    return first == "adapters" or first.startswith("vscode")


def _violations() -> List[str]:
    out: List[str] = []
    for py in sorted(CORE_DIR.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_forbidden(alias.name):
                        out.append(f"{py.name}:{node.lineno} imports {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                # Covers relative escapes too: `from ..adapters import x`
                # carries module='adapters' with level=2.
                if _is_forbidden(node.module or ""):
                    out.append(f"{py.name}:{node.lineno} imports from {node.module}")
    return out


def test_core_never_imports_adapters_or_vscode() -> None:
    violations = _violations()
    assert not violations, "seam violations:\n" + "\n".join(violations)


if __name__ == "__main__":
    found = _violations()
    if found:
        print("FAIL: core/ reaches around the provider port:")
        for v in found:
            print("  " + v)
        sys.exit(1)
    count = len(list(CORE_DIR.rglob("*.py")))
    print(f"PASS: {count} core modules import neither adapters nor vscode")
