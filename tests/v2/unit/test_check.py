"""The check a job goes through when it is loaded: every fault of a flow in one report."""
import pytest

from src.v2.engine import load_job
from src.v2.errors import JobRefusedError

from .kit import REGISTRY, job, schema_of

NUMBER = schema_of(("n", "int"))


def chain(tmp_path, *steps, schemas=(), **more):
    """rows -> the steps, one after another -> save. ``schemas`` names the components that declare ``n``."""
    components = [("in", "rows", {"data": {"n": [1, 2]}}), *steps, ("out", "save", {"path": str(tmp_path / "o.csv")})]
    ids = [component_id for component_id, _, _ in components]
    flows = [(f"r{place}", source, target, "flow") for place, (source, target) in enumerate(zip(ids, ids[1:]))]
    made = job(components, flows, **more)
    for component in made["components"]:
        if component["id"] in schemas:
            component["schema"] = NUMBER
    return made


def refused(made):
    """The refusals of a job config that is not let through, as (component id, reason)."""
    with pytest.raises(JobRefusedError) as caught:
        load_job(made, registry=REGISTRY)
    return [(refusal.where.split()[1], refusal.reason) for refusal in caught.value.report]


def calc(component_id, expression):
    return (component_id, "calc", {"expression": expression})


def test_two_faults_on_one_flow_are_reported_together(tmp_path):
    made = chain(tmp_path, calc("first", "nope + 1"), calc("second", "missing * 2"), schemas=("in", "first"))
    found = refused(made)
    assert [component_id for component_id, _ in found] == ["first", "second"]
    assert "nope" in found[0][1] and "missing" in found[1][1]


def test_fault_further_down_is_found_past_two_faulty_components(tmp_path):
    made = chain(tmp_path, calc("first", "nope + 1"), calc("second", "missing * 2"), calc("third", "gone - 3"),
                 schemas=("in", "first", "second"))
    assert [component_id for component_id, _ in refused(made)] == ["first", "second", "third"]


def test_one_fault_is_one_line_however_much_follows_it(tmp_path):
    made = chain(tmp_path, calc("first", "nope + 1"), calc("second", "n * 2"), calc("third", "n - 3"),
                 schemas=("in", "first", "second"))
    assert [component_id for component_id, _ in refused(made)] == ["first"]


def test_what_follows_a_faulty_component_that_declares_no_columns_stays_unchecked(tmp_path):
    # Its columns would be a guess, and a guess reports faults that are not there.
    made = chain(tmp_path, calc("first", "nope + 1"), calc("second", "missing * 2"), schemas=("in",))
    assert [component_id for component_id, _ in refused(made)] == ["first"]


def test_fault_of_a_component_that_cannot_be_built_from_its_input_is_followed_too(tmp_path):
    # Not an expression this time: the column the component works on is not there.
    made = chain(tmp_path, ("first", "add", {"column": "absent"}), calc("second", "missing * 2"),
                 schemas=("in", "first"))
    assert [component_id for component_id, _ in refused(made)] == ["first", "second"]


def test_only_the_main_output_of_a_faulty_component_is_followed(tmp_path):
    # What leaves by its other outputs is not declared anywhere: the split's rejects are left unchecked.
    components = [("in", "rows", {"data": {"n": [1, 2]}}), ("split", "split", {"limit": 1}),
                  calc("kept", "missing * 2"), calc("turned_away", "gone * 2"),
                  ("out", "save", {"path": str(tmp_path / "o.csv")}), ("low", "save", {"path": str(tmp_path / "l.csv")})]
    flows = [("r1", "in", "split", "flow"), ("r2", "split", "kept", "flow"), ("r3", "split", "turned_away", "reject"),
             ("r4", "kept", "out", "flow"), ("r5", "turned_away", "low", "flow")]
    made = job(components, flows)
    made["components"][0]["schema"] = schema_of(("other", "int"))   # the split finds no column n
    made["components"][1]["schema"] = NUMBER
    assert [component_id for component_id, _ in refused(made)] == ["split", "kept"]


def test_component_that_waits_for_a_context_value_is_not_judged_and_neither_is_what_it_feeds(tmp_path):
    components = [("vars", "rows", {"data": {"bonus": [5]}}), ("set", "set_context", {}),
                  ("in", "rows", {"data": {"n": [1]}}), calc("waits", "n + context.bonus"),
                  calc("after", "missing * 2"), ("out", "save", {"path": str(tmp_path / "o.csv")})]
    flows = [("r0", "vars", "set", "flow"), ("r1", "in", "waits", "flow"), ("r2", "waits", "after", "flow"),
             ("r3", "after", "out", "flow")]
    made = job(components, flows)
    for component in made["components"]:
        if component["id"] in ("in", "waits"):
            component["schema"] = NUMBER
    assert load_job(made, registry=REGISTRY).name == "t"


def test_component_that_reads_a_count_of_the_run_is_not_judged_and_neither_is_what_it_feeds(tmp_path):
    made = chain(tmp_path, calc("counts", 'n + globalMap.get("elsewhere_NB_LINE")'), calc("after", "missing * 2"),
                 schemas=("in", "counts"))
    assert load_job(made, registry=REGISTRY).name == "t"


NOTE = " (checked against the columns 'first' declares, because 'first' has a fault of its own)"


def test_fault_found_past_a_faulty_component_says_which_columns_it_was_judged_on(tmp_path):
    made = chain(tmp_path, calc("first", "nope + 1"), calc("second", "missing * 2"), schemas=("in", "first"))
    (_, first), (_, second) = refused(made)
    assert "checked against" not in first
    assert second.endswith(NOTE)


def test_the_note_names_the_faulty_component_also_past_healthy_ones(tmp_path):
    made = chain(tmp_path, calc("first", "nope + 1"), calc("fine", "n * 2"), calc("third", "gone - 3"),
                 schemas=("in", "first", "fine"))
    found = refused(made)
    assert [component_id for component_id, _ in found] == ["first", "third"]
    assert found[1][1].endswith(NOTE)


def test_column_a_faulty_component_would_pass_on_undeclared_is_reported_with_the_note(tmp_path):
    # `first` declares n only and would pass `extra` on as well. That cannot be known while it is
    # faulty, so what reads `extra` is reported, and the note says what the report rests on.
    components = [("in", "rows", {"data": {"n": [1], "extra": [2]}}), ("first", "add", {"column": "absent"}),
                  calc("second", "extra * 2"), ("out", "save", {"path": str(tmp_path / "o.csv")})]
    flows = [("r1", "in", "first", "flow"), ("r2", "first", "second", "flow"), ("r3", "second", "out", "flow")]
    made = job(components, flows)
    made["components"][0]["schema"] = schema_of(("n", "int"), ("extra", "int"))
    made["components"][1]["schema"] = NUMBER
    found = refused(made)
    assert [component_id for component_id, _ in found] == ["first", "second"]
    assert "extra" in found[1][1] and found[1][1].endswith(NOTE)
