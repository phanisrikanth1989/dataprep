"""Standard tests for FilterRows component (COMP-02).

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
from src.v2.components.transform.filter_rows import FilterRows


class TestFilterRows(ComponentTestCase):
    """Full standard test class for FilterRows."""

    component_type = "filter_rows"
    component_class = FilterRows
    golden_dir = "filter_rows_cases"

    # ---- Golden-case tests (D-12, D-13) ----

    def test_golden_cases(self):
        """Parametrized golden-case tests loaded from filter_rows_cases/*.json."""
        cases = self.load_golden_cases()
        assert len(cases) > 0, f"No golden cases found in {self.golden_dir}"

        for case in cases:
            case_id = case.get("case_id", "unknown")
            config = case["config"]
            inputs = {name: self._dict_to_lazyframe(data) for name, data in case["inputs"].items()}
            expected = case["expected"]

            result = self.run_component(config=config, inputs=inputs)

            for output_name, expected_data in expected.items():
                assert output_name in result, f"Case {case_id}: expected output '{output_name}' not in result"
                self.assert_frame_equal(result[output_name], expected_data)

    # ---- Validation tests ----

    def test_validate_missing_condition(self):
        """Missing 'condition' config triggers validation error."""
        result = self.run_component(
            config={},
            expect_validation_errors=True,
        )
        assert "_validation_errors" in result

    # ---- Behavior tests ----

    def test_basic_filter(self):
        """Filter amount > 100 on a 4-row frame keeps 2 rows."""
        df = pl.DataFrame(
            {
                "id": [1, 2, 3, 4],
                "amount": [50, 150, 100, 200],
            }
        ).lazy()
        result = self.run_component(
            config={"condition": "amount > 100"},
            inputs={"main": df},
        )
        collected = result["main"].collect()
        assert len(collected) == 2
        assert collected["amount"].to_list() == [150, 200]

    def test_reject_output_complement(self):
        """With reject_output=True, main + reject rows equal input rows."""
        df = pl.DataFrame(
            {
                "id": [1, 2, 3, 4, 5],
                "amount": [50, 150, 100, 200, 75],
            }
        ).lazy()
        result = self.run_component(
            config={"condition": "amount > 100", "reject_output": True},
            inputs={"main": df},
        )
        assert "main" in result
        assert "reject" in result

        main_df = result["main"].collect()
        reject_df = result["reject"].collect()

        # Main + reject = total input
        assert len(main_df) + len(reject_df) == 5

        # Check that main has the matching rows and reject has the complement
        main_ids = sorted(main_df["id"].to_list())
        reject_ids = sorted(reject_df["id"].to_list())
        assert main_ids == [2, 4]
        assert reject_ids == [1, 3, 5]

    def test_no_main_input(self):
        """No main input returns empty dict."""
        result = self.run_component(
            config={"condition": "amount > 100"},
            inputs={},
        )
        assert result == {}

    def test_string_filter(self):
        """Filter status == 'active' keeps only active rows."""
        df = pl.DataFrame(
            {
                "id": [1, 2, 3],
                "status": ["active", "inactive", "active"],
            }
        ).lazy()
        result = self.run_component(
            config={"condition": "status == 'active'"},
            inputs={"main": df},
        )
        collected = result["main"].collect()
        assert len(collected) == 2
        assert collected["id"].to_list() == [1, 3]

    def test_compound_and_condition(self):
        """Filter amount > 50 && status == 'active' matches both conditions."""
        df = pl.DataFrame(
            {
                "id": [1, 2, 3, 4],
                "amount": [100, 30, 200, 10],
                "status": ["active", "active", "inactive", "active"],
            }
        ).lazy()
        result = self.run_component(
            config={"condition": "amount > 50 && status == 'active'"},
            inputs={"main": df},
        )
        collected = result["main"].collect()
        assert len(collected) == 1
        assert collected["id"].to_list() == [1]

    def test_compound_or_condition(self):
        """Filter amount > 200 || status == 'active' matches either condition."""
        df = pl.DataFrame(
            {
                "id": [1, 2, 3, 4],
                "amount": [100, 30, 300, 10],
                "status": ["active", "inactive", "inactive", "active"],
            }
        ).lazy()
        result = self.run_component(
            config={"condition": "amount > 200 || status == 'active'"},
            inputs={"main": df},
        )
        collected = result["main"].collect()
        assert len(collected) == 3
        assert sorted(collected["id"].to_list()) == [1, 3, 4]

    def test_null_filtered_out(self):
        """Null values in filter column are treated as false by Polars filter."""
        df = pl.DataFrame(
            {
                "id": [1, 2, 3],
                "amount": [150, None, 200],
            }
        ).lazy()
        result = self.run_component(
            config={"condition": "amount > 100"},
            inputs={"main": df},
        )
        collected = result["main"].collect()
        assert len(collected) == 2
        assert collected["id"].to_list() == [1, 3]

    def test_special_char_string_filter(self):
        """Filter on string column with spaces in values (review suggestion)."""
        df = pl.DataFrame(
            {
                "id": [1, 2, 3, 4],
                "category": ["foo bar", "baz", "foo bar", "qux"],
            }
        ).lazy()
        result = self.run_component(
            config={"condition": "category == 'foo bar'"},
            inputs={"main": df},
        )
        collected = result["main"].collect()
        assert len(collected) == 2
        assert collected["id"].to_list() == [1, 3]
        assert collected["category"].to_list() == ["foo bar", "foo bar"]

    def test_is_barrier_with_reject(self):
        """is_barrier is True when reject_output is True (review concern from Plan 01)."""
        comp = FilterRows("fr_barrier", {"condition": "true", "reject_output": True})
        assert comp.is_barrier is True

    def test_is_barrier_default_false(self):
        """is_barrier is False when reject_output is not set (single-output mode)."""
        comp = FilterRows("fr_no_barrier", {"condition": "true"})
        assert comp.is_barrier is False

    # ---- Integration tests (D-11) ----

    def test_integration_pipeline(self):
        """Verify FilterRows resolves from REGISTRY and validates correctly."""
        from src.v2.components.registry import REGISTRY

        cls = REGISTRY.get("filter_rows")
        assert cls is FilterRows

        comp = cls("fr_integration", {"condition": "amount > 0"})
        errors = comp.validate()
        assert errors == []

        # Full apply integration
        df = pl.DataFrame(
            {
                "id": [1, 2, 3],
                "amount": [10, -5, 20],
            }
        ).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect()
        assert len(collected) == 2
        assert collected["id"].to_list() == [1, 3]

    def test_integration_through_engine(self, tmp_path):
        """Run FilterRows through PyETLEngine to verify full integration."""
        # Write a CSV for the source component
        csv_file = tmp_path / "input.csv"
        csv_file.write_text("id;amount\n1;50\n2;150\n3;100\n4;200\n")

        job_config = {
            "name": "filter_rows_integration_test",
            "engine": "v2",
            "components": [
                {
                    "id": "src",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(csv_file),
                        "delimiter": ";",
                        "schema": [
                            {"name": "id", "type": "int"},
                            {"name": "amount", "type": "int"},
                        ],
                    },
                },
                {
                    "id": "filter",
                    "type": "filter_rows",
                    "config": {
                        "condition": "amount > 100",
                    },
                },
            ],
            "flows": [
                {
                    "source": "src",
                    "target": "filter",
                    "output": "main",
                    "input": "main",
                },
            ],
        }
        result = self.run_integration(job_config)
        assert result["status"] == "success"

    # ---- Benchmark tests (D-16, D-18) ----

    @staticmethod
    def _make_benchmark_data(n: int = 100_000) -> pl.LazyFrame:
        """Create a benchmark dataset for FilterRows.

        amount is uniform [0, 10000] so threshold selection controls selectivity:
          amount > 9000  -> ~10% pass (high selectivity, most rejected)
          amount > 5000  -> ~50% pass (medium selectivity)
          amount > 1000  -> ~90% pass (low selectivity, few rejected)
        """
        import random

        random.seed(42)
        return pl.DataFrame(
            {
                "id": list(range(n)),
                "name": [f"name_{i}" for i in range(n)],
                "amount": [random.uniform(0, 10000) for _ in range(n)],
                "category": [f"cat_{i % 50}" for i in range(n)],
                "active": [i % 3 != 0 for i in range(n)],
            }
        ).lazy()

    @pytest.mark.benchmark
    def test_benchmark_ratio(self):
        """Verify v2 FilterRows (reject-off) is within 10% of raw Polars (D-18).

        Uses 1M rows so Polars work dominates Python overhead, giving stable ratios.
        """
        dataset = self._make_benchmark_data(n=1_000_000)
        config = {"condition": "amount > 5000"}
        comp = FilterRows("bench_ratio", config)

        # Warmup both
        for _ in range(100):
            comp.apply({"main": dataset})["main"].collect()
            dataset.filter(pl.col("amount") > 5000).collect()

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
            dataset.filter(pl.col("amount") > 5000).collect()
            raw_timings.append(time.perf_counter_ns() - start)

        v2_median = sorted(v2_timings)[len(v2_timings) // 2]
        raw_median = sorted(raw_timings)[len(raw_timings) // 2]

        ratio = v2_median / raw_median if raw_median > 0 else float("inf")
        print(f"FilterRows reject-off: v2={v2_median / 1e6:.2f}ms, raw={raw_median / 1e6:.2f}ms, ratio={ratio:.2f}x")
        assert ratio <= 1.10, (
            f"FilterRows is {ratio:.2f}x slower than raw Polars "
            f"(v2={v2_median / 1e6:.2f}ms, raw={raw_median / 1e6:.2f}ms). "
            f"Must be within 1.10x per D-18."
        )

    @pytest.mark.benchmark
    def test_benchmark_reject_on(self):
        """Verify v2 FilterRows (reject-on) is within 10% of raw Polars dual-filter (D-18).

        With reject_output=True the component produces two outputs (main + reject),
        which forces a barrier materialization. The raw-Polars equivalent also does
        two separate filter+collect passes so the comparison is fair.

        Uses 1M rows so Polars work dominates Python overhead, giving stable ratios.
        """
        dataset = self._make_benchmark_data(n=1_000_000)
        config = {"condition": "amount > 5000", "reject_output": True}
        comp = FilterRows("bench_reject", config)
        expr = pl.col("amount") > 5000

        # Warmup both
        for _ in range(100):
            r = comp.apply({"main": dataset})
            r["main"].collect()
            r["reject"].collect()
            dataset.filter(expr).collect()
            dataset.filter(~expr).collect()

        # Run v2
        v2_timings = []
        for _ in range(5):
            start = time.perf_counter_ns()
            r = comp.apply({"main": dataset})
            r["main"].collect()
            r["reject"].collect()
            v2_timings.append(time.perf_counter_ns() - start)

        # Run raw (two collects to match multi-output)
        raw_timings = []
        for _ in range(5):
            start = time.perf_counter_ns()
            dataset.filter(expr).collect()
            dataset.filter(~expr).collect()
            raw_timings.append(time.perf_counter_ns() - start)

        v2_median = sorted(v2_timings)[len(v2_timings) // 2]
        raw_median = sorted(raw_timings)[len(raw_timings) // 2]

        ratio = v2_median / raw_median if raw_median > 0 else float("inf")
        print(f"FilterRows reject-on: v2={v2_median / 1e6:.2f}ms, raw={raw_median / 1e6:.2f}ms, ratio={ratio:.2f}x")
        assert ratio <= 1.10, (
            f"FilterRows reject-on is {ratio:.2f}x slower than raw Polars "
            f"(v2={v2_median / 1e6:.2f}ms, raw={raw_median / 1e6:.2f}ms). "
            f"Must be within 1.10x per D-18."
        )

    @pytest.mark.benchmark
    def test_benchmark_selectivity_sweep(self):
        """Measure reject-on overhead at varied selectivity levels (review suggestion).

        Selectivity levels:
          ~10% pass (amount > 9000): large reject output, small main
          ~50% pass (amount > 5000): balanced outputs
          ~90% pass (amount > 1000): small reject output, large main

        This test is informational -- it prints results for baseline documentation
        but does NOT assert a ratio. All three selectivity measurements are recorded
        in the baseline JSON under a ``selectivity_sweep`` key.

        Uses 1M rows so Polars work dominates Python overhead, giving stable ratios.
        """
        dataset = self._make_benchmark_data(n=1_000_000)
        thresholds = [
            ("10% pass", 9000),
            ("50% pass", 5000),
            ("90% pass", 1000),
        ]
        for label, threshold in thresholds:
            config = {"condition": f"amount > {threshold}", "reject_output": True}
            comp = FilterRows(f"bench_sel_{threshold}", config)
            expr = pl.col("amount") > threshold

            # Warmup
            for _ in range(100):
                r = comp.apply({"main": dataset})
                r["main"].collect()
                r["reject"].collect()
                dataset.filter(expr).collect()
                dataset.filter(~expr).collect()

            # Run v2
            v2_timings = []
            for _ in range(5):
                start = time.perf_counter_ns()
                r = comp.apply({"main": dataset})
                r["main"].collect()
                r["reject"].collect()
                v2_timings.append(time.perf_counter_ns() - start)

            # Run raw
            raw_timings = []
            for _ in range(5):
                start = time.perf_counter_ns()
                dataset.filter(expr).collect()
                dataset.filter(~expr).collect()
                raw_timings.append(time.perf_counter_ns() - start)

            v2_median = sorted(v2_timings)[len(v2_timings) // 2]
            raw_median = sorted(raw_timings)[len(raw_timings) // 2]
            ratio = v2_median / raw_median if raw_median > 0 else float("inf")
            print(
                f"  Selectivity {label} (>{threshold}): "
                f"v2={v2_median / 1e6:.2f}ms, raw={raw_median / 1e6:.2f}ms, "
                f"ratio={ratio:.2f}x"
            )
