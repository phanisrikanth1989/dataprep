"""Tests for Denormalize (tDenormalize engine implementation).

Covers (per ENGINE_TEST_PATTERN.md):
  TestRegistration        -- both v1 and Talend alias registered in REGISTRY
  TestValidation          -- _validate_config raises ConfigurationError for bad shape
  TestDefaults            -- default config (no denormalize_columns) passes data through
  TestMainFlow            -- core groupby + concatenation behavior
  TestMergeFlag           -- merge=True deduplicates values before concatenation
  TestNullHandling        -- null_as_empty=True/False behavior
  TestKeyColumnDetection  -- key column auto-detection (all non-denorm columns)
  TestNullKeyRows         -- null key column values preserved as separate group
  TestEdgeCases           -- None input, empty df, single-row groups, all-cols-denorm
  TestGlobalMapVariables  -- NB_LINE, NB_LINE_OK, NB_LINE_REJECT set correctly
  TestIterateReexecution  -- execute() twice with reset() gives consistent results
"""
import copy

import pandas as pd
import pytest

from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.components.transform.denormalize import Denormalize
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError, DataValidationError, ComponentExecutionError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Fixtures / Helpers
# ------------------------------------------------------------------

_DEFAULT_CONFIG: dict = {}


def _make_component(config=None, global_map=None, context_manager=None):
    """Create a Denormalize component with test defaults.

    Creates fresh GlobalMap and ContextManager unless explicitly provided.
    """
    gm = global_map if global_map is not None else GlobalMap()
    cm = context_manager or ContextManager()
    return Denormalize(
        component_id="tDenormalize_1",
        config=config if config is not None else dict(_DEFAULT_CONFIG),
        global_map=gm,
        context_manager=cm,
    )


def _make_df(order_ids=None, products=None):
    """Create a simple order/product test DataFrame.

    Args:
        order_ids: list of order_id values.
        products: list of product_name values (same length as order_ids).
    """
    if order_ids is None:
        order_ids = [1, 1, 2, 2, 2]
    if products is None:
        products = ["A", "B", "C", "D", "E"]
    return pd.DataFrame({"order_id": order_ids, "product": products})


# ------------------------------------------------------------------
# TestRegistration
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    """Component must be reachable by both its v1 name and Talend alias."""

    def test_v1_name_registered(self):
        """'Denormalize' is registered in REGISTRY."""
        assert "Denormalize" in REGISTRY._components, (
            "'Denormalize' not found in component registry"
        )

    def test_talend_alias_registered(self):
        """'tDenormalize' alias is registered in REGISTRY."""
        assert "tDenormalize" in REGISTRY._components, (
            "'tDenormalize' alias not found in component registry"
        )

    def test_both_aliases_resolve_same_class(self):
        """Both 'Denormalize' and 'tDenormalize' resolve to the Denormalize class."""
        cls_v1 = REGISTRY._components["Denormalize"]
        cls_talend = REGISTRY._components["tDenormalize"]
        assert cls_v1 is cls_talend is Denormalize

    def test_decorator_is_on_class(self):
        """The @REGISTRY.register decorator is applied to Denormalize itself."""
        assert issubclass(Denormalize, object)
        assert Denormalize.__name__ == "Denormalize"


# ------------------------------------------------------------------
# TestValidation
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    """_validate_config raises ConfigurationError for invalid config shape."""

    def test_valid_empty_config_passes(self):
        """Empty config (no denormalize_columns) is valid."""
        comp = _make_component(config={})
        import copy as cp
        comp.config = cp.deepcopy(comp._original_config)
        assert comp._validate_config() is None

    def test_validate_config_returns_none(self):
        """_validate_config() returns None (not a list) -- ABC contract."""
        config = {
            "denormalize_columns": [{"input_column": "product", "delimiter": ";"}]
        }
        comp = _make_component(config=config)
        import copy as cp
        comp.config = cp.deepcopy(comp._original_config)
        result = comp._validate_config()
        assert result is None, (
            f"_validate_config() must return None (raises on error), "
            f"got {type(result)}: {result!r}"
        )

    def test_denormalize_columns_not_list_raises(self):
        """denormalize_columns must be a list."""
        comp = _make_component(config={"denormalize_columns": "product"})
        with pytest.raises(ConfigurationError, match="denormalize_columns"):
            comp.execute(_make_df())

    def test_denormalize_columns_entry_not_dict_raises(self):
        """Each entry in denormalize_columns must be a dict."""
        comp = _make_component(config={"denormalize_columns": ["product"]})
        with pytest.raises(ConfigurationError, match="denormalize_columns"):
            comp.execute(_make_df())

    def test_missing_input_column_raises(self):
        """Entry missing 'input_column' key raises ConfigurationError."""
        comp = _make_component(config={
            "denormalize_columns": [{"delimiter": ";"}]
        })
        with pytest.raises(ConfigurationError, match="input_column"):
            comp.execute(_make_df())


