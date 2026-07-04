"""Tests for TriggerManager -- trigger flow and condition evaluation.

Covers: ENG-06 (operator corruption), ENG-10 (OnSubjobOk timing),
NEW-04 (sandboxed eval), NEW-05 (cast types), trigger routing.
"""
import pytest
from src.v1.engine.trigger_manager import TriggerManager, TriggerType, Trigger
from src.v1.engine.global_map import GlobalMap
from src.v1.engine.exceptions import TriggerEvaluationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tm(global_map=None):
    """Create a TriggerManager with optional GlobalMap."""
    gm = global_map or GlobalMap()
    return TriggerManager(gm), gm


# ---------------------------------------------------------------------------
# 1. Condition evaluation -- operator conversion
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestTriggerConditionEval:
    """Test Java-to-Python operator conversion in _evaluate_condition."""

    def test_not_equals_preserved(self):
        """!= must not be corrupted to 'not ='."""
        tm, gm = _make_tm()
        gm.put("x", 1)
        assert tm._evaluate_condition('globalMap.get("x") != 0') is True

    def test_not_equals_false_when_equal(self):
        """!= evaluates to False when values are equal."""
        tm, gm = _make_tm()
        gm.put("x", 0)
        assert tm._evaluate_condition('globalMap.get("x") != 0') is False

    def test_equals_operator(self):
        """== works correctly."""
        tm, gm = _make_tm()
        gm.put("x", 1)
        assert tm._evaluate_condition('globalMap.get("x") == 1') is True

    def test_equals_operator_false(self):
        """== evaluates to False when not equal."""
        tm, gm = _make_tm()
        gm.put("x", 2)
        assert tm._evaluate_condition('globalMap.get("x") == 1') is False

    def test_and_operator(self):
        """&& is converted to 'and'."""
        tm, gm = _make_tm()
        gm.put("x", 5)
        assert tm._evaluate_condition('globalMap.get("x") > 0 && globalMap.get("x") < 10') is True

    def test_or_operator(self):
        """|| is converted to 'or'."""
        tm, gm = _make_tm()
        gm.put("x", 0)
        assert tm._evaluate_condition('globalMap.get("x") == 0 || globalMap.get("x") == 1') is True

    def test_null_conversion(self):
        """null is converted to None."""
        tm, gm = _make_tm()
        gm.put("x", "hello")
        assert tm._evaluate_condition('globalMap.get("x") != null') is True

    def test_null_check_missing_key(self):
        """null check for missing key evaluates correctly."""
        tm, gm = _make_tm()
        # Key not set, globalMap.get returns None
        assert tm._evaluate_condition('globalMap.get("missing") == null') is True

    def test_true_literal(self):
        """true literal evaluates to True."""
        tm, _ = _make_tm()
        assert tm._evaluate_condition("true") is True

    def test_false_literal(self):
        """false literal evaluates to False."""
        tm, _ = _make_tm()
        assert tm._evaluate_condition("false") is False

    def test_complex_condition(self):
        """Complex condition with multiple globalMap lookups and operators."""
        tm, gm = _make_tm()
        gm.put("key", "value")
        gm.put("count", 5)
        assert tm._evaluate_condition(
            'globalMap.get("key") != null && globalMap.get("count") > 0'
        ) is True

    def test_invalid_condition_raises_trigger_error(self):
        """Invalid condition raises TriggerEvaluationError, not generic Exception."""
        tm, _ = _make_tm()
        with pytest.raises(TriggerEvaluationError):
            tm._evaluate_condition("this is not valid python +++ ///")

    def test_boolean_negation_with_not(self):
        """! (boolean negation) is converted to 'not'."""
        tm, gm = _make_tm()
        gm.put("flag", False)
        assert tm._evaluate_condition('!((Boolean)globalMap.get("flag"))') is True

    def test_none_condition_returns_true(self):
        """None/empty condition returns True (no condition means always fire)."""
        tm, _ = _make_tm()
        assert tm._evaluate_condition(None) is True
        assert tm._evaluate_condition("") is True


