"""Full pipeline integration test: tFileInputDelimited → tMap → tFileOutputDelimited.

Validates that the three core Talend components work together through the
actual engine execution loop (ExecutionPlan, OutputRouter, Executor).

No Java bridge needed -- uses simple column reference joins (pandas path).
"""
import json
import logging
import os
import tempfile

import pandas as pd
import pytest

from src.v1.engine.engine import ETLEngine  # auto-imports components via engine.py

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestFullPipeline:
    """End-to-end: read CSV → tMap join → write CSV."""

    def _build_job_config(self, input_path, lookup_path, output_path):
        """Build a job config JSON for the pipeline.

        Pipeline:
            orders.csv (main) → tMap (join with customers.csv on customer_id)
                                    → out1: enriched orders (customer_name added)
                                    → reject1: orders with no matching customer
                              → tFileOutputDelimited (write enriched orders)
        """
        return {
            "job_name": "test_full_pipeline",
            "java_config": {"enabled": True},
            "context": {},
            "components": [
                {
                    "id": "tFileInputDelimited_1",
                    "type": "tFileInputDelimited",
                    "config": {
                        "filepath": input_path,
                        "fieldseparator": ",",
                        "encoding": "UTF-8",
                        "header_rows": 1,
                        "footer_rows": 0,
                        "limit": 0,
                        "remove_empty_row": True,
                        "csv_option": False,
                        "die_on_error": True,
                        "check_fields_num": False,
                        "check_date": False,
                        "schema": [
                            {"name": "order_id", "type": "int", "nullable": False},
                            {"name": "customer_id", "type": "int", "nullable": False},
                            {"name": "amount", "type": "float", "nullable": False},
                            {"name": "product", "type": "str", "nullable": False},
                        ],
                    },
                    "inputs": [],
                    "outputs": ["row1"],
                    "schema": {},
                    "subjob_id": "subjob_1",
                    "is_subjob_start": True,
                },
                {
                    "id": "tFileInputDelimited_2",
                    "type": "tFileInputDelimited",
                    "config": {
                        "filepath": lookup_path,
                        "fieldseparator": ",",
                        "encoding": "UTF-8",
                        "header_rows": 1,
                        "footer_rows": 0,
                        "limit": 0,
                        "remove_empty_row": True,
                        "csv_option": False,
                        "die_on_error": True,
                        "check_fields_num": False,
                        "check_date": False,
                        "schema": [
                            {"name": "customer_id", "type": "int", "nullable": False},
                            {"name": "customer_name", "type": "str", "nullable": False},
                            {"name": "region", "type": "str", "nullable": False},
                        ],
                    },
                    "inputs": [],
                    "outputs": ["customers"],
                    "schema": {},
                    "subjob_id": "subjob_1",
                    "is_subjob_start": False,
                },
                {
                    "id": "tMap_1",
                    "type": "tMap",
                    "config": {
                        "inputs": {
                            "main": {
                                "name": "row1",
                                "filter": "",
                                "activate_filter": False,
                                "matching_mode": "UNIQUE_MATCH",
                                "lookup_mode": "LOAD_ONCE",
                            },
                            "lookups": [
                                {
                                    "name": "customers",
                                    "matching_mode": "UNIQUE_MATCH",
                                    "lookup_mode": "LOAD_ONCE",
                                    "filter": "",
                                    "activate_filter": False,
                                    "join_keys": [
                                        {
                                            "lookup_column": "customer_id",
                                            "expression": "{{java}}row1.customer_id",
                                            "type": "int",
                                            "nullable": False,
                                        }
                                    ],
                                    "join_mode": "LEFT_OUTER_JOIN",
                                }
                            ],
                        },
                        "variables": [],
                        "outputs": [
                            {
                                "name": "out1",
                                "is_reject": False,
                                "inner_join_reject": False,
                                "filter": "",
                                "activate_filter": False,
                                "catch_output_reject": False,
                                "columns": [
                                    {"name": "order_id", "expression": "{{java}}row1.order_id", "type": "int", "nullable": False},
                                    {"name": "customer_name", "expression": "{{java}}customers.customer_name", "type": "str", "nullable": True},
                                    {"name": "amount", "expression": "{{java}}row1.amount", "type": "float", "nullable": False},
                                    {"name": "product", "expression": "{{java}}row1.product", "type": "str", "nullable": False},
                                    {"name": "region", "expression": "{{java}}customers.region", "type": "str", "nullable": True},
                                ],
                            }
                        ],
                        "die_on_error": True,
                    },
                    "inputs": ["row1", "customers"],
                    "outputs": ["out1"],
                    "schema": {},
                    "subjob_id": "subjob_1",
                    "is_subjob_start": False,
                },
                {
                    "id": "tFileOutputDelimited_1",
                    "type": "tFileOutputDelimited",
                    "config": {
                        "filepath": output_path,
                        "fieldseparator": ",",
                        "encoding": "UTF-8",
                        "include_header": True,
                        "append": False,
                        "csv_option": False,
                        "die_on_error": True,
                        "create_directory": True,
                        "file_exist_exception": False,
                        "schema": [
                            {"name": "order_id", "type": "int", "nullable": False},
                            {"name": "customer_name", "type": "str", "nullable": True},
                            {"name": "amount", "type": "float", "nullable": False},
                            {"name": "product", "type": "str", "nullable": False},
                            {"name": "region", "type": "str", "nullable": True},
                        ],
                    },
                    "inputs": ["out1"],
                    "outputs": [],
                    "schema": {},
                    "subjob_id": "subjob_1",
                    "is_subjob_start": False,
                },
            ],
            "flows": [
                {"name": "row1", "from": "tFileInputDelimited_1", "to": "tMap_1", "type": "flow"},
                {"name": "customers", "from": "tFileInputDelimited_2", "to": "tMap_1", "type": "flow"},
                {"name": "out1", "from": "tMap_1", "to": "tFileOutputDelimited_1", "type": "flow"},
            ],
            "triggers": [],
            "subjobs": {
                "subjob_1": [
                    "tFileInputDelimited_1",
                    "tFileInputDelimited_2",
                    "tMap_1",
                    "tFileOutputDelimited_1",
                ],
            },
        }

    def test_read_join_write_pipeline(self, tmp_path):
        """Full pipeline: read orders + customers → join on customer_id → write enriched output."""
        # Create input files
        orders_csv = tmp_path / "orders.csv"
        orders_csv.write_text(
            "order_id,customer_id,amount,product\n"
            "1,101,29.99,Widget\n"
            "2,102,49.50,Gadget\n"
            "3,101,15.00,Doohickey\n"
            "4,103,99.99,Thingamajig\n"
            "5,999,10.00,Mystery\n"  # No matching customer -- left outer join keeps it
        )

        customers_csv = tmp_path / "customers.csv"
        customers_csv.write_text(
            "customer_id,customer_name,region\n"
            "101,Alice,WEST\n"
            "102,Bob,EAST\n"
            "103,Charlie,NORTH\n"
        )

        output_csv = tmp_path / "output" / "enriched_orders.csv"

        # Build and run job
        config = self._build_job_config(
            str(orders_csv), str(customers_csv), str(output_csv)
        )
        engine = ETLEngine(config)
        stats = engine.execute()

        # Verify execution succeeded
        assert stats.get("status") != "error", f"Job failed: {stats.get('error')}"

        # Verify output file was created
        assert output_csv.exists(), "Output file not created"

        # Read and verify output
        result = pd.read_csv(str(output_csv))
        logger.info(f"Output:\n{result.to_string()}")

        # 5 orders in, 5 out (left outer join keeps unmatched)
        assert len(result) == 5, f"Expected 5 rows, got {len(result)}"

        # Check columns
        expected_cols = {"order_id", "customer_name", "amount", "product", "region"}
        assert set(result.columns) == expected_cols, f"Columns: {list(result.columns)}"

        # Check joined data -- order 1 should have Alice/WEST
        alice_orders = result[result["customer_name"] == "Alice"]
        assert len(alice_orders) == 2, "Alice should have 2 orders"
        assert set(alice_orders["order_id"].tolist()) == {1, 3}

        # Check unmatched row -- order 5 (customer_id=999) should have NaN customer_name
        mystery = result[result["order_id"] == 5]
        assert len(mystery) == 1
        assert pd.isna(mystery.iloc[0]["customer_name"]), "Unmatched customer should be NaN"
        assert pd.isna(mystery.iloc[0]["region"]), "Unmatched region should be NaN"

        # Check globalMap stats
        gm = stats.get("global_map", {})
        logger.info(f"GlobalMap stats: {gm}")

        print("\n=== PIPELINE SUCCESS ===")
        print(f"Orders read: 5")
        print(f"Customers read: 3")
        print(f"Enriched output: {len(result)} rows")
        print(f"Output file: {output_csv}")
        print(result.to_string(index=False))
        print("========================\n")

    def test_inner_join_with_reject(self, tmp_path):
        """Pipeline with inner join -- unmatched orders route to reject."""
        orders_csv = tmp_path / "orders.csv"
        orders_csv.write_text(
            "order_id,customer_id,amount\n"
            "1,101,29.99\n"
            "2,102,49.50\n"
            "3,999,10.00\n"  # No match -- should go to reject
        )

        customers_csv = tmp_path / "customers.csv"
        customers_csv.write_text(
            "customer_id,customer_name\n"
            "101,Alice\n"
            "102,Bob\n"
        )

        output_csv = tmp_path / "output" / "matched.csv"
        reject_csv = tmp_path / "output" / "rejected.csv"

        config = {
            "job_name": "test_inner_join_reject",
            "java_config": {"enabled": True},
            "context": {},
            "components": [
                {
                    "id": "input_orders",
                    "type": "tFileInputDelimited",
                    "config": {
                        "filepath": str(orders_csv),
                        "fieldseparator": ",",
                        "encoding": "UTF-8",
                        "header_rows": 1,
                        "footer_rows": 0,
                        "limit": 0,
                        "remove_empty_row": True,
                        "csv_option": False,
                        "die_on_error": True,
                        "check_fields_num": False,
                        "check_date": False,
                        "schema": [
                            {"name": "order_id", "type": "int", "nullable": False},
                            {"name": "customer_id", "type": "int", "nullable": False},
                            {"name": "amount", "type": "float", "nullable": False},
                        ],
                    },
                    "inputs": [],
                    "outputs": ["row1"],
                    "schema": {},
                    "subjob_id": "subjob_1",
                    "is_subjob_start": True,
                },
                {
                    "id": "input_customers",
                    "type": "tFileInputDelimited",
                    "config": {
                        "filepath": str(customers_csv),
                        "fieldseparator": ",",
                        "encoding": "UTF-8",
                        "header_rows": 1,
                        "footer_rows": 0,
                        "limit": 0,
                        "remove_empty_row": True,
                        "csv_option": False,
                        "die_on_error": True,
                        "check_fields_num": False,
                        "check_date": False,
                        "schema": [
                            {"name": "customer_id", "type": "int", "nullable": False},
                            {"name": "customer_name", "type": "str", "nullable": False},
                        ],
                    },
                    "inputs": [],
                    "outputs": ["customers"],
                    "schema": {},
                    "subjob_id": "subjob_1",
                    "is_subjob_start": False,
                },
                {
                    "id": "tMap_1",
                    "type": "tMap",
                    "config": {
                        "inputs": {
                            "main": {
                                "name": "row1",
                                "filter": "",
                                "activate_filter": False,
                                "matching_mode": "UNIQUE_MATCH",
                                "lookup_mode": "LOAD_ONCE",
                            },
                            "lookups": [
                                {
                                    "name": "customers",
                                    "matching_mode": "UNIQUE_MATCH",
                                    "lookup_mode": "LOAD_ONCE",
                                    "filter": "",
                                    "activate_filter": False,
                                    "join_keys": [
                                        {
                                            "lookup_column": "customer_id",
                                            "expression": "{{java}}row1.customer_id",
                                            "type": "int",
                                            "nullable": False,
                                        }
                                    ],
                                    "join_mode": "INNER_JOIN",
                                }
                            ],
                        },
                        "variables": [],
                        "outputs": [
                            {
                                "name": "out1",
                                "is_reject": False,
                                "inner_join_reject": False,
                                "filter": "",
                                "activate_filter": False,
                                "catch_output_reject": False,
                                "columns": [
                                    {"name": "order_id", "expression": "{{java}}row1.order_id", "type": "int", "nullable": False},
                                    {"name": "customer_name", "expression": "{{java}}customers.customer_name", "type": "str", "nullable": False},
                                    {"name": "amount", "expression": "{{java}}row1.amount", "type": "float", "nullable": False},
                                ],
                            },
                            {
                                "name": "reject1",
                                "is_reject": False,
                                "inner_join_reject": True,
                                "filter": "",
                                "activate_filter": False,
                                "catch_output_reject": False,
                                "columns": [
                                    {"name": "order_id", "expression": "{{java}}row1.order_id", "type": "int", "nullable": False},
                                    {"name": "customer_id", "expression": "{{java}}row1.customer_id", "type": "int", "nullable": False},
                                    {"name": "amount", "expression": "{{java}}row1.amount", "type": "float", "nullable": False},
                                ],
                            },
                        ],
                        "die_on_error": True,
                    },
                    "inputs": ["row1", "customers"],
                    "outputs": ["out1", "reject1"],
                    "schema": {},
                    "subjob_id": "subjob_1",
                    "is_subjob_start": False,
                },
                {
                    "id": "output_matched",
                    "type": "tFileOutputDelimited",
                    "config": {
                        "filepath": str(output_csv),
                        "fieldseparator": ",",
                        "encoding": "UTF-8",
                        "include_header": True,
                        "append": False,
                        "csv_option": False,
                        "die_on_error": True,
                        "create_directory": True,
                        "file_exist_exception": False,
                        "schema": [
                            {"name": "order_id", "type": "int", "nullable": False},
                            {"name": "customer_name", "type": "str", "nullable": False},
                            {"name": "amount", "type": "float", "nullable": False},
                        ],
                    },
                    "inputs": ["out1"],
                    "outputs": [],
                    "schema": {},
                    "subjob_id": "subjob_1",
                    "is_subjob_start": False,
                },
                {
                    "id": "output_rejected",
                    "type": "tFileOutputDelimited",
                    "config": {
                        "filepath": str(reject_csv),
                        "fieldseparator": ",",
                        "encoding": "UTF-8",
                        "include_header": True,
                        "append": False,
                        "csv_option": False,
                        "die_on_error": True,
                        "create_directory": True,
                        "file_exist_exception": False,
                        "schema": [
                            {"name": "order_id", "type": "int", "nullable": False},
                            {"name": "customer_id", "type": "int", "nullable": False},
                            {"name": "amount", "type": "float", "nullable": False},
                        ],
                    },
                    "inputs": ["reject1"],
                    "outputs": [],
                    "schema": {},
                    "subjob_id": "subjob_1",
                    "is_subjob_start": False,
                },
            ],
            "flows": [
                {"name": "row1", "from": "input_orders", "to": "tMap_1", "type": "flow"},
                {"name": "customers", "from": "input_customers", "to": "tMap_1", "type": "flow"},
                {"name": "out1", "from": "tMap_1", "to": "output_matched", "type": "flow"},
                {"name": "reject1", "from": "tMap_1", "to": "output_rejected", "type": "flow"},
            ],
            "triggers": [],
            "subjobs": {
                "subjob_1": [
                    "input_orders", "input_customers", "tMap_1",
                    "output_matched", "output_rejected",
                ],
            },
        }

        engine = ETLEngine(config)
        stats = engine.execute()

        assert stats.get("status") != "error", f"Job failed: {stats.get('error')}"

        # Matched output
        assert output_csv.exists(), "Matched output not created"
        matched = pd.read_csv(str(output_csv))
        assert len(matched) == 2, f"Expected 2 matched, got {len(matched)}"

        # Rejected output
        assert reject_csv.exists(), "Reject output not created"
        rejected = pd.read_csv(str(reject_csv))
        assert len(rejected) == 1, f"Expected 1 rejected, got {len(rejected)}"
        assert rejected.iloc[0]["order_id"] == 3
        assert rejected.iloc[0]["customer_id"] == 999

        print("\n=== INNER JOIN + REJECT PIPELINE SUCCESS ===")
        print(f"Matched: {len(matched)} rows")
        print(matched.to_string(index=False))
        print(f"\nRejected: {len(rejected)} rows")
        print(rejected.to_string(index=False))
        print("=============================================\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
