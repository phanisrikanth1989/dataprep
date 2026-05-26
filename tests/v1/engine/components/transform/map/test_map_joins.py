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


# ===== Task 4.1 (updated for CONSTANT_KEY signature change): classify_join_strategy =====

def test_classify_reload_overrides_everything():
    lk = _lkup(lookup_mode="RELOAD_AT_EACH_ROW",
              join_keys=[JoinKeyCfg("k", "{{java}}row1.key", "str")])
    assert classify_join_strategy(lk, "row1", []) == JoinStrategy.RELOAD


def test_classify_simple_when_all_keys_are_plain_column_refs():
    lk = _lkup(join_keys=[JoinKeyCfg("k", "{{java}}row1.key", "str")])
    assert classify_join_strategy(lk, "row1", []) == JoinStrategy.SIMPLE


def test_classify_computed_when_any_key_has_expression():
    lk = _lkup(join_keys=[
        JoinKeyCfg("k", "{{java}}routines.StringHandling.UPCASE(row1.key)", "str"),
    ])
    assert classify_join_strategy(lk, "row1", []) == JoinStrategy.COMPUTED


def test_classify_filter_as_match_when_no_keys_and_active_filter():
    lk = _lkup(activate_filter=True, filter="{{java}}row1.a == row2.b")
    assert classify_join_strategy(lk, "row1", []) == JoinStrategy.FILTER_AS_MATCH


def test_classify_filter_as_match_when_no_keys_no_filter_pure_cartesian():
    lk = _lkup()
    assert classify_join_strategy(lk, "row1", []) == JoinStrategy.FILTER_AS_MATCH


def test_classify_constant_key_pure_context_var():
    lk = _lkup(join_keys=[JoinKeyCfg("name", "{{java}}context.SOURCE", "str")])
    assert classify_join_strategy(lk, "row1", []) == JoinStrategy.CONSTANT_KEY


def test_classify_constant_key_bare_context_var_no_marker():
    lk = _lkup(join_keys=[JoinKeyCfg("name", "context.SOURCE", "str")])
    assert classify_join_strategy(lk, "row1", []) == JoinStrategy.CONSTANT_KEY


def test_classify_constant_key_global_map():
    lk = _lkup(join_keys=[JoinKeyCfg("k", "{{java}}globalMap.X", "str")])
    assert classify_join_strategy(lk, "row1", []) == JoinStrategy.CONSTANT_KEY


def test_classify_constant_key_literal_expression():
    lk = _lkup(join_keys=[JoinKeyCfg("k", '{{java}}"constant"', "str")])
    assert classify_join_strategy(lk, "row1", []) == JoinStrategy.CONSTANT_KEY


def test_classify_constant_key_routine_static_field():
    lk = _lkup(join_keys=[JoinKeyCfg("k", "{{java}}MyRoutine.CONST", "str")])
    assert classify_join_strategy(lk, "row1", []) == JoinStrategy.CONSTANT_KEY


def test_classify_mixed_constant_and_row_key_routes_to_computed():
    # one constant key + one row-dependent key: NOT all constant, NOT all simple
    lk = _lkup(join_keys=[
        JoinKeyCfg("name", "{{java}}context.SOURCE", "str"),
        JoinKeyCfg("code", "{{java}}row1.code", "str"),
    ])
    assert classify_join_strategy(lk, "row1", []) == JoinStrategy.COMPUTED


def test_classify_marker_over_known_input_row_col_stays_simple():
    # Secondary fix validation: marker presence does NOT force COMPUTED;
    # the table prefix must be a known input to qualify as SIMPLE.
    lk = _lkup(join_keys=[JoinKeyCfg("k", "{{java}}row1.k", "str")])
    assert classify_join_strategy(lk, "row1", []) == JoinStrategy.SIMPLE


def test_classify_marker_over_prior_lookup_col_stays_simple():
    lk = _lkup(join_keys=[JoinKeyCfg("k", "{{java}}row3.k", "str")])
    assert classify_join_strategy(lk, "row1", ["row3"]) == JoinStrategy.SIMPLE


def test_classify_row_ref_in_quoted_string_routes_to_constant_key():
    # row1.foo appears only inside a quoted string -- it's data, not a ref
    lk = _lkup(join_keys=[JoinKeyCfg("k", '{{java}}"row1.foo as text"', "str")])
    assert classify_join_strategy(lk, "row1", []) == JoinStrategy.CONSTANT_KEY


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


# ===== Task 4.4: join_computed_equality =====

from unittest.mock import MagicMock


def _make_bridge_fn(bridge):
    """Build a bridge_eval callable that delegates to a mocked bridge."""
    def fn(df, expressions, main_table_name, lookup_table_names):
        return bridge.execute_tmap_preprocessing(
            df=df, expressions=expressions,
            main_table_name=main_table_name,
            lookup_table_names=lookup_table_names,
        )
    return fn


def test_computed_equality_batch_evals_expression_then_merges():
    """COMPUTED uses bridge to eval expressions on joined_df, then merges."""
    joined = pd.DataFrame({"id": [1, 2], "key": ["a", "b"]})
    lookup = pd.DataFrame({"upper_key": ["A", "B"], "label": ["alpha", "beta"]})
    lk = LookupCfg(
        name="row2",
        join_keys=[JoinKeyCfg(
            "upper_key",
            "{{java}}routines.StringHandling.UPCASE(row1.key)",
            "str",
        )],
        join_mode="LEFT_OUTER_JOIN",
    )
    bridge = MagicMock()
    bridge.execute_tmap_preprocessing.return_value = {
        "__jk_main_0__": ["A", "B"],
    }
    from src.v1.engine.components.transform.map.map_joins import (
        join_computed_equality,
    )
    result, rejects = join_computed_equality(
        joined, lookup, lk, main_name="row1",
        prior_lookups=[], bridge_eval_fn=_make_bridge_fn(bridge),
    )
    # Temp column dropped after merge
    assert "__jk_main_0__" not in result.columns
    assert list(result["row2.label"]) == ["alpha", "beta"]
    assert rejects is None
    # Bridge was called once with the expression dict
    bridge.execute_tmap_preprocessing.assert_called_once()