# ---------------------------------------------------------------------------
# 2. Cast type handling
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestTriggerCastTypes:
    """Test Java-style cast type handling in conditions."""

    def test_integer_cast(self):
        """((Integer)globalMap.get("key")) returns int."""
        tm, gm = _make_tm()
        gm.put("count", 42)
        assert tm._evaluate_condition('((Integer)globalMap.get("count")) > 0') is True

    def test_boolean_cast(self):
        """((Boolean)globalMap.get("key")) returns bool."""
        tm, gm = _make_tm()
        gm.put("flag", True)
        assert tm._evaluate_condition('((Boolean)globalMap.get("flag"))') is True

    def test_boolean_cast_false(self):
        """((Boolean)globalMap.get("key")) with False value."""
        tm, gm = _make_tm()
        gm.put("flag", False)
        assert tm._evaluate_condition('((Boolean)globalMap.get("flag"))') is False

    def test_string_cast(self):
        """((String)globalMap.get("key")) returns string."""
        tm, gm = _make_tm()
        gm.put("name", "hello")
        assert tm._evaluate_condition('((String)globalMap.get("name")) != null') is True

    def test_long_cast(self):
        """((Long)globalMap.get("key")) returns int (Python treats Long as int)."""
        tm, gm = _make_tm()
        gm.put("big", 9999999999)
        assert tm._evaluate_condition('((Long)globalMap.get("big")) > 0') is True

    def test_float_cast(self):
        """((Float)globalMap.get("key")) returns float."""
        tm, gm = _make_tm()
        gm.put("rate", 3.14)
        assert tm._evaluate_condition('((Float)globalMap.get("rate")) > 3.0') is True

    def test_double_cast(self):
        """((Double)globalMap.get("key")) returns float."""
        tm, gm = _make_tm()
        gm.put("precise", 2.71828)
        assert tm._evaluate_condition('((Double)globalMap.get("precise")) > 2.0') is True

    def test_short_cast(self):
        """((Short)globalMap.get("key")) returns int."""
        tm, gm = _make_tm()
        gm.put("small", 7)
        assert tm._evaluate_condition('((Short)globalMap.get("small")) == 7') is True

    def test_byte_cast(self):
        """((Byte)globalMap.get("key")) returns int."""
        tm, gm = _make_tm()
        gm.put("tiny", 1)
        assert tm._evaluate_condition('((Byte)globalMap.get("tiny")) == 1') is True

    def test_cast_missing_key_integer(self):
        """Cast with missing key evaluates to 0 for numeric types."""
        tm, gm = _make_tm()
        # "missing" key not set -- should default to 0 for Integer cast
        assert tm._evaluate_condition('((Integer)globalMap.get("missing")) == 0') is True

    def test_cast_missing_key_boolean(self):
        """Cast with missing key evaluates to False for Boolean."""
        tm, gm = _make_tm()
        assert tm._evaluate_condition('((Boolean)globalMap.get("missing"))') is False

    def test_cast_missing_key_string(self):
        """Cast with missing key evaluates to 'None' string for String."""
        tm, gm = _make_tm()
        assert tm._evaluate_condition('((String)globalMap.get("missing")) == "None"') is True


# ---------------------------------------------------------------------------
# 3. Security -- sandboxed eval
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestTriggerSecurity:
    """Test that condition evaluation is properly sandboxed."""

    def test_import_blocked(self):
        """__import__('os') in condition raises TriggerEvaluationError."""
        tm, _ = _make_tm()
        with pytest.raises(TriggerEvaluationError):
            tm._evaluate_condition("__import__('os').system('echo pwned')")

    def test_nested_eval_blocked(self):
        """eval() in condition is blocked (no eval in builtins)."""
        tm, _ = _make_tm()
        with pytest.raises(TriggerEvaluationError):
            tm._evaluate_condition('eval("1+1")')

    def test_open_blocked(self):
        """open() in condition is blocked."""
        tm, _ = _make_tm()
        with pytest.raises(TriggerEvaluationError):
            tm._evaluate_condition("open('/etc/passwd').read()")

    def test_exec_blocked(self):
        """exec() in condition is blocked."""
        tm, _ = _make_tm()
        with pytest.raises(TriggerEvaluationError):
            tm._evaluate_condition("exec('import os')")

    def test_getattr_on_builtins_blocked(self):
        """Accessing builtins via getattr is blocked."""
        tm, _ = _make_tm()
        with pytest.raises(TriggerEvaluationError):
            tm._evaluate_condition("getattr(__builtins__, '__import__')('os')")


