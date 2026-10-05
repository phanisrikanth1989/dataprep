"""Loading a job config: v1's shape in, v2's model out, one refusal report."""
import copy
import json

import pytest

from src.v2.components.base import Component
from src.v2.components.registry import Registry
from src.v2.errors import JobRefusedError
from src.v2.job.keys import EXPRESSION, Key, Kind
from src.v2.job.loader import load_job


class Reader(Component):
    names = ("reader", "Reader", "tReader")
    keys = (Key("path", required=True, aliases=("filepath",)), Key("limit", type=int))
    max_inputs = 0


class Keeper(Component):
    names = ("keeper", "Keeper")
    keys = (Key("condition", type=EXPRESSION, default=""), Key("uncompress", kind=Kind.REFUSED, reason="no zip"))
    outputs = {"main": ("flow", "main", "filter"), "reject": ("reject",)}


class Writer(Component):
    names = ("writer", "Writer")
    keys = (Key("path", required=True, aliases=("filepath",)),)
    outputs = {}


REGISTRY = Registry()
for _cls in (Reader, Keeper, Writer):
    REGISTRY.register(_cls)

COLUMNS = [{"name": "id", "type": "int", "nullable": False, "key": False}, {"name": "name", "type": "str"}]

V1_JOB = {
    "job_name": "orders",
    "job_type": "Standard",
    "default_context": "Default",
    "context": {"Default": {"in_dir": {"value": "/data", "type": "str"}, "max": {"value": "5", "type": "int"}}},
    "components": [
        {"id": "in_1", "type": "Reader", "original_type": "tReader", "position": {"x": 1, "y": 2},
         "config": {"filepath": "a.csv"}, "schema": {"input": [], "output": COLUMNS},
         "inputs": [], "outputs": ["row1"]},
        {"id": "keep_1", "type": "Keeper", "config": {"condition": "row1.id > 1"},
         "schema": {"input": COLUMNS, "output": COLUMNS}, "inputs": ["row1"], "outputs": ["row2", "bad"]},
        {"id": "out_1", "type": "Writer", "config": {"filepath": "b.csv"}, "schema": {}, "inputs": ["row2"], "outputs": []},
        {"id": "out_2", "type": "Writer", "config": {"filepath": "c.csv"}, "schema": {}, "inputs": ["bad"], "outputs": []},
    ],
    "flows": [
        {"name": "row1", "from": "in_1", "to": "keep_1", "type": "flow"},
        {"name": "row2", "from": "keep_1", "to": "out_1", "type": "filter"},
        {"name": "bad", "from": "keep_1", "to": "out_2", "type": "reject"},
    ],
    "triggers": [],
    "subjobs": {"subjob_1": ["in_1", "keep_1", "out_1", "out_2"]},
    "java_config": {"enabled": True, "routines": ["routines.TalendDate"], "libraries": []},
    "_validation": {"valid": True},
    "_needs_review": [],
}


def load(job, **kwargs):
    return load_job(job, registry=REGISTRY, **kwargs)


def refusals(job, **kwargs):
    with pytest.raises(JobRefusedError) as caught:
        load(job, **kwargs)
    return [(r.where, r.key, r.reason) for r in caught.value.report]


def changed(**edits):
    job = copy.deepcopy(V1_JOB)
    job.update(edits)
    return job


# ------------------------------------------------------------------
# A v1 job config loads as it is
# ------------------------------------------------------------------

def test_v1_job_config_loads_without_edits():
    job = load(V1_JOB)
    assert job.name == "orders"
    assert list(job.components) == ["in_1", "keep_1", "out_1", "out_2"]


def test_component_config_is_held_under_v2_names():
    job = load(V1_JOB)
    assert job.components["in_1"].config == {"path": "a.csv", "limit": None}
    assert job.components["in_1"].cls is Reader


def test_declared_schema_is_read_from_beside_the_config():
    job = load(V1_JOB)
    out = job.components["in_1"].schema
    assert [(c.name, c.type, c.nullable) for c in out] == [("id", "int", False), ("name", "str", True)]


def test_flows_carry_their_name_ends_and_the_port_they_leave_by():
    job = load(V1_JOB)
    assert [(f.name, f.source, f.target, f.port) for f in job.flows] == [
        ("row1", "in_1", "keep_1", "main"),
        ("row2", "keep_1", "out_1", "main"),
        ("bad", "keep_1", "out_2", "reject"),
    ]


def test_job_config_can_be_given_as_a_file_path(tmp_path):
    path = tmp_path / "job.json"
    path.write_text(json.dumps(V1_JOB))
    assert load(str(path)).name == "orders"
    assert load(path).name == "orders"


def test_loading_does_not_change_the_callers_job_config():
    before = copy.deepcopy(V1_JOB)
    load(V1_JOB)
    assert V1_JOB == before


# ------------------------------------------------------------------
# v2 spellings of the outer shape
# ------------------------------------------------------------------

