"""
Integration tests for Polars streaming mode.

Verifies that streaming=true in job config uses Polars' streaming engine
at barrier points, and produces identical results to non-streaming mode.
"""
import csv
from pathlib import Path

import polars as pl
import pytest

from src.v2.engine import PyETLEngine


@pytest.fixture
def data_dir(tmp_path):
    """Create test CSV data with enough rows to exercise streaming."""
    rows = [
        (f"P{i:04d}", f"Category_{i % 5}", float(i * 10), float(i * 6), i % 3 == 0)
        for i in range(1, 1001)
    ]
    input_file = tmp_path / "products.csv"
    with open(input_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["product_id", "category", "revenue", "cost", "active"])
        writer.writerows(rows)

    return tmp_path


def _build_filter_map_config(data_dir, output_file, streaming):
    """Filter+Map pipeline — fully streaming-compatible."""
    return {
        "name": "streaming_filter_map_test",
        "engine": "v2",
        "streaming": streaming,
        "components": [
            {
                "id": "read",
                "type": "file_input_delimited",
                "config": {
                    "path": str(data_dir / "products.csv"),
                    "schema": [
                        {"name": "product_id", "type": "string"},
                        {"name": "category", "type": "string"},
                        {"name": "revenue", "type": "float"},
                        {"name": "cost", "type": "float"},
                        {"name": "active", "type": "boolean"},
                    ],
                },
            },
            {
                "id": "filter_active",
                "type": "filter",
                "config": {"condition": "active == true"},
            },
            {
                "id": "calc",
                "type": "map",
                "config": {
                    "outputs": [{
                        "name": "main",
                        "columns": [
                            {"name": "product_id", "expression": "product_id"},
                            {"name": "category", "expression": "category"},
                            {"name": "revenue", "expression": "revenue"},
                            {"name": "profit", "expression": "revenue - cost"},
                        ],
                    }],
                },
            },
            {
                "id": "write",
                "type": "file_output_delimited",
                "config": {"path": str(output_file)},
            },
        ],
        "flows": [
            {"source": "read", "target": "filter_active"},
            {"source": "filter_active", "target": "calc"},
            {"source": "calc", "target": "write"},
        ],
    }


def _build_aggregate_config(data_dir, output_file, streaming):
    """Aggregate pipeline — aggregate silently falls back from streaming."""
    return {
        "name": "streaming_aggregate_test",
        "engine": "v2",
        "streaming": streaming,
        "components": [
            {
                "id": "read",
                "type": "file_input_delimited",
                "config": {
                    "path": str(data_dir / "products.csv"),
                    "schema": [
                        {"name": "product_id", "type": "string"},
                        {"name": "category", "type": "string"},
                        {"name": "revenue", "type": "float"},
                        {"name": "cost", "type": "float"},
                        {"name": "active", "type": "boolean"},
                    ],
                },
            },
            {
                "id": "agg",
                "type": "aggregate",
                "config": {
                    "group_by": ["category"],
                    "aggregations": [
                        {"name": "total_revenue", "function": "sum", "column": "revenue"},
                        {"name": "total_cost", "function": "sum", "column": "cost"},
                        {"name": "product_count", "function": "count", "column": "*"},
                    ],
                },
            },
            {
                "id": "sort",
                "type": "sort_row",
                "config": {
                    "columns": [{"name": "category", "order": "asc"}],
                },
            },
            {
                "id": "write",
                "type": "file_output_delimited",
                "config": {"path": str(output_file)},
            },
        ],
        "flows": [
            {"source": "read", "target": "agg"},
            {"source": "agg", "target": "sort"},
            {"source": "sort", "target": "write"},
        ],
    }


def _build_python_barrier_config(data_dir, output_file, streaming):
    """Pipeline with python_code barrier — hard barrier, no streaming."""
    return {
        "name": "streaming_python_barrier_test",
        "engine": "v2",
        "streaming": streaming,
        "components": [
            {
                "id": "read",
                "type": "file_input_delimited",
                "config": {
                    "path": str(data_dir / "products.csv"),
                    "schema": [
                        {"name": "product_id", "type": "string"},
                        {"name": "category", "type": "string"},
                        {"name": "revenue", "type": "float"},
                        {"name": "cost", "type": "float"},
                        {"name": "active", "type": "boolean"},
                    ],
                },
            },
            {
                "id": "py_transform",
                "type": "python_code",
                "config": {
                    "code": "output_df = input_df.with_columns((pl.col('revenue') * 1.1).round(2).alias('adjusted_revenue'))",
                },
            },
            {
                "id": "select_cols",
                "type": "filter_columns",
                "config": {
                    "columns": ["product_id", "revenue", "adjusted_revenue"],
                },
            },
            {
                "id": "write",
                "type": "file_output_delimited",
                "config": {"path": str(output_file)},
            },
        ],
        "flows": [
            {"source": "read", "target": "py_transform"},
            {"source": "py_transform", "target": "select_cols"},
            {"source": "select_cols", "target": "write"},
        ],
    }


class TestStreamingDefault:
    """Verify streaming defaults to off."""

    def test_streaming_default_false(self):
        """streaming should be False by default."""
        config = {
            "name": "default_test",
            "components": [],
            "flows": [],
        }
        from src.v2.config import JobConfig
        job = JobConfig(**config)
        assert job.streaming is False

    def test_streaming_explicit_true(self):
        """streaming=true should be accepted in config."""
        config = {
            "name": "streaming_test",
            "streaming": True,
            "components": [],
            "flows": [],
        }
        from src.v2.config import JobConfig
        job = JobConfig(**config)
        assert job.streaming is True