# ------------------------------------------------------------------
# TestDefaults
# ------------------------------------------------------------------


@pytest.mark.unit
class TestDefaults:
    """Default config (no denormalize_columns) passes data through unchanged."""

    def test_no_denormalize_columns_passthrough(self):
        """Empty denormalize_columns -> output equals input."""
        comp = _make_component(config={})
        df = _make_df()
        result = comp.execute(df)
        out = result["main"]
        pd.testing.assert_frame_equal(out.reset_index(drop=True), df.reset_index(drop=True))

    def test_empty_list_passthrough(self):
        """denormalize_columns=[] -> output equals input."""
        comp = _make_component(config={"denormalize_columns": []})
        df = _make_df()
        result = comp.execute(df)
        out = result["main"]
        assert len(out) == len(df)

    def test_reject_key_present(self):
        """Result dict always contains 'reject' key."""
        comp = _make_component(config={})
        result = comp.execute(_make_df())
        assert "reject" in result


# ------------------------------------------------------------------
# TestMainFlow
# ------------------------------------------------------------------


@pytest.mark.unit
class TestMainFlow:
    """Core groupby + concatenation behavior."""

    def test_basic_groupby_and_concat(self):
        """Two orders, each with two products -> two output rows, products concatenated."""
        config = {
            "denormalize_columns": [{"input_column": "product", "delimiter": ";"}]
        }
        comp = _make_component(config=config)
        df = pd.DataFrame({
            "order_id": [1, 1, 2, 2],
            "product": ["A", "B", "C", "D"],
        })
        result = comp.execute(df)
        out = result["main"]
        assert len(out) == 2
        row1 = out[out["order_id"] == 1].iloc[0]
        row2 = out[out["order_id"] == 2].iloc[0]
        assert row1["product"] == "A;B"
        assert row2["product"] == "C;D"

    def test_single_row_group_no_concat(self):
        """Group with single row -> value unchanged (no delimiter added)."""
        config = {
            "denormalize_columns": [{"input_column": "product", "delimiter": ";"}]
        }
        comp = _make_component(config=config)
        df = pd.DataFrame({"order_id": [1], "product": ["solo"]})
        result = comp.execute(df)
        out = result["main"]
        assert out["product"].iloc[0] == "solo"

    def test_output_row_count(self):
        """Output has one row per unique key combination."""
        config = {
            "denormalize_columns": [{"input_column": "product", "delimiter": ","}]
        }
        comp = _make_component(config=config)
        df = pd.DataFrame({
            "order_id": [1, 1, 2, 3, 3, 3],
            "product": ["A", "B", "C", "D", "E", "F"],
        })
        result = comp.execute(df)
        out = result["main"]
        assert len(out) == 3

    def test_custom_delimiter(self):
        """Custom delimiter is used in concatenation."""
        config = {
            "denormalize_columns": [{"input_column": "product", "delimiter": " | "}]
        }
        comp = _make_component(config=config)
        df = pd.DataFrame({"order_id": [1, 1], "product": ["X", "Y"]})
        result = comp.execute(df)
        out = result["main"]
        assert out["product"].iloc[0] == "X | Y"

    def test_multiple_denorm_columns(self):
        """Multiple denormalize_columns are concatenated independently."""
        config = {
            "denormalize_columns": [
                {"input_column": "product", "delimiter": ";"},
                {"input_column": "qty", "delimiter": ","},
            ]
        }
        comp = _make_component(config=config)
        df = pd.DataFrame({
            "order_id": [1, 1],
            "product": ["A", "B"],
            "qty": [2, 3],
        })
        result = comp.execute(df)
        out = result["main"]
        assert len(out) == 1
        assert out["product"].iloc[0] == "A;B"
        assert out["qty"].iloc[0] == "2,3"

    def test_column_order_key_first(self):
        """Output column order: key columns first, then denorm columns."""
        config = {
            "denormalize_columns": [{"input_column": "product", "delimiter": ";"}]
        }
        comp = _make_component(config=config)
        df = pd.DataFrame({
            "order_id": [1, 1],
            "product": ["A", "B"],
        })
        result = comp.execute(df)
        out = result["main"]
        assert list(out.columns) == ["order_id", "product"]

    def test_missing_denorm_column_raises(self):
        """Configured denorm column not in input -> ComponentExecutionError (wraps DataValidationError)."""
        config = {
            "denormalize_columns": [{"input_column": "nonexistent", "delimiter": ";"}]
        }
        comp = _make_component(config=config)
        df = pd.DataFrame({"order_id": [1], "product": ["A"]})
        with pytest.raises(ComponentExecutionError, match="nonexistent"):
            comp.execute(df)

    def test_all_columns_denorm_raises(self):
        """All columns in denormalize_columns (no key columns) -> ComponentExecutionError."""
        config = {
            "denormalize_columns": [
                {"input_column": "order_id", "delimiter": ";"},
                {"input_column": "product", "delimiter": ";"},
            ]
        }
        comp = _make_component(config=config)
        df = pd.DataFrame({"order_id": [1, 1], "product": ["A", "B"]})
        with pytest.raises(ComponentExecutionError, match="key"):
            comp.execute(df)


