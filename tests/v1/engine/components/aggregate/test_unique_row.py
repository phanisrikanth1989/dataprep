"""Tests for UniqueRow (tUniqRow engine implementation).

Covers UNIQUE/DUPLICATE output routing, per-column case sensitivity,
key_columns normalisation (dict-list vs str-list), registry aliases,
stats lifecycle, and edge cases.
"""
import pytest
import pandas as pd

from src.v1.engine.components.aggregate.unique_row import UniqueRow
from src.v1.engine.component_registry import REGISTRY
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError
from src.v1.engine.global_map import GlobalMap


# ------------------------------------------------------------------
# Test Helpers
# ------------------------------------------------------------------

_DEFAULT_CONFIG = {"component_type": "UniqueRow"}


def _make_component(config=None, global_map=None):
    """Create a UniqueRow with test defaults.

    NOTE: self.config is only populated inside execute(), so all behavioural
    tests must call execute(), not _process() directly.
    """
    gm = global_map if global_map is not None else GlobalMap()
    cm = ContextManager()
    comp = UniqueRow(
        component_id="tUniqRow_1",
        config=config or dict(_DEFAULT_CONFIG),
        global_map=gm,
        context_manager=cm,
    )
    comp.output_schema = []
    comp.input_schema = []
    comp.inputs = ["row1"]
    return comp


def _df(*rows, columns=None):
    """Quick DataFrame builder from tuple rows."""
    return pd.DataFrame(list(rows), columns=columns)


# ------------------------------------------------------------------
# TestRegistration
# ------------------------------------------------------------------


@pytest.mark.unit
class TestRegistration:
    """All four registry aliases must resolve to UniqueRow."""

    def test_registry_uniquerow(self):
        assert REGISTRY.get("UniqueRow") is UniqueRow

    def test_registry_tuniqrow(self):
        assert REGISTRY.get("tUniqRow") is UniqueRow

    def test_registry_tuniquerow(self):
        assert REGISTRY.get("tUniqueRow") is UniqueRow

    def test_registry_tunqrow(self):
        assert REGISTRY.get("tUnqRow") is UniqueRow


# ------------------------------------------------------------------
# TestNoExecuteOverride
# ------------------------------------------------------------------


@pytest.mark.unit
class TestNoExecuteOverride:
    """execute() must NOT be overridden -- Rule 4."""

    def test_execute_not_in_own_dict(self):
        assert "execute" not in UniqueRow.__dict__


# ------------------------------------------------------------------
# TestValidation
# ------------------------------------------------------------------


@pytest.mark.unit
class TestValidation:
    """_validate_config() -- container-shape checks only (Rule 12).

    execute() is used so that self.config is populated before validation.
    """

    def test_valid_config_no_key_columns(self):
        comp = _make_component()
        comp.execute(pd.DataFrame())  # must not raise

    def test_valid_config_dict_list(self):
        comp = _make_component(config={
            "component_type": "UniqueRow",
            "key_columns": [{"column": "id", "case_sensitive": True}],
        })
        comp.execute(pd.DataFrame())  # must not raise

    def test_valid_config_str_list(self):
        comp = _make_component(config={
            "component_type": "UniqueRow",
            "key_columns": ["id", "name"],
        })
        comp.execute(pd.DataFrame())  # must not raise

    def test_invalid_key_columns_not_list(self):
        comp = _make_component(config={
            "component_type": "UniqueRow",
            "key_columns": "id",
        })
        with pytest.raises(ConfigurationError):
            comp.execute(pd.DataFrame())

    def test_invalid_key_columns_integer(self):
        comp = _make_component(config={
            "component_type": "UniqueRow",
            "key_columns": 42,
        })
        with pytest.raises(ConfigurationError):
            comp.execute(pd.DataFrame())


# ------------------------------------------------------------------
# TestDeduplication
# ------------------------------------------------------------------


