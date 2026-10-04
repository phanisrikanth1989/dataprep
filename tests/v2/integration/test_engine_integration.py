"""
Integration tests for v2 PyETLEngine.

Tests full job execution with multiple components.
"""
import json
import pytest
import polars as pl
from pathlib import Path

from v2 import PyETLEngine
from v2.config import JobConfig


class TestEngineBasicPipeline:
    """Test basic ETL pipeline execution."""

    def test_simple_read_transform_write(self, temp_dir):
        """Test simple: read CSV -> transform -> write CSV."""
        # Create input file
        input_path = temp_dir / "input.csv"
        input_path.write_text(
            "id,name,amount\n"
            "1,alice,100\n"
            "2,bob,200\n"
            "3,charlie,150\n"
        )

        output_path = temp_dir / "output.csv"

        # Define job configuration
        config = {
            "name": "simple_pipeline",
            "version": "2.0",
            "components": [
                {
                    "id": "input",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(input_path),
                        "schema": [
                            {"name": "id", "type": "integer"},
                            {"name": "name", "type": "string"},
                            {"name": "amount", "type": "integer"},
                        ],
                    },
                },
                {
                    "id": "transform",
                    "type": "map",
                    "config": {
                        "outputs": [{
                            "name": "main",
                            "columns": [
                                {"name": "id", "expression": "id"},
                                {"name": "upper_name", "expression": "UPPER(name)"},
                                {"name": "doubled", "expression": "amount * 2"},
                            ],
                        }],
                    },
                },
                {
                    "id": "output",
                    "type": "file_output_delimited",
                    "config": {"path": str(output_path)},
                },
            ],
            "flows": [
                {"source": "input", "target": "transform"},
                {"source": "transform", "target": "output"},
            ],
        }

        # Execute
        engine = PyETLEngine(config)
        result = engine.execute()

        # Verify
        assert result["status"] == "success"
        assert len(result["components"]) == 3

        output_df = pl.read_csv(output_path)
        assert len(output_df) == 3
        assert output_df["upper_name"].to_list() == ["ALICE", "BOB", "CHARLIE"]
        assert output_df["doubled"].to_list() == [200, 400, 300]

    def test_filter_pipeline(self, temp_dir):
        """Test pipeline with filter component."""
        input_path = temp_dir / "input.csv"
        input_path.write_text(
            "id,status,amount\n"
            "1,active,100\n"
            "2,inactive,200\n"
            "3,active,300\n"
            "4,inactive,50\n"
        )

        output_path = temp_dir / "output.csv"

        config = {
            "name": "filter_pipeline",
            "components": [
                {
                    "id": "input",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(input_path),
                        "schema": [
                            {"name": "id", "type": "integer"},
                            {"name": "status", "type": "string"},
                            {"name": "amount", "type": "integer"},
                        ],
                    },
                },
                {
                    "id": "filter",
                    "type": "filter",
                    "config": {"condition": "status == 'active' && amount > 100"},
                },
                {
                    "id": "output",
                    "type": "file_output_delimited",
                    "config": {"path": str(output_path)},
                },
            ],
            "flows": [
                {"source": "input", "target": "filter"},
                {"source": "filter", "target": "output"},
            ],
        }

        engine = PyETLEngine(config)
        result = engine.execute()

        assert result["status"] == "success"

        output_df = pl.read_csv(output_path)
        assert len(output_df) == 1
        assert output_df["id"][0] == 3

    def test_aggregate_pipeline(self, temp_dir):
        """Test pipeline with aggregation."""
        input_path = temp_dir / "orders.csv"
        input_path.write_text(
            "customer,product,quantity,price\n"
            "C1,Widget,5,10\n"
            "C1,Gadget,2,25\n"
            "C2,Widget,3,10\n"
            "C2,Widget,7,10\n"
        )

        output_path = temp_dir / "summary.csv"

        config = {
            "name": "aggregate_pipeline",
            "components": [
                {
                    "id": "input",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(input_path),
                        "schema": [
                            {"name": "customer", "type": "string"},
                            {"name": "product", "type": "string"},
                            {"name": "quantity", "type": "integer"},
                            {"name": "price", "type": "integer"},
                        ],
                    },
                },
                {
                    "id": "calc",
                    "type": "map",
                    "config": {
                        "outputs": [{
                            "name": "main",
                            "columns": [
                                {"name": "customer", "expression": "customer"},
                                {"name": "total", "expression": "quantity * price"},
                            ],
                        }],
                    },
                },
                {
                    "id": "agg",
                    "type": "aggregate",
                    "config": {
                        "group_by": ["customer"],
                        "aggregations": [
                            {"name": "total_amount", "function": "sum", "column": "total"},
                            {"name": "order_count", "function": "count", "column": "total"},
                        ],
                    },
                },
                {
                    "id": "output",
                    "type": "file_output_delimited",
                    "config": {"path": str(output_path)},
                },
            ],
            "flows": [
                {"source": "input", "target": "calc"},
                {"source": "calc", "target": "agg"},
                {"source": "agg", "target": "output"},
            ],
        }

        engine = PyETLEngine(config)
        result = engine.execute()

        assert result["status"] == "success"

        output_df = pl.read_csv(output_path).sort("customer")
        assert len(output_df) == 2

        c1_row = output_df.filter(pl.col("customer") == "C1")
        assert c1_row["total_amount"][0] == 100  # 5*10 + 2*25

        c2_row = output_df.filter(pl.col("customer") == "C2")
        assert c2_row["total_amount"][0] == 100  # 3*10 + 7*10


