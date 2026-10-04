"""
Performance barrier scenario tests for V2 PyETL Engine.

Compares 3 barrier placement strategies processing e-commerce orders
through a 15-component pipeline. The same business logic runs in all 3
scenarios -- only the barrier count differs.

Scenario A: 1 barrier (sink only) -- fully lazy
Scenario B: 3 barriers + sink -- python_code replaces filter_active, map_calculate, filter_validate
Scenario C: 6 barriers + sink -- B + map_cleanup, aggregate_summary, sort_revenue
"""
import os
import platform
import resource
import tracemalloc
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import polars as pl
import pytest

from src.v2.engine import PyETLEngine

# ---------------------------------------------------------------------------
# Scale constant
# ---------------------------------------------------------------------------
SCALE = 1_000_000


# ---------------------------------------------------------------------------
# Data generation
# ---------------------------------------------------------------------------
class DataGenerator:
    """Generate deterministic e-commerce test data."""

    @staticmethod
    def generate(base_dir: Path, scale: int = SCALE) -> Dict[str, Path]:
        rng = np.random.default_rng(42)

        paths = {}
        paths["orders"] = DataGenerator._gen_orders(base_dir, scale, rng)
        paths["products"] = DataGenerator._gen_products(base_dir, scale // 2, rng)
        paths["customers"] = DataGenerator._gen_customers(base_dir, scale // 5, rng)
        paths["discounts"] = DataGenerator._gen_discounts(base_dir, scale // 20, rng)
        paths["base_dir"] = base_dir
        paths["scale"] = scale
        return paths

    @staticmethod
    def _gen_orders(base_dir: Path, n: int, rng) -> Path:
        n_customers = n // 5
        n_products = n // 2
        n_discounts = n // 20

        order_ids = np.arange(1, n + 1)
        customer_ids = np.array([f"CUST_{i}" for i in rng.integers(0, n_customers, size=n)])
        product_ids = np.array([f"PROD_{i}" for i in rng.integers(0, n_products, size=n)])

        # discount_code: ~50% have a code, rest empty string
        disc_mask = rng.random(n) < 0.5
        disc_indices = rng.integers(0, n_discounts, size=n)
        discount_codes = np.where(disc_mask, np.array([f"DISC_{i}" for i in disc_indices]), "")

        quantities = rng.integers(1, 101, size=n)
        unit_prices = np.round(rng.uniform(5.0, 500.0, size=n), 2)

        statuses_pool = np.array(["completed", "shipped", "cancelled", "returned", "pending"])
        statuses = statuses_pool[rng.integers(0, 5, size=n)]

        months = rng.integers(1, 13, size=n)
        days = rng.integers(1, 29, size=n)
        order_dates = np.array([f"2024-{m:02d}-{d:02d}" for m, d in zip(months, days)])

        df = pl.DataFrame({
            "order_id": order_ids,
            "customer_id": customer_ids,
            "product_id": product_ids,
            "discount_code": discount_codes,
            "quantity": quantities,
            "unit_price": unit_prices,
            "status": statuses,
            "order_date": order_dates,
        })
        path = base_dir / "orders.csv"
        df.write_csv(path)
        return path

    @staticmethod
    def _gen_products(base_dir: Path, n: int, rng) -> Path:
        categories = [
            "Electronics", "Clothing", "Home", "Sports", "Books",
            "Toys", "Food", "Beauty", "Automotive", "Garden",
        ]
        product_ids = np.array([f"PROD_{i}" for i in range(n)])
        product_names = np.array([f"Product_{i}" for i in range(n)])
        cats = np.array(categories)[rng.integers(0, len(categories), size=n)]
        cost_prices = np.round(rng.uniform(2.0, 300.0, size=n), 2)
        weights = np.round(rng.uniform(0.1, 50.0, size=n), 2)

        df = pl.DataFrame({
            "product_id": product_ids,
            "product_name": product_names,
            "category": cats,
            "cost_price": cost_prices,
            "weight_kg": weights,
        })
        path = base_dir / "products.csv"
        df.write_csv(path)
        return path

    @staticmethod
    def _gen_customers(base_dir: Path, n: int, rng) -> Path:
        tiers = np.array(["Gold", "Silver", "Bronze", "Platinum"])
        regions = np.array(["North", "South", "East", "West", "Central"])

        customer_ids = np.array([f"CUST_{i}" for i in range(n)])
        customer_names = np.array([f"Customer_{i}" for i in range(n)])
        tier_arr = tiers[rng.integers(0, len(tiers), size=n)]
        region_arr = regions[rng.integers(0, len(regions), size=n)]
        emails = np.array([f"cust_{i}@example.com" for i in range(n)])

        df = pl.DataFrame({
            "customer_id": customer_ids,
            "customer_name": customer_names,
            "tier": tier_arr,
            "region": region_arr,
            "email": emails,
        })
        path = base_dir / "customers.csv"
        df.write_csv(path)
        return path

    @staticmethod
    def _gen_discounts(base_dir: Path, n: int, rng) -> Path:
        discount_codes = np.array([f"DISC_{i}" for i in range(n)])
        discount_pcts = np.round(rng.uniform(0.05, 0.50, size=n), 2)
        min_order_values = np.round(rng.uniform(10.0, 200.0, size=n), 2)

        df = pl.DataFrame({
            "discount_code": discount_codes,
            "discount_pct": discount_pcts,
            "min_order_value": min_order_values,
        })
        path = base_dir / "discounts.csv"
        df.write_csv(path)
        return path


# ---------------------------------------------------------------------------
# Memory helpers
# ---------------------------------------------------------------------------
def get_peak_memory_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    if platform.system() == "Darwin":
        return usage.ru_maxrss / (1024 * 1024)  # macOS: bytes
    else:
        return usage.ru_maxrss / 1024  # Linux: KB


# ---------------------------------------------------------------------------
# Config builder
# ---------------------------------------------------------------------------
def _file_input(comp_id: str, path: str, schema: List[Dict]) -> Dict:
    return {
        "id": comp_id,
        "type": "file_input_delimited",
        "config": {"path": path, "schema": schema},
    }


def _file_output(comp_id: str, path: str) -> Dict:
    return {
        "id": comp_id,
        "type": "file_output_delimited",
        "config": {"path": path, "delimiter": ","},
    }


ORDERS_SCHEMA = [
    {"name": "order_id", "type": "integer"},
    {"name": "customer_id", "type": "string"},
    {"name": "product_id", "type": "string"},
    {"name": "discount_code", "type": "string"},
    {"name": "quantity", "type": "integer"},
    {"name": "unit_price", "type": "float"},
    {"name": "status", "type": "string"},
    {"name": "order_date", "type": "string"},
]

PRODUCTS_SCHEMA = [
    {"name": "product_id", "type": "string"},
    {"name": "product_name", "type": "string"},
    {"name": "category", "type": "string"},
    {"name": "cost_price", "type": "float"},
    {"name": "weight_kg", "type": "float"},
]

CUSTOMERS_SCHEMA = [
    {"name": "customer_id", "type": "string"},
    {"name": "customer_name", "type": "string"},
    {"name": "tier", "type": "string"},
    {"name": "region", "type": "string"},
    {"name": "email", "type": "string"},
]

DISCOUNTS_SCHEMA = [
    {"name": "discount_code", "type": "string"},
    {"name": "discount_pct", "type": "float"},
    {"name": "min_order_value", "type": "float"},
]


# -- Shared component configs ------------------------------------------------

def _map_cleanup_lazy():
    """map component: UPPER(status) + pass-through."""
    return {
        "id": "map_cleanup",
        "type": "map",
        "config": {
            "outputs": [{"name": "main", "columns": [
                {"name": "order_id", "expression": "order_id"},
                {"name": "customer_id", "expression": "customer_id"},
                {"name": "product_id", "expression": "product_id"},
                {"name": "discount_code", "expression": "discount_code"},
                {"name": "quantity", "expression": "quantity"},
                {"name": "unit_price", "expression": "unit_price"},
                {"name": "status", "expression": "UPPER(status)"},
                {"name": "order_date", "expression": "order_date"},
            ]}],
        },
    }


def _map_cleanup_python():
    """python_code: UPPER(status)."""
    return {
        "id": "map_cleanup",
        "type": "python_code",
        "config": {
            "code": "output_df = input_df.with_columns(pl.col('status').str.to_uppercase())",
        },
    }


def _filter_active_lazy():
    return {
        "id": "filter_active",
        "type": "filter",
        "config": {"condition": "status != 'CANCELLED' && status != 'RETURNED'"},
    }


def _filter_active_python():
    return {
        "id": "filter_active",
        "type": "python_code",
        "config": {
            "code": "output_df = input_df.filter((pl.col('status') != 'CANCELLED') & (pl.col('status') != 'RETURNED'))",
        },
    }


def _map_product_enrich():
    """Lookup join to products (always lazy map -- cannot be python_code)."""
    return {
        "id": "map_product_enrich",
        "type": "map",
        "config": {
            "lookups": [{
                "name": "products",
                "input": "products",
                "keys": [{"main": "product_id", "lookup": "product_id"}],
                "join_type": "left",
                "match_mode": "first",
            }],
            "outputs": [{"name": "main", "columns": [
                {"name": "order_id", "expression": "order_id"},
                {"name": "customer_id", "expression": "customer_id"},
                {"name": "product_id", "expression": "product_id"},
                {"name": "discount_code", "expression": "discount_code"},
                {"name": "quantity", "expression": "quantity"},
                {"name": "unit_price", "expression": "unit_price"},
                {"name": "status", "expression": "status"},
                {"name": "order_date", "expression": "order_date"},
                {"name": "category", "expression": "products.category"},
                {"name": "cost_price", "expression": "products.cost_price"},
            ]}],
        },
    }


def _map_customer_enrich():
    """Lookup join to customers."""
    return {
        "id": "map_customer_enrich",
        "type": "map",
        "config": {
            "lookups": [{
                "name": "customers",
                "input": "customers",
                "keys": [{"main": "customer_id", "lookup": "customer_id"}],
                "join_type": "left",
                "match_mode": "first",
            }],
            "outputs": [{"name": "main", "columns": [
                {"name": "order_id", "expression": "order_id"},
                {"name": "customer_id", "expression": "customer_id"},
                {"name": "product_id", "expression": "product_id"},
                {"name": "discount_code", "expression": "discount_code"},
                {"name": "quantity", "expression": "quantity"},
                {"name": "unit_price", "expression": "unit_price"},
                {"name": "status", "expression": "status"},
                {"name": "order_date", "expression": "order_date"},
                {"name": "category", "expression": "category"},
                {"name": "cost_price", "expression": "cost_price"},
                {"name": "tier", "expression": "customers.tier"},
                {"name": "region", "expression": "customers.region"},
            ]}],
        },
    }


def _map_discount_enrich():
    """Lookup join to discounts with COALESCE for null fill."""
    return {
        "id": "map_discount_enrich",
        "type": "map",
        "config": {
            "lookups": [{
                "name": "discounts",
                "input": "discounts",
                "keys": [{"main": "discount_code", "lookup": "discount_code"}],
                "join_type": "left",
                "match_mode": "first",
            }],
            "outputs": [{"name": "main", "columns": [
                {"name": "order_id", "expression": "order_id"},
                {"name": "customer_id", "expression": "customer_id"},
                {"name": "product_id", "expression": "product_id"},
                {"name": "discount_code", "expression": "discount_code"},
                {"name": "quantity", "expression": "quantity"},
                {"name": "unit_price", "expression": "unit_price"},
                {"name": "status", "expression": "status"},
                {"name": "order_date", "expression": "order_date"},
                {"name": "category", "expression": "category"},
                {"name": "cost_price", "expression": "cost_price"},
                {"name": "tier", "expression": "tier"},
                {"name": "region", "expression": "region"},
                {"name": "discount_pct", "expression": "COALESCE(discounts.discount_pct, 0.0)"},
            ]}],
        },
    }


def _map_calculate_lazy():
    """Map component: compute financial columns."""
    return {
        "id": "map_calculate",
        "type": "map",
        "config": {
            "outputs": [{"name": "main", "columns": [
                {"name": "order_id", "expression": "order_id"},
                {"name": "customer_id", "expression": "customer_id"},
                {"name": "product_id", "expression": "product_id"},
                {"name": "discount_code", "expression": "discount_code"},
                {"name": "quantity", "expression": "quantity"},
                {"name": "unit_price", "expression": "unit_price"},
                {"name": "status", "expression": "status"},
                {"name": "order_date", "expression": "order_date"},
                {"name": "category", "expression": "category"},
                {"name": "cost_price", "expression": "cost_price"},
                {"name": "tier", "expression": "tier"},
                {"name": "region", "expression": "region"},
                {"name": "discount_pct", "expression": "discount_pct"},
                {"name": "line_total", "expression": "quantity * unit_price"},
                {"name": "discount_amount", "expression": "quantity * unit_price * discount_pct"},
                {"name": "net_total", "expression": "quantity * unit_price - quantity * unit_price * discount_pct"},
                {"name": "tax", "expression": "(quantity * unit_price - quantity * unit_price * discount_pct) * 0.08"},
                {"name": "gross_total", "expression": "(quantity * unit_price - quantity * unit_price * discount_pct) * 1.08"},
                {"name": "profit_margin", "expression": "(quantity * unit_price - quantity * unit_price * discount_pct) - quantity * cost_price"},
            ]}],
        },
    }


def _map_calculate_python():
    """python_code: compute financial columns."""
    return {
        "id": "map_calculate",
        "type": "python_code",
        "config": {
            "code": (
                "line_total = pl.col('quantity') * pl.col('unit_price')\n"
                "discount_amount = line_total * pl.col('discount_pct')\n"
                "net_total = line_total - discount_amount\n"
                "tax = net_total * 0.08\n"
                "gross_total = net_total * 1.08\n"
                "profit_margin = net_total - pl.col('quantity') * pl.col('cost_price')\n"
                "output_df = input_df.with_columns([\n"
                "    line_total.alias('line_total'),\n"
                "    discount_amount.alias('discount_amount'),\n"
                "    net_total.alias('net_total'),\n"
                "    tax.alias('tax'),\n"
                "    gross_total.alias('gross_total'),\n"
                "    profit_margin.alias('profit_margin'),\n"
                "])"
            ),
        },
    }


def _filter_validate_lazy():
    return {
        "id": "filter_validate",
        "type": "filter",
        "config": {"condition": "profit_margin >= 0 && quantity <= 1000"},
    }


def _filter_validate_python():
    return {
        "id": "filter_validate",
        "type": "python_code",
        "config": {
            "code": "output_df = input_df.filter((pl.col('profit_margin') >= 0) & (pl.col('quantity') <= 1000))",
        },
    }


def _aggregate_summary_lazy():
    return {
        "id": "aggregate_summary",
        "type": "aggregate",
        "config": {
            "group_by": ["region", "category"],
            "aggregations": [
                {"name": "total_revenue", "function": "sum", "column": "gross_total"},
                {"name": "order_count", "function": "count", "column": "order_id"},
                {"name": "avg_order_value", "function": "avg", "column": "gross_total"},
                {"name": "total_profit", "function": "sum", "column": "profit_margin"},
                {"name": "avg_discount", "function": "avg", "column": "discount_amount"},
            ],
        },
    }


def _aggregate_summary_python():
    return {
        "id": "aggregate_summary",
        "type": "python_code",
        "config": {
            "code": (
                "output_df = input_df.group_by(['region', 'category']).agg([\n"
                "    pl.col('gross_total').sum().alias('total_revenue'),\n"
                "    pl.col('order_id').count().alias('order_count'),\n"
                "    pl.col('gross_total').mean().alias('avg_order_value'),\n"
                "    pl.col('profit_margin').sum().alias('total_profit'),\n"
                "    pl.col('discount_amount').mean().alias('avg_discount'),\n"
                "])"
            ),
        },
    }


def _sort_revenue_lazy():
    return {
        "id": "sort_revenue",
        "type": "sort_row",
        "config": {"columns": [{"name": "total_revenue", "order": "desc"}]},
    }


def _sort_revenue_python():
    return {
        "id": "sort_revenue",
        "type": "python_code",
        "config": {
            "code": "output_df = input_df.sort('total_revenue', descending=True)",
        },
    }


def _select_final():
    return {
        "id": "select_final",
        "type": "filter_columns",
        "config": {
            "columns": [
                "region",
                "category",
                "total_revenue",
                "order_count",
                "avg_order_value",
                "total_profit",
                "avg_discount",
            ],
        },
    }


FLOWS = [
    {"source": "read_orders", "target": "map_cleanup"},
    {"source": "map_cleanup", "target": "filter_active"},
    {"source": "filter_active", "target": "map_product_enrich"},
    {"source": "read_products", "target": "map_product_enrich", "input": "products"},
    {"source": "map_product_enrich", "target": "map_customer_enrich"},
    {"source": "read_customers", "target": "map_customer_enrich", "input": "customers"},
    {"source": "map_customer_enrich", "target": "map_discount_enrich"},
    {"source": "read_discounts", "target": "map_discount_enrich", "input": "discounts"},
    {"source": "map_discount_enrich", "target": "map_calculate"},
    {"source": "map_calculate", "target": "filter_validate"},
    {"source": "filter_validate", "target": "aggregate_summary"},
    {"source": "aggregate_summary", "target": "sort_revenue"},
    {"source": "sort_revenue", "target": "select_final"},
    {"source": "select_final", "target": "write_output"},
]


def build_config(
    perf_data: Dict[str, Any],
    output_path: str,
    scenario: str,
) -> Dict[str, Any]:
    """Build a complete job config for a given scenario."""
    # File inputs are the same for all scenarios
    components: List[Dict] = [
        _file_input("read_orders", str(perf_data["orders"]), ORDERS_SCHEMA),
        _file_input("read_products", str(perf_data["products"]), PRODUCTS_SCHEMA),
        _file_input("read_customers", str(perf_data["customers"]), CUSTOMERS_SCHEMA),
        _file_input("read_discounts", str(perf_data["discounts"]), DISCOUNTS_SCHEMA),
    ]

    if scenario == "a":
        # All lazy
        components += [
            _map_cleanup_lazy(),
            _filter_active_lazy(),
            _map_product_enrich(),
            _map_customer_enrich(),
            _map_discount_enrich(),
            _map_calculate_lazy(),
            _filter_validate_lazy(),
            _aggregate_summary_lazy(),
            _sort_revenue_lazy(),
            _select_final(),
        ]
    elif scenario == "b":
        # 3 barriers (python_code): filter_active, map_calculate, filter_validate
        components += [
            _map_cleanup_lazy(),
            _filter_active_python(),
            _map_product_enrich(),
            _map_customer_enrich(),
            _map_discount_enrich(),
            _map_calculate_python(),
            _filter_validate_python(),
            _aggregate_summary_lazy(),
            _sort_revenue_lazy(),
            _select_final(),
        ]
    elif scenario == "c":
        # 6 barriers: all of B + map_cleanup, aggregate_summary, sort_revenue
        components += [
            _map_cleanup_python(),
            _filter_active_python(),
            _map_product_enrich(),
            _map_customer_enrich(),
            _map_discount_enrich(),
            _map_calculate_python(),
            _filter_validate_python(),
            _aggregate_summary_python(),
            _sort_revenue_python(),
            _select_final(),
        ]
    else:
        raise ValueError(f"Unknown scenario: {scenario}")

    components.append(_file_output("write_output", output_path))

    return {
        "name": f"perf_barrier_scenario_{scenario}",
        "version": "2.0",
        "components": components,
        "flows": FLOWS,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def _print_report(
    scenario_name: str,
    result: Dict[str, Any],
    rss_before: float,
    rss_after: float,
    tracemalloc_peak_mb: float,
) -> None:
    print(f"\n{'=' * 78}")
    print(f"  SCENARIO {scenario_name}")
    print(f"{'=' * 78}")
    print(f"  Status         : {result['status']}")
    print(f"  Total time     : {result['duration_ms']:.1f} ms")
    print(f"  Peak RSS delta : {rss_after - rss_before:.1f} MB")
    print(f"  tracemalloc    : {tracemalloc_peak_mb:.1f} MB")
    print(f"  {'─' * 74}")
    print(f"  {'Component':<28} {'Time (ms)':>10} {'Barrier':>8} {'Rows out':>12}")
    print(f"  {'─' * 74}")

    comp_stats = result.get("components", {})
    for comp_id, stats in comp_stats.items():
        duration = stats.get("duration_ms", 0)
        barrier = "YES" if stats.get("barrier", False) else "no"
        rows = stats.get("rows_out", {})
        rows_str = str(rows.get("main", "")) if rows else ""
        print(f"  {comp_id:<28} {duration:>10.1f} {barrier:>8} {rows_str:>12}")

    print(f"  {'─' * 74}\n")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def perf_data(tmp_path_factory):
    base_dir = tmp_path_factory.mktemp("perf_data")
    scale = int(os.environ.get("PERF_SCALE", str(SCALE)))
    print(f"\n  Generating test data: scale={scale:,} ...")
    return DataGenerator.generate(base_dir, scale=scale)


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------
@pytest.mark.slow
class TestBarrierPerformanceScenarios:
    """Compare barrier placement strategies for the V2 engine."""

    def _run_scenario(
        self,
        scenario_name: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run a scenario with memory + timing instrumentation."""
        rss_before = get_peak_memory_mb()
        tracemalloc.start()

        engine = PyETLEngine(config)
        result = engine.execute()

        _, tracemalloc_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        tracemalloc_peak_mb = tracemalloc_peak / (1024 * 1024)
        rss_after = get_peak_memory_mb()

        _print_report(scenario_name, result, rss_before, rss_after, tracemalloc_peak_mb)
        return result

    # ---- Scenario A: fully lazy (1 barrier -- the sink) -------------------

    def test_scenario_a_max_laziness(self, perf_data, tmp_path):
        output_file = tmp_path / "result_a.csv"
        config = build_config(perf_data, str(output_file), "a")
        result = self._run_scenario("A -- Max Laziness (1 barrier: sink)", config)

        assert result["status"] == "success", f"Scenario A failed: {result.get('error', '')}"
        assert len(result["components"]) == 15

        # Only the sink should be a barrier
        barriers = [
            cid for cid, s in result["components"].items() if s.get("barrier")
        ]
        assert "write_output" in barriers
        assert output_file.exists()

    # ---- Scenario B: moderate barriers (3 + sink) -------------------------

    def test_scenario_b_moderate_barriers(self, perf_data, tmp_path):
        output_file = tmp_path / "result_b.csv"
        config = build_config(perf_data, str(output_file), "b")
        result = self._run_scenario("B -- Moderate Barriers (3 python_code + sink)", config)

        assert result["status"] == "success", f"Scenario B failed: {result.get('error', '')}"
        assert len(result["components"]) == 15

        barriers = [
            cid for cid, s in result["components"].items() if s.get("barrier")
        ]
        for expected in ("filter_active", "map_calculate", "filter_validate", "write_output"):
            assert expected in barriers, f"{expected} should be a barrier in scenario B"
        assert output_file.exists()

    # ---- Scenario C: max barriers (6 + sink) ------------------------------

    def test_scenario_c_max_barriers(self, perf_data, tmp_path):
        output_file = tmp_path / "result_c.csv"
        config = build_config(perf_data, str(output_file), "c")
        result = self._run_scenario("C -- Max Barriers (6 python_code + sink)", config)

        assert result["status"] == "success", f"Scenario C failed: {result.get('error', '')}"
        assert len(result["components"]) == 15

        barriers = [
            cid for cid, s in result["components"].items() if s.get("barrier")
        ]
        for expected in (
            "map_cleanup", "filter_active", "map_calculate",
            "filter_validate", "aggregate_summary", "sort_revenue", "write_output",
        ):
            assert expected in barriers, f"{expected} should be a barrier in scenario C"
        assert output_file.exists()

    # ---- Output equivalence -----------------------------------------------

    def test_output_equivalence(self, perf_data, tmp_path):
        """All 3 scenarios must produce the same aggregated output."""
        results = {}
        dfs = {}
        for scenario in ("a", "b", "c"):
            output_file = tmp_path / f"result_{scenario}.csv"
            config = build_config(perf_data, str(output_file), scenario)
            result = self._run_scenario(f"Equivalence-{scenario.upper()}", config)
            assert result["status"] == "success", (
                f"Scenario {scenario} failed: {result.get('error', '')}"
            )
            results[scenario] = result

            df = pl.read_csv(output_file)
            # Sort deterministically for comparison
            df = df.sort(["region", "category"])
            dfs[scenario] = df

        # Compare B and C against A (the reference)
        ref = dfs["a"]
        for other_key in ("b", "c"):
            other = dfs[other_key]
            assert ref.shape == other.shape, (
                f"Shape mismatch: A={ref.shape} vs {other_key.upper()}={other.shape}"
            )
            # Compare string columns exactly
            for col in ("region", "category"):
                assert ref[col].to_list() == other[col].to_list(), (
                    f"Column {col} differs between A and {other_key.upper()}"
                )
            # Compare numeric columns with tolerance
            for col in ("total_revenue", "order_count", "avg_order_value", "total_profit", "avg_discount"):
                ref_vals = ref[col].to_list()
                other_vals = other[col].to_list()
                assert ref_vals == pytest.approx(other_vals, rel=1e-6), (
                    f"Column {col} differs between A and {other_key.upper()}"
                )
