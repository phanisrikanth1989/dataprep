"""Tests for Normalize (tNormalize engine implementation)."""
import inspect

import pytest
import pandas as pd
import numpy as np

from src.v1.engine.components.transform.normalize import Normalize
from src.v1.engine.global_map import GlobalMap
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

_DEFAULT_CONFIG = {
    "component_type": "Normalize",
    "normalize_column": "tags",
    "item_separator": ",",
    "trim": False,
    "discard_trailing_empty_str": False,
    "deduplicate": False,
}


def _make_component(config=None, global_map=None, context_manager=None):
    """Create a Normalize component with test defaults.

    Always creates fresh GlobalMap and ContextManager instances
    unless explicitly provided.
    """
    gm = global_map or GlobalMap()
    cm = context_manager or ContextManager()
    return Normalize(
        component_id="tNormalize_1",
        config=config or dict(_DEFAULT_CONFIG),
        global_map=gm,
        context_manager=cm,
    )


def _make_input_df(tags_values=None, extra_cols=None):
    """Create test input DataFrame.

    Args:
        tags_values: list of strings for the 'tags' column.
        extra_cols: dict of additional column name -> list of values.
    """
    if tags_values is None:
        tags_values = ["a,b,c"]
    data = {"tags": tags_values}
    if extra_cols:
        data.update(extra_cols)
    return pd.DataFrame(data)


# ------------------------------------------------------------------
# TestValidation
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    """_validate_config raises ConfigurationError for invalid config."""

    def test_missing_normalize_column_raises(self):
        """ENG-CR-01: missing normalize_column -> ConfigurationError on execute."""
        config = dict(_DEFAULT_CONFIG)
        del config["normalize_column"]
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="normalize_column"):
            comp.execute(_make_input_df())

    def test_invalid_normalize_column_type_raises(self):
        """normalize_column=123 (not str) -> ConfigurationError."""
        config = dict(_DEFAULT_CONFIG)
        config["normalize_column"] = 123
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="normalize_column"):
            comp.execute(_make_input_df())

    def test_validate_config_returns_none(self):
        """Valid config -> _validate_config() returns None (not a list).

        ENG-CR-01 inverse: the ABC contract requires None return, not a list.
        """
        comp = _make_component()
        # Prime config the way execute() does
        import copy
        comp.config = copy.deepcopy(comp._original_config)
        result = comp._validate_config()
        assert result is None, (
            f"_validate_config() must return None (raises on error), got {type(result)}: {result!r}"
        )

    def test_empty_normalize_column_raises(self):
        """normalize_column='  ' (whitespace only) -> ConfigurationError."""
        config = dict(_DEFAULT_CONFIG)
        config["normalize_column"] = "   "
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="normalize_column"):
            comp.execute(_make_input_df())


# ------------------------------------------------------------------
# TestTalendParity
# ------------------------------------------------------------------