class TestEngineWithContext:
    """Test engine with context variables."""

    def test_context_variables(self, temp_dir):
        """Test using context variables in expressions."""
        input_path = temp_dir / "input.csv"
        input_path.write_text("amount\n100\n200\n300\n")

        output_path = temp_dir / "output.csv"

        config = {
            "name": "context_test",
            "context": {
                "tax_rate": {"value": 0.08, "type": "float"},
                "discount": {"value": 10, "type": "float"},
            },
            "components": [
                {
                    "id": "input",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(input_path),
                        "schema": [
                            {"name": "amount", "type": "float"},
                        ],
                    },
                },
                {
                    "id": "calc",
                    "type": "map",
                    "config": {
                        "outputs": [{
                            "name": "main",
                            "columns": [
                                {"name": "amount", "expression": "amount"},
                                {"name": "tax", "expression": "amount * context.tax_rate"},
                                {"name": "final", "expression": "amount + (amount * context.tax_rate) - context.discount"},
                            ],
                        }],
                    },
                },
                {
                    "id": "output",
                    "type": "file_output_delimited",
                    "config": {"path": str(output_path)},
                },
            ],
            "flows": [
                {"source": "input", "target": "calc"},
                {"source": "calc", "target": "output"},
            ],
        }

        engine = PyETLEngine(config)
        result = engine.execute()

        assert result["status"] == "success"

        output_df = pl.read_csv(output_path)
        # First row: amount=100, tax=8, final=100+8-10=98
        assert output_df["tax"][0] == 8.0
        assert output_df["final"][0] == 98.0


