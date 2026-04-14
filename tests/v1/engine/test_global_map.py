"""Tests for GlobalMap -- Talend-compatible key-value store.

Covers: ENG-02 regression (get default parameter), component stat management,
reset_component for iterate, edge cases (None, 0, empty).
"""
import pytest

from src.v1.engine.global_map import GlobalMap


# ---------------------------------------------------------------------------
# TestGlobalMapGet
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGlobalMapGet:
    """get() must return stored values or default when key is missing."""

    def test_get_existing_key(self):
        gm = GlobalMap()
        gm.put("key", "value")
        assert gm.get("key") == "value"

    def test_get_missing_key_returns_none(self):
        gm = GlobalMap()
        assert gm.get("missing") is None

    def test_get_missing_key_with_custom_default(self):
        gm = GlobalMap()
        assert gm.get("missing", 42) == 42

    def test_get_with_falsy_value_zero(self):
        gm = GlobalMap()
        gm.put("zero", 0)
        assert gm.get("zero") == 0
        assert gm.get("zero") is not None

    def test_get_with_none_value_stored(self):
        gm = GlobalMap()
        gm.put("none_val", None)
        assert gm.get("none_val") is None
        assert gm.contains("none_val")

    def test_get_with_falsy_value_empty_string(self):
        gm = GlobalMap()
        gm.put("empty", "")
        assert gm.get("empty") == ""

    def test_get_with_falsy_value_false(self):
        gm = GlobalMap()
        gm.put("flag", False)
        assert gm.get("flag") is False


# ---------------------------------------------------------------------------
# TestGlobalMapPut
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGlobalMapPut:
    """put() stores values that are retrievable via get()."""

    def test_put_string(self):
        gm = GlobalMap()
        gm.put("name", "alice")
        assert gm.get("name") == "alice"

    def test_put_int(self):
        gm = GlobalMap()
        gm.put("count", 100)
        assert gm.get("count") == 100

    def test_put_none(self):
        gm = GlobalMap()
        gm.put("nothing", None)
        assert gm.get("nothing") is None
        assert gm.contains("nothing")

    def test_put_overwrites_existing(self):
        gm = GlobalMap()
        gm.put("key", "first")
        gm.put("key", "second")
        assert gm.get("key") == "second"


# ---------------------------------------------------------------------------
# TestGlobalMapRemove
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGlobalMapRemove:
    """remove() deletes keys without errors on missing keys."""

    def test_remove_existing_key(self):
        gm = GlobalMap()
        gm.put("key", "value")
        gm.remove("key")
        assert not gm.contains("key")

    def test_remove_missing_key_no_error(self):
        gm = GlobalMap()
        gm.remove("nonexistent")  # Should not raise

    def test_remove_then_get_returns_default(self):
        gm = GlobalMap()
        gm.put("key", "value")
        gm.remove("key")
        assert gm.get("key") is None
        assert gm.get("key", "fallback") == "fallback"


# ---------------------------------------------------------------------------
# TestGlobalMapContains
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGlobalMapContains:
    """contains() checks key presence correctly."""

    def test_contains_existing_key(self):
        gm = GlobalMap()
        gm.put("key", "value")
        assert gm.contains("key") is True

    def test_contains_missing_key(self):
        gm = GlobalMap()
        assert gm.contains("missing") is False

    def test_contains_after_remove(self):
        gm = GlobalMap()
        gm.put("key", "value")
        gm.remove("key")
        assert gm.contains("key") is False


# ---------------------------------------------------------------------------
# TestGlobalMapComponentStats
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGlobalMapComponentStats:
    """Component stat API stores and retrieves stats correctly."""

    def test_put_component_stat_stores_value(self):
        gm = GlobalMap()
        gm.put_component_stat("comp_1", "NB_LINE", 100)
        assert gm.get_component_stat("comp_1", "NB_LINE") == 100

    def test_get_component_stat_retrieves_value(self):
        gm = GlobalMap()
        gm.put_component_stat("comp_1", "NB_LINE_OK", 50)
        assert gm.get_component_stat("comp_1", "NB_LINE_OK") == 50

    def test_flat_key_access_via_get(self):
        gm = GlobalMap()
        gm.put_component_stat("comp_1", "NB_LINE", 100)
        assert gm.get("comp_1_NB_LINE") == 100

    def test_get_component_stat_default_on_missing(self):
        gm = GlobalMap()
        assert gm.get_component_stat("missing", "NB_LINE", 0) == 0

    def test_get_component_stat_default_on_missing_stat_name(self):
        gm = GlobalMap()
        gm.put_component_stat("comp_1", "NB_LINE", 100)
        assert gm.get_component_stat("comp_1", "NB_LINE_REJECT", 0) == 0

    def test_multiple_stats_same_component(self):
        gm = GlobalMap()
        gm.put_component_stat("comp_1", "NB_LINE", 100)
        gm.put_component_stat("comp_1", "NB_LINE_OK", 80)
        gm.put_component_stat("comp_1", "NB_LINE_REJECT", 20)
        assert gm.get_component_stat("comp_1", "NB_LINE") == 100
        assert gm.get_component_stat("comp_1", "NB_LINE_OK") == 80
        assert gm.get_component_stat("comp_1", "NB_LINE_REJECT") == 20

    def test_stats_for_different_components(self):
        gm = GlobalMap()
        gm.put_component_stat("comp_1", "NB_LINE", 100)
        gm.put_component_stat("comp_2", "NB_LINE", 200)
        assert gm.get_component_stat("comp_1", "NB_LINE") == 100
        assert gm.get_component_stat("comp_2", "NB_LINE") == 200


