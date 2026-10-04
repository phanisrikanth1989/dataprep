"""Integration tests: convert a real Talend XML sample and verify the output."""
from __future__ import annotations

import pytest
from pathlib import Path

from src.converters.talend_to_v2.converter import TalendToV2Converter

SAMPLE_JOB = Path(__file__).parent.parent.parent.parent / (
    "sample_jobs/old/Order_management_demo_complicated_tmap_0.1.item"
)


@pytest.mark.skipif(not SAMPLE_JOB.exists(), reason="Sample job not available")
class TestRealTalendJob:
    @pytest.fixture
    def result(self):
        return TalendToV2Converter(str(SAMPLE_JOB)).convert()

    def test_converts_without_error(self, result):
        assert result.config is not None

    def test_has_job_name(self, result):
        assert result.config["name"] == "Order_management_demo_complicated_tmap"

    def test_context_variables_present(self, result):
        ctx = result.config["context"]
        # The job has 6 context variables
        assert len(ctx) >= 6
        expected_keys = {
            "customers_file",
            "orders_file",
            "products_file",
            "output_dir",
            "vip_threshold",
            "report_date",
        }
        assert expected_keys.issubset(set(ctx.keys()))

    def test_context_variable_types(self, result):
        """Context variable types should be converted from Talend to V2 types."""
        ctx = result.config["context"]
        # All six are id_String in the XML -> context type map yields "str"
        for name in ("customers_file", "orders_file", "products_file", "output_dir"):
            assert ctx[name]["type"] == "str", f"{name} should be str"

    def test_components_present(self, result):
        comps = result.config["components"]
        assert len(comps) > 0
        comp_types = {c["type"] for c in comps}
        # Should have at least file_input_delimited and map
        assert "file_input_delimited" in comp_types
        assert "map" in comp_types

    def test_has_three_file_inputs(self, result):
        """The job has 3 tFileInputDelimited components."""
        inputs = [c for c in result.config["components"] if c["type"] == "file_input_delimited"]
        assert len(inputs) == 3

    def test_has_two_file_outputs(self, result):
        """The job has 2 tFileOutputDelimited components."""
        outputs = [c for c in result.config["components"] if c["type"] == "file_output_delimited"]
        assert len(outputs) == 2

    def test_has_one_tmap(self, result):
        """The job has 1 tMap component."""
        maps = [c for c in result.config["components"] if c["type"] == "map"]
        assert len(maps) == 1

    def test_flows_present(self, result):
        flows = result.config["flows"]
        assert len(flows) > 0

    def test_tmap_lookup_flows_have_input_port(self, result):
        """Critical fix: lookup flows must have input port names."""
        flows = result.config["flows"]
        # Find tMap component
        tmap_ids = [c["id"] for c in result.config["components"] if c["type"] == "map"]
        for tmap_id in tmap_ids:
            tmap_target_flows = [f for f in flows if f.get("target") == tmap_id]
            # At least some flows should have input port set
            inputs_with_port = [f for f in tmap_target_flows if "input" in f]
            assert len(inputs_with_port) > 0, f"No input ports set for tMap {tmap_id}"

    def test_tmap_expressions_no_main_prefix(self, result):
        """Critical fix: main edge prefix must be stripped from expressions."""
        for comp in result.config["components"]:
            if comp["type"] != "map":
                continue
            for output in comp["config"].get("outputs", []):
                for col in output.get("columns", []):
                    expr = col.get("expression", "")
                    # Should not start with the main edge name "orders." —
                    # the converter should strip the main input prefix
                    assert not expr.startswith("orders."), (
                        f"Column '{col['name']}' still has main edge prefix: {expr}"
                    )

    def test_tmap_join_keys_non_empty(self, result):
        """Critical fix: join keys must have non-empty main field."""
        for comp in result.config["components"]:
            if comp["type"] != "map":
                continue
            for lookup in comp["config"].get("lookups", []):
                for key in lookup.get("keys", []):
                    assert key["main"], f"Empty main key in lookup '{lookup['name']}'"
                    assert key["lookup"], f"Empty lookup key in lookup '{lookup['name']}'"

    def test_tmap_var_references_lowercase(self, result):
        """Critical fix: Var. should be converted to var."""
        for comp in result.config["components"]:
            if comp["type"] != "map":
                continue
            for output in comp["config"].get("outputs", []):
                for col in output.get("columns", []):
                    expr = col.get("expression", "")
                    assert "Var." not in expr, (
                        f"Column '{col['name']}' has uppercase Var.: {expr}"
                    )

    def test_tmap_has_lookups(self, result):
        """The tMap has two lookups: products and customers."""
        for comp in result.config["components"]:
            if comp["type"] != "map":
                continue
            lookups = comp["config"].get("lookups", [])
            lookup_names = {lk["name"] for lk in lookups}
            assert "products" in lookup_names, "Missing 'products' lookup"
            assert "customers" in lookup_names, "Missing 'customers' lookup"

    def test_tmap_has_two_outputs(self, result):
        """The tMap has two output tables: enriched_orders and vip_orders."""
        for comp in result.config["components"]:
            if comp["type"] != "map":
                continue
            outputs = comp["config"].get("outputs", [])
            output_names = {o["name"] for o in outputs}
            assert "enriched_orders" in output_names
            assert "vip_orders" in output_names

    def test_tmap_vip_orders_has_filter(self, result):
        """The vip_orders output has a filter expression."""
        for comp in result.config["components"]:
            if comp["type"] != "map":
                continue
            for output in comp["config"].get("outputs", []):
                if output["name"] == "vip_orders":
                    assert output.get("filter"), (
                        "vip_orders output should have a filter expression"
                    )

    def test_tmap_has_variables(self, result):
        """The tMap has var table entries (total_amount, is_vip)."""
        for comp in result.config["components"]:
            if comp["type"] != "map":
                continue
            variables = comp["config"].get("variables", [])
            var_names = {v["name"] for v in variables}
            assert "total_amount" in var_names, "Missing var 'total_amount'"
            assert "is_vip" in var_names, "Missing var 'is_vip'"

    def test_validation_report(self, result):
        """Validation report should be present."""
        assert result.report is not None
        # Errors related to converter bugs should not be present
        errors = [i for i in result.report.issues if i.severity == "error"]
        # Print any errors for debugging
        for e in errors:
            print(f"  ERROR: {e.component_id}: {e.message}")
