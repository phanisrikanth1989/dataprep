"""Integration tests — end-to-end conversion of real .item XML files.

These tests exercise the full TalendToV1Converter pipeline against the
sample .item files shipped in ``sample_jobs/``.  They verify:

1. Smoke: every .item file converts without error and returns required keys
2. Component coverage: no ``_unsupported`` placeholders (registration gaps)
3. Validation: the built-in validator passes for every converted job
4. Structure: the complex tMap job contains expected structural elements
5. Java detection: demo_java_usage correctly flags java_config.enabled
6. Registry completeness: at least 85 types are registered
7. Backwards compatibility: structural comparison with old ComplexTalendConverter
"""
from __future__ import annotations

import pytest
from pathlib import Path
from typing import Any, Dict, List

# New converter under test
from src.converters.talend_to_v1.converter import TalendToV1Converter
from src.converters.talend_to_v1.components.registry import REGISTRY

# Old converter for comparison
from src.converters.complex_converter.converter import ComplexTalendConverter


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

SAMPLE_JOBS_DIR = Path(__file__).resolve().parents[3] / "sample_jobs"

# All .item files available for testing
_ITEM_FILES = sorted(SAMPLE_JOBS_DIR.rglob("*.item"))

# Named paths for targeted tests
_TFILELIST = SAMPLE_JOBS_DIR / "demo_tFileList_0.1.item"
_TFLOWTOITERATE = SAMPLE_JOBS_DIR / "demo_tFlowToIterate_0.1.item"
_JAVA_USAGE = SAMPLE_JOBS_DIR / "old" / "demo_java_usage_0.1.item"
_COMPLEX_TMAP = SAMPLE_JOBS_DIR / "old" / "Order_management_demo_complicated_tmap_0.1.item"