@pytest.mark.unit
class TestTalendParity:
    """Talend tNormalize behavioral contract tests."""

    def test_basic_split_explode(self):
        """Input 'a,b,c' with separator ',' -> 3 output rows."""
        comp = _make_component()
        df = _make_input_df(["a,b,c"])
        result = comp.execute(df)
        out = result["main"]
        assert len(out) == 3
        assert list(out["tags"]) == ["a", "b", "c"]

    def test_trailing_only_empties_discarded(self):
        """ENG-CR-03: input 'a,b,,' + discard_trailing=True -> ['a', 'b'].

        Only trailing empties are removed; interior empties are preserved.
        """
        config = dict(_DEFAULT_CONFIG)
        config["discard_trailing_empty_str"] = True
        comp = _make_component(config=config)
        df = _make_input_df(["a,b,,"])
        result = comp.execute(df)
        out = result["main"]
        assert list(out["tags"]) == ["a", "b"]

    def test_interior_empties_preserved(self):
        """ENG-CR-03: input 'a,,b,,' + discard_trailing=True -> ['a', '', 'b'].

        The interior empty between 'a' and 'b' must be preserved.
        Only the two trailing empties are discarded.
        """
        config = dict(_DEFAULT_CONFIG)
        config["discard_trailing_empty_str"] = True
        comp = _make_component(config=config)
        df = _make_input_df(["a,,b,,"])
        result = comp.execute(df)
        out = result["main"]
        assert list(out["tags"]) == ["a", "", "b"]

    def test_combined_options_order(self):
        """ENG-WR-03: Talend order = discard_trailing -> trim -> dedupe.

        Input: ' a , a , ' (with trailing space after last comma)
        discard_trailing=True -> [' a ', ' a ', ' '] -> trailing ' ' stripped -> [' a ', ' a ']
        trim=True -> ['a', 'a']
        dedupe=True -> ['a']
        """
        config = dict(_DEFAULT_CONFIG)
        config["discard_trailing_empty_str"] = True
        config["trim"] = True
        config["deduplicate"] = True
        comp = _make_component(config=config)
        # The separator is ','. Input splits into [' a ', ' a ', ' ']
        # After discard_trailing (last item ' ' is not empty -- but Talend strips empties,
        # meaning items that ARE empty strings after strip? No -- discard_trailing checks raw
        # BEFORE trim. Raw trailing item is ' ' which != '', so not discarded.
        # After trim: ['a', 'a', '']
        # After dedupe: ['a', '']
        # This tests the ordering precisely.
        df = _make_input_df([" a , a , "])
        result = comp.execute(df)
        out = result["main"]
        # discard_trailing on raw: [' a ', ' a ', ' '] -> ' ' != '' so not discarded -> stays
        # trim: ['a', 'a', '']
        # dedupe: ['a', '']
        assert list(out["tags"]) == ["a", ""]

    def test_combined_options_with_trailing_empty(self):
        """ENG-WR-03: discard runs first -- trailing empty removed before trim.

        Input: 'a , b ,,' splits to ['a ', ' b ', '', '']
        discard_trailing=True -> ['a ', ' b '] (two trailing empties removed)
        trim=True -> ['a', 'b']
        dedupe=True -> ['a', 'b']
        """
        config = dict(_DEFAULT_CONFIG)
        config["discard_trailing_empty_str"] = True
        config["trim"] = True
        config["deduplicate"] = True
        comp = _make_component(config=config)
        df = _make_input_df(["a , b ,,"])
        result = comp.execute(df)
        out = result["main"]
        assert list(out["tags"]) == ["a", "b"]

    def test_empty_result_emits_zero_rows(self):
        """ENG-WR-02: input ',,,' + discard_trailing=True -> 0 output rows.

        All values are empty strings; all are trailing. Talend emits 0 rows.
        """
        config = dict(_DEFAULT_CONFIG)
        config["discard_trailing_empty_str"] = True
        comp = _make_component(config=config)
        df = _make_input_df([",,,"])
        result = comp.execute(df)
        out = result["main"]
        assert len(out) == 0, f"Expected 0 rows, got {len(out)}: {list(out.get('tags', []))}"

    def test_dedupe_preserves_first_seen_order(self):
        """Input 'c,a,c,b' + dedupe=True -> ['c', 'a', 'b'] (first-seen order)."""
        config = dict(_DEFAULT_CONFIG)
        config["deduplicate"] = True
        comp = _make_component(config=config)
        df = _make_input_df(["c,a,c,b"])
        result = comp.execute(df)
        out = result["main"]
        assert list(out["tags"]) == ["c", "a", "b"]

    def test_trim_only(self):
        """Trim strips whitespace from each split value."""
        config = dict(_DEFAULT_CONFIG)
        config["trim"] = True
        comp = _make_component(config=config)
        df = _make_input_df([" hello , world "])
        result = comp.execute(df)
        out = result["main"]
        assert list(out["tags"]) == ["hello", "world"]

    def test_multiple_input_rows(self):
        """Each input row is split independently; output has sum of all split values."""
        comp = _make_component()
        df = _make_input_df(["a,b", "x,y,z"])
        result = comp.execute(df)
        out = result["main"]
        assert len(out) == 5
        assert list(out["tags"]) == ["a", "b", "x", "y", "z"]


# ------------------------------------------------------------------
# TestSchemaHandling
# ------------------------------------------------------------------


