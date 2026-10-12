"""Run job: another job run as one step of this one."""
import json
import logging
import os

import pytest

from src.v2 import load_job, run_job
from src.v2.errors import JobRefusedError
from tests.v2.components.kit import flow, job, reader, writer

from .test_file_actions_kit import action, filled


def run_step(kind="RunJob", **config):
    return action("run", kind, **config)


def touching(name="child", **context):
    """A job that makes the file its context variable `name` names; more variables may be declared."""
    declared = {"name": {"value": "made.txt", "type": "str"}, **context}
    return dict(job([action("make", "FileTouch", filename="${context.name}")], []), job_name=name,
                context={"Default": declared})


def touching_when(condition, filename, **context):
    """A job that makes `first.txt`, and then the file `filename` when a condition over its context holds."""
    made = dict(job([action("first", "FileTouch", filename="first.txt"), action("then", "FileTouch", filename=filename)], []),
                job_name="child", context={"Default": context})
    made["triggers"] = [{"type": "RunIf", "from": "first", "to": "then", "condition": condition}]
    return made


def ran(tmp_path, parent, files, context=None):
    """Write the job configs to a folder and run `parent.json` there; returns how it ended and the folder."""
    held = {name: json.dumps(made).encode() if isinstance(made, dict) else made for name, made in files.items()}
    folder = filled(tmp_path, dict(held, **{"parent.json": json.dumps(parent).encode()}))
    previous = os.getcwd()
    os.chdir(folder)
    try:
        return run_job("parent.json", context=context), folder
    finally:
        os.chdir(previous)


def refusals(tmp_path, parent, files):
    held = {name: json.dumps(made).encode() for name, made in files.items()}
    folder = filled(tmp_path, dict(held, **{"parent.json": json.dumps(parent).encode()}))
    with pytest.raises(JobRefusedError) as refused:
        load_job(str(folder / "parent.json"))
    return [(refusal.where, refusal.key, refusal.reason) for refusal in refused.value.report]


def parent_of(*steps, **more):
    return dict(job(list(steps), []), job_name="parent", **more)


# ------------------------------------------------------------------
# The child runs
# ------------------------------------------------------------------

def test_child_runs_as_a_step_of_the_parent_and_its_summary_is_in_the_parents(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="src.v2")
    result, folder = ran(tmp_path, parent_of(run_step(process="child")), {"child.json": touching()})
    assert result.status == "success", result.error
    assert (folder / "made.txt").exists()
    assert result.global_map["run_CHILD_RETURN_CODE"] == 0 and "run_CHILD_EXCEPTION_STACKTRACE" not in result.global_map
    told = result.summary()["children"]["run"]
    assert (told["job_name"], told["runs"], told["last"]["status"], told["last"]["job_name"]) == ("child", 1, "success", "child")
    lines = [record.getMessage() for record in caplog.records if record.getMessage().startswith("[run]")]
    assert lines[0] == "[run] running the job 'child' (child.json)" and lines[-1].startswith("[run] the job 'child' finished in ")


def test_one_row_is_counted(tmp_path):
    parent = dict(parent_of(run_step(process="child")), run={"row_counts": True})
    result, _ = ran(tmp_path, parent, {"child.json": touching()})
    assert result.counts["run"] == {"NB_LINE": 1, "NB_LINE_OK": 1, "NB_LINE_REJECT": 0}


@pytest.mark.parametrize("there, taken", [
    (["child_0.1.json", "child_0.10.json", "child_0.2.json"], "child_0.10.json"),
    (["child.json", "child_0.3.json"], "child.json"),
    (["child_1.0.json", "child_other_9.9.json", "child_draft.json"], "child_1.0.json"),
], ids=["the highest version, counted in numbers", "the name alone before any version", "another job of a longer name is not it"])
def test_job_config_of_the_child_is_found_beside_the_parent_by_its_name_and_its_version(tmp_path, there, taken):
    files = {name: touching(name="child", name_of={"value": name, "type": "str"}) for name in there}
    for name in there:
        files[name]["components"][0]["config"]["filename"] = name + ".ran"
    result, folder = ran(tmp_path, parent_of(run_step(process="child")), files)
    assert result.status == "success", result.error
    assert sorted(path.name for path in folder.glob("*.ran")) == [taken + ".ran"]


