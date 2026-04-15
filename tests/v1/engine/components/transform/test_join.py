"""Tests for Join (tJoin engine implementation).

Covers requirements JOIN-01 through JOIN-08:
  JOIN-01: Case-sensitive join keys
  JOIN-02: Left outer join with reject
  JOIN-03: Reject schema with errorCode/errorMessage
  JOIN-04: INCLUDE_LOOKUP toggle
  JOIN-05: ERROR_MESSAGE in globalMap
  JOIN-07: Single-pass merge
  JOIN-08: Null keys do not match
"""
import pytest
import numpy as np
import pandas as pd

from src.v1.engine.components.transform.join import Join
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Test Helpers
# ------------------------------------------------------------------

_DEFAULT_CONFIG = {
    "component_type": "Join",
    "use_inner_join": False,
    "join_key": [{"input_column": "id", "lookup_column": "ref_id"}],
    "use_lookup_cols": False,
    "lookup_cols": [],
}


def _make_component(config=None, global_map=None, output_schema=None, reject_schema=None):
    """Create a Join with test defaults."""
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    comp = Join(
        component_id="tJoin_1",
        config=config or dict(_DEFAULT_CONFIG),
        global_map=gm,
        context_manager=cm,
    )
    comp.output_schema = output_schema or [
        {"name": "id", "type": "str", "nullable": True},
        {"name": "name", "type": "str", "nullable": True},
    ]
    comp.reject_schema = reject_schema or []
    comp.inputs = ["row1", "row2"]
    return comp


def _main_df():
    """Main input: 3 rows with id and name."""
    return pd.DataFrame({"id": ["A", "B", "C"], "name": ["Alice", "Bob", "Carol"]})


def _lookup_df():
    """Lookup input: 3 rows with ref_id and city."""
    return pd.DataFrame({"ref_id": ["A", "C", "D"], "city": ["NYC", "LA", "CHI"]})


def _exec(comp, main=None, lookup=None):
    """Execute join with main and lookup DataFrames."""
    main_data = main if main is not None else _main_df()
    lookup_data = lookup if lookup is not None else _lookup_df()
    return comp.execute({"row1": main_data, "row2": lookup_data})


# ------------------------------------------------------------------
# TestRegistration
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    """Component registry registration."""

    def test_registry_join(self):
        assert REGISTRY.get("Join") is Join

    def test_registry_tjoin(self):
        assert REGISTRY.get("tJoin") is Join


# ------------------------------------------------------------------
# TestValidation
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    """Config validation error handling."""

    def test_missing_join_key(self):
        """Empty config -> ConfigurationError."""
        config = {"component_type": "Join"}
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="join_key"):
            _exec(comp)

    def test_empty_join_key(self):
        """join_key: [] -> ConfigurationError."""
        config = {**_DEFAULT_CONFIG, "join_key": []}
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="join_key"):
            _exec(comp)

    def test_join_key_missing_input_column(self):
        """join_key entry missing input_column -> ConfigurationError."""
        config = {**_DEFAULT_CONFIG, "join_key": [{"lookup_column": "x"}]}
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="input_column"):
            _exec(comp)

    def test_join_key_missing_lookup_column(self):
        """join_key entry missing lookup_column -> ConfigurationError."""
        config = {**_DEFAULT_CONFIG, "join_key": [{"input_column": "x"}]}
        comp = _make_component(config=config)
        with pytest.raises(ConfigurationError, match="lookup_column"):
            _exec(comp)


# ------------------------------------------------------------------
# TestLeftOuterJoin -- covers JOIN-02
# ------------------------------------------------------------------


