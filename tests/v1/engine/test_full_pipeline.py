"""Full pipeline integration test: tFileInputDelimited -> tMap -> tFileOutputDelimited.

Validates that the three core Talend components work together through the
actual engine execution loop (ExecutionPlan, OutputRouter, Executor).

TestFullPipeline: No Java bridge needed -- uses simple column reference joins (pandas path).
TestTMapJavaExpressionPipeline: Requires live JVM -- tests compiled Groovy expressions
    (string concat, ternary, cross-table lookups) through the real Java bridge.
"""
import logging
from pathlib import Path

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

        logger.info("=== PIPELINE SUCCESS ===")
        logger.info("Orders read: 5")
        logger.info("Customers read: 3")
        logger.info(f"Enriched output: {len(result)} rows")
        logger.info(f"Output file: {output_csv}")
        logger.info(result.to_string(index=False))
        logger.info("========================")

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

        logger.info("=== INNER JOIN + REJECT PIPELINE SUCCESS ===")
        logger.info(f"Matched: {len(matched)} rows")
        logger.info(matched.to_string(index=False))
        logger.info(f"Rejected: {len(rejected)} rows")
        logger.info(rejected.to_string(index=False))
        logger.info("=============================================")


@pytest.mark.java
@pytest.mark.integration
class TestTMapJavaExpressionPipeline:
    """End-to-end pipeline with Java expressions through real JVM bridge.

    Verifies the extractTypedValue fix (Phase 5.1) by running a complete
    pipeline: CSV read -> tMap with compiled Groovy expressions -> CSV write.

    Expressions tested:
      - String concatenation: row1.first_name + " " + row1.last_name
      - Ternary conditional: row1.salary >= 75000 ? "Senior" : "Junior"
      - Cross-table lookups: countries.country_name, countries.region
      - Simple column ref: row1.department, row1.salary

    Uses fixture CSVs at tests/v1/engine/fixtures/pipeline/:
      - employees.csv (7 rows, semicolon-delimited)
      - country_lookup.csv (8 rows, semicolon-delimited)
    """

    FIXTURES_DIR = Path(__file__).parent / "fixtures" / "pipeline"

    def _build_java_pipeline_config(self, employees_path, lookup_path, output_path):
        """Build a job config for tMap with Java expressions.

        Pipeline:
            tFileInputDelimited_1 (employees.csv, ";") -> row1
            tFileInputDelimited_2 (country_lookup.csv, ";") -> countries
            tMap_1:
              main: row1
              lookup: countries (LEFT_OUTER_JOIN on country_code)
              out1 columns:
                full_name = row1.first_name + " " + row1.last_name  (string concat)
                department = row1.department  (simple ref)
                salary = row1.salary  (numeric passthrough)
                country_name = countries.country_name  (cross-table)
                region = countries.region  (cross-table)
                salary_grade = row1.salary >= 75000 ? "Senior" : "Junior"  (ternary)
            tFileOutputDelimited_1 (output.csv, ",")
        """
        return {
            "job_name": "test_java_expression_pipeline",
            "java_config": {"enabled": True, "routines": []},
            "context": {},
            "components": [
                {
                    "id": "tFileInputDelimited_1",
                    "type": "tFileInputDelimited",
                    "config": {
                        "filepath": employees_path,
                        "fieldseparator": ";",
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
                            {"name": "id", "type": "int", "nullable": False},
                            {"name": "first_name", "type": "str", "nullable": False},
                            {"name": "last_name", "type": "str", "nullable": False},
                            {"name": "department", "type": "str", "nullable": False},
                            {"name": "salary", "type": "float", "nullable": False},
                            {"name": "country_code", "type": "str", "nullable": False},
                        ],
                    },
                    "inputs": [],
                    "outputs": ["row1"],
                    "schema": {
                        "output": [
                            {"name": "id", "type": "int", "nullable": False},
                            {"name": "first_name", "type": "str", "nullable": False},
                            {"name": "last_name", "type": "str", "nullable": False},
                            {"name": "department", "type": "str", "nullable": False},
                            {"name": "salary", "type": "float", "nullable": False},
                            {"name": "country_code", "type": "str", "nullable": False},
                        ],
                    },
                    "subjob_id": "subjob_1",
                    "is_subjob_start": True,
                },
                {
                    "id": "tFileInputDelimited_2",
                    "type": "tFileInputDelimited",
                    "config": {
                        "filepath": lookup_path,
                        "fieldseparator": ";",
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
                            {"name": "country_code", "type": "str", "nullable": False},
                            {"name": "country_name", "type": "str", "nullable": False},
                            {"name": "region", "type": "str", "nullable": False},
                        ],
                    },
                    "inputs": [],
                    "outputs": ["countries"],
                    "schema": {
                        "output": [
                            {"name": "country_code", "type": "str", "nullable": False},
                            {"name": "country_name", "type": "str", "nullable": False},
                            {"name": "region", "type": "str", "nullable": False},
                        ],
                    },
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
                                    "name": "countries",
                                    "matching_mode": "UNIQUE_MATCH",
                                    "lookup_mode": "LOAD_ONCE",
                                    "filter": "",
                                    "activate_filter": False,
                                    "join_keys": [
                                        {
                                            "lookup_column": "country_code",
                                            "expression": "{{java}}row1.country_code",
                                            "type": "str",
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
                                    {
                                        "name": "full_name",
                                        "expression": '{{java}}row1.first_name + " " + row1.last_name',
                                        "type": "str",
                                        "nullable": False,
                                    },
                                    {
                                        "name": "department",
                                        "expression": "{{java}}row1.department",
                                        "type": "str",
                                        "nullable": False,
                                    },
                                    {
                                        "name": "salary",
                                        "expression": "{{java}}row1.salary",
                                        "type": "float",
                                        "nullable": False,
                                    },
                                    {
                                        "name": "country_name",
                                        "expression": "{{java}}countries.country_name",
                                        "type": "str",
                                        "nullable": True,
                                    },
                                    {
                                        "name": "region",
                                        "expression": "{{java}}countries.region",
                                        "type": "str",
                                        "nullable": True,
                                    },
                                    {
                                        "name": "salary_grade",
                                        "expression": '{{java}}row1.salary >= 75000 ? "Senior" : "Junior"',
                                        "type": "str",
                                        "nullable": False,
                                    },
                                ],
                            }
                        ],
                        "die_on_error": True,
                    },
                    "inputs": ["row1", "countries"],
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
                            {"name": "full_name", "type": "str", "nullable": False},
                            {"name": "department", "type": "str", "nullable": False},
                            {"name": "salary", "type": "float", "nullable": False},
                            {"name": "country_name", "type": "str", "nullable": True},
                            {"name": "region", "type": "str", "nullable": True},
                            {"name": "salary_grade", "type": "str", "nullable": False},
                        ],
                    },
                    "inputs": ["out1"],
                    "outputs": [],
                    "schema": {
                        "output": [
                            {"name": "full_name", "type": "str", "nullable": False},
                            {"name": "department", "type": "str", "nullable": False},
                            {"name": "salary", "type": "float", "nullable": False},
                            {"name": "country_name", "type": "str", "nullable": True},
                            {"name": "region", "type": "str", "nullable": True},
                            {"name": "salary_grade", "type": "str", "nullable": False},
                        ],
                    },
                    "subjob_id": "subjob_1",
                    "is_subjob_start": False,
                },
            ],
            "flows": [
                {"name": "row1", "from": "tFileInputDelimited_1", "to": "tMap_1", "type": "flow"},
                {"name": "countries", "from": "tFileInputDelimited_2", "to": "tMap_1", "type": "flow"},
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

    def test_java_expression_pipeline(self, tmp_path):
        """Full pipeline: employees + countries -> tMap with Java expressions -> enriched CSV.

        Validates D-07: real pipeline with string concat, ternary, and cross-table
        lookups through the live JVM bridge with compiled Groovy scripts.
        """
        employees_csv = str(self.FIXTURES_DIR / "employees.csv")
        lookup_csv = str(self.FIXTURES_DIR / "country_lookup.csv")
        output_csv = tmp_path / "output" / "enriched_employees.csv"

        config = self._build_java_pipeline_config(
            employees_csv, lookup_csv, str(output_csv)
        )
        engine = ETLEngine(config)
        stats = engine.execute()

        # Verify execution succeeded
        assert stats.get("status") != "error", f"Job failed: {stats.get('error')}"
        assert output_csv.exists(), "Output file not created"

        # Read output
        result = pd.read_csv(str(output_csv))
        logger.info(f"Java expression pipeline output:\n{result.to_string()}")

        # -- Row count: all 7 employees (LEFT_OUTER_JOIN keeps all) --
        assert len(result) == 7, f"Expected 7 rows, got {len(result)}"

        # -- Column check --
        expected_cols = {"full_name", "department", "salary", "country_name", "region", "salary_grade"}
        assert set(result.columns) == expected_cols, f"Columns: {list(result.columns)}"

        # -- String concatenation (THE BUG that Phase 5.1 fixes) --
        full_names = result["full_name"].tolist()
        expected_names = [
            "John Smith", "Jane Doe", "Pierre Dupont", "Hans Mueller",
            "Maria Garcia", "Yuki Tanaka", "Li Wei",
        ]
        assert sorted(full_names) == sorted(expected_names), (
            f"String concat failed. Expected {expected_names}, got {full_names}"
        )

        # -- Ternary conditional (THE BUG that Phase 5.1 fixes) --
        # Senior: salary >= 75000 -> John(85000), Pierre(90000), Maria(78000), Li(95000)
        # Junior: salary < 75000  -> Jane(65000), Hans(55000), Yuki(72000)
        grades = dict(zip(result["full_name"], result["salary_grade"]))
        assert grades["John Smith"] == "Senior", f"John should be Senior, got {grades['John Smith']}"
        assert grades["Jane Doe"] == "Junior", f"Jane should be Junior, got {grades['Jane Doe']}"
        assert grades["Pierre Dupont"] == "Senior", f"Pierre should be Senior, got {grades['Pierre Dupont']}"
        assert grades["Hans Mueller"] == "Junior", f"Hans should be Junior, got {grades['Hans Mueller']}"
        assert grades["Maria Garcia"] == "Senior", f"Maria should be Senior, got {grades['Maria Garcia']}"
        assert grades["Yuki Tanaka"] == "Junior", f"Yuki should be Junior, got {grades['Yuki Tanaka']}"
        assert grades["Li Wei"] == "Senior", f"Li should be Senior, got {grades['Li Wei']}"

        # -- Cross-table lookups (country_name and region from lookup table) --
        countries = dict(zip(result["full_name"], result["country_name"]))
        assert countries["John Smith"] == "United States"
        assert countries["Jane Doe"] == "United Kingdom"
        assert countries["Pierre Dupont"] == "France"
        assert countries["Hans Mueller"] == "Germany"
        assert countries["Maria Garcia"] == "Spain"
        assert countries["Yuki Tanaka"] == "Japan"
        assert countries["Li Wei"] == "China"

        regions = dict(zip(result["full_name"], result["region"]))
        assert regions["John Smith"] == "Americas"
        assert regions["Jane Doe"] == "Europe"
        assert regions["Pierre Dupont"] == "Europe"
        assert regions["Hans Mueller"] == "Europe"
        assert regions["Maria Garcia"] == "Europe"
        assert regions["Yuki Tanaka"] == "Asia"
        assert regions["Li Wei"] == "Asia"

        # -- Department passthrough --
        depts = dict(zip(result["full_name"], result["department"]))
        assert depts["John Smith"] == "Engineering"
        assert depts["Jane Doe"] == "Marketing"
        assert depts["Li Wei"] == "Sales"

        # -- Salary numeric passthrough --
        salaries = dict(zip(result["full_name"], result["salary"]))
        assert salaries["John Smith"] == 85000.0
        assert salaries["Jane Doe"] == 65000.0
        assert salaries["Li Wei"] == 95000.0

        logger.info("=== JAVA EXPRESSION PIPELINE SUCCESS ===")
        logger.info("Employees read: 7 (semicolon-delimited)")
        logger.info("Countries read: 8 (semicolon-delimited)")
        logger.info(f"Enriched output: {len(result)} rows")
        logger.info(f"String concat: {len([n for n in full_names if ' ' in n])}/7 have spaces")
        logger.info(f"Ternary: {len([g for g in grades.values() if g == 'Senior'])} Senior, "
                     f"{len([g for g in grades.values() if g == 'Junior'])} Junior")
        logger.info(result.to_string(index=False))
        logger.info("=========================================")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