# Top-level keys every converted config must contain
_REQUIRED_KEYS = {
    "job_name",
    "job_type",
    "default_context",
    "context",
    "components",
    "flows",
    "triggers",
    "subjobs",
    "java_config",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def new_converter():
    return TalendToV1Converter()


@pytest.fixture
def old_converter():
    return ComplexTalendConverter()


# Cache converted results per session so we don't re-parse for every test
_CONVERTED_CACHE: Dict[str, Dict[str, Any]] = {}


def _convert_cached(path: Path) -> Dict[str, Any]:
    """Convert an .item file, caching the result for the session."""
    key = str(path)
    if key not in _CONVERTED_CACHE:
        _CONVERTED_CACHE[key] = TalendToV1Converter().convert_file(key)
    return _CONVERTED_CACHE[key]


# ---------------------------------------------------------------------------
# 1. Smoke tests — each .item file converts without error
# ---------------------------------------------------------------------------

class TestSmokeConversion:
    """Every .item file must convert without raising and return required keys."""

    @pytest.mark.parametrize("item_path", _ITEM_FILES, ids=lambda p: p.name)
    def test_converts_without_error(self, item_path):
        result = _convert_cached(item_path)
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"

    @pytest.mark.parametrize("item_path", _ITEM_FILES, ids=lambda p: p.name)
    def test_has_required_keys(self, item_path):
        result = _convert_cached(item_path)
        missing = _REQUIRED_KEYS - set(result.keys())
        assert not missing, f"Missing required keys: {missing}"

    @pytest.mark.parametrize("item_path", _ITEM_FILES, ids=lambda p: p.name)
    def test_components_is_nonempty_list(self, item_path):
        result = _convert_cached(item_path)
        assert isinstance(result["components"], list)
        assert len(result["components"]) > 0, "Job should have at least one component"

    @pytest.mark.parametrize("item_path", _ITEM_FILES, ids=lambda p: p.name)
    def test_java_config_structure(self, item_path):
        result = _convert_cached(item_path)
        jc = result["java_config"]
        assert "enabled" in jc
        assert "routines" in jc
        assert "libraries" in jc
        assert isinstance(jc["enabled"], bool)
        assert isinstance(jc["routines"], list)
        assert isinstance(jc["libraries"], list)


# ---------------------------------------------------------------------------
# 2. Component coverage — no unsupported placeholders
# ---------------------------------------------------------------------------

class TestComponentCoverage:
    """All components should be handled by a registered converter."""

    @pytest.mark.parametrize("item_path", _ITEM_FILES, ids=lambda p: p.name)
    def test_no_unsupported_components(self, item_path):
        result = _convert_cached(item_path)
        unsupported = [
            c for c in result["components"] if c.get("_unsupported", False)
        ]
        unsupported_types = [c.get("type", "unknown") for c in unsupported]
        assert len(unsupported) == 0, (
            f"Found {len(unsupported)} unsupported component(s): {unsupported_types}"
        )


# ---------------------------------------------------------------------------
# 3. Validator passes — no errors
# ---------------------------------------------------------------------------

class TestValidation:
    """Post-conversion validator should report no errors."""

    @pytest.mark.parametrize("item_path", _ITEM_FILES, ids=lambda p: p.name)
    def test_validation_passes(self, item_path):
        result = _convert_cached(item_path)
        validation = result.get("_validation", {})
        is_valid = validation.get("valid", False)
        if not is_valid:
            issues = validation.get("issues", [])
            error_issues = [i for i in issues if i.get("severity") == "error"]
            issue_msgs = [
                f"[{i['severity']}] {i.get('component_id', 'global')}: {i['message']}"
                for i in error_issues
            ]
            pytest.fail(
                f"Validation failed with {len(error_issues)} error(s):\n"
                + "\n".join(issue_msgs)
            )


# ---------------------------------------------------------------------------
# 4. Structure checks on complex tMap job
# ---------------------------------------------------------------------------

class TestComplexTMapStructure:
    """The complex tMap job should have rich structural output."""

    @pytest.fixture(autouse=True)
    def _load(self):
        self.result = _convert_cached(_COMPLEX_TMAP)

    def test_has_components(self):
        assert len(self.result["components"]) > 0

    def test_has_flows(self):
        assert len(self.result["flows"]) > 0

    def test_triggers_is_list(self):
        """Triggers may be empty for flow-only jobs, but must be a list."""
        assert isinstance(self.result["triggers"], list)

    def test_has_subjobs(self):
        assert len(self.result["subjobs"]) > 0

    def test_tmap_component_has_expected_config(self):
        """Find a tMap component and verify its config structure."""
        tmap_components = [
            c for c in self.result["components"]
            if c.get("type") == "tMap" or c.get("original_type") == "tMap"
        ]
        assert len(tmap_components) > 0, "Expected at least one tMap component"

        tmap = tmap_components[0]
        config = tmap.get("config", {})
        assert "inputs" in config, "tMap config should have 'inputs'"
        assert "variables" in config, "tMap config should have 'variables'"
        assert "outputs" in config, "tMap config should have 'outputs'"

    def test_flow_structure(self):
        """Each flow should have from, to, name, and type."""
        for flow in self.result["flows"]:
            assert "from" in flow, f"Flow missing 'from': {flow}"
            assert "to" in flow, f"Flow missing 'to': {flow}"
            assert "name" in flow, f"Flow missing 'name': {flow}"
            assert "type" in flow, f"Flow missing 'type': {flow}"

    def test_trigger_structure(self):
        """Each trigger should have from, to, and type."""
        for trigger in self.result["triggers"]:
            assert "from" in trigger, f"Trigger missing 'from': {trigger}"
            assert "to" in trigger, f"Trigger missing 'to': {trigger}"
            assert "type" in trigger, f"Trigger missing 'type': {trigger}"

    def test_component_ids_are_unique(self):
        """All component IDs should be unique."""
        ids = [c["id"] for c in self.result["components"]]
        assert len(ids) == len(set(ids)), (
            f"Duplicate component IDs found: "
            f"{[x for x in ids if ids.count(x) > 1]}"
        )


# ---------------------------------------------------------------------------
# 5. Java detection
# ---------------------------------------------------------------------------

class TestJavaDetection:
    """demo_java_usage should trigger Java requirement."""

    def test_java_enabled(self):
        result = _convert_cached(_JAVA_USAGE)
        assert result["java_config"]["enabled"] is True, (
            "demo_java_usage should have java_config.enabled = True"
        )

    def test_tfilelist_java_enabled(self):
        """demo_tFileList contains a tJava component, so Java is required."""
        result = _convert_cached(_TFILELIST)
        assert result["java_config"]["enabled"] is True, (
            "demo_tFileList contains tJava_1 — java_config.enabled should be True"
        )

    def test_non_java_jobs_disabled(self):
        """tFlowToIterate job should NOT require Java."""
        result = _convert_cached(_TFLOWTOITERATE)
        assert result["java_config"]["enabled"] is False, (
            f"{_TFLOWTOITERATE.name} should have java_config.enabled = False"
        )


# ---------------------------------------------------------------------------
# 6. Registry completeness check
# ---------------------------------------------------------------------------

class TestRegistryCompleteness:
    """The converter registry must have at least 85 registered type names."""

    def test_minimum_registered_types(self):
        registered = REGISTRY.list_types()
        assert len(registered) >= 85, (
            f"Expected >= 85 registered types, got {len(registered)}: {registered}"
        )

    def test_critical_types_registered(self):
        """Spot-check that high-priority types are registered."""
        critical_types = [
            "tMap",
            "tLogRow",
            "tFileInputDelimited",
            "tFileOutputDelimited",
            "tFilterRow",
            "tAggregateRow",
            "tSortRow",
            "tUniqRow",
            "tJoin",
            "tJavaRow",
            "tJava",
            "tFlowToIterate",
            "tFileList",
            "tRunJob",
            "tPrejob",
            "tPostjob",
            "tOracleInput",
            "tOracleOutput",
            "tOracleConnection",
            "tFixedFlowInput",
        ]
        registered = set(REGISTRY.list_types())
        missing = [t for t in critical_types if t not in registered]
        assert not missing, f"Critical types not registered: {missing}"


# ---------------------------------------------------------------------------
# 7. Backwards compatibility — structural comparison with old converter
# ---------------------------------------------------------------------------

class TestBackwardsCompatibility:
    """New converter output should be structurally comparable to old converter."""

    @pytest.fixture(autouse=True)
    def _load(self):
        self.old_converter = ComplexTalendConverter()
        self.new_converter = TalendToV1Converter()

    def test_tfilelist_same_component_count(self):
        """Same number of components from both converters."""
        old = self.old_converter.convert_file(str(_TFILELIST))
        new = self.new_converter.convert_file(str(_TFILELIST))
        assert len(new["components"]) == len(old["components"]), (
            f"Component count mismatch: old={len(old['components'])}, "
            f"new={len(new['components'])}"
        )

    def test_tfilelist_same_component_ids(self):
        """Same component IDs (names) from both converters."""
        old = self.old_converter.convert_file(str(_TFILELIST))
        new = self.new_converter.convert_file(str(_TFILELIST))
        old_ids = sorted(c["id"] for c in old["components"])
        new_ids = sorted(c["id"] for c in new["components"])
        assert new_ids == old_ids, (
            f"Component ID mismatch:\n"
            f"  old only: {set(old_ids) - set(new_ids)}\n"
            f"  new only: {set(new_ids) - set(old_ids)}"
        )

    def test_tfilelist_same_flow_count(self):
        """Same number of flows from both converters."""
        old = self.old_converter.convert_file(str(_TFILELIST))
        new = self.new_converter.convert_file(str(_TFILELIST))
        assert len(new["flows"]) == len(old["flows"]), (
            f"Flow count mismatch: old={len(old['flows'])}, "
            f"new={len(new['flows'])}"
        )

    def test_complex_tmap_new_is_superset_of_old(self):
        """Complex tMap job: new converter should include all old component IDs.

        The new converter may include extra components (e.g. tMap) that the
        old converter skipped due to parsing limitations.  This is an
        intentional improvement, so we only require the new output to be a
        superset of the old output.
        """
        old = self.old_converter.convert_file(str(_COMPLEX_TMAP))
        new = self.new_converter.convert_file(str(_COMPLEX_TMAP))
        old_ids = set(c["id"] for c in old["components"])
        new_ids = set(c["id"] for c in new["components"])
        missing = old_ids - new_ids
        assert not missing, (
            f"New converter is missing component IDs that old converter had: {missing}"
        )

    def test_complex_tmap_same_flow_count(self):
        """Complex tMap job: same number of flows from both converters."""
        old = self.old_converter.convert_file(str(_COMPLEX_TMAP))
        new = self.new_converter.convert_file(str(_COMPLEX_TMAP))
        assert len(new["flows"]) == len(old["flows"]), (
            f"Flow count mismatch on complex tMap: "
            f"old={len(old['flows'])}, new={len(new['flows'])}"
        )

    def test_all_jobs_preserve_job_name(self):
        """Both converters should produce the same job_name for every file."""
        for path in _ITEM_FILES:
            old = self.old_converter.convert_file(str(path))
            new = self.new_converter.convert_file(str(path))
            assert new["job_name"] == old["job_name"], (
                f"Job name mismatch for {path.name}: "
                f"old={old['job_name']!r}, new={new['job_name']!r}"
            )