def test_child_of_a_child_runs_too(tmp_path):
    middle = dict(job([run_step(process="grandchild")], []), job_name="child")
    result, folder = ran(tmp_path, parent_of(run_step(process="child")),
                         {"child.json": middle, "grandchild.json": touching(name="grandchild")})
    assert result.status == "success", result.error
    assert (folder / "made.txt").exists()
    assert result.summary()["children"]["run"]["last"]["children"]["run"]["last"]["job_name"] == "grandchild"


def noting(key):
    return {"id": "note", "type": "SetGlobalVar", "inputs": [], "outputs": [],
            "config": {"variables": [{"key": key, "value": "x"}]}, "schema": {"input": [], "output": []}}


def test_child_is_run_whole_and_as_its_parent_is_whatever_its_own_run_block_says(tmp_path):
    child = dict(touching(), run={"summary_file": "child_summary.json", "row_counts": False})
    parent = dict(parent_of(run_step(process="child")), run={"row_counts": True})
    result, folder = ran(tmp_path, parent, {"child.json": child})
    assert result.status == "success", result.error
    assert not (folder / "child_summary.json").exists()
    assert result.summary()["children"]["run"]["last"]["counts"]["make"] == {"NB_LINE": 1, "NB_LINE_OK": 1, "NB_LINE_REJECT": 0}
    quiet, _ = ran(tmp_path / "quiet", parent_of(run_step(process="child")), {"child.json": dict(touching(), run={"row_counts": True})})
    assert quiet.summary()["children"]["run"]["last"]["counts"] == {}


def test_what_the_child_holds_does_not_reach_the_parent_nor_the_parents_the_child(tmp_path):
    child = touching_when('globalMap.get("of_the_parent") is None', "alone.txt", own={"value": "mine", "type": "str"})
    child["components"].append(noting("of_the_child"))
    parent = parent_of(noting("of_the_parent"), run_step(process="child"))
    parent["triggers"] = [{"type": "OnSubjobOk", "from": "note", "to": "run"}]
    result, folder = ran(tmp_path, parent, {"child.json": child})
    assert result.status == "success", result.error
    assert (folder / "alone.txt").exists()
    assert result.global_map["of_the_parent"] == "x" and "of_the_child" not in result.global_map
    assert "own" not in result.context


# ------------------------------------------------------------------
# What the parent gives the child
# ------------------------------------------------------------------

def test_value_given_by_name_is_the_childs_context_variable_with_the_type_the_child_declares(tmp_path):
    # The condition adds one to the number: text in its place would be no number to add to.
    child = touching_when("context.n + 1 == 42", "${context.word}", n={"value": "1", "type": "int"},
                          word={"value": "none.txt", "type": "str"})
    step = run_step(process="child", context_params=[{"param_name": "n", "param_value": "41"},
                                                      {"param_name": "word", "param_value": "given.txt"}])
    result, folder = ran(tmp_path, parent_of(step), {"child.json": child})
    assert result.status == "success", result.error
    assert (folder / "given.txt").exists() and not (folder / "none.txt").exists()


def named_by(*names):
    """A job that makes one file, named by its context variables one after another."""
    declared = {name: {"value": f"{name}0", "type": "str"} for name in names}
    return dict(touching(), context={"Default": declared},
                components=[action("make", "FileTouch", filename="".join(f"${{context.{name}}}" for name in names) + ".made")])


def made_in(folder):
    return sorted(path.name for path in folder.glob("*.made"))


def test_whole_context_gives_the_child_what_it_declares_and_a_value_given_by_name_wins(tmp_path):
    context = {"Default": {"a": {"value": "A", "type": "str"}, "b": {"value": "B", "type": "str"},
                           "only_the_parents": {"value": "x", "type": "str"}}}
    step = run_step(process="child", transmit_whole_context=True, context_params=[{"param_name": "b", "param_value": "named"}])
    result, folder = ran(tmp_path, parent_of(step, context=context), {"child.json": named_by("a", "b", "c")})
    assert result.status == "success", result.error
    assert made_in(folder) == ["Anamedc0.made"]


