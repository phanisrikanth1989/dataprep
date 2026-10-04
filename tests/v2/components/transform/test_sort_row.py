"""Standard tests for SortRow component (COMP-07).

Subclasses ComponentTestCase to get:
  - validate-before-apply enforcement
  - golden-case parametrized loading
  - integration-through-PyETLEngine
  - benchmark pair quarantined behind @pytest.mark.benchmark
"""
import time

import pytest
import polars as pl

from tests.v2._harness.component_test_case import ComponentTestCase
from src.v2.components.transform.sort_row import SortRow


class TestSortRow(ComponentTestCase):
    """Full standard test class for SortRow."""

    component_type = "sort_row"
    component_class = SortRow
    golden_dir = "sort_row_cases"

    # ---- Golden-case tests ----

    def test_golden_cases(self):
        """Parametrized golden-case tests loaded from sort_row_cases/*.json."""
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
                # Sort output is deterministic when maintain_order=True
                # or when there are no ties
                self.assert_frame_equal(
                    result[output_name], expected_data, check_order=True
                )

    # ---- Validation tests ----

    def test_validate_no_columns(self):
        """Config {} triggers validation error containing 'columns'."""
        result = self.run_component(
            config={},
            expect_validation_errors=True,
        )
        assert "_validation_errors" in result

    def test_validate_columns_not_list(self):
        """Config {'columns': 'not_a_list'} triggers error."""
        result = self.run_component(
            config={"columns": "not_a_list"},
            expect_validation_errors=True,
        )
        assert "_validation_errors" in result

    def test_validate_empty_columns(self):
        """Config {'columns': []} triggers error."""
        result = self.run_component(
            config={"columns": []},
            expect_validation_errors=True,
        )
        assert "_validation_errors" in result

    def test_validate_missing_name(self):
        """Config with column missing 'name' triggers error."""
        result = self.run_component(
            config={"columns": [{"order": "asc"}]},
            expect_validation_errors=True,
        )
        assert "_validation_errors" in result

    def test_validate_invalid_order(self):
        """Config with invalid order triggers error."""
        result = self.run_component(
            config={"columns": [{"name": "a", "order": "sideways"}]},
            expect_validation_errors=True,
        )
        assert "_validation_errors" in result

    def test_validate_passes_valid(self):
        """Valid config passes validation and apply works."""
        df = pl.DataFrame({"a": [3, 1, 2]}).lazy()
        result = self.run_component(
            config={"columns": [{"name": "a", "order": "asc"}]},
            inputs={"main": df},
        )
        assert "main" in result
        collected = result["main"].collect()
        assert collected["a"].to_list() == [1, 2, 3]

    # ---- Behavior tests ----

    def test_single_column_ascending(self):
        """5 rows, sort by amount asc, verify order."""
        df = pl.DataFrame(
            {"amount": [50, 10, 30, 20, 40], "label": ["E", "A", "C", "B", "D"]}
        ).lazy()
        result = self.run_component(
            config={
                "columns": [{"name": "amount", "order": "asc"}],
                "maintain_order": True,
            },
            inputs={"main": df},
        )
        collected = result["main"].collect()
        assert collected["amount"].to_list() == [10, 20, 30, 40, 50]
        assert collected["label"].to_list() == ["A", "B", "C", "D", "E"]

    def test_single_column_descending(self):
        """5 rows, sort by amount desc, verify order."""
        df = pl.DataFrame(
            {"amount": [50, 10, 30, 20, 40], "label": ["E", "A", "C", "B", "D"]}
        ).lazy()
        result = self.run_component(
            config={
                "columns": [{"name": "amount", "order": "desc"}],
                "maintain_order": True,
            },
            inputs={"main": df},
        )
        collected = result["main"].collect()
        assert collected["amount"].to_list() == [50, 40, 30, 20, 10]
        assert collected["label"].to_list() == ["E", "D", "C", "B", "A"]

    def test_multi_column_sort(self):
        """Two sort keys, verify primary then secondary ordering."""
        df = pl.DataFrame(
            {
                "category": ["B", "A", "B", "A", "C"],
                "amount": [200, 100, 300, 400, 150],
                "id": [1, 2, 3, 4, 5],
            }
        ).lazy()
        result = self.run_component(
            config={
                "columns": [
                    {"name": "category", "order": "asc"},
                    {"name": "amount", "order": "desc"},
                ],
                "maintain_order": True,
            },
            inputs={"main": df},
        )
        collected = result["main"].collect()
        assert collected["category"].to_list() == ["A", "A", "B", "B", "C"]
        assert collected["amount"].to_list() == [400, 100, 300, 200, 150]

    def test_nulls_last_true(self):
        """Sort with nulls_last=True, verify nulls at end."""
        df = pl.DataFrame(
            {"value": [30, None, 10, None, 20], "label": ["C", "N1", "A", "N2", "B"]}
        ).lazy()
        result = self.run_component(
            config={
                "columns": [{"name": "value", "order": "asc"}],
                "nulls_last": True,
                "maintain_order": True,
            },
            inputs={"main": df},
        )
        collected = result["main"].collect()
        assert collected["value"].to_list() == [10, 20, 30, None, None]
        assert collected["label"].to_list() == ["A", "B", "C", "N1", "N2"]

    def test_nulls_last_false(self):
        """Sort with nulls_last=False (default), verify nulls at beginning."""
        df = pl.DataFrame(
            {"value": [30, None, 10, None, 20], "label": ["C", "N1", "A", "N2", "B"]}
        ).lazy()
        result = self.run_component(
            config={
                "columns": [{"name": "value", "order": "asc"}],
                "nulls_last": False,
                "maintain_order": True,
            },
            inputs={"main": df},
        )
        collected = result["main"].collect()
        assert collected["value"].to_list() == [None, None, 10, 20, 30]
        assert collected["label"].to_list() == ["N1", "N2", "A", "B", "C"]

    def test_per_column_nulls_override(self):
        """Component-level nulls_last=false, one column has nulls_last=true override.

        Verifies hierarchical default merging: the column with the override
        has its nulls positioned last, while the other column follows the
        component-level default (nulls first).

        Addresses Gemini review concern 2: explicitly verify the
        col.get('nulls_last', default_nulls_last) hierarchical merging logic.
        """
        df = pl.DataFrame(
            {
                "category": ["A", None, "B", None, "A"],
                "amount": [100, 200, None, 400, None],
            }
        ).lazy()
        result = self.run_component(
            config={
                "columns": [
                    {"name": "category", "order": "asc"},
                    {"name": "amount", "order": "asc", "nulls_last": True},
                ],
                "nulls_last": False,
                "maintain_order": True,
            },
            inputs={"main": df},
        )
        collected = result["main"].collect()
        categories = collected["category"].to_list()
        amounts = collected["amount"].to_list()

        # category uses component default (nulls_last=false): nulls first
        # Then within each category group, amount uses override (nulls_last=true): nulls last
        # Expected order:
        # 1. category=null (nulls first for category): amount 200, 400 (asc, no nulls)
        # 2. category=A: amount 100, null (null last for amount)
        # 3. category=B: amount null (only one row)
        assert categories == [None, None, "A", "A", "B"]
        assert amounts == [200, 400, 100, None, None]

    def test_per_column_nulls_override_reverse(self):
        """Component-level nulls_last=true, one column has nulls_last=false override.

        Verifies the override works in the reverse direction too
        (column-level false overrides component-level true).
        """
        df = pl.DataFrame(
            {
                "category": ["A", None, "B", None, "A"],
                "amount": [100, 200, None, 400, None],
            }
        ).lazy()
        result = self.run_component(
            config={
                "columns": [
                    {"name": "category", "order": "asc"},
                    {"name": "amount", "order": "asc", "nulls_last": False},
                ],
                "nulls_last": True,
                "maintain_order": True,
            },
            inputs={"main": df},
        )
        collected = result["main"].collect()
        categories = collected["category"].to_list()
        amounts = collected["amount"].to_list()

        # category uses component default (nulls_last=true): nulls last
        # Within each category group, amount uses override (nulls_last=false): nulls first
        # Expected order:
        # 1. category=A: amount null, 100 (null first for amount override)
        # 2. category=B: amount null (only one row)
        # 3. category=null (nulls last for category): amount 200, 400 (no nulls)
        assert categories == ["A", "A", "B", None, None]
        assert amounts == [None, 100, None, 200, 400]

    def test_maintain_order_true(self):
        """Stable sort: equal-keyed rows maintain input order."""
        df = pl.DataFrame(
            {"category": ["B", "A", "B", "A"], "seq": [1, 2, 3, 4]}
        ).lazy()
        result = self.run_component(
            config={
                "columns": [{"name": "category", "order": "asc"}],
                "maintain_order": True,
            },
            inputs={"main": df},
        )
        collected = result["main"].collect()
        assert collected["category"].to_list() == ["A", "A", "B", "B"]
        assert collected["seq"].to_list() == [2, 4, 1, 3]

    def test_maintain_order_false(self):
        """Unstable sort: verify correct count (order non-deterministic for ties)."""
        df = pl.DataFrame(
            {"category": ["B", "A", "B", "A"], "seq": [1, 2, 3, 4]}
        ).lazy()
        result = self.run_component(
            config={
                "columns": [{"name": "category", "order": "asc"}],
                "maintain_order": False,
            },
            inputs={"main": df},
        )
        collected = result["main"].collect()
        assert len(collected) == 4
        assert sorted(collected["category"].to_list()) == ["A", "A", "B", "B"]

    def test_empty_input(self):
        """Empty dataframe, verify empty output."""
        df = pl.DataFrame({"amount": [], "label": []}).lazy()
        result = self.run_component(
            config={"columns": [{"name": "amount", "order": "asc"}]},
            inputs={"main": df},
        )
        collected = result["main"].collect()
        assert len(collected) == 0

    def test_single_row(self):
        """Single row passes through."""
        df = pl.DataFrame({"amount": [42], "label": ["X"]}).lazy()
        result = self.run_component(
            config={"columns": [{"name": "amount", "order": "asc"}]},
            inputs={"main": df},
        )
        collected = result["main"].collect()
        assert len(collected) == 1
        assert collected["amount"].to_list() == [42]

    def test_dataframe_input_coerced(self):
        """Non-lazy DataFrame input is coerced to LazyFrame."""
        df = pl.DataFrame({"amount": [3, 1, 2]})  # Not lazy
        result = self.run_component(
            config={"columns": [{"name": "amount", "order": "asc"}]},
            inputs={"main": df},
        )
        assert isinstance(result["main"], pl.LazyFrame)

    def test_stays_lazy(self):
        """Output is always LazyFrame."""
        df = pl.DataFrame({"amount": [3, 1, 2]}).lazy()
        result = self.run_component(
            config={"columns": [{"name": "amount", "order": "asc"}]},
            inputs={"main": df},
        )
        assert isinstance(result["main"], pl.LazyFrame)

    def test_order_defaults_to_asc(self):
        """Column entry without 'order' key sorts ascending."""
        df = pl.DataFrame({"amount": [30, 10, 20]}).lazy()
        result = self.run_component(
            config={
                "columns": [{"name": "amount"}],
                "maintain_order": True,
            },
            inputs={"main": df},
        )
        collected = result["main"].collect()
        assert collected["amount"].to_list() == [10, 20, 30]

    def test_no_barrier(self):
        """SortRow is_barrier is False."""
        comp = SortRow(
            "s",
            {"columns": [{"name": "a", "order": "asc"}]},
        )
        assert comp.is_barrier is False

    # ---- Integration tests ----

    def test_integration_registry(self):
        """REGISTRY.get('sort_row') returns SortRow, instantiate, validate, apply."""
        from src.v2.components.registry import REGISTRY

        cls = REGISTRY.get("sort_row")
        assert cls is SortRow

        comp = cls(
            "sr_integration",
            {"columns": [{"name": "amount", "order": "asc"}]},
        )
        errors = comp.validate()
        assert errors == []

        df = pl.DataFrame({"amount": [30, 10, 20], "name": ["C", "A", "B"]}).lazy()
        result = comp.apply({"main": df})
        assert "main" in result
        collected = result["main"].collect()
        assert collected["amount"].to_list() == [10, 20, 30]

    def test_integration_through_engine(self, tmp_path):
        """Run SortRow through PyETLEngine with file_input_delimited source."""
        csv_path = tmp_path / "input.csv"
        csv_path.write_text("id;name;amount\n1;Charlie;300\n2;Alice;100\n3;Bob;200\n")

        job_config = {
            "name": "sort_row_integration_test",
            "engine": "v2",
            "components": [
                {
                    "id": "src1",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(csv_path),
                        "delimiter": ";",
                        "schema": [
                            {"name": "id", "type": "int"},
                            {"name": "name", "type": "string"},
                            {"name": "amount", "type": "float"},
                        ],
                    },
                },
                {
                    "id": "sort1",
                    "type": "sort_row",
                    "config": {
                        "columns": [{"name": "amount", "order": "desc"}],
                    },
                },
            ],
            "flows": [
                {"source": "src1", "target": "sort1", "output": "main", "input": "main"},
            ],
        }
        result = self.run_integration(job_config)
        assert result["status"] == "success"

    # ---- Benchmark tests ----

    @staticmethod
    def _make_benchmark_data(n: int = 100_000) -> pl.LazyFrame:
        """Create a benchmark LazyFrame with mixed-type columns.

        Columns: id (int range), name (string), amount (float, random),
        category (cat_{i%50}), active (bool).
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
        """Verify SortRow is within 1.10x of raw pl.LazyFrame.sort().

        Uses 1M rows, sort by amount desc. Raw Polars reference is a simple
        dataset.sort('amount', descending=True).collect().
        """
        dataset = self._make_benchmark_data(n=1_000_000)
        config = {
            "columns": [{"name": "amount", "order": "desc"}],
        }
        comp = SortRow("bench_ratio", config)

        # Warmup both paths
        for _ in range(100):
            comp.apply({"main": dataset})["main"].collect()
            dataset.sort("amount", descending=True).collect()

        # Run v2
        v2_timings = []
        for _ in range(5):
            start = time.perf_counter_ns()
            result = comp.apply({"main": dataset})
            result["main"].collect()
            v2_timings.append(time.perf_counter_ns() - start)

        # Run raw Polars
        raw_timings = []
        for _ in range(5):
            start = time.perf_counter_ns()
            dataset.sort("amount", descending=True).collect()
            raw_timings.append(time.perf_counter_ns() - start)

        v2_median = sorted(v2_timings)[len(v2_timings) // 2]
        raw_median = sorted(raw_timings)[len(raw_timings) // 2]

        ratio = v2_median / raw_median if raw_median > 0 else float("inf")
        assert ratio <= 1.10, (
            f"SortRow is {ratio:.2f}x slower than raw Polars sort() "
            f"(v2={v2_median / 1e6:.2f}ms, raw={raw_median / 1e6:.2f}ms). "
            f"Must be within 1.10x."
        )

    @pytest.mark.benchmark
    def test_benchmark_multi_column_ratio(self):
        """Verify multi-column SortRow is within 1.10x of raw Polars sort().

        Sort by category asc + amount desc. Raw Polars reference:
        dataset.sort(['category', 'amount'], descending=[False, True]).collect().
        """
        dataset = self._make_benchmark_data(n=1_000_000)
        config = {
            "columns": [
                {"name": "category", "order": "asc"},
                {"name": "amount", "order": "desc"},
            ],
        }
        comp = SortRow("bench_multi", config)

        # Warmup both paths
        for _ in range(100):
            comp.apply({"main": dataset})["main"].collect()
            dataset.sort(
                ["category", "amount"], descending=[False, True]
            ).collect()

        # Run v2
        v2_timings = []
        for _ in range(5):
            start = time.perf_counter_ns()
            result = comp.apply({"main": dataset})
            result["main"].collect()
            v2_timings.append(time.perf_counter_ns() - start)

        # Run raw Polars
        raw_timings = []
        for _ in range(5):
            start = time.perf_counter_ns()
            dataset.sort(
                ["category", "amount"], descending=[False, True]
            ).collect()
            raw_timings.append(time.perf_counter_ns() - start)

        v2_median = sorted(v2_timings)[len(v2_timings) // 2]
        raw_median = sorted(raw_timings)[len(raw_timings) // 2]

        ratio = v2_median / raw_median if raw_median > 0 else float("inf")
        assert ratio <= 1.10, (
            f"SortRow multi-column is {ratio:.2f}x slower than raw Polars "
            f"(v2={v2_median / 1e6:.2f}ms, raw={raw_median / 1e6:.2f}ms). "
            f"Must be within 1.10x."
        )