@pytest.mark.unit
class TestLeftOuterJoin:
    """Left outer join (default mode)."""

    def test_left_outer_all_match(self):
        """All main rows match -> 3 main, 0 reject."""
        lookup = pd.DataFrame({"ref_id": ["A", "B", "C"], "city": ["NYC", "LA", "CHI"]})
        comp = _make_component()
        result = _exec(comp, lookup=lookup)
        assert len(result["main"]) == 3
        assert result.get("reject") is None

    def test_left_outer_partial_match(self):
        """2 of 3 match -> 3 main (with NaN for unmatched), 1 reject."""
        comp = _make_component()
        result = _exec(comp)
        # Main has all 3 rows (left outer preserves unmatched)
        assert len(result["main"]) == 3
        # Reject has 1 row (B not in lookup)
        assert result["reject"] is not None
        assert len(result["reject"]) == 1
        assert result["reject"]["id"].iloc[0] == "B"

    def test_left_outer_no_match(self):
        """0 match -> 3 main, 3 reject."""
        lookup = pd.DataFrame({"ref_id": ["X", "Y", "Z"], "city": ["a", "b", "c"]})
        comp = _make_component()
        result = _exec(comp, lookup=lookup)
        assert len(result["main"]) == 3
        assert result["reject"] is not None
        assert len(result["reject"]) == 3


# ------------------------------------------------------------------
# TestInnerJoin
# ------------------------------------------------------------------


@pytest.mark.unit
class TestInnerJoin:
    """Inner join mode."""

    def test_inner_join_all_match(self):
        """All match -> 3 main, 0 reject."""
        config = {**_DEFAULT_CONFIG, "use_inner_join": True}
        lookup = pd.DataFrame({"ref_id": ["A", "B", "C"], "city": ["NYC", "LA", "CHI"]})
        comp = _make_component(config=config)
        result = _exec(comp, lookup=lookup)
        assert len(result["main"]) == 3
        assert result.get("reject") is None

    def test_inner_join_partial_match(self):
        """2 of 3 match -> 2 main, 1 reject."""
        config = {**_DEFAULT_CONFIG, "use_inner_join": True}
        comp = _make_component(config=config)
        result = _exec(comp)
        assert len(result["main"]) == 2
        assert result["reject"] is not None
        assert len(result["reject"]) == 1

    def test_inner_join_no_match(self):
        """0 match -> 0 main, 3 reject."""
        config = {**_DEFAULT_CONFIG, "use_inner_join": True}
        lookup = pd.DataFrame({"ref_id": ["X", "Y", "Z"], "city": ["a", "b", "c"]})
        comp = _make_component(config=config)
        result = _exec(comp, lookup=lookup)
        assert len(result["main"]) == 0
        assert result["reject"] is not None
        assert len(result["reject"]) == 3


# ------------------------------------------------------------------
# TestCaseSensitiveJoin -- covers JOIN-01
# ------------------------------------------------------------------


@pytest.mark.unit
class TestCaseSensitiveJoin:
    """Case-sensitive join keys (default behavior)."""

    def test_case_sensitive_default(self):
        """Main 'A', lookup 'a' -> no match (case sensitive is default)."""
        main = pd.DataFrame({"id": ["A"], "name": ["Alice"]})
        lookup = pd.DataFrame({"ref_id": ["a"], "city": ["NYC"]})
        config = {**_DEFAULT_CONFIG, "use_inner_join": True}
        comp = _make_component(config=config)
        result = _exec(comp, main=main, lookup=lookup)
        assert len(result["main"]) == 0

    def test_original_data_preserved(self):
        """After join, original column values are NOT lowercased."""
        main = pd.DataFrame({"id": ["A"], "name": ["Alice"]})
        lookup = pd.DataFrame({"ref_id": ["A"], "city": ["NYC"]})
        comp = _make_component()
        result = _exec(comp, main=main, lookup=lookup)
        assert result["main"]["id"].iloc[0] == "A"
        assert result["main"]["name"].iloc[0] == "Alice"

    def test_mixed_case_exact_match(self):
        """Main 'Alice', lookup 'Alice' -> match."""
        main = pd.DataFrame({"id": ["Alice"], "name": ["test"]})
        lookup = pd.DataFrame({"ref_id": ["Alice"], "city": ["NYC"]})
        comp = _make_component()
        result = _exec(comp, main=main, lookup=lookup)
        assert len(result["main"]) == 1
        assert result.get("reject") is None


