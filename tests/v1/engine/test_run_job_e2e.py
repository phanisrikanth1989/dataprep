"""End-to-end integration test: parent tRunJob runs a child job that writes a file.

Proves the complete tRunJob path with real ETLEngine instances:
  - success path: child writes a CSV via tFixedFlowInput -> tFileOutputDelimited;
    parent status is 'success' and CHILD_RETURN_CODE == 0.
  - failure path: child aborts via tDie with die_on_child_error=True;
    parent status is non-success and CHILD_RETURN_CODE != 0.

Config keys verified against real component sources:
  tFixedFlowInput: values_config (list[dict] with schema_column/value keys), not 'values'
  tFileOutputDelimited: filepath (not file_path), fieldseparator (not field_delimiter)
  tDie: message, code, priority (all strings accepted)
"""
import json
import os

import pytest

from src.v1.engine.engine import ETLEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(dirpath, name, cfg):
    """Write a JSON job config to <dirpath>/<name>.json and return the absolute path.

    Merges cfg on top of minimal required defaults so callers only specify what
    differs from the bare minimum structure.
    """
    base = {
        "job_name": name,
        "flows": [],
        "triggers": [],
        "subjobs": {},
        "context": {"Default": {}},
    }
    base.update(cfg)
    path = os.path.join(str(dirpath), f"{name}.json")
    with open(path, "w") as f:
        json.dump(base, f)
    return path


# ---------------------------------------------------------------------------
# Success path: child writes a CSV
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_parent_runs_child_that_writes_file(tmp_path):
    """Parent tRunJob succeeds; child tFixedFlowInput -> tFileOutputDelimited writes a CSV."""
    out_csv = os.path.join(str(tmp_path), "enriched.csv")

    # ---- Child job: tFixedFlowInput -> tFileOutputDelimited ----
    # Config key fixes vs. brief:
    #   values_config (not 'values'); list[dict] with 'schema_column'/'value' keys.
    #   filepath (not 'file_path').
    #   fieldseparator (not 'field_delimiter').
    child_cfg = {
        "components": [
            {
                "id": "ffi_1",
                "type": "tFixedFlowInput",
                "config": {
                    "nb_rows": 1,
                    "use_singlemode": True,
                    "values_config": [{"schema_column": "id", "value": "1"}],
                },
                "schema": {
                    "input": [],
                    "output": [{"name": "id", "type": "id_String"}],
                },
                "inputs": [],
                "outputs": ["row1"],
            },
            {
                "id": "fout_1",
                "type": "tFileOutputDelimited",
                "config": {
                    "filepath": out_csv,
                    "fieldseparator": ",",
                    "include_header": True,
                    # Prevent spurious FileOperationError if tmp_path is reused
                    "file_exist_exception": False,
                },
                "schema": {
                    "input": [{"name": "id", "type": "id_String"}],
                    "output": [],
                },
                "inputs": ["row1"],
                "outputs": [],
            },
        ],
        "flows": [{"name": "row1", "from": "ffi_1", "to": "fout_1", "type": "flow"}],
        "subjobs": {"subjob_1": ["ffi_1", "fout_1"]},
    }
    _write(tmp_path, "Enrich", child_cfg)

    # ---- Parent job: single tRunJob ----
    parent_path = _write(tmp_path, "Parent", {
        "components": [
            {
                "id": "trun_1",
                "type": "tRunJob",
                "config": {"process": "Enrich", "die_on_child_error": True},
                "schema": {},
                "inputs": [],
                "outputs": [],
            }
        ],
        "subjobs": {"subjob_1": ["trun_1"]},
    })

    # Load parent via file path so ETLEngine sets _job_dir for child resolution.
    with ETLEngine(parent_path) as engine:
        stats = engine.execute()

    assert stats["status"] == "success", (
        f"Expected parent status 'success', got '{stats.get('status')}'. "
        f"Full stats: {stats}"
    )
    assert os.path.isfile(out_csv), (
        f"Expected child output file '{out_csv}' to exist but it does not."
    )
    assert engine.global_map.get("trun_1_CHILD_RETURN_CODE") == 0, (
        f"Expected CHILD_RETURN_CODE == 0, got "
        f"{engine.global_map.get('trun_1_CHILD_RETURN_CODE')!r}"
    )


# ---------------------------------------------------------------------------
# Failure path: child aborts via tDie, die_on_child_error=True
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_parent_fails_when_child_aborts_via_tdie(tmp_path):
    """Parent with die_on_child_error=True must end non-success when child has tDie."""
    # ---- Child job: single tDie that always terminates the child ----
    child_cfg = {
        "components": [
            {
                "id": "die_1",
                "type": "tDie",
                "config": {
                    "message": "induced failure for e2e test",
                    "code": "4",
                    "priority": "5",
                },
                "schema": {},
                "inputs": [],
                "outputs": [],
            }
        ],
        "subjobs": {"subjob_1": ["die_1"]},
    }
    _write(tmp_path, "DieChild", child_cfg)

    # ---- Parent job: tRunJob pointing at the dying child ----
    parent_path = _write(tmp_path, "ParentFail", {
        "components": [
            {
                "id": "trun_1",
                "type": "tRunJob",
                "config": {"process": "DieChild", "die_on_child_error": True},
                "schema": {},
                "inputs": [],
                "outputs": [],
            }
        ],
        "subjobs": {"subjob_1": ["trun_1"]},
    })

    with ETLEngine(parent_path) as engine:
        stats = engine.execute()

    assert stats["status"] != "success", (
        f"Expected parent to fail, but got status '{stats.get('status')}'. "
        f"Full stats: {stats}"
    )
    child_rc = engine.global_map.get("trun_1_CHILD_RETURN_CODE")
    assert child_rc != 0, (
        f"Expected CHILD_RETURN_CODE != 0 when child aborts, got {child_rc!r}"
    )