# ---------------------------------------------------------------------------
# TestGlobalMapResetComponent
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGlobalMapResetComponent:
    """reset_component() clears stats for one component, preserving others."""

    def test_reset_clears_target_component(self):
        gm = GlobalMap()
        gm.put_component_stat("comp_1", "NB_LINE", 100)
        gm.put_component_stat("comp_1", "NB_LINE_OK", 80)
        gm.reset_component("comp_1")
        assert gm.get_component_stat("comp_1", "NB_LINE", 0) == 0
        assert gm.get_component_stat("comp_1", "NB_LINE_OK", 0) == 0

    def test_reset_preserves_other_components(self):
        gm = GlobalMap()
        gm.put_component_stat("comp_1", "NB_LINE", 100)
        gm.put_component_stat("comp_2", "NB_LINE", 200)
        gm.reset_component("comp_1")
        assert gm.get_component_stat("comp_2", "NB_LINE") == 200

    def test_reset_removes_flat_keys(self):
        gm = GlobalMap()
        gm.put_component_stat("comp_1", "NB_LINE", 100)
        gm.put_component_stat("comp_1", "NB_LINE_OK", 80)
        gm.reset_component("comp_1")
        assert not gm.contains("comp_1_NB_LINE")
        assert not gm.contains("comp_1_NB_LINE_OK")

    def test_reset_nonexistent_component_no_error(self):
        gm = GlobalMap()
        gm.reset_component("nonexistent")  # Should not raise


# ---------------------------------------------------------------------------
# TestGlobalMapClear
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGlobalMapClear:
    """clear() empties all internal state."""

    def test_clear_empties_all_entries(self):
        gm = GlobalMap()
        gm.put("key1", "val1")
        gm.put("key2", "val2")
        gm.clear()
        assert gm.get("key1") is None
        assert gm.get("key2") is None
        assert gm.get_all() == {}

    def test_clear_empties_component_stats(self):
        gm = GlobalMap()
        gm.put_component_stat("comp_1", "NB_LINE", 100)
        gm.clear()
        assert gm.get_component_stat("comp_1", "NB_LINE", 0) == 0


# ---------------------------------------------------------------------------
# TestGlobalMapGetAll
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGlobalMapGetAll:
    """get_all() must return a defensive copy to prevent external mutation."""

    def test_returns_copy_not_reference(self):
        gm = GlobalMap()
        gm.put("key", "value")
        snapshot = gm.get_all()
        snapshot["key"] = "mutated"
        assert gm.get("key") == "value"  # Internal state unchanged

    def test_mutation_of_returned_dict_does_not_affect_store(self):
        """Addresses Gemini review: verify get_all() returns shallow copy preventing
        external components from accidentally mutating internal state."""
        gm = GlobalMap()
        gm.put("original", 42)
        returned = gm.get_all()
        returned["injected"] = "should_not_appear"
        del returned["original"]
        # Verify internal state is untouched
        assert gm.contains("original")
        assert gm.get("original") == 42
        assert not gm.contains("injected")

    def test_reflects_current_state(self):
        gm = GlobalMap()
        gm.put("a", 1)
        gm.put("b", 2)
        all_data = gm.get_all()
        assert all_data == {"a": 1, "b": 2}


# ---------------------------------------------------------------------------
# TestENG02Regression
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestENG02Regression:
    """Regression: GlobalMap.get() must not raise NameError (ENG-02)."""

    def test_get_missing_key_no_name_error(self):
        gm = GlobalMap()
        # This used to raise NameError: name 'default' is not defined
        result = gm.get("nonexistent")
        assert result is None

    def test_get_with_explicit_default(self):
        gm = GlobalMap()
        result = gm.get("nonexistent", "fallback")
        assert result == "fallback"
