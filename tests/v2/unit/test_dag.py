"""Tests for basic DAG operations."""
import pytest
from src.v2.execution.dag import DAG, DAGBuilder, DAGValidationError


class TestDAGBasics:
    def test_linear_execution_order(self):
        dag = DAG()
        dag.add_node("a", "file_input", {})
        dag.add_node("b", "filter", {})
        dag.add_node("c", "file_output", {})
        dag.add_edge("a", "b")
        dag.add_edge("b", "c")
        assert dag.get_execution_order() == ["a", "b", "c"]

    def test_cycle_detection(self):
        dag = DAG()
        dag.add_node("a", "filter", {})
        dag.add_node("b", "filter", {})
        dag.add_edge("a", "b")
        dag.add_edge("b", "a")
        with pytest.raises(DAGValidationError, match="cycles"):
            dag.get_execution_order()

    def test_fan_out(self):
        dag = DAG()
        dag.add_node("a", "file_input", {})
        dag.add_node("b", "filter", {})
        dag.add_node("c", "filter", {})
        dag.add_edge("a", "b")
        dag.add_edge("a", "c")
        order = dag.get_execution_order()
        assert order.index("a") < order.index("b")
        assert order.index("a") < order.index("c")


    def test_ref_counts(self):
        """Reference counts track how many consumers each component has"""
        dag = DAG()
        dag.add_node("a", "file_input", {})
        dag.add_node("b", "filter", {})
        dag.add_node("c", "file_output", {})
        dag.add_node("d", "file_output", {})
        dag.add_edge("a", "b")
        dag.add_edge("b", "c")
        dag.add_edge("b", "d")
        ref_counts = dag.get_ref_counts()
        assert ref_counts["a"] == 1  # feeds b
        assert ref_counts["b"] == 2  # feeds c and d
        assert ref_counts["c"] == 0  # sink
        assert ref_counts["d"] == 0  # sink


# ---- Phase 1.1 probe tests (D-09 #2): Kahn's algorithm determinism ----
# These are permanent regression guards for DAG.get_execution_order.
# Added by plan 01.1-01. If either fails, the engine has lost its
# deterministic-execution-order guarantee and downstream component phases
# cannot rely on reproducible runs.


def test_kahn_determinism_on_ambiguous_dag():
    """
    Probe test (Phase 1.1, D-09 #2): assert DAG.get_execution_order() returns
    the same ordering across repeated calls when topological ordering is ambiguous.
    The engine relies on this to produce reproducible runs.
    """
    dag = DAG()
    # Three independent sources all flowing into one sink.
    # Topological order is ambiguous among the three sources; sink must be last.
    dag.add_node("a", "source", {})
    dag.add_node("b", "source", {})
    dag.add_node("c", "source", {})
    dag.add_node("sink", "sink", {})
    dag.add_edge("a", "sink")
    dag.add_edge("b", "sink")
    dag.add_edge("c", "sink")

    order_1 = dag.get_execution_order()
    # Rebuild to force recomputation (existing DAG caches the result).
    dag._execution_order = None
    order_2 = dag.get_execution_order()
    dag._execution_order = None
    order_3 = dag.get_execution_order()

    assert order_1 == order_2 == order_3, (
        f"get_execution_order not deterministic: "
        f"{order_1} vs {order_2} vs {order_3}"
    )
    assert order_1[-1] == "sink", f"sink must be last, got {order_1}"
    # All three sources must appear before the sink.
    for src in ("a", "b", "c"):
        assert order_1.index(src) < order_1.index("sink"), (
            f"source {src} must come before sink, got {order_1}"
        )


def test_kahn_sorted_tiebreak_on_ambiguous_dag():
    """
    Probe test (Phase 1.1, D-09 #2): assert alphabetical tiebreak when
    ambiguous — 'alpha' must come before 'zebra' when both are in the same
    Kahn wave (i.e., both sources of the same sink).
    """
    dag = DAG()
    dag.add_node("zebra", "source", {})
    dag.add_node("alpha", "source", {})
    dag.add_node("sink", "sink", {})
    dag.add_edge("zebra", "sink")
    dag.add_edge("alpha", "sink")

    order = dag.get_execution_order()
    assert order.index("alpha") < order.index("zebra"), (
        f"expected sorted tiebreak (alpha < zebra), got {order}"
    )
    assert order[-1] == "sink"
