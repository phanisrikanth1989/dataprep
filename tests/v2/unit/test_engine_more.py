"""The engine: checks, taps, when files appear, counts, context and schemas."""
import datetime as dt
import os

import polars as pl
import pytest

from src.v2.errors import JobRefusedError

from .kit import Either, Glance, Scratch, job, lines, run, schema_of


def with_schema(components, schemas):
    """Attach schema blocks to components of a job made by ``job``."""
    for component in components["components"]:
        if component["id"] in schemas:
            component["schema"] = schemas[component["id"]]
    return components


# ------------------------------------------------------------------
# Checks and taps
# ------------------------------------------------------------------

def test_failed_check_fails_the_component_and_no_file_appears(tmp_path):
    out = tmp_path / "out.csv"
    result = run(job(
        [("in", "rows", {"data": {"n": [1, -2, -3]}}), ("guard", "guard", {}), ("out", "save", {"path": str(out)})],
        [("r1", "in", "guard", "flow"), ("r2", "guard", "out", "flow")],
    ))
    assert result.status == "failed"
    assert result.failed_component == "guard"
    assert result.error == "2 negative value(s)"
    assert not out.exists()
    assert os.listdir(tmp_path) == []


def test_passing_check_changes_nothing(tmp_path):
    out = tmp_path / "out.csv"
    result = run(job(
        [("in", "rows", {"data": {"n": [1, 2]}}), ("guard", "guard", {}), ("out", "save", {"path": str(out)})],
        [("r1", "in", "guard", "flow"), ("r2", "guard", "out", "flow")],
    ))
    assert result.status == "success"
    assert lines(out) == ["n", "1", "2"]


def test_tap_is_handed_its_rows_once_the_pass_has_run(tmp_path):
    Glance.seen.clear()
    out = tmp_path / "out.csv"
    run(job(
        [("in", "rows", {"data": {"n": [5, 6, 7]}}), ("glance", "glance", {}), ("out", "save", {"path": str(out)})],
        [("r1", "in", "glance", "flow"), ("r2", "glance", "out", "flow")],
    ))
    assert [frame["n"].to_list() for frame in Glance.seen] == [[5, 6]]
    assert lines(out) == ["n", "5", "6", "7"]


def test_component_chooses_per_run_whether_it_needs_rows_in_hand(tmp_path):
    for rows_in_hand, expected in ((False, "LazyFrame"), (True, "DataFrame")):
        Either.handed.clear()
        run(job(
            [("in", "rows", {"data": {"n": [1]}}), ("either", "either", {"rows_in_hand": rows_in_hand}),
             ("out", "save", {"path": str(tmp_path / f"{expected}.csv")})],
            [("r1", "in", "either", "flow"), ("r2", "either", "out", "flow")],
        ))
        assert Either.handed == [expected]


# ------------------------------------------------------------------
# When files appear
# ------------------------------------------------------------------

def test_no_file_of_a_subjob_appears_when_a_later_part_of_it_fails(tmp_path):
    early, late = tmp_path / "early.csv", tmp_path / "late.csv"
    result = run(job(
        [("in", "rows", {"data": {"n": [1]}}), ("early", "save", {"path": str(early)}), ("peek", "peek", {}),
         ("add", "add", {"column": "missing"}), ("late", "save", {"path": str(late)})],
        [("r1", "in", "early", "flow"), ("r2", "in", "peek", "flow"), ("r3", "peek", "add", "flow"),
         ("r4", "add", "late", "flow")],
    ))
    assert result.status == "failed"
    assert os.listdir(tmp_path) == []


def test_scratch_files_a_component_asked_for_are_removed_when_the_job_ends(tmp_path):
    Scratch.made.clear()
    out = tmp_path / "out.csv"
    result = run(job([("in", "scratch", {}), ("out", "save", {"path": str(out)})], [("r1", "in", "out", "flow")]))
    assert result.status == "success"
    assert lines(out) == ["n", "7"]
    assert Scratch.made and not any(os.path.exists(path) for path in Scratch.made)


# ------------------------------------------------------------------
# Row counts
# ------------------------------------------------------------------