def test_child_is_given_only_what_it_declares(tmp_path):
    # Run alone, this child fails: it asks after a variable it does not declare. It fails the same under a parent
    # that has one of that name.
    child = touching_when('context.only_the_parents == "x"', "given_more.txt")
    parent = parent_of(run_step(process="child", transmit_whole_context=True),
                       context={"Default": {"only_the_parents": {"value": "x", "type": "str"}}})
    result, folder = ran(tmp_path, parent, {"child.json": child})
    assert (result.status, result.failed_component) == ("failed", "run")
    assert not (folder / "given_more.txt").exists()


def test_value_of_the_whole_context_has_the_type_the_child_declares_too(tmp_path):
    child = touching_when("context.n + 1 == 42", "typed.txt", n={"value": "1", "type": "int"})
    parent = parent_of(run_step(process="child", transmit_whole_context=True),
                       context={"Default": {"n": {"value": "41", "type": "str"}}})
    result, folder = ran(tmp_path / "fits", parent, {"child.json": child})
    assert result.status == "success", result.error
    assert (folder / "typed.txt").exists()
    parent["context"]["Default"]["n"]["value"] = "many"
    result, folder = ran(tmp_path / "does not", parent, {"child.json": child})
    assert (result.status, result.failed_component) == ("failed", "run")
    assert result.error == "the parent's context variable 'n': 'many' is no int, which the job 'child' declares 'n' to be"


def test_without_the_whole_context_the_child_has_its_own_values(tmp_path):
    parent = parent_of(run_step(process="child"), context={"Default": {"a": {"value": "A", "type": "str"}}})
    _, folder = ran(tmp_path, parent, {"child.json": named_by("a")})
    assert made_in(folder) == ["a0.made"]


def test_value_the_parent_was_started_with_goes_to_the_child_with_the_whole_context(tmp_path):
    parent = parent_of(run_step(process="child", transmit_whole_context=True),
                       context={"Default": {"a": {"value": "A", "type": "str"}}})
    _, folder = ran(tmp_path, parent, {"child.json": named_by("a")}, context={"a": "started_with"})
    assert made_in(folder) == ["started_with.made"]


def test_child_runs_once_for_each_pass_of_a_loop_with_the_item_given_to_it(tmp_path):
    each = {"id": "each", "type": "Foreach", "config": {"values": ["a", "b"]}, "inputs": [], "outputs": ["it"],
            "schema": {"input": [], "output": []}}
    given = '{{java}}((String)globalMap.get("each_CURRENT_VALUE")) + ".txt"'
    parent = parent_of(each, run_step(process="child", context_params=[{"param_name": "name", "param_value": given}]))
    parent["flows"] = [{"name": "it", "from": "each", "to": "run", "type": "iterate"}]
    result, folder = ran(tmp_path, parent, {"child.json": touching()})
    assert result.status == "success", result.error
    assert sorted(path.name for path in folder.glob("*.txt")) == ["a.txt", "b.txt"]
    assert result.summary()["children"]["run"]["runs"] == 2


@pytest.mark.parametrize("declared", ["int", "Decimal", "float", "bool"])
def test_value_that_does_not_fit_the_childs_type_fails_the_job(tmp_path, declared):
    child = touching(n={"value": "1", "type": declared})
    step = run_step(process="child", context_params=[{"param_name": "n", "param_value": "many"}])
    result, folder = ran(tmp_path, parent_of(step), {"child.json": child})
    assert (result.status, result.failed_component) == ("failed", "run")
    assert result.error == (
        f"context_params[0].param_value: 'many' is no {declared}, which the job 'child' declares 'n' to be")
    assert not (folder / "made.txt").exists()


