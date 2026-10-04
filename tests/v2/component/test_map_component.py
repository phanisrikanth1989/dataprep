"""
Tests for v2 Map component.

Tests cover:
- Basic column passthrough and expression transforms
- Context variable usage in expressions
- Variable computation (including chaining)
- Lookup joins (left, inner, cross, match modes)
- Multi-output with filters
- Validation
- Registry registration
"""
import pytest
import polars as pl

from src.v2.components.transform.map_component import Map


class TestMapBasic:
    def test_simple_column_passthrough(self):
        comp = Map("m", {"outputs": [{"name": "main", "columns": [
            {"name": "id", "expression": "id"},
            {"name": "name", "expression": "name"},
        ]}]})
        df = pl.DataFrame({"id": [1, 2], "name": ["A", "B"]}).lazy()
        result = comp.apply({"main": df})
        assert "main" in result
        collected = result["main"].collect()
        assert collected["id"].to_list() == [1, 2]
        assert collected["name"].to_list() == ["A", "B"]

    def test_expression_transform(self):
        comp = Map("m", {"outputs": [{"name": "main", "columns": [
            {"name": "upper_name", "expression": "UPPER(name)"},
            {"name": "doubled", "expression": "amount * 2"},
        ]}]})
        df = pl.DataFrame({"name": ["alice"], "amount": [100]}).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect()
        assert collected["upper_name"][0] == "ALICE"
        assert collected["doubled"][0] == 200

    def test_context_in_expression(self):
        comp = Map("m", {"outputs": [{"name": "main", "columns": [
            {"name": "total", "expression": "amount * context.rate"},
        ]}]}, context={"rate": 0.08})
        df = pl.DataFrame({"amount": [100.0]}).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect()
        assert abs(collected["total"][0] - 8.0) < 0.01

    def test_no_main_input_returns_empty(self):
        comp = Map("m", {"outputs": [{"name": "main", "columns": []}]})
        result = comp.apply({})
        assert result == {}

    def test_dataframe_input_converted_to_lazy(self):
        comp = Map("m", {"outputs": [{"name": "main", "columns": [
            {"name": "id", "expression": "id"},
        ]}]})
        df = pl.DataFrame({"id": [1]})  # DataFrame not LazyFrame
        result = comp.apply({"main": df})
        assert isinstance(result["main"], pl.LazyFrame)

    def test_single_output_stays_lazy(self):
        comp = Map("m", {"outputs": [{"name": "main", "columns": [
            {"name": "id", "expression": "id"},
        ]}]})
        df = pl.DataFrame({"id": [1]}).lazy()
        result = comp.apply({"main": df})
        assert isinstance(result["main"], pl.LazyFrame)


class TestMapVariables:
    def test_variable_computation(self):
        comp = Map("m", {
            "variables": [
                {"name": "total", "expression": "qty * price"},
            ],
            "outputs": [{"name": "main", "columns": [
                {"name": "total", "expression": "var.total"},
            ]}],
        })
        df = pl.DataFrame({"qty": [5], "price": [10.0]}).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect()
        assert collected["total"][0] == 50.0

    def test_variable_chain(self):
        """Variables can reference earlier variables."""
        comp = Map("m", {
            "variables": [
                {"name": "subtotal", "expression": "qty * price"},
                {"name": "tax", "expression": "var.subtotal * 0.08"},
            ],
            "outputs": [{"name": "main", "columns": [
                {"name": "total", "expression": "var.subtotal + var.tax"},
            ]}],
        })
        df = pl.DataFrame({"qty": [10], "price": [100.0]}).lazy()
        result = comp.apply({"main": df})
        collected = result["main"].collect()
        assert abs(collected["total"][0] - 1080.0) < 0.01