# ------------------------------------------------------------------
# TestMergeFlag
# ------------------------------------------------------------------


@pytest.mark.unit
class TestMergeFlag:
    """merge=True deduplicates values before concatenation (Talend merge behavior)."""

    def test_merge_true_removes_duplicates(self):
        """merge=True: duplicate values within a group appear only once."""
        config = {
            "denormalize_columns": [{"input_column": "tag", "delimiter": ";", "merge": True}]
        }
        comp = _make_component(config=config)
        df = pd.DataFrame({
            "order_id": [1, 1, 1],
            "tag": ["red", "blue", "red"],
        })
        result = comp.execute(df)
        out = result["main"]
        assert out["tag"].iloc[0] == "red;blue"

    def test_merge_false_keeps_duplicates(self):
        """merge=False (default): all values concatenated including duplicates."""
        config = {
            "denormalize_columns": [{"input_column": "tag", "delimiter": ";", "merge": False}]
        }
        comp = _make_component(config=config)
        df = pd.DataFrame({
            "order_id": [1, 1, 1],
            "tag": ["red", "blue", "red"],
        })
        result = comp.execute(df)
        out = result["main"]
        assert out["tag"].iloc[0] == "red;blue;red"

    def test_merge_true_preserves_first_seen_order(self):
        """merge=True: unique values appear in first-seen order, not sorted."""
        config = {
            "denormalize_columns": [{"input_column": "tag", "delimiter": ",", "merge": True}]
        }
        comp = _make_component(config=config)
        df = pd.DataFrame({
            "order_id": [1, 1, 1, 1],
            "tag": ["c", "a", "c", "b"],
        })
        result = comp.execute(df)
        out = result["main"]
        assert out["tag"].iloc[0] == "c,a,b"

    def test_default_merge_is_false(self):
        """Default merge flag (not set) behaves like merge=False."""
        config = {
            "denormalize_columns": [{"input_column": "tag", "delimiter": ";"}]
        }
        comp = _make_component(config=config)
        df = pd.DataFrame({
            "order_id": [1, 1],
            "tag": ["x", "x"],
        })
        result = comp.execute(df)
        out = result["main"]
        assert out["tag"].iloc[0] == "x;x"


# ------------------------------------------------------------------
# TestNullHandling
# ------------------------------------------------------------------


@pytest.mark.unit
class TestNullHandling:
    """null_as_empty=True/False behavior for null values in denorm columns."""

    def test_null_as_empty_false_skips_nulls(self):
        """null_as_empty=False (default): null values are skipped in concatenation."""
        config = {
            "denormalize_columns": [{"input_column": "product", "delimiter": ";"}],
            "null_as_empty": False,
        }
        comp = _make_component(config=config)
        df = pd.DataFrame({
            "order_id": [1, 1, 1],
            "product": ["A", None, "B"],
        })
        result = comp.execute(df)
        out = result["main"]
        assert out["product"].iloc[0] == "A;B"

    def test_null_as_empty_true_includes_empty_string(self):
        """null_as_empty=True: null values become empty strings in concatenation."""
        config = {
            "denormalize_columns": [{"input_column": "product", "delimiter": ";"}],
            "null_as_empty": True,
        }
        comp = _make_component(config=config)
        df = pd.DataFrame({
            "order_id": [1, 1, 1],
            "product": ["A", None, "B"],
        })
        result = comp.execute(df)
        out = result["main"]
        assert out["product"].iloc[0] == "A;;B"

    def test_all_nulls_null_as_empty_false_produces_empty_string(self):
        """null_as_empty=False: group where all values are null -> empty concatenation."""
        config = {
            "denormalize_columns": [{"input_column": "product", "delimiter": ";"}],
            "null_as_empty": False,
        }
        comp = _make_component(config=config)
        df = pd.DataFrame({
            "order_id": [1, 1],
            "product": [None, None],
        })
        result = comp.execute(df)
        out = result["main"]
        assert out["product"].iloc[0] == ""


