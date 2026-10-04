"""Python-callback ban enforcement (PITFALLS #2).

Greps src/v2/components/ (excluding python/) for banned patterns:
  - map_elements
  - .apply(lambda
  - map_batches

Fails if any are found. The python/ directory is explicitly excluded
because python_row, python_code, python_dataframe are exempted from
this ban -- the whole point of those components is to run Python.
"""
import re
from pathlib import Path

import pytest

COMPONENTS_DIR = Path("src/v2/components")
EXCLUDED_DIRS = {"python", "__pycache__"}

BANNED_PATTERNS = [
    re.compile(r"\.map_elements\s*\("),
    re.compile(r"\.apply\s*\(\s*lambda"),
    re.compile(r"\.map_batches\s*\("),
]

BANNED_NAMES = ["map_elements", ".apply(lambda", "map_batches"]


class TestNoPythonCallbacks:
    """Enforce PITFALLS #2: no Python callbacks in non-python components."""

    def test_no_banned_patterns(self):
        """No .map_elements(), .apply(lambda, or .map_batches() in non-python component code."""
        violations = []

        for py_file in COMPONENTS_DIR.rglob("*.py"):
            # Skip python/ subpackage and __pycache__
            if any(part in EXCLUDED_DIRS for part in py_file.parts):
                continue

            content = py_file.read_text()
            for pattern, name in zip(BANNED_PATTERNS, BANNED_NAMES):
                for match in pattern.finditer(content):
                    line_num = content[: match.start()].count("\n") + 1
                    violations.append(f"{py_file}:{line_num} -- banned pattern '{name}' found")

        assert not violations, (
            "Python callback patterns found in non-python components "
            "(PITFALLS #2 violation):\n" + "\n".join(violations)
        )
