"""Tests for OutputRouter -- data flow routing between components.

Covers: output routing for all flow types (flow, reject, filter, iterate),
input resolution (0, 1, N inputs), readiness checking, flow cleanup with
cross-subjob consumer safety (D-16), and streaming chunk handling (PERF-01).
"""
import pytest
import pandas as pd

from src.v1.engine.output_router import OutputRouter


def _make_router(flows, components=None):
    """Build OutputRouter with flow and component configs."""
    if components is None:
        # Auto-generate minimal component configs from flows
        comp_ids = set()
        for f in flows:
            comp_ids.add(f["from"])
            comp_ids.add(f["to"])
        components = [{"id": cid, "inputs": [], "outputs": []} for cid in comp_ids]
    return OutputRouter(flows, components)


# ---------------------------------------------------------------------------
# TestRouteOutputs
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRouteOutputs:
    """route_outputs maps component results to named flows based on flow config."""

    def test_route_main_to_flow(self):
        router = _make_router([
            {"name": "row1", "from": "A", "to": "B", "type": "flow"},
        ])
        df = pd.DataFrame({"x": [1, 2, 3]})
        router.route_outputs("A", {"main": df})
        assert router.has_flow_data("row1")
        pd.testing.assert_frame_equal(router.get_flow_data("row1"), df)

    def test_route_reject_to_reject_flow(self):
        router = _make_router([
            {"name": "reject1", "from": "A", "to": "B", "type": "reject"},
        ])
        df = pd.DataFrame({"err": ["bad"]})
        router.route_outputs("A", {"reject": df})
        assert router.has_flow_data("reject1")
        pd.testing.assert_frame_equal(router.get_flow_data("reject1"), df)

    def test_route_main_to_filter_flow(self):
        router = _make_router([
            {"name": "filter1", "from": "A", "to": "B", "type": "filter"},
        ])
        df = pd.DataFrame({"x": [10]})
        router.route_outputs("A", {"main": df})
        assert router.has_flow_data("filter1")
        pd.testing.assert_frame_equal(router.get_flow_data("filter1"), df)

    def test_route_iterate_to_iterate_flow(self):
        router = _make_router([
            {"name": "iter1", "from": "A", "to": "B", "type": "iterate"},
        ])
        items = [{"file": "/tmp/a.csv"}, {"file": "/tmp/b.csv"}]
        router.route_outputs("A", {"iterate": items})
        assert router.has_flow_data("iter1")
        assert router.get_flow_data("iter1") == items

    def test_route_none_main_skipped(self):
        router = _make_router([
            {"name": "row1", "from": "A", "to": "B", "type": "flow"},
        ])
        router.route_outputs("A", {"main": None})
        assert not router.has_flow_data("row1")

    def test_route_multiple_outputs(self):
        router = _make_router([
            {"name": "row1", "from": "A", "to": "B", "type": "flow"},
            {"name": "reject1", "from": "A", "to": "C", "type": "reject"},
        ])
        main_df = pd.DataFrame({"x": [1]})
        reject_df = pd.DataFrame({"err": ["bad"]})
        router.route_outputs("A", {"main": main_df, "reject": reject_df})
        pd.testing.assert_frame_equal(router.get_flow_data("row1"), main_df)
        pd.testing.assert_frame_equal(router.get_flow_data("reject1"), reject_df)

    def test_route_named_output_declared(self):
        components = [
            {"id": "A", "inputs": [], "outputs": ["custom_out"]},
            {"id": "B", "inputs": ["custom_out"], "outputs": []},
        ]
        router = _make_router([], components)
        df = pd.DataFrame({"y": [5]})
        router.route_outputs("A", {"custom_out": df})
        pd.testing.assert_frame_equal(router.get_flow_data("custom_out"), df)

    def test_route_named_output_undeclared(self):
        components = [
            {"id": "A", "inputs": [], "outputs": []},
            {"id": "B", "inputs": [], "outputs": []},
        ]
        router = _make_router([], components)
        df = pd.DataFrame({"z": [99]})
        router.route_outputs("A", {"extra_data": df})
        pd.testing.assert_frame_equal(router.get_flow_data("A_extra_data"), df)