class TestMapLookups:
    def test_left_join(self):
        comp = Map("m", {
            "lookups": [{
                "name": "customers",
                "keys": [{"main": "cust_id", "lookup": "id"}],
                "join_type": "left",
            }],
            "outputs": [{"name": "main", "columns": [
                {"name": "order_id", "expression": "order_id"},
                {"name": "cust_name", "expression": "customers.name"},
            ]}],
        })
        orders = pl.DataFrame({"order_id": [1, 2, 3], "cust_id": [10, 20, 30]}).lazy()
        customers = pl.DataFrame({"id": [10, 20], "name": ["Alice", "Bob"]}).lazy()
        result = comp.apply({"main": orders, "customers": customers})
        collected = result["main"].collect()
        assert len(collected) == 3
        assert collected["cust_name"][0] == "Alice"
        assert collected["cust_name"][2] is None

    def test_inner_join(self):
        comp = Map("m", {
            "lookups": [{
                "name": "customers",
                "keys": [{"main": "cust_id", "lookup": "id"}],
                "join_type": "inner",
            }],
            "outputs": [{"name": "main", "columns": [
                {"name": "order_id", "expression": "order_id"},
                {"name": "cust_name", "expression": "customers.name"},
            ]}],
        })
        orders = pl.DataFrame({"order_id": [1, 2, 3], "cust_id": [10, 20, 30]}).lazy()
        customers = pl.DataFrame({"id": [10, 20], "name": ["Alice", "Bob"]}).lazy()
        result = comp.apply({"main": orders, "customers": customers})
        collected = result["main"].collect()
        assert len(collected) == 2

    def test_cross_join(self):
        comp = Map("m", {
            "lookups": [{
                "name": "regions",
                "keys": [],
                "join_type": "cross",
            }],
            "outputs": [{"name": "main", "columns": [
                {"name": "product", "expression": "product"},
                {"name": "region", "expression": "regions.region"},
            ]}],
        })
        products = pl.DataFrame({"product": ["A", "B"]}).lazy()
        regions = pl.DataFrame({"region": ["US", "EU", "APAC"]}).lazy()
        result = comp.apply({"main": products, "regions": regions})
        collected = result["main"].collect()
        assert len(collected) == 6

    def test_match_mode_first(self):
        comp = Map("m", {
            "lookups": [{
                "name": "prices",
                "keys": [{"main": "product", "lookup": "product"}],
                "join_type": "left",
                "match_mode": "first",
            }],
            "outputs": [{"name": "main", "columns": [
                {"name": "product", "expression": "product"},
                {"name": "price", "expression": "prices.price"},
            ]}],
        })
        orders = pl.DataFrame({"product": ["A"]}).lazy()
        prices = pl.DataFrame({"product": ["A", "A"], "price": [10, 20]}).lazy()
        result = comp.apply({"main": orders, "prices": prices})
        collected = result["main"].collect()
        assert len(collected) == 1
        assert collected["price"][0] == 10

    def test_match_mode_last(self):
        comp = Map("m", {
            "lookups": [{
                "name": "prices",
                "keys": [{"main": "product", "lookup": "product"}],
                "join_type": "left",
                "match_mode": "last",
            }],
            "outputs": [{"name": "main", "columns": [
                {"name": "product", "expression": "product"},
                {"name": "price", "expression": "prices.price"},
            ]}],
        })
        orders = pl.DataFrame({"product": ["A"]}).lazy()
        prices = pl.DataFrame({"product": ["A", "A"], "price": [10, 20]}).lazy()
        result = comp.apply({"main": orders, "prices": prices})
        collected = result["main"].collect()
        assert len(collected) == 1
        assert collected["price"][0] == 20

    def test_match_mode_unique(self):
        """Unique match mode behaves like last (Talend's default)."""
        comp = Map("m", {
            "lookups": [{
                "name": "prices",
                "keys": [{"main": "product", "lookup": "product"}],
                "join_type": "left",
                "match_mode": "unique",
            }],
            "outputs": [{"name": "main", "columns": [
                {"name": "product", "expression": "product"},
                {"name": "price", "expression": "prices.price"},
            ]}],
        })
        orders = pl.DataFrame({"product": ["A"]}).lazy()
        prices = pl.DataFrame({"product": ["A", "A"], "price": [10, 20]}).lazy()
        result = comp.apply({"main": orders, "prices": prices})
        collected = result["main"].collect()
        assert len(collected) == 1
        assert collected["price"][0] == 20

    def test_join_type_outer(self):
        """Full outer join keeps all rows from both sides."""
        comp = Map("m", {
            "lookups": [{
                "name": "customers",
                "keys": [{"main": "cust_id", "lookup": "id"}],
                "join_type": "outer",
            }],
            "outputs": [{"name": "main", "columns": []}],
        })
        orders = pl.DataFrame({"cust_id": [1, 2], "amount": [100, 200]}).lazy()
        customers = pl.DataFrame({"id": [2, 3], "name": ["Bob", "Charlie"]}).lazy()
        result = comp.apply({"main": orders, "customers": customers})
        collected = result["main"].collect()
        assert len(collected) == 3  # order1 no-match, order2+Bob, Charlie no-match

    def test_join_type_right(self):
        """Right join keeps all lookup rows."""
        comp = Map("m", {
            "lookups": [{
                "name": "customers",
                "keys": [{"main": "cust_id", "lookup": "id"}],
                "join_type": "right",
            }],
            "outputs": [{"name": "main", "columns": []}],
        })
        orders = pl.DataFrame({"cust_id": [1, 2], "amount": [100, 200]}).lazy()
        customers = pl.DataFrame({"id": [2, 3], "name": ["Bob", "Charlie"]}).lazy()
        result = comp.apply({"main": orders, "customers": customers})
        collected = result["main"].collect()
        assert len(collected) == 2  # order2+Bob, Charlie no-match on main

    def test_lookup_input_differs_from_name(self):
        """The 'input' key overrides 'name' for data lookup."""
        comp = Map("m", {
            "lookups": [{
                "name": "customers",
                "input": "cust_data",
                "keys": [{"main": "cust_id", "lookup": "id"}],
                "join_type": "left",
            }],
            "outputs": [{"name": "main", "columns": [
                {"name": "cust_name", "expression": "customers.name"},
            ]}],
        })
        orders = pl.DataFrame({"cust_id": [1]}).lazy()
        custs = pl.DataFrame({"id": [1], "name": ["Alice"]}).lazy()
        result = comp.apply({"main": orders, "cust_data": custs})
        collected = result["main"].collect()
        assert collected["cust_name"][0] == "Alice"

    def test_multiple_lookups(self):
        comp = Map("m", {
            "lookups": [
                {"name": "customers", "keys": [{"main": "cid", "lookup": "id"}], "join_type": "left"},
                {"name": "products", "keys": [{"main": "pid", "lookup": "id"}], "join_type": "left"},
            ],
            "outputs": [{"name": "main", "columns": [
                {"name": "cust", "expression": "customers.name"},
                {"name": "prod", "expression": "products.name"},
            ]}],
        })
        main = pl.DataFrame({"cid": [1], "pid": [2]}).lazy()
        custs = pl.DataFrame({"id": [1], "name": ["Alice"]}).lazy()
        prods = pl.DataFrame({"id": [2], "name": ["Widget"]}).lazy()
        result = comp.apply({"main": main, "customers": custs, "products": prods})
        collected = result["main"].collect()
        assert collected["cust"][0] == "Alice"
        assert collected["prod"][0] == "Widget"


