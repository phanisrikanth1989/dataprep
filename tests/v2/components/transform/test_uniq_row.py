"""Standard tests for UniqRow component (COMP-04).

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
from src.v2.components.transform.uniq_row import UniqRow


class TestUniqRow(ComponentTestCase):
    """Full standard test class for UniqRow."""

    component_type = "uniq_row"
    component_class = UniqRow
    golden_dir = "uniq_row_cases"

    # ---- Golden-case tests ----

    def test_golden_cases(self):
        """Parametrized golden-case tests loaded from uniq_row_cases/*.json."""
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
                # Order is deterministic for "unique" output with keep="first",
                # but "duplicate" output and non-first keep modes may reorder
                keep = config.get("keep", "first")
                check_order = (keep == "first" and output_name == "unique")
                self.assert_frame_equal(
                    result[output_name], expected_data, check_order=check_order
                )

    # ---- Validation tests ----

    def test_validate_no_key_columns(self):
        """Empty config with no key_columns triggers validation error."""
        result = self.run_component(
            config={},
            expect_validation_errors=True,
        )
        assert "_validation_errors" in result

    def test_validate_missing_column_key(self):
        """key_columns entry missing 'column' triggers validation error."""
        result = self.run_component(
            config={"key_columns": [{"case_sensitive": True}]},
            expect_validation_errors=True,
        )
        assert "_validation_errors" in result

    def test_validate_invalid_keep(self):
        """keep='bogus' triggers validation error."""
        result = self.run_component(
            config={
                "key_columns": [{"column": "id", "case_sensitive": True}],
                "keep": "bogus",
            },
            expect_validation_errors=True,
        )
        assert "_validation_errors" in result

    def test_validate_passes_with_valid_config(self):
        """Valid key_columns + keep='first' passes validation."""
        df = pl.DataFrame({"id": [1, 2], "name": ["A", "B"]}).lazy()
        result = self.run_component(
            config={
                "key_columns": [{"column": "id", "case_sensitive": True}],
                "keep": "first",
            },
            inputs={"main": df},
        )
        assert "unique" in result

    # ---- Behavior tests ----

    def test_basic_dedup_single_column(self):
        """Dedup on single key column with 5 rows, 2 dupes keeps 3 unique rows."""
        df = pl.DataFrame(
            {"id": [1, 2, 1, 3, 2], "name": ["A", "B", "A2", "C", "B2"]}
        ).lazy()
        result = self.run_component(
            config={"key_columns": [{"column": "id", "case_sensitive": True}]},
            inputs={"main": df},
        )
        collected = result["unique"].collect()
        assert len(collected) == 3
        assert collected["id"].to_list() == [1, 2, 3]
        assert collected["name"].to_list() == ["A", "B", "C"]

    def test_case_insensitive_dedup(self):
        """case_sensitive=False groups Alice/alice as same key."""
        df = pl.DataFrame(
            {"name": ["Alice", "alice", "Bob", "BOB", "Charlie"], "score": [100, 90, 80, 85, 70]}
        ).lazy()
        result = self.run_component(
            config={"key_columns": [{"column": "name", "case_sensitive": False}]},
            inputs={"main": df},
        )
        collected = result["unique"].collect()
        assert len(collected) == 3
        assert collected["name"].to_list() == ["Alice", "Bob", "Charlie"]

    def test_mixed_case_sensitivity(self):
        """Two key columns: one case-sensitive, one not."""
        df = pl.DataFrame(
            {
                "code": ["A", "A", "B", "B"],
                "name": ["Alice", "alice", "Bob", "Carol"],
                "val": [1, 2, 3, 4],
            }
        ).lazy()
        result = self.run_component(
            config={
                "key_columns": [
                    {"column": "code", "case_sensitive": True},
                    {"column": "name", "case_sensitive": False},
                ],
            },
            inputs={"main": df},
        )
        collected = result["unique"].collect()
        # ("A", "alice") == ("A", "Alice") case-insensitive on name -> row 1 kept
        # ("B", "bob") != ("B", "carol") -> both kept
        assert len(collected) == 3
        assert collected["code"].to_list() == ["A", "B", "B"]

    def test_duplicate_output_enabled(self):
        """duplicate_output=True emits both 'unique' and 'duplicate'."""
        df = pl.DataFrame({"id": [1, 2, 1, 3, 2], "val": ["a", "b", "c", "d", "e"]}).lazy()
        result = self.run_component(
            config={
                "key_columns": [{"column": "id", "case_sensitive": True}],
                "duplicate_output": True,
            },
            inputs={"main": df},
        )
        assert "unique" in result
        assert "duplicate" in result
        unique_df = result["unique"].collect()
        dup_df = result["duplicate"].collect()
        assert len(unique_df) == 3
        assert len(dup_df) == 2

    def test_duplicate_output_disabled(self):
        """duplicate_output=False (default) emits only 'unique', no 'duplicate'."""
        df = pl.DataFrame({"id": [1, 2, 1], "val": ["a", "b", "c"]}).lazy()
        result = self.run_component(
            config={"key_columns": [{"column": "id", "case_sensitive": True}]},
            inputs={"main": df},
        )
        assert "unique" in result
        assert "duplicate" not in result

    def test_only_once_each_duplicated_key(self):
        """only_once=True with triplicate key: only one entry per key in duplicate output."""
        df = pl.DataFrame(
            {"id": [1, 1, 1, 2, 2], "val": ["a", "b", "c", "d", "e"]}
        ).lazy()
        result = self.run_component(
            config={
                "key_columns": [{"column": "id", "case_sensitive": True}],
                "duplicate_output": True,
                "only_once": True,
            },
            inputs={"main": df},
        )
        dup_df = result["duplicate"].collect()
        # Only one duplicate per key group
        assert len(dup_df) == 2
        assert sorted(dup_df["id"].to_list()) == [1, 2]

    def test_keep_last(self):
        """keep='last' keeps last occurrence of each key."""
        df = pl.DataFrame(
            {"id": [1, 2, 1, 3], "name": ["A1", "B1", "A2", "C1"]}
        ).lazy()
        result = self.run_component(
            config={
                "key_columns": [{"column": "id", "case_sensitive": True}],
                "keep": "last",
            },
            inputs={"main": df},
        )
        collected = result["unique"].collect()
        assert len(collected) == 3
        # Check values regardless of order
        id_name_map = dict(zip(collected["id"].to_list(), collected["name"].to_list()))
        assert id_name_map[1] == "A2"  # last occurrence of id=1
        assert id_name_map[2] == "B1"
        assert id_name_map[3] == "C1"

    def test_keep_none(self):
        """keep='none' removes all keys that have duplicates."""
        df = pl.DataFrame(
            {"id": [1, 2, 1, 3, 2], "val": ["a", "b", "c", "d", "e"]}
        ).lazy()
        result = self.run_component(
            config={
                "key_columns": [{"column": "id", "case_sensitive": True}],
                "keep": "none",
            },
            inputs={"main": df},
        )
        collected = result["unique"].collect()
        assert len(collected) == 1
        assert collected["id"].to_list() == [3]
        assert collected["val"].to_list() == ["d"]

    def test_keep_none_with_duplicate_output(self):
        """keep='none' + duplicate_output: unique gets non-duplicated keys only,
        duplicate gets ALL rows of any key that appeared more than once."""
        df = pl.DataFrame(
            {"id": [1, 2, 1, 3, 2], "val": ["a", "b", "c", "d", "e"]}
        ).lazy()
        result = self.run_component(
            config={
                "key_columns": [{"column": "id", "case_sensitive": True}],
                "keep": "none",
                "duplicate_output": True,
            },
            inputs={"main": df},
        )
        unique_df = result["unique"].collect()
        dup_df = result["duplicate"].collect()
        assert len(unique_df) == 1  # Only id=3
        assert unique_df["id"].to_list() == [3]
        assert len(dup_df) == 4  # All rows with id=1 or id=2

    def test_keep_any(self):
        """keep='any' deduplicates (exact row non-deterministic, count is correct)."""
        df = pl.DataFrame(
            {"id": [1, 2, 1, 3, 2], "val": ["a", "b", "c", "d", "e"]}
        ).lazy()
        result = self.run_component(
            config={
                "key_columns": [{"column": "id", "case_sensitive": True}],
                "keep": "any",
            },
            inputs={"main": df},
        )
        collected = result["unique"].collect()
        assert len(collected) == 3
        assert sorted(collected["id"].to_list()) == [1, 2, 3]

    def test_maintain_order_true_default(self):
        """Default maintain_order=True preserves input order for first-seen rows."""
        df = pl.DataFrame(
            {"id": [3, 1, 2, 1, 3], "val": ["a", "b", "c", "d", "e"]}
        ).lazy()
        result = self.run_component(
            config={
                "key_columns": [{"column": "id", "case_sensitive": True}],
                "keep": "first",
            },
            inputs={"main": df},
        )
        collected = result["unique"].collect()
        # Order should match first-seen order: 3, 1, 2
        assert collected["id"].to_list() == [3, 1, 2]

    def test_maintain_order_false(self):
        """maintain_order=False produces correct count (order non-deterministic)."""
        df = pl.DataFrame(
            {"id": [3, 1, 2, 1, 3], "val": ["a", "b", "c", "d", "e"]}
        ).lazy()
        result = self.run_component(
            config={
                "key_columns": [{"column": "id", "case_sensitive": True}],
                "keep": "first",
                "maintain_order": False,
            },
            inputs={"main": df},
        )
        collected = result["unique"].collect()
        assert len(collected) == 3
        assert sorted(collected["id"].to_list()) == [1, 2, 3]

    def test_null_keys_grouped(self):
        """Null values in key column are treated as equal (grouped together per D-15)."""
        df = pl.DataFrame(
            {"id": [1, None, 2, None, 3], "val": ["a", "b", "c", "d", "e"]}
        ).lazy()
        result = self.run_component(
            config={"key_columns": [{"column": "id", "case_sensitive": True}]},
            inputs={"main": df},
        )
        collected = result["unique"].collect()
        # 4 unique keys: 1, null, 2, 3 (two nulls grouped into one)
        assert len(collected) == 4
        assert collected["id"].null_count() == 1

    def test_null_case_insensitive_interaction(self):
        """str.to_lowercase() on null stays null; nulls still grouped together.

        Addresses review concern: null + case-insensitive interaction. The
        str.to_lowercase() expression must not crash on null or convert null
        to empty string.
        """
        df = pl.DataFrame(
            {"name": ["Alice", None, "alice", None, "Bob"], "val": [1, 2, 3, 4, 5]}
        ).lazy()
        result = self.run_component(
            config={"key_columns": [{"column": "name", "case_sensitive": False}]},
            inputs={"main": df},
        )
        collected = result["unique"].collect()
        # 3 unique groups: "alice" (Alice/alice), null (two nulls), "bob"
        assert len(collected) == 3
        # Verify null is preserved as null (not converted to empty string)
        assert collected["name"].null_count() == 1

    def test_empty_input(self):
        """Empty dataframe produces empty output."""
        df = pl.DataFrame({"id": [], "val": []}).lazy()
        result = self.run_component(
            config={"key_columns": [{"column": "id", "case_sensitive": True}]},
            inputs={"main": df},
        )
        collected = result["unique"].collect()
        assert len(collected) == 0

    def test_single_row(self):
        """Single row input passes through as unique."""
        df = pl.DataFrame({"id": [1], "val": ["a"]}).lazy()
        result = self.run_component(
            config={"key_columns": [{"column": "id", "case_sensitive": True}]},
            inputs={"main": df},
        )
        collected = result["unique"].collect()
        assert len(collected) == 1
        assert collected["id"].to_list() == [1]

    def test_dataframe_input_coerced(self):
        """Non-lazy DataFrame input is coerced to LazyFrame output."""
        df = pl.DataFrame({"id": [1, 2, 1], "val": ["a", "b", "c"]})  # Not lazy
        result = self.run_component(
            config={"key_columns": [{"column": "id", "case_sensitive": True}]},
            inputs={"main": df},
        )
        assert isinstance(result["unique"], pl.LazyFrame)

    def test_stays_lazy(self):
        """Output is always a LazyFrame."""
        df = pl.DataFrame({"id": [1, 2, 1], "val": ["a", "b", "c"]}).lazy()
        result = self.run_component(
            config={"key_columns": [{"column": "id", "case_sensitive": True}]},
            inputs={"main": df},
        )
        assert isinstance(result["unique"], pl.LazyFrame)

    def test_dynamic_barrier_true(self):
        """With duplicate_output=True, is_barrier is True (D-05)."""
        comp = UniqRow(
            "barrier_on",
            {"key_columns": [{"column": "id", "case_sensitive": True}], "duplicate_output": True},
        )
        assert comp.is_barrier is True

    def test_dynamic_barrier_false(self):
        """With duplicate_output=False, is_barrier is False (D-05)."""
        comp = UniqRow(
            "barrier_off",
            {"key_columns": [{"column": "id", "case_sensitive": True}]},
        )
        assert comp.is_barrier is False

    # ---- Integration tests ----

    def test_integration_registry(self):
        """Verify REGISTRY.get('uniq_row') returns UniqRow, instantiate, validate, apply."""
        from src.v2.components.registry import REGISTRY

        cls = REGISTRY.get("uniq_row")
        assert cls is UniqRow

        comp = cls(
            "ur_integration",
            {"key_columns": [{"column": "id", "case_sensitive": True}]},
        )
        errors = comp.validate()
        assert errors == []

        df = pl.DataFrame({"id": [1, 2, 1, 3], "name": ["A", "B", "C", "D"]}).lazy()
        result = comp.apply({"main": df})
        assert "unique" in result
        assert len(result["unique"].collect()) == 3

    def test_integration_through_engine(self, tmp_path):
        """Run UniqRow through PyETLEngine with file_input_delimited source."""
        csv_path = tmp_path / "input.csv"
        csv_path.write_text("id;name\n1;A\n2;B\n1;C\n3;D\n")

        job_config = {
            "name": "uniq_row_integration_test",
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
                        ],
                    },
                },
                {
                    "id": "dedup",
                    "type": "uniq_row",
                    "config": {
                        "key_columns": [{"column": "id", "case_sensitive": True}],
                    },
                },
            ],
            "flows": [
                {"source": "src1", "target": "dedup", "output": "main", "input": "main"},
            ],
        }
        result = self.run_integration(job_config)
        assert result["status"] == "success"

    # ---- Benchmark tests ----

    @staticmethod
    def _make_benchmark_data(n: int = 100_000) -> pl.LazyFrame:
        """Create a benchmark LazyFrame with ~50% duplicate rate.

        Columns: id (range mod n//2 for dupes), name (strings),
        amount (floats), category (cat_{i%50}), active (bool).
        """
        import random

        random.seed(42)
        half_n = max(n // 2, 1)
        return pl.DataFrame(
            {
                "id": [i % half_n for i in range(n)],
                "name": [f"name_{i}" for i in range(n)],
                "amount": [random.uniform(0, 10000) for _ in range(n)],
                "category": [f"cat_{i % 50}" for i in range(n)],
                "active": [i % 3 != 0 for i in range(n)],
            }
        ).lazy()

    @pytest.mark.benchmark
    def test_benchmark_ratio(self):
        """Verify UniqRow is within 1.10x of raw pl.LazyFrame.unique().

        Uses 1M rows, key_columns=[{column: 'id', case_sensitive: True}],
        keep='first'. Raw Polars reference is a simple
        lf.unique(subset=['id'], keep='first', maintain_order=True).collect()
        -- no duplicate branch, no row index, no anti-join.
        """
        dataset = self._make_benchmark_data(n=1_000_000)
        config = {
            "key_columns": [{"column": "id", "case_sensitive": True}],
            "keep": "first",
        }
        comp = UniqRow("bench_ratio", config)

        # Warmup both paths
        for _ in range(100):
            comp.apply({"main": dataset})["unique"].collect()
            dataset.unique(subset=["id"], keep="first", maintain_order=True).collect()

        # Run v2
        v2_timings = []
        for _ in range(5):
            start = time.perf_counter_ns()
            result = comp.apply({"main": dataset})
            result["unique"].collect()
            v2_timings.append(time.perf_counter_ns() - start)

        # Run raw Polars
        raw_timings = []
        for _ in range(5):
            start = time.perf_counter_ns()
            dataset.unique(subset=["id"], keep="first", maintain_order=True).collect()
            raw_timings.append(time.perf_counter_ns() - start)

        v2_median = sorted(v2_timings)[len(v2_timings) // 2]
        raw_median = sorted(raw_timings)[len(raw_timings) // 2]

        ratio = v2_median / raw_median if raw_median > 0 else float("inf")
        assert ratio <= 1.10, (
            f"UniqRow is {ratio:.2f}x slower than raw Polars unique() "
            f"(v2={v2_median / 1e6:.2f}ms, raw={raw_median / 1e6:.2f}ms). "
            f"Must be within 1.10x."
        )

    @pytest.mark.benchmark
    def test_benchmark_case_insensitive_ratio(self):
        """Verify case-insensitive UniqRow is within 1.10x of equivalent raw Polars.

        Raw Polars reference does the same lowercase + unique (no duplicate branch):
        lf.with_columns(pl.col('name').str.to_lowercase().alias('__tmp'))
          .unique(subset=['__tmp'], keep='first', maintain_order=True)
          .drop('__tmp').collect()

        Tests that case-insensitive overhead is from the lowercasing itself,
        not from v2 wrapper overhead (per D-10).
        """
        dataset = self._make_benchmark_data(n=1_000_000)
        config = {
            "key_columns": [{"column": "name", "case_sensitive": False}],
            "keep": "first",
        }
        comp = UniqRow("bench_ci", config)

        # Warmup both paths
        for _ in range(100):
            comp.apply({"main": dataset})["unique"].collect()
            (
                dataset
                .with_columns(pl.col("name").str.to_lowercase().alias("__tmp"))
                .unique(subset=["__tmp"], keep="first", maintain_order=True)
                .drop("__tmp")
                .collect()
            )

        # Run v2
        v2_timings = []
        for _ in range(5):
            start = time.perf_counter_ns()
            result = comp.apply({"main": dataset})
            result["unique"].collect()
            v2_timings.append(time.perf_counter_ns() - start)

        # Run raw Polars (same lowercase step)
        raw_timings = []
        for _ in range(5):
            start = time.perf_counter_ns()
            (
                dataset
                .with_columns(pl.col("name").str.to_lowercase().alias("__tmp"))
                .unique(subset=["__tmp"], keep="first", maintain_order=True)
                .drop("__tmp")
                .collect()
            )
            raw_timings.append(time.perf_counter_ns() - start)

        v2_median = sorted(v2_timings)[len(v2_timings) // 2]
        raw_median = sorted(raw_timings)[len(raw_timings) // 2]

        ratio = v2_median / raw_median if raw_median > 0 else float("inf")
        assert ratio <= 1.10, (
            f"UniqRow case-insensitive is {ratio:.2f}x slower than raw Polars "
            f"(v2={v2_median / 1e6:.2f}ms, raw={raw_median / 1e6:.2f}ms). "
            f"Must be within 1.10x per D-10."
        )