def test_computed_equality_inner_join_collects_rejects():
    joined = pd.DataFrame({"id": [1, 2], "key": ["a", "b"]})
    lookup = pd.DataFrame({"upper_key": ["A"], "label": ["alpha"]})
    lk = LookupCfg(
        name="row2",
        join_keys=[JoinKeyCfg("upper_key", "{{java}}row1.key.toUpperCase()", "str")],
        join_mode="INNER_JOIN",
    )
    bridge = MagicMock()
    bridge.execute_tmap_preprocessing.return_value = {
        "__jk_main_0__": ["A", "B"],
    }
    from src.v1.engine.components.transform.map.map_joins import (
        join_computed_equality,
    )
    result, rejects = join_computed_equality(
        joined, lookup, lk, main_name="row1",
        prior_lookups=[], bridge_eval_fn=_make_bridge_fn(bridge),
    )
    assert list(result["id"]) == [1]
    assert rejects is not None
    assert list(rejects["id"]) == [2]


# ===== Task 4.5: join_filter_as_match =====

import pytest
from src.v1.engine.exceptions import ComponentExecutionError


def test_filter_as_match_no_filter_pure_cartesian():
    """No filter -> pure cartesian product."""
    joined = pd.DataFrame({"a": [1, 2]})
    lookup = pd.DataFrame({"b": [10, 20]})
    lk = LookupCfg(name="row2", join_keys=[], join_mode="LEFT_OUTER_JOIN")
    from src.v1.engine.components.transform.map.map_joins import (
        join_filter_as_match,
    )
    result, rejects = join_filter_as_match(
        joined, lookup, lk, main_name="row1",
        prior_lookups=[], bridge_eval_fn=None,
    )
    assert len(result) == 4  # 2 x 2
    assert rejects is None


def test_filter_as_match_with_filter_keeps_matches():
    """Filter expression acts as the matching condition; bridge-evaluated per chunk."""
    joined = pd.DataFrame({"a": [1, 5]})
    lookup = pd.DataFrame({"b": [3, 10]})
    lk = LookupCfg(
        name="row2", join_keys=[],
        activate_filter=True, filter="{{java}}row1.a < row2.b",
        join_mode="LEFT_OUTER_JOIN",
    )
    # 4 pairs in the cross-product:
    # (1, 3) -> True (1 < 3)
    # (1, 10) -> True
    # (5, 3) -> False
    # (5, 10) -> True
    bridge = MagicMock()
    bridge.execute_tmap_preprocessing.return_value = {
        "__filter__": [True, True, False, True],
    }
    from src.v1.engine.components.transform.map.map_joins import (
        join_filter_as_match,
    )
    result, _ = join_filter_as_match(
        joined, lookup, lk, main_name="row1",
        prior_lookups=[], bridge_eval_fn=_make_bridge_fn(bridge),
    )
    assert len(result) == 3
    bridge.execute_tmap_preprocessing.assert_called_once()


def test_filter_as_match_size_guard_fails_at_100M():
    """Direct check of the size-guard threshold function."""
    from src.v1.engine.components.transform.map.map_joins import (
        _check_cross_size_guard,
    )
    with pytest.raises(ComponentExecutionError, match="safety limit"):
        _check_cross_size_guard(10_001, 10_001)  # ~100M


def test_filter_as_match_size_guard_passes_below_threshold():
    """Below 100M is fine; the function returns silently."""
    from src.v1.engine.components.transform.map.map_joins import (
        _check_cross_size_guard,
    )
    _check_cross_size_guard(1000, 1000)  # 1M -- no raise


def test_filter_as_match_inner_join_marks_main_rows_with_no_match_as_rejects():
    """INNER_JOIN: main rows that survived 0 cross-product matches go to rejects."""
    joined = pd.DataFrame({"a": [1, 5]})
    lookup = pd.DataFrame({"b": [3, 10]})
    lk = LookupCfg(
        name="row2", join_keys=[],
        activate_filter=True, filter="{{java}}row1.a < row2.b",
        join_mode="INNER_JOIN",
    )
    # 4 pairs: (1,3) T, (1,10) T, (5,3) F, (5,10) F
    bridge = MagicMock()
    bridge.execute_tmap_preprocessing.return_value = {
        "__filter__": [True, True, False, False],
    }
    from src.v1.engine.components.transform.map.map_joins import (
        join_filter_as_match,
    )
    result, rejects = join_filter_as_match(
        joined, lookup, lk, main_name="row1",
        prior_lookups=[], bridge_eval_fn=_make_bridge_fn(bridge),
    )
    # a=1 matched twice; a=5 matched zero times -> in rejects
    assert sorted(result["a"]) == [1, 1]
    assert rejects is not None
    assert list(rejects["a"]) == [5]


# ===== Task 4.6: RELOAD strategy =====