class TestMapMultiOutput:
    def test_filtered_outputs(self):
        comp = Map("m", {
            "outputs": [
                {"name": "high", "filter": "amount > 100", "columns": [
                    {"name": "id", "expression": "id"},
                ]},
                {"name": "low", "filter": "amount <= 100", "columns": [
                    {"name": "id", "expression": "id"},
                ]},
            ],
        })
        df = pl.DataFrame({"id": [1, 2, 3], "amount": [50, 150, 200]}).lazy()
        result = comp.apply({"main": df})
        assert "high" in result
        assert "low" in result
        high = result["high"].collect()
        low = result["low"].collect()
        assert len(high) == 2
        assert len(low) == 1

    def test_single_output_returns_lazy(self):
        comp = Map("m", {"outputs": [{"name": "main", "columns": [
            {"name": "id", "expression": "id"},
        ]}]})
        df = pl.DataFrame({"id": [1]}).lazy()
        result = comp.apply({"main": df})
        assert isinstance(result["main"], pl.LazyFrame)


class TestMapValidation:
    def test_missing_outputs(self):
        comp = Map("m", {})
        errors = comp.validate()
        assert any("output" in e.lower() for e in errors)

    def test_output_missing_name(self):
        comp = Map("m", {"outputs": [{"columns": []}]})
        errors = comp.validate()
        assert any("name" in e.lower() for e in errors)

    def test_output_missing_columns(self):
        comp = Map("m", {"outputs": [{"name": "main"}]})
        errors = comp.validate()
        assert any("columns" in e.lower() for e in errors)

    def test_valid_config(self):
        comp = Map("m", {"outputs": [{"name": "main", "columns": [
            {"name": "id", "expression": "id"}
        ]}]})
        errors = comp.validate()
        assert errors == []