@pytest.mark.unit
class TestDeduplication:
    """Core deduplication logic (tested via execute())."""

    def test_keep_first_default(self):
        df = _df(("A", 1), ("A", 2), ("B", 3), columns=["id", "val"])
        comp = _make_component(config={
            "component_type": "UniqueRow",
            "key_columns": [{"column": "id", "case_sensitive": True}],
            "keep": "first",
        })
        result = comp.execute(df)
        assert list(result["main"]["id"]) == ["A", "B"]
        assert list(result["main"]["val"]) == [1, 3]

    def test_keep_last(self):
        df = _df(("A", 1), ("A", 2), ("B", 3), columns=["id", "val"])
        comp = _make_component(config={
            "component_type": "UniqueRow",
            "key_columns": [{"column": "id", "case_sensitive": True}],
            "keep": "last",
        })
        result = comp.execute(df)
        assert list(result["main"]["val"]) == [2, 3]

    def test_keep_false_drops_all_duplicates(self):
        df = _df(("A", 1), ("A", 2), ("B", 3), columns=["id", "val"])
        comp = _make_component(config={
            "component_type": "UniqueRow",
            "key_columns": [{"column": "id", "case_sensitive": True}],
            "keep": False,
        })
        result = comp.execute(df)
        assert list(result["main"]["id"]) == ["B"]

    def test_multi_key_columns_dict_list(self):
        df = _df(
            ("A", 1), ("A", 1), ("A", 2), ("B", 1),
            columns=["id", "seq"],
        )
        comp = _make_component(config={
            "component_type": "UniqueRow",
            "key_columns": [
                {"column": "id", "case_sensitive": True},
                {"column": "seq", "case_sensitive": True},
            ],
        })
        result = comp.execute(df)
        assert len(result["main"]) == 3

    def test_str_list_key_columns_backward_compat(self):
        df = _df(("A", 1), ("A", 2), ("B", 3), columns=["id", "val"])
        comp = _make_component(config={
            "component_type": "UniqueRow",
            "key_columns": ["id"],
        })
        result = comp.execute(df)
        assert len(result["main"]) == 2

    def test_all_columns_fallback_no_key_columns(self):
        df = _df(("A", 1), ("A", 1), ("B", 2), columns=["id", "val"])
        comp = _make_component()
        result = comp.execute(df)
        assert len(result["main"]) == 2

    def test_nonexistent_key_columns_fallback(self):
        df = _df(("A",), ("A",), columns=["id"])
        comp = _make_component(config={
            "component_type": "UniqueRow",
            "key_columns": [{"column": "MISSING", "case_sensitive": True}],
        })
        result = comp.execute(df)
        assert len(result["main"]) == 1


# ------------------------------------------------------------------
# TestCaseSensitivity
# ------------------------------------------------------------------


@pytest.mark.unit
class TestCaseSensitivity:
    """Per-column and global case sensitivity."""

    def test_case_sensitive_true_no_merge(self):
        df = _df(("Alice",), ("alice",), ("Bob",), columns=["name"])
        comp = _make_component(config={
            "component_type": "UniqueRow",
            "key_columns": [{"column": "name", "case_sensitive": True}],
        })
        result = comp.execute(df)
        assert len(result["main"]) == 3

    def test_case_insensitive_dict_deduplicates(self):
        df = _df(("Alice",), ("alice",), ("Bob",), columns=["name"])
        comp = _make_component(config={
            "component_type": "UniqueRow",
            "key_columns": [{"column": "name", "case_sensitive": False}],
        })
        result = comp.execute(df)
        assert len(result["main"]) == 2

    def test_global_case_insensitive_fallback(self):
        df = _df(("Alice",), ("ALICE",), columns=["name"])
        comp = _make_component(config={
            "component_type": "UniqueRow",
            "key_columns": ["name"],
            "case_sensitive": False,
        })
        result = comp.execute(df)
        assert len(result["main"]) == 1

    def test_per_column_mixed_sensitivity(self):
        df = _df(
            ("Alice", "NYC"), ("alice", "NYC"), ("Alice", "nyc"),
            columns=["name", "city"],
        )
        comp = _make_component(config={
            "component_type": "UniqueRow",
            "key_columns": [
                {"column": "name", "case_sensitive": False},
                {"column": "city", "case_sensitive": True},
            ],
        })
        result = comp.execute(df)
        assert len(result["main"]) == 2

    def test_no_temp_columns_in_output(self):
        """Temp CI columns must NOT appear in the output DataFrames."""
        df = _df(("Alice",), ("alice",), ("Bob",), columns=["name"])
        comp = _make_component(config={
            "component_type": "UniqueRow",
            "key_columns": [{"column": "name", "case_sensitive": False}],
        })
        result = comp.execute(df)
        for col in result["main"].columns:
            assert not col.startswith("__uniq_ci_"), f"Temp col leaked: {col}"
        for col in result["reject"].columns:
            assert not col.startswith("__uniq_ci_"), f"Temp col leaked: {col}"