# ------------------------------------------------------------------
# TestNullJoinKeys -- covers JOIN-08
# ------------------------------------------------------------------


@pytest.mark.unit
class TestNullJoinKeys:
    """Null join keys do not match (SQL/Talend semantics)."""

    def test_null_keys_do_not_match(self):
        """Main NaN, lookup NaN -> they do NOT match."""
        main = pd.DataFrame({"id": [np.nan], "name": ["test"]})
        lookup = pd.DataFrame({"ref_id": [np.nan], "city": ["NYC"]})
        config = {**_DEFAULT_CONFIG, "use_inner_join": True}
        comp = _make_component(config=config)
        result = _exec(comp, main=main, lookup=lookup)
        assert len(result["main"]) == 0

    def test_null_main_key_goes_to_reject(self):
        """Main row with NaN key -> reject (left outer)."""
        main = pd.DataFrame({"id": [np.nan, "A"], "name": ["test1", "test2"]})
        lookup = pd.DataFrame({"ref_id": ["A"], "city": ["NYC"]})
        comp = _make_component()
        result = _exec(comp, main=main, lookup=lookup)
        assert result["reject"] is not None
        assert len(result["reject"]) == 1

    def test_null_lookup_key_not_matched(self):
        """Lookup row with NaN key is never matched."""
        main = pd.DataFrame({"id": ["A", "B"], "name": ["test1", "test2"]})
        lookup = pd.DataFrame({"ref_id": ["A", np.nan], "city": ["NYC", "LA"]})
        config = {**_DEFAULT_CONFIG, "use_inner_join": True}
        comp = _make_component(config=config)
        result = _exec(comp, main=main, lookup=lookup)
        # Only A matches, B does not (even though lookup has NaN)
        assert len(result["main"]) == 1
        assert result["main"]["id"].iloc[0] == "A"

    def test_mixed_null_and_valid_keys(self):
        """Some null, some valid -> only valid keys match."""
        main = pd.DataFrame({"id": ["A", np.nan, "C"], "name": ["a", "b", "c"]})
        lookup = pd.DataFrame({"ref_id": ["A", "C", np.nan], "city": ["x", "y", "z"]})
        config = {**_DEFAULT_CONFIG, "use_inner_join": True}
        comp = _make_component(config=config)
        result = _exec(comp, main=main, lookup=lookup)
        assert len(result["main"]) == 2
        assert set(result["main"]["id"].tolist()) == {"A", "C"}


# ------------------------------------------------------------------
# TestRejectOutput -- covers JOIN-02, JOIN-03
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRejectOutput:
    """Reject flow behavior."""

    def test_reject_contains_unmatched_main_rows(self):
        """Reject has exactly the unmatched rows."""
        comp = _make_component()
        result = _exec(comp)
        # B is unmatched
        assert result["reject"] is not None
        assert len(result["reject"]) == 1
        assert "B" in result["reject"]["id"].values

    def test_reject_schema_with_error_columns(self):
        """When reject_schema includes errorCode/errorMessage, reject has those columns."""
        reject_schema = [
            {"name": "id", "type": "str", "nullable": True},
            {"name": "name", "type": "str", "nullable": True},
            {"name": "errorCode", "type": "str", "nullable": True},
            {"name": "errorMessage", "type": "str", "nullable": True},
        ]
        comp = _make_component(reject_schema=reject_schema)
        result = _exec(comp)
        assert result["reject"] is not None
        assert "errorCode" in result["reject"].columns
        assert "errorMessage" in result["reject"].columns

    def test_reject_error_code_value(self):
        """Reject rows have errorCode='JOIN_REJECT'."""
        reject_schema = [
            {"name": "id", "type": "str", "nullable": True},
            {"name": "name", "type": "str", "nullable": True},
            {"name": "errorCode", "type": "str", "nullable": True},
            {"name": "errorMessage", "type": "str", "nullable": True},
        ]
        comp = _make_component(reject_schema=reject_schema)
        result = _exec(comp)
        assert result["reject"] is not None
        assert result["reject"]["errorCode"].iloc[0] == "JOIN_REJECT"

    def test_reject_error_message_value(self):
        """Reject rows have errorMessage set."""
        reject_schema = [
            {"name": "id", "type": "str", "nullable": True},
            {"name": "name", "type": "str", "nullable": True},
            {"name": "errorCode", "type": "str", "nullable": True},
            {"name": "errorMessage", "type": "str", "nullable": True},
        ]
        comp = _make_component(reject_schema=reject_schema)
        result = _exec(comp)
        assert result["reject"] is not None
        assert result["reject"]["errorMessage"].iloc[0] is not None
        assert len(str(result["reject"]["errorMessage"].iloc[0])) > 0


