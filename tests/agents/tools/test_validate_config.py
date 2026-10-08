import agents.tools.validate_config as vc
from agents.tools.validate_config import validate_config


def test_valid_filter_config_passes():
    cfg = {"conditions": [{"column": "amt", "operator": ">", "value": "0"}], "logical_op": "&&"}
    assert validate_config("FilterRows", cfg) == []


def test_unknown_key_flagged_strict_only():
    cfg = {"bogus_key": 1, "conditions": []}
    errs = validate_config("FilterRows", cfg, strict=True)
    assert any("bogus_key" in e for e in errs)
    assert validate_config("FilterRows", cfg, strict=False) == []   # ignored when not strict


def test_missing_required_when():
    cfg = {"use_advanced": True}          # advanced_cond required when use_advanced
    errs = validate_config("FilterRows", cfg)
    assert any("advanced_cond" in e for e in errs)


def test_wrong_type_flagged():
    cfg = {"conditions": "not a list"}
    assert any("conditions" in e and "list" in e for e in validate_config("FilterRows", cfg))


def test_out_of_enum_operator_flagged():
    cfg = {"conditions": [{"column": "amt", "operator": "<=>"}]}  # <=> not in _OPERATOR_MAP
    assert any("operator" in e for e in validate_config("FilterRows", cfg))


def test_nested_missing_required_column():
    cfg = {"conditions": [{"operator": "=="}]}   # column required per item
    assert any("column" in e for e in validate_config("FilterRows", cfg))


def test_invalid_uniquerow_keep_returns_error_not_crash():
    errs = validate_config("UniqueRow", {"keep": "bogus"})   # must NOT raise
    assert any("keep" in e for e in errs)


# ---------------------------------------------------------------------------
# Important #1 -- validate_config must NEVER raise on untrusted input.
# ---------------------------------------------------------------------------


def test_unhashable_enum_value_returns_error_not_crash():
    # keep has an enum but no type; a list value is unhashable -> must not crash.
    errs = validate_config("UniqueRow", {"keep": ["x"]})
    assert errs and any("keep" in e for e in errs)


def test_unknown_schema_type_name_does_not_crash(monkeypatch):
    # A schema referencing a type name not in _PY_TYPES must skip the isinstance
    # check rather than KeyError-crash.
    monkeypatch.setattr(vc, "is_curated", lambda ct: True)   # bypass curation gate to reach strict path
    monkeypatch.setattr(vc, "load_schema", lambda ct: {"keys": {"n": {"type": "integer"}}})
    assert vc.validate_config("X", {"n": 1}) == []   # must NOT raise


# ---------------------------------------------------------------------------
# Important #2 -- nested unknown sub-keys flagged under strict only.
# ---------------------------------------------------------------------------


def test_nested_unknown_subkey_flagged_strict_only():
    cfg = {"conditions": [{"column": "a", "operator": "==", "BOGUS": 1}]}
    assert any("BOGUS" in e for e in validate_config("FilterRows", cfg, strict=True))
    assert validate_config("FilterRows", cfg, strict=False) == []


# ---------------------------------------------------------------------------
# Minor (a) -- a bool must be flagged for an int/float field.
# ---------------------------------------------------------------------------


def test_bool_flagged_for_int_field(monkeypatch):
    monkeypatch.setattr(vc, "is_curated", lambda ct: True)   # bypass curation gate to reach strict path
    monkeypatch.setattr(vc, "load_schema", lambda ct: {"keys": {"n": {"type": "int"}}})
    assert any("n" in e for e in vc.validate_config("X", {"n": True}))
    assert vc.validate_config("X", {"n": 5}) == []          # a real int still passes


def test_bool_flagged_for_float_field(monkeypatch):
    monkeypatch.setattr(vc, "is_curated", lambda ct: True)   # bypass curation gate to reach strict path
    monkeypatch.setattr(vc, "load_schema", lambda ct: {"keys": {"n": {"type": "float"}}})
    assert any("n" in e for e in vc.validate_config("X", {"n": False}))
    assert vc.validate_config("X", {"n": 1.5}) == []


# ---------------------------------------------------------------------------
# Minor (b) -- non_empty list rule.
# ---------------------------------------------------------------------------


def test_empty_criteria_flagged_sortrow():
    assert any("criteria" in e for e in validate_config("SortRow", {"criteria": []}))


def test_empty_outputs_flagged_map():
    errs = validate_config("Map", {"inputs": {}, "outputs": []})
    assert any("outputs" in e for e in errs)


# ---------------------------------------------------------------------------
# Full-component support -- uncurated types degrade gracefully (advisory only).
# ---------------------------------------------------------------------------


def test_uncurated_type_degrades_gracefully():
    from agents.tools.validate_config import validate_config
    # a real but non-curated component -> no hard error, no raise
    # (tPython/PythonComponent is registered but intentionally has no curated schema)
    assert validate_config("tPython", {"python_code": "df['x']=1", "anything": 2}) == []


def test_is_curated_flags_curated_vs_not():
    from agents.tools.component_schema import is_curated
    assert is_curated("FilterRows") is True
    assert is_curated("tPython") is False   # a real but non-curated engine component
