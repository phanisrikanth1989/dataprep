"""Tests for the main V1ToV2Converter."""
import pytest
from src.converters.v1_to_v2.converter import V1ToV2Converter


class TestTopLevelMapping:
    def test_job_name_renamed(self):
        v1 = {"job_name": "my_pipeline", "components": [], "flows": []}
        result = V1ToV2Converter(v1).convert()
        assert result["name"] == "my_pipeline"
        assert "job_name" not in result

    def test_version_always_2(self):
        v1 = {"job_name": "x", "components": [], "flows": []}
        result = V1ToV2Converter(v1).convert()
        assert result["version"] == "2.0"

    def test_metadata_present(self):
        v1 = {"job_name": "x", "components": [], "flows": []}
        result = V1ToV2Converter(v1).convert()
        meta = result["_conversion_metadata"]
        assert meta["source_version"] == "v1"
        assert "converted_at" in meta


class TestContextConversion:
    def test_default_context_set(self):
        v1 = {
            "job_name": "x",
            "components": [],
            "flows": [],
            "context": {
                "Default": {
                    "tax_rate": {"value": 0.08, "type": "id_Double"},
                    "name": {"value": "ACME", "type": "id_String"},
                }
            },
        }
        result = V1ToV2Converter(v1).convert()
        ctx = result["context"]
        assert ctx["tax_rate"] == {"value": 0.08, "type": "float"}
        assert ctx["name"] == {"value": "ACME", "type": "str"}

    def test_explicit_default_context(self):
        v1 = {
            "job_name": "x",
            "components": [],
            "flows": [],
            "default_context": "Production",
            "context": {
                "Default": {"a": {"value": 1, "type": "id_Integer"}},
                "Production": {"b": {"value": 2, "type": "id_Integer"}},
            },
        }
        result = V1ToV2Converter(v1).convert()
        assert "b" in result["context"]
        assert "a" not in result["context"]

    def test_date_context_variable(self):
        v1 = {
            "job_name": "x",
            "components": [],
            "flows": [],
            "context": {
                "Default": {
                    "start": {"value": "2026-01-01", "type": "id_Date"},
                }
            },
        }
        result = V1ToV2Converter(v1).convert()
        assert result["context"]["start"]["type"] == "date"

    def test_boolean_type(self):
        v1 = {
            "job_name": "x",
            "components": [],
            "flows": [],
            "context": {
                "Default": {
                    "flag": {"value": "true", "type": "id_Boolean"},
                }
            },
        }
        result = V1ToV2Converter(v1).convert()
        assert result["context"]["flag"]["type"] == "bool"

    def test_bigdecimal_to_str(self):
        v1 = {
            "job_name": "x",
            "components": [],
            "flows": [],
            "context": {
                "Default": {
                    "price": {"value": "123.45", "type": "id_BigDecimal"},
                }
            },
        }
        result = V1ToV2Converter(v1).convert()
        assert result["context"]["price"]["type"] == "str"

    def test_empty_context(self):
        v1 = {"job_name": "x", "components": [], "flows": []}
        result = V1ToV2Converter(v1).convert()
        assert result["context"] == {}


class TestFlowConversion:
    def test_regular_flow(self):
        v1 = {
            "job_name": "x",
            "components": [],
            "flows": [
                {"from": "read", "to": "transform", "name": "data", "type": "flow"}
            ],
        }
        result = V1ToV2Converter(v1).convert()
        flow = result["flows"][0]
        assert flow["source"] == "read"
        assert flow["target"] == "transform"
        assert "output" not in flow
        assert "name" not in flow

    def test_reject_flow(self):
        v1 = {
            "job_name": "x",
            "components": [],
            "flows": [
                {"from": "filter", "to": "errors", "name": "bad", "type": "reject"}
            ],
        }
        result = V1ToV2Converter(v1).convert()
        flow = result["flows"][0]
        assert flow["source"] == "filter"
        assert flow["target"] == "errors"
        assert flow["output"] == "reject"

    def test_filter_flow(self):
        v1 = {
            "job_name": "x",
            "components": [],
            "flows": [
                {"from": "filt", "to": "sink", "name": "unmatched", "type": "filter"}
            ],
        }
        result = V1ToV2Converter(v1).convert()
        assert result["flows"][0]["output"] == "unmatched"

    def test_iterate_flow_warned(self):
        v1 = {
            "job_name": "x",
            "components": [],
            "flows": [
                {"from": "iter", "to": "proc", "name": "loop", "type": "iterate"}
            ],
        }
        result = V1ToV2Converter(v1).convert()
        flow = result["flows"][0]
        assert flow.get("_unsupported") is True
        warnings = result["_conversion_metadata"]["warnings"]
        assert any("iterate" in w.lower() for w in warnings)