def test_context_group_of_the_child_is_the_one_named(tmp_path):
    child = named_by("a")
    child["context"] = {"Default": {"a": {"value": "of_Default", "type": "str"}}, "Prod": {"a": {"value": "of_Prod", "type": "str"}}}
    _, folder = ran(tmp_path / "named", parent_of(run_step(process="child", context_name="Prod")), {"child.json": child})
    assert made_in(folder) == ["of_Prod.made"]
    child["default_context"] = "Prod"
    del child["context"]["Default"]
    # `Default` is what the converter writes when the job named none: the child then has the group it has itself.
    _, folder = ran(tmp_path / "its own", parent_of(run_step(process="child", context_name="Default")), {"child.json": child})
    assert made_in(folder) == ["of_Prod.made"]
    _, folder = ran(tmp_path / "none named", parent_of(run_step(process="child", context_name="")), {"child.json": child})
    assert made_in(folder) == ["of_Prod.made"]


# ------------------------------------------------------------------
# A child that fails
# ------------------------------------------------------------------

def failing_child():
    made = dict(job([reader("id:int", path="not_there.csv", outputs=("row2",), die_on_error=True), writer("id:int")],
                    [flow("row2", "in", "out")]), job_name="child")
    return made


def test_child_that_fails_fails_the_parent_at_the_step_with_the_childs_reason(tmp_path):
    result, _ = ran(tmp_path, parent_of(run_step(process="child")), {"child.json": failing_child()})
    assert (result.status, result.failed_component) == ("failed", "run")
    child_said = result.summary()["children"]["run"]["last"]["error"]
    assert child_said and result.error == f"the job 'child' failed at in: {child_said}"
    assert result.global_map["run_CHILD_RETURN_CODE"] == 1
    assert result.global_map["run_CHILD_EXCEPTION_STACKTRACE"] == child_said


def test_child_that_fails_at_no_one_component_fails_the_parent_with_the_reason_alone(tmp_path):
    child = touching_when("context.nothing_of_the_kind > 1", "never.txt")
    result, _ = ran(tmp_path, parent_of(run_step(process="child")), {"child.json": child})
    assert (result.status, result.failed_component) == ("failed", "run")
    assert result.error.startswith("the job 'child' failed: RunIf condition cannot be evaluated: ")


def test_parent_goes_on_after_a_child_that_fails_when_it_is_not_to_die_of_it(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger="src.v2.components")
    step = run_step(process="child", die_on_child_error=False)
    after = action("after", "FileTouch", filename="after.txt")
    parent = parent_of(step, after)
    parent["triggers"] = [{"type": "OnSubjobOk", "from": "run", "to": "after"}]
    result, folder = ran(tmp_path, parent, {"child.json": failing_child()})
    assert result.status == "success", result.error
    assert (folder / "after.txt").exists()
    said = result.global_map["run_ERROR_MESSAGE"]
    assert said.startswith("the job 'child' failed at in: ") and result.global_map["run_CHILD_RETURN_CODE"] == 1
    assert [record.getMessage() for record in caplog.records if record.name.endswith("run_job")] == [
        f"[run] {said}; the job goes on"]


def test_child_that_failed_is_counted_as_a_row_turned_away(tmp_path):
    parent = dict(parent_of(run_step(process="child", die_on_child_error=False)), run={"row_counts": True})
    result, _ = ran(tmp_path, parent, {"child.json": failing_child()})
    assert result.status == "success" and result.counts["run"] == {"NB_LINE": 1, "NB_LINE_OK": 0, "NB_LINE_REJECT": 1}


def test_child_that_ends_in_a_die_gives_the_dies_exit_code(tmp_path):
    child = dict(job([action("end", "Die", message="enough", exit_code=3)], []), job_name="child")
    result, _ = ran(tmp_path, parent_of(run_step(process="child", die_on_child_error=False)), {"child.json": child})
    assert result.status == "success" and result.global_map["run_CHILD_RETURN_CODE"] == 3


def test_reason_of_an_earlier_child_that_failed_is_not_left_after_one_that_did_not(tmp_path):
    each = {"id": "each", "type": "Foreach", "config": {"values": ["nowhere/x.txt", "fine.txt"]}, "inputs": [],
            "outputs": ["it"], "schema": {"input": [], "output": []}}
    given = '{{java}}((String)globalMap.get("each_CURRENT_VALUE"))'
    step = run_step(process="child", die_on_child_error=False, context_params=[{"param_name": "name", "param_value": given}])
    parent = parent_of(each, step)
    parent["flows"] = [{"name": "it", "from": "each", "to": "run", "type": "iterate"}]
    result, folder = ran(tmp_path, parent, {"child.json": touching()})
    assert result.status == "success", result.error
    assert (folder / "fine.txt").exists() and result.global_map["run_CHILD_RETURN_CODE"] == 0
    assert "run_CHILD_EXCEPTION_STACKTRACE" not in result.global_map