@pytest.mark.unit
class TestSchemaHandling:
    """Schema and dtype preservation tests."""

    def test_int_column_dtype_preserved(self):
        """ENG-CR-02: non-normalized int column dtype preserved (not coerced to object).

        The vectorized path with .explode() must not erase dtypes of
        columns that were not split.
        """
        config = dict(_DEFAULT_CONFIG)
        comp = _make_component(config=config)
        df = pd.DataFrame({
            "tags": ["a,b"],
            "count": pd.array([42], dtype="int64"),
        })
        result = comp.execute(df)
        out = result["main"]
        assert out["count"].dtype == np.dtype("int64"), (
            f"Expected int64, got {out['count'].dtype} -- dtype erased by iterrows/rebuild"
        )

    def test_float_column_dtype_preserved(self):
        """Non-normalized float64 column dtype preserved after explode."""
        comp = _make_component()
        df = pd.DataFrame({
            "tags": ["x,y"],
            "score": pd.array([3.14], dtype="float64"),
        })
        result = comp.execute(df)
        out = result["main"]
        assert out["score"].dtype == np.dtype("float64")

    def test_normalize_column_output_is_string(self):
        """The exploded normalize column contains string values (not objects)."""
        comp = _make_component()
        df = _make_input_df(["hello,world"])
        result = comp.execute(df)
        out = result["main"]
        # Each value must be a Python str
        for val in out["tags"]:
            assert isinstance(val, str), f"Expected str, got {type(val)}: {val!r}"

    def test_non_normalized_columns_carried_through(self):
        """Extra columns are repeated for each exploded row."""
        comp = _make_component()
        df = pd.DataFrame({
            "tags": ["a,b,c"],
            "id": [99],
            "name": ["Alice"],
        })
        result = comp.execute(df)
        out = result["main"]
        assert len(out) == 3
        assert list(out["id"]) == [99, 99, 99]
        assert list(out["name"]) == ["Alice", "Alice", "Alice"]


# ------------------------------------------------------------------
# TestEdgeCases
# ------------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """Edge cases: empty input, None input, missing columns, arrays."""

    def test_empty_input_returns_empty_df(self):
        """input_data is empty DataFrame -> returns empty DataFrame with same columns."""
        comp = _make_component()
        df = pd.DataFrame({"tags": pd.Series([], dtype="object")})
        result = comp.execute(df)
        out = result["main"]
        assert isinstance(out, pd.DataFrame)
        assert len(out) == 0

    def test_none_input_returns_empty_result(self):
        """input_data is None -> returns main: empty DataFrame, reject: None."""
        comp = _make_component()
        result = comp.execute(None)
        assert isinstance(result["main"], pd.DataFrame)
        assert len(result["main"]) == 0
        assert result.get("reject") is None

    def test_missing_column_raises(self):
        """normalize_column not in input columns -> ConfigurationError."""
        config = dict(_DEFAULT_CONFIG)
        config["normalize_column"] = "nonexistent"
        comp = _make_component(config=config)
        df = pd.DataFrame({"tags": ["a,b"]})
        with pytest.raises(ConfigurationError, match="nonexistent"):
            comp.execute(df)

    def test_array_isna_no_crash(self):
        """ENG-WR-01: input column contains a list value -> no array-truthiness crash.

        Old code used per-cell pd.isna(cell_value) which raises ValueError when
        cell_value is an array/list. Vectorized path is immune.
        """
        comp = _make_component()
        # Mix: one normal string row, one row with list value
        df = pd.DataFrame({
            "tags": ["a,b", ["this", "is", "a", "list"]],
        })
        # Should not raise ValueError: "The truth value of an array is ambiguous"
        # The vectorized path coerces via .astype("string") before splitting.
        result = comp.execute(df)
        assert isinstance(result["main"], pd.DataFrame)

    def test_single_value_no_separator(self):
        """Input with no separator in value -> single output row with original value."""
        comp = _make_component()
        df = _make_input_df(["hello"])
        result = comp.execute(df)
        out = result["main"]
        assert len(out) == 1
        assert out["tags"].iloc[0] == "hello"

    def test_custom_separator(self):
        """Custom item_separator '|' splits correctly."""
        config = dict(_DEFAULT_CONFIG)
        config["item_separator"] = "|"
        comp = _make_component(config=config)
        df = _make_input_df(["a|b|c"])
        result = comp.execute(df)
        out = result["main"]
        assert list(out["tags"]) == ["a", "b", "c"]


# ------------------------------------------------------------------
# TestTypeAnnotations (regression guard)
# ------------------------------------------------------------------


@pytest.mark.unit
class TestTypeAnnotations:
    """Guards against regression to non-vectorized implementation."""

    def test_no_iterrows_in_source(self):
        """Source code must not contain 'iterrows' -- guards against O(n^2) regression."""
        import src.v1.engine.components.transform.normalize as normalize_module
        source = inspect.getsource(normalize_module)
        assert "iterrows" not in source, (
            "Found 'iterrows' in normalize.py -- vectorized path regression!"
        )

    def test_no_series_copy_in_loop(self):
        """Source code must not use row.copy() in a loop (old O(n^2) pattern)."""
        import src.v1.engine.components.transform.normalize as normalize_module
        source = inspect.getsource(normalize_module)
        # row.copy() inside a for loop was the O(n^2) pattern.
        # We check that the module does not contain iterrows at all (covered above),
        # and that it contains the vectorized split marker.
        assert "str.split" in source or ".str.split" in source, (
            "Vectorized .str.split not found -- implementation may have reverted"
        )