def test_v2_spellings_of_the_outer_shape_are_accepted():
    job = copy.deepcopy(V1_JOB)
    job["name"] = job.pop("job_name")
    job["flows"] = [
        {"name": "row1", "source": "in_1", "target": "keep_1"},
        {"name": "row2", "source": "keep_1", "target": "out_1", "output": "main"},
        {"name": "bad", "source": "keep_1", "target": "out_2", "output": "reject"},
    ]
    job["components"][0]["type"] = "reader"
    loaded = load(job)
    assert loaded.name == "orders"
    assert [f.port for f in loaded.flows] == ["main", "main", "reject"]


def test_schema_inside_the_config_is_accepted_as_the_output_schema():
    job = copy.deepcopy(V1_JOB)
    component = job["components"][0]
    component["config"]["schema"] = component.pop("schema")["output"]
    assert [c.name for c in load(job).components["in_1"].schema] == ["id", "name"]


# ------------------------------------------------------------------
# Context
# ------------------------------------------------------------------

def test_context_comes_from_the_default_group_with_typed_values():
    assert load(V1_JOB).context == {"in_dir": "/data", "max": 5}


def test_context_may_be_flat():
    job = changed(context={"max": {"value": "7", "type": "int"}, "plain": "x"})
    del job["default_context"]
    assert load(job).context == {"max": 7, "plain": "x"}


def test_context_values_can_be_overridden_at_load():
    assert load(V1_JOB, context={"max": "9"}).context == {"in_dir": "/data", "max": 9}


def test_override_of_an_undeclared_context_variable_is_added_as_text():
    assert load(V1_JOB, context={"extra": "1"}).context["extra"] == "1"


def test_named_default_context_that_does_not_exist_is_refused():
    found = refusals(changed(default_context="Prod"))
    assert ("job", "default_context", "there is no context group named 'Prod'") in found


def test_context_value_that_does_not_fit_its_type_is_refused():
    job = changed(context={"Default": {"max": {"value": "many", "type": "int"}}})
    assert [(where, key) for where, key, _ in refusals(job)] == [("job", "context.max")]


# ------------------------------------------------------------------
# What is refused, all in one report
# ------------------------------------------------------------------

def test_unknown_component_type_is_refused():
    job = copy.deepcopy(V1_JOB)
    job["components"][0]["type"] = "tOracleInput"
    found = refusals(job)
    assert found[0][:2] == ("component in_1 (tOracleInput)", "type")
    assert "not supported" in found[0][2]


def test_config_problems_are_reported_against_their_component():
    job = copy.deepcopy(V1_JOB)
    job["components"][1]["config"].update({"uncompress": True, "bogus": 1})
    found = refusals(job)
    assert ("component keep_1 (Keeper)", "uncompress", "no zip") in found
    assert ("component keep_1 (Keeper)", "bogus", "unknown config key") in found


def test_java_expression_left_in_a_config_is_refused_where_it_sits():
    job = copy.deepcopy(V1_JOB)
    job["components"][1]["config"]["condition"] = "{{java}}row1.id.equals(1)"
    found = refusals(job)
    assert found == [(
        "component keep_1 (Keeper)",
        "condition",
        "Java expressions are not run by v2; rewrite it in Python",
    )]


def test_java_expression_nested_in_a_config_is_found():
    job = copy.deepcopy(V1_JOB)
    job["components"][0]["config"]["filepath"] = "{{java}}context.dir + \"/a.csv\""
    assert [key for _, key, _ in refusals(job)] == ["filepath"]


@pytest.mark.parametrize(
    "edit, key",
    [
        ({"components": []}, "components"),
        ({"bogus_key": 1}, "bogus_key"),
        ({"job_name": ""}, "job_name"),
    ],
)
def test_job_level_problems(edit, key):
    assert ("job", key) in [(where, k) for where, k, _ in refusals(changed(**edit))]


def test_duplicate_component_id_is_refused():
    job = copy.deepcopy(V1_JOB)
    job["components"][3]["id"] = "out_1"
    assert ("job", "components[3].id") in [(w, k) for w, k, _ in refusals(job)]


def test_component_without_an_id_or_a_type_is_refused():
    job = copy.deepcopy(V1_JOB)
    del job["components"][3]["id"]
    del job["components"][2]["type"]
    keys = [k for _, k, _ in refusals(job)]
    assert "components[3].id" in keys and "components[2].type" in keys


def test_unknown_component_level_key_is_refused():
    job = copy.deepcopy(V1_JOB)
    job["components"][0]["confg"] = {}
    assert ("component in_1 (Reader)", "confg") in [(w, k) for w, k, _ in refusals(job)]