class TestEngineSortAndUnique:
    """Test sorting and deduplication."""

    def test_sort_pipeline(self, temp_dir):
        """Test sorting in pipeline."""
        input_path = temp_dir / "input.csv"
        input_path.write_text("name,score\nCharlie,85\nAlice,95\nBob,90\n")

        output_path = temp_dir / "output.csv"

        config = {
            "name": "sort_test",
            "components": [
                {
                    "id": "input",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(input_path),
                        "schema": [
                            {"name": "name", "type": "string"},
                            {"name": "score", "type": "integer"},
                        ],
                    },
                },
                {
                    "id": "sort",
                    "type": "sort_row",
                    "config": {"columns": [{"name": "score", "order": "desc"}]},
                },
                {
                    "id": "output",
                    "type": "file_output_delimited",
                    "config": {"path": str(output_path)},
                },
            ],
            "flows": [
                {"source": "input", "target": "sort"},
                {"source": "sort", "target": "output"},
            ],
        }

        engine = PyETLEngine(config)
        result = engine.execute()

        assert result["status"] == "success"

        output_df = pl.read_csv(output_path)
        assert output_df["name"].to_list() == ["Alice", "Bob", "Charlie"]

    def test_unique_pipeline(self, temp_dir):
        """Test deduplication in pipeline."""
        input_path = temp_dir / "input.csv"
        input_path.write_text(
            "customer_id,order_date\n"
            "C1,2024-01-01\n"
            "C1,2024-01-02\n"
            "C2,2024-01-01\n"
            "C1,2024-01-03\n"
        )

        output_path = temp_dir / "output.csv"

        config = {
            "name": "unique_test",
            "components": [
                {
                    "id": "input",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(input_path),
                        "schema": [
                            {"name": "customer_id", "type": "string"},
                            {"name": "order_date", "type": "string"},
                        ],
                    },
                },
                {
                    "id": "unique",
                    "type": "uniq_row",
                    "config": {
                        "key_columns": [{"column": "customer_id", "case_sensitive": True}],
                    },
                },
                {
                    "id": "output",
                    "type": "file_output_delimited",
                    "config": {"path": str(output_path)},
                },
            ],
            "flows": [
                {"source": "input", "target": "unique"},
                {"source": "unique", "target": "output", "output": "unique"},
            ],
        }

        engine = PyETLEngine(config)
        result = engine.execute()

        assert result["status"] == "success"

        output_df = pl.read_csv(output_path)
        assert len(output_df) == 2  # One row per customer


class TestEngineFromJsonFile:
    """Test loading job from JSON file."""

    def test_load_from_json(self, temp_dir):
        """Test loading job configuration from JSON file."""
        # Create input data
        input_path = temp_dir / "data.csv"
        input_path.write_text("id,value\n1,100\n2,200\n")

        output_path = temp_dir / "result.csv"

        # Create job JSON
        job_config = {
            "name": "json_test",
            "components": [
                {
                    "id": "in",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(input_path),
                        "schema": [
                            {"name": "id", "type": "integer"},
                            {"name": "value", "type": "integer"},
                        ],
                    },
                },
                {
                    "id": "out",
                    "type": "file_output_delimited",
                    "config": {"path": str(output_path)},
                },
            ],
            "flows": [{"source": "in", "target": "out"}],
        }

        job_path = temp_dir / "job.json"
        job_path.write_text(json.dumps(job_config))

        # Execute from file path
        engine = PyETLEngine(job_path)
        result = engine.execute()

        assert result["status"] == "success"
        assert output_path.exists()


class TestEngineLookupPipeline:
    """Test Map component with lookups (joins)."""

    def test_map_with_left_join(self, temp_dir):
        """read orders + read customers -> map with lookup -> write"""
        # Create orders
        orders_path = temp_dir / "orders.csv"
        orders_path.write_text("order_id,customer_id,amount\n1,C1,100\n2,C2,200\n3,C3,300\n")

        # Create customers
        customers_path = temp_dir / "customers.csv"
        customers_path.write_text("id,name\nC1,Alice\nC2,Bob\n")  # C3 missing

        output_path = temp_dir / "output.csv"

        config = {
            "name": "lookup_test",
            "components": [
                {"id": "orders", "type": "file_input_delimited", "config": {
                    "path": str(orders_path),
                    "schema": [
                        {"name": "order_id", "type": "integer"},
                        {"name": "customer_id", "type": "string"},
                        {"name": "amount", "type": "integer"},
                    ],
                }},
                {"id": "customers", "type": "file_input_delimited", "config": {
                    "path": str(customers_path),
                    "schema": [
                        {"name": "id", "type": "string"},
                        {"name": "name", "type": "string"},
                    ],
                }},
                {"id": "join", "type": "map", "config": {
                    "lookups": [{
                        "name": "customers",
                        "keys": [{"main": "customer_id", "lookup": "id"}],
                        "join_type": "left",
                    }],
                    "outputs": [{"name": "main", "columns": [
                        {"name": "order_id", "expression": "order_id"},
                        {"name": "customer_name", "expression": "customers.name"},
                        {"name": "amount", "expression": "amount"},
                    ]}],
                }},
                {"id": "write", "type": "file_output_delimited", "config": {"path": str(output_path)}},
            ],
            "flows": [
                {"source": "orders", "target": "join"},
                {"source": "customers", "target": "join", "input": "customers"},
                {"source": "join", "target": "write"},
            ],
        }

        engine = PyETLEngine(config)
        result = engine.execute()

        assert result["status"] == "success"
        df = pl.read_csv(output_path)
        assert len(df) == 3
        assert df.filter(pl.col("order_id") == 1)["customer_name"][0] == "Alice"
        # C3 has no match -> null
        assert df.filter(pl.col("order_id") == 3)["customer_name"][0] is None


