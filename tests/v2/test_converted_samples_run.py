"""Converted Talend sample jobs, run as they are on v1 and on v2.

The converter's sample job configs are taken unchanged apart from where
their files live: every delimited input gets a generated file that fits its
declared schema, and every log row (the samples end in one, which writes no
file) gets a file output behind it, so that there is something to compare.
A sample v2 refuses (Java expressions, components it does not have) is
skipped here; `test_converter_samples.py` covers what v2 accepts key by key.
"""
import copy
import json
import random
from pathlib import Path

import pytest

from src.v2 import JobRefusedError, load_job
from tests.v2.answer_key import assert_matches_v1

SAMPLES = sorted((Path(__file__).resolve().parents[1] / "talend_xml_samples" / "converted_jsons").glob("*.json"))
WORDS = ["alpha", "Bravo", "charlie", "DELTA", "echo", "alpha", "bravo", "Foxtrot"]
ROWS = 60


def value(column, rng, row, keys):
    """One field of a generated file, as text, for a declared column.

    ``keys`` is how many values a key-like column takes in this file: few, so
    that joins match and groups repeat, and fewer in each later file of a
    job, so that some rows find no match (v1 stalls on a reject flow that
    gets no row).
    """
    kind, name = column.get("type", "str"), column["name"].lower()
    if name.endswith("id") and name != "id" and kind in ("int", "str"):
        key = rng.randint(1, keys)
        return str(key) if kind == "int" else f"K{key}"
    if kind == "int":
        return str(row + 1 if name == "id" else rng.randint(1, 500))
    if kind in ("float", "Decimal"):
        return f"{rng.randint(1, 99999) / 100:.2f}"
    if kind == "bool":
        return rng.choice(["true", "false"])
    if kind == "datetime":
        day = f"2024-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"
        pattern = column.get("date_pattern") or "%Y-%m-%d"
        return day if pattern == "%Y-%m-%d" else __import__("datetime").datetime.strptime(day, "%Y-%m-%d").strftime(pattern)
    return rng.choice(WORDS)


def localised(sample):
    """The sample with its files in the working folder, the input files to write, and outputs to compare."""
    job = copy.deepcopy(sample)
    inputs = {}
    rng = random.Random(job.get("job_name", ""))
    for component in list(job["components"]):
        config = component.get("config") or {}
        if component["type"] == "FileInputDelimited":
            path = f"{component['id']}.csv"
            columns = component["schema"]["output"]
            separator = config.get("fieldseparator", ";").replace("\\t", "\t")
            keys = 8 - 3 * len(inputs)
            lines = [separator.join(column["name"] for column in columns)] * int(config.get("header_rows") or 0)
            lines += [separator.join(value(column, rng, row, keys) for column in columns) for row in range(ROWS)]
            inputs[path] = ("\n".join(lines) + "\n").encode("iso-8859-15")
            config["filepath"] = path
        elif component["type"] == "FileOutputDelimited":
            config.update({"filepath": f"{component['id']}.csv", "file_exist_exception": False, "append": False})
        elif component["type"] == "LogRow":
            flow_name = f"{component['id']}_kept"
            component.setdefault("outputs", []).append(flow_name)
            job["components"].append({
                "id": f"{component['id']}_file", "type": "FileOutputDelimited",
                "config": {"filepath": f"{component['id']}.out.csv", "fieldseparator": ";", "encoding": "UTF-8",
                           "include_header": True, "file_exist_exception": False},
                "schema": {"input": component.get("schema", {}).get("output", []), "output": []},
                "inputs": [flow_name], "outputs": [],
            })
            job["flows"].append({"name": flow_name, "from": component["id"], "to": f"{component['id']}_file", "type": "flow"})
    return job, inputs


# Sources this test can make an input file for.
READERS = {"FileInputDelimited"}


def runnable():
    found = []
    for path in SAMPLES:
        sample = json.loads(path.read_text())
        sources = {c["type"] for c in sample["components"] if not c.get("inputs")}
        if not sources <= READERS:
            continue
        job, inputs = localised(sample)
        try:
            load_job(job)
        except JobRefusedError:
            continue
        found.append(pytest.param(job, inputs, id=path.stem))
    return found


RUNNABLE = runnable()


def test_some_converted_samples_run_on_v2_as_they_are():
    assert len(RUNNABLE) >= 8


# Samples neither engine can finish, with the reason both give. The join sample declares a lookup
# column not nullable on its reject side, where unmatched rows never have it.
FAIL_ON_BOTH = {"Job_tJoin_0.1": "Column 'dept_name' has NULL values but is not nullable"}


@pytest.mark.parametrize("job, inputs", RUNNABLE)
def test_converted_sample_writes_what_v1_writes(tmp_path, job, inputs):
    run = assert_matches_v1(job, inputs, tmp_path)
    reason = FAIL_ON_BOTH.get(job["job_name"])
    if reason is not None:
        assert not run.succeeded and reason in run.error
        return
    assert run.succeeded, run.error
    assert run.files, "the job wrote nothing to compare"