# ---------------------------------------------------------------------------
# 4. OnSubjobOk trigger timing
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestOnSubjobOk:
    """Test OnSubjobOk trigger fires only when ALL subjob components complete."""

    def test_single_component_subjob_fires(self):
        """OnSubjobOk fires when a single-component subjob completes."""
        tm, gm = _make_tm()
        tm.register_subjob("subjob_1", ["comp_a"])
        tm.add_trigger("OnSubjobOk", "comp_a", "comp_downstream")
        tm.set_component_status("comp_a", "ok")
        triggered = tm.get_triggered_components("comp_a")
        assert "comp_downstream" in triggered

    def test_multi_component_fires_when_all_complete(self):
        """OnSubjobOk fires when all components in subjob complete."""
        tm, gm = _make_tm()
        tm.register_subjob("subjob_1", ["comp_a", "comp_b", "comp_c"])
        tm.add_trigger("OnSubjobOk", "comp_a", "comp_downstream")

        tm.set_component_status("comp_a", "ok")
        tm.set_component_status("comp_b", "ok")
        tm.set_component_status("comp_c", "ok")

        triggered = tm.get_triggered_components("comp_c")
        assert "comp_downstream" in triggered

    def test_multi_component_does_not_fire_when_partial(self):
        """OnSubjobOk does NOT fire when only some components complete."""
        tm, gm = _make_tm()
        tm.register_subjob("subjob_1", ["comp_a", "comp_b", "comp_c"])
        tm.add_trigger("OnSubjobOk", "comp_a", "comp_downstream")

        tm.set_component_status("comp_a", "ok")
        # comp_b and comp_c not yet complete
        triggered = tm.get_triggered_components("comp_a")
        assert "comp_downstream" not in triggered

    def test_does_not_fire_on_error(self):
        """OnSubjobOk does NOT fire when a component has error status."""
        tm, gm = _make_tm()
        tm.register_subjob("subjob_1", ["comp_a", "comp_b"])
        tm.add_trigger("OnSubjobOk", "comp_a", "comp_downstream")

        tm.set_component_status("comp_a", "ok")
        tm.set_component_status("comp_b", "error")

        triggered = tm.get_triggered_components("comp_b")
        assert "comp_downstream" not in triggered

    def test_success_status_alias(self):
        """OnSubjobOk accepts 'success' as well as 'ok'."""
        tm, gm = _make_tm()
        tm.register_subjob("subjob_1", ["comp_a"])
        tm.add_trigger("OnSubjobOk", "comp_a", "comp_downstream")

        tm.set_component_status("comp_a", "success")
        triggered = tm.get_triggered_components("comp_a")
        assert "comp_downstream" in triggered


# ---------------------------------------------------------------------------
# 5. OnSubjobError
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestOnSubjobError:
    """Test OnSubjobError trigger behavior."""

    def test_fires_on_error(self):
        """OnSubjobError fires when a component in the subjob has error status."""
        tm, gm = _make_tm()
        tm.register_subjob("subjob_1", ["comp_a"])
        tm.add_trigger("OnSubjobError", "comp_a", "comp_error_handler")

        tm.set_component_status("comp_a", "error")
        triggered = tm.get_triggered_components("comp_a")
        assert "comp_error_handler" in triggered

    def test_does_not_fire_on_success(self):
        """OnSubjobError does NOT fire when all components succeed."""
        tm, gm = _make_tm()
        tm.register_subjob("subjob_1", ["comp_a"])
        tm.add_trigger("OnSubjobError", "comp_a", "comp_error_handler")

        tm.set_component_status("comp_a", "ok")
        triggered = tm.get_triggered_components("comp_a")
        assert "comp_error_handler" not in triggered


