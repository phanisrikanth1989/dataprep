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
