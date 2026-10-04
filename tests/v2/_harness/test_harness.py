"""Self-tests for the ComponentTestCase harness.

Validates that the harness base class works correctly using the existing
Filter component (registered as "filter") as the test subject.  These
tests verify:

1. run_component with valid config creates, validates, and applies
2. run_component with invalid config + expect_validation_errors returns errors
3. run_component with invalid config raises AssertionError (gate catches it)
4. _dict_to_lazyframe converts column-oriented dict correctly
5. assert_frame_equal passes for matching frames and fails for mismatched
"""
import pytest
import polars as pl

from tests.v2._harness.component_test_case import ComponentTestCase


class TestHarness(ComponentTestCase):
    """Verify the harness itself works using the existing Filter component."""

    component_type = "filter"

    def test_run_component_valid(self):
        """run_component with valid config calls validate() then apply()."""
        result = self.run_component(
            config={"condition": "amount > 100"},
            inputs={"main": pl.DataFrame({"amount": [50, 150, 200]}).lazy()},
        )
        assert "main" in result
        collected = result["main"].collect()
        assert len(collected) == 2

    def test_run_component_validation_gate(self):
        """run_component with invalid config and expect_validation_errors=True returns errors."""
        result = self.run_component(
            config={},  # missing 'condition'
            expect_validation_errors=True,
        )
        assert "_validation_errors" in result

    def test_run_component_validation_gate_catches_invalid(self):
        """run_component with invalid config raises when expect_validation_errors=False."""
        with pytest.raises(AssertionError):
            self.run_component(config={})  # missing 'condition', should fail validate

    def test_dict_to_lazyframe(self):
        """_dict_to_lazyframe converts column-oriented dict to LazyFrame."""
        lf = self._dict_to_lazyframe({"a": [1, 2], "b": ["x", "y"]})
        assert isinstance(lf, pl.LazyFrame)
        df = lf.collect()
        assert df["a"].to_list() == [1, 2]
        assert df["b"].to_list() == ["x", "y"]

    def test_assert_frame_equal_pass(self):
        """assert_frame_equal passes for matching frames."""
        lf = pl.DataFrame({"a": [1, 2]}).lazy()
        self.assert_frame_equal(lf, {"a": [1, 2]})

    def test_assert_frame_equal_fail(self):
        """assert_frame_equal fails for mismatched frames."""
        lf = pl.DataFrame({"a": [1, 2]}).lazy()
        with pytest.raises(AssertionError):
            self.assert_frame_equal(lf, {"a": [3, 4]})