class TestEnginePythonUDF:
    """Test Python component in pipeline."""

    def test_python_code_pipeline(self, temp_dir):
        """read -> python_code -> write"""
        input_path = temp_dir / "input.csv"
        input_path.write_text("name,score\nalice,85\nbob,92\n")
        output_path = temp_dir / "output.csv"

        config = {
            "name": "python_test",
            "components": [
                {"id": "read", "type": "file_input_delimited", "config": {
                    "path": str(input_path),
                    "schema": [
                        {"name": "name", "type": "string"},
                        {"name": "score", "type": "integer"},
                    ],
                }},
                {"id": "transform", "type": "python_code", "config": {
                    "code": "output_df = input_df.with_columns((pl.col('score') * 10).alias('scaled'))"
                }},
                {"id": "write", "type": "file_output_delimited", "config": {"path": str(output_path)}},
            ],
            "flows": [
                {"source": "read", "target": "transform"},
                {"source": "transform", "target": "write"},
            ],
        }

        engine = PyETLEngine(config)
        result = engine.execute()

        assert result["status"] == "success"
        df = pl.read_csv(output_path)
        assert df["scaled"].to_list() == [850, 920]


class TestEngineRejectFlow:
    """Test die_on_error with reject routing."""

    def test_reject_flow_routes_bad_rows(self, temp_dir):
        """Map with die_on_error=false routes bad casts to reject output."""
        input_path = temp_dir / "input.csv"
        input_path.write_text("id,raw_amount\n1,100\n2,bad\n3,300\n")
        output_path = temp_dir / "output.csv"
        reject_path = temp_dir / "reject.csv"

        config = {
            "name": "reject_test",
            "components": [
                {"id": "read", "type": "file_input_delimited", "config": {
                    "path": str(input_path),
                    "schema": [
                        {"name": "id", "type": "integer"},
                        {"name": "raw_amount", "type": "string"},
                    ],
                }},
                {"id": "transform", "type": "map", "config": {
                    "die_on_error": False,
                    "error_reject_output": "reject",
                    "outputs": [
                        {"name": "main", "columns": [
                            {"name": "id", "expression": "id"},
                            {"name": "amount", "expression": "TO_INTEGER(raw_amount)"},
                        ]},
                        {"name": "reject", "columns": []},
                    ],
                }},
                {"id": "write_main", "type": "file_output_delimited", "config": {"path": str(output_path)}},
                {"id": "write_reject", "type": "file_output_delimited", "config": {"path": str(reject_path)}},
            ],
            "flows": [
                {"source": "read", "target": "transform"},
                {"source": "transform", "target": "write_main"},
                {"source": "transform", "target": "write_reject", "output": "reject"},
            ],
        }

        engine = PyETLEngine(config)
        result = engine.execute()

        assert result["status"] == "success"

        main_df = pl.read_csv(output_path)
        assert len(main_df) == 2  # rows 1 and 3
        assert main_df["amount"].to_list() == [100, 300]

        reject_df = pl.read_csv(reject_path)
        assert len(reject_df) == 1  # row 2


