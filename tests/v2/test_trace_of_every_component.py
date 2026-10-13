"""A run for picked rows, traced, through each of the components built in 2026-10.

``run.only`` and ``run.trace`` are the engine's, and a component has them by
keeping to its contract. Each case here runs one component for one picked
row and holds what the trace says it did with it: the rows of each output,
as text, and the place of the row each came from.
"""
import pytest

from .components import test_die as die_kit
from .components import test_extract_delimited_fields as delimited_kit
from .components import test_extract_json_fields as json_kit
from .components import test_extract_positional_fields as positional_kit
from .components import test_extract_regex_fields as regex_kit
from .components import test_file_output_excel as excel_kit
from .components import test_file_output_positional as fixed_width_kit
from .components import test_pivot_to_columns_delimited as pivot_kit
from .components import test_row_generator as generator_kit
from .components import test_set_global_var as global_var_kit
from .components import test_warn as warn_kit
from .components.kit import flow, job, reader
from .test_only import TABLE, fixed
from .test_row_numbers import PEOPLE, PEOPLE_DATA, chain, ran

LINE_3, LINE_4 = "line 3 of in.csv (id=2)", "line 4 of in.csv (id=3)"
UNPIVOTED = "id:int, name:str, what:str, years:int"
TWICE = [{"id": "row1.id", "name": "row1.name", "age": "1"}, {"id": "row1.id", "name": "row1.name", "age": "row1.age"}]
BY_NAME = {"groupbys": [{"input_column": "name", "output_column": "name"}],
           "operations": [{"output_column": "age", "function": "max", "input_column": "age"},
                          {"output_column": "id", "function": "min", "input_column": "id"}]}


def step(kind, config, declared=PEOPLE):
    """file -> the component -> a sort -> file, where no column has to be there."""
    return chain((kind, config, declared), last=declared), {"in.csv": PEOPLE_DATA}


def traced(tmp_path, made, files, **picked):
    """Run for the picked rows of `in` with a trace; returns how it ended and the trace by component id."""
    made = dict(made, run={"only": {"source": "in", **picked}, "trace": True})
    result = ran(tmp_path, made, files)
    return result, {entry["id"]: entry for entry in result.summary()["trace"]}


def outputs(entry):
    return {port: (held["data"], held["from"]) for port, held in entry["outputs"].items()}


# ------------------------------------------------------------------
# Components that hand rows on
# ------------------------------------------------------------------

@pytest.mark.parametrize("case, component_id, picked, expected", [
    (step("Replicate", {}), "s1", {"lines": [3]}, {"main": ([["2", "bob", "41"]], [LINE_3])}),
    (step("SampleRow", {"range": "1..9"}), "s1", {"lines": [3]},
     {"main": ([["2", "bob", "41"]], [LINE_3]), "reject": ([], [])}),
    (step("SplitRow", {"col_mapping": TWICE}), "s1", {"lines": [3]},
     {"main": ([["2", "bob", "1"], ["2", "bob", "41"]], [LINE_3, LINE_3])}),
    (step("Replace", {"substitutions": [{"input_column": "name", "search_pattern": "cy", "replace_string": "cyd"}]}),
     "s1", {"lines": [4]}, {"main": ([["3", "cyd", None]], [LINE_4])}),
    (step("ConvertType", {"manualtable": [{"input_column": "name", "output_column": "name"}]}), "s1", {"lines": [3]},
     {"main": ([["2", "bob", "41"]], [LINE_3]), "reject": ([], [])}),
    (step("UnpivotRow", {"row_keys": ["id", "name"], "pivot_key": "what", "pivot_value": "years"}, UNPIVOTED),
     "s1", {"lines": [3]}, {"main": ([["2", "bob", "age", "41"]], [LINE_3])}),
    (step("Denormalize", {"denormalize_columns": [{"input_column": "name"}]}), "s1", {"lines": [3]},
     {"main": ([["2", "bob", "41"]], [LINE_3])}),
    (step("AggregateSortedRow", BY_NAME), "s1", {"lines": [3]}, {"main": ([["2", "bob", "41"]], [LINE_3])}),
    (step("SchemaComplianceCheck", {"schema": [{"name": "name", "type": "str", "nullable": False}]}), "s1",
     {"lines": [3]}, {"main": ([["2", "bob", "41"]], [LINE_3]), "reject": ([], [])}),
    ((delimited_kit.extract(), {"in.csv": delimited_kit.DATA}), "it", {"lines": [3]},
     {"main": ([["2", "d", "e", None]], ["line 3 of in.csv"]), "reject": ([], [])}),
    ((positional_kit.extract(), {"in.csv": positional_kit.DATA}), "it", {"lines": [3]},
     {"main": ([["2", "abc", "", ""]], ["line 3 of in.csv"]), "reject": ([], [])}),
    ((regex_kit.extract(), {"in.csv": regex_kit.DATA}), "it", {"lines": [2]},
     {"main": ([["1", "ann", "30", "x"]], ["line 2 of in.csv"]), "reject": ([], [])}),
    ((regex_kit.extract(), {"in.csv": regex_kit.DATA}), "it", {"lines": [3]},
     {"main": ([], []), "reject": ([["2", "bob", "NO_MATCH", "Regex did not match: 'bob'"]], ["line 3 of in.csv"])}),
    ((json_kit.extract(), {"in.csv": json_kit.DATA}), "it", {"lines": [3]},
     {"main": ([["2", "bob", None, "false", "", "", "", None]], ["line 3 of in.csv"]), "reject": ([], [])}),
    ((warn_kit.through(message="seen"), {"in.csv": b"1\n2\n3\n"}), "say", {"lines": [3]},
     {"main": ([["3"]], ["line 3 of in.csv"])}),
    ((global_var_kit.in_flow("k", variables=global_var_kit.variables(k="'v'")), {"in.csv": global_var_kit.DATA}),
     "set", {"lines": [2]}, {"main": ([["2", "bob", "2.5"]], ["line 2 of in.csv"])}),
], ids=["replicate", "sample row", "split row", "replace", "convert type", "unpivot row", "denormalize",
        "aggregate sorted row", "schema compliance check", "extract delimited fields", "extract positional fields",
        "extract regex fields", "extract regex fields, turned away", "extract json fields", "warn", "set global var"])