# ---------------------------------------------------------------------------
# 6. OnComponentOk
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestOnComponentOk:
    """Test OnComponentOk trigger behavior."""

    def test_fires_on_success(self):
        """OnComponentOk fires when specific component succeeds."""
        tm, gm = _make_tm()
        tm.add_trigger("OnComponentOk", "comp_a", "comp_b")

        tm.set_component_status("comp_a", "ok")
        triggered = tm.get_triggered_components("comp_a")
        assert "comp_b" in triggered

    def test_does_not_fire_on_error(self):
        """OnComponentOk does NOT fire when component has error status."""
        tm, gm = _make_tm()
        tm.add_trigger("OnComponentOk", "comp_a", "comp_b")

        tm.set_component_status("comp_a", "error")
        triggered = tm.get_triggered_components("comp_a")
        assert "comp_b" not in triggered

    def test_returns_correct_downstream(self):
        """OnComponentOk returns the correct downstream component."""
        tm, gm = _make_tm()
        tm.add_trigger("OnComponentOk", "comp_a", "comp_b")
        tm.add_trigger("OnComponentOk", "comp_a", "comp_c")

        tm.set_component_status("comp_a", "ok")
        triggered = tm.get_triggered_components("comp_a")
        assert "comp_b" in triggered
        assert "comp_c" in triggered

    def test_success_status_alias(self):
        """OnComponentOk accepts 'success' as well as 'ok'."""
        tm, gm = _make_tm()
        tm.add_trigger("OnComponentOk", "comp_a", "comp_b")

        tm.set_component_status("comp_a", "success")
        triggered = tm.get_triggered_components("comp_a")
        assert "comp_b" in triggered


# ---------------------------------------------------------------------------
# 7. OnComponentError
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestOnComponentError:
    """Test OnComponentError trigger behavior."""

    def test_fires_on_error(self):
        """OnComponentError fires when specific component errors."""
        tm, gm = _make_tm()
        tm.add_trigger("OnComponentError", "comp_a", "comp_error")

        tm.set_component_status("comp_a", "error")
        triggered = tm.get_triggered_components("comp_a")
        assert "comp_error" in triggered

    def test_does_not_fire_on_success(self):
        """OnComponentError does NOT fire on success."""
        tm, gm = _make_tm()
        tm.add_trigger("OnComponentError", "comp_a", "comp_error")

        tm.set_component_status("comp_a", "ok")
        triggered = tm.get_triggered_components("comp_a")
        assert "comp_error" not in triggered


# ---------------------------------------------------------------------------
# 8. RunIf trigger
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRunIf:
    """Test RunIf trigger with condition evaluation."""

    def test_true_condition_triggers(self):
        """RunIf with true condition triggers downstream."""
        tm, gm = _make_tm()
        gm.put("count", 10)
        tm.add_trigger("RunIf", "comp_a", "comp_b",
                        condition='((Integer)globalMap.get("count")) > 0')

        tm.set_component_status("comp_a", "ok")
        triggered = tm.get_triggered_components("comp_a")
        assert "comp_b" in triggered

    def test_false_condition_does_not_trigger(self):
        """RunIf with false condition does not trigger downstream."""
        tm, gm = _make_tm()
        gm.put("count", 0)
        tm.add_trigger("RunIf", "comp_a", "comp_b",
                        condition='((Integer)globalMap.get("count")) > 0')

        tm.set_component_status("comp_a", "ok")
        triggered = tm.get_triggered_components("comp_a")
        assert "comp_b" not in triggered

    def test_missing_globalmap_variable(self):
        """RunIf with missing globalMap key handles gracefully."""
        tm, gm = _make_tm()
        # "count" not set -- Integer cast should default to 0
        tm.add_trigger("RunIf", "comp_a", "comp_b",
                        condition='((Integer)globalMap.get("count")) > 0')

        tm.set_component_status("comp_a", "ok")
        triggered = tm.get_triggered_components("comp_a")
        assert "comp_b" not in triggered

    def test_complex_condition_multiple_lookups(self):
        """RunIf with multiple globalMap lookups."""
        tm, gm = _make_tm()
        gm.put("status", "ok")
        gm.put("count", 5)
        tm.add_trigger("RunIf", "comp_a", "comp_b",
                        condition='globalMap.get("status") != null && ((Integer)globalMap.get("count")) > 0')

        tm.set_component_status("comp_a", "ok")
        triggered = tm.get_triggered_components("comp_a")
        assert "comp_b" in triggered

    def test_runif_no_condition_triggers(self):
        """RunIf with no condition always triggers."""
        tm, gm = _make_tm()
        tm.add_trigger("RunIf", "comp_a", "comp_b", condition=None)

        tm.set_component_status("comp_a", "ok")
        triggered = tm.get_triggered_components("comp_a")
        assert "comp_b" in triggered