# ---------------------------------------------------------------------------
# TestGetInputData
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGetInputData:
    """get_input_data resolves upstream flow data for a component."""

    def test_single_input_returns_dataframe(self):
        components = [
            {"id": "A", "inputs": [], "outputs": ["row1"]},
            {"id": "B", "inputs": ["row1"], "outputs": []},
        ]
        router = _make_router(
            [{"name": "row1", "from": "A", "to": "B", "type": "flow"}],
            components,
        )
        df = pd.DataFrame({"x": [1, 2]})
        router.route_outputs("A", {"main": df})
        result = router.get_input_data("B")
        pd.testing.assert_frame_equal(result, df)

    def test_multiple_inputs_returns_dict(self):
        components = [
            {"id": "A", "inputs": [], "outputs": ["row1"]},
            {"id": "B", "inputs": [], "outputs": ["row2"]},
            {"id": "C", "inputs": ["row1", "row2"], "outputs": []},
        ]
        router = _make_router(
            [
                {"name": "row1", "from": "A", "to": "C", "type": "flow"},
                {"name": "row2", "from": "B", "to": "C", "type": "flow"},
            ],
            components,
        )
        df1 = pd.DataFrame({"x": [1]})
        df2 = pd.DataFrame({"y": [2]})
        router.route_outputs("A", {"main": df1})
        router.route_outputs("B", {"main": df2})
        result = router.get_input_data("C")
        assert isinstance(result, dict)
        pd.testing.assert_frame_equal(result["row1"], df1)
        pd.testing.assert_frame_equal(result["row2"], df2)

    def test_no_inputs_returns_none(self):
        components = [{"id": "A", "inputs": [], "outputs": []}]
        router = _make_router([], components)
        assert router.get_input_data("A") is None

    def test_missing_input_data_returns_none_in_dict(self):
        components = [
            {"id": "A", "inputs": [], "outputs": ["row1"]},
            {"id": "B", "inputs": [], "outputs": ["row2"]},
            {"id": "C", "inputs": ["row1", "row2"], "outputs": []},
        ]
        router = _make_router(
            [
                {"name": "row1", "from": "A", "to": "C", "type": "flow"},
                {"name": "row2", "from": "B", "to": "C", "type": "flow"},
            ],
            components,
        )
        df1 = pd.DataFrame({"x": [1]})
        router.route_outputs("A", {"main": df1})
        # B has not routed yet, so row2 is missing
        result = router.get_input_data("C")
        assert isinstance(result, dict)
        pd.testing.assert_frame_equal(result["row1"], df1)
        assert result["row2"] is None


# ---------------------------------------------------------------------------
# TestAreInputsReady
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestAreInputsReady:
    """are_inputs_ready checks if all upstream flows have data."""

    def test_no_inputs_always_ready(self):
        components = [{"id": "A", "inputs": [], "outputs": []}]
        router = _make_router([], components)
        assert router.are_inputs_ready("A") is True

    def test_all_inputs_available(self):
        components = [
            {"id": "A", "inputs": [], "outputs": ["row1"]},
            {"id": "B", "inputs": ["row1"], "outputs": []},
        ]
        router = _make_router(
            [{"name": "row1", "from": "A", "to": "B", "type": "flow"}],
            components,
        )
        router.route_outputs("A", {"main": pd.DataFrame({"x": [1]})})
        assert router.are_inputs_ready("B") is True

    def test_missing_input(self):
        components = [
            {"id": "A", "inputs": [], "outputs": ["row1"]},
            {"id": "B", "inputs": ["row1"], "outputs": []},
        ]
        router = _make_router(
            [{"name": "row1", "from": "A", "to": "B", "type": "flow"}],
            components,
        )
        # A hasn't routed yet
        assert router.are_inputs_ready("B") is False

    def test_becomes_ready_after_route(self):
        components = [
            {"id": "A", "inputs": [], "outputs": ["row1"]},
            {"id": "B", "inputs": ["row1"], "outputs": []},
        ]
        router = _make_router(
            [{"name": "row1", "from": "A", "to": "B", "type": "flow"}],
            components,
        )
        assert router.are_inputs_ready("B") is False
        router.route_outputs("A", {"main": pd.DataFrame({"x": [1]})})
        assert router.are_inputs_ready("B") is True


