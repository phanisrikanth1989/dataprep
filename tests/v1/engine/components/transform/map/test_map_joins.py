"""Join strategy classification, schema computation, and join execution."""
from src.v1.engine.components.transform.map.map_config import (
    LookupCfg, JoinKeyCfg, VariableCfg,
)
from src.v1.engine.components.transform.map.map_joins import (
    JoinStrategy,
    classify_join_strategy,
    compute_joined_df_schema,
)


def _lkup(join_keys=(), activate_filter=False, filter="", lookup_mode="LOAD_ONCE"):
    return LookupCfg(
        name="row2",
        join_keys=list(join_keys),
        lookup_mode=lookup_mode,
        filter=filter,
        activate_filter=activate_filter,
    )


# ===== Task 4.1: classify_join_strategy =====

def test_classify_reload_overrides_everything():
    lk = _lkup(lookup_mode="RELOAD_AT_EACH_ROW",
              join_keys=[JoinKeyCfg("k", "{{java}}row1.key", "str")])
    assert classify_join_strategy(lk) == JoinStrategy.RELOAD


def test_classify_simple_when_all_keys_are_plain_column_refs():
    lk = _lkup(join_keys=[JoinKeyCfg("k", "{{java}}row1.key", "str")])
    assert classify_join_strategy(lk) == JoinStrategy.SIMPLE


def test_classify_computed_when_any_key_has_expression():
    lk = _lkup(join_keys=[
        JoinKeyCfg("k", "{{java}}routines.StringHandling.UPCASE(row1.key)", "str"),
    ])
    assert classify_join_strategy(lk) == JoinStrategy.COMPUTED


def test_classify_filter_as_match_when_no_keys_and_active_filter():
    lk = _lkup(activate_filter=True, filter="{{java}}row1.a == row2.b")
    assert classify_join_strategy(lk) == JoinStrategy.FILTER_AS_MATCH


def test_classify_filter_as_match_when_no_keys_no_filter_pure_cartesian():
    lk = _lkup()
    # Pure cartesian (no keys, no filter) -- treat as FILTER_AS_MATCH with no filter
    assert classify_join_strategy(lk) == JoinStrategy.FILTER_AS_MATCH


# ===== Task 4.2: compute_joined_df_schema =====

def _col(name, type):
    return {"name": name, "type": type}


def test_compute_schema_main_only():
    schema = compute_joined_df_schema(
        main_schema=[_col("id", "int"), _col("name", "str")],
        consumed_lookups=[],
        variables=[],
        temp_join_key_cols={},
    )
    assert schema == {"id": "int", "name": "str"}


def test_compute_schema_with_lookups_prefixed():
    schema = compute_joined_df_schema(
        main_schema=[_col("id", "int")],
        consumed_lookups=[
            ("row2", [_col("key", "str"), _col("label", "str")]),
            ("row3", [_col("amount", "float")]),
        ],
        variables=[],
        temp_join_key_cols={},
    )
    assert schema == {
        "id": "int",
        "row2.key": "str",
        "row2.label": "str",
        "row3.amount": "float",
    }


def test_compute_schema_with_variables_prefixed():
    schema = compute_joined_df_schema(
        main_schema=[_col("id", "int")],
        consumed_lookups=[],
        variables=[VariableCfg(name="v1", expression="", type="str")],
        temp_join_key_cols={},
    )
    assert schema == {"id": "int", "Var.v1": "str"}


def test_compute_schema_with_temp_join_key_cols():
    schema = compute_joined_df_schema(
        main_schema=[_col("id", "int")],
        consumed_lookups=[],
        variables=[],
        temp_join_key_cols={"__jk_main_0__": "str"},
    )
    assert schema == {"id": "int", "__jk_main_0__": "str"}
