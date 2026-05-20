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


# ===== _emit_vars_section =====

from src.v1.engine.components.transform.map.map_compiled_script import (
    _emit_vars_section,
)
from src.v1.engine.components.transform.map.map_config import parse_config


def _cfg_with_vars(var_specs):
    """var_specs: list of (name, expression) pairs."""
    raw = {
        "inputs": {
            "main": {"name": "row1"},
            "lookups": [{
                "name": "lkp1", "join_keys": [],
                "matching_mode": "UNIQUE_MATCH", "lookup_mode": "LOAD_ONCE",
            }],
        },
        "variables": [
            {"name": n, "expression": e, "type": "str"}
            for n, e in var_specs
        ],
        "outputs": [{
            "name": "out", "columns": [
                {"name": "id", "expression": "row1.id", "type": "int"},
            ],
        }],
    }
    return parse_config(raw)


def test_emit_vars_section_empty_returns_no_closures():
    cfg = _cfg_with_vars([])
    closure_defs, dispatch_lines = _emit_vars_section(cfg, component_id="tMap_1")
    assert closure_defs == []
    assert dispatch_lines == []


def test_emit_vars_section_single_var_one_closure():
    cfg = _cfg_with_vars([("v1", "row1.amount + 1")])
    closure_defs, dispatch_lines = _emit_vars_section(cfg, component_id="tMap_1")
    # One closure definition starting with `def vars_chunk0 = {`
    assert any("def vars_chunk0 =" in d for d in closure_defs)
    # One dispatch call site
    assert dispatch_lines == ['vars_chunk0.call(i, row1, lkp1, Var);']
    # Closure body contains the Var.put line
    full = "\n".join(closure_defs)
    assert 'Var.put("v1", row1.amount + 1);' in full


def test_emit_vars_section_many_small_vars_one_closure():
    # 10 vars of ~50 chars each = ~500 chars, well under 8000 target
    cfg = _cfg_with_vars([(f"v{i}", f"row1.x{i}") for i in range(10)])
    closure_defs, dispatch_lines = _emit_vars_section(cfg, component_id="tMap_1")
    # All in one closure
    closure_def_count = sum(1 for d in closure_defs if "def vars_chunk" in d)
    assert closure_def_count == 1
    assert dispatch_lines == ['vars_chunk0.call(i, row1, lkp1, Var);']


def test_emit_vars_section_large_vars_split_into_multiple_closures():
    # 200 vars with ~80-char expressions = ~16KB; expect 2 or 3 closures
    cfg = _cfg_with_vars([(f"v{i}", "row1." + ("x" * 70)) for i in range(200)])
    closure_defs, dispatch_lines = _emit_vars_section(cfg, component_id="tMap_1")
    closure_def_count = sum(1 for d in closure_defs if "def vars_chunk" in d)
    assert closure_def_count >= 2, f"Expected >=2 closures, got {closure_def_count}"
    # One dispatch line per closure, in order
    assert len(dispatch_lines) == closure_def_count
    for i, line in enumerate(dispatch_lines):
        assert f"vars_chunk{i}.call(i, row1, lkp1, Var);" == line


def test_emit_vars_section_signature_includes_all_lookups():
    raw = {
        "inputs": {
            "main": {"name": "row1"},
            "lookups": [
                {"name": "lkpA", "join_keys": []},
                {"name": "lkpB", "join_keys": []},
            ],
        },
        "variables": [{"name": "v", "expression": "1", "type": "str"}],
        "outputs": [{"name": "out", "columns": [{"name": "id", "expression": "1", "type": "int"}]}],
    }
    cfg = parse_config(raw)
    closure_defs, _ = _emit_vars_section(cfg, component_id="tMap_1")
    full = "\n".join(closure_defs)
    # Closure signature lists both lookups
    assert "RowWrapper lkpA" in full
    assert "RowWrapper lkpB" in full


def test_emit_vars_section_strips_java_marker_and_escapes_dollar():
    cfg = _cfg_with_vars([("v1", '{{java}}"$total"')])
    closure_defs, _ = _emit_vars_section(cfg, component_id="tMap_1")
    full = "\n".join(closure_defs)
    # Marker stripped, $ escaped
    assert 'Var.put("v1", "\\$total");' in full
    assert "{{java}}" not in full