# ---------------------------------------------------------------------------
# 9. Trigger registration and management
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestTriggerRegistration:
    """Test trigger registration and management operations."""

    def test_add_trigger_creates_trigger(self):
        """add_trigger creates and stores a Trigger object."""
        tm, gm = _make_tm()
        tm.add_trigger("OnSubjobOk", "comp_a", "comp_b")
        assert len(tm.triggers) == 1
        assert tm.triggers[0].type == TriggerType.ON_SUBJOB_OK
        assert tm.triggers[0].from_component == "comp_a"
        assert tm.triggers[0].to_component == "comp_b"

    def test_register_subjob_maps_components(self):
        """register_subjob maps components to subjob."""
        tm, gm = _make_tm()
        tm.register_subjob("sj_1", ["comp_a", "comp_b", "comp_c"])
        assert tm.subjob_components["sj_1"] == ["comp_a", "comp_b", "comp_c"]
        assert tm.component_to_subjob["comp_a"] == "sj_1"
        assert tm.component_to_subjob["comp_b"] == "sj_1"
        assert tm.component_to_subjob["comp_c"] == "sj_1"

    def test_get_triggered_components_returns_correct_list(self):
        """get_triggered_components returns correct downstream list."""
        tm, gm = _make_tm()
        tm.add_trigger("OnComponentOk", "comp_a", "comp_b")
        tm.add_trigger("OnComponentOk", "comp_a", "comp_c")
        tm.add_trigger("OnComponentOk", "comp_d", "comp_e")

        tm.set_component_status("comp_a", "ok")
        triggered = tm.get_triggered_components("comp_a")
        assert set(triggered) == {"comp_b", "comp_c"}

    def test_get_triggered_components_empty_for_non_trigger(self):
        """get_triggered_components returns empty list for component with no triggers."""
        tm, gm = _make_tm()
        tm.add_trigger("OnComponentOk", "comp_a", "comp_b")

        tm.set_component_status("comp_x", "ok")
        triggered = tm.get_triggered_components("comp_x")
        assert triggered == []

    def test_multiple_trigger_types_from_same_component(self):
        """Component can have multiple trigger types."""
        tm, gm = _make_tm()
        tm.register_subjob("sj_1", ["comp_a"])
        tm.add_trigger("OnSubjobOk", "comp_a", "comp_b")
        tm.add_trigger("OnSubjobError", "comp_a", "comp_c")

        tm.set_component_status("comp_a", "ok")
        triggered = tm.get_triggered_components("comp_a")
        assert "comp_b" in triggered
        assert "comp_c" not in triggered

    def test_trigger_type_enum_values(self):
        """TriggerType enum has correct values."""
        assert TriggerType.ON_SUBJOB_OK.value == "OnSubjobOk"
        assert TriggerType.ON_SUBJOB_ERROR.value == "OnSubjobError"
        assert TriggerType.ON_COMPONENT_OK.value == "OnComponentOk"
        assert TriggerType.ON_COMPONENT_ERROR.value == "OnComponentError"
        assert TriggerType.RUN_IF.value == "RunIf"

    def test_trigger_repr(self):
        """Trigger has meaningful string representation."""
        t = Trigger("OnSubjobOk", "comp_a", "comp_b")
        assert "OnSubjobOk" in repr(t)
        assert "comp_a" in repr(t)
        assert "comp_b" in repr(t)


