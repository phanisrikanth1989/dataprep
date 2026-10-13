"""Replicate, against v1 on the same job config and bytes."""
import json
from pathlib import Path

import pytest

from src.v2 import load_job
from src.v2.errors import JobRefusedError
from tests.v2.answer_key import assert_matches_v1

from .kit import columns, flow, job, reader, writer

SAMPLE = Path(__file__).parents[2] / "talend_xml_samples" / "converted_jsons" / "Job_tReplicate_0.1.json"
SCHEMA = "id:int, name:str, amt:Decimal#2"
DATA = b"id;name;amt\n1;ann;1.50\n2;;\n3;cy;3.25\n"


def replicated(copies=2, **config):
    """file -> replicate -> one file for each copy."""
    component = {"id": "it", "type": "Replicate", "config": config,
                 "schema": {"input": columns(SCHEMA), "output": columns(SCHEMA)},
                 "inputs": ["row1"], "outputs": [f"copy{n}" for n in range(copies)]}
    writers = [writer(SCHEMA, f"out{n}", f"out{n}.csv", (f"copy{n}",)) for n in range(copies)]
    flows = [flow("row1", "in", "it")] + [flow(f"copy{n}", "it", f"out{n}") for n in range(copies)]
    return job([reader(SCHEMA, header_rows=1), component] + writers, flows)


@pytest.mark.parametrize("copies", [1, 2, 3])
def test_every_flow_that_leaves_gets_every_row(tmp_path, copies):
    run = assert_matches_v1(replicated(copies), {"in.csv": DATA}, tmp_path)
    assert run.succeeded, run.error
    assert [run.files[f"out{n}.csv"] for n in range(copies)] == [DATA] * copies


def test_no_rows_in_gives_no_rows_out(tmp_path):
    run = assert_matches_v1(replicated(), {"in.csv": b"id;name;amt\n"}, tmp_path)
    assert run.succeeded and run.files["out1.csv"] == b"id;name;amt\n"


def test_output_count_is_accepted_and_changes_nothing(tmp_path):
    run = assert_matches_v1(replicated(2, output_count=5), {"in.csv": DATA}, tmp_path)
    assert run.files["out0.csv"] == DATA


def test_key_it_does_not_know_refuses_the_job():
    with pytest.raises(JobRefusedError, match="unknown config key"):
        load_job(replicated(copies_wanted=3))


def test_converters_sample_loads():
    made = json.loads(SAMPLE.read_text())
    spec = next(c for c in made["components"] if c["type"] == "Replicate")
    load_job(replicated(**spec["config"]))


# ------------------------------------------------------------------
# What a second reader of this component found (ticket 62)
# ------------------------------------------------------------------

def test_die_on_error_is_the_engines_as_on_every_component(tmp_path):
    made = replicated(1, die_on_error=False)
    made["components"][1]["schema"]["output"][1]["nullable"] = False
    run = assert_matches_v1(made, {"in.csv": DATA}, tmp_path)
    assert run.succeeded and run.files["out0.csv"] == DATA


@pytest.mark.parametrize("count", [0, 11, "many"])
def test_output_count_out_of_v1s_range_refuses_the_job(count):
    with pytest.raises(JobRefusedError, match="output_count"):
        load_job(replicated(output_count=count))
