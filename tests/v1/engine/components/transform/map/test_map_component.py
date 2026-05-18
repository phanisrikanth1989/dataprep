"""Map component lifecycle + orchestration."""
import json
from pathlib import Path

import pandas as pd
import pytest

from src.v1.engine.components.transform.map.map_component import Map
from src.v1.engine.base_component import ExecutionMode
from src.v1.engine.exceptions import ConfigurationError


SAMPLE_CONFIG = {
    "component_type": "Map",
    "inputs": {
        "main": {"name": "row1", "filter": "", "activate_filter": False,
                 "matching_mode": "UNIQUE_MATCH", "lookup_mode": "LOAD_ONCE"},
        "lookups": [],
    },
    "variables": [],
    "outputs": [{
        "name": "out", "is_reject": False, "inner_join_reject": False,
        "catch_output_reject": False, "filter": "", "activate_filter": False,
        "columns": [{"name": "id", "expression": "row1.id", "type": "int", "nullable": True}],
    }],
    "die_on_error": True,
}


def test_map_select_mode_always_batch():
    m = Map("tMap_1", SAMPLE_CONFIG)
    assert m._select_mode(None) == ExecutionMode.BATCH


def test_map_validate_no_java_marker_no_bridge_ok():
    cfg = {**SAMPLE_CONFIG, "outputs": [{
        **SAMPLE_CONFIG["outputs"][0],
        "columns": [{"name": "id", "expression": "1", "type": "int", "nullable": True}],
    }]}
    m = Map("tMap_1", cfg)
    m._fresh_config()
    m._validate_config()  # must not raise


def test_map_validate_java_marker_no_bridge_raises():
    cfg = {**SAMPLE_CONFIG, "outputs": [{
        **SAMPLE_CONFIG["outputs"][0],
        "columns": [{"name": "id", "expression": "{{java}}row1.id", "type": "int", "nullable": True}],
    }]}
    m = Map("tMap_1", cfg)
    m._fresh_config()
    with pytest.raises(ConfigurationError, match="Java bridge"):
        m._validate_config()


@pytest.mark.java
def test_process_map_with_lookup_fixture(java_bridge):
    """End-to-end against the map_with_lookup.json fixture (real bridge)."""
    fixture = Path("tests/fixtures/jobs/transform/map_with_lookup.json")
    job = json.loads(fixture.read_text())
    map_comp = next(c for c in job["components"] if c["id"] == "tMap_1")

    m = Map("tMap_1", map_comp["config"])
    m.schema_inputs_map = map_comp["schema"]["inputs"]
    m.output_schema = map_comp["schema"]["output"]
    m.java_bridge = java_bridge

    main_df = pd.DataFrame({"id": [1, 2], "key": ["A", "B"], "val": [100, 200]})
    lookup_df = pd.DataFrame({"key": ["A"], "label": ["alpha"]})

    result = m.execute({"row1": main_df, "row2": lookup_df})
    out = result["out_main"]
    assert list(out["id"]) == [1, 2]
    # LEFT_OUTER: row id=1 matched ("alpha"), row id=2 unmatched (NaN)
    labels = list(out["label"])
    assert labels[0] == "alpha"
    assert pd.isna(labels[1])
