"""Guardrail tests: rung is derived from the handle TYPE (authority), never the LLM hint; fail-closed default."""
from agents.tools.normalize_validate import _derive_rung, _resolve


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