class TestMapLookupReject:
    def test_inner_join_reject_routed(self):
        """Rows that fail inner join are routed to lookup_reject_output."""
        comp = Map("m", {
            "lookups": [{
                "name": "customers",
                "keys": [{"main": "cust_id", "lookup": "id"}],
                "join_type": "inner",
            }],
            "lookup_reject_output": "bad_lookups",
            "outputs": [
                {"name": "main", "columns": [
                    {"name": "order_id", "expression": "order_id"},
                    {"name": "cust_name", "expression": "customers.name"},
                ]},
                {"name": "bad_lookups", "columns": [
                    {"name": "order_id", "expression": "order_id"},
                    {"name": "cust_id", "expression": "cust_id"},
                ]},
            ],
        })
        orders = pl.DataFrame({"order_id": [1, 2, 3], "cust_id": [10, 20, 30]}).lazy()
        customers = pl.DataFrame({"id": [10, 20], "name": ["Alice", "Bob"]}).lazy()
        result = comp.apply({"main": orders, "customers": customers})

        main = result["main"].collect()
        assert len(main) == 2
        assert main["order_id"].to_list() == [1, 2]

        rejects = result["bad_lookups"].collect()
        assert len(rejects) == 1
        assert rejects["order_id"][0] == 3

    def test_left_join_no_reject(self):
        """Left join does not produce lookup rejects."""
        comp = Map("m", {
            "lookups": [{
                "name": "customers",
                "keys": [{"main": "cust_id", "lookup": "id"}],
                "join_type": "left",
            }],
            "lookup_reject_output": "bad_lookups",
            "outputs": [
                {"name": "main", "columns": []},
                {"name": "bad_lookups", "columns": []},
            ],
        })
        orders = pl.DataFrame({"cust_id": [10, 20, 30]}).lazy()
        customers = pl.DataFrame({"id": [10]}).lazy()
        result = comp.apply({"main": orders, "customers": customers})

        main = result["main"].collect()
        assert len(main) == 3  # all rows preserved

        rejects = result["bad_lookups"].collect()
        assert len(rejects) == 0

    def test_multiple_inner_join_rejects_combined(self):
        """Rejects from multiple inner-join lookups are combined."""
        comp = Map("m", {
            "lookups": [
                {"name": "custs", "keys": [{"main": "cid", "lookup": "id"}], "join_type": "inner"},
                {"name": "prods", "keys": [{"main": "pid", "lookup": "id"}], "join_type": "inner"},
            ],
            "lookup_reject_output": "rejects",
            "outputs": [
                {"name": "main", "columns": []},
                {"name": "rejects", "columns": []},
            ],
        })
        main = pl.DataFrame({"cid": [1, 2, 3], "pid": [10, 20, 30]}).lazy()
        custs = pl.DataFrame({"id": [1, 2, 3]}).lazy()
        prods = pl.DataFrame({"id": [10, 20]}).lazy()
        result = comp.apply({"main": main, "custs": custs, "prods": prods})

        # Row 3 survives custs inner join but fails prods inner join
        main_df = result["main"].collect()
        assert len(main_df) == 2

        rejects = result["rejects"].collect()
        assert len(rejects) == 1

    def test_validation_lookup_reject_output_exists(self):
        """Validation error if lookup_reject_output doesn't reference a defined output."""
        comp = Map("m", {
            "lookup_reject_output": "nonexistent",
            "outputs": [
                {"name": "main", "columns": []},
            ],
        })
        errors = comp.validate()
        assert any("lookup_reject_output" in e for e in errors)