def test_emit_vars_section_hard_cap_violation_names_the_variable():
    """When a variable expression exceeds the hard cap, the error
    message identifies which variable -- not just 'variable expression'.
    """
    huge_expr = "row1.x + " + ("a" * 50000)
    cfg = _cfg_with_vars([("v_good", "row1.y"), ("v_huge", huge_expr)])
    with pytest.raises(ConfigurationError) as exc:
        _emit_vars_section(cfg, component_id="tMap_42")
    msg = str(exc.value)
    assert "tMap_42" in msg
    assert "v_huge" in msg, f"Error should name the offending variable, got: {msg}"


# ===== _emit_output_section =====

from src.v1.engine.components.transform.map.map_compiled_script import (
    _emit_output_section,
)


def _cfg_with_output(output_cols, is_reject_pass=False):
    """output_cols: list of (name, expression) pairs."""
    raw = {
        "inputs": {
            "main": {"name": "row1"},
            "lookups": [{"name": "lkp1", "join_keys": []}],
        },
        "variables": [],
        "outputs": [{
            "name": "out", "is_reject": False,
            "inner_join_reject": is_reject_pass,
            "catch_output_reject": False,
            "columns": [
                {"name": n, "expression": e, "type": "str"}
                for n, e in output_cols
            ],
        }],
    }
    return parse_config(raw)


def test_emit_output_section_small_output_one_closure():
    cfg = _cfg_with_output([("a", "row1.x"), ("b", "row1.y")])
    out = cfg.outputs[0]
    closure_defs, dispatch_lines = _emit_output_section(
        out, cfg, component_id="tMap_1", is_reject_pass=False,
    )
    assert any("def out_chunk0 =" in d for d in closure_defs)
    assert dispatch_lines == ['out_chunk0.call(i, row1, lkp1, Var, out_tempRow);']
    full = "\n".join(closure_defs)
    assert "tempRow[0] = row1.x;" in full
    assert "tempRow[1] = row1.y;" in full


def test_emit_output_section_large_output_multiple_closures():
    # 180 cols x ~50-char exprs = ~9KB; expect at least 2 closures
    cols = [(f"c{i}", f"row1.col{i} + " + ('x' * 40)) for i in range(180)]
    cfg = _cfg_with_output(cols)
    out = cfg.outputs[0]
    closure_defs, dispatch_lines = _emit_output_section(
        out, cfg, component_id="tMap_1", is_reject_pass=False,
    )
    closure_count = sum(1 for d in closure_defs if "def out_chunk" in d)
    assert closure_count >= 2, f"Expected >=2 closures for 180 cols, got {closure_count}"
    # Dispatch lines match closure count, in order
    assert len(dispatch_lines) == closure_count
    for i, line in enumerate(dispatch_lines):
        assert f"out_chunk{i}.call(i, row1, lkp1, Var, out_tempRow);" == line


def test_emit_output_section_reject_pass_uses_reject_chunk_naming():
    cfg = _cfg_with_output([("a", "row1.x")], is_reject_pass=True)
    out = cfg.outputs[0]
    closure_defs, dispatch_lines = _emit_output_section(
        out, cfg, component_id="tMap_1", is_reject_pass=True,
    )
    # Reject pass uses {name}_reject_chunk{N}
    assert any("def out_reject_chunk0 =" in d for d in closure_defs)
    assert dispatch_lines == ['out_reject_chunk0.call(i, row1, lkp1, Var, out_tempRow);']


def test_emit_output_section_single_huge_expression_in_own_chunk():
    # One 9KB expression alongside two small ones
    huge = "row1.x + " + ("a" * 8990)
    cfg = _cfg_with_output([("s1", "row1.x"), ("big", huge), ("s2", "row1.y")])
    out = cfg.outputs[0]
    closure_defs, dispatch_lines = _emit_output_section(
        out, cfg, component_id="tMap_1", is_reject_pass=False,
    )
    closure_count = sum(1 for d in closure_defs if "def out_chunk" in d)
    assert closure_count >= 2, "Huge expression should force at least one chunk boundary"


def test_emit_output_section_expression_over_hard_cap_raises_with_column_name():
    over_cap = "row1.x + " + ("a" * 50000)
    cfg = _cfg_with_output([("good", "row1.y"), ("toobig", over_cap)])
    out = cfg.outputs[0]
    with pytest.raises(ConfigurationError) as exc:
        _emit_output_section(
            out, cfg, component_id="tMap_4", is_reject_pass=False,
        )
    msg = str(exc.value)
    assert "tMap_4" in msg
    assert "output 'out' column 'toobig'" in msg