class TestEngineUnion:
    """Test Union component in pipeline."""

    def test_union_two_sources(self, temp_dir):
        """Two reads -> union -> write"""
        file1 = temp_dir / "a.csv"
        file2 = temp_dir / "b.csv"
        file1.write_text("id,name\n1,Alice\n2,Bob\n")
        file2.write_text("id,name\n3,Charlie\n4,Diana\n")
        output_path = temp_dir / "output.csv"

        config = {
            "name": "union_test",
            "components": [
                {"id": "read_a", "type": "file_input_delimited", "config": {
                    "path": str(file1),
                    "schema": [
                        {"name": "id", "type": "integer"},
                        {"name": "name", "type": "string"},
                    ],
                }},
                {"id": "read_b", "type": "file_input_delimited", "config": {
                    "path": str(file2),
                    "schema": [
                        {"name": "id", "type": "integer"},
                        {"name": "name", "type": "string"},
                    ],
                }},
                {"id": "combine", "type": "unite", "config": {}},
                {"id": "write", "type": "file_output_delimited", "config": {"path": str(output_path)}},
            ],
            "flows": [
                {"source": "read_a", "target": "combine", "input": "a"},
                {"source": "read_b", "target": "combine", "input": "b"},
                {"source": "combine", "target": "write"},
            ],
        }

        engine = PyETLEngine(config)
        result = engine.execute()

        assert result["status"] == "success"
        df = pl.read_csv(output_path)
        assert len(df) == 4


class TestEngineLargeData:
    """Performance tests with larger datasets."""

    def test_10k_rows(self, temp_dir):
        """Verify performance doesn't regress with 10K rows."""
        import csv
        input_path = temp_dir / "large.csv"
        with open(input_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "value", "category"])
            for i in range(10000):
                writer.writerow([i, i * 10, f"cat_{i % 5}"])

        output_path = temp_dir / "output.csv"

        config = {
            "name": "large_test",
            "components": [
                {"id": "read", "type": "file_input_delimited", "config": {
                    "path": str(input_path),
                    "schema": [
                        {"name": "id", "type": "integer"},
                        {"name": "value", "type": "integer"},
                        {"name": "category", "type": "string"},
                    ],
                }},
                {"id": "filter", "type": "filter", "config": {"condition": "value > 50000"}},
                {"id": "transform", "type": "map", "config": {
                    "outputs": [{"name": "main", "columns": [
                        {"name": "id", "expression": "id"},
                        {"name": "doubled", "expression": "value * 2"},
                    ]}],
                }},
                {"id": "write", "type": "file_output_delimited", "config": {"path": str(output_path)}},
            ],
            "flows": [
                {"source": "read", "target": "filter"},
                {"source": "filter", "target": "transform"},
                {"source": "transform", "target": "write"},
            ],
        }

        engine = PyETLEngine(config)
        result = engine.execute()

        assert result["status"] == "success"
        df = pl.read_csv(output_path)
        assert len(df) == 4999  # ids 5001-9999
        assert result["duration_ms"] < 5000  # should be fast


class TestEngineStatsVerification:
    """Test per-component stats in execution result."""

    def test_component_stats(self, temp_dir):
        input_path = temp_dir / "input.csv"
        input_path.write_text("x\n1\n2\n3\n")
        output_path = temp_dir / "output.csv"

        config = {
            "name": "stats_test",
            "components": [
                {"id": "read", "type": "file_input_delimited", "config": {
                    "path": str(input_path),
                    "schema": [{"name": "x", "type": "integer"}],
                }},
                {"id": "write", "type": "file_output_delimited", "config": {"path": str(output_path)}},
            ],
            "flows": [{"source": "read", "target": "write"}],
        }

        engine = PyETLEngine(config)
        result = engine.execute()

        assert result["status"] == "success"
        assert "components" in result

        # Both components should have stats
        assert "read" in result["components"]
        assert "write" in result["components"]

        # Check stats structure
        write_stats = result["components"]["write"]
        assert "duration_ms" in write_stats
        assert "type" in write_stats
        assert write_stats["barrier"] is True  # sinks are barriers