class TestMapFilterReject:
    def test_filter_reject_routed(self):
        """Rows matching no output filter are routed to filter_reject_output."""
        comp = Map("m", {
            "filter_reject_output": "unmatched",
            "outputs": [
                {"name": "high", "filter": "amount > 100", "columns": [
                    {"name": "id", "expression": "id"},
                ]},
                {"name": "low", "filter": "amount <= 50", "columns": [
                    {"name": "id", "expression": "id"},
                ]},
                {"name": "unmatched", "columns": [
                    {"name": "id", "expression": "id"},
                    {"name": "amount", "expression": "amount"},
                ]},
            ],
        })
        df = pl.DataFrame({"id": [1, 2, 3, 4], "amount": [200, 75, 30, 150]}).lazy()
        result = comp.apply({"main": df})

        high = result["high"].collect()
        assert high["id"].to_list() == [1, 4]

        low = result["low"].collect()
        assert low["id"].to_list() == [3]

        unmatched = result["unmatched"].collect()
        assert unmatched["id"].to_list() == [2]  # 75: not > 100 and not <= 50

    def test_no_filters_no_reject(self):
        """When no outputs have filters, no filter rejects are produced."""
        comp = Map("m", {
            "filter_reject_output": "unmatched",
            "outputs": [
                {"name": "main", "columns": [{"name": "id", "expression": "id"}]},
                {"name": "unmatched", "columns": []},
            ],
        })
        df = pl.DataFrame({"id": [1, 2]}).lazy()
        result = comp.apply({"main": df})
        assert result["unmatched"].collect().height == 0

    def test_all_rows_matched_empty_reject(self):
        """When all rows match some filter, reject output is empty."""
        comp = Map("m", {
            "filter_reject_output": "unmatched",
            "outputs": [
                {"name": "positive", "filter": "amount > 0", "columns": [
                    {"name": "id", "expression": "id"},
                ]},
                {"name": "unmatched", "columns": []},
            ],
        })
        df = pl.DataFrame({"id": [1, 2], "amount": [100, 200]}).lazy()
        result = comp.apply({"main": df})
        assert result["unmatched"].collect().height == 0

    def test_validation_filter_reject_output_exists(self):
        """Validation error if filter_reject_output doesn't reference a defined output."""
        comp = Map("m", {
            "filter_reject_output": "nonexistent",
            "outputs": [
                {"name": "main", "columns": []},
            ],
        })
        errors = comp.validate()
        assert any("filter_reject_output" in e for e in errors)