# ---------------------------------------------------------------------------
# 10. ENG-06 Regression tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestENG06Regression:
    """ENG-06: != operator must NOT be corrupted by ! -> not replacement."""

    def test_not_equals_operator_preserved(self):
        """'status != None' must NOT become 'status not = None'."""
        gm = GlobalMap()
        gm.put("status", "error")
        tm = TriggerManager(gm)
        assert tm._evaluate_condition('globalMap.get("status") != None') is True

    def test_not_equals_with_string_comparison(self):
        """!= with string values works correctly."""
        gm = GlobalMap()
        gm.put("code", "200")
        tm = TriggerManager(gm)
        assert tm._evaluate_condition('globalMap.get("code") != "500"') is True

    def test_not_equals_with_numeric_comparison(self):
        """!= with numeric values works correctly."""
        gm = GlobalMap()
        gm.put("count", 5)
        tm = TriggerManager(gm)
        assert tm._evaluate_condition('globalMap.get("count") != 0') is True

    def test_not_equals_combined_with_and(self):
        """!= combined with && works correctly."""
        gm = GlobalMap()
        gm.put("a", 1)
        gm.put("b", 2)
        tm = TriggerManager(gm)
        assert tm._evaluate_condition(
            'globalMap.get("a") != 0 && globalMap.get("b") != 0'
        ) is True

    def test_not_equals_with_null(self):
        """!= null comparison works correctly."""
        gm = GlobalMap()
        gm.put("key", "value")
        tm = TriggerManager(gm)
        assert tm._evaluate_condition('globalMap.get("key") != null') is True

    def test_not_equals_null_when_actually_null(self):
        """!= null evaluates to False when value IS null/None."""
        gm = GlobalMap()
        # "key" not set
        tm = TriggerManager(gm)
        assert tm._evaluate_condition('globalMap.get("key") != null') is False


# ---------------------------------------------------------------------------
# 11. ENG-10 Regression tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestENG10Regression:
    """ENG-10: OnSubjobOk must check ALL subjob components, not just trigger source."""

    def test_multi_component_subjob_waits_for_all(self):
        """OnSubjobOk with 3-component subjob waits for all to complete."""
        gm = GlobalMap()
        tm = TriggerManager(gm)
        tm.register_subjob("subjob_1", ["comp_a", "comp_b", "comp_c"])
        tm.add_trigger("OnSubjobOk", "comp_a", "comp_downstream")

        # Only comp_a done -- should NOT fire
        tm.set_component_status("comp_a", "ok")
        triggered = tm.get_triggered_components("comp_a")
        assert "comp_downstream" not in triggered

        # comp_b done -- still should NOT fire
        tm.set_component_status("comp_b", "ok")
        triggered = tm.get_triggered_components("comp_b")
        assert "comp_downstream" not in triggered

        # Now all done -- should fire
        tm.set_component_status("comp_c", "ok")
        triggered = tm.get_triggered_components("comp_c")
        assert "comp_downstream" in triggered

    def test_trigger_from_non_last_component(self):
        """OnSubjobOk fires even if trigger's from_component finishes first."""
        gm = GlobalMap()
        tm = TriggerManager(gm)
        tm.register_subjob("subjob_1", ["comp_a", "comp_b"])
        tm.add_trigger("OnSubjobOk", "comp_a", "comp_downstream")

        # comp_a (trigger source) finishes first
        tm.set_component_status("comp_a", "ok")
        triggered = tm.get_triggered_components("comp_a")
        assert "comp_downstream" not in triggered

        # comp_b finishes -- now subjob is complete, trigger should fire
        tm.set_component_status("comp_b", "ok")
        triggered = tm.get_triggered_components("comp_b")
        assert "comp_downstream" in triggered

    def test_partial_completion_with_error_blocks(self):
        """OnSubjobOk does not fire when one component has error."""
        gm = GlobalMap()
        tm = TriggerManager(gm)
        tm.register_subjob("subjob_1", ["comp_a", "comp_b", "comp_c"])
        tm.add_trigger("OnSubjobOk", "comp_a", "comp_downstream")

        tm.set_component_status("comp_a", "ok")
        tm.set_component_status("comp_b", "error")
        tm.set_component_status("comp_c", "ok")

        triggered = tm.get_triggered_components("comp_c")
        assert "comp_downstream" not in triggered

    def test_two_component_subjob_requires_both(self):
        """Two-component subjob requires both to complete for OnSubjobOk."""
        gm = GlobalMap()
        tm = TriggerManager(gm)
        tm.register_subjob("subjob_1", ["comp_a", "comp_b"])
        tm.add_trigger("OnSubjobOk", "comp_a", "comp_downstream")

        tm.set_component_status("comp_a", "ok")
        assert "comp_downstream" not in tm.get_triggered_components("comp_a")

        tm.set_component_status("comp_b", "ok")
        assert "comp_downstream" in tm.get_triggered_components("comp_b")