def counted(tmp_path, condition=None, **extra_config):
    triggers = []
    components = [("in", "rows", {"data": {"n": [5, 1, 9, 2]}}), ("split", "split", {"limit": 4}),
                  ("kept", "save", {"path": str(tmp_path / "k.csv")})]
    if condition:
        components.append(("next", "mark", {"name": "next"}))
        triggers.append({"type": "RunIf", "from": "kept", "to": "next", "condition": condition})
    return run(job(components, [("r1", "in", "split", "flow"), ("ok", "split", "kept", "filter")], triggers=triggers))


def test_rows_written_are_always_counted(tmp_path):
    assert counted(tmp_path).global_map == {"kept_NB_LINE": 2}


def test_counts_of_other_components_are_taken_only_when_something_reads_them(tmp_path):
    condition = ('((Integer)globalMap.get("split_NB_LINE")) == 4 && ((Integer)globalMap.get("split_NB_LINE_OK")) == 2'
                 ' && ((Integer)globalMap.get("split_NB_LINE_REJECT")) == 2 && ((Integer)globalMap.get("in_NB_LINE")) == 4')
    result = counted(tmp_path, condition)
    assert result.global_map == {
        "kept_NB_LINE": 2, "split_NB_LINE": 4, "split_NB_LINE_OK": 2, "split_NB_LINE_REJECT": 2, "in_NB_LINE": 4,
    }


# ------------------------------------------------------------------
# Context in config values
# ------------------------------------------------------------------

def saved_to(tmp_path, path_text, context):
    result = run(job(
        [("in", "rows", {"data": {"n": [1]}}), ("out", "save", {"path": path_text})],
        [("r1", "in", "out", "flow")],
        context=context,
    ))
    return result


def test_bare_context_reference_inside_a_value_is_replaced_as_in_v1(tmp_path):
    result = saved_to(tmp_path, "context.dir/out.csv", {"dir": str(tmp_path)})
    assert result.status == "success"
    assert (tmp_path / "out.csv").exists()


def test_bare_reference_to_an_unknown_variable_is_left_as_written(tmp_path):
    os.chdir(tmp_path)
    result = saved_to(tmp_path, "context.csv", {})
    assert result.status == "success"
    assert (tmp_path / "context.csv").exists()


def test_template_reference_is_replaced_as_text(tmp_path):
    result = saved_to(tmp_path, "${context.dir}/out_${context.n}.csv", {"dir": str(tmp_path), "n": 7})
    assert result.status == "success"
    assert (tmp_path / "out_7.csv").exists()


def test_value_that_is_one_reference_keeps_the_variables_type(tmp_path):
    out = tmp_path / "out.csv"
    run(job(
        [("in", "rows", {"data": {"n": [1]}}), ("add", "add", {"amount": "context.by"}),
         ("out", "save", {"path": str(out)})],
        [("r1", "in", "add", "flow"), ("r2", "add", "out", "flow")],
        context={"by": {"value": "41", "type": "int"}},
    ))
    assert lines(out) == ["n", "42"]


# ------------------------------------------------------------------
# Declared schemas
# ------------------------------------------------------------------

def shaped(tmp_path, data, schema, die_on_error=None, reject=False):
    out, rejected = tmp_path / "out.csv", tmp_path / "rej.csv"
    config = {} if die_on_error is None else {"die_on_error": die_on_error}
    components = [("in", "rows", {"data": data}), ("pass", "through", config), ("out", "save", {"path": str(out)})]
    flows = [("r1", "in", "pass", "flow"), ("r2", "pass", "out", "flow")]
    if reject:
        components.append(("rej", "save", {"path": str(rejected)}))
        flows.append(("r3", "pass", "rej", "reject"))
    made = with_schema(job(components, flows), {"pass": schema})
    return run(made), out, rejected


def test_output_is_put_in_the_declared_shape(tmp_path):
    result, out, _ = shaped(tmp_path, {"b": ["2"], "extra": ["x"], "a": ["1"]},
                            schema_of(("a", "int"), ("b", "int"), ("c", "str")))
    assert result.status == "success"
    assert lines(out) == ["a,b,c,extra", "1,2,,x"]


def test_missing_value_where_none_is_allowed_fails_the_component(tmp_path):
    result, out, _ = shaped(tmp_path, {"a": [1, None]}, schema_of(("a", "int", False)))
    assert result.status == "failed"
    assert result.failed_component == "pass"
    assert result.error == "Column 'a' has NULL values but is not nullable"
    assert not out.exists()