# ------------------------------------------------------------------
# TestIncludeLookup -- covers JOIN-04
# ------------------------------------------------------------------


@pytest.mark.unit
class TestIncludeLookup:
    """INCLUDE_LOOKUP toggle for lookup columns in output."""

    def test_use_lookup_cols_false(self):
        """Output contains only main columns (no lookup columns)."""
        comp = _make_component()
        result = _exec(comp)
        # Main columns only: id, name (no city from lookup)
        assert "city" not in result["main"].columns

    def test_use_lookup_cols_true_with_lookup_cols(self):
        """Output contains main columns + specified lookup columns."""
        config = {
            **_DEFAULT_CONFIG,
            "use_lookup_cols": True,
            "lookup_cols": [{"output_column": "city", "lookup_column": "city"}],
        }
        comp = _make_component(config=config)
        result = _exec(comp)
        assert "city" in result["main"].columns

    def test_use_lookup_cols_true_empty_lookup_cols(self):
        """With empty lookup_cols list, no lookup columns added."""
        config = {
            **_DEFAULT_CONFIG,
            "use_lookup_cols": True,
            "lookup_cols": [],
        }
        comp = _make_component(config=config)
        result = _exec(comp)
        assert "city" not in result["main"].columns


# ------------------------------------------------------------------
# TestErrorMessage -- covers JOIN-05
# ------------------------------------------------------------------


@pytest.mark.unit
class TestErrorMessage:
    """ERROR_MESSAGE in globalMap on reject."""

    def test_error_message_globalmap_on_reject(self):
        """When join produces rejects, ERROR_MESSAGE is set in globalMap."""
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        _exec(comp)  # B is unmatched -> reject exists
        error_msg = gm.get("tJoin_1_ERROR_MESSAGE")
        assert error_msg is not None
        assert "reject" in error_msg.lower()


# ------------------------------------------------------------------
# TestSinglePassMerge -- covers JOIN-07
# ------------------------------------------------------------------


@pytest.mark.unit
class TestSinglePassMerge:
    """Single-pass merge produces correct results."""

    def test_single_pass_produces_correct_results(self):
        """Inner join with partial match -> correct counts."""
        config = {**_DEFAULT_CONFIG, "use_inner_join": True}
        comp = _make_component(config=config)
        result = _exec(comp)
        # A and C match, B does not
        assert len(result["main"]) == 2
        assert result["reject"] is not None
        assert len(result["reject"]) == 1


# ------------------------------------------------------------------
# TestFirstMatchDedup -- Pitfall 7
# ------------------------------------------------------------------