def test_reload_per_row_matches_uniquely():
    """RELOAD: lookup re-matched per main row using simple-equality keys."""
    joined = pd.DataFrame({"id": [1, 2], "region": ["WEST", "EAST"]})
    lookup = pd.DataFrame({
        "region": ["WEST", "WEST", "EAST"],
        "label": ["w1", "w2", "e1"],
    })
    lk = LookupCfg(
        name="row2",
        join_keys=[JoinKeyCfg("region", "{{java}}row1.region", "str")],
        join_mode="LEFT_OUTER_JOIN",
        lookup_mode="RELOAD_AT_EACH_ROW",
        matching_mode="UNIQUE_MATCH",
    )
    from src.v1.engine.components.transform.map.map_joins import (
        join_reload_per_row,
    )
    result, rejects = join_reload_per_row(
        joined, lookup, lk, bridge_eval_fn=None,
    )
    # UNIQUE_MATCH keeps the last; so row 1 (WEST) -> w2, row 2 (EAST) -> e1
    assert list(result["id"]) == [1, 2]
    assert list(result["row2.label"]) == ["w2", "e1"]
    assert rejects is None


def test_reload_per_row_inner_join_unmatched_to_rejects():
    """RELOAD + INNER_JOIN: unmatched main rows go to rejects."""
    joined = pd.DataFrame({"id": [1, 2], "region": ["WEST", "SOUTH"]})
    lookup = pd.DataFrame({"region": ["WEST"], "label": ["w1"]})
    lk = LookupCfg(
        name="row2",
        join_keys=[JoinKeyCfg("region", "{{java}}row1.region", "str")],
        join_mode="INNER_JOIN",
        lookup_mode="RELOAD_AT_EACH_ROW",
        matching_mode="UNIQUE_MATCH",
    )
    from src.v1.engine.components.transform.map.map_joins import (
        join_reload_per_row,
    )
    result, rejects = join_reload_per_row(joined, lookup, lk, bridge_eval_fn=None)
    assert list(result["id"]) == [1]
    assert rejects is not None
    assert list(rejects["id"]) == [2]


def test_reload_per_row_left_outer_unmatched_padded_with_nan():
    """RELOAD + LEFT_OUTER: unmatched main rows pass through with NaN lookup cols."""
    import numpy as np
    joined = pd.DataFrame({"id": [1, 2], "region": ["WEST", "SOUTH"]})
    lookup = pd.DataFrame({"region": ["WEST"], "label": ["w1"]})
    lk = LookupCfg(
        name="row2",
        join_keys=[JoinKeyCfg("region", "{{java}}row1.region", "str")],
        join_mode="LEFT_OUTER_JOIN",
        lookup_mode="RELOAD_AT_EACH_ROW",
        matching_mode="UNIQUE_MATCH",
    )
    from src.v1.engine.components.transform.map.map_joins import (
        join_reload_per_row,
    )
    result, rejects = join_reload_per_row(joined, lookup, lk, bridge_eval_fn=None)
    assert list(result["id"]) == [1, 2]
    assert result.iloc[0]["row2.label"] == "w1"
    assert pd.isna(result.iloc[1]["row2.label"])
    assert rejects is None


# ===== Task 4.7: apply_filter =====

def test_apply_filter_no_filter_returns_df_unchanged():
    df = pd.DataFrame({"a": [1, 2, 3]})
    from src.v1.engine.components.transform.map.map_joins import apply_filter
    result = apply_filter(df, filter_expr="", bridge_eval_fn=None,
                          main_name="row1", lookup_names=[])
    assert result is df  # same object, not a copy


def test_apply_filter_empty_df_returns_unchanged():
    df = pd.DataFrame({"a": []})
    from src.v1.engine.components.transform.map.map_joins import apply_filter
    bridge = MagicMock()
    result = apply_filter(
        df, filter_expr="{{java}}row1.a > 1",
        bridge_eval_fn=_make_bridge_fn(bridge),
        main_name="row1", lookup_names=[],
    )
    assert len(result) == 0
    bridge.execute_tmap_preprocessing.assert_not_called()


def test_apply_filter_with_filter_uses_bridge_mask():
    df = pd.DataFrame({"a": [1, 2, 3]})
    bridge = MagicMock()
    bridge.execute_tmap_preprocessing.return_value = {
        "__filter__": [True, False, True],
    }
    from src.v1.engine.components.transform.map.map_joins import apply_filter
    result = apply_filter(
        df, filter_expr="{{java}}row1.a != 2",
        bridge_eval_fn=_make_bridge_fn(bridge),
        main_name="row1", lookup_names=[],
    )
    assert list(result["a"]) == [1, 3]


def test_apply_filter_raises_when_filter_present_but_no_bridge_fn():
    df = pd.DataFrame({"a": [1, 2, 3]})
    from src.v1.engine.components.transform.map.map_joins import apply_filter
    with pytest.raises(RuntimeError, match="bridge_eval_fn"):
        apply_filter(df, filter_expr="{{java}}row1.a > 0",
                      bridge_eval_fn=None, main_name="row1", lookup_names=[])


# ===== coverage-fill (Task 11.1) =====

def test_simple_equality_all_null_keys_inner_join_rejects_main():
    """All main keys are null -> main_nonnull empty -> INNER_JOIN dumps
    main_null to rejects, output is empty (lines 155-158)."""
    joined = pd.DataFrame({"id": [1, 2], "key": [None, None]})
    lookup = pd.DataFrame({"key": ["A"], "label": ["alpha"]})
    result, rejects = join_simple_equality(
        joined, lookup, _lookup_simple(join_mode="INNER_JOIN")
    )
    assert result.empty
    assert rejects is not None
    assert list(rejects["id"]) == [1, 2]


def test_simple_equality_inner_join_combines_unmatched_and_null_keys_in_rejects():
    """Mixed: one main row has non-null key but no match; another has null
    key. INNER_JOIN should concatenate both into rejects (line 171)."""
    joined = pd.DataFrame({"id": [1, 2, 3], "key": ["A", None, "Z"]})
    lookup = pd.DataFrame({"key": ["A"], "label": ["alpha"]})
    result, rejects = join_simple_equality(
        joined, lookup, _lookup_simple(join_mode="INNER_JOIN")
    )
    assert list(result["id"]) == [1]
    assert rejects is not None
    assert sorted(rejects["id"].tolist()) == [2, 3]