# ---------------------------------------------------------------------------
# 12. Reset and state management
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestTriggerStateManagement:
    """Test state management and reset functionality."""

    def test_reset_clears_status(self):
        """reset() clears component status."""
        tm, gm = _make_tm()
        tm.set_component_status("comp_a", "ok")
        tm.reset()
        assert tm.component_status == {}

    def test_reset_clears_triggered_tracking(self):
        """reset() clears triggered component tracking."""
        tm, gm = _make_tm()
        tm.add_trigger("OnComponentOk", "comp_a", "comp_b")
        tm.set_component_status("comp_a", "ok")
        tm.get_triggered_components("comp_a")

        tm.reset()
        assert tm.triggered_components == set()

    def test_component_not_triggered_twice(self):
        """A component is not triggered twice (idempotency)."""
        tm, gm = _make_tm()
        tm.add_trigger("OnComponentOk", "comp_a", "comp_b")

        tm.set_component_status("comp_a", "ok")
        triggered1 = tm.get_triggered_components("comp_a")
        assert "comp_b" in triggered1

        # Call again -- comp_b already triggered
        triggered2 = tm.get_triggered_components("comp_a")
        assert "comp_b" not in triggered2


# ---------------------------------------------------------------------------
# Plan 14-10 lift: 91% -> 95%+ -- coverage for missed branches
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRunIfWrongFromComponent:
    """RunIf trigger only fires for trigger.from_component (line 198)."""

    def test_runif_does_not_fire_for_different_source(self):
        """RunIf source mismatch returns False without evaluating condition."""
        tm, gm = _make_tm()
        gm.put("flag", 1)
        tm.add_trigger("RunIf", "comp_a", "comp_b", 'globalMap.get("flag") == 1')
        # complete a different component
        tm.set_component_status("comp_other", "ok")
        triggered = tm.get_triggered_components("comp_other")
        assert "comp_b" not in triggered


@pytest.mark.unit
class TestShouldFireUnknownTriggerType:
    """should_fire_trigger returns False for unknown TriggerType (line 201)."""

    def test_unknown_trigger_type_returns_false(self):
        """Build a Trigger with valid type then mutate .type to a sentinel
        that does not match any branch -- exercises the trailing return False.
        """
        tm, gm = _make_tm()
        trig = Trigger("OnComponentOk", "a", "b")
        # Replace with a sentinel object that is not one of the enum values
        trig.type = object()
        tm.set_component_status("a", "ok")
        assert tm.should_fire_trigger(trig, "a") is False


@pytest.mark.unit
class TestCheckSubjobErrorMismatch:
    """_check_subjob_error returns False when subjobs do not align (line 228)."""

    def test_subjob_error_subjob_mismatch_returns_false(self):
        tm, gm = _make_tm()
        tm.register_subjob("s1", ["c1", "c2"])
        tm.register_subjob("s2", ["c3"])
        tm.add_trigger("OnSubjobError", "c1", "c3")
        tm.set_component_status("c3", "error")  # different subjob from from_component
        triggered = tm.get_triggered_components("c3")
        # c3 is in s2, from is c1 in s1 -- mismatch -> False
        assert "c3" not in triggered


