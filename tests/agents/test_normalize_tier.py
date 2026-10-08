"""Guardrail tests: rung is derived from the handle TYPE (authority), never the LLM hint; fail-closed default."""
import pytest

from agents.tools.normalize_validate import (
    NeedsHuman,
    _compute_tier,
    _cross_check_coverage,
    _derive_rung,
    _reorder_to_schema,
    _resolve,
    assemble,
)


def test_rung_derived_from_type_not_hint():
    inv = {"handles": [{"id": "image:0", "type": "image"},
                       {"id": "sibling:t.csv", "type": "sibling", "csv_dialect": {"delimiter": ","}}]}
    assert _derive_rung("image:0", inv) == "3a"      # even if the LLM hinted rung-2
    assert _derive_rung("sibling:t.csv", inv) == "1"


def test_xlsx_handle_needs_human():
    inv = {"handles": [
        {"id": "sibling:book.xlsx", "type": "sibling", "path": "/x/book.xlsx", "csv_dialect": None},
        {"id": "embed:book.xls", "type": "embed", "path": "/x/book.xls"},
    ]}
    assert _derive_rung("sibling:book.xlsx", inv) == "needs_human"   # Phase 2 adds the xlsx reader
    assert _derive_rung("embed:book.xls", inv) == "needs_human"


def test_null_dialect_csv_needs_human():
    inv = {"handles": [{"id": "sibling:t.csv", "type": "sibling", "path": "/x/t.csv", "csv_dialect": None}]}
    assert _derive_rung("sibling:t.csv", inv) == "needs_human"       # unsniffable CSV -> fail closed


def test_unresolvable_id_needs_human():
    inv = {"handles": [{"id": "image:0", "type": "image"}]}
    assert _resolve("nope:9", inv) is None
    assert _derive_rung("nope:9", inv) == "needs_human"


# ------------------------------------------------------------------
# Tier: fail-closed, quantified over EVERY source AND EVERY graded output.
# ------------------------------------------------------------------
def test_rung3_expected_caps_verified_to_smoke():
    prov = {"trades": {"rung": "1"}, "result": {"rung": "3a"}}   # answer key transcribed
    assert _compute_tier(prov, ["result"], True) == "smoke"


def test_all_exact_earns_verified():
    prov = {"trades": {"rung": "1"}, "result": {"rung": "2"}}
    assert _compute_tier(prov, ["result"], True) == "verified"


def test_distinctness_violation_degrades():
    prov = {"trades": {"rung": "1"}, "result": {"rung": "2"}}   # same-all-exact
    assert _compute_tier(prov, ["result"], False) == "smoke"    # but content passthrough -> degrade


def test_needs_human_rung_caps_smoke():
    prov = {"trades": {"rung": "needs_human"}, "result": {"rung": "2"}}
    assert _compute_tier(prov, ["result"], True) == "smoke"     # a source not exact -> never verified


def test_no_sample_is_build():
    assert _compute_tier({}, [], True) == "build"               # no sample source present at all


# ------------------------------------------------------------------
# Section-9 completeness: an unaccounted handle is a hard blocker.
# ------------------------------------------------------------------
def test_unaccounted_handle_sets_needs_human():
    inventory = {"handles": [{"id": "table:0", "type": "table"},
                             {"id": "para:0", "type": "prose"}]}
    coverage_map = [{"handle": "table:0", "disposition": "extracted_to", "refs": ["trades.id"]}]
    emitted = {"trades", "trades.id"}
    unaccounted, unresolved = _cross_check_coverage(inventory, coverage_map, emitted)
    assert "para:0" in unaccounted           # absent from coverage_map -> unaccounted
    assert "table:0" not in unaccounted       # accounted: disposition + resolvable ref
    assert unresolved == []


def test_extracted_to_with_dangling_ref_is_unaccounted():
    inventory = {"handles": [{"id": "table:0", "type": "table"}]}
    coverage_map = [{"handle": "table:0", "disposition": "extracted_to", "refs": ["ghost.col"]}]
    unaccounted, _ = _cross_check_coverage(inventory, coverage_map, {"trades.id"})
    assert "table:0" in unaccounted           # ref resolves to nothing emitted -> not accounted


def test_irrelevant_handle_is_accounted():
    inventory = {"handles": [{"id": "image:0", "type": "image"}]}
    coverage_map = [{"handle": "image:0", "disposition": "irrelevant"}]
    unaccounted, _ = _cross_check_coverage(inventory, coverage_map, set())
    assert unaccounted == []                   # irrelevant needs no refs


# ------------------------------------------------------------------
# Ragged rung-3a transcription: a later row missing a row0 column must
# DEGRADE (NeedsHuman -> needs_human), never crash with a bare KeyError.
# ------------------------------------------------------------------
def test_reorder_ragged_rows_raises_needs_human_not_keyerror():
    with pytest.raises(NeedsHuman):
        _reorder_to_schema([{"a": "1", "b": "2"}, {"a": "3"}], ["a", "b"])   # row1 misses 'b'


def test_assemble_ragged_rung3a_degrades_to_needs_human():
    inventory = {"handles": [{"id": "image:0", "type": "image"}]}
    proposal = {
        "sources_schema": {"trades": [{"name": "a"}, {"name": "b"}]},
        "located": {"sample_input": {"trades": ["image:0"]}, "expected_output": {}},
        "sample_input": {"trades": [{"a": "1", "b": "2"}, {"a": "3"}]},   # ragged rung-3a transcription
        "coverage_map": [{"handle": "image:0", "disposition": "extracted_to", "refs": ["trades.a"]}],
    }
    extract_dict, status = assemble(proposal, inventory)   # must not raise
    assert status == "needs_human"
    assert extract_dict["extraction"]["status"] == "needs_human"
    assert "trades" in extract_dict["extraction"]["unresolved"]   # ragged source routed to unresolved