class TestTriggerWarnings:
    def test_triggers_generate_warnings(self):
        v1 = {
            "job_name": "x",
            "components": [],
            "flows": [],
            "triggers": [
                {"type": "OnSubjobOk", "from": "a", "to": "b"},
                {"type": "OnComponentError", "from": "c", "to": "d"},
            ],
        }
        result = V1ToV2Converter(v1).convert()
        warnings = result["_conversion_metadata"]["warnings"]
        assert any("trigger" in w.lower() and "OnSubjobOk" in w for w in warnings)
        assert any("OnComponentError" in w for w in warnings)


class TestJavaConfigWarning:
    def test_enabled_java_config_warned(self):
        v1 = {
            "job_name": "x",
            "components": [],
            "flows": [],
            "java_config": {"enabled": True, "routines": ["StringUtils"]},
        }
        result = V1ToV2Converter(v1).convert()
        warnings = result["_conversion_metadata"]["warnings"]
        assert any("java" in w.lower() for w in warnings)

    def test_disabled_java_config_no_warning(self):
        v1 = {
            "job_name": "x",
            "components": [],
            "flows": [],
            "java_config": {"enabled": False},
        }
        result = V1ToV2Converter(v1).convert()
        warnings = result["_conversion_metadata"]["warnings"]
        assert not any("java_config" in w.lower() for w in warnings)


class TestComponentConversion:
    def test_components_converted(self):
        v1 = {
            "job_name": "x",
            "components": [
                {
                    "id": "read",
                    "type": "tFileInputDelimited",
                    "config": {"filepath": "/data/f.csv"},
                }
            ],
            "flows": [],
        }
        result = V1ToV2Converter(v1).convert()
        assert len(result["components"]) == 1
        assert result["components"][0]["type"] == "file_input_delimited"

    def test_unsupported_component_in_metadata(self):
        v1 = {
            "job_name": "x",
            "components": [
                {"id": "jrow", "type": "tJavaRow", "config": {"java_code": "x"}},
            ],
            "flows": [],
        }
        result = V1ToV2Converter(v1).convert()
        meta = result["_conversion_metadata"]
        assert "jrow" in meta["components_needing_review"]

    def test_expression_review_in_metadata(self):
        v1 = {
            "job_name": "x",
            "components": [
                {
                    "id": "m",
                    "type": "tMap",
                    "config": {
                        "outputs": [
                            {
                                "name": "main",
                                "columns": [
                                    {
                                        "name": "x",
                                        "expression": "{{java}} input.get('x')",
                                    }
                                ],
                            }
                        ]
                    },
                }
            ],
            "flows": [],
        }
        result = V1ToV2Converter(v1).convert()
        meta = result["_conversion_metadata"]
        assert len(meta["expressions_needing_review"]) >= 1


class TestFullPipeline:
    """End-to-end conversion of a realistic V1 config."""

    def test_full_pipeline(self):
        v1 = {
            "job_name": "order_processing",
            "context": {
                "Default": {
                    "input_path": {"value": "/data/orders.csv", "type": "id_String"},
                    "output_path": {"value": "/data/out.csv", "type": "id_String"},
                    "tax_rate": {"value": 0.08, "type": "id_Double"},
                }
            },
            "components": [
                {
                    "id": "read",
                    "type": "tFileInputDelimited",
                    "config": {"filepath": "${context.input_path}", "delimiter": ","},
                    "schema": {
                        "output": [
                            {"name": "id", "type": "id_Integer"},
                            {"name": "amount", "type": "id_Double"},
                            {"name": "status", "type": "id_String"},
                        ]
                    },
                },
                {
                    "id": "filter",
                    "type": "tFilterRows",
                    "config": {
                        "conditions": [
                            {"column": "status", "operator": "==", "value": "ACTIVE"}
                        ]
                    },
                },
                {
                    "id": "agg",
                    "type": "tAggregateRow",
                    "config": {
                        "group_by": ["status"],
                        "operations": [
                            {"input_column": "amount", "output_column": "total", "function": "sum"}
                        ],
                    },
                },
                {
                    "id": "write",
                    "type": "tFileOutputDelimited",
                    "config": {"filepath": "${context.output_path}", "include_header": True},
                },
            ],
            "flows": [
                {"from": "read", "to": "filter", "name": "raw", "type": "flow"},
                {"from": "filter", "to": "agg", "name": "active", "type": "flow"},
                {"from": "agg", "to": "write", "name": "summary", "type": "flow"},
            ],
            "triggers": [
                {"type": "OnSubjobOk", "from": "read", "to": "filter"},
            ],
        }
        result = V1ToV2Converter(v1).convert()

        # Top level
        assert result["name"] == "order_processing"
        assert result["version"] == "2.0"

        # Context
        assert result["context"]["tax_rate"]["type"] == "float"

        # Components
        assert len(result["components"]) == 4
        types = [c["type"] for c in result["components"]]
        assert types == ["file_input_delimited", "filter", "aggregate", "file_output_delimited"]

        # Flows
        assert len(result["flows"]) == 3
        assert result["flows"][0]["source"] == "read"
        assert result["flows"][0]["target"] == "filter"

        # Warnings (trigger)
        assert len(result["_conversion_metadata"]["warnings"]) >= 1