class TestStreamingFilterMapPipeline:
    """Test streaming with filter+map (fully streaming-compatible operations)."""

    def test_streaming_off(self, data_dir):
        """Baseline: streaming=false produces correct results."""
        output_file = data_dir / "out_normal.csv"
        config = _build_filter_map_config(data_dir, output_file, streaming=False)

        result = PyETLEngine(config).execute()
        assert result["status"] == "success"

        df = pl.read_csv(output_file)
        # 1000 rows, every 3rd is active (i % 3 == 0), so ~333 rows
        assert len(df) == 333
        assert "profit" in df.columns

    def test_streaming_on(self, data_dir):
        """streaming=true produces correct results."""
        output_file = data_dir / "out_streaming.csv"
        config = _build_filter_map_config(data_dir, output_file, streaming=True)

        result = PyETLEngine(config).execute()
        assert result["status"] == "success"

        df = pl.read_csv(output_file)
        assert len(df) == 333
        assert "profit" in df.columns

    def test_streaming_vs_normal_identical(self, data_dir):
        """Streaming and non-streaming produce identical output."""
        out_normal = data_dir / "out_normal.csv"
        out_stream = data_dir / "out_stream.csv"

        config_normal = _build_filter_map_config(data_dir, out_normal, streaming=False)
        config_stream = _build_filter_map_config(data_dir, out_stream, streaming=True)

        r1 = PyETLEngine(config_normal).execute()
        r2 = PyETLEngine(config_stream).execute()

        assert r1["status"] == "success"
        assert r2["status"] == "success"

        df1 = pl.read_csv(out_normal).sort("product_id")
        df2 = pl.read_csv(out_stream).sort("product_id")

        assert df1.shape == df2.shape
        assert df1.equals(df2)


class TestStreamingAggregatePipeline:
    """Test streaming with aggregate (silently falls back to in-memory)."""

    def test_aggregate_streaming_succeeds(self, data_dir):
        """Aggregate with streaming=true should succeed (silent fallback)."""
        output_file = data_dir / "out_agg_stream.csv"
        config = _build_aggregate_config(data_dir, output_file, streaming=True)

        result = PyETLEngine(config).execute()
        assert result["status"] == "success"

        df = pl.read_csv(output_file)
        # 5 categories (i % 5)
        assert len(df) == 5

    def test_aggregate_streaming_vs_normal_identical(self, data_dir):
        """Aggregate results should be identical with and without streaming."""
        out_normal = data_dir / "out_agg_normal.csv"
        out_stream = data_dir / "out_agg_stream.csv"

        config_normal = _build_aggregate_config(data_dir, out_normal, streaming=False)
        config_stream = _build_aggregate_config(data_dir, out_stream, streaming=True)

        r1 = PyETLEngine(config_normal).execute()
        r2 = PyETLEngine(config_stream).execute()

        assert r1["status"] == "success"
        assert r2["status"] == "success"

        df1 = pl.read_csv(out_normal).sort("category")
        df2 = pl.read_csv(out_stream).sort("category")

        assert df1.shape == df2.shape
        assert df1.equals(df2)


class TestStreamingWithPythonBarrier:
    """Test streaming with python_code barrier (hard barrier, no streaming)."""

    def test_python_barrier_streaming_succeeds(self, data_dir):
        """python_code barrier should work fine with streaming=true."""
        output_file = data_dir / "out_py_stream.csv"
        config = _build_python_barrier_config(data_dir, output_file, streaming=True)

        result = PyETLEngine(config).execute()
        assert result["status"] == "success"

        df = pl.read_csv(output_file)
        assert len(df) == 1000
        # adjusted_revenue should be revenue * 1.1
        row = df.filter(pl.col("product_id") == "P0001")
        assert row["adjusted_revenue"][0] == pytest.approx(11.0)

    def test_python_barrier_streaming_vs_normal_identical(self, data_dir):
        """Python barrier results should be identical with and without streaming."""
        out_normal = data_dir / "out_py_normal.csv"
        out_stream = data_dir / "out_py_stream.csv"

        config_normal = _build_python_barrier_config(data_dir, out_normal, streaming=False)
        config_stream = _build_python_barrier_config(data_dir, out_stream, streaming=True)

        r1 = PyETLEngine(config_normal).execute()
        r2 = PyETLEngine(config_stream).execute()

        assert r1["status"] == "success"
        assert r2["status"] == "success"

        df1 = pl.read_csv(out_normal).sort("product_id")
        df2 = pl.read_csv(out_stream).sort("product_id")

        assert df1.shape == df2.shape
        assert df1.equals(df2)


class TestStreamingParquetSink:
    """Test streaming with Parquet output sink."""

    def test_parquet_streaming(self, data_dir):
        """Parquet sink should work with streaming=true."""
        output_file = data_dir / "out_stream.parquet"
        config = {
            "name": "streaming_parquet_test",
            "engine": "v2",
            "streaming": True,
            "components": [
                {
                    "id": "read",
                    "type": "file_input_delimited",
                    "config": {
                        "path": str(data_dir / "products.csv"),
                        "schema": [
                            {"name": "product_id", "type": "string"},
                            {"name": "category", "type": "string"},
                            {"name": "revenue", "type": "float"},
                            {"name": "cost", "type": "float"},
                            {"name": "active", "type": "boolean"},
                        ],
                    },
                },
                {
                    "id": "filter_active",
                    "type": "filter",
                    "config": {"condition": "active == true"},
                },
                {
                    "id": "write",
                    "type": "file_output_parquet",
                    "config": {"path": str(output_file)},
                },
            ],
            "flows": [
                {"source": "read", "target": "filter_active"},
                {"source": "filter_active", "target": "write"},
            ],
        }

        result = PyETLEngine(config).execute()
        assert result["status"] == "success"

        df = pl.read_parquet(output_file)
        assert len(df) == 333
