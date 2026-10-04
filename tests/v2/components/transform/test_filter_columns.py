"""Standard tests for FilterColumns component (COMP-01 prover).

Subclasses ComponentTestCase to get:
  - validate-before-apply enforcement (D-14)
  - golden-case parametrized loading (D-13)
  - integration-through-PyETLEngine (D-11)
  - benchmark pair quarantined behind @pytest.mark.benchmark (D-16)
"""
import time

import pytest
import polars as pl

from tests.v2._harness.component_test_case import ComponentTestCase
from src.v2.components.transform.filter_columns import FilterColumns


class TestFilterColumns(ComponentTestCase):
    """Full standard test class for FilterColumns."""

    component_type = "filter_columns"
    component_class = FilterColumns
    golden_dir = "filter_columns_cases"

    # ---- Golden-case tests (D-12, D-13) ----

    def test_golden_cases(self):
        """Parametrized golden-case tests loaded from filter_columns_cases/*.json."""
        cases = self.load_golden_cases()
        assert len(cases) > 0, f"No golden cases found in {self.golden_dir}"

        for case in cases:
            case_id = case.get("case_id", "unknown")
            config = case["config"]
            inputs = {
                name: self._dict_to_lazyframe(data)
                for name, data in case["inputs"].items()
            }
            expected = case["expected"]

            result = self.run_component(config=config, inputs=inputs)

            for output_name, expected_data in expected.items():
                assert output_name in result, (
                    f"Case {case_id}: expected output '{output_name}' not in result"
                )
                self.assert_frame_equal(
                    result[output_name], expected_data
                )

    # ---- Validation tests ----

    def test_validate_missing_columns(self):
        """Missing 'columns' config triggers validation error."""
        result = self.run_component(
            config={},
            expect_validation_errors=True,
        )
        assert "_validation_errors" in result

    def test_validate_invalid_mode(self):
        """Invalid 'mode' triggers validation error."""
        result = self.run_component(
            config={"columns": ["id"], "mode": "invalid"},
            expect_validation_errors=True,
        )
        assert "_validation_errors" in result

    # ---- Behavior tests ----

    def test_keep_mode_default(self):
        """Default mode is 'keep'."""
        result = self.run_component(
            config={"columns": ["id"]},
            inputs={"main": pl.DataFrame({"id": [1], "name": ["a"]}).lazy()},
        )
        collected = result["main"].collect()
        assert collected.columns == ["id"]

    def test_remove_mode(self):
        """Remove mode drops listed columns."""
        result = self.run_component(
            config={"columns": ["name"], "mode": "remove"},
            inputs={"main": pl.DataFrame({"id": [1], "name": ["a"], "amount": [100]}).lazy()},
        )
        collected = result["main"].collect()
        assert "name" not in collected.columns
        assert "id" in collected.columns
        assert "amount" in collected.columns

    def test_no_main_input(self):
        """No main input returns empty dict."""
        result = self.run_component(
            config={"columns": ["id"]},
            inputs={},
        )
        assert result == {}

    def test_not_barrier(self):
        """FilterColumns is not a barrier (pure lazy transform)."""
        comp = FilterColumns("fc", {"columns": ["id"]})
        assert comp.is_barrier is False

    # ---- Integration test (D-11) ----

    def test_integration_pipeline(self):
        """Verify FilterColumns resolves from REGISTRY and validates correctly."""
        from src.v2.components.registry import REGISTRY

        cls = REGISTRY.get("filter_columns")
        assert cls is FilterColumns
        comp = cls("fc_integration", {"columns": ["id", "name"]})
        errors = comp.validate()
        assert errors == []

        # Full apply integration
        df = pl.DataFrame({"id": [1, 2], "name": ["A", "B"], "extra": [True, False]}).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect()
        assert collected.columns == ["id", "name"]
        assert len(collected) == 2

    # ---- Benchmark tests (D-16, D-18) ----

    @staticmethod
    def _make_benchmark_data(n: int = 100_000) -> pl.LazyFrame:
        """Create a benchmark dataset."""
        import random
        random.seed(42)
        return pl.DataFrame({
            "id": list(range(n)),
            "name": [f"name_{i}" for i in range(n)],
            "amount": [random.uniform(0, 10000) for _ in range(n)],
            "category": [f"cat_{i % 50}" for i in range(n)],
            "active": [i % 3 != 0 for i in range(n)],
        }).lazy()

    @pytest.mark.benchmark
    def test_benchmark_ratio(self):
        """Verify v2 component is within 10% of raw Polars (D-18)."""
        dataset = self._make_benchmark_data()
        config = {"columns": ["id", "name", "amount"]}
        comp = FilterColumns("bench_ratio", config)

        # Warmup both
        for _ in range(100):
            comp.apply({"main": dataset})["main"].collect()
            dataset.select([pl.col("id"), pl.col("name"), pl.col("amount")]).collect()

        # Run v2
        v2_timings = []
        for _ in range(5):
            start = time.perf_counter_ns()
            result = comp.apply({"main": dataset})
            result["main"].collect()
            v2_timings.append(time.perf_counter_ns() - start)

        # Run raw
        raw_timings = []
        for _ in range(5):
            start = time.perf_counter_ns()
            dataset.select([
                pl.col("id"), pl.col("name"), pl.col("amount")
            ]).collect()
            raw_timings.append(time.perf_counter_ns() - start)

        v2_median = sorted(v2_timings)[len(v2_timings) // 2]
        raw_median = sorted(raw_timings)[len(raw_timings) // 2]

        ratio = v2_median / raw_median if raw_median > 0 else float("inf")
        assert ratio <= 1.10, (
            f"FilterColumns is {ratio:.2f}x slower than raw Polars "
            f"(v2={v2_median / 1e6:.2f}ms, raw={raw_median / 1e6:.2f}ms). "
            f"Must be within 1.10x per D-18."
        )