@pytest.mark.parametrize(
    "flow, key, word",
    [
        ({"name": "x", "from": "nope", "to": "out_1", "type": "flow"}, "flows[3].from", "nope"),
        ({"name": "x", "from": "in_1", "to": "nope", "type": "flow"}, "flows[3].to", "nope"),
        ({"name": "row1", "from": "in_1", "to": "out_1", "type": "flow"}, "flows[3].name", "row1"),
        ({"name": "x", "from": "in_1", "to": "out_1", "type": "iterate"}, "flows[3].type", "iterate"),
        ({"name": "x", "from": "in_1", "to": "out_1", "type": "reject"}, "flows[3].type", "reject"),
        ({"name": "x", "from": "in_1", "to": "out_1", "type": "flow", "colour": 1}, "flows[3].colour", "unknown"),
        ({"from": "in_1", "to": "out_1", "type": "flow"}, "flows[3].name", "missing"),
    ],
)
def test_flow_problems(flow, key, word):
    job = copy.deepcopy(V1_JOB)
    job["flows"].append(flow)
    found = {k: reason for where, k, reason in refusals(job) if where == "job"}
    assert key in found
    assert word in found[key]


def test_flow_into_a_component_that_takes_no_input_is_refused():
    job = copy.deepcopy(V1_JOB)
    job["flows"].append({"name": "x", "from": "keep_1", "to": "in_1", "type": "flow"})
    found = refusals(job)
    assert ("component in_1 (Reader)", "inputs", "takes no input, but 1 flow arrives") in found


def test_triggers_are_read_with_their_condition():
    job = copy.deepcopy(V1_JOB)
    job["components"] += [{"id": "next_1", "type": "Reader", "config": {"filepath": "n1.csv"}},
                          {"id": "next_2", "type": "Reader", "config": {"filepath": "n2.csv"}}]
    job["triggers"] = [
        {"type": "OnSubjobOk", "from": "in_1", "to": "next_1", "output_id": 2},
        {"type": "RunIf", "from": "in_1", "to": "next_2", "condition": "context.max > 1"},
    ]
    loaded = load(job)
    assert [(t.kind, t.source, t.target, t.condition, t.order) for t in loaded.triggers] == [
        ("OnSubjobOk", "in_1", "next_1", None, 2),
        ("RunIf", "in_1", "next_2", "context.max > 1", 0),
    ]


@pytest.mark.parametrize(
    "trigger, key",
    [
        ({"type": "OnSunday", "from": "in_1", "to": "out_1"}, "triggers[0].type"),
        ({"type": "OnSubjobOk", "from": "nope", "to": "out_1"}, "triggers[0].from"),
        ({"type": "OnSubjobOk", "from": "in_1", "to": "nope"}, "triggers[0].to"),
        ({"type": "RunIf", "from": "in_1", "to": "out_1"}, "triggers[0].condition"),
        ({"type": "RunIf", "from": "in_1", "to": "out_1", "condition": "{{java}}x"}, "triggers[0].condition"),
    ],
)
def test_trigger_problems(trigger, key):
    job = copy.deepcopy(V1_JOB)
    job["triggers"] = [trigger]
    assert ("job", key) in [(w, k) for w, k, _ in refusals(job)]


def test_everything_refused_is_reported_together():
    job = copy.deepcopy(V1_JOB)
    job["components"][0]["type"] = "tOracleInput"
    job["components"][1]["config"]["bogus"] = 1
    job["flows"].append({"name": "x", "from": "in_1", "to": "nope", "type": "flow"})
    job["zzz"] = 1
    assert len(refusals(job)) == 4


def test_report_names_the_job():
    with pytest.raises(JobRefusedError) as caught:
        load(changed(bogus_key=1))
    assert caught.value.report.job_name == "orders"


# ------------------------------------------------------------------
# Context values and their declared types
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "value, type_name, expected",
    [
        ("TRUE", "bool", True), ("yes", "bool", True), ("1", "bool", True), ("false", "bool", False),
        ("0", "bool", False), ("no", "bool", False), (True, "id_Boolean", True),
        ("100", "id_Integer", 100), ("1.50", "id_Double", 1.5), ("2024-01-31", "datetime", "2024-01-31"),
        ("", "int", ""), (None, "int", None), ("xyz", "id_String", "xyz"), (9, "str", "9"),
    ],
)
def test_context_value_becomes_its_declared_type_as_in_v1(value, type_name, expected):
    job = changed(context={"Default": {"v": {"value": value, "type": type_name}}})
    loaded = load(job).context["v"]
    assert loaded == expected and type(loaded) is type(expected)


def test_declared_context_types_are_kept_for_components_that_set_context():
    assert load(V1_JOB).context_types == {"in_dir": "str", "max": "int"}


def test_routine_settings_are_read():
    job = changed(python_config={"enabled": True, "routines_dir": "my/routines", "routines": ["Fees"]})
    assert load(job).routines == {"enabled": True, "routines_dir": "my/routines", "routines": ["Fees"]}


def test_unknown_routine_setting_is_refused():
    found = refusals(changed(python_config={"enabled": True, "folder": "x"}))
    assert ("job", "python_config.folder") in [(where, key) for where, key, _ in found]


def test_component_fed_by_a_refused_component_is_not_reported_as_short_of_inputs():
    job = copy.deepcopy(V1_JOB)
    job["components"][0]["type"] = "tNoSuchReader"
    found = refusals(job)
    assert [(where, key) for where, key, _ in found] == [("component in_1 (tNoSuchReader)", "type")]
