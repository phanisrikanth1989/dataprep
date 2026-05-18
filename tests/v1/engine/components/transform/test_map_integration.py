"""Integration tests for Map component with real converter JSON output.

Verifies the engine component processes actual converter output correctly,
catching config key mismatches between converter and engine layers.

Tests marked @pytest.mark.java require a running JVM with the bridge JAR built.
"""
import copy
import json
from pathlib import Path

import numpy as np
import pytest
import pandas as pd

from src.v1.engine.components.transform.map import Map
from src.v1.engine.global_map import GlobalMap
from src.v1.engine.context_manager import ContextManager
from src.v1.engine.exceptions import ConfigurationError


# ------------------------------------------------------------------
# Paths to converter JSON configs
# ------------------------------------------------------------------

_CONVERTED_JSONS_DIR = Path(__file__).resolve().parents[4] / (
    "talend_xml_samples" / Path("converted_jsons")
)

_SAMPLE_JSON = _CONVERTED_JSONS_DIR / "Job_tMap_0.1.json"
_SAMPLE_EXISTS = _SAMPLE_JSON.exists()

pytestmark = pytest.mark.skipif(
    not _SAMPLE_EXISTS, reason="Sample JSON not found"
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _load_job_config():
    """Load the tMap sample job config."""
    with open(_SAMPLE_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_tmap_config():
    """Load tMap component config from real converter JSON."""
    job = _load_job_config()
    for comp in job["components"]:
        if comp.get("type") == "Map":
            return comp["config"]
    raise ValueError("No Map component found in sample JSON")


def _make_employee_df():
    """Create synthetic employee data matching the sample job schema."""
    return pd.DataFrame({
        "id": [1, 2, 3],
        "first_name": ["Alice", "Bob", "Charlie"],
        "last_name": ["Smith", "Jones", "Brown"],
        "department": ["Eng", "Sales", "Eng"],
        "salary": [80000, 50000, 90000],
        "country_code": ["US", "UK", "US"],
    })


def _make_country_df():
    """Create synthetic country lookup data matching the sample job schema."""
    return pd.DataFrame({
        "country_code": ["US", "UK", "DE"],
        "country_name": ["United States", "United Kingdom", "Germany"],
        "region": ["NA", "EU", "EU"],
    })


# ------------------------------------------------------------------
# Tests: Config structure compatibility
# ------------------------------------------------------------------


class TestConverterOutputCompatibility:
    """Verify engine accepts real converter output without ConfigurationError."""

    def test_sample_json_exists(self):
        """Converter sample JSON file exists at expected path."""
        assert _SAMPLE_JSON.exists(), (
            f"Sample JSON not found at {_SAMPLE_JSON}"
        )

    def test_config_has_expected_structure(self):
        """Converter output has all keys the engine expects."""
        config = _load_tmap_config()
        # Top-level keys
        assert "inputs" in config
        assert "outputs" in config
        assert "variables" in config
        assert "die_on_error" in config

        # Main input structure
        main = config["inputs"]["main"]
        assert "name" in main
        assert "matching_mode" in main

        # Lookups structure
        assert "lookups" in config["inputs"]
        for lookup in config["inputs"]["lookups"]:
            assert "name" in lookup
            assert "join_keys" in lookup
            assert "join_mode" in lookup

        # Outputs structure
        for output in config["outputs"]:
            assert "name" in output
            assert "columns" in output
            assert "is_reject" in output
            assert "inner_join_reject" in output

    def test_enable_auto_convert_type_present(self):
        """MAP-06: enable_auto_convert_type key exists in converter output."""
        config = _load_tmap_config()
        assert "enable_auto_convert_type" in config

    def test_output_column_expressions_have_java_marker(self):
        """Output column expressions are prefixed with {{java}} marker."""
        config = _load_tmap_config()
        for output in config["outputs"]:
            for col in output["columns"]:
                expr = col.get("expression", "")
                if expr:
                    assert expr.startswith("{{java}}"), (
                        f"Output column {col['name']} expression missing "
                        f"{{{{java}}}} marker: {expr}"
                    )

    def test_join_key_expressions_have_java_marker(self):
        """Join key expressions are prefixed with {{java}} marker."""
        config = _load_tmap_config()
        for lookup in config["inputs"]["lookups"]:
            for jk in lookup["join_keys"]:
                expr = jk.get("expression", "")
                if expr:
                    assert expr.startswith("{{java}}"), (
                        f"Join key expression missing "
                        f"{{{{java}}}} marker: {expr}"
                    )


# ------------------------------------------------------------------
# Tests: Engine component instantiation
# ------------------------------------------------------------------


class TestComponentInstantiation:
    """Verify Map engine component instantiates with real converter config."""

    def test_real_config_creates_component(self):
        """Map component can be instantiated with real converter output."""
        config = _load_tmap_config()
        gm = GlobalMap()
        comp = Map(component_id="tMap_2", config=config, global_map=gm)
        assert comp.id == "tMap_2"
        assert comp._original_config is not config  # deepcopy

    def test_real_config_requires_bridge_when_markers_present(self):
        """D-01: Real converter output with {{java}} markers requires Java bridge.

        Real converter output uses {{java}} markers on all expressions.
        Under D-01, attempting to execute without a bridge raises ConfigurationError
        (hard-fail rather than the old silent-empty-cells path).
        """
        config = _load_tmap_config()
        gm = GlobalMap()
        comp = Map(component_id="tMap_2", config=config, global_map=gm)

        main_df = _make_employee_df()
        lookup_df = _make_country_df()
        input_data = {"row1": main_df, "row2": lookup_df}
        with pytest.raises(ConfigurationError, match="Java bridge"):
            comp.execute(input_data)

    def test_output_names_in_config(self):
        """Converter output names are declared in config (structure only, no execute needed)."""
        config = _load_tmap_config()
        config_output_names = [o["name"] for o in config["outputs"]]
        assert len(config_output_names) > 0, "Config should have at least one output"
        for name in config_output_names:
            assert isinstance(name, str) and name, f"Output name should be non-empty string"


# ------------------------------------------------------------------
# Tests: Data processing with simple column references
# ------------------------------------------------------------------


class TestSimpleColumnProcessing:
    """Verify D-01: real converter output (with {{java}} markers) requires Java bridge.

    Under D-01, all {{java}}-marked expressions route to the compiled bridge path.
    Executing without a bridge raises ConfigurationError (hard-fail). Tests in this
    class verify the hard-fail behavior; bridge-dependent tests are in test_map_bridge.py.
    """

    def test_execute_without_bridge_raises_config_error(self):
        """D-01: real converter output with {{java}} markers + no bridge -> ConfigurationError."""
        config = _load_tmap_config()
        gm = GlobalMap()
        comp = Map(component_id="tMap_2", config=config, global_map=gm)

        main_df = _make_employee_df()
        lookup_df = _make_country_df()
        input_data = {"row1": main_df, "row2": lookup_df}
        with pytest.raises(ConfigurationError, match="Java bridge"):
            comp.execute(input_data)

    def test_config_structure_has_expected_outputs(self):
        """Real config declares expected output column structure."""
        config = _load_tmap_config()
        assert "outputs" in config
        assert len(config["outputs"]) > 0
        # All outputs have required fields
        for output in config["outputs"]:
            assert "name" in output
            assert "columns" in output

    def test_hard_fail_does_not_produce_empty_results(self):
        """D-01: hard-fail ConfigurationError is preferred over silent empty results.

        The OLD behavior was to silently emit empty cells when bridge was unavailable.
        The NEW behavior is to raise ConfigurationError immediately (D-01).
        """
        config = _load_tmap_config()
        gm = GlobalMap()
        comp = Map(component_id="tMap_2", config=config, global_map=gm)

        main_df = _make_employee_df()
        lookup_df = _make_country_df()
        input_data = {"row1": main_df, "row2": lookup_df}
        # Must raise, NOT silently return empty DataFrames
        with pytest.raises(ConfigurationError):
            comp.execute(input_data)


# ------------------------------------------------------------------
# Tests: RELOAD_AT_EACH_ROW with real Java bridge
# ------------------------------------------------------------------

def _find_jar_path() -> Path:
    """Find Java bridge JAR, checking worktree and main repo paths.

    Build artifacts (target/) are gitignored so they only exist in the
    main repo. In worktrees, we resolve via git-common-dir.
    """
    import subprocess

    _JAR_REL = Path("src/v1/java_bridge/java/target/java-bridge-with-dependencies.jar")
    test_dir = Path(__file__).resolve().parent
    # In a git worktree, build artifacts live in the main repo only.
    # git-common-dir returns the shared .git dir (relative to where git was
    # invoked); its parent is the main repo root.
    try:
        common_dir = subprocess.check_output(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=str(test_dir),
            text=True,
        ).strip()
        # The returned path is relative to the git invocation cwd (test_dir),
        # not Python's cwd. Resolve manually against test_dir before
        # asking pathlib for the absolute form.
        common_dir_path = Path(common_dir)
        if not common_dir_path.is_absolute():
            common_dir_path = test_dir / common_dir_path
        main_repo = common_dir_path.resolve().parent
        main_jar = main_repo / _JAR_REL
        if main_jar.exists():
            return main_jar
    except Exception:
        pass
    # Fallback: relative to project root from this file's location.
    # File: tests/v1/engine/components/transform/test_map_integration.py
    # parents: [0]=transform, [1]=components, [2]=engine, [3]=v1,
    #          [4]=tests, [5]=project_root.
    return Path(__file__).resolve().parents[5] / _JAR_REL


_JAR_PATH = _find_jar_path()


@pytest.fixture(scope="module")
def java_bridge():
    """Start a real Java bridge for the test module.

    Skips if the JAR is not built. In worktrees, creates a symlink to the
    main repo's JAR since build artifacts are gitignored.
    """
    if not _JAR_PATH.exists():
        pytest.skip(
            f"Java bridge JAR not found at {_JAR_PATH}. "
            f"Build with: cd src/v1/java_bridge/java && mvn clean package -q"
        )

    # In a worktree, the JavaBridge class resolves its JAR relative to its
    # own __file__ which is in the worktree. Since build artifacts (target/)
    # are gitignored, they won't exist. Create a symlink so the bridge can
    # find the JAR at the expected location.
    from src.v1.java_bridge import bridge as bridge_mod
    bridge_base = Path(bridge_mod.__file__).resolve().parent
    worktree_target_dir = bridge_base / "java" / "target"
    worktree_jar = worktree_target_dir / "java-bridge-with-dependencies.jar"
    symlink_created = False
    if not worktree_jar.exists() and _JAR_PATH.exists():
        worktree_target_dir.mkdir(parents=True, exist_ok=True)
        worktree_jar.symlink_to(_JAR_PATH)
        symlink_created = True

    from src.v1.java_bridge.bridge import JavaBridge
    b = JavaBridge()
    try:
        b.start()
    except Exception as exc:
        if symlink_created:
            worktree_jar.unlink(missing_ok=True)
        pytest.skip(f"Java bridge failed to start: {exc}")
    yield b
    b.stop()
    if symlink_created:
        worktree_jar.unlink(missing_ok=True)


@pytest.mark.java
@pytest.mark.integration
class TestReloadAtEachRowIntegration:
    """RELOAD_AT_EACH_ROW per-row filter through real JVM bridge.

    Exercises the full path: _substitute_row_refs replaces main row values,
    _apply_filter sends expression to Java bridge for evaluation, per-row
    filtering produces correct matched/unmatched rows.
    """

    @staticmethod
    def _make_reload_config():
        """Build a RELOAD_AT_EACH_ROW config with per-row filter."""
        return {
            "component_type": "Map",
            "inputs": {
                "main": {
                    "name": "row1",
                    "filter": "",
                    "activate_filter": False,
                    "matching_mode": "UNIQUE_MATCH",
                    "lookup_mode": "LOAD_ONCE",
                },
                "lookups": [{
                    "name": "row2",
                    "matching_mode": "UNIQUE_MATCH",
                    "lookup_mode": "RELOAD_AT_EACH_ROW",
                    "activate_filter": True,
                    # .equals() forces Java bridge evaluation (not simple column ref)
                    "filter": '{{java}}row1.region.equals(row2.region)',
                    "join_keys": [{
                        "lookup_column": "key",
                        "expression": "{{java}}row1.key",
                        "type": "str",
                        "nullable": False,
                        "operator": "=",
                    }],
                    "join_mode": "LEFT_OUTER_JOIN",
                }],
            },
            "variables": [],
            "outputs": [{
                "name": "out1",
                "is_reject": False,
                "inner_join_reject": False,
                "filter": "",
                "activate_filter": False,
                "columns": [
                    {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
                    {"name": "region", "expression": "{{java}}row1.region", "type": "str", "nullable": True},
                    {"name": "label", "expression": "{{java}}row2.label", "type": "str", "nullable": True},
                ],
                "catch_output_reject": False,
            }],
            "die_on_error": True,
        }

    def test_reload_per_row_filter_java_bridge(self, java_bridge):
        """Per-row filter with .equals() evaluated through real JVM bridge.

        Main rows: US/EU/US regions with keys A/B/C.
        Lookup rows: A=US, B=EU, C=EU.
        Filter: row1.region.equals(row2.region).

        After _substitute_row_refs, each main row's region is substituted:
        - Row 1 (US, key=A): filter becomes "US".equals(row2.region)
          -> lookup A (region=US) passes, matches on key -> Alpha
        - Row 2 (EU, key=B): filter becomes "EU".equals(row2.region)
          -> lookup B (region=EU) passes, matches on key -> Beta
        - Row 3 (US, key=C): filter becomes "US".equals(row2.region)
          -> lookup C (region=EU) fails filter -> LEFT_OUTER NaN
        """
        config = self._make_reload_config()
        main_df = pd.DataFrame([
            {"id": 1, "key": "A", "region": "US"},
            {"id": 2, "key": "B", "region": "EU"},
            {"id": 3, "key": "C", "region": "US"},
        ])
        lookup_df = pd.DataFrame([
            {"key": "A", "label": "Alpha", "region": "US"},
            {"key": "B", "label": "Beta", "region": "EU"},
            {"key": "C", "label": "Gamma", "region": "EU"},
        ])

        gm = GlobalMap()
        comp = Map(component_id="tMap_reload", config=config, global_map=gm)
        comp.java_bridge = java_bridge

        result = comp.execute({"row1": main_df, "row2": lookup_df})
        out = result["out1"]

        assert len(out) == 3, f"Expected 3 rows, got {len(out)}"

        # Row 1 (US, key=A): lookup A is US -> matches
        r1 = out[out["id"] == 1]
        assert len(r1) == 1
        assert r1.iloc[0]["label"] == "Alpha"

        # Row 2 (EU, key=B): lookup B is EU -> matches
        r2 = out[out["id"] == 2]
        assert len(r2) == 1
        assert r2.iloc[0]["label"] == "Beta"

        # Row 3 (US, key=C): lookup C is EU, filter rejects -> NaN
        r3 = out[out["id"] == 3]
        assert len(r3) == 1
        assert pd.isna(r3.iloc[0]["label"]), (
            f"Expected NaN for unmatched row, got {r3.iloc[0]['label']}"
        )
