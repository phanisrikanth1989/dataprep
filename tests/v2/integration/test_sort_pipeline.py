"""Integration tests for Sort component in end-to-end pipelines."""
import polars as pl

from src.v2.engine import PyETLEngine


class TestSortPipeline:
    """End-to-end pipeline tests for Sort component."""

    def test_sort_with_nulls_pipeline(self, tmp_path):
        """Source -> Sort (nulls_last) -> Output pipeline."""
        # Create input CSV with null values
        input_file = tmp_path / "input.csv"
        input_file.write_text("name,amount\nAlice,300\nBob,\nCharlie,100\nDiana,200\n")

        output_file = tmp_path / "output.csv"

        config = {
            "name": "sort_nulls_test",
            "components": [
                {
                    "id": "source",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(input_file),
                        "schema": [
                            {"name": "name", "type": "string"},
                            {"name": "amount", "type": "integer"},
                        ],
                    },
                },
                {
                    "id": "sort",
                    "type": "sort_row",
                    "config": {
                        "columns": [{"name": "amount", "order": "asc"}],
                        "nulls_last": True,
                    },
                },
                {
                    "id": "output",
                    "type": "file_output_delimited",
                    "config": {"path": str(output_file)},
                },
            ],
            "flows": [
                {"source": "source", "target": "sort"},
                {"source": "sort", "target": "output"},
            ],
        }

        engine = PyETLEngine(config)
        result = engine.execute()

        assert result["status"] == "success"
        output_df = pl.read_csv(output_file)
        # Nulls should be at the end
        assert output_df["name"].to_list() == ["Charlie", "Diana", "Alice", "Bob"]
        assert output_df["amount"].to_list() == [100, 200, 300, None]

    def test_sort_maintain_order_pipeline(self, tmp_path):
        """Source -> Sort (maintain_order) -> Output pipeline."""
        input_file = tmp_path / "input.csv"
        input_file.write_text(
            "category,id\nB,1\nA,2\nB,3\nA,4\nB,5\n"
        )

        output_file = tmp_path / "output.csv"

        config = {
            "name": "sort_stable_test",
            "components": [
                {
                    "id": "source",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(input_file),
                        "schema": [
                            {"name": "category", "type": "string"},
                            {"name": "id", "type": "integer"},
                        ],
                    },
                },
                {
                    "id": "sort",
                    "type": "sort_row",
                    "config": {
                        "columns": [{"name": "category", "order": "asc"}],
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
                {"source": "source", "target": "sort"},
                {"source": "sort", "target": "output"},
            ],
        }

        engine = PyETLEngine(config)
        result = engine.execute()

        assert result["status"] == "success"
        output_df = pl.read_csv(output_file)
        assert output_df["category"].to_list() == ["A", "A", "B", "B", "B"]
        # Stable sort preserves original order within equal categories
        assert output_df["id"].to_list() == [2, 4, 1, 3, 5]

    def test_sort_multi_column_nulls_mixed_pipeline(self, tmp_path):
        """Multi-column sort with per-column nulls_last in a pipeline."""
        input_file = tmp_path / "input.csv"
        input_file.write_text(
            "dept,salary,name\nSales,50000,Alice\n,60000,Bob\nSales,,Charlie\nHR,45000,Diana\n"
        )

        output_file = tmp_path / "output.csv"

        config = {
            "name": "sort_multi_nulls_test",
            "components": [
                {
                    "id": "source",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(input_file),
                        "schema": [
                            {"name": "dept", "type": "string"},
                            {"name": "salary", "type": "integer"},
                            {"name": "name", "type": "string"},
                        ],
                    },
                },
                {
                    "id": "sort",
                    "type": "sort_row",
                    "config": {
                        "columns": [
                            {"name": "dept", "order": "asc", "nulls_last": True},
                            {"name": "salary", "order": "desc"},
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
                {"source": "source", "target": "sort"},
                {"source": "sort", "target": "output"},
            ],
        }

        engine = PyETLEngine(config)
        result = engine.execute()

        assert result["status"] == "success"
        output_df = pl.read_csv(output_file)
        # HR first, Sales second, null dept last
        assert output_df["dept"].to_list() == ["HR", "Sales", "Sales", None]
        # Within Sales: salary DESC with nulls_last=False (default) puts null salary first
        assert output_df["name"].to_list() == ["Diana", "Charlie", "Alice", "Bob"]