# ------------------------------------------------------------------
# TestOutputFlows
# ------------------------------------------------------------------


@pytest.mark.unit
class TestOutputFlows:
    """Unique rows go to main; duplicates go to reject."""

    def test_unique_rows_in_main(self):
        df = _df(("A",), ("A",), ("B",), columns=["id"])
        comp = _make_component()
        result = comp.execute(df)
        assert set(result["main"]["id"]) == {"A", "B"}

    def test_duplicate_rows_in_reject(self):
        df = _df(("A",), ("A",), ("B",), columns=["id"])
        comp = _make_component()
        result = comp.execute(df)
        assert list(result["reject"]["id"]) == ["A"]

    def test_reject_empty_when_output_duplicates_false(self):
        df = _df(("A",), ("A",), ("B",), columns=["id"])
        comp = _make_component(config={
            "component_type": "UniqueRow",
            "output_duplicates": False,
        })
        result = comp.execute(df)
        assert result["reject"].empty
        assert "id" in result["reject"].columns


# ------------------------------------------------------------------
# TestOnlyOnceEachDuplicate
# ------------------------------------------------------------------


@pytest.mark.unit
class TestOnlyOnceEachDuplicate:
    """only_once_each_duplicated_key=True: each key group appears at most once
    in the DUPLICATE (reject) output."""

    def test_only_once_limits_reject_to_one_per_group(self):
        # john appears 3x: row 0 -> unique, rows 1+2 -> both duplicates normally
        # with only_once=True: only row 1 appears in reject
        df = _df(("john",), ("john",), ("john",), columns=["email"])
        comp = _make_component(config={
            "component_type": "UniqueRow",
            "key_columns": [{"column": "email", "case_sensitive": True}],
            "only_once_each_duplicated_key": True,
        })
        result = comp.execute(df)
        assert len(result["main"]) == 1
        assert len(result["reject"]) == 1  # only first duplicate, not both

    def test_only_once_false_emits_all_duplicates(self):
        # Default: all duplicates appear in reject
        df = _df(("john",), ("john",), ("john",), columns=["email"])
        comp = _make_component(config={
            "component_type": "UniqueRow",
            "key_columns": [{"column": "email", "case_sensitive": True}],
            "only_once_each_duplicated_key": False,
        })
        result = comp.execute(df)
        assert len(result["main"]) == 1
        assert len(result["reject"]) == 2  # both duplicates emitted

    def test_only_once_unique_output_unaffected(self):
        # UNIQUE output must still be the first occurrence regardless of only_once
        df = _df(
            ("john", 1), ("jane", 2), ("john", 3), ("jane", 4),
            columns=["email", "id"],
        )
        comp = _make_component(config={
            "component_type": "UniqueRow",
            "key_columns": [{"column": "email", "case_sensitive": True}],
            "only_once_each_duplicated_key": True,
        })
        result = comp.execute(df)
        assert list(result["main"]["id"]) == [1, 2]  # first occurrences

    def test_only_once_with_case_insensitive(self):
        # CI: Alice/alice are the same key; only first duplicate goes to reject
        df = _df(("Alice",), ("alice",), ("ALICE",), columns=["name"])
        comp = _make_component(config={
            "component_type": "UniqueRow",
            "key_columns": [{"column": "name", "case_sensitive": False}],
            "only_once_each_duplicated_key": True,
        })
        result = comp.execute(df)
        assert len(result["main"]) == 1
        assert len(result["reject"]) == 1  # only first CI duplicate


