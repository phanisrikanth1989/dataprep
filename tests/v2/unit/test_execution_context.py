import pytest
import polars as pl
from src.v2.execution.context import ExecutionContext


class TestExecutionContext:
    def test_store_and_retrieve_output(self):
        ctx = ExecutionContext()
        df = pl.DataFrame({"a": [1]}).lazy()
        ctx.store_output("comp_a", "main", df)
        result = ctx.get_output("comp_a", "main")
        assert result is not None
        assert result.collect()["a"][0] == 1

    def test_ref_counting_frees_output(self):
        ctx = ExecutionContext()
        ctx.set_ref_count("comp_a", 2)
        df = pl.DataFrame({"a": [1]}).lazy()
        ctx.store_output("comp_a", "main", df)

        # First consumer
        ctx.decrement_ref("comp_a")
        assert ctx.get_output("comp_a", "main") is not None  # still alive

        # Second consumer
        ctx.decrement_ref("comp_a")
        assert ctx.get_output("comp_a", "main") is None  # freed

    def test_component_stats(self):
        ctx = ExecutionContext()
        ctx.record_component_stats("comp_a", {
            "type": "filter",
            "duration_ms": 42,
            "rows_out": {"main": 1000},
        })
        stats = ctx.get_component_stats("comp_a")
        assert stats["duration_ms"] == 42

    def test_context_vars(self):
        ctx = ExecutionContext(context_vars={"rate": 0.08})
        assert ctx.get("rate") == 0.08

    def test_resolve_string(self):
        ctx = ExecutionContext(context_vars={"dir": "/data"})
        assert ctx.resolve("${context.dir}/file.csv") == "/data/file.csv"

    def test_execution_result(self):
        ctx = ExecutionContext()
        ctx.record_component_stats("a", {"type": "file_input_delimited", "duration_ms": 10})
        ctx.record_component_stats("b", {"type": "filter", "duration_ms": 20})
        result = ctx.get_execution_result()
        assert "components" in result
        assert len(result["components"]) == 2

    def test_ref_count_zero_on_no_downstream(self):
        """Components with no downstream (sinks) don't need ref counting"""
        ctx = ExecutionContext()
        ctx.set_ref_count("sink", 0)
        df = pl.DataFrame({"a": [1]}).lazy()
        ctx.store_output("sink", "main", df)
        # With refcount 0, output should be freed immediately
        # (or just not tracked -- either way, the output was consumed)

    def test_multiple_outputs(self):
        """Component with multiple named outputs"""
        ctx = ExecutionContext()
        ctx.store_output("map1", "main", pl.DataFrame({"a": [1]}).lazy())
        ctx.store_output("map1", "reject", pl.DataFrame({"err": ["bad"]}).lazy())
        main = ctx.get_output("map1", "main")
        reject = ctx.get_output("map1", "reject")
        assert main is not None
        assert reject is not None
        assert main.collect()["a"][0] == 1
        assert reject.collect()["err"][0] == "bad"


