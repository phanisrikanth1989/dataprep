"""
Integration tests for routines working end-to-end through the engine pipeline.

Verifies that routine_registry is properly wired from engine -> components -> compile_expression.
Uses MathUtils (vectorized Tier 1) routines through Map and Filter components.
"""
import csv
import tempfile
from pathlib import Path

import polars as pl
import pytest

from src.v2.engine import PyETLEngine


@pytest.fixture
def data_dir(tmp_path):
    """Create test CSV data."""
    # Sales data with revenue and cost columns
    rows = [
        ("P001", 1000.0, 600.0, 5000.0),
        ("P002", 250.0, 200.0, 5000.0),
        ("P003", 0.0, 50.0, 5000.0),      # zero revenue -> null margin
        ("P004", 800.0, 300.0, 5000.0),
        ("P005", 150.0, 120.0, 5000.0),
    ]
    input_file = tmp_path / "sales.csv"
    with open(input_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["product_id", "revenue", "cost", "target"])
        writer.writerows(rows)

    return tmp_path


class TestRoutineThroughMapComponent:
    """Test routines called from Map component expressions via full engine pipeline."""

    def test_vectorized_percentage_in_map(self, data_dir):
        """MathUtils.percentage() should work in a Map column expression."""
        output_file = data_dir / "output.csv"

        config = {
            "name": "routine_percentage_test",
            "engine": "v2",
            "components": [
                {
                    "id": "read_sales",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(data_dir / "sales.csv"),
                        "schema": [
                            {"name": "product_id", "type": "string"},
                            {"name": "revenue", "type": "float"},
                            {"name": "cost", "type": "float"},
                            {"name": "target", "type": "float"},
                        ],
                    },
                },
                {
                    "id": "calc_pct",
                    "type": "map",
                    "config": {
                        "outputs": [{
                            "name": "main",
                            "columns": [
                                {"name": "product_id", "expression": "product_id"},
                                {"name": "revenue", "expression": "revenue"},
                                {"name": "pct_of_target", "expression": "MathUtils.percentage(revenue, target)"},
                            ],
                        }],
                    },
                },
                {
                    "id": "write_out",
                    "type": "file_output_delimited",
                    "config": {"path": str(output_file)},
                },
            ],
            "flows": [
                {"source": "read_sales", "target": "calc_pct"},
                {"source": "calc_pct", "target": "write_out"},
            ],
        }

        result = PyETLEngine(config).execute()
        assert result["status"] == "success"

        df = pl.read_csv(output_file)
        assert len(df) == 5

        # P001: 1000/5000 * 100 = 20.0
        assert df.filter(pl.col("product_id") == "P001")["pct_of_target"][0] == 20.0
        # P002: 250/5000 * 100 = 5.0
        assert df.filter(pl.col("product_id") == "P002")["pct_of_target"][0] == 5.0
        # P003: 0/5000 * 100 = 0.0
        assert df.filter(pl.col("product_id") == "P003")["pct_of_target"][0] == 0.0

    def test_vectorized_margin_in_map(self, data_dir):
        """MathUtils.margin() should work in a Map column expression."""
        output_file = data_dir / "output.csv"

        config = {
            "name": "routine_margin_test",
            "engine": "v2",
            "components": [
                {
                    "id": "read_sales",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(data_dir / "sales.csv"),
                        "schema": [
                            {"name": "product_id", "type": "string"},
                            {"name": "revenue", "type": "float"},
                            {"name": "cost", "type": "float"},
                            {"name": "target", "type": "float"},
                        ],
                    },
                },
                {
                    "id": "calc_margin",
                    "type": "map",
                    "config": {
                        "outputs": [{
                            "name": "main",
                            "columns": [
                                {"name": "product_id", "expression": "product_id"},
                                {"name": "revenue", "expression": "revenue"},
                                {"name": "cost", "expression": "cost"},
                                {"name": "profit_margin", "expression": "MathUtils.margin(revenue, cost)"},
                            ],
                        }],
                    },
                },
                {
                    "id": "write_out",
                    "type": "file_output_delimited",
                    "config": {"path": str(output_file)},
                },
            ],
            "flows": [
                {"source": "read_sales", "target": "calc_margin"},
                {"source": "calc_margin", "target": "write_out"},
            ],
        }

        result = PyETLEngine(config).execute()
        assert result["status"] == "success"

        df = pl.read_csv(output_file)

        # P001: (1000-600)/1000 * 100 = 40.0
        assert df.filter(pl.col("product_id") == "P001")["profit_margin"][0] == 40.0
        # P004: (800-300)/800 * 100 = 62.5
        assert df.filter(pl.col("product_id") == "P004")["profit_margin"][0] == 62.5
        # P003: revenue=0 -> null margin
        assert df.filter(pl.col("product_id") == "P003")["profit_margin"][0] is None

    def test_vectorized_clamp_in_map(self, data_dir):
        """MathUtils.clamp() should work in a Map column expression."""
        output_file = data_dir / "output.csv"

        config = {
            "name": "routine_clamp_test",
            "engine": "v2",
            "components": [
                {
                    "id": "read_sales",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(data_dir / "sales.csv"),
                        "schema": [
                            {"name": "product_id", "type": "string"},
                            {"name": "revenue", "type": "float"},
                            {"name": "cost", "type": "float"},
                            {"name": "target", "type": "float"},
                        ],
                    },
                },
                {
                    "id": "clamp_revenue",
                    "type": "map",
                    "config": {
                        "outputs": [{
                            "name": "main",
                            "columns": [
                                {"name": "product_id", "expression": "product_id"},
                                {"name": "clamped", "expression": "MathUtils.clamp(revenue, 200, 900)"},
                            ],
                        }],
                    },
                },
                {
                    "id": "write_out",
                    "type": "file_output_delimited",
                    "config": {"path": str(output_file)},
                },
            ],
            "flows": [
                {"source": "read_sales", "target": "clamp_revenue"},
                {"source": "clamp_revenue", "target": "write_out"},
            ],
        }

        result = PyETLEngine(config).execute()
        assert result["status"] == "success"

        df = pl.read_csv(output_file)

        # P001: 1000 clamped to 900
        assert df.filter(pl.col("product_id") == "P001")["clamped"][0] == 900.0
        # P002: 250 stays 250 (within range)
        assert df.filter(pl.col("product_id") == "P002")["clamped"][0] == 250.0
        # P003: 0 clamped to 200
        assert df.filter(pl.col("product_id") == "P003")["clamped"][0] == 200.0
        # P005: 150 clamped to 200
        assert df.filter(pl.col("product_id") == "P005")["clamped"][0] == 200.0


