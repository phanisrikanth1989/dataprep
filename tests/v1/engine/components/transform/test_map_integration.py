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

    def test_real_config_passes_validation(self):
        """Real converter output passes _validate_config without error."""
        config = _load_tmap_config()
        gm = GlobalMap()
        comp = Map(component_id="tMap_2", config=config, global_map=gm)

        # execute() calls _validate_config internally -- create input data
        main_df = _make_employee_df()
        lookup_df = _make_country_df()
        input_data = {"row1": main_df, "row2": lookup_df}
        result = comp.execute(input_data)
        assert result is not None

    def test_output_names_match_config(self):
        """Engine produces outputs matching converter-specified output names."""
        config = _load_tmap_config()
        gm = GlobalMap()
        comp = Map(component_id="tMap_2", config=config, global_map=gm)

        main_df = _make_employee_df()
        lookup_df = _make_country_df()
        input_data = {"row1": main_df, "row2": lookup_df}
        result = comp.execute(input_data)

        config_output_names = [o["name"] for o in config["outputs"]]
        for name in config_output_names:
            assert name in result, f"Output '{name}' missing from result"


# ------------------------------------------------------------------
# Tests: Data processing with simple column references
# ------------------------------------------------------------------


class TestSimpleColumnProcessing:
    """Verify Map processes simple column references without Java bridge.

    Without Java bridge, only simple table.column expressions are evaluated.
    Complex expressions (concatenation, ternary) produce None columns.
    """

    def test_simple_column_refs_resolved(self):
        """Simple table.column expressions produce non-null data."""
        config = _load_tmap_config()
        gm = GlobalMap()
        comp = Map(component_id="tMap_2", config=config, global_map=gm)

        main_df = _make_employee_df()
        lookup_df = _make_country_df()
        input_data = {"row1": main_df, "row2": lookup_df}
        result = comp.execute(input_data)

        # out2 has only simple refs: row1.id, row1.first_name, etc.
        assert "out2" in result
        out2 = result["out2"]
        assert isinstance(out2, pd.DataFrame)
        assert len(out2) > 0, "out2 should have rows"

        # Simple column refs should produce non-null data
        assert "id" in out2.columns
        assert "first_name" in out2.columns
        assert "last_name" in out2.columns
        assert "country_code" in out2.columns

    def test_lookup_join_produces_data(self):
        """Equality join on country_code produces merged rows."""
        config = _load_tmap_config()
        gm = GlobalMap()
        comp = Map(component_id="tMap_2", config=config, global_map=gm)

        main_df = _make_employee_df()
        lookup_df = _make_country_df()
        input_data = {"row1": main_df, "row2": lookup_df}
        result = comp.execute(input_data)

        # out has simple refs (department, salary) + lookup refs (country, region)
        assert "out" in result
        out = result["out"]
        assert isinstance(out, pd.DataFrame)
        assert len(out) > 0, "out should have rows after join"

        # Simple column refs from main input
        assert "department" in out.columns
        assert "salary" in out.columns

    def test_stats_updated(self):
        """GlobalMap stats updated after execution."""
        config = _load_tmap_config()
        gm = GlobalMap()
        comp = Map(component_id="tMap_2", config=config, global_map=gm)

        main_df = _make_employee_df()
        lookup_df = _make_country_df()
        input_data = {"row1": main_df, "row2": lookup_df}
        comp.execute(input_data)

        # Stats should be updated
        nb_line = gm.get_component_stat("tMap_2", "NB_LINE")
        assert nb_line is not None and nb_line > 0, (
            "NB_LINE should be positive after processing"
        )


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
    # In a git worktree, build artifacts live in the main repo only.
    # git-common-dir returns the shared .git dir; its parent is the main repo root.
    try:
        common_dir = subprocess.check_output(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=str(Path(__file__).resolve().parent),
            text=True,
        ).strip()
        main_repo = Path(common_dir).resolve().parent
        main_jar = main_repo / _JAR_REL
        if main_jar.exists():
            return main_jar
    except Exception:
        pass
    # Fallback: try relative to test file (works in main repo)
    return Path(__file__).resolve().parents[4] / _JAR_REL


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