def test_simple_equality_drops_dup_cols():
    """If main has a column that collides with the lookup prefix (e.g. a
    'row2.label' column already exists), pd.merge suffixes the duplicate
    with __dup__ which is then dropped (line 186)."""
    joined = pd.DataFrame({
        "id": [1],
        "key": ["A"],
        "row2.label": ["preexisting"],
    })
    lookup = pd.DataFrame({"key": ["A"], "label": ["from_lookup"]})
    result, _ = join_simple_equality(joined, lookup, _lookup_simple())
    # The lookup-side dup col is dropped; main value is preserved
    assert "row2.label__dup__" not in result.columns
    assert list(result["row2.label"]) == ["preexisting"]


def test_computed_equality_all_null_keys_inner_join_rejects_main():
    """Computed: bridge returns None for all key evals -> main_nonnull empty
    -> INNER_JOIN dumps main_null to rejects (lines 253-256)."""
    joined = pd.DataFrame({"id": [1, 2], "key": ["a", "b"]})
    lookup = pd.DataFrame({"key": ["A"], "label": ["alpha"]})
    lk = LookupCfg(
        name="row2",
        join_keys=[JoinKeyCfg("key", "{{java}}routines.StringHandling.UPCASE(row1.key)", "str")],
        join_mode="INNER_JOIN",
    )
    bridge = MagicMock()
    bridge.execute_tmap_preprocessing.return_value = {
        "__jk_main_0__": [None, None],
    }
    from src.v1.engine.components.transform.map.map_joins import (
        join_computed_equality,
    )
    result, rejects = join_computed_equality(
        joined, lookup, lk, main_name="row1",
        prior_lookups=[], bridge_eval_fn=_make_bridge_fn(bridge),
    )
    assert result.empty
    assert rejects is not None
    assert list(rejects["id"]) == [1, 2]


def test_computed_equality_left_outer_with_null_keys_passes_through():
    """Computed + LEFT_OUTER: null-key main rows pass through with NaN
    lookup cols (line 278)."""
    joined = pd.DataFrame({"id": [1, 2], "key": ["a", None]})
    lookup = pd.DataFrame({"key": ["A"], "label": ["alpha"]})
    lk = LookupCfg(
        name="row2",
        join_keys=[JoinKeyCfg("key", "{{java}}routines.StringHandling.UPCASE(row1.key)", "str")],
        join_mode="LEFT_OUTER_JOIN",
    )
    bridge = MagicMock()
    bridge.execute_tmap_preprocessing.return_value = {
        "__jk_main_0__": ["A", None],
    }
    from src.v1.engine.components.transform.map.map_joins import (
        join_computed_equality,
    )
    result, rejects = join_computed_equality(
        joined, lookup, lk, main_name="row1",
        prior_lookups=[], bridge_eval_fn=_make_bridge_fn(bridge),
    )
    assert sorted(result["id"].tolist()) == [1, 2]
    assert rejects is None


def test_apply_matching_mode_no_matching_keys_returns_unchanged():
    """If none of the requested key_cols exist in the lookup, return as-is."""
    from src.v1.engine.components.transform.map.map_joins import (
        _apply_matching_mode,
    )
    df = pd.DataFrame({"x": [1, 2]})
    out = _apply_matching_mode(df, key_cols=["missing"], mode="UNIQUE_MATCH")
    assert out is df  # same object, no-op


def test_prefilter_null_keys_empty_df():
    """Empty df: returns (empty copy, empty frame)."""
    from src.v1.engine.components.transform.map.map_joins import (
        _prefilter_null_keys,
    )
    df = pd.DataFrame({"k": []})
    nonnull, null = _prefilter_null_keys(df, ["k"])
    assert nonnull.empty
    assert null.empty


def test_prefilter_null_keys_no_matching_cols():
    """No requested key_cols exist in df: returns (copy, empty)."""
    from src.v1.engine.components.transform.map.map_joins import (
        _prefilter_null_keys,
    )
    df = pd.DataFrame({"a": [1, 2]})
    nonnull, null = _prefilter_null_keys(df, ["missing"])
    assert list(nonnull["a"]) == [1, 2]
    assert null.empty


def test_filter_as_match_empty_lookup_left_outer():
    """Empty lookup_df + LEFT_OUTER: Talend parity -- main rows pass through
    with NaN lookup cols (prefixed). rejects=None.
    """
    from src.v1.engine.components.transform.map.map_joins import (
        join_filter_as_match,
    )
    joined = pd.DataFrame({"a": [1, 2]})
    lookup = pd.DataFrame({"b": []})
    lk = LookupCfg(name="row2", join_keys=[], join_mode="LEFT_OUTER_JOIN")
    result, rejects = join_filter_as_match(
        joined, lookup, lk, main_name="row1",
        prior_lookups=[], bridge_eval_fn=None,
    )
    assert list(result["a"]) == [1, 2]
    assert "row2.b" in result.columns
    assert result["row2.b"].isna().all()
    assert rejects is None


def test_filter_as_match_empty_lookup_inner_join_dumps_main_to_rejects():
    """Empty lookup_df + INNER_JOIN: rejects = joined_df (line 397)."""
    from src.v1.engine.components.transform.map.map_joins import (
        join_filter_as_match,
    )
    joined = pd.DataFrame({"a": [1, 2]})
    lookup = pd.DataFrame({"b": []})
    lk = LookupCfg(name="row2", join_keys=[], join_mode="INNER_JOIN")
    result, rejects = join_filter_as_match(
        joined, lookup, lk, main_name="row1",
        prior_lookups=[], bridge_eval_fn=None,
    )
    assert result.empty
    assert rejects is not None
    assert list(rejects["a"]) == [1, 2]