def test_trace_holds_what_the_component_did_with_the_picked_row(tmp_path, case, component_id, picked, expected):
    made, files = case
    result, trace = traced(tmp_path, made, files, **picked)
    assert result.status == "success", result.error
    assert result.summary()["only"]["rows"] == [f"line {picked['lines'][0]} of in.csv"]
    assert outputs(trace[component_id]) == expected
    # The file the picked row ends in holds what the component handed on, and says where it came from.
    assert (trace["out"]["data"], trace["out"]["from"]) == expected["main"]


# ------------------------------------------------------------------
# Components that write a file
# ------------------------------------------------------------------

@pytest.mark.parametrize("case, component_id, path, expected", [
    ((pivot_kit.pivoted(**pivot_kit.BASE), {"in.csv": pivot_kit.DATA}), "it", "out.csv", ["1", "ann", "Q1", "2.0"]),
    ((excel_kit.to_excel(), {"in.csv": excel_kit.DATA}), "out", "out.xlsx", ["2", "bob", "2.0"]),
    ((fixed_width_kit.positional([fixed_width_kit.field("id", 4), fixed_width_kit.field("name", 6)]),
      {"in.csv": fixed_width_kit.DATA}), "out", "out.txt", ["22  ", "abcdefgh"]),
], ids=["pivot to columns delimited", "file output excel", "file output positional"])
def test_trace_of_a_file_output_holds_the_picked_row_it_was_handed(tmp_path, case, component_id, path, expected):
    made, files = case
    result, trace = traced(tmp_path, made, files, lines=[3])
    assert result.status == "success", result.error
    held = trace[component_id]
    assert (held["path"], held["written"], held["rows"]) == (path, True, 1)
    assert (held["data"], held["from"]) == ([expected], ["line 3 of in.csv"])
    assert (tmp_path / path).exists()


# ------------------------------------------------------------------
# Components that make their own rows
# ------------------------------------------------------------------

def test_trace_of_a_fixed_flow_input_holds_the_picked_row(tmp_path):
    result, trace = traced(tmp_path, fixed(**TABLE), {}, rows=[2])
    assert result.status == "success", result.error
    assert outputs(trace["in"]) == {"main": ([["2", "20"]], ["row 2 of in"])}
    assert (trace["out"]["data"], trace["out"]["from"]) == ([["2", "20"]], ["row 2 of in"])


def test_trace_of_a_row_generator_holds_the_picked_row(tmp_path):
    made = generator_kit.generator(nb_rows=4, values=generator_kit.values(id="7", name="'n'", amt="1.5"))
    result, trace = traced(tmp_path, made, {}, rows=[2])
    assert result.status == "success", result.error
    assert outputs(trace["in"]) == {"main": ([["7", "n", "1.5"]], ["row 2 of in"]), "reject": ([], [])}
    assert (trace["out"]["data"], trace["out"]["from"]) == ([["7", "n", "1.5"]], ["row 2 of in"])


# ------------------------------------------------------------------
# A die
# ------------------------------------------------------------------

def test_trace_ends_at_the_die_the_picked_row_reached(tmp_path):
    made = job([reader("id:int", component_id="in"), die_kit.die(inputs=("row1",), message="stop")],
               [flow("row1", "in", "stop")])
    result, trace = traced(tmp_path, made, {"in.csv": b"1\n2\n3\n"}, lines=[3])
    assert result.status == "failed"
    assert outputs(trace["in"])["main"] == ([["3"]], ["line 3 of in.csv"])
    assert trace["stop"] == {"id": "stop", "type": "Die",
                             "error": "Job terminated by tDie: stop (exit code: 1); the row is line 3 of in.csv"}


def test_die_no_picked_row_reaches_stops_nothing_and_has_nothing_to_show(tmp_path):
    result, trace = traced(tmp_path, die_kit.to_die(message="turned away"), {"in.csv": b"1\n-2\n3\n"}, lines=[3])
    assert result.status == "success", result.error
    assert trace["stop"] == {"id": "stop", "type": "Die", "outputs": {}}
    assert (trace["out"]["data"], trace["out"]["from"]) == ([["3"]], ["line 3 of in.csv"])


def test_die_the_picked_row_is_turned_away_to_stops_the_job_and_names_it(tmp_path):
    result, trace = traced(tmp_path, die_kit.to_die(message="turned away"), {"in.csv": b"1\n-2\n3\n"}, lines=[2])
    assert result.status == "failed"
    assert result.error.endswith("the row is line 2 of in.csv")
    assert outputs(trace["it"])["reject"][1] == ["line 2 of in.csv"]