def test_missing_value_goes_to_reject_when_errors_are_not_fatal(tmp_path):
    result, out, rejected = shaped(tmp_path, {"a": [1, None, 3], "b": ["x", "y", "z"]},
                                   schema_of(("a", "int", False), ("b", "str")), die_on_error=False, reject=True)
    assert result.status == "success"
    assert lines(out) == ["a,b", "1,x", "3,z"]
    assert lines(rejected) == ["a,b,errorCode,errorMessage", ",y,SCHEMA_VIOLATION,Column 'a': non-nullable column has null"]


def test_error_columns_arriving_on_the_main_output_are_renamed(tmp_path):
    result, out, _ = shaped(tmp_path, {"id": [1], "errorCode": ["E"], "errorMessage": ["m"]}, schema_of(("id", "int")))
    assert lines(out) == ["id,errorCode_user,errorMessage_user", "1,E,m"]


def test_source_schema_types_are_not_second_guessed(tmp_path):
    out = tmp_path / "out.csv"
    made = with_schema(
        job([("in", "rows", {"data": {"d": [dt.datetime(2024, 1, 31)]}}), ("out", "save", {"path": str(out)})],
            [("r1", "in", "out", "flow")]),
        {"in": schema_of(("d", "datetime"))},
    )
    assert run(made).status == "success"


# ------------------------------------------------------------------
# What a job config may say about schemas and subjobs
# ------------------------------------------------------------------

def test_v1_schema_blocks_and_subjob_markers_are_accepted(tmp_path):
    made = job([("in", "rows", {"data": {"n": [1]}}), ("out", "save", {"path": str(tmp_path / "o.csv")})],
               [("r1", "in", "out", "flow")])
    made["components"][0].update({"subjob_id": "subjob_1", "is_subjob_start": True})
    made["components"][0]["schema"] = {
        "input": [], "output": [{"name": "n", "type": "int"}],
        "reject": [{"name": "n", "type": "int"}], "inputs": {"row1": [{"name": "n", "type": "int"}]},
    }
    assert run(made).status == "success"


def test_unknown_schema_block_is_refused(tmp_path):
    made = job([("in", "rows", {"data": {"n": [1]}})], [])
    made["components"][0]["schema"] = {"output": [], "sideways": []}
    with pytest.raises(JobRefusedError) as caught:
        run(made)
    assert "schema.sideways" in caught.value.report.format()


# ------------------------------------------------------------------
# The order inputs reach a component in
# ------------------------------------------------------------------

def test_inputs_follow_the_components_own_list_when_it_gives_one_as_in_v1(tmp_path):
    out = tmp_path / "out.csv"
    made = job(
        [("a", "rows", {"data": {"n": [1]}}), ("b", "rows", {"data": {"n": [2]}}),
         ("c", "rows", {"data": {"n": [3]}}), ("stack", "stack", {}), ("out", "save", {"path": str(out)})],
        [("fa", "a", "stack", "flow"), ("fb", "b", "stack", "flow"), ("fc", "c", "stack", "flow"),
         ("r", "stack", "out", "flow")],
    )
    made["components"][3]["inputs"] = ["fc", "fa"]
    run(made)
    assert lines(out) == ["n,via", "3,fc", "1,fa", "2,fb"]


# ------------------------------------------------------------------
# Which rows a component's NB_LINE counts
# ------------------------------------------------------------------

def test_component_says_which_frames_its_line_count_covers(tmp_path):
    from src.v2.components.base import Transform
    from src.v2.components.registry import Registry
    from src.v2.engine import run_job

    from .kit import REGISTRY as KIT

    class FirstOnly(Transform):
        """Takes two inputs, passes the first on, and counts only that one as v1's join does."""

        names = ("first_only",)
        max_inputs = 2

        def build(self, inputs):
            return {"main": next(iter(inputs.values()))}

        def line_counts(self, inputs, outputs):
            counts = super().line_counts(inputs, outputs)
            counts["NB_LINE"] = [next(iter(inputs.values()))]
            return counts

    registry = Registry()
    for cls in list(KIT.classes()) + [FirstOnly]:
        registry.register(cls)
    made = job(
        [("a", "rows", {"data": {"n": [1, 2, 3]}}), ("b", "rows", {"data": {"n": [7, 8]}}), ("it", "first_only", {}),
         ("out", "save", {"path": str(tmp_path / "o.csv")}), ("next", "mark", {"name": "next"})],
        [("fa", "a", "it", "flow"), ("fb", "b", "it", "flow"), ("r", "it", "out", "flow")],
        triggers=[{"type": "RunIf", "from": "out", "to": "next", "condition": '((Integer)globalMap.get("it_NB_LINE")) == 3'}],
    )
    result = run_job(made, registry=registry)
    assert result.global_map["it_NB_LINE"] == 3