def test_filter_as_match_no_bridge_fn_with_filter_raises():
    """FILTER_AS_MATCH with a filter but no bridge_eval_fn -> RuntimeError
    (line 423)."""
    from src.v1.engine.components.transform.map.map_joins import (
        join_filter_as_match,
    )
    joined = pd.DataFrame({"a": [1, 2]})
    lookup = pd.DataFrame({"b": [10]})
    lk = LookupCfg(
        name="row2", join_keys=[],
        activate_filter=True, filter="{{java}}row1.a < row2.b",
        join_mode="LEFT_OUTER_JOIN",
    )
    with pytest.raises(RuntimeError, match="bridge_eval_fn"):
        join_filter_as_match(
            joined, lookup, lk, main_name="row1",
            prior_lookups=[], bridge_eval_fn=None,
        )


def test_filter_as_match_inner_join_no_matches_at_all():
    """INNER_JOIN where ALL filter results are False: merged is empty, every
    main row goes to rejects (line 456)."""
    joined = pd.DataFrame({"a": [1, 2]})
    lookup = pd.DataFrame({"b": [10]})
    lk = LookupCfg(
        name="row2", join_keys=[],
        activate_filter=True, filter="{{java}}row1.a > row2.b",
        join_mode="INNER_JOIN",
    )
    bridge = MagicMock()
    bridge.execute_tmap_preprocessing.return_value = {
        "__filter__": [False, False],
    }
    from src.v1.engine.components.transform.map.map_joins import (
        join_filter_as_match,
    )
    result, rejects = join_filter_as_match(
        joined, lookup, lk, main_name="row1",
        prior_lookups=[], bridge_eval_fn=_make_bridge_fn(bridge),
    )
    assert result.empty
    assert rejects is not None
    assert sorted(rejects["a"].tolist()) == [1, 2]


def test_reload_per_row_empty_lookup_inner_join_rejects_main():
    """RELOAD: lookup is empty -> for each main row, INNER_JOIN sends it to
    rejects (lines 496-497)."""
    from src.v1.engine.components.transform.map.map_joins import (
        join_reload_per_row,
    )
    joined = pd.DataFrame({"id": [1, 2], "region": ["WEST", "EAST"]})
    lookup = pd.DataFrame({"region": [], "label": []})
    lk = LookupCfg(
        name="row2",
        join_keys=[JoinKeyCfg("region", "{{java}}row1.region", "str")],
        join_mode="INNER_JOIN",
        lookup_mode="RELOAD_AT_EACH_ROW",
    )
    result, rejects = join_reload_per_row(joined, lookup, lk, bridge_eval_fn=None)
    assert result.empty
    assert rejects is not None
    assert sorted(rejects["id"].tolist()) == [1, 2]


def test_reload_per_row_empty_lookup_left_outer_passes_main_through():
    """RELOAD: lookup empty + LEFT_OUTER -> main rows pass through
    unchanged (lines 498-500)."""
    from src.v1.engine.components.transform.map.map_joins import (
        join_reload_per_row,
    )
    joined = pd.DataFrame({"id": [1, 2], "region": ["WEST", "EAST"]})
    lookup = pd.DataFrame({"region": [], "label": []})
    lk = LookupCfg(
        name="row2",
        join_keys=[JoinKeyCfg("region", "{{java}}row1.region", "str")],
        join_mode="LEFT_OUTER_JOIN",
        lookup_mode="RELOAD_AT_EACH_ROW",
    )
    result, rejects = join_reload_per_row(joined, lookup, lk, bridge_eval_fn=None)
    assert sorted(result["id"].tolist()) == [1, 2]
    assert rejects is None


def test_reload_per_row_non_simple_key_expression_treats_main_val_as_none():
    """RELOAD: if a join key expression is not a simple table.col form, the
    main_val falls back to None and no row will match (line 519)."""
    from src.v1.engine.components.transform.map.map_joins import (
        join_reload_per_row,
    )
    joined = pd.DataFrame({"id": [1], "region": ["WEST"]})
    lookup = pd.DataFrame({"region": ["WEST"], "label": ["w1"]})
    lk = LookupCfg(
        name="row2",
        # Complex expression: regex won't match -> main_val = None
        join_keys=[JoinKeyCfg(
            "region",
            "{{java}}routines.StringHandling.UPCASE(row1.region)",
            "str",
        )],
        join_mode="LEFT_OUTER_JOIN",
        lookup_mode="RELOAD_AT_EACH_ROW",
    )
    result, _ = join_reload_per_row(joined, lookup, lk, bridge_eval_fn=None)
    # Main pass-through with NaN lookup col since main_val was None
    assert list(result["id"]) == [1]
    assert pd.isna(result.iloc[0]["row2.label"])


def test_simple_equality_join_key_falls_back_when_column_missing():
    """If a join key expression references a column not present in joined_df
    (neither prefixed nor bare), the code falls back to prefixed form
    (line 140). The subsequent pd.merge will then error out helpfully --
    we just confirm the path is reached."""
    joined = pd.DataFrame({"id": [1]})  # no 'key' column at all
    lookup = pd.DataFrame({"key": ["A"], "label": ["alpha"]})
    lk = _lookup_simple()  # join_key expression references row1.key
    # pd.merge will raise KeyError because 'row1.key' isn't in joined_df
    with pytest.raises((KeyError, Exception)):
        join_simple_equality(joined, lookup, lk)


# ===== CONSTANT_KEY: _is_known_input_col_ref =====

