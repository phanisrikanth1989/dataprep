"""Benchmark fixtures providing reference datasets of varying sizes.

All benchmark tests use disable_gc=True, warmup of 1000, and N>=5 runs.
Polars version is pinned at baseline capture time.
"""
import polars as pl
import pytest


@pytest.fixture
def small_dataset() -> pl.LazyFrame:
    """10,000-row reference dataset for quick benchmarks."""
    import random

    random.seed(42)
    n = 10_000
    return pl.DataFrame(
        {
            "id": list(range(n)),
            "name": [f"name_{i}" for i in range(n)],
            "amount": [random.uniform(0, 10000) for _ in range(n)],
            "category": [f"cat_{i % 20}" for i in range(n)],
            "active": [i % 3 != 0 for i in range(n)],
        }
    ).lazy()


@pytest.fixture
def medium_dataset() -> pl.LazyFrame:
    """100,000-row reference dataset for standard benchmarks."""
    import random

    random.seed(42)
    n = 100_000
    return pl.DataFrame(
        {
            "id": list(range(n)),
            "name": [f"name_{i}" for i in range(n)],
            "amount": [random.uniform(0, 10000) for _ in range(n)],
            "category": [f"cat_{i % 50}" for i in range(n)],
            "active": [i % 3 != 0 for i in range(n)],
        }
    ).lazy()


@pytest.fixture
def large_dataset() -> pl.LazyFrame:
    """1,000,000-row reference dataset for stress benchmarks."""
    import random

    random.seed(42)
    n = 1_000_000
    return pl.DataFrame(
        {
            "id": list(range(n)),
            "name": [f"name_{i}" for i in range(n)],
            "amount": [random.uniform(0, 10000) for _ in range(n)],
            "category": [f"cat_{i % 100}" for i in range(n)],
            "active": [i % 3 != 0 for i in range(n)],
        }
    ).lazy()
