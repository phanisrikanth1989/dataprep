"""Integration tests for Aggregate component in end-to-end pipelines."""
import polars as pl

from src.v2.engine import PyETLEngine


class TestAggregatePipeline:
    """End-to-end pipeline tests for Aggregate component."""

    def test_aggregate_list_pipeline(self, tmp_path):
        """Source -> Aggregate(list function) -> Output pipeline."""
        input_file = tmp_path / "input.csv"
        input_file.write_text(
            "customer,product\nAlice,Widget\nAlice,Gadget\nBob,Widget\nAlice,Gizmo\n"
        )
        output_file = tmp_path / "output.csv"

        config = {
            "name": "agg_list_test",
            "components": [
                {
                    "id": "source",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(input_file),
                        "schema": [
                            {"name": "customer", "type": "string"},
                            {"name": "product", "type": "string"},
                        ],
                    },
                },
                {
                    "id": "agg",
                    "type": "aggregate",
                    "config": {
                        "group_by": ["customer"],
                        "aggregations": [
                            {"name": "products", "function": "list", "column": "product"},
                            {"name": "order_count", "function": "count", "column": "*"},
                        ],
                        "maintain_order": True,
                    },
                },
                {
                    "id": "output",
                    "type": "file_output_delimited",
                    "config": {"path": str(output_file)},
                },
            ],
            "flows": [
                {"source": "source", "target": "agg"},
                {"source": "agg", "target": "output"},
            ],
        }

        engine = PyETLEngine(config)
        result = engine.execute()

        assert result["status"] == "success"
        output_df = pl.read_csv(output_file)
        alice_row = output_df.filter(pl.col("customer") == "Alice")
        bob_row = output_df.filter(pl.col("customer") == "Bob")
        assert alice_row["order_count"][0] == 3
        assert bob_row["order_count"][0] == 1
        alice_products = alice_row["products"][0]
        assert "Widget" in alice_products
        assert "Gadget" in alice_products
        assert "Gizmo" in alice_products

    def test_aggregate_ignore_nulls_pipeline(self, tmp_path):
        """Source with nulls -> Aggregate -> verify null handling."""
        input_file = tmp_path / "input.csv"
        input_file.write_text(
            "dept,salary\nEng,100\nEng,\nSales,200\nSales,300\n"
        )
        output_file = tmp_path / "output.csv"

        config = {
            "name": "agg_nulls_test",
            "components": [
                {
                    "id": "source",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(input_file),
                        "schema": [
                            {"name": "dept", "type": "string"},
                            {"name": "salary", "type": "integer"},
                        ],
                    },
                },
                {
                    "id": "agg",
                    "type": "aggregate",
                    "config": {
                        "group_by": ["dept"],
                        "aggregations": [
                            {"name": "total", "function": "sum", "column": "salary"},
                            {"name": "cnt_nonnull", "function": "count", "column": "salary", "ignore_nulls": True},
                            {"name": "cnt_all", "function": "count", "column": "salary", "ignore_nulls": False},
                        ],
                        "maintain_order": True,
                    },
                },
                {
                    "id": "output",
                    "type": "file_output_delimited",
                    "config": {"path": str(output_file)},
                },
            ],
            "flows": [
                {"source": "source", "target": "agg"},
                {"source": "agg", "target": "output"},
            ],
        }

        engine = PyETLEngine(config)
        result = engine.execute()

        assert result["status"] == "success"
        output_df = pl.read_csv(output_file)
        eng_row = output_df.filter(pl.col("dept") == "Eng")
        sales_row = output_df.filter(pl.col("dept") == "Sales")
        assert eng_row["total"][0] == 100
        assert eng_row["cnt_nonnull"][0] == 1
        assert eng_row["cnt_all"][0] == 2
        assert sales_row["total"][0] == 500
        assert sales_row["cnt_nonnull"][0] == 2
        assert sales_row["cnt_all"][0] == 2

    def test_aggregate_rename_pipeline(self, tmp_path):
        """Source -> Aggregate(group_by rename) -> Output pipeline."""
        input_file = tmp_path / "input.csv"
        input_file.write_text(
            "customer_id,amount\nC1,100\nC1,200\nC2,300\n"
        )
        output_file = tmp_path / "output.csv"

        config = {
            "name": "agg_rename_test",
            "components": [
                {
                    "id": "source",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(input_file),
                        "schema": [
                            {"name": "customer_id", "type": "string"},
                            {"name": "amount", "type": "integer"},
                        ],
                    },
                },
                {
                    "id": "agg",
                    "type": "aggregate",
                    "config": {
                        "group_by": [{"input": "customer_id", "output": "cust_id"}],
                        "aggregations": [
                            {"name": "total", "function": "sum", "column": "amount"},
                        ],
                        "maintain_order": True,
                    },
                },
                {
                    "id": "output",
                    "type": "file_output_delimited",
                    "config": {"path": str(output_file)},
                },
            ],
            "flows": [
                {"source": "source", "target": "agg"},
                {"source": "agg", "target": "output"},
            ],
        }

        engine = PyETLEngine(config)
        result = engine.execute()

        assert result["status"] == "success"
        output_df = pl.read_csv(output_file)
        assert "cust_id" in output_df.columns
        assert "customer_id" not in output_df.columns
        assert output_df.sort("cust_id")["cust_id"].to_list() == ["C1", "C2"]
        assert output_df.sort("cust_id")["total"].to_list() == [300, 300]