def test_every_component_accepts_v1s_component_type_label(tmp_path):
    made = job([("in", "rows", {"data": {"n": [1]}, "component_type": "Rows"}),
                ("out", "save", {"path": str(tmp_path / "o.csv"), "component_type": "Save"})],
               [("r1", "in", "out", "flow")])
    assert run(made).status == "success"


# ------------------------------------------------------------------
# Values that only exist once the job runs
# ------------------------------------------------------------------

def test_expression_reading_a_row_count_is_not_refused_at_load(tmp_path):
    out = tmp_path / "out.csv"
    made = with_schema(job(
        [("a", "rows", {"data": {"n": [1, 2, 3]}}), ("first", "save", {"path": str(tmp_path / "first.csv")}),
         ("b", "rows", {"data": {"n": [10]}}),
         ("calc", "calc", {"expression": 'n + globalMap.get("first_NB_LINE")'}), ("out", "save", {"path": str(out)})],
        [("r1", "a", "first", "flow"), ("r2", "b", "calc", "flow"), ("r3", "calc", "out", "flow")],
    ), {"b": schema_of(("n", "int"))})
    result = run(made)
    assert result.status == "success"
    assert lines(out) == ["n", "13"]


def test_expression_reading_a_context_value_set_while_the_job_runs_is_not_refused_at_load(tmp_path):
    out = tmp_path / "out.csv"
    made = with_schema(job(
        [("vars", "rows", {"data": {"bonus": [5]}}), ("set", "set_context", {}),
         ("b", "rows", {"data": {"n": [10]}}), ("calc", "calc", {"expression": "n + context.bonus"}),
         ("out", "save", {"path": str(out)})],
        [("r0", "vars", "set", "flow"), ("r2", "b", "calc", "flow"), ("r3", "calc", "out", "flow")],
    ), {"b": schema_of(("n", "int"))})
    result = run(made)
    assert result.status == "success"
    assert lines(out) == ["n", "15"]


def test_expression_reading_a_context_value_nothing_sets_is_refused_at_load(tmp_path):
    made = with_schema(job(
        [("b", "rows", {"data": {"n": [10]}}), ("calc", "calc", {"expression": "n + context.bonus"}),
         ("out", "save", {"path": str(tmp_path / "o.csv")})],
        [("r2", "b", "calc", "flow"), ("r3", "calc", "out", "flow")],
    ), {"b": schema_of(("n", "int"))})
    with pytest.raises(JobRefusedError) as caught:
        run(made)
    assert "context has no variable 'bonus'" in caught.value.report.format()


def test_rows_handed_to_a_component_that_needs_them_are_computed_once():
    # Its row count is read by a trigger; counting must not run the plan that feeds it a second time.
    from src.v2.components.base import Source
    from src.v2.components.registry import Registry
    from src.v2.engine import run_job

    from .kit import Mark, Peek

    runs = []

    class Noted(Source):
        """Rows whose plan notes each time it is run."""

        names = ("noted",)

        def read(self):
            def note(batch):
                runs.append(batch.height)
                return batch

            return {"main": pl.LazyFrame({"n": [1, 2, 3]}).map_batches(note)}

    registry = Registry()
    for cls in (Noted, Peek, Mark):
        registry.register(cls)
    condition = '((Integer)globalMap.get("peek_NB_LINE")) == 3'
    made = job([("src", "noted", {}), ("peek", "peek", {}), ("next", "mark", {"name": "next"})],
               [("row1", "src", "peek", "flow")],
               triggers=[{"type": "RunIf", "from": "peek", "to": "next", "condition": condition}])
    Mark.ran.clear()
    result = run_job(made, registry=registry)
    assert result.status == "success" and result.global_map["peek_NB_LINE"] == 3 and Mark.ran == ["next"]
    assert runs == [3]
