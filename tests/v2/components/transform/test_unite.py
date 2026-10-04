"""Standard tests for Unite component (COMP-03).

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
from src.v2.components.transform.unite import Unite


class TestUnite(ComponentTestCase):
    """Full standard test class for Unite."""

    component_type = "unite"
    component_class = Unite
    golden_dir = "unite_cases"

    # ---- Golden-case tests (D-12, D-13) ----

    def test_golden_cases(self):
        """Parametrized golden-case tests loaded from unite_cases/*.json."""
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
                # distinct_mode case needs check_order=False since unique() order is unspecified
                check_order = "distinct" not in config.get("mode", "all")
                self.assert_frame_equal(
                    result[output_name], expected_data, check_order=check_order
                )

    # ---- Validation tests ----

    def test_validate_always_passes(self):
        """Unite has no required config, so empty config is valid."""
        result = self.run_component(
            config={},
            inputs={"a": pl.DataFrame({"x": [1]}).lazy()},
        )
        assert "main" in result

    def test_validate_invalid_mode(self):
        """Invalid 'mode' triggers validation error."""
        result = self.run_component(
            config={"mode": "invalid"},
            expect_validation_errors=True,
        )
        assert "_validation_errors" in result

    # ---- Behavior tests ----

    def test_two_inputs_union(self):
        """Two frames with same schema produce 4-row union."""
        df1 = pl.DataFrame({"id": [1, 2], "name": ["A", "B"]}).lazy()
        df2 = pl.DataFrame({"id": [3, 4], "name": ["C", "D"]}).lazy()
        result = self.run_component(
            config={},
            inputs={"input1": df1, "input2": df2},
        )
        collected = result["main"].collect()
        assert len(collected) == 4
        assert collected["id"].to_list() == [1, 2, 3, 4]

    def test_three_inputs(self):
        """Three frames produce union of all rows."""
        df1 = pl.DataFrame({"x": [1]}).lazy()
        df2 = pl.DataFrame({"x": [2]}).lazy()
        df3 = pl.DataFrame({"x": [3]}).lazy()
        result = self.run_component(
            config={},
            inputs={"a": df1, "b": df2, "c": df3},
        )
        assert result["main"].collect()["x"].to_list() == [1, 2, 3]

    def test_single_input_passthrough(self):
        """Single input passes through unchanged."""
        df = pl.DataFrame({"x": [1, 2]}).lazy()
        result = self.run_component(
            config={},
            inputs={"main": df},
        )
        assert result["main"].collect()["x"].to_list() == [1, 2]

    def test_distinct_mode(self):
        """Two frames with overlapping rows, mode=distinct removes dupes."""
        df1 = pl.DataFrame({"x": [1, 2]}).lazy()
        df2 = pl.DataFrame({"x": [2, 3]}).lazy()
        result = self.run_component(
            config={"mode": "distinct"},
            inputs={"a": df1, "b": df2},
        )
        collected = result["main"].collect()
        assert len(collected) == 3
        assert sorted(collected["x"].to_list()) == [1, 2, 3]

    def test_align_schemas_false_default(self):
        """Default config with mismatched schemas raises error on collect."""
        df1 = pl.DataFrame({"x": [1], "y": [10]}).lazy()
        df2 = pl.DataFrame({"x": [2], "z": [20]}).lazy()
        result = self.run_component(
            config={},
            inputs={"a": df1, "b": df2},
        )
        # Lazy concat with how="vertical" defers the schema check to collect.
        # Polars raises ShapeError when column names don't match.
        with pytest.raises(pl.exceptions.ShapeError):
            result["main"].collect()

    def test_align_schemas_true(self):
        """align_schemas=True merges different column sets with null-fill."""
        df1 = pl.DataFrame({"x": [1], "y": [10]}).lazy()
        df2 = pl.DataFrame({"x": [2], "z": [20]}).lazy()
        result = self.run_component(
            config={"align_schemas": True},
            inputs={"a": df1, "b": df2},
        )
        collected = result["main"].collect()
        assert len(collected) == 2
        assert set(collected.columns) == {"x", "y", "z"}
        # First row has y=10, z=null; second has y=null, z=20
        assert collected["y"].to_list() == [10, None]
        assert collected["z"].to_list() == [None, 20]

    def test_selective_inputs(self):
        """Selective inputs list includes only named inputs."""
        orders = pl.DataFrame({"id": [1]}).lazy()
        returns = pl.DataFrame({"id": [2]}).lazy()
        extra = pl.DataFrame({"id": [99]}).lazy()
        result = self.run_component(
            config={"inputs": ["orders", "returns"]},
            inputs={"orders": orders, "returns": returns, "extra": extra},
        )
        collected = result["main"].collect()
        assert len(collected) == 2
        assert sorted(collected["id"].to_list()) == [1, 2]

    def test_no_inputs_returns_empty(self):
        """Empty inputs dict returns empty result."""
        result = self.run_component(
            config={},
            inputs={},
        )
        assert result == {}

    def test_dataframe_input_coerced(self):
        """Non-lazy DataFrame input is coerced to LazyFrame."""
        df = pl.DataFrame({"x": [1]})  # Not lazy
        result = self.run_component(
            config={},
            inputs={"main": df},
        )
        assert isinstance(result["main"], pl.LazyFrame)

    def test_stays_lazy(self):
        """Output is always a LazyFrame."""
        df1 = pl.DataFrame({"x": [1]}).lazy()
        df2 = pl.DataFrame({"x": [2]}).lazy()
        result = self.run_component(
            config={},
            inputs={"a": df1, "b": df2},
        )
        assert isinstance(result["main"], pl.LazyFrame)

    def test_not_barrier(self):
        """Unite always produces single 'main' output, so is not a barrier."""
        comp = Unite("u", {})
        assert comp.is_barrier is False

    # ---- Integration tests (D-11) ----

    def test_integration_pipeline(self):
        """Verify Unite resolves from REGISTRY, validates correctly, full apply."""
        from src.v2.components.registry import REGISTRY

        cls = REGISTRY.get("unite")
        assert cls is Unite

        comp = cls("unite_integration", {})
        errors = comp.validate()
        assert errors == []

        # Full apply integration
        df1 = pl.DataFrame({"id": [1, 2], "name": ["A", "B"]}).lazy()
        df2 = pl.DataFrame({"id": [3, 4], "name": ["C", "D"]}).lazy()
        result = comp.apply({"a": df1, "b": df2})
        collected = result["main"].collect()
        assert len(collected) == 4
        assert collected["id"].to_list() == [1, 2, 3, 4]

    def test_integration_through_engine(self, tmp_path):
        """Run Unite through PyETLEngine with two file_input_delimited sources."""
        # Write two CSVs for the source components
        csv1 = tmp_path / "input1.csv"
        csv1.write_text("id;name\n1;A\n2;B\n")

        csv2 = tmp_path / "input2.csv"
        csv2.write_text("id;name\n3;C\n4;D\n")

        job_config = {
            "name": "unite_integration_test",
            "engine": "v2",
            "components": [
                {
                    "id": "src1",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(csv1),
                        "delimiter": ";",
                        "schema": [
                            {"name": "id", "type": "int"},
                            {"name": "name", "type": "string"},
                        ],
                    },
                },
                {
                    "id": "src2",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(csv2),
                        "delimiter": ";",
                        "schema": [
                            {"name": "id", "type": "int"},
                            {"name": "name", "type": "string"},
                        ],
                    },
                },
                {
                    "id": "merge",
                    "type": "unite",
                    "config": {},
                },
            ],
            "flows": [
                {
                    "source": "src1",
                    "target": "merge",
                    "output": "main",
                    "input": "from_src1",
                },
                {
                    "source": "src2",
                    "target": "merge",
                    "output": "main",
                    "input": "from_src2",
                },
            ],
        }
        result = self.run_integration(job_config)
        assert result["status"] == "success"

    # ---- Benchmark tests (D-16, D-18) ----

    @staticmethod
    def _make_benchmark_data(n: int = 100_000) -> list:
        """Create 3 LazyFrames each with n rows for benchmarking."""
        import random

        random.seed(42)
        frames = []
        for _ in range(3):
            frames.append(
                pl.DataFrame(
                    {
                        "id": list(range(n)),
                        "name": [f"name_{i}" for i in range(n)],
                        "amount": [random.uniform(0, 10000) for _ in range(n)],
                        "category": [f"cat_{i % 50}" for i in range(n)],
                        "active": [i % 3 != 0 for i in range(n)],
                    }
                ).lazy()
            )
        return frames

    @pytest.mark.benchmark
    def test_benchmark_ratio(self):
        """Verify Unite is within 10% of raw pl.concat (D-18).

        Uses 1M rows per frame (3 frames) so Polars work dominates Python overhead.
        """
        frames = self._make_benchmark_data(n=1_000_000)
        inputs = {f"input_{i}": f for i, f in enumerate(frames)}
        comp = Unite("bench_ratio", {})

        # Warmup both
        for _ in range(100):
            comp.apply(inputs)["main"].collect()
            pl.concat(frames, how="vertical").collect()

        # Run v2
        v2_timings = []
        for _ in range(5):
            start = time.perf_counter_ns()
            result = comp.apply(inputs)
            result["main"].collect()
            v2_timings.append(time.perf_counter_ns() - start)

        # Run raw
        raw_timings = []
        for _ in range(5):
            start = time.perf_counter_ns()
            pl.concat(frames, how="vertical").collect()
            raw_timings.append(time.perf_counter_ns() - start)

        v2_median = sorted(v2_timings)[len(v2_timings) // 2]
        raw_median = sorted(raw_timings)[len(raw_timings) // 2]

        ratio = v2_median / raw_median if raw_median > 0 else float("inf")
        assert ratio <= 1.10, (
            f"Unite is {ratio:.2f}x slower than raw pl.concat "
            f"(v2={v2_median / 1e6:.2f}ms, raw={raw_median / 1e6:.2f}ms). "
            f"Must be within 1.10x per D-18."
        )