class TestRoutineThroughFilterComponent:
    """Test routines called from Filter condition expressions via full engine pipeline."""

    def test_routine_in_filter_condition(self, data_dir):
        """MathUtils.margin() in a Filter condition should work."""
        output_file = data_dir / "output.csv"

        config = {
            "name": "routine_filter_test",
            "engine": "v2",
            "components": [
                {
                    "id": "read_sales",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(data_dir / "sales.csv"),
                        "schema": [
                            {"name": "product_id", "type": "string"},
                            {"name": "revenue", "type": "float"},
                            {"name": "cost", "type": "float"},
                            {"name": "target", "type": "float"},
                        ],
                    },
                },
                {
                    "id": "calc_margin",
                    "type": "map",
                    "config": {
                        "outputs": [{
                            "name": "main",
                            "columns": [
                                {"name": "product_id", "expression": "product_id"},
                                {"name": "revenue", "expression": "revenue"},
                                {"name": "cost", "expression": "cost"},
                                {"name": "profit_margin", "expression": "MathUtils.margin(revenue, cost)"},
                            ],
                        }],
                    },
                },
                {
                    "id": "filter_high_margin",
                    "type": "filter",
                    "config": {
                        "condition": "profit_margin > 30",
                    },
                },
                {
                    "id": "write_out",
                    "type": "file_output_delimited",
                    "config": {"path": str(output_file)},
                },
            ],
            "flows": [
                {"source": "read_sales", "target": "calc_margin"},
                {"source": "calc_margin", "target": "filter_high_margin"},
                {"source": "filter_high_margin", "target": "write_out"},
            ],
        }

        result = PyETLEngine(config).execute()
        assert result["status"] == "success"

        df = pl.read_csv(output_file)
        # P001: margin=40%, P004: margin=62.5% -> both pass > 30%
        # P002: margin=20%, P003: null, P005: margin=20% -> filtered out
        assert len(df) == 2
        product_ids = sorted(df["product_id"].to_list())
        assert product_ids == ["P001", "P004"]


class TestRoutineMultiComponentPipeline:
    """Test routines across a multi-component pipeline."""

    def test_multiple_routines_in_pipeline(self, data_dir):
        """Pipeline using multiple routine functions across Map + Filter."""
        output_file = data_dir / "output.csv"

        config = {
            "name": "routine_multi_test",
            "engine": "v2",
            "components": [
                {
                    "id": "read_sales",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(data_dir / "sales.csv"),
                        "schema": [
                            {"name": "product_id", "type": "string"},
                            {"name": "revenue", "type": "float"},
                            {"name": "cost", "type": "float"},
                            {"name": "target", "type": "float"},
                        ],
                    },
                },
                {
                    "id": "enrich",
                    "type": "map",
                    "config": {
                        "outputs": [{
                            "name": "main",
                            "columns": [
                                {"name": "product_id", "expression": "product_id"},
                                {"name": "revenue", "expression": "revenue"},
                                {"name": "cost", "expression": "cost"},
                                {"name": "pct_of_target", "expression": "MathUtils.percentage(revenue, target)"},
                                {"name": "profit_margin", "expression": "MathUtils.margin(revenue, cost)"},
                                {"name": "clamped_cost", "expression": "MathUtils.clamp(cost, 100, 500)"},
                            ],
                        }],
                    },
                },
                {
                    "id": "filter_viable",
                    "type": "filter",
                    "config": {
                        "condition": "pct_of_target >= 5",
                    },
                },
                {
                    "id": "write_out",
                    "type": "file_output_delimited",
                    "config": {"path": str(output_file)},
                },
            ],
            "flows": [
                {"source": "read_sales", "target": "enrich"},
                {"source": "enrich", "target": "filter_viable"},
                {"source": "filter_viable", "target": "write_out"},
            ],
        }

        result = PyETLEngine(config).execute()
        assert result["status"] == "success"

        df = pl.read_csv(output_file)
        # pct_of_target >= 5: P001=20%, P002=5%, P004=16% pass. P003=0%, P005=3% fail.
        assert len(df) == 3
        product_ids = sorted(df["product_id"].to_list())
        assert product_ids == ["P001", "P002", "P004"]

        # Verify all routine columns computed correctly
        p1 = df.filter(pl.col("product_id") == "P001")
        assert p1["pct_of_target"][0] == 20.0
        assert p1["profit_margin"][0] == 40.0
        assert p1["clamped_cost"][0] == 500.0  # 600 clamped to 500