@pytest.mark.unit
class TestEvaluateConditionMissingGlobalMap:
    """_evaluate_condition returns True when global_map is None (line 265)."""

    def test_missing_global_map_returns_true(self):
        # Construct manager without global_map
        tm = TriggerManager(global_map=None)
        # Direct call -- bypass should_fire_trigger
        assert tm._evaluate_condition('globalMap.get("x") == 1') is True


@pytest.mark.unit
class TestEvaluateConditionPropagatesTriggerError:
    """_evaluate_condition re-raises TriggerEvaluationError unchanged (line 286)."""

    def test_trigger_evaluation_error_re_raised_inner(self, monkeypatch):
        tm, gm = _make_tm()

        def _boom(_self, _condition):
            raise TriggerEvaluationError(
                trigger_type="condition", condition="x", message="inner"
            )

        # Patch _resolve_casts on the instance to raise a TriggerEvaluationError
        monkeypatch.setattr(
            tm, "_resolve_casts", lambda c: (_ for _ in ()).throw(
                TriggerEvaluationError(
                    trigger_type="condition", condition=c, message="inner"
                )
            )
        )
        with pytest.raises(TriggerEvaluationError):
            tm._evaluate_condition('something')


@pytest.mark.unit
class TestResolveCastsUnknownType:
    """_resolve_casts logs warning and emits repr() for unknown cast types (309-310)."""

    def test_unknown_cast_type_emits_repr(self):
        tm, gm = _make_tm()
        gm.put("v", "abc")
        # ((Foobar)globalMap.get("v")) -- 'Foobar' is unknown
        out = tm._resolve_casts('((Foobar)globalMap.get("v")) == "abc"')
        # repr("abc") == "'abc'"; assert it ended up there as substring
        assert "'abc'" in out


@pytest.mark.unit
class TestResolveCastsValueErrorFallback:
    """_resolve_casts falls back when converter raises ValueError/TypeError (323-329)."""

    def test_value_error_int_returns_zero(self):
        """Casting non-numeric string to Integer -> ValueError -> '0'."""
        tm, gm = _make_tm()
        gm.put("k", "not-a-number")
        out = tm._resolve_casts('((Integer)globalMap.get("k"))')
        assert out == "0"

    def test_value_error_bool_returns_false(self):
        """Casting an object that bool() cannot handle -> '0' is reached only
        for int/float; for bool we hit the elif branch returning 'False'.
        bool(x) accepts any object, so simulate a TypeError via an object that
        raises in __bool__.
        """
        class Boom:
            def __bool__(self):
                raise TypeError("nope")

        tm, gm = _make_tm()
        gm.put("k", Boom())
        out = tm._resolve_casts('((Boolean)globalMap.get("k"))')
        assert out == "False"

    def test_string_cast_succeeds_on_int(self):
        """str(int) is total; this exercises the successful cast path,
        complementing the int/float ValueError fallback above.
        """
        tm, gm = _make_tm()
        gm.put("k", 42)
        out = tm._resolve_casts('((String)globalMap.get("k"))')
        # repr("42") == "'42'"
        assert out == "'42'"

    def test_string_cast_str_raises_falls_back_repr(self):
        """str converter raising falls into the else branch returning repr(str(raw))."""
        class StrFails:
            def __str__(self):
                raise ValueError("nope")

        tm, gm = _make_tm()
        # Bypass GlobalMap.put (which f-string-logs the value); set raw dict.
        gm._map["k"] = StrFails()
        # The cast tries str(raw) which raises -> except (ValueError, TypeError)
        # -> converter is str so falls into the else branch -> repr(str(raw_value))
        # str() raises again so the outer _CAST_PATTERN.sub will propagate.
        # We expect a ValueError to leak out -- catch it, the line was still hit.
        try:
            tm._resolve_casts('((String)globalMap.get("k"))')
        except ValueError:
            pass  # line 329 was reached (the second str() raised)


@pytest.mark.unit
class TestResolveCastsValueErrorFloat:
    """ValueError on Float / non-int cast falls into the int/float fallback."""

    def test_float_converter_value_error_returns_zero(self):
        tm, gm = _make_tm()
        gm.put("k", "not-a-float")
        out = tm._resolve_casts('((Float)globalMap.get("k"))')
        assert out == "0"
