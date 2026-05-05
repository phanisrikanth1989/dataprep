"""Unit tests for ENABLE_PARALLEL/NUMBER_PARALLEL converter extraction (Phase 10-05)."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.converters.talend_to_v1.converter import TalendToV1Converter, convert_job
from src.converters.talend_to_v1.xml_parser import XmlParser


SAMPLE_FILELIST = "tests/talend_xml_samples/Job_tFileList_0.1.item"
SAMPLE_FLOWTOITERATE = "tests/talend_xml_samples/Job_tFlowToIterate_0.1.item"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_iterate_flows(result):
    """Return iterate-typed flow dicts from a convert_job result."""
    return [f for f in result["flows"] if f.get("type") == "iterate"]


def _get_engine_gap_parallel_entries(result):
    """Return engine_gap needs_review entries mentioning Parallel iteration."""
    return [
        e for e in result.get("_needs_review", [])
        if e.get("severity") == "engine_gap"
        and "Parallel iteration" in e.get("message", "")
    ]


# ---------------------------------------------------------------------------
# Tests: extraction from real .item fixtures
# ---------------------------------------------------------------------------


class TestExtractFromRealFixtures:
    def test_filelist_fixture_extracts_enable_parallel_false(self):
        """Job_tFileList_0.1.item ITERATE connection has ENABLE_PARALLEL=false."""
        result = convert_job(SAMPLE_FILELIST)
        iterate_flows = _get_iterate_flows(result)
        assert iterate_flows, "No iterate flow found in Job_tFileList fixture"
        assert iterate_flows[0]["enable_parallel"] is False

    def test_filelist_fixture_extracts_number_parallel(self):
        """Job_tFileList_0.1.item ITERATE connection has NUMBER_PARALLEL=2."""
        result = convert_job(SAMPLE_FILELIST)
        iterate_flows = _get_iterate_flows(result)
        assert iterate_flows, "No iterate flow found in Job_tFileList fixture"
        assert iterate_flows[0]["number_parallel"] == 2

    def test_flowtoiterate_fixture_extracts_enable_parallel_false(self):
        """Job_tFlowToIterate_0.1.item ITERATE connection has ENABLE_PARALLEL=false."""
        result = convert_job(SAMPLE_FLOWTOITERATE)
        iterate_flows = _get_iterate_flows(result)
        assert iterate_flows, "No iterate flow found in Job_tFlowToIterate fixture"
        assert iterate_flows[0]["enable_parallel"] is False

    def test_flowtoiterate_fixture_extracts_number_parallel(self):
        """Job_tFlowToIterate_0.1.item ITERATE connection has NUMBER_PARALLEL=2."""
        result = convert_job(SAMPLE_FLOWTOITERATE)
        iterate_flows = _get_iterate_flows(result)
        assert iterate_flows, "No iterate flow found in Job_tFlowToIterate fixture"
        assert iterate_flows[0]["number_parallel"] == 2

    def test_no_needs_review_when_enable_parallel_false(self):
        """ENABLE_PARALLEL=false does not emit a Parallel iteration engine_gap entry."""
        result = convert_job(SAMPLE_FLOWTOITERATE)
        parallel_entries = _get_engine_gap_parallel_entries(result)
        assert parallel_entries == [], (
            "Expected no Parallel iteration engine_gap entry when ENABLE_PARALLEL=false"
        )

    def test_no_needs_review_when_enable_parallel_false_filelist(self):
        """Same check for Job_tFileList fixture (ENABLE_PARALLEL=false)."""
        result = convert_job(SAMPLE_FILELIST)
        parallel_entries = _get_engine_gap_parallel_entries(result)
        assert parallel_entries == [], (
            "Expected no Parallel iteration engine_gap entry when ENABLE_PARALLEL=false"
        )


# ---------------------------------------------------------------------------
# Tests: ENABLE_PARALLEL=true branch via mutation
# ---------------------------------------------------------------------------


class TestEnableParallelTrueBranch:
    def test_enable_parallel_true_emits_engine_gap(self, tmp_path):
        """Mutating ENABLE_PARALLEL to true produces a Parallel iteration engine_gap entry."""
        xml = Path(SAMPLE_FLOWTOITERATE).read_text(encoding="utf-8")
        mutated = xml.replace(
            'name="ENABLE_PARALLEL" value="false"',
            'name="ENABLE_PARALLEL" value="true"',
        )
        assert 'name="ENABLE_PARALLEL" value="true"' in mutated, (
            "Mutation did not change ENABLE_PARALLEL to true"
        )

        mutated_path = tmp_path / "mutated.item"
        mutated_path.write_text(mutated, encoding="utf-8")
        result = convert_job(str(mutated_path))

        parallel_entries = _get_engine_gap_parallel_entries(result)
        assert len(parallel_entries) >= 1, (
            "Expected at least one Parallel iteration engine_gap entry when ENABLE_PARALLEL=true"
        )

        entry = parallel_entries[0]
        assert entry["severity"] == "engine_gap"
        assert "Parallel iteration" in entry["message"]
        assert "sequentially" in entry["message"]

    def test_enable_parallel_true_sets_flow_flag(self, tmp_path):
        """Mutated ENABLE_PARALLEL=true results in enable_parallel=True in the flow dict."""
        xml = Path(SAMPLE_FLOWTOITERATE).read_text(encoding="utf-8")
        mutated = xml.replace(
            'name="ENABLE_PARALLEL" value="false"',
            'name="ENABLE_PARALLEL" value="true"',
        )
        mutated_path = tmp_path / "mutated.item"
        mutated_path.write_text(mutated, encoding="utf-8")
        result = convert_job(str(mutated_path))

        iterate_flows = _get_iterate_flows(result)
        assert iterate_flows, "No iterate flow found in mutated fixture"
        assert iterate_flows[0]["enable_parallel"] is True

    def test_enable_parallel_true_records_component_id(self, tmp_path):
        """engine_gap entry component_id matches the iterate source component."""
        xml = Path(SAMPLE_FLOWTOITERATE).read_text(encoding="utf-8")
        mutated = xml.replace(
            'name="ENABLE_PARALLEL" value="false"',
            'name="ENABLE_PARALLEL" value="true"',
        )
        mutated_path = tmp_path / "mutated.item"
        mutated_path.write_text(mutated, encoding="utf-8")
        result = convert_job(str(mutated_path))

        parallel_entries = _get_engine_gap_parallel_entries(result)
        assert parallel_entries
        entry = parallel_entries[0]
        # component_id must be a non-empty string (the iterate source)
        assert entry.get("component_id"), "engine_gap entry missing component_id"

        # Confirm it matches the source of the iterate flow
        iterate_flows = _get_iterate_flows(result)
        assert iterate_flows
        assert entry["component_id"] == iterate_flows[0]["from"]


# ---------------------------------------------------------------------------
# Tests: Non-iterate flow regression (PATTERNS.md Section 7g)
# ---------------------------------------------------------------------------


class TestNonIterateFlowRegression:
    def test_non_iterate_flows_have_no_parallel_keys(self):
        """Non-ITERATE flow dicts must not contain enable_parallel or number_parallel."""
        result = convert_job(SAMPLE_FLOWTOITERATE)
        non_iterate = [f for f in result["flows"] if f.get("type") != "iterate"]
        for flow in non_iterate:
            assert "enable_parallel" not in flow, (
                f"Non-iterate flow '{flow.get('name')}' unexpectedly contains enable_parallel"
            )
            assert "number_parallel" not in flow, (
                f"Non-iterate flow '{flow.get('name')}' unexpectedly contains number_parallel"
            )

    def test_non_iterate_flows_have_no_parallel_keys_filelist(self):
        """Same regression check for Job_tFileList fixture."""
        result = convert_job(SAMPLE_FILELIST)
        non_iterate = [f for f in result["flows"] if f.get("type") != "iterate"]
        for flow in non_iterate:
            assert "enable_parallel" not in flow, (
                f"Non-iterate flow '{flow.get('name')}' unexpectedly contains enable_parallel"
            )
            assert "number_parallel" not in flow, (
                f"Non-iterate flow '{flow.get('name')}' unexpectedly contains number_parallel"
            )


# ---------------------------------------------------------------------------
# Tests: iterate flow dict shape compatibility
# ---------------------------------------------------------------------------


class TestIterateFlowDictShape:
    def test_iterate_flow_has_all_required_keys(self):
        """Iterate flow dict has required base keys AND new parallel keys."""
        result = convert_job(SAMPLE_FILELIST)
        iterate_flows = _get_iterate_flows(result)
        assert iterate_flows, "No iterate flow found"
        f = iterate_flows[0]
        for key in ("name", "from", "to", "type", "enable_parallel", "number_parallel"):
            assert key in f, f"Iterate flow missing required key: {key}"

    def test_iterate_flow_type_is_lowercase(self):
        """Iterate flow type is lowercased 'iterate' (consistent with other flow types)."""
        result = convert_job(SAMPLE_FILELIST)
        iterate_flows = _get_iterate_flows(result)
        assert iterate_flows
        assert iterate_flows[0]["type"] == "iterate"

    def test_iterate_flow_has_from_and_to(self):
        """Iterate flow dict has non-empty 'from' and 'to' keys."""
        result = convert_job(SAMPLE_FILELIST)
        iterate_flows = _get_iterate_flows(result)
        assert iterate_flows
        f = iterate_flows[0]
        assert f["from"], "Iterate flow 'from' is empty"
        assert f["to"], "Iterate flow 'to' is empty"


# ---------------------------------------------------------------------------
# Tests: XmlParser params population
# ---------------------------------------------------------------------------


class TestXmlParserParamsPopulation:
    def test_iterate_connection_params_populated(self):
        """XmlParser._parse_connections populates params dict with ENABLE_PARALLEL."""
        parser = XmlParser()
        job = parser.parse(SAMPLE_FILELIST)
        iterate_conns = [c for c in job.connections if c.connector_type == "ITERATE"]
        assert iterate_conns, "No ITERATE connection found in Job_tFileList fixture"
        conn = iterate_conns[0]
        assert "ENABLE_PARALLEL" in conn.params, (
            f"ENABLE_PARALLEL not found in params; got {conn.params}"
        )
        assert "NUMBER_PARALLEL" in conn.params, (
            f"NUMBER_PARALLEL not found in params; got {conn.params}"
        )

    def test_non_iterate_connections_have_empty_params_or_no_parallel_keys(self):
        """Non-ITERATE connections do not have ENABLE_PARALLEL in params."""
        parser = XmlParser()
        job = parser.parse(SAMPLE_FLOWTOITERATE)
        non_iterate = [c for c in job.connections if c.connector_type != "ITERATE"]
        for conn in non_iterate:
            assert "ENABLE_PARALLEL" not in conn.params, (
                f"Non-iterate connection '{conn.name}' unexpectedly has ENABLE_PARALLEL"
            )