from src.v1.engine.components.transform.map.map_joins import (
    _is_known_input_col_ref,
)


def test_known_input_col_ref_main_table():
    assert _is_known_input_col_ref("row1.col", "row1", []) is True


def test_known_input_col_ref_main_table_with_marker():
    assert _is_known_input_col_ref("{{java}}row1.col", "row1", []) is True


def test_known_input_col_ref_prior_lookup():
    assert _is_known_input_col_ref("row3.col", "row1", ["row3"]) is True


def test_known_input_col_ref_unknown_table_returns_false():
    # context is not an input flow name -- this is the bug-trigger case
    assert _is_known_input_col_ref("{{java}}context.SOURCE", "row1", []) is False


def test_known_input_col_ref_non_dotted_expression_returns_false():
    # Function call or literal: shape doesn't match table.col
    assert _is_known_input_col_ref("{{java}}routines.X.foo(row1.k)", "row1", []) is False


def test_known_input_col_ref_bare_identifier_returns_false():
    assert _is_known_input_col_ref("just_an_id", "row1", []) is False


def test_known_input_col_ref_empty_string_returns_false():
    assert _is_known_input_col_ref("", "row1", []) is False


# ===== CONSTANT_KEY: _is_main_row_independent =====

from src.v1.engine.components.transform.map.map_joins import (
    _is_main_row_independent,
)


def test_main_row_independent_pure_context_var():
    assert _is_main_row_independent("{{java}}context.SOURCE", "row1", []) is True


def test_main_row_independent_bare_context_var():
    assert _is_main_row_independent("context.SOURCE", "row1", []) is True


def test_main_row_independent_global_map():
    assert _is_main_row_independent("{{java}}globalMap.X", "row1", []) is True


def test_main_row_independent_literal_string():
    assert _is_main_row_independent('{{java}}"hardcoded"', "row1", []) is True


def test_main_row_independent_arithmetic_constant():
    assert _is_main_row_independent("{{java}}5 + 5", "row1", []) is True


def test_main_row_independent_routine_static_field():
    assert _is_main_row_independent("{{java}}MyRoutine.SOME_CONST", "row1", []) is True


def test_main_row_independent_with_main_row_ref_false():
    assert _is_main_row_independent("{{java}}row1.col", "row1", []) is False


def test_main_row_independent_with_prior_lookup_ref_false():
    assert _is_main_row_independent("{{java}}row3.col", "row1", ["row3"]) is False


def test_main_row_independent_with_var_ref_false():
    # Var.x is the tMap variable table -- treat as row-dependent
    assert _is_main_row_independent("{{java}}Var.calculated", "row1", []) is False


def test_main_row_independent_row_ref_inside_quoted_string_true():
    # "row1.foo" is a string literal, not a row ref -- expression is constant
    expr = '{{java}}"row1.foo says hi"'
    assert _is_main_row_independent(expr, "row1", []) is True


# ===== Option C: empty-lookup pass-through per join strategy =====
#
# When the orchestrator no longer early-skips empty lookups, every join
# strategy must produce Talend-correct results on an empty lookup_df:
#   - LEFT_OUTER_JOIN: main rows pass through with NaN prefixed lookup cols
#   - INNER_JOIN: every main row goes to rejects
# (FILTER_AS_MATCH and RELOAD already have dedicated tests above.)


def test_simple_empty_lookup_left_outer_passes_main_through():
    """SIMPLE + empty lookup + LEFT_OUTER: 7 main rows -> 7 result rows
    with NaN row2.<col>. Regression for the silent-empty-output bug.
    """
    joined = pd.DataFrame({"newColumn": [1, 2, 3, 4, 5, 6, 7]})
    lookup = pd.DataFrame({"newColumn": []})  # empty lookup
    lk = LookupCfg(
        name="row2",
        join_keys=[JoinKeyCfg("newColumn", "{{java}}row1.newColumn", "int")],
        join_mode="LEFT_OUTER_JOIN",
    )
    result, rejects = join_simple_equality(joined, lookup, lk)
    assert list(result["newColumn"]) == [1, 2, 3, 4, 5, 6, 7]
    assert "row2.newColumn" in result.columns
    assert result["row2.newColumn"].isna().all()
    assert rejects is None


def test_simple_empty_lookup_inner_join_rejects_all_main():
    """SIMPLE + empty lookup + INNER: all main rows -> rejects."""
    joined = pd.DataFrame({"newColumn": [1, 2, 3]})
    lookup = pd.DataFrame({"newColumn": []})
    lk = LookupCfg(
        name="row2",
        join_keys=[JoinKeyCfg("newColumn", "{{java}}row1.newColumn", "int")],
        join_mode="INNER_JOIN",
    )
    result, rejects = join_simple_equality(joined, lookup, lk)
    assert result.empty
    assert rejects is not None
    assert sorted(rejects["newColumn"].tolist()) == [1, 2, 3]


def test_computed_empty_lookup_left_outer_passes_main_through():
    """COMPUTED + empty lookup + LEFT_OUTER: main rows pass through with
    NaN row2.<col>; temp __jk_main_<i>__ col dropped from result.
    """
    joined = pd.DataFrame({"id": [1, 2], "key": ["a", "b"]})
    lookup = pd.DataFrame({"upper_key": [], "label": []})
    lk = LookupCfg(
        name="row2",
        join_keys=[JoinKeyCfg(
            "upper_key",
            "{{java}}row1.key.toUpperCase()",
            "str",
        )],
        join_mode="LEFT_OUTER_JOIN",
    )
    bridge = MagicMock()
    bridge.execute_tmap_preprocessing.return_value = {
        "__jk_main_0__": ["A", "B"],
    }
    from src.v1.engine.components.transform.map.map_joins import (
        join_computed_equality,
    )
    result, rejects = join_computed_equality(
        joined, lookup, lk, main_name="row1",
        prior_lookups=[], bridge_eval_fn=_make_bridge_fn(bridge),
    )
    assert "__jk_main_0__" not in result.columns
    assert list(result["id"]) == [1, 2]
    assert "row2.label" in result.columns
    assert result["row2.label"].isna().all()
    assert rejects is None


