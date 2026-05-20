"""Unit tests for the line-chunking helper in map_compiled_script."""
import pytest

from src.v1.engine.components.transform.map.map_compiled_script import (
    _CHUNK_TARGET_CHARS,
    _SINGLE_EXPR_HARD_CAP,
    _chunk_emitted_lines,
)
from src.v1.engine.exceptions import ConfigurationError


def test_empty_lines_returns_empty_chunks():
    assert _chunk_emitted_lines([], section_label="vars", component_id="tMap_1") == []


def test_single_small_line_returns_one_chunk():
    lines = ['Var.put("a", 1);']
    chunks = _chunk_emitted_lines(lines, section_label="vars", component_id="tMap_1")
    assert chunks == [lines]


def test_lines_under_target_stay_in_one_chunk():
    lines = ['Var.put("a", 1);'] * 10  # ~160 chars total
    chunks = _chunk_emitted_lines(lines, section_label="vars", component_id="tMap_1")
    assert len(chunks) == 1
    assert chunks[0] == lines


def test_lines_over_target_split_into_multiple_chunks():
    # Each line is ~100 chars; with target=8000, expect ~80 lines per chunk
    line = "x" * 100  # 100-char line
    lines = [line] * 200  # 20,000 total chars; expect ~3 chunks
    chunks = _chunk_emitted_lines(lines, section_label="vars", component_id="tMap_1")
    assert len(chunks) >= 2, f"Expected multiple chunks for 20KB of lines, got {len(chunks)}"
    # No chunk exceeds the target by more than one line's worth
    for chunk in chunks:
        total = sum(len(l) for l in chunk)
        assert total <= _CHUNK_TARGET_CHARS + len(line), (
            f"Chunk total {total} exceeds target {_CHUNK_TARGET_CHARS} + slack"
        )


def test_single_oversized_line_gets_own_chunk_no_error():
    # One 9KB line is over the 8KB target but under the 50KB hard cap
    over_target = "x" * 9000
    small = "y" * 100
    lines = [small, over_target, small]
    chunks = _chunk_emitted_lines(lines, section_label="vars", component_id="tMap_1")
    # The oversized line ends up as the sole content of its chunk
    chunk_with_big_line = next(
        (c for c in chunks if any(len(l) > _CHUNK_TARGET_CHARS for l in c)),
        None,
    )
    assert chunk_with_big_line is not None
    assert len(chunk_with_big_line) == 1
    assert chunk_with_big_line[0] == over_target


def test_single_line_over_hard_cap_raises_configuration_error():
    over_cap = "x" * (_SINGLE_EXPR_HARD_CAP + 1)
    with pytest.raises(ConfigurationError) as exc:
        _chunk_emitted_lines([over_cap], section_label="output 'out1' column 'col_42'",
                             component_id="tMap_7")
    msg = str(exc.value)
    assert "tMap_7" in msg
    assert "output 'out1' column 'col_42'" in msg
    assert str(_SINGLE_EXPR_HARD_CAP) in msg


def test_chunk_boundary_only_breaks_between_lines_never_mid_line():
    # Construct lines such that the cumulative sum lands exactly at the
    # boundary at line 5: 5 lines * 1700 chars = 8500, > 8000 target.
    lines = ["a" * 1700 for _ in range(5)] + ["b" * 100 for _ in range(5)]
    chunks = _chunk_emitted_lines(lines, section_label="vars", component_id="tMap_1")
    # Every line must appear exactly once, in order, and only at a chunk break
    flattened = [l for c in chunks for l in c]
    assert flattened == lines


def test_constants_have_expected_values():
    # Sanity: spec section 4.2 lists these constants
    assert _CHUNK_TARGET_CHARS == 8000
    assert _SINGLE_EXPR_HARD_CAP == 50000
