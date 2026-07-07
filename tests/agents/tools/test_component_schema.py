from agents.tools.component_schema import BASE_KEYS, load_schema, resolve_enum_ref


def test_load_schema_by_type_and_alias():
    by_type = load_schema("FilterRows")
    assert by_type["type"] == "FilterRows"
    assert by_type["keys"]["logical_op"]["enum"] == ["&&", "||", "AND", "OR"]
    by_alias = load_schema("tFilterRow")           # alias resolves to same schema
    assert by_alias["type"] == "FilterRows"


def test_resolve_enum_ref_reads_live_operator_map():
    values = resolve_enum_ref("src.v1.engine.components.transform.filter_rows:_OPERATOR_MAP")
    assert "==" in values and "IS_NULL" in values      # live keys of _OPERATOR_MAP
    assert isinstance(values, set)


def test_base_keys_present():
    assert "die_on_error" in BASE_KEYS
