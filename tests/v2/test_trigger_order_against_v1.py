"""The order triggered subjobs run in, against v1 on the same job config.

The first subjob reads a file and writes it (``root_in`` -> ``root_out``).
Every subjob it sets off appends its own name to ``order.csv``, so the file
lists the subjobs in the order they ran.
"""
import pytest

from tests.v2.answer_key import assert_matches_v1, run_job, run_v1, run_v2
from tests.v2.components.kit import flow, job, reader, writer

READER_COUNT = '((Integer)globalMap.get("root_in_NB_LINE")) > 0'
WRITER_COUNT = '((Integer)globalMap.get("root_out_NB_LINE")) > 0'
ALWAYS = "1 == 1"


def stage(name):
    """A subjob that appends its name to order.csv."""
    parts = [reader("n:str", component_id=f"{name}_in", path=f"{name}.csv", outputs=(f"{name}_row",)),
             writer("n:str", component_id=f"{name}_out", path="order.csv", inputs=(f"{name}_row",),
                    include_header=False, append=True)]
    return parts, [flow(f"{name}_row", f"{name}_in", f"{name}_out")]


def made(triggers):
    """The job: ``triggers`` is a list of (type, source component, target subjob, output_id, condition)."""
    components = [reader("n:str", component_id="root_in", path="root.csv", outputs=("root_row",)),
                  writer("n:str", component_id="root_out", path="root_out.csv", inputs=("root_row",))]
    flows = [flow("root_row", "root_in", "root_out")]
    targets = []
    for _, _, target, _, _ in triggers:
        if target not in targets:
            targets.append(target)
            parts, wires = stage(target)
            components += parts
            flows += wires
    wired = [
        {"type": kind, "from": source, "to": f"{target}_in", "output_id": order,
         **({"condition": condition} if condition else {})}
        for kind, source, target, order, condition in triggers
    ]
    inputs = {"root.csv": b"x\n", **{f"{name}.csv": name.encode() + b"\n" for name in targets}}
    return job(components, flows, triggers=wired), inputs


@pytest.mark.parametrize(
    "triggers, order",
    [
        # A component's own triggers fire when it is done, a subjob's with its last component.
        ([("OnSubjobOk", "root_in", "s", 1, None), ("OnComponentOk", "root_in", "c", 2, None)], ["c", "s"]),
        ([("OnComponentOk", "root_out", "b", 1, None), ("OnComponentOk", "root_in", "a", 2, None)], ["a", "b"]),
        ([("OnSubjobOk", "root_in", "s", 1, None), ("RunIf", "root_in", "r", 2, ALWAYS)], ["r", "s"]),
        ([("RunIf", "root_in", "t", 2, READER_COUNT), ("OnSubjobOk", "root_in", "s", 1, None)], ["t", "s"]),
        # With the last component, everything that fires goes by output_id.
        ([("OnSubjobOk", "root_in", "s", 2, None), ("OnComponentOk", "root_out", "c", 1, None)], ["c", "s"]),
        ([("OnSubjobOk", "root_in", "s", 1, None), ("OnComponentOk", "root_out", "c", 2, None)], ["s", "c"]),
        ([("OnSubjobOk", "root_out", "s", 3, None), ("RunIf", "root_out", "r", 2, ALWAYS),
          ("OnComponentOk", "root_out", "c", 1, None)], ["c", "r", "s"]),
        ([("OnSubjobOk", "root_in", "p", 2, None), ("OnSubjobOk", "root_in", "q", 1, None)], ["q", "p"]),
        # A condition that only holds once the whole subjob is done fires last, in the order the job lists them.
        ([("RunIf", "root_in", "t", 1, WRITER_COUNT), ("OnComponentOk", "root_out", "c", 1, None)], ["c", "t"]),
        ([("RunIf", "root_in", "t", 1, WRITER_COUNT), ("OnSubjobOk", "root_in", "s", 2, None)], ["s", "t"]),
        ([("RunIf", "root_in", "p", 2, WRITER_COUNT), ("RunIf", "root_in", "q", 1, WRITER_COUNT)], ["p", "q"]),
        ([("RunIf", "root_in", "t", 1, WRITER_COUNT)], ["t"]),
        # A subjob waiting its turn is brought forward by a subjob trigger of the one that just ran, not by
        # a component trigger.
        ([("OnSubjobOk", "root_in", "p", 1, None), ("OnSubjobOk", "root_in", "q", 2, None),
          ("OnSubjobOk", "root_in", "z", 3, None), ("OnSubjobOk", "p_in", "z", 1, None)], ["p", "z", "q"]),
        ([("OnSubjobOk", "root_in", "p", 1, None), ("OnSubjobOk", "root_in", "q", 2, None),
          ("OnSubjobOk", "root_in", "z", 3, None), ("OnComponentOk", "p_out", "z", 1, None)], ["p", "q", "z"]),
    ],
)
def test_triggered_subjobs_run_in_v1s_order(tmp_path, triggers, order):
    job_config, inputs = made(triggers)
    run = assert_matches_v1(job_config, inputs, tmp_path)
    assert run.succeeded, run.error
    assert run.files["order.csv"].decode().split() == order


def test_condition_on_a_count_not_there_yet_stops_the_job_as_in_v1(tmp_path):
    # v1 evaluates a RunIf when its own component is done: a later component's count is not there yet,
    # and without a cast that cannot be compared with a number.
    triggers = [("RunIf", "root_in", "t", 1, 'globalMap.get("root_out_NB_LINE") > 0')]
    job_config, inputs = made(triggers)
    on_v1 = run_job(job_config, inputs, tmp_path / "v1", run_v1)
    on_v2 = run_job(job_config, inputs, tmp_path / "v2", run_v2)
    assert not on_v1.succeeded and not on_v2.succeeded
    assert "order.csv" not in on_v1.files and "order.csv" not in on_v2.files
    assert "RunIf condition cannot be evaluated" in on_v2.error