def test_emit_output_section_no_lookups_signature_omits_lookup_params():
    raw = {
        "inputs": {"main": {"name": "row1"}, "lookups": []},
        "variables": [],
        "outputs": [{
            "name": "out", "columns": [{"name": "a", "expression": "row1.x", "type": "str"}],
        }],
    }
    cfg = parse_config(raw)
    out = cfg.outputs[0]
    closure_defs, dispatch_lines = _emit_output_section(
        out, cfg, component_id="tMap_1", is_reject_pass=False,
    )
    full = "\n".join(closure_defs)
    # No "RowWrapper lkp" in signature
    assert "RowWrapper lkp" not in full
    # Dispatch line has no lookup args
    assert dispatch_lines == ['out_chunk0.call(i, row1, Var, out_tempRow);']


# ===== _emit_filter_section =====

from src.v1.engine.components.transform.map.map_compiled_script import (
    _emit_filter_section,
)


def test_emit_filter_section_no_filter_returns_none_and_true():
    cfg = _cfg_with_output([("a", "row1.x")])
    out = cfg.outputs[0]
    out.activate_filter = False
    out.filter = ""
    closure_def, expr = _emit_filter_section(out, cfg, component_id="tMap_1")
    assert closure_def is None
    assert expr == "true"


def test_emit_filter_section_small_filter_inline():
    cfg = _cfg_with_output([("a", "row1.x")])
    out = cfg.outputs[0]
    out.activate_filter = True
    out.filter = "row1.amount > 0"
    closure_def, expr = _emit_filter_section(out, cfg, component_id="tMap_1")
    # Inline: no closure
    assert closure_def is None
    assert expr == "row1.amount > 0"


def test_emit_filter_section_huge_filter_hoisted_to_closure():
    cfg = _cfg_with_output([("a", "row1.x")])
    out = cfg.outputs[0]
    out.activate_filter = True
    # 9KB filter
    out.filter = "row1.x > 0 && " + "true && " * 1200  # ~9.6KB
    closure_def, expr = _emit_filter_section(out, cfg, component_id="tMap_1")
    # Closure emitted
    assert closure_def is not None
    assert "def out_filter =" in closure_def
    # Callable expression dispatches to the closure
    assert expr == "out_filter.call(i, row1, lkp1, Var)"


def test_emit_filter_section_filter_over_hard_cap_raises():
    cfg = _cfg_with_output([("a", "row1.x")])
    out = cfg.outputs[0]
    out.activate_filter = True
    out.filter = "x" * (_SINGLE_EXPR_HARD_CAP + 100)
    with pytest.raises(ConfigurationError) as exc:
        _emit_filter_section(out, cfg, component_id="tMap_9")
    msg = str(exc.value)
    assert "tMap_9" in msg
    assert "output 'out' filter" in msg


def test_emit_filter_section_strips_java_marker_and_escapes_dollar():
    cfg = _cfg_with_output([("a", "row1.x")])
    out = cfg.outputs[0]
    out.activate_filter = True
    out.filter = '{{java}}"$amount" != null'
    closure_def, expr = _emit_filter_section(out, cfg, component_id="tMap_1")
    # Marker stripped, $ escaped in inline expression
    assert closure_def is None
    assert expr == '"\\$amount" != null'


def test_emit_filter_section_huge_filter_no_lookups_signature_omits_lookups():
    raw = {
        "inputs": {"main": {"name": "row1"}, "lookups": []},
        "variables": [],
        "outputs": [{
            "name": "out",
            "columns": [{"name": "a", "expression": "row1.x", "type": "str"}],
        }],
    }
    cfg = parse_config(raw)
    out = cfg.outputs[0]
    out.activate_filter = True
    # Force a hoist by exceeding _CHUNK_TARGET_CHARS
    out.filter = "row1.x > 0 && " + "true && " * 1200
    closure_def, expr = _emit_filter_section(out, cfg, component_id="tMap_1")
    assert closure_def is not None
    assert "RowWrapper lkp" not in closure_def
    # Dispatch call has no lookup args
    assert expr == "out_filter.call(i, row1, Var)"


def test_emit_vars_section_no_lookups_signature_omits_lookups():
    raw = {
        "inputs": {"main": {"name": "row1"}, "lookups": []},
        "variables": [{"name": "v1", "expression": "row1.amount + 1", "type": "int"}],
        "outputs": [{"name": "out", "columns": [{"name": "id", "expression": "row1.id", "type": "int"}]}],
    }
    cfg = parse_config(raw)
    closure_defs, dispatch_lines = _emit_vars_section(cfg, component_id="tMap_1")
    full = "\n".join(closure_defs)
    assert "RowWrapper lkp" not in full
    # Dispatch line has no lookup args
    assert dispatch_lines == ['vars_chunk0.call(i, row1, Var);']
