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


# ===== Task 4.3: join_simple_equality =====

import pandas as pd

from src.v1.engine.components.transform.map.map_joins import (
    join_simple_equality,
)


def _lookup_simple(name="row2", lookup_column="key", join_mode="LEFT_OUTER_JOIN",
                   matching_mode="UNIQUE_MATCH"):
    return LookupCfg(
        name=name,
        join_keys=[JoinKeyCfg(lookup_column, "{{java}}row1.key", "str")],
        join_mode=join_mode,
        matching_mode=matching_mode,
    )


def test_simple_equality_left_outer_basic():
    joined = pd.DataFrame({"id": [1, 2], "key": ["A", "B"]})
    lookup = pd.DataFrame({"key": ["A", "C"], "label": ["alpha", "charlie"]})
    result, rejects = join_simple_equality(joined, lookup, _lookup_simple())
    assert list(result["id"]) == [1, 2]
    # Row 0 should have label "alpha"; row 1 has NaN (unmatched)
    labels = list(result["row2.label"])
    assert labels[0] == "alpha"
    assert pd.isna(labels[1])
    assert rejects is None


def test_simple_equality_inner_join_with_rejects():
    joined = pd.DataFrame({"id": [1, 2], "key": ["A", "B"]})
    lookup = pd.DataFrame({"key": ["A"], "label": ["alpha"]})
    result, rejects = join_simple_equality(
        joined, lookup, _lookup_simple(join_mode="INNER_JOIN")
    )
    assert list(result["id"]) == [1]
    assert rejects is not None
    assert list(rejects["id"]) == [2]


def test_simple_equality_unique_match_keeps_last():
    """UNIQUE_MATCH on duplicate keys keeps the LAST (HashMap.put semantic)."""
    joined = pd.DataFrame({"id": [1], "key": ["A"]})
    lookup = pd.DataFrame({"key": ["A", "A"], "label": ["first", "last"]})
    result, _ = join_simple_equality(joined, lookup, _lookup_simple())
    assert list(result["row2.label"]) == ["last"]


def test_simple_equality_first_match():
    joined = pd.DataFrame({"id": [1], "key": ["A"]})
    lookup = pd.DataFrame({"key": ["A", "A"], "label": ["first", "last"]})
    result, _ = join_simple_equality(
        joined, lookup, _lookup_simple(matching_mode="FIRST_MATCH")
    )
    assert list(result["row2.label"]) == ["first"]


def test_simple_equality_all_matches_cartesian():
    joined = pd.DataFrame({"id": [1], "key": ["A"]})
    lookup = pd.DataFrame({"key": ["A", "A"], "label": ["v1", "v2"]})
    result, _ = join_simple_equality(
        joined, lookup, _lookup_simple(matching_mode="ALL_MATCHES")
    )
    assert sorted(result["row2.label"]) == ["v1", "v2"]