# ------------------------------------------------------------------
# Known when the parent loads
# ------------------------------------------------------------------

WHERE = "component run (RunJob)"


def test_child_that_is_not_there_refuses_the_parent(tmp_path):
    found = refusals(tmp_path, parent_of(run_step(process="child")), {"other.json": touching()})
    assert found == [(WHERE, "process", f"there is no job config for 'child' in '{tmp_path}': neither child.json nor a "
                                        "child_<version>.json")]


@pytest.mark.parametrize("written, said", [
    (b"{not a job config", "'child.json' is no job config that can be read: Expecting property name enclosed in double "
                           "quotes: line 1 column 2 (char 1)"),
    (b"[1, 2]", "'child.json' is no job config that can be read: expected an object, found list"),
], ids=["no JSON", "JSON that is no object"])
def test_child_whose_job_config_cannot_be_read_refuses_the_parent(tmp_path, written, said):
    folder = filled(tmp_path, {"parent.json": json.dumps(parent_of(run_step(process="child"))).encode(), "child.json": written})
    with pytest.raises(JobRefusedError) as refused:
        load_job(str(folder / "parent.json"))
    assert [(refusal.where, refusal.key, refusal.reason) for refusal in refused.value.report] == [(WHERE, "process", said)]


def test_what_is_wrong_with_the_child_refuses_the_parent_and_is_said_under_the_step(tmp_path):
    child = touching()
    child["components"][0]["config"]["nope"] = 1
    child["components"].append(action("odd", "NoSuchComponent"))
    found = refusals(tmp_path, parent_of(run_step(process="child")), {"child.json": child})
    assert found == [
        (f"{WHERE}, its job 'child': component make (FileTouch)", "nope", "unknown config key"),
        (f"{WHERE}, its job 'child': component odd (NoSuchComponent)", "type",
         "component type 'NoSuchComponent' is not supported in v2")]


def test_what_only_a_check_of_the_child_finds_refuses_the_parent_too(tmp_path):
    step = {"id": "sorted", "type": "SortRow", "config": {"criteria": [{"column": "nope", "sort_type": "num", "order": "asc"}]},
            "inputs": ["row1"], "outputs": ["row2"], "schema": {"input": [], "output": []}}
    child = dict(job([reader("id:int"), step, writer(None)], [flow("row1", "in", "sorted"), flow("row2", "sorted", "out")]),
                 job_name="child")
    found = refusals(tmp_path, parent_of(run_step(process="child")), {"child.json": child})
    assert found == [(f"{WHERE}, its job 'child': component sorted (SortRow)", "config",
                      "criteria[0]: there is no column 'nope' to sort by")]


def test_job_that_would_run_itself_refuses_the_parent(tmp_path):
    again = dict(job([run_step(process="parent")], []), job_name="child")
    found = refusals(tmp_path / "round", parent_of(run_step(process="child")), {"child.json": again})
    assert found == [(f"{WHERE}, its job 'child': {WHERE}", "process",
                      "the job would run itself: parent.json -> child.json -> parent.json")]
    found = refusals(tmp_path / "itself", parent_of(run_step(process="parent")), {})
    assert found == [(WHERE, "process", "the job would run itself: parent.json -> parent.json")]


def test_name_the_child_does_not_declare_refuses_the_parent(tmp_path):
    step = run_step(process="child", context_params=[{"param_name": "nmae", "param_value": "x"}])
    found = refusals(tmp_path, parent_of(step), {"child.json": touching(other={"value": "", "type": "str"})})
    assert found == [(WHERE, "context_params[0].param_name",
                      "the job 'child' has no context variable 'nmae'; it has: name, other")]


