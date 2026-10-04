"""Tests for TriggerEvaluator — safe condition evaluation."""
import pytest

from src.v2.execution.trigger import TriggerEvaluator
from src.v2.execution.stage import StageStatus
from src.v2.config.job_config import TriggerConnection


class TestTriggerEvaluatorRules:
    """Tests for on_success / on_failure / conditional trigger evaluation."""

    def test_on_success_with_success_status(self):
        trigger = TriggerConnection(source="A", target="B", type="on_success")
        result = TriggerEvaluator.evaluate(trigger, StageStatus.SUCCESS, {})
        assert result is True

    def test_on_success_with_failed_status(self):
        trigger = TriggerConnection(source="A", target="B", type="on_success")
        result = TriggerEvaluator.evaluate(trigger, StageStatus.FAILED, {})
        assert result is False

    def test_on_success_with_skipped_status(self):
        trigger = TriggerConnection(source="A", target="B", type="on_success")
        result = TriggerEvaluator.evaluate(trigger, StageStatus.SKIPPED, {})
        assert result is False

    def test_on_failure_with_failed_status(self):
        trigger = TriggerConnection(source="A", target="B", type="on_failure")
        result = TriggerEvaluator.evaluate(trigger, StageStatus.FAILED, {})
        assert result is True

    def test_on_failure_with_success_status(self):
        trigger = TriggerConnection(source="A", target="B", type="on_failure")
        result = TriggerEvaluator.evaluate(trigger, StageStatus.SUCCESS, {})
        assert result is False

    def test_on_failure_with_skipped_status(self):
        trigger = TriggerConnection(source="A", target="B", type="on_failure")
        result = TriggerEvaluator.evaluate(trigger, StageStatus.SKIPPED, {})
        assert result is False