# ---------------------------------------------------------------------------
# TestClearFlows
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestClearFlows:
    """Flow cleanup including cross-subjob consumer safety (D-16)."""

    def test_clear_flow_removes_data(self):
        router = _make_router([
            {"name": "row1", "from": "A", "to": "B", "type": "flow"},
        ])
        router.route_outputs("A", {"main": pd.DataFrame({"x": [1]})})
        assert router.has_flow_data("row1")
        router.clear_flow("row1")
        assert not router.has_flow_data("row1")

    def test_clear_flow_nonexistent_no_error(self):
        router = _make_router([])
        # Should not raise
        router.clear_flow("nonexistent")

    def test_clear_subjob_flows_clears_outgoing(self):
        """Flows within a subjob are cleared after subjob completion."""
        components = [
            {"id": "A", "inputs": [], "outputs": ["row1"]},
            {"id": "B", "inputs": ["row1"], "outputs": ["row2"]},
            {"id": "C", "inputs": ["row2"], "outputs": []},
        ]
        router = _make_router(
            [
                {"name": "row1", "from": "A", "to": "B", "type": "flow"},
                {"name": "row2", "from": "B", "to": "C", "type": "flow"},
            ],
            components,
        )
        router.route_outputs("A", {"main": pd.DataFrame({"x": [1]})})
        router.route_outputs("B", {"main": pd.DataFrame({"y": [2]})})

        subjob_ids = {"A", "B", "C"}
        router.clear_subjob_flows(subjob_ids, executed_components=subjob_ids)
        assert not router.has_flow_data("row1")
        assert not router.has_flow_data("row2")

    def test_clear_subjob_flows_preserves_other_subjobs(self):
        """Clearing subjob_1 does not affect subjob_2 flows."""
        components = [
            {"id": "A", "inputs": [], "outputs": ["row1"]},
            {"id": "B", "inputs": ["row1"], "outputs": []},
            {"id": "X", "inputs": [], "outputs": ["row9"]},
            {"id": "Y", "inputs": ["row9"], "outputs": []},
        ]
        router = _make_router(
            [
                {"name": "row1", "from": "A", "to": "B", "type": "flow"},
                {"name": "row9", "from": "X", "to": "Y", "type": "flow"},
            ],
            components,
        )
        router.route_outputs("A", {"main": pd.DataFrame({"x": [1]})})
        router.route_outputs("X", {"main": pd.DataFrame({"z": [9]})})

        # Clear only subjob_1
        router.clear_subjob_flows({"A", "B"}, executed_components={"A", "B"})
        assert not router.has_flow_data("row1")
        # subjob_2 intact
        assert router.has_flow_data("row9")

    def test_clear_subjob_flows_preserves_cross_subjob_pending_consumer(self):
        """Cross-subjob flow preserved when downstream consumer has not executed."""
        components = [
            {"id": "A", "inputs": [], "outputs": ["cross_flow"]},
            {"id": "B", "inputs": [], "outputs": []},
            {"id": "C", "inputs": ["cross_flow"], "outputs": []},
        ]
        router = _make_router(
            [{"name": "cross_flow", "from": "A", "to": "C", "type": "flow"}],
            components,
        )
        router.route_outputs("A", {"main": pd.DataFrame({"x": [1]})})

        # C is in subjob_2, not in subjob_1. C has NOT executed yet.
        subjob_1 = {"A", "B"}
        router.clear_subjob_flows(subjob_1, executed_components={"A", "B"})

        # cross_flow must be preserved because C (consumer) hasn't executed
        assert router.has_flow_data("cross_flow")

    def test_clear_subjob_flows_clears_cross_subjob_after_consumer_executed(self):
        """Cross-subjob flow cleared once downstream consumer has executed."""
        components = [
            {"id": "A", "inputs": [], "outputs": ["cross_flow"]},
            {"id": "B", "inputs": [], "outputs": []},
            {"id": "C", "inputs": ["cross_flow"], "outputs": []},
        ]
        router = _make_router(
            [{"name": "cross_flow", "from": "A", "to": "C", "type": "flow"}],
            components,
        )
        router.route_outputs("A", {"main": pd.DataFrame({"x": [1]})})

        # C has already executed
        subjob_1 = {"A", "B"}
        router.clear_subjob_flows(subjob_1, executed_components={"A", "B", "C"})

        # cross_flow can be cleared since C already consumed it
        assert not router.has_flow_data("cross_flow")


# ---------------------------------------------------------------------------
# TestStreamingChunkRouting
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestStreamingChunkRouting:
    """Streaming/chunked result routing (PERF-01)."""

    def test_route_chunk_result(self):
        router = _make_router([
            {"name": "row1", "from": "A", "to": "B", "type": "flow"},
        ])
        df = pd.DataFrame({"x": [1, 2, 3]})
        router.route_outputs("A", {"main": df})
        pd.testing.assert_frame_equal(router.get_flow_data("row1"), df)

    def test_route_multiple_chunks_last_wins(self):
        """In batch mode, routing a second time replaces the first."""
        router = _make_router([
            {"name": "row1", "from": "A", "to": "B", "type": "flow"},
        ])
        df1 = pd.DataFrame({"x": [1]})
        df2 = pd.DataFrame({"x": [2, 3]})
        router.route_outputs("A", {"main": df1})
        router.route_outputs("A", {"main": df2})
        pd.testing.assert_frame_equal(router.get_flow_data("row1"), df2)


# ---------------------------------------------------------------------------
# TestDiagnostics
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDiagnostics:
    """Diagnostic helper methods."""

    def test_get_pending_flow_names(self):
        router = _make_router([
            {"name": "row1", "from": "A", "to": "B", "type": "flow"},
            {"name": "row2", "from": "B", "to": "C", "type": "flow"},
        ])
        router.route_outputs("A", {"main": pd.DataFrame({"x": [1]})})
        pending = router.get_pending_flow_names()
        assert "row1" in pending
        assert "row2" not in pending

    def test_has_flow_data_returns_false_for_missing(self):
        router = _make_router([])
        assert router.has_flow_data("nonexistent") is False