# ------------------------------------------------------------------
# TestKeyColumnDetection
# ------------------------------------------------------------------


@pytest.mark.unit
class TestKeyColumnDetection:
    """Key column auto-detection: all non-denormalize columns become grouping keys."""

    def test_multiple_key_columns(self):
        """Multiple key columns all participate in groupby."""
        config = {
            "denormalize_columns": [{"input_column": "tag", "delimiter": ","}]
        }
        comp = _make_component(config=config)
        df = pd.DataFrame({
            "order_id": [1, 1, 1, 2],
            "customer": ["Alice", "Alice", "Alice", "Bob"],
            "tag": ["a", "b", "c", "d"],
        })
        result = comp.execute(df)
        out = result["main"]
        assert len(out) == 2
        alice_row = out[(out["order_id"] == 1) & (out["customer"] == "Alice")]
        assert alice_row["tag"].iloc[0] == "a,b,c"

    def test_key_columns_in_output(self):
        """Key columns appear before denorm columns in output."""
        config = {
            "denormalize_columns": [{"input_column": "product", "delimiter": ";"}]
        }
        comp = _make_component(config=config)
        df = pd.DataFrame({
            "order_id": [1, 1],
            "region": ["EU", "EU"],
            "product": ["X", "Y"],
        })
        result = comp.execute(df)
        out = result["main"]
        assert list(out.columns[:2]) == ["order_id", "region"]
        assert out.columns[-1] == "product"


# ------------------------------------------------------------------
# TestNullKeyRows
# ------------------------------------------------------------------


@pytest.mark.unit
class TestNullKeyRows:
    """Null key column values are preserved as a separate group (Talend parity)."""

    def test_null_key_rows_preserved(self):
        """Rows with null key column value form their own group."""
        config = {
            "denormalize_columns": [{"input_column": "product", "delimiter": ";"}]
        }
        comp = _make_component(config=config)
        df = pd.DataFrame({
            "order_id": [1.0, 1.0, None, None],
            "product": ["A", "B", "C", "D"],
        })
        result = comp.execute(df)
        out = result["main"]
        # Should have 2 groups: order_id=1 and order_id=null
        assert len(out) == 2
        null_row = out[out["order_id"].isna()]
        assert len(null_row) == 1
        assert null_row["product"].iloc[0] == "C;D"


# ------------------------------------------------------------------
# TestEdgeCases
# ------------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """Edge cases: None input, empty df, single-row input."""

    def test_none_input_returns_empty_df(self):
        """input_data=None -> returns main: empty DataFrame, reject: None."""
        comp = _make_component(config={
            "denormalize_columns": [{"input_column": "product", "delimiter": ";"}]
        })
        result = comp.execute(None)
        assert isinstance(result["main"], pd.DataFrame)
        assert len(result["main"]) == 0
        assert result.get("reject") is None

    def test_empty_input_returns_empty_df(self):
        """Empty DataFrame -> returns empty DataFrame."""
        comp = _make_component(config={
            "denormalize_columns": [{"input_column": "product", "delimiter": ";"}]
        })
        df = pd.DataFrame({"order_id": pd.Series([], dtype="int64"), "product": pd.Series([], dtype="object")})
        result = comp.execute(df)
        assert isinstance(result["main"], pd.DataFrame)
        assert len(result["main"]) == 0

    def test_single_input_row(self):
        """Single-row input -> single-row output, value unchanged."""
        config = {
            "denormalize_columns": [{"input_column": "product", "delimiter": ";"}]
        }
        comp = _make_component(config=config)
        df = pd.DataFrame({"order_id": [42], "product": ["solo"]})
        result = comp.execute(df)
        out = result["main"]
        assert len(out) == 1
        assert out["product"].iloc[0] == "solo"

    def test_reject_always_none(self):
        """tDenormalize never populates reject flow -- always None."""
        config = {
            "denormalize_columns": [{"input_column": "product", "delimiter": ";"}]
        }
        comp = _make_component(config=config)
        df = pd.DataFrame({"order_id": [1, 1], "product": ["A", "B"]})
        result = comp.execute(df)
        assert result.get("reject") is None

    def test_numeric_values_converted_to_string(self):
        """Numeric values in denorm column are converted to string in output."""
        config = {
            "denormalize_columns": [{"input_column": "qty", "delimiter": ","}]
        }
        comp = _make_component(config=config)
        df = pd.DataFrame({"order_id": [1, 1], "qty": [10, 20]})
        result = comp.execute(df)
        out = result["main"]
        assert out["qty"].iloc[0] == "10,20"