def test_computed_empty_lookup_inner_join_rejects_all_main():
    """COMPUTED + empty lookup + INNER: all main rows -> rejects;
    temp join-key column dropped from rejects too.
    """
    joined = pd.DataFrame({"id": [1, 2], "key": ["a", "b"]})
    lookup = pd.DataFrame({"upper_key": [], "label": []})
    lk = LookupCfg(
        name="row2",
        join_keys=[JoinKeyCfg(
            "upper_key",
            "{{java}}row1.key.toUpperCase()",
            "str",
        )],
        join_mode="INNER_JOIN",
    )
    bridge = MagicMock()
    bridge.execute_tmap_preprocessing.return_value = {
        "__jk_main_0__": ["A", "B"],
    }
    from src.v1.engine.components.transform.map.map_joins import (
        join_computed_equality,
    )
    result, rejects = join_computed_equality(
        joined, lookup, lk, main_name="row1",
        prior_lookups=[], bridge_eval_fn=_make_bridge_fn(bridge),
    )
    assert result.empty
    assert rejects is not None
    assert sorted(rejects["id"].tolist()) == [1, 2]
    assert "__jk_main_0__" not in rejects.columns


def test_constant_key_empty_lookup_left_outer_passes_main_through():
    """CONSTANT_KEY + empty lookup + LEFT_OUTER: main rows pass through
    with NaN row2.<col>.
    """
    from src.v1.engine.components.transform.map.map_joins import (
        join_constant_key,
    )
    joined = pd.DataFrame({"id": [1, 2]})
    lookup = pd.DataFrame({"name": [], "info": []})
    lk = LookupCfg(
        name="row2",
        join_keys=[JoinKeyCfg("name", "{{java}}context.SOURCE", "str")],
        join_mode="LEFT_OUTER_JOIN",
    )

    def fake_eval(exprs):
        return {k: "anything" for k in exprs}

    result, rejects = join_constant_key(
        joined, lookup, lk, main_name="row1",
        prior_lookups=[], constant_eval_fn=fake_eval,
    )
    assert list(result["id"]) == [1, 2]
    assert "row2.name" in result.columns
    assert result["row2.name"].isna().all()
    assert rejects is None


def test_constant_key_empty_lookup_inner_join_rejects_all_main():
    """CONSTANT_KEY + empty lookup + INNER: all main rows -> rejects."""
    from src.v1.engine.components.transform.map.map_joins import (
        join_constant_key,
    )
    joined = pd.DataFrame({"id": [1, 2]})
    lookup = pd.DataFrame({"name": [], "info": []})
    lk = LookupCfg(
        name="row2",
        join_keys=[JoinKeyCfg("name", "{{java}}context.SOURCE", "str")],
        join_mode="INNER_JOIN",
    )

    def fake_eval(exprs):
        return {k: "anything" for k in exprs}

    result, rejects = join_constant_key(
        joined, lookup, lk, main_name="row1",
        prior_lookups=[], constant_eval_fn=fake_eval,
    )
    assert result.empty
    assert rejects is not None
    assert sorted(rejects["id"].tolist()) == [1, 2]


def test_main_row_independent_mixed_main_ref_outside_quotes_false():
    # row1.col reference outside string literal still triggers row-dependence
    expr = '{{java}}row1.col + "row1.label"'
    assert _is_main_row_independent(expr, "row1", []) is False


def test_main_row_independent_empty_expression_true():
    # Trivially row-independent; defensive return
    assert _is_main_row_independent("", "row1", []) is True


# ===== CONSTANT_KEY: join_constant_key =====

import pandas as pd
from src.v1.engine.components.transform.map.map_joins import (
    join_constant_key,
)
from src.v1.engine.exceptions import ComponentExecutionError


def _ck_lkup(name="row8", lookup_column="name", expression="{{java}}context.SOURCE",
             matching_mode="FIRST_MATCH", join_mode="LEFT_OUTER_JOIN",
             extra_keys=()):
    keys = [JoinKeyCfg(lookup_column, expression, "str")]
    keys.extend(extra_keys)
    return LookupCfg(
        name=name, join_keys=keys, matching_mode=matching_mode,
        join_mode=join_mode, lookup_mode="LOAD_ONCE",
    )


def test_join_constant_key_left_outer_match_broadcast():
    joined = pd.DataFrame({"id": [1, 2, 3], "desc": ["a", "b", "c"]})
    lookup = pd.DataFrame({
        "name": ["alpha", "beta", "gamma"],
        "info": ["A", "B", "G"],
    })
    lk = _ck_lkup()

    def constant_eval(exprs):
        return {k: "beta" for k in exprs}

    merged, rejects = join_constant_key(
        joined, lookup, lk, "row1", [], constant_eval,
    )

    assert rejects is None
    assert len(merged) == 3
    assert list(merged["row8.name"]) == ["beta", "beta", "beta"]
    assert list(merged["row8.info"]) == ["B", "B", "B"]


def test_join_constant_key_left_outer_no_match_keeps_main_with_nulls():
    joined = pd.DataFrame({"id": [1, 2]})
    lookup = pd.DataFrame({"name": ["alpha"], "info": ["A"]})
    lk = _ck_lkup()

    def constant_eval(exprs):
        return {k: "no_such_value" for k in exprs}

    merged, rejects = join_constant_key(
        joined, lookup, lk, "row1", [], constant_eval,
    )

    assert rejects is None
    assert len(merged) == 2
    assert merged["row8.name"].isna().all()
    assert merged["row8.info"].isna().all()