class TestMapErrorReject:
    def test_error_reject_on_main(self):
        """die_on_error=false routes expression errors to error_reject_output."""
        comp = Map("m", {
            "die_on_error": False,
            "error_reject_output": "errors",
            "outputs": [
                {"name": "main", "columns": [
                    {"name": "id", "expression": "id"},
                    {"name": "amount", "expression": "TO_INTEGER(raw)"},
                ]},
                {"name": "errors", "columns": []},
            ],
        })
        df = pl.DataFrame({"id": [1, 2, 3], "raw": ["100", "bad", "300"]}).lazy()
        result = comp.apply({"main": df})

        main = result["main"].collect()
        assert len(main) == 2
        assert main["id"].to_list() == [1, 3]

        errors = result["errors"].collect()
        assert len(errors) == 1
        assert errors["id"][0] == 2
        assert "_error_message" in errors.columns

    def test_error_reject_on_non_main_output(self):
        """Reject works on any named output, not just main."""
        comp = Map("m", {
            "die_on_error": False,
            "error_reject_output": "errors",
            "outputs": [
                {"name": "converted", "columns": [
                    {"name": "id", "expression": "id"},
                    {"name": "amount", "expression": "TO_INTEGER(raw)"},
                ]},
                {"name": "errors", "columns": []},
            ],
        })
        df = pl.DataFrame({"id": [1, 2], "raw": ["100", "bad"]}).lazy()
        result = comp.apply({"main": df})

        converted = result["converted"].collect()
        assert len(converted) == 1

        errors = result["errors"].collect()
        assert len(errors) == 1

    def test_error_message_includes_column_name(self):
        """Error message includes the specific column that failed."""
        comp = Map("m", {
            "die_on_error": False,
            "error_reject_output": "errors",
            "outputs": [
                {"name": "main", "columns": [
                    {"name": "id", "expression": "id"},
                    {"name": "amount", "expression": "TO_INTEGER(raw)"},
                ]},
                {"name": "errors", "columns": []},
            ],
        })
        df = pl.DataFrame({"id": [1], "raw": ["bad"]}).lazy()
        result = comp.apply({"main": df})
        errors = result["errors"].collect()
        assert "amount" in errors["_error_message"][0]

    def test_no_error_reject_output_skips_routing(self):
        """Without error_reject_output, die_on_error=false still works but no reject output."""
        comp = Map("m", {
            "die_on_error": False,
            "outputs": [
                {"name": "main", "columns": [
                    {"name": "amount", "expression": "TO_INTEGER(raw)"},
                ]},
            ],
        })
        df = pl.DataFrame({"raw": ["100", "bad"]}).lazy()
        result = comp.apply({"main": df})
        # No error_reject_output, so no "reject"/"errors" key
        assert "reject" not in result
        # Main still contains all rows (nulls for failures)
        main = result["main"].collect()
        assert len(main) == 2

    def test_error_reject_aggregates_across_outputs(self):
        """Error rejects from multiple outputs with different schemas are combined."""
        comp = Map("m", {
            "die_on_error": False,
            "error_reject_output": "errors",
            "outputs": [
                {"name": "out_a", "columns": [
                    {"name": "id", "expression": "id"},
                    {"name": "amount", "expression": "TO_INTEGER(raw)"},
                ]},
                {"name": "out_b", "columns": [
                    {"name": "id", "expression": "id"},
                    {"name": "score", "expression": "TO_INTEGER(raw)"},
                ]},
                {"name": "errors", "columns": []},
            ],
        })
        df = pl.DataFrame({"id": [1, 2], "raw": ["100", "bad"]}).lazy()
        result = comp.apply({"main": df})

        # Row 2 fails in both out_a and out_b
        errors = result["errors"].collect()
        assert len(errors) == 2
        assert "_error_message" in errors.columns

    def test_validation_error_reject_output_exists(self):
        """Validation error if error_reject_output doesn't reference a defined output."""
        comp = Map("m", {
            "error_reject_output": "nonexistent",
            "outputs": [
                {"name": "main", "columns": []},
            ],
        })
        errors = comp.validate()
        assert any("error_reject_output" in e for e in errors)


class TestMapRegistry:
    def test_registered_as_map(self):
        from src.v2.components.registry import REGISTRY
        assert REGISTRY.get("map") is not None