class TestConditionalEvaluation:
    """Tests for conditional trigger expression evaluation."""

    def test_string_equality_true(self):
        trigger = TriggerConnection(
            source="A", target="B", type="conditional",
            condition="${context.env} == 'PROD'",
        )
        result = TriggerEvaluator.evaluate(
            trigger, StageStatus.SUCCESS, {"env": "PROD"}
        )
        assert result is True

    def test_string_equality_false(self):
        trigger = TriggerConnection(
            source="A", target="B", type="conditional",
            condition="${context.env} == 'PROD'",
        )
        result = TriggerEvaluator.evaluate(
            trigger, StageStatus.SUCCESS, {"env": "DEV"}
        )
        assert result is False

    def test_string_inequality(self):
        trigger = TriggerConnection(
            source="A", target="B", type="conditional",
            condition="${context.env} != 'DEV'",
        )
        result = TriggerEvaluator.evaluate(
            trigger, StageStatus.SUCCESS, {"env": "PROD"}
        )
        assert result is True

    def test_numeric_greater_than_true(self):
        trigger = TriggerConnection(
            source="A", target="B", type="conditional",
            condition="${context.row_count} > 0",
        )
        result = TriggerEvaluator.evaluate(
            trigger, StageStatus.SUCCESS, {"row_count": 100}
        )
        assert result is True

    def test_numeric_greater_than_false(self):
        trigger = TriggerConnection(
            source="A", target="B", type="conditional",
            condition="${context.row_count} > 0",
        )
        result = TriggerEvaluator.evaluate(
            trigger, StageStatus.SUCCESS, {"row_count": 0}
        )
        assert result is False

    def test_numeric_less_than(self):
        trigger = TriggerConnection(
            source="A", target="B", type="conditional",
            condition="${context.error_count} < 10",
        )
        result = TriggerEvaluator.evaluate(
            trigger, StageStatus.SUCCESS, {"error_count": 5}
        )
        assert result is True

    def test_numeric_equality(self):
        trigger = TriggerConnection(
            source="A", target="B", type="conditional",
            condition="${context.flag} == 1",
        )
        result = TriggerEvaluator.evaluate(
            trigger, StageStatus.SUCCESS, {"flag": 1}
        )
        assert result is True

    def test_numeric_greater_equal(self):
        trigger = TriggerConnection(
            source="A", target="B", type="conditional",
            condition="${context.count} >= 10",
        )
        result = TriggerEvaluator.evaluate(
            trigger, StageStatus.SUCCESS, {"count": 10}
        )
        assert result is True

    def test_numeric_less_equal(self):
        trigger = TriggerConnection(
            source="A", target="B", type="conditional",
            condition="${context.count} <= 5",
        )
        result = TriggerEvaluator.evaluate(
            trigger, StageStatus.SUCCESS, {"count": 5}
        )
        assert result is True

    def test_float_comparison(self):
        trigger = TriggerConnection(
            source="A", target="B", type="conditional",
            condition="${context.rate} > 0.5",
        )
        result = TriggerEvaluator.evaluate(
            trigger, StageStatus.SUCCESS, {"rate": 0.75}
        )
        assert result is True

    def test_boolean_and_true(self):
        trigger = TriggerConnection(
            source="A", target="B", type="conditional",
            condition="${context.env} == 'PROD' and ${context.enabled} == true",
        )
        result = TriggerEvaluator.evaluate(
            trigger, StageStatus.SUCCESS, {"env": "PROD", "enabled": True}
        )
        assert result is True

    def test_boolean_and_false(self):
        trigger = TriggerConnection(
            source="A", target="B", type="conditional",
            condition="${context.env} == 'PROD' and ${context.enabled} == true",
        )
        result = TriggerEvaluator.evaluate(
            trigger, StageStatus.SUCCESS, {"env": "PROD", "enabled": False}
        )
        assert result is False

    def test_boolean_or(self):
        trigger = TriggerConnection(
            source="A", target="B", type="conditional",
            condition="${context.env} == 'PROD' or ${context.env} == 'STAGING'",
        )
        result = TriggerEvaluator.evaluate(
            trigger, StageStatus.SUCCESS, {"env": "STAGING"}
        )
        assert result is True

    def test_boolean_not(self):
        trigger = TriggerConnection(
            source="A", target="B", type="conditional",
            condition="not ${context.skip}",
        )
        result = TriggerEvaluator.evaluate(
            trigger, StageStatus.SUCCESS, {"skip": False}
        )
        assert result is True

    def test_parenthesized_expression(self):
        trigger = TriggerConnection(
            source="A", target="B", type="conditional",
            condition="(${context.a} > 1) and (${context.b} < 10)",
        )
        result = TriggerEvaluator.evaluate(
            trigger, StageStatus.SUCCESS, {"a": 5, "b": 3}
        )
        assert result is True

    def test_true_literal(self):
        trigger = TriggerConnection(
            source="A", target="B", type="conditional",
            condition="${context.flag} == true",
        )
        result = TriggerEvaluator.evaluate(
            trigger, StageStatus.SUCCESS, {"flag": True}
        )
        assert result is True

    def test_false_literal(self):
        trigger = TriggerConnection(
            source="A", target="B", type="conditional",
            condition="${context.flag} == false",
        )
        result = TriggerEvaluator.evaluate(
            trigger, StageStatus.SUCCESS, {"flag": False}
        )
        assert result is True

    def test_null_comparison(self):
        trigger = TriggerConnection(
            source="A", target="B", type="conditional",
            condition="${context.val} != null",
        )
        result = TriggerEvaluator.evaluate(
            trigger, StageStatus.SUCCESS, {"val": "something"}
        )
        assert result is True

    def test_conditional_on_skipped_source_returns_false(self):
        """Conditional triggers don't fire if source stage was skipped."""
        trigger = TriggerConnection(
            source="A", target="B", type="conditional",
            condition="${context.env} == 'PROD'",
        )
        result = TriggerEvaluator.evaluate(
            trigger, StageStatus.SKIPPED, {"env": "PROD"}
        )
        assert result is False

    def test_unresolved_context_var_raises(self):
        """Missing context variable in condition should raise."""
        trigger = TriggerConnection(
            source="A", target="B", type="conditional",
            condition="${context.missing} > 0",
        )
        with pytest.raises(ValueError, match="[Uu]nresolved|[Uu]nknown|[Mm]issing"):
            TriggerEvaluator.evaluate(
                trigger, StageStatus.SUCCESS, {}
            )

    def test_double_quoted_strings(self):
        trigger = TriggerConnection(
            source="A", target="B", type="conditional",
            condition='${context.env} == "PROD"',
        )
        result = TriggerEvaluator.evaluate(
            trigger, StageStatus.SUCCESS, {"env": "PROD"}
        )
        assert result is True