def test_join_constant_key_inner_no_match_rejects_all_main():
    joined = pd.DataFrame({"id": [1, 2]})
    lookup = pd.DataFrame({"name": ["alpha"], "info": ["A"]})
    lk = _ck_lkup(join_mode="INNER_JOIN")

    def constant_eval(exprs):
        return {k: "no_such_value" for k in exprs}

    merged, rejects = join_constant_key(
        joined, lookup, lk, "row1", [], constant_eval,
    )

    assert merged.empty
    assert rejects is not None
    assert len(rejects) == 2
    assert list(rejects["id"]) == [1, 2]


def test_join_constant_key_first_match_dedups_lookup():
    joined = pd.DataFrame({"id": [1]})
    lookup = pd.DataFrame({
        "name": ["beta", "beta", "beta"],
        "info": ["first", "second", "third"],
    })
    lk = _ck_lkup(matching_mode="FIRST_MATCH")

    def constant_eval(exprs):
        return {k: "beta" for k in exprs}

    merged, _ = join_constant_key(
        joined, lookup, lk, "row1", [], constant_eval,
    )

    assert len(merged) == 1
    assert merged["row8.info"].iloc[0] == "first"


def test_join_constant_key_all_matches_cross_product():
    joined = pd.DataFrame({"id": [1, 2]})
    lookup = pd.DataFrame({
        "name": ["beta", "beta", "alpha"],
        "info": ["b1", "b2", "a"],
    })
    lk = _ck_lkup(matching_mode="ALL_MATCHES")

    def constant_eval(exprs):
        return {k: "beta" for k in exprs}

    merged, _ = join_constant_key(
        joined, lookup, lk, "row1", [], constant_eval,
    )

    # 2 main rows x 2 matching lookup rows = 4 rows
    assert len(merged) == 4
    assert set(merged["row8.info"]) == {"b1", "b2"}


def test_join_constant_key_multi_key_and_filter():
    joined = pd.DataFrame({"id": [1]})
    lookup = pd.DataFrame({
        "code": ["X", "X", "Y"],
        "name": ["beta", "alpha", "beta"],
        "info": ["match", "noco", "noname"],
    })
    lk = _ck_lkup(extra_keys=[JoinKeyCfg("code", "{{java}}context.CODE", "str")])

    def constant_eval(exprs):
        # match name=beta AND code=X
        results = {}
        for k, expr in exprs.items():
            if "SOURCE" in expr:
                results[k] = "beta"
            elif "CODE" in expr:
                results[k] = "X"
        return results

    merged, _ = join_constant_key(
        joined, lookup, lk, "row1", [], constant_eval,
    )

    assert len(merged) == 1
    assert merged["row8.info"].iloc[0] == "match"


def test_join_constant_key_null_eval_short_circuits_to_no_match():
    joined = pd.DataFrame({"id": [1, 2]})
    lookup = pd.DataFrame({"name": ["alpha"], "info": ["A"]})
    lk = _ck_lkup(join_mode="LEFT_OUTER_JOIN")

    def constant_eval(exprs):
        return {k: None for k in exprs}

    merged, rejects = join_constant_key(
        joined, lookup, lk, "row1", [], constant_eval,
    )

    assert rejects is None
    assert len(merged) == 2
    assert merged["row8.info"].isna().all()


def test_join_constant_key_bridge_error_raises():
    joined = pd.DataFrame({"id": [1]})
    lookup = pd.DataFrame({"name": ["alpha"], "info": ["A"]})
    lk = _ck_lkup()

    def constant_eval(exprs):
        return {k: "{{ERROR}}NullPointerException in context resolve" for k in exprs}

    try:
        join_constant_key(joined, lookup, lk, "row1", [], constant_eval)
    except ComponentExecutionError as e:
        assert "context resolve" in str(e) or "ERROR" in str(e)
    else:
        raise AssertionError("expected ComponentExecutionError")


def test_join_constant_key_size_guard_warns_at_10m(monkeypatch, caplog):
    # 1M main rows x 11 matching lookup rows -> 11M predicted; should WARN
    import logging
    joined = pd.DataFrame({"id": range(1_000_000)})
    lookup = pd.DataFrame({
        "name": ["beta"] * 11, "info": [f"i{i}" for i in range(11)],
    })
    lk = _ck_lkup(matching_mode="ALL_MATCHES")

    def constant_eval(exprs):
        return {k: "beta" for k in exprs}

    with caplog.at_level(logging.WARNING):
        merged, _ = join_constant_key(
            joined, lookup, lk, "row1", [], constant_eval,
        )

    assert any("Cross-product" in rec.message or "broadcast" in rec.message.lower()
               for rec in caplog.records)
    assert len(merged) == 11_000_000


def test_join_constant_key_size_guard_fails_at_100m():
    # 10M main rows x 11 matching = 110M predicted; should raise
    joined = pd.DataFrame({"id": range(10_000_000)})
    lookup = pd.DataFrame({
        "name": ["beta"] * 11, "info": [f"i{i}" for i in range(11)],
    })
    lk = _ck_lkup(matching_mode="ALL_MATCHES")

    def constant_eval(exprs):
        return {k: "beta" for k in exprs}

    try:
        join_constant_key(joined, lookup, lk, "row1", [], constant_eval)
    except ComponentExecutionError as e:
        assert "safety limit" in str(e).lower() or "100" in str(e)
    else:
        raise AssertionError("expected ComponentExecutionError")
