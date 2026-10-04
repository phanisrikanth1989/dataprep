"""
Test fixtures specific to v2 engine tests.
"""
import pytest
import polars as pl
from pathlib import Path


@pytest.fixture
def sample_orders_df():
    """Create a sample orders DataFrame for testing."""
    return pl.DataFrame({
        "order_id": [1001, 1002, 1003, 1004, 1005],
        "customer_id": ["C001", "C002", "C001", "C003", "C002"],
        "product": ["Widget", "Gadget", "Widget", "Gizmo", "Widget"],
        "quantity": [5, 3, 2, 1, 10],
        "unit_price": [10.00, 25.00, 10.00, 50.00, 10.00],
    })


@pytest.fixture
def sample_customers_df():
    """Create a sample customers DataFrame for lookup testing."""
    return pl.DataFrame({
        "customer_id": ["C001", "C002", "C003"],
        "name": ["Acme Corp", "Beta Inc", "Gamma LLC"],
        "country": ["US", "UK", "US"],
        "tier": ["Gold", "Silver", "Bronze"],
    })


@pytest.fixture
def sample_products_df():
    """Create a sample products DataFrame for testing."""
    return pl.DataFrame({
        "product": ["Widget", "Gadget", "Gizmo"],
        "category": ["Tools", "Electronics", "Tools"],
        "cost": [5.00, 15.00, 30.00],
    })


@pytest.fixture
def empty_df():
    """Create an empty DataFrame with schema."""
    return pl.DataFrame({
        "id": pl.Series([], dtype=pl.Int64),
        "name": pl.Series([], dtype=pl.Utf8),
        "value": pl.Series([], dtype=pl.Float64),
    })


@pytest.fixture
def df_with_nulls():
    """Create a DataFrame with NULL values for null handling tests."""
    return pl.DataFrame({
        "id": [1, 2, 3, 4],
        "name": ["Alice", None, "Charlie", ""],
        "amount": [100.0, None, 150.0, 200.0],
        "date": ["2024-01-15", "2024-01-16", None, "2024-01-18"],
    })


@pytest.fixture
def sample_context():
    """Create sample context variables for testing."""
    return {
        "tax_rate": 0.08,
        "currency": "USD",
        "processing_date": "2024-01-15",
        "region": "US",
    }


@pytest.fixture
def temp_job_dir(tmp_path):
    """Create a temporary job directory with input/output folders."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    return {
        "base": tmp_path,
        "input": input_dir,
        "output": output_dir,
    }


@pytest.fixture
def sample_job_config(temp_job_dir):
    """Create a sample job configuration for testing."""
    return {
        "name": "test_job",
        "version": "2.0",
        "engine": "python",
        "context": {
            "tax_rate": {"value": 0.08, "type": "float"},
            "output_dir": {"value": str(temp_job_dir["output"]), "type": "str"},
        },
        "components": [],
    }
