"""Integration tests for Map component reject routing (lookup, filter, error)."""
import pytest
import polars as pl
from pathlib import Path
import tempfile

from src.v2.engine import PyETLEngine


@pytest.fixture
def data_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


class TestLookupRejectIntegration:
    def test_lookup_reject_end_to_end(self, data_dir):
        """Full pipeline: source -> map with inner join -> main + reject output files."""
        orders_file = data_dir / "orders.csv"
        orders_file.write_text("order_id,cust_id,amount\n1,10,100\n2,20,200\n3,30,300\n")

        customers_file = data_dir / "customers.csv"
        customers_file.write_text("id,name\n10,Alice\n20,Bob\n")

        main_out = data_dir / "main.csv"
        reject_out = data_dir / "rejects.csv"

        config = {
            "name": "lookup_reject_test",
            "components": [
                {"id": "orders", "type": "file_input_delimited", "config": {
                    "path": str(orders_file),
                    "schema": [
                        {"name": "order_id", "type": "integer"},
                        {"name": "cust_id", "type": "integer"},
                        {"name": "amount", "type": "integer"},
                    ],
                }},
                {"id": "customers", "type": "file_input_delimited", "config": {
                    "path": str(customers_file),
                    "schema": [
                        {"name": "id", "type": "integer"},
                        {"name": "name", "type": "string"},
                    ],
                }},
                {"id": "transform", "type": "map", "config": {
                    "lookup_reject_output": "bad_lookups",
                    "lookups": [{
                        "name": "customers",
                        "keys": [{"main": "cust_id", "lookup": "id"}],
                        "join_type": "inner",
                    }],
                    "outputs": [
                        {"name": "main", "columns": [
                            {"name": "order_id", "expression": "order_id"},
                            {"name": "customer_name", "expression": "customers.name"},
                        ]},
                        {"name": "bad_lookups", "columns": [
                            {"name": "order_id", "expression": "order_id"},
                            {"name": "cust_id", "expression": "cust_id"},
                        ]},
                    ],
                }},
                {"id": "write_main", "type": "file_output_delimited", "config": {"path": str(main_out)}},
                {"id": "write_rejects", "type": "file_output_delimited", "config": {"path": str(reject_out)}},
            ],
            "flows": [
                {"source": "orders", "target": "transform"},
                {"source": "customers", "target": "transform", "input": "customers"},
                {"source": "transform", "target": "write_main"},
                {"source": "transform", "target": "write_rejects", "output": "bad_lookups"},
            ],
        }
        result = PyETLEngine(config).execute()
        assert result["status"] == "success"

        main_df = pl.read_csv(main_out)
        assert len(main_df) == 2
        assert main_df["order_id"].to_list() == [1, 2]

        reject_df = pl.read_csv(reject_out)
        assert len(reject_df) == 1
        assert reject_df["order_id"][0] == 3


class TestFilterRejectIntegration:
    def test_filter_reject_end_to_end(self, data_dir):
        """Full pipeline: source -> map with filters -> filtered outputs + reject file."""
        input_file = data_dir / "data.csv"
        input_file.write_text("id,amount\n1,200\n2,75\n3,30\n4,150\n")

        high_out = data_dir / "high.csv"
        low_out = data_dir / "low.csv"
        reject_out = data_dir / "unmatched.csv"

        config = {
            "name": "filter_reject_test",
            "components": [
                {"id": "input", "type": "file_input_delimited", "config": {
                    "path": str(input_file),
                    "schema": [
                        {"name": "id", "type": "integer"},
                        {"name": "amount", "type": "integer"},
                    ],
                }},
                {"id": "transform", "type": "map", "config": {
                    "filter_reject_output": "unmatched",
                    "outputs": [
                        {"name": "high", "filter": "amount > 100", "columns": [
                            {"name": "id", "expression": "id"},
                            {"name": "amount", "expression": "amount"},
                        ]},
                        {"name": "low", "filter": "amount <= 50", "columns": [
                            {"name": "id", "expression": "id"},
                            {"name": "amount", "expression": "amount"},
                        ]},
                        {"name": "unmatched", "columns": [
                            {"name": "id", "expression": "id"},
                            {"name": "amount", "expression": "amount"},
                        ]},
                    ],
                }},
                {"id": "write_high", "type": "file_output_delimited", "config": {"path": str(high_out)}},
                {"id": "write_low", "type": "file_output_delimited", "config": {"path": str(low_out)}},
                {"id": "write_unmatched", "type": "file_output_delimited", "config": {"path": str(reject_out)}},
            ],
            "flows": [
                {"source": "input", "target": "transform"},
                {"source": "transform", "target": "write_high", "output": "high"},
                {"source": "transform", "target": "write_low", "output": "low"},
                {"source": "transform", "target": "write_unmatched", "output": "unmatched"},
            ],
        }
        result = PyETLEngine(config).execute()
        assert result["status"] == "success"

        high_df = pl.read_csv(high_out)
        assert high_df["id"].to_list() == [1, 4]

        low_df = pl.read_csv(low_out)
        assert low_df["id"].to_list() == [3]

        reject_df = pl.read_csv(reject_out)
        assert reject_df["id"].to_list() == [2]


class TestErrorRejectIntegration:
    def test_error_reject_end_to_end(self, data_dir):
        """Full pipeline: source -> map with die_on_error=false -> main + error reject file."""
        input_file = data_dir / "data.csv"
        input_file.write_text("id,raw_amount\n1,100\n2,bad\n3,300\n")

        main_out = data_dir / "main.csv"
        error_out = data_dir / "errors.csv"

        config = {
            "name": "error_reject_test",
            "components": [
                {"id": "input", "type": "file_input_delimited", "config": {
                    "path": str(input_file),
                    "schema": [
                        {"name": "id", "type": "integer"},
                        {"name": "raw_amount", "type": "string"},
                    ],
                }},
                {"id": "transform", "type": "map", "config": {
                    "die_on_error": False,
                    "error_reject_output": "errors",
                    "outputs": [
                        {"name": "main", "columns": [
                            {"name": "id", "expression": "id"},
                            {"name": "amount", "expression": "TO_INTEGER(raw_amount)"},
                        ]},
                        {"name": "errors", "columns": []},
                    ],
                }},
                {"id": "write_main", "type": "file_output_delimited", "config": {"path": str(main_out)}},
                {"id": "write_errors", "type": "file_output_delimited", "config": {"path": str(error_out)}},
            ],
            "flows": [
                {"source": "input", "target": "transform"},
                {"source": "transform", "target": "write_main"},
                {"source": "transform", "target": "write_errors", "output": "errors"},
            ],
        }
        result = PyETLEngine(config).execute()
        assert result["status"] == "success"

        main_df = pl.read_csv(main_out)
        assert len(main_df) == 2
        assert main_df["id"].to_list() == [1, 3]

        error_df = pl.read_csv(error_out)
        assert len(error_df) == 1
        assert error_df["id"][0] == 2
        assert "_error_message" in error_df.columns