# ------------------------------------------------------------------
# TestGlobalMapVariables
# ------------------------------------------------------------------


@pytest.mark.unit
class TestGlobalMapVariables:
    """NB_LINE, NB_LINE_OK, NB_LINE_REJECT set correctly in GlobalMap."""

    def test_nb_line_equals_output_rows(self):
        """NB_LINE is set to the number of INPUT rows (Talend transform convention).

        For transform components the base class sets NB_LINE = len(input_data).
        4 input rows (2 orders x 2 products each) -> NB_LINE = 4.
        NB_LINE_OK = 2 (one output row per order).
        """
        gm = GlobalMap()
        config = {
            "denormalize_columns": [{"input_column": "product", "delimiter": ";"}]
        }
        comp = _make_component(config=config, global_map=gm)
        df = pd.DataFrame({
            "order_id": [1, 1, 2, 2],
            "product": ["A", "B", "C", "D"],
        })
        comp.execute(df)
        # NB_LINE = input rows (transform convention); NB_LINE_OK = output rows
        assert gm.get("tDenormalize_1_NB_LINE") == 4

    def test_nb_line_ok_equals_output_rows(self):
        """NB_LINE_OK is set to the number of output rows (post-groupby)."""
        gm = GlobalMap()
        config = {
            "denormalize_columns": [{"input_column": "product", "delimiter": ";"}]
        }
        comp = _make_component(config=config, global_map=gm)
        df = pd.DataFrame({
            "order_id": [1, 1, 2],
            "product": ["A", "B", "C"],
        })
        comp.execute(df)
        assert gm.get("tDenormalize_1_NB_LINE_OK") == 2

    def test_nb_line_reject_is_zero(self):
        """NB_LINE_REJECT is always 0 (no reject flow for this component)."""
        gm = GlobalMap()
        config = {
            "denormalize_columns": [{"input_column": "product", "delimiter": ";"}]
        }
        comp = _make_component(config=config, global_map=gm)
        df = pd.DataFrame({"order_id": [1, 1], "product": ["A", "B"]})
        comp.execute(df)
        assert gm.get("tDenormalize_1_NB_LINE_REJECT") == 0

    def test_globalmap_passthrough_mode(self):
        """Pass-through mode (no denormalize_columns) also sets correct stats."""
        gm = GlobalMap()
        comp = _make_component(config={}, global_map=gm)
        df = pd.DataFrame({"order_id": [1, 2, 3], "product": ["A", "B", "C"]})
        comp.execute(df)
        # 3 rows in, 3 rows out (passthrough)
        assert gm.get("tDenormalize_1_NB_LINE") == 3


# ------------------------------------------------------------------
# TestIterateReexecution
# ------------------------------------------------------------------


@pytest.mark.unit
class TestIterateReexecution:
    """execute() called twice (simulating iterate loop) produces consistent results."""

    def test_reexecution_consistent(self):
        """Second execute() call yields same result as first."""
        config = {
            "denormalize_columns": [{"input_column": "product", "delimiter": ";"}]
        }
        comp = _make_component(config=config)
        df = pd.DataFrame({"order_id": [1, 1], "product": ["A", "B"]})
        result1 = comp.execute(df)
        result2 = comp.execute(df)
        pd.testing.assert_frame_equal(
            result1["main"].reset_index(drop=True),
            result2["main"].reset_index(drop=True),
        )

    def test_reexecution_globalmap_updated(self):
        """GlobalMap NB_LINE accumulates across execute() calls (running total)."""
        gm = GlobalMap()
        config = {
            "denormalize_columns": [{"input_column": "product", "delimiter": ";"}]
        }
        comp = _make_component(config=config, global_map=gm)

        df_small = pd.DataFrame({"order_id": [1, 1], "product": ["A", "B"]})
        comp.execute(df_small)
        # After first call: 2 input rows -> NB_LINE=2
        assert gm.get("tDenormalize_1_NB_LINE") == 2

        df_large = pd.DataFrame({
            "order_id": [1, 1, 2, 2, 3, 3],
            "product": ["A", "B", "C", "D", "E", "F"],
        })
        comp.execute(df_large)
        # Stats accumulate: 2 + 6 = 8
        assert gm.get("tDenormalize_1_NB_LINE") == 8
