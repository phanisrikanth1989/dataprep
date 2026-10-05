"""The rules every v2 source file keeps, checked on the text of the code.

They are the ones in docs/v2/writing-a-component.md that a reviewer would
otherwise have to look for by eye in each new component.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCES = sorted((ROOT / "src" / "v2").rglob("*.py"))
COMPONENTS = [path for path in SOURCES if "components" in path.parts]

# Where a component is allowed to run data itself, and why.
MAY_COLLECT = {
    "file_input_delimited.py": "a footer is counted in lines from the end, so the file's length is needed first",
    "file_input_positional.py": "the same footer count",
    "file_input_fullrow.py": "the same footer count",
    "file_input_excel.py": "there is no lazy Excel reader",
    "file_output_delimited.py": "counts the rows of the file it has just written",
}
ROW_BY_ROW = re.compile(r"\.(map_elements|map_batches|map_rows|apply|iter_rows|rows)\(")
# Components that are handed real rows by the engine and may walk them.
HOLD_ROWS = {"context_load.py", "log_row.py", "python_dataframe.py", "file_input_excel.py"}


def code_lines(path):
    """The lines of a file that are code: no comments, no docstrings."""
    text = path.read_text(encoding="utf-8")
    text = re.sub(r'"""(?:.|\n)*?"""', '""', text)
    return [(number, line.split("#")[0]) for number, line in enumerate(text.splitlines(), start=1)]


def relative(path):
    return str(path.relative_to(ROOT))


@pytest.mark.parametrize("path", SOURCES, ids=relative)
def test_source_is_plain_ascii(path):
    text = path.read_text(encoding="utf-8")
    strange = sorted({char for char in text if ord(char) > 127})
    assert strange == [], f"non-ASCII characters {strange!r}"


@pytest.mark.parametrize("path", SOURCES, ids=relative)
def test_no_frame_is_marked_cached(path):
    # Polars 1.44 loses a select or drop that sits between a cached frame and a frame with two readers.
    found = [number for number, line in code_lines(path) if re.search(r"\.cache\(\)", line)]
    assert found == [], f".cache() on line(s) {found}"


@pytest.mark.parametrize("path", COMPONENTS, ids=relative)
def test_components_do_not_run_the_data(path):
    if path.name in MAY_COLLECT:
        return
    found = [number for number, line in code_lines(path) if re.search(r"\.(collect|fetch)\(", line)]
    assert found == [], f"collect() on line(s) {found}; components build plans, the engine runs them"


@pytest.mark.parametrize("path", COMPONENTS, ids=relative)
def test_components_do_not_work_row_by_row(path):
    if path.name in HOLD_ROWS:
        return
    found = [number for number, line in code_lines(path) if ROW_BY_ROW.search(line)]
    assert found == [], f"row-by-row call on line(s) {found}"


@pytest.mark.parametrize("path", COMPONENTS, ids=relative)
def test_joins_and_groupings_keep_row_order(path):
    lines = code_lines(path)
    text = "\n".join(line for _, line in lines)
    for call in re.finditer(r"\.(join|unique|group_by)\(", text):
        # The call's arguments, up to its closing bracket.
        depth, end = 0, call.end()
        for end in range(call.end() - 1, len(text)):
            depth += text[end] == "("
            depth -= text[end] == ")"
            if depth == 0:
                break
        arguments = text[call.end():end]
        if call.group(1) == "join" and "how=" not in arguments:
            continue  # joining text ("; ".join(...)), not frames
        assert "maintain_order" in arguments, (
            f"{relative(path)}: .{call.group(1)}({arguments.strip()[:60]}...) does not say maintain_order"
        )
