"""The first slice end to end: file in, filter, sort, file out, against v1."""
import json
from pathlib import Path

from tests.v2.answer_key import assert_matches_v1

ANSWER_KEY = Path(__file__).parent / "answer_key"
EMPLOYEES = Path(__file__).parents[1] / "v1" / "engine" / "fixtures" / "data" / "employees.csv"
JOB = json.loads((ANSWER_KEY / "first_slice.json").read_text())


def test_first_slice_writes_what_v1_writes(tmp_path):
    run = assert_matches_v1(JOB, {"employees.csv": EMPLOYEES}, tmp_path)
    assert list(run.files) == ["out/result.csv"]
