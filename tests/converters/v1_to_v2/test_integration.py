"""Integration tests -- convert realistic V1 configs and validate V2 output."""
import pytest
from src.converters.v1_to_v2.converter import V1ToV2Converter
from src.v2.config import JobConfig


class TestRealisticPipeline:
    """Convert a realistic multi-component V1 pipeline."""

    @pytest.fixture
    def v1_config(self):
        return {
            "job_name": "customer_order_report",
            "default_context": "Default",
            "context": {
                "Default": {
                    "input_dir": {"value": "/data/input", "type": "id_String"},
                    "output_dir": {"value": "/data/output", "type": "id_String"},
                    "tax_rate": {"value": 0.08, "type": "id_Double"},
                    "min_order": {"value": 100, "type": "id_Integer"},
                    "report_date": {"value": "2026-01-01", "type": "id_Date"},
                }
            },
            "java_config": {"enabled": True, "routines": ["StringUtils"]},
            "components": [
                {
                    "id": "read_orders",
                    "type": "tFileInputDelimited",
                    "config": {
                        "filepath": "${context.input_dir}/orders.csv",
                        "delimiter": ",",
                        "encoding": "UTF-8",
                        "header_rows": 1,
                    },
                    "schema": {
                        "output": [
                            {"name": "order_id", "type": "id_Integer"},
                            {"name": "customer_id", "type": "id_Integer"},
                            {"name": "amount", "type": "id_Double"},
                            {"name": "status", "type": "id_String"},
                            {"name": "order_date", "type": "id_Date", "date_pattern": "yyyy-MM-dd"},
                        ]
                    },
                },
                {
                    "id": "read_customers",
                    "type": "tFileInputDelimited",
                    "config": {
                        "filepath": "${context.input_dir}/customers.csv",
                        "delimiter": ",",
                        "header_rows": 1,
                    },
                    "schema": {
                        "output": [
                            {"name": "id", "type": "id_Integer"},
                            {"name": "name", "type": "id_String"},
                            {"name": "tier", "type": "id_String"},
                        ]
                    },
                },
                {
                    "id": "filter_active",
                    "type": "tFilterRows",
                    "config": {
                        "conditions": [
                            {"column": "status", "operator": "==", "value": "ACTIVE"},
                            {"column": "amount", "operator": ">=", "value": 100},
                        ],
                        "logical_operator": "AND",
                    },
                },
                {
                    "id": "enrich",
                    "type": "tMap",
                    "config": {
                        "inputs": {
                            "main": {"name": "orders"},
                            "lookups": [
                                {
                                    "name": "customers",
                                    "join_keys": [
                                        {"main_column": "customer_id", "lookup_column": "id"}
                                    ],
                                    "join_type": "LEFT",
                                }
                            ],
                        },
                        "variables": [
                            {"name": "total", "expression": "main.amount * (1 + context.tax_rate)"}
                        ],
                        "outputs": [
                            {
                                "name": "main",
                                "columns": [
                                    {"name": "order_id", "expression": "main.order_id"},
                                    {"name": "customer_name", "expression": "customers.name"},
                                    {"name": "amount", "expression": "main.amount"},
                                    {"name": "total", "expression": "var.total"},
                                    {"name": "tier", "expression": "customers.tier"},
                                ],
                            }
                        ],
                    },
                },
                {
                    "id": "aggregate",
                    "type": "tAggregateRow",
                    "config": {
                        "group_by": ["tier"],
                        "operations": [
                            {"input_column": "total", "output_column": "revenue", "function": "sum"},
                            {"input_column": "order_id", "output_column": "count", "function": "count"},
                        ],
                    },
                },
                {
                    "id": "sort_revenue",
                    "type": "tSortRow",
                    "config": {
                        "sort_keys": [{"column": "revenue", "ascending": False}]
                    },
                },
                {
                    "id": "write_report",
                    "type": "tFileOutputDelimited",
                    "config": {
                        "filepath": "${context.output_dir}/report.csv",
                        "delimiter": ",",
                        "include_header": True,
                    },
                },
                {
                    "id": "java_transform",
                    "type": "tJavaRow",
                    "config": {
                        "java_code": "output_row.set('upper_name', input_row.get('name').toUpperCase());"
                    },
                },
            ],
            "flows": [
                {"from": "read_orders", "to": "filter_active", "name": "raw", "type": "flow"},
                {"from": "read_customers", "to": "enrich", "name": "cust", "type": "flow"},
                {"from": "filter_active", "to": "enrich", "name": "filtered", "type": "flow"},
                {"from": "enrich", "to": "aggregate", "name": "enriched", "type": "flow"},
                {"from": "aggregate", "to": "sort_revenue", "name": "grouped", "type": "flow"},
                {"from": "sort_revenue", "to": "write_report", "name": "sorted", "type": "flow"},
            ],
            "triggers": [
                {"type": "OnSubjobOk", "from": "read_orders", "to": "filter_active"},
            ],
        }

    def test_converts_successfully(self, v1_config):
        result = V1ToV2Converter(v1_config).convert()
        assert result["name"] == "customer_order_report"
        assert result["version"] == "2.0"

    def test_context_types_correct(self, v1_config):
        result = V1ToV2Converter(v1_config).convert()
        ctx = result["context"]
        assert ctx["input_dir"]["type"] == "str"
        assert ctx["tax_rate"]["type"] == "float"
        assert ctx["min_order"]["type"] == "int"
        assert ctx["report_date"]["type"] == "date"

    def test_component_types_correct(self, v1_config):
        result = V1ToV2Converter(v1_config).convert()
        type_map = {c["id"]: c["type"] for c in result["components"]}
        assert type_map["read_orders"] == "file_input_delimited"
        assert type_map["read_customers"] == "file_input_delimited"
        assert type_map["filter_active"] == "filter"
        assert type_map["enrich"] == "map"
        assert type_map["aggregate"] == "aggregate"
        assert type_map["sort_revenue"] == "sort_row"
        assert type_map["write_report"] == "file_output_delimited"

    def test_java_component_flagged(self, v1_config):
        result = V1ToV2Converter(v1_config).convert()
        meta = result["_conversion_metadata"]
        assert "java_transform" in meta["components_needing_review"]

    def test_trigger_warned(self, v1_config):
        result = V1ToV2Converter(v1_config).convert()
        warnings = result["_conversion_metadata"]["warnings"]
        assert any("OnSubjobOk" in w for w in warnings)

    def test_java_config_warned(self, v1_config):
        result = V1ToV2Converter(v1_config).convert()
        warnings = result["_conversion_metadata"]["warnings"]
        assert any("java" in w.lower() and "StringUtils" in w for w in warnings)

    def test_schema_date_pattern_converted(self, v1_config):
        result = V1ToV2Converter(v1_config).convert()
        read_orders = next(c for c in result["components"] if c["id"] == "read_orders")
        date_col = next(
            s for s in read_orders["config"]["schema"] if s["name"] == "order_date"
        )
        assert date_col["type"] == "date"
        assert date_col["date_pattern"] == "%Y-%m-%d"

    def test_map_lookup_converted(self, v1_config):
        result = V1ToV2Converter(v1_config).convert()
        enrich = next(c for c in result["components"] if c["id"] == "enrich")
        lookups = enrich["config"]["lookups"]
        assert len(lookups) == 1
        assert lookups[0]["name"] == "customers"
        assert lookups[0]["keys"] == [{"main": "customer_id", "lookup": "id"}]
        assert lookups[0]["join_type"] == "left"

    def test_map_expressions_translated(self, v1_config):
        result = V1ToV2Converter(v1_config).convert()
        enrich = next(c for c in result["components"] if c["id"] == "enrich")
        cols = enrich["config"]["outputs"][0]["columns"]
        expr_map = {c["name"]: c["expression"] for c in cols}
        assert expr_map["order_id"] == "order_id"
        assert expr_map["customer_name"] == "customers.name"
        # var. prefix is preserved for V2 Map variable column references
        assert expr_map["total"] == "var.total"

    def test_map_variables_translated(self, v1_config):
        result = V1ToV2Converter(v1_config).convert()
        enrich = next(c for c in result["components"] if c["id"] == "enrich")
        variables = enrich["config"]["variables"]
        assert variables[0]["expression"] == "amount * (1 + context.tax_rate)"

    def test_v2_config_loads(self, v1_config):
        """The converted config should be loadable by V2 JobConfig
        after stripping metadata and unsupported components."""
        result = V1ToV2Converter(v1_config).convert()
        result.pop("_conversion_metadata", None)

        unsupported_ids = {
            c["id"]
            for c in result["components"]
            if c.get("config", {}).get("_unsupported")
        }
        result["components"] = [
            c for c in result["components"] if c["id"] not in unsupported_ids
        ]
        result["flows"] = [
            f
            for f in result["flows"]
            if f["source"] not in unsupported_ids and f["target"] not in unsupported_ids
        ]

        job_config = JobConfig(**result)
        assert job_config.name == "customer_order_report"
        assert len(job_config.components) == 7
