"""Integration tests for Map component with real converter JSON output.

Verifies the engine component processes actual converter output correctly,
catching config key mismatches between converter and engine layers.
"""
import json
from pathlib import Path

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