# ------------------------------------------------------------------
# TestStats
# ------------------------------------------------------------------


@pytest.mark.unit
class TestStats:
    """Stats lifecycle: NB_LINE, NB_LINE_OK, NB_LINE_REJECT, global_map extras."""

    def test_nb_line_equals_total_input(self):
        df = _df(("A",), ("A",), ("B",), columns=["id"])
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(df)
        assert comp.stats["NB_LINE"] == 3

    def test_nb_line_ok_equals_unique_count(self):
        df = _df(("A",), ("A",), ("B",), columns=["id"])
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(df)
        assert comp.stats["NB_LINE_OK"] == 2

    def test_nb_line_reject_when_is_reject_duplicate_true(self):
        df = _df(("A",), ("A",), ("B",), columns=["id"])
        gm = GlobalMap()
        comp = _make_component(config={
            "component_type": "UniqueRow",
            "is_reject_duplicate": True,
        }, global_map=gm)
        comp.execute(df)
        assert comp.stats["NB_LINE_REJECT"] == 1

    def test_nb_line_reject_zero_when_is_reject_duplicate_false(self):
        df = _df(("A",), ("A",), ("B",), columns=["id"])
        gm = GlobalMap()
        comp = _make_component(config={
            "component_type": "UniqueRow",
            "is_reject_duplicate": False,
        }, global_map=gm)
        comp.execute(df)
        assert comp.stats["NB_LINE_REJECT"] == 0

    def test_global_map_nb_uniques(self):
        df = _df(("A",), ("A",), ("B",), columns=["id"])
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(df)
        assert gm.get("tUniqRow_1_NB_UNIQUES") == 2

    def test_global_map_nb_duplicates(self):
        df = _df(("A",), ("A",), ("B",), columns=["id"])
        gm = GlobalMap()
        comp = _make_component(global_map=gm)
        comp.execute(df)
        assert gm.get("tUniqRow_1_NB_DUPLICATES") == 1

    def test_stats_set_by_component_flag(self):
        """Base class auto-count must be bypassed (manual _update_stats)."""
        df = _df(("A",), ("B",), columns=["id"])
        comp = _make_component()
        comp.execute(df)
        assert comp._stats_set_by_component is True


# ------------------------------------------------------------------
# TestEdgeCases
# ------------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """Boundary and degenerate inputs."""

    def test_none_input_returns_empty(self):
        comp = _make_component()
        result = comp.execute(None)
        assert result["main"].empty
        assert result["reject"].empty

    def test_empty_dataframe_returns_empty(self):
        comp = _make_component()
        result = comp.execute(pd.DataFrame(columns=["id"]))
        assert result["main"].empty
        assert result["reject"].empty

    def test_single_row_no_duplicates(self):
        df = _df(("A",), columns=["id"])
        comp = _make_component()
        result = comp.execute(df)
        assert len(result["main"]) == 1
        assert result["reject"].empty

    def test_all_unique_rows(self):
        df = _df(("A",), ("B",), ("C",), columns=["id"])
        comp = _make_component()
        result = comp.execute(df)
        assert len(result["main"]) == 3
        assert result["reject"].empty

    def test_all_duplicate_rows(self):
        df = _df(("A",), ("A",), ("A",), columns=["id"])
        comp = _make_component()
        result = comp.execute(df)
        assert len(result["main"]) == 1
        assert len(result["reject"]) == 2

    def test_output_preserves_all_columns(self):
        """No columns should be dropped from the output DataFrames."""
        df = _df(("A", 1, True), ("A", 2, False), columns=["id", "num", "flag"])
        comp = _make_component(config={
            "component_type": "UniqueRow",
            "key_columns": [{"column": "id", "case_sensitive": True}],
        })
        result = comp.execute(df)
        assert list(result["main"].columns) == ["id", "num", "flag"]
        assert list(result["reject"].columns) == ["id", "num", "flag"]