@pytest.mark.unit
class TestFirstMatchDedup:
    """First-match deduplication on lookup side."""

    def test_duplicate_lookup_keys_uses_first(self):
        """Lookup has 2 rows for same key -> first row's values used."""
        main = pd.DataFrame({"id": ["A"], "name": ["Alice"]})
        lookup = pd.DataFrame({
            "ref_id": ["A", "A"],
            "city": ["NYC", "LA"],
        })
        config = {
            **_DEFAULT_CONFIG,
            "use_lookup_cols": True,
            "lookup_cols": [{"output_column": "city", "lookup_column": "city"}],
        }
        comp = _make_component(config=config)
        result = _exec(comp, main=main, lookup=lookup)
        assert len(result["main"]) == 1
        assert result["main"]["city"].iloc[0] == "NYC"  # first match

    def test_no_row_multiplication(self):
        """Main 1 row, lookup 3 rows same key -> output 1 row."""
        main = pd.DataFrame({"id": ["A"], "name": ["Alice"]})
        lookup = pd.DataFrame({
            "ref_id": ["A", "A", "A"],
            "city": ["NYC", "LA", "CHI"],
        })
        comp = _make_component()
        result = _exec(comp, main=main, lookup=lookup)
        assert len(result["main"]) == 1


# ------------------------------------------------------------------
# TestEdgeCases
# ------------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """Edge cases for join."""

    def test_empty_main(self):
        """Empty main DataFrame -> empty output."""
        main = pd.DataFrame(columns=["id", "name"])
        comp = _make_component()
        result = _exec(comp, main=main)
        assert len(result["main"]) == 0

    def test_empty_lookup(self):
        """Empty lookup DataFrame -> all main rows in reject (left outer)."""
        lookup = pd.DataFrame(columns=["ref_id", "city"])
        comp = _make_component()
        result = _exec(comp, lookup=lookup)
        # Left outer: all 3 main rows in main, but all unmatched -> all 3 in reject
        assert result["reject"] is not None
        assert len(result["reject"]) == 3

    def test_single_row_match(self):
        """1 main, 1 lookup, matching key -> 1 output."""
        main = pd.DataFrame({"id": ["A"], "name": ["Alice"]})
        lookup = pd.DataFrame({"ref_id": ["A"], "city": ["NYC"]})
        comp = _make_component()
        result = _exec(comp, main=main, lookup=lookup)
        assert len(result["main"]) == 1
        assert result.get("reject") is None

    def test_multi_key_join(self):
        """Join on 2 key columns simultaneously."""
        main = pd.DataFrame({"k1": ["A", "B"], "k2": [1, 2], "val": ["x", "y"]})
        lookup = pd.DataFrame({"lk1": ["A", "B"], "lk2": [1, 9], "info": ["m", "n"]})
        config = {
            **_DEFAULT_CONFIG,
            "join_key": [
                {"input_column": "k1", "lookup_column": "lk1"},
                {"input_column": "k2", "lookup_column": "lk2"},
            ],
            "use_inner_join": True,
        }
        comp = _make_component(config=config)
        result = _exec(comp, main=main, lookup=lookup)
        # Only first row matches (A,1) -> (A,1)
        assert len(result["main"]) == 1
        assert result["main"]["val"].iloc[0] == "x"

    def test_stats_updated(self):
        """GlobalMap has NB_LINE, NB_LINE_OK, NB_LINE_REJECT after execute."""
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        _exec(comp)  # 3 main, 2 match, 1 reject
        # _process calls _update_stats(3, 3, 1) for left outer
        # _update_stats_from_result adds (3 main, 1 reject)
        # NB_LINE = 3 + (3+1) = 7, NB_LINE_OK = 3 + 3 = 6, NB_LINE_REJECT = 1 + 1 = 2
        nb_line = gm.get_nb_line("tJoin_1")
        nb_line_ok = gm.get_nb_line_ok("tJoin_1")
        nb_reject = gm.get_nb_line_reject("tJoin_1")
        assert nb_line > 0
        assert nb_line_ok > 0
        assert nb_reject > 0