class TestClearStage:
    """Tests for clearing stage intermediates."""

    def test_clear_stage_removes_outputs(self):
        ctx = ExecutionContext(context_vars={})
        ctx.store_output("A", "main", pl.DataFrame({"x": [1]}).lazy())
        ctx.store_output("B", "main", pl.DataFrame({"x": [2]}).lazy())
        ctx.store_output("C", "main", pl.DataFrame({"x": [3]}).lazy())

        ctx.clear_stage({"A", "B"})

        assert ctx.get_output("A", "main") is None
        assert ctx.get_output("B", "main") is None
        assert ctx.get_output("C", "main") is not None

    def test_clear_stage_removes_ref_counts(self):
        ctx = ExecutionContext(context_vars={})
        ctx.set_ref_count("A", 2)
        ctx.set_ref_count("B", 1)
        ctx.set_ref_count("C", 3)

        ctx.clear_stage({"A", "B"})

        assert "C" in ctx._ref_counts
        assert "A" not in ctx._ref_counts
        assert "B" not in ctx._ref_counts

    def test_clear_stage_preserves_context_vars(self):
        ctx = ExecutionContext(context_vars={"env": "PROD"})
        ctx.store_output("A", "main", pl.DataFrame({"x": [1]}).lazy())

        ctx.clear_stage({"A"})

        assert ctx.context_vars["env"] == "PROD"

    def test_clear_stage_preserves_component_stats(self):
        ctx = ExecutionContext(context_vars={})
        ctx.record_component_stats("A", {"rows_out": {"main": 100}})

        ctx.clear_stage({"A"})

        assert ctx.get_component_stats("A") is not None

    def test_clear_stage_with_empty_set(self):
        ctx = ExecutionContext(context_vars={})
        ctx.store_output("A", "main", pl.DataFrame({"x": [1]}).lazy())
        ctx.clear_stage(set())
        assert ctx.get_output("A", "main") is not None

    def test_clear_stage_with_nonexistent_components(self):
        ctx = ExecutionContext(context_vars={})
        ctx.clear_stage({"X", "Y"})  # should not error


# ---- Phase 1.1 probe tests (D-09 #3): ref count correctness + stage clear ----
# These are permanent regression guards for ExecutionContext.decrement_ref
# and ExecutionContext.clear_stage. Added by plan 01.1-01.
# Covers the memory-management lifecycle the engine relies on for multi-stage
# execution (PITFALLS #3 — stage boundary memory release).


def test_ref_count_freed_at_stage_boundary():
    """
    Probe test (Phase 1.1, D-09 #3): assert ExecutionContext properly frees
    outputs via decrement_ref when ref count reaches 0.

    The engine sets a component's ref count to its downstream consumer count,
    then decrements once per consuming downstream component. When the count
    hits 0, the output must be freed so the job does not hold onto every
    intermediate LazyFrame through end-of-job.
    """
    ctx = ExecutionContext()
    lf = pl.LazyFrame({"col": [1, 2, 3]})
    ctx.store_output("comp_a", "main", lf)
    ctx.set_ref_count("comp_a", 2)

    # First get — output still alive
    out_1 = ctx.get_output("comp_a", "main")
    assert out_1 is not None, "output missing after single store"

    # First decrement — count=1, still alive
    ctx.decrement_ref("comp_a")
    out_2 = ctx.get_output("comp_a", "main")
    assert out_2 is not None, (
        "output wrongly freed after first decrement (count should be 1)"
    )

    # Second decrement — count=0, must be freed
    ctx.decrement_ref("comp_a")
    out_3 = ctx.get_output("comp_a", "main")
    assert out_3 is None, (
        f"ExecutionContext did not free output after ref count hit 0; "
        f"still retrievable as {type(out_3).__name__}"
    )


def test_clear_stage_frees_listed_outputs_only():
    """
    Probe test (Phase 1.1, D-09 #3): assert clear_stage frees outputs for
    the listed components and leaves unlisted components untouched.

    The engine calls clear_stage(stage.component_ids) at each stage boundary
    to release the memory held by that stage's intermediates. The contract
    is 'free exactly the listed set' — over-freeing would drop live data
    from other stages; under-freeing would defeat the purpose.
    """
    ctx = ExecutionContext()
    lf_a = pl.LazyFrame({"x": [1]})
    lf_b = pl.LazyFrame({"y": [2]})
    lf_c = pl.LazyFrame({"z": [3]})
    ctx.store_output("comp_a", "main", lf_a)
    ctx.store_output("comp_b", "main", lf_b)
    ctx.store_output("comp_c", "main", lf_c)

    # Clear stage containing a and b
    ctx.clear_stage({"comp_a", "comp_b"})

    assert ctx.get_output("comp_a", "main") is None, (
        "comp_a not freed by clear_stage"
    )
    assert ctx.get_output("comp_b", "main") is None, (
        "comp_b not freed by clear_stage"
    )
    assert ctx.get_output("comp_c", "main") is not None, (
        "comp_c was wrongly freed by clear_stage"
    )
