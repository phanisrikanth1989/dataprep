"""Config parsing + validation for the new Map component."""
import copy
import pytest

from src.v1.engine.components.transform.map.map_config import (
    MapConfig,
    parse_config,
    validate_config,
)
from src.v1.engine.exceptions import ConfigurationError


SAMPLE_CONFIG = {
    "component_type": "Map",
    "inputs": {
        "main": {
            "name": "row1",
            "filter": "",
            "activate_filter": False,
            "matching_mode": "UNIQUE_MATCH",
            "lookup_mode": "LOAD_ONCE",
        },
        "lookups": [{
            "name": "row2",
            "matching_mode": "UNIQUE_MATCH",
            "lookup_mode": "LOAD_ONCE",
            "filter": "",
            "activate_filter": False,
            "join_keys": [{
                "lookup_column": "key",
                "expression": "{{java}}row1.key",
                "type": "str",
                "nullable": True,
                "operator": "=",
            }],
            "join_mode": "LEFT_OUTER_JOIN",
        }],
    },
    "variables": [],
    "outputs": [{
        "name": "out_main",
        "is_reject": False,
        "inner_join_reject": False,
        "catch_output_reject": False,
        "filter": "",
        "activate_filter": False,
        "columns": [
            {"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True},
        ],
    }],
    "die_on_error": True,
    "enable_auto_convert_type": False,
}


# === parse_config tests (Task 2.1) ===

def test_parse_config_basic():
    cfg = parse_config(SAMPLE_CONFIG)
    assert isinstance(cfg, MapConfig)
    assert cfg.main.name == "row1"
    assert len(cfg.lookups) == 1
    assert cfg.lookups[0].name == "row2"
    assert cfg.lookups[0].join_keys[0].expression == "{{java}}row1.key"
    assert cfg.lookups[0].join_mode == "LEFT_OUTER_JOIN"
    assert cfg.die_on_error is True
    assert len(cfg.outputs) == 1
    assert cfg.outputs[0].columns[0].type == "int"


def test_parse_config_preserves_die_on_error_false():
    raw = {**SAMPLE_CONFIG, "die_on_error": False}
    cfg = parse_config(raw)
    assert cfg.die_on_error is False


# === validate_config tests (Task 2.2) ===

def test_validate_missing_main_name_raises():
    raw = {**SAMPLE_CONFIG}
    raw["inputs"] = {**raw["inputs"], "main": {**raw["inputs"]["main"], "name": ""}}
    cfg = parse_config(raw)
    with pytest.raises(ConfigurationError, match="inputs.main.name"):
        validate_config(cfg, java_bridge_available=True)


def test_validate_no_outputs_raises():
    raw = {**SAMPLE_CONFIG, "outputs": []}
    cfg = parse_config(raw)
    with pytest.raises(ConfigurationError, match="At least one output"):
        validate_config(cfg, java_bridge_available=True)


def test_validate_output_no_columns_raises():
    raw = {**SAMPLE_CONFIG}
    raw["outputs"] = [{**raw["outputs"][0], "columns": []}]
    cfg = parse_config(raw)
    with pytest.raises(ConfigurationError, match="no columns"):
        validate_config(cfg, java_bridge_available=True)


def test_validate_lookup_missing_lookup_column_raises():
    raw = copy.deepcopy(SAMPLE_CONFIG)
    raw["inputs"]["lookups"][0]["join_keys"][0]["lookup_column"] = ""
    cfg = parse_config(raw)
    with pytest.raises(ConfigurationError, match="lookup_column"):
        validate_config(cfg, java_bridge_available=True)


def test_validate_java_marker_without_bridge_raises():
    cfg = parse_config(SAMPLE_CONFIG)
    with pytest.raises(ConfigurationError, match="Java bridge is unavailable"):
        validate_config(cfg, java_bridge_available=False)


def test_validate_no_marker_no_bridge_passes():
    """All expressions stripped of {{java}}; should pass without bridge."""
    raw = {
        **SAMPLE_CONFIG,
        "outputs": [{
            **SAMPLE_CONFIG["outputs"][0],
            "columns": [{"name": "id", "expression": "1", "type": "int", "nullable": True}],
        }],
        "inputs": {
            **SAMPLE_CONFIG["inputs"],
            "lookups": [{
                **SAMPLE_CONFIG["inputs"]["lookups"][0],
                "join_keys": [{
                    **SAMPLE_CONFIG["inputs"]["lookups"][0]["join_keys"][0],
                    "expression": "row1.key",  # no {{java}} prefix
                }],
            }],
        },
    }
    cfg = parse_config(raw)
    validate_config(cfg, java_bridge_available=False)  # must not raise


# === coverage-fill (Task 11.1) ===

def test_validate_output_missing_name_raises():
    raw = copy.deepcopy(SAMPLE_CONFIG)
    raw["outputs"][0]["name"] = ""
    cfg = parse_config(raw)
    with pytest.raises(ConfigurationError, match=r"Output \[0\] missing 'name'"):
        validate_config(cfg, java_bridge_available=True)


def test_validate_lookup_missing_name_raises():
    raw = copy.deepcopy(SAMPLE_CONFIG)
    raw["inputs"]["lookups"][0]["name"] = ""
    cfg = parse_config(raw)
    with pytest.raises(ConfigurationError, match=r"Lookup \[0\] missing 'name'"):
        validate_config(cfg, java_bridge_available=True)


def test_validate_lookup_missing_join_key_expression_raises():
    raw = copy.deepcopy(SAMPLE_CONFIG)
    raw["inputs"]["lookups"][0]["join_keys"][0]["expression"] = ""
    cfg = parse_config(raw)
    with pytest.raises(ConfigurationError, match="missing 'expression'"):
        validate_config(cfg, java_bridge_available=True)