class TestEngineBrokenRoutineObservability:
    """
    AUD-RTN-02 integration regression (Phase 1.1 Tier 1 fix).

    PyETLEngine wires a RoutineManager in its __init__; if the user's
    routines_dir contains a broken .py file, the engine MUST still
    initialize (PITFALLS #6 "log and skip" pattern) AND the ERROR log
    record emitted for the broken routine MUST carry ``exc_info`` with
    a populated traceback (PITFALLS #7 observability prevention rule).

    Before the fix, ``logger.error(msg)`` was called with no
    ``exc_info=True``, so the traceback was silently dropped and a user
    debugging a broken routine had only the exception ``__str__``.
    """

    def test_aud_rtn_02_bug_integration(self, temp_dir, caplog):
        """
        Drop a broken routine file into a tmp routines dir and run an
        ``input -> output`` pipeline through ``PyETLEngine(config,
        routines_dir=...)``. Assert:
          1. The engine constructs and runs successfully despite the
             broken routine (log-and-skip).
          2. The ERROR log record for ``broken_routine.py`` has
             ``exc_info`` populated with a traceback — this is the
             PITFALLS #7 observability requirement.
        """
        import logging

        # Build a routines dir containing one broken routine file.
        routines_dir = temp_dir / "routines"
        routines_dir.mkdir()
        broken = routines_dir / "broken_routine.py"
        broken.write_text(
            "# Intentionally invalid — SyntaxError at module load time\n"
            "def greet(name:\n"  # missing closing paren
            "    return name\n"
        )

        # Minimal pipeline that does not itself use any routine — it
        # just proves the engine initializes the RoutineManager with the
        # broken dir and keeps going.
        input_path = temp_dir / "input.csv"
        input_path.write_text("id,amount\n1,100\n2,200\n")
        output_path = temp_dir / "output.csv"

        config = {
            "name": "routine_error_observability",
            "components": [
                {
                    "id": "read",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(input_path),
                        "schema": [
                            {"name": "id", "type": "integer"},
                            {"name": "amount", "type": "integer"},
                        ],
                    },
                },
                {
                    "id": "write",
                    "type": "file_output_delimited",
                    "config": {"path": str(output_path)},
                },
            ],
            "flows": [{"source": "read", "target": "write"}],
        }

        caplog.clear()
        with caplog.at_level(logging.ERROR, logger="src.v2.routines.manager"):
            # Engine constructor triggers RoutineManager.load() via auto_load=True
            engine = PyETLEngine(config, routines_dir=str(routines_dir))
            result = engine.execute()

        # (1) Engine completed the job despite the broken routine
        assert result["status"] == "success", (
            f"engine should tolerate a broken routine (log-and-skip), "
            f"got result={result}"
        )
        assert output_path.exists()

        # (2) ERROR record exists and carries the traceback
        matching = [
            rec for rec in caplog.records
            if rec.levelno == logging.ERROR
            and "broken_routine.py" in rec.getMessage()
        ]
        assert matching, (
            "expected an ERROR log record mentioning 'broken_routine.py' "
            "to be emitted by RoutineManager during engine init — "
            f"got records: "
            f"{[(r.name, r.levelname, r.getMessage()) for r in caplog.records]}"
        )

        rec = matching[0]
        assert rec.exc_info is not None, (
            "AUD-RTN-02 violated: the ERROR record from the routine "
            "manager's load() loop has no exc_info attached. The "
            "traceback was dropped. PITFALLS #7 observability prevention "
            "rule requires 'log with traceback' for loader failures."
        )
        exc_type, exc_val, exc_tb = rec.exc_info
        assert exc_type is SyntaxError
        assert exc_tb is not None, "traceback (exc_info[2]) must be non-None"
