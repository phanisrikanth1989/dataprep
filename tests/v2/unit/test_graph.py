"""Subjobs and the order components run in: the same as v1 works out."""
import random

import pytest

from src.v2.job.graph import loop, subjobs
from src.v2.job.model import ComponentSpec, Flow, Job


def make(ids, edges):
    job = Job(name="g")
    for component_id in ids:
        job.components[component_id] = ComponentSpec(component_id, "x", None, {}, {})
    for index, (source, target) in enumerate(edges):
        job.flows.append(Flow(f"f{index}", source, target, "flow", "main"))
    return job


def v1_order(ids, edges):
    """What v1's execution plan makes of the same components and flows."""
    from src.v1.engine.execution_plan import ExecutionPlan

    plan = ExecutionPlan(
        [{"id": component_id, "type": "x"} for component_id in ids],
        [{"name": f"f{i}", "from": a, "to": b, "type": "flow"} for i, (a, b) in enumerate(edges)],
        [],
    )
    return [list(plan.get_subjob_plan(subjob_id).component_ids) for subjob_id in plan.all_subjob_ids]


def test_components_joined_by_flows_form_one_subjob():
    job = make(["a", "b", "c", "d"], [("a", "b"), ("c", "d")])
    assert subjobs(job) == [["a", "b"], ["c", "d"]]


def test_subjobs_come_in_the_order_of_their_first_component():
    job = make(["late_source", "early", "late_sink"], [("late_source", "late_sink")])
    assert subjobs(job) == [["late_source", "late_sink"], ["early"]]


def test_every_source_of_a_subjob_runs_before_what_they_feed():
    edges = [("src1", "map"), ("src2", "map"), ("map", "log1"), ("map", "log2")]
    job = make(["src1", "map", "src2", "log1", "log2"], edges)
    assert subjobs(job) == [["src1", "src2", "map", "log1", "log2"]]


def test_branches_advance_one_layer_at_a_time():
    edges = [("s", "x1"), ("x1", "x2"), ("x2", "j"), ("s", "y1"), ("y1", "j")]
    job = make(["s", "x1", "x2", "y1", "j"], edges)
    assert subjobs(job) == [["s", "x1", "y1", "x2", "j"]]


@pytest.mark.parametrize("seed", range(40))
def test_order_is_the_one_v1_works_out(seed):
    rng = random.Random(seed)
    ids = [f"c{n}" for n in range(rng.randint(2, 12))]
    listed = ids[:]
    rng.shuffle(listed)
    edges = []
    for upper in range(1, len(ids)):
        for lower in range(upper):
            if rng.random() < 0.22:
                edges.append((ids[lower], ids[upper]))
    rng.shuffle(edges)
    assert subjobs(make(listed, edges)) == v1_order(listed, edges)


def test_loop_names_the_components_caught_in_it():
    job = make(["a", "b", "c"], [("a", "b"), ("b", "c"), ("c", "b")])
    assert set(loop(job)) == {"b", "c"}


def test_no_loop_is_none():
    assert loop(make(["a", "b"], [("a", "b")])) is None