def test_context_group_the_child_does_not_have_refuses_the_parent(tmp_path):
    found = refusals(tmp_path, parent_of(run_step(process="child", context_name="Prod")), {"child.json": touching()})
    assert found == [(WHERE, "context_name", "the job 'child' has no context group 'Prod'; it has: Default")]


@pytest.mark.parametrize("config, key, said", [
    ({"process": ""}, "process", "there is no job named"),
    ({"process": "../elsewhere/child"}, "process", "a job is named by its name, not by a path: '../elsewhere/child'"),
    ({"process": "${context.which}"}, "process",
     "the job to run has to be known when the parent loads, and '${context.which}' is known only when it runs"),
    ({"process": "child", "context_name": "${context.which}"}, "context_name",
     "the child's context group has to be known when the parent loads, and '${context.which}' is known only when it runs"),
    ({"process": "child", "use_dynamic_job": True}, "use_dynamic_job",
     "the job to run has to be known when the parent loads: name it in `process`"),
    ({"process": "child", "use_dynamic_context": True}, "use_dynamic_context",
     "the child's context group has to be known when the parent loads: name it in `context_name`"),
    ({"process": "child", "propagate_child_result": True}, "propagate_child_result",
     "v2 hands no rows from one job to another in memory: have the child write a file and the parent read it"),
])
def test_what_cannot_be_done_refuses_the_parent(tmp_path, config, key, said):
    found = refusals(tmp_path, parent_of(run_step(**config), context={"Default": {"which": {"value": "child", "type": "str"}}}),
                     {"child.json": touching()})
    assert found == [(WHERE, key, said)]


def test_flow_to_it_refuses_the_parent(tmp_path):
    parent = dict(job([reader("id:int"), dict(run_step(process="child"), inputs=["row1"])], [flow("row1", "in", "run")]),
                  job_name="parent")
    found = refusals(tmp_path, parent, {"child.json": touching()})
    assert found == [(WHERE, "inputs", "takes no input, but 1 flow arrives")]


# ------------------------------------------------------------------
# A parent that was not read from a file
# ------------------------------------------------------------------

def test_parent_that_is_no_file_says_where_its_children_are_or_is_refused(tmp_path):
    folder = filled(tmp_path, {"jobs/child.json": json.dumps(touching()).encode()})
    parent = parent_of(run_step(process="child"))
    with pytest.raises(JobRefusedError) as refused:
        load_job(parent)
    assert [(refusal.key, refusal.reason) for refusal in refused.value.report] == [
        ("process", "the job config was not read from a file, so there is no folder to look for 'child' in: name one "
                    "in `engine_config.jobs_dir`")]
    previous = os.getcwd()
    os.chdir(folder)
    try:
        result = run_job(dict(parent, engine_config={"jobs_dir": str(folder / "jobs")}))
    finally:
        os.chdir(previous)
    assert result.status == "success" and (folder / "made.txt").exists()


# ------------------------------------------------------------------
# A converted job, and the names it goes by
# ------------------------------------------------------------------

def test_what_the_converter_writes_is_taken(tmp_path):
    step = run_step(
        kind="tRunJob", use_dynamic_job=False, context_job="", process="child", context_name="Default",
        use_independent_process=False, die_on_child_error=True, transmit_whole_context=False, context_params=[],
        jvm_arguments=[{"argument": "-Xmx1g"}], propagate_child_result=False, print_parameter=False,
        transmit_original_context=True, use_child_jvm_setting=True, use_custom_jvm_setting=False, use_dynamic_context=False,
        dynamic_context="", use_extra_classpath=False, extra_classpath="", load_context_from_file=False,
        tstatcatcher_stats=False, label="x",
    )
    result, folder = ran(tmp_path, parent_of(step), {"child_0.1.json": touching()})
    assert result.status == "success", result.error
    assert (folder / "made.txt").exists()


@pytest.mark.parametrize("kind", ["run_job", "RunJob", "tRunJob"])
def test_every_name_of_it(tmp_path, kind):
    result, folder = ran(tmp_path, parent_of(run_step(kind=kind, process="child")), {"child.json": touching()})
    assert result.status == "success" and (folder / "made.txt").exists()
