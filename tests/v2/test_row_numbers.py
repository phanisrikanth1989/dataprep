"""Every source numbers its rows, and a failure names the row it was.

The number is a hidden column: it travels with the row through the job and
is never written to a file. These tests hold what a failure says; that no
file changes is held by every test that compares v2's files with v1's.
"""
import os

import pytest

from src.v2 import run_job

from .components.kit import columns, flow, job, reader, through, writer
from .components.test_file_input_excel import book, excel
from .components.test_file_input_json import json_job
from .components.test_file_input_fullrow import read_lines
from .components.test_file_input_positional import cut
from .components.test_map import config as map_config
from .components.test_map import lookup as map_lookup
from .components.test_map import mapping
from .components.test_map import out as map_out

IDS = "id:int, amount:int"


def keyed(made, component_id="in", key="id"):
    """Mark a column of a component's output schema as its key."""
    for component in made["components"]:
        if component["id"] == component_id:
            for column in component["schema"]["output"]:
                column["key"] = column["name"] == key
    return made


def copying(schema=IDS, write_schema="same", **read):
    """file -> file."""
    return job([reader(schema, **read), writer(schema if write_schema == "same" else write_schema, inputs=("row1",))],
               [flow("row1", "in", "out")])


def ran(tmp_path, made, files):
    """Run a job on v2 inside tmp_path with these files; returns how it ended."""
    for name, data in files.items():
        (tmp_path / name).write_bytes(data)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        return run_job(made)
    finally:
        os.chdir(previous)


def failed(tmp_path, made, files):
    result = ran(tmp_path, made, files)
    assert result.status == "failed", "the job finished"
    return result.error


# ------------------------------------------------------------------
# A reader names the line
# ------------------------------------------------------------------

def test_reader_names_the_line_of_the_row_it_cannot_read(tmp_path):
    error = failed(tmp_path, copying(header_rows=1, die_on_error=True), {"in.csv": b"id;amount\n1;10\n2;20\n3;x\n4;40\n"})
    assert error == ("Schema/coercion failed for 1 row(s); first error: Column 'amount': could not convert string "
                     "to float: 'x'; the row is line 4 of in.csv")


def test_reader_shows_the_value_of_the_key_column_too(tmp_path):
    made = keyed(copying(header_rows=1, die_on_error=True))
    error = failed(tmp_path, made, {"in.csv": b"id;amount\n1;10\n2;20\n3;x\n4;40\n"})
    assert error.endswith("; the row is line 4 of in.csv (id=3)")


def test_first_bad_row_is_the_one_named_and_all_are_counted(tmp_path):
    error = failed(tmp_path, keyed(copying(die_on_error=True)), {"in.csv": b"1;10\n2;x\n3;30\n4;y\n"})
    assert error.startswith("Schema/coercion failed for 2 row(s); first error: ") and "'x'" in error
    assert error.endswith("; the row is line 2 of in.csv (id=2)")


def test_blank_lines_before_the_row_are_counted_as_lines(tmp_path):
    error = failed(tmp_path, copying(header_rows=1, die_on_error=True), {"in.csv": b"id;amount\n1;10\n\n\n2;x\n"})
    assert error.endswith("; the row is line 5 of in.csv")


def test_line_is_right_when_the_reader_splits_the_rows_itself(tmp_path):
    made = copying(header_rows=2, die_on_error=True, check_fields_num=True)
    error = failed(tmp_path, made, {"in.csv": b"title\nid;amount\n1;10\n\n2;20;extra\n3;30\n"})
    assert "Field count mismatch" in error
    assert error.endswith("; the row is line 5 of in.csv")


def test_file_with_enclosures_names_the_record_not_a_line(tmp_path):
    # A field may hold a line break there, so a record's number is not the line an editor shows.
    made = copying("id:int, note:str, amount:int", header_rows=1, die_on_error=True, csv_option=True)
    error = failed(tmp_path, made, {"in.csv": b'id;note;amount\n1;"two\nlines";10\n2;b;x\n'})
    assert error.endswith("; the row is record 2 of in.csv")


def test_key_value_is_cut_at_a_hundred_characters(tmp_path):
    made = keyed(copying("name:str, amount:int", die_on_error=True), key="name")
    error = failed(tmp_path, made, {"in.csv": b"a;1\n" + b"k" * 150 + b";x\n"})
    assert error.endswith("; the row is line 2 of in.csv (name=" + "k" * 100 + "...)")


def test_path_is_named_as_the_job_gives_it(tmp_path):
    (tmp_path / "data").mkdir()
    made = copying(path="data/in.csv", die_on_error=True)
    error = failed(tmp_path, made, {"data/in.csv": b"1;x\n"})
    assert error.endswith("; the row is line 1 of data/in.csv")


# ------------------------------------------------------------------
# The other readers
# ------------------------------------------------------------------

def test_positional_reader_names_the_line_and_the_key(tmp_path):
    made = keyed(cut(schema="a:str, n:int", pattern="3,3", header_rows=1, die_on_error=True), key="a")
    error = failed(tmp_path, made, {"in.txt": b"nam  n\nabc  1\n\ndef  x\nghi  3\n"})
    assert error == ("Schema/coercion failed for 1 row(s); first error: Column 'n': could not convert string to "
                     "float: 'x'; the row is line 4 of in.txt (a=def)")


def test_full_row_reader_numbers_its_lines(tmp_path):
    # The map reads each line as a whole number; the third line after the header is not one.
    lines = read_lines(header_rows=1)
    to_number = {"id": "it", "type": "PyMap", "config": map_config([map_out("row2", [("n", "row1.line", "int")])]),
                 "schema": {"inputs": {"row1": columns("line:str")}}, "inputs": ["row1"], "outputs": ["row2"]}
    made = job([lines["components"][0], to_number, writer("n:int", inputs=("row2",))],
               [flow("row1", "in", "it"), flow("row2", "it", "out")])
    error = failed(tmp_path, made, {"in.txt": b"numbers\n10\n\n30\nforty\n50\n"})
    assert error.endswith("; the row is line 5 of in.txt")


def test_excel_reader_names_the_sheet_and_the_row(tmp_path):
    made = keyed(excel("id:int, n:int!", header=1, die_on_error=True, all_sheets=True))
    sheets = book({"first": [["id", "n"], [1, 10], [2, 20]], "second": [["id", "n"], [3, 30], [4, None], [5, 50]]})
    error = failed(tmp_path, made, {"in.xlsx": sheets})
    assert error == ("Column 'n' has NULL values but is not nullable; "
                     "the row is row 3 of sheet 'second' of in.xlsx (id=4)")


def test_excel_row_is_the_sheets_own_when_the_sheet_starts_with_empty_rows(tmp_path):
    made = keyed(excel("id:int, n:int!", header=3, die_on_error=True))
    sheets = book({"only": [[None, None], [None, None], ["id", "n"], [1, 10], [2, None]]})
    error = failed(tmp_path, made, {"in.xlsx": sheets})
    assert error.endswith("; the row is row 5 of sheet 'only' of in.xlsx (id=2)")


# ------------------------------------------------------------------
# The number is never seen
# ------------------------------------------------------------------

def test_file_written_holds_the_declared_columns_only(tmp_path):
    result = ran(tmp_path, keyed(copying(header_rows=1)), {"in.csv": b"id;amount\n1;10\n2;20\n"})
    assert result.status == "success"
    assert (tmp_path / "out.csv").read_bytes() == b"id;amount\n1;10\n2;20\n"


def test_reject_file_holds_no_number(tmp_path):
    made = job([reader(IDS, outputs=("row1", "bad")), writer(IDS, inputs=("row1",)),
                writer(None, component_id="rej", path="rej.csv", inputs=("bad",))],
               [flow("row1", "in", "out"), flow("bad", "in", "rej", "reject")])
    result = ran(tmp_path, keyed(made), {"in.csv": b"1;10\n2;x\n"})
    assert result.status == "success"
    assert (tmp_path / "rej.csv").read_bytes().splitlines()[0] == b"id;amount;errorCode;errorMessage"


# ------------------------------------------------------------------
# The number travels with the row
# ------------------------------------------------------------------

PEOPLE = "id:int, name:str, age:int"
# The row with id 3 has no age: line 4 of the file, under one header line.
PEOPLE_DATA = b"id;name;age\n1;ann;30\n2;bob;41\n3;cy;\n4;di;25\n"
NEEDS_AGE = "id:int, name:str, age:int!"


def chain(*steps, schema=PEOPLE, last=NEEDS_AGE):
    """file -> the steps, one after another -> a sort that needs every age -> file.

    Each step is (type, config, the columns it declares); the sort is where
    the row without an age fails the job, so its message says how far the
    row's number travelled.
    """
    components = [keyed(job([reader(schema, header_rows=1)], []))["components"][0]]
    flows, before, had = [], "in", schema
    for number, (kind, settings, declared) in enumerate(steps, start=1):
        components.append({"id": f"s{number}", "type": kind, "config": settings,
                           "schema": {"input": columns(had), "output": columns(declared) if declared else []},
                           "inputs": [f"row{number}"], "outputs": [f"row{number + 1}"]})
        flows.append(flow(f"row{number}", before, f"s{number}"))
        before, had = f"s{number}", declared or had
    place = len(steps) + 1
    by_id = {"criteria": [{"column": "id", "sort_type": "num", "order": "asc"}]}
    components.append({"id": "needs", "type": "SortRow", "config": by_id,
                       "schema": {"input": columns(had), "output": columns(last)},
                       "inputs": [f"row{place}"], "outputs": [f"row{place + 1}"]})
    components.append(writer(last, inputs=(f"row{place + 1}",)))
    flows += [flow(f"row{place}", before, "needs"), flow(f"row{place + 1}", "needs", "out")]
    return job(components, flows)


NAMED = "Column 'age' has NULL values but is not nullable; the row is line 4 of in.csv (id=3)"


def test_number_travels_through_a_filter_of_columns(tmp_path):
    made = chain(("FilterColumns", {}, "age:int, id:int, name:str"))
    assert failed(tmp_path, made, {"in.csv": PEOPLE_DATA}) == NAMED


def test_number_travels_through_a_map(tmp_path):
    kept = [("id", "row1.id", "int"), ("name", "row1.name.upper()", "str"), ("age", "row1.age", "int")]
    made = chain(("PyMap", map_config([map_out("row2", kept)]), None))
    made["components"][1]["schema"] = {"inputs": {"row1": columns(PEOPLE)}}
    assert failed(tmp_path, made, {"in.csv": PEOPLE_DATA}) == NAMED


@pytest.mark.parametrize("step", [
    ("UniqueRow", {"key_columns": [{"column": "id"}]}, PEOPLE),
    ("UniqueRow", {}, PEOPLE),
    ("LogRow", {}, PEOPLE),
    ("SortRow", {"criteria": [{"column": "name", "sort_type": "alpha", "order": "desc"}]}, PEOPLE),
    ("FilterRows", {"conditions": [{"column": "id", "operator": ">", "function": "", "value": "0"}]}, PEOPLE),
], ids=["unique row", "unique row without keys", "log row", "sort row", "filter rows"])
def test_number_travels_through_a_step_that_keeps_its_rows(tmp_path, step):
    assert failed(tmp_path, chain(step), {"in.csv": PEOPLE_DATA}) == NAMED


def test_number_travels_through_two_maps_and_a_filter(tmp_path):
    kept = [("id", "row1.id", "int"), ("name", "row1.name", "str"), ("age", "row1.age", "int")]
    again = map_config([map_out("row4", [("id", "row3.id", "int"), ("name", "row3.name", "str"),
                                         ("age", "row3.age", "int")])])
    again["inputs"]["main"]["name"] = "row3"
    made = chain(
        ("PyMap", map_config([map_out("row2", kept)]), None),
        ("FilterRows", {"conditions": [{"column": "id", "operator": ">", "function": "", "value": "1"}]}, PEOPLE),
        ("PyMap", again, None),
    )
    made["components"][1]["schema"] = {"inputs": {"row1": columns(PEOPLE)}}
    made["components"][3]["schema"] = {"inputs": {"row3": columns(PEOPLE)}}
    assert failed(tmp_path, made, {"in.csv": PEOPLE_DATA}) == NAMED


def test_map_names_the_row_whose_text_it_cannot_read(tmp_path):
    kept = [("id", "row1.id", "int"), ("n", "row1.name", "int")]
    made = keyed(through({"type": "PyMap", "config": map_config([map_out("row2", kept)]),
                          "schema": {"inputs": {"row1": columns(PEOPLE)}}}, PEOPLE, "id:int, n:int"))
    error = failed(tmp_path, made, {"in.csv": b"id;name;age\n1;7;30\n2;bob;41\n3;9;1\n"})
    assert error == ("output 'row2' column 'n': 'bob' cannot be read as int (1 row of the output holds such a value)"
                     "; the row is line 3 of in.csv (id=2)")


def test_map_names_the_value_and_the_row_of_one_and_the_same_failure(tmp_path):
    # The first text that cannot be read is on line 3, in the second of the two columns; the first column's
    # is a line further down.
    pairs = "id:int, a:str, b:str"
    kept = [("id", "row1.id", "int"), ("a", "row1.a", "int"), ("b", "row1.b", "int")]
    made = keyed(through({"type": "PyMap", "config": map_config([map_out("row2", kept)]),
                          "schema": {"inputs": {"row1": columns(pairs)}}}, pairs, "id:int, a:int, b:int"))
    error = failed(tmp_path, made, {"in.csv": b"id;a;b\n1;7;8\n2;7;x\n3;y;8\n"})
    assert error == ("output 'row2' column 'b': 'x' cannot be read as int (2 rows of the output hold such a value)"
                     "; the row is line 3 of in.csv (id=2)")


def test_row_of_a_group_is_named_by_the_first_row_that_went_into_it(tmp_path):
    # The highest age of each name; the two rows called cy have none, so their group has none either.
    data = b"id;name;age\n1;ann;30\n2;cy;\n3;ann;5\n4;cy;\n"
    grouped = {"groupbys": [{"input_column": "name", "output_column": "name"}],
               "operations": [{"output_column": "age", "function": "max", "input_column": "age"},
                              {"output_column": "id", "function": "min", "input_column": "id"}]}
    made = chain(("AggregateRow", grouped, "id:int, name:str, age:int"))
    error = failed(tmp_path, made, {"in.csv": data})
    assert error == ("Column 'age' has NULL values but is not nullable; the row is line 3 of in.csv, "
                     "the first of 2 rows that were combined (id=2)")


# ------------------------------------------------------------------
# Where two inputs meet
# ------------------------------------------------------------------

def needing_age(arriving, declared=PEOPLE):
    """A sort that needs every age, and the file it writes: where a row without one fails the job."""
    by_id = {"criteria": [{"column": "id", "sort_type": "num", "order": "asc"}]}
    return [{"id": "needs", "type": "SortRow", "config": by_id,
             "schema": {"input": columns(declared), "output": columns(NEEDS_AGE)},
             "inputs": [arriving], "outputs": ["sorted"]},
            writer(NEEDS_AGE, inputs=("sorted",))], [flow("sorted", "needs", "out")]


@pytest.mark.parametrize("declared", [None, PEOPLE + ", errorCode:str, errorMessage:str"],
                         ids=["no reject schema", "a reject schema"])
def test_number_travels_through_the_reject_output_of_a_join(tmp_path, declared):
    # cy and di are in no list of names, and cy has no age.
    join = {"id": "it", "type": "Join", "config": {"join_key": [{"input_column": "name", "lookup_column": "name"}]},
            "schema": {"input": columns("name:str"), "output": columns(PEOPLE)},
            "inputs": ["row1", "row2"], "outputs": ["hit", "miss"]}
    if declared:
        join["schema"]["reject"] = columns(declared)
    last, sorted_flow = needing_age("miss")
    made = keyed(job(
        [reader(PEOPLE, header_rows=1), reader("name:str", "names", "names.csv", ("row2",), header_rows=1), join,
         writer(PEOPLE, "hits", "hits.csv", ("hit",))] + last,
        [flow("row1", "in", "it"), flow("row2", "names", "it"), flow("hit", "it", "hits"),
         flow("miss", "it", "needs", "reject")] + sorted_flow,
    ))
    assert failed(tmp_path, made, {"in.csv": PEOPLE_DATA, "names.csv": b"name\nann\nbob\n"}) == NAMED


def united(*more):
    """in.csv and more.csv -> a unite -> the steps -> a sort that needs every age -> file."""
    made = chain(("Unite", {}, PEOPLE), *more)
    made["components"].insert(1, reader(PEOPLE, "more", "more.csv", ("extra",), header_rows=1))
    made["components"][2]["inputs"].append("extra")
    made["flows"].append(flow("extra", "more", "s1"))
    return keyed(made, "more")


def test_row_is_named_by_the_input_it_came_from_after_a_unite(tmp_path):
    files = {"in.csv": b"id;name;age\n1;ann;30\n", "more.csv": b"id;name;age\n7;bob;41\n8;cy;\n"}
    assert failed(tmp_path, united(), files) == (
        "Column 'age' has NULL values but is not nullable; the row is line 3 of more.csv (id=8)")


def test_group_of_united_rows_names_the_first_row_of_each_input_that_is_in_it(tmp_path):
    # The highest age of each name. cy is in both files without an age; di, with none either, in the second alone.
    grouped = {"groupbys": [{"input_column": "name", "output_column": "name"}],
               "operations": [{"output_column": "age", "function": "max", "input_column": "age"},
                              {"output_column": "id", "function": "min", "input_column": "id"}]}
    made = united(("AggregateRow", grouped, "id:int, name:str, age:int"))
    files = {"in.csv": b"id;name;age\n1;ann;30\n2;cy;\n", "more.csv": b"id;name;age\n7;cy;\n8;ann;3\n9;cy;\n"}
    assert failed(tmp_path, made, files) == (
        "Column 'age' has NULL values but is not nullable; the row is line 3 of in.csv (id=2) "
        "and line 2 of more.csv, the first of 2 rows that were combined (id=7)")
    files["in.csv"] = b"id;name;age\n1;ann;30\n"
    assert failed(tmp_path, made, files) == (
        "Column 'age' has NULL values but is not nullable; the row is line 2 of more.csv, "
        "the first of 2 rows that were combined (id=7)")


def test_row_of_a_lookup_is_named_when_the_lookups_own_filter_fails_on_it(tmp_path):
    names = map_lookup("names", [("id", "row1.id")], filter="int(names.code) > 0", activate_filter=True)
    kept = [("id", "row1.id", "int"), ("code", "names.code", "str")]
    made = mapping(map_config([map_out("o", kept)], lookups=[names]), {"row1": IDS, "names": "id:int, code:str"},
                   {"o": "id:int, code:str"})
    files = {"row1.csv": b"id;amount\n1;10\n", "names.csv": b"id;code\n1;5\n2;x\n"}
    assert failed(tmp_path, keyed(made, "in_names"), files) == (
        "inputs.lookups[0].filter: int() could not read 'x' (in: int(names.code) > 0); 1 row failed; "
        "the row is line 3 of names.csv (id=2)")


def test_row_a_map_fails_on_is_the_main_inputs_and_not_the_lookups(tmp_path):
    names = map_lookup("names", [("id", "row1.id")])
    kept = [("id", "row1.id", "int"), ("n", "int(names.code)", "int")]
    made = mapping(map_config([map_out("o", kept)], lookups=[names]), {"row1": IDS, "names": "id:int, code:str"},
                   {"o": "id:int, n:int"})
    files = {"row1.csv": b"id;amount\n1;10\n2;20\n", "names.csv": b"id;code\n9;5\n2;x\n1;7\n"}
    assert failed(tmp_path, keyed(keyed(made, "in_names"), "in_row1"), files) == (
        "outputs[0].columns[1].expression: int() could not read 'x' (in: int(names.code)); 1 row failed; "
        "the row is line 3 of row1.csv (id=2)")


def test_every_row_a_normalize_makes_carries_the_number_of_the_row_it_came_from(tmp_path):
    # The third data row holds two ages; the second of them is no number, and the sort after it needs one.
    data = b"id;name;age\n1;ann;30\n2;bob;41\n3;cy;25,old\n4;di;7\n"
    made = chain(("Normalize", {"normalize_column": "age"}, "id:int, name:str, age:int"), schema="id:int, name:str, age:str")
    assert failed(tmp_path, made, {"in.csv": data}) == NAMED


# ------------------------------------------------------------------
# Who does not see it
# ------------------------------------------------------------------

def test_python_code_is_handed_the_declared_columns_only(tmp_path):
    made = keyed(through({"type": "PythonDataFrameComponent", "config": {"python_code": "df['seen'] = len(df.columns)"}},
                         PEOPLE, "id:int, seen:int"))
    result = ran(tmp_path, made, {"in.csv": PEOPLE_DATA})
    assert result.status == "success", result.error
    # Three columns were there for the code to count: id, name and age.
    assert (tmp_path / "out.csv").read_bytes().splitlines()[1].startswith(b"1;3;")


def test_row_that_went_through_python_code_is_no_longer_named(tmp_path):
    # What the code hands back is a table of its own making: the engine cannot say which row became which.
    made = chain(("PythonDataFrameComponent", {"python_code": "df = df"}, PEOPLE))
    assert failed(tmp_path, made, {"in.csv": PEOPLE_DATA}) == "Column 'age' has NULL values but is not nullable"


def test_debug_lines_do_not_list_the_hidden_columns(tmp_path, caplog):
    import logging

    caplog.set_level(logging.DEBUG, logger="src.v2")
    assert ran(tmp_path, keyed(copying(PEOPLE, header_rows=1)), {"in.csv": PEOPLE_DATA}).status == "success"
    listed = [record.getMessage() for record in caplog.records if "] output " in record.getMessage()]
    assert listed and not [line for line in listed if "__v2_" in line]


# ------------------------------------------------------------------
# A source that is not lines of text, and a step that makes several rows of one
# ------------------------------------------------------------------

# Three orders; the second has a tag that is no number, and the third no tags at all.
ORDERS = b"""{"orders": [
  {"id": 101, "tags": "1,2"},
  {"id": 102, "tags": "3,x7,5"},
  {"id": 103, "tags": ""}
]}"""
ORDER = "id:int, tags:str"


def orders(*steps, last="id:int, tags:int!", loop="$.orders[*]", **config):
    """orders.json -> the steps, one after another -> a sort that needs every tag to be a number -> file."""
    source = keyed(json_job(ORDER, [("id", "$.id"), ("tags", "$.tags")], loop=loop, **config))["components"][0]
    made = chain(*steps, schema=ORDER, last=last)
    made["components"][0] = source
    return made


def test_json_record_is_named_by_its_number_its_path_and_its_key(tmp_path):
    # No step in between: the third order has no tags, and the sort needs them.
    error = failed(tmp_path, orders(last="id:int, tags:str!"), {"in.json": ORDERS.replace(b'"tags": ""', b'"tags": null')})
    assert error == ("Column 'tags' has NULL values but is not nullable; "
                     "the row is record 3 ($.orders[2]) of in.json (id=103)")


def test_record_is_still_named_after_a_normalize_made_several_rows_of_it(tmp_path):
    made = orders(("Normalize", {"normalize_column": "tags"}, "id:int, tags:int"))
    error = failed(tmp_path, made, {"in.json": ORDERS})
    # "x7" is the second piece of the second order: not a number, so it goes missing, and the sort needs it.
    assert error == ("Column 'tags' has NULL values but is not nullable; "
                     "the row is record 2 ($.orders[1]) of in.json (id=102)")


def test_conversion_that_fails_after_a_normalize_names_the_record(tmp_path):
    doubled = map_config([map_out("row3", [("id", "row2.id", "int"), ("tags", "int(row2.tags) * 2", "int")])])
    doubled["inputs"]["main"]["name"] = "row2"
    made = orders(("Normalize", {"normalize_column": "tags", "discard_trailing_empty_str": True}, ORDER),
                  ("PyMap", doubled, None), last="id:int, tags:int")
    made["components"][2]["schema"] = {"inputs": {"row2": columns(ORDER)}}
    error = failed(tmp_path, made, {"in.json": ORDERS})
    assert error == ("outputs[0].columns[1].expression: int() could not read 'x7' (in: int(row2.tags) * 2); "
                     "1 row failed; the row is record 2 ($.orders[1]) of in.json (id=102)")


def test_group_made_of_normalized_json_records_names_its_first(tmp_path):
    # Every piece of every order in one group per order; the second order's group holds a piece that is no number.
    grouped = {"groupbys": [{"input_column": "id", "output_column": "id"}],
               "operations": [{"output_column": "tags", "function": "min", "input_column": "tags"}]}
    made = orders(("Normalize", {"normalize_column": "tags"}, "id:int, tags:int"),
                  ("FilterRows", {"conditions": [{"column": "id", "operator": "==", "function": "", "value": "103"}]},
                   "id:int, tags:int"),
                  ("AggregateRow", grouped, "id:int, tags:int"))
    error = failed(tmp_path, made, {"in.json": ORDERS})
    assert error == ("Column 'tags' has NULL values but is not nullable; "
                     "the row is record 3 ($.orders[2]) of in.json (id=103)")


def test_json_loop_gone_through_as_root_names_the_item(tmp_path):
    made = orders(last="id:int, tags:str!", loop="$.orders", use_loop_as_root=True)
    error = failed(tmp_path, made, {"in.json": ORDERS.replace(b'"tags": ""', b'"tags": null')})
    assert error.endswith("; the row is record 3 ($.orders[2]) of in.json (id=103)")


def test_line_is_still_named_after_a_normalize(tmp_path):
    data = b"id;name;age\n1;ann;30\n2;bob;4,x1\n"
    doubled = map_config([map_out("row3", [("id", "row2.id", "int"), ("age", "int(row2.age)", "int")])])
    doubled["inputs"]["main"]["name"] = "row2"
    made = chain(("Normalize", {"normalize_column": "age"}, "id:int, name:str, age:str"), ("PyMap", doubled, None),
                 schema="id:int, name:str, age:str", last="id:int, age:int")
    made["components"][2]["schema"] = {"inputs": {"row2": columns("id:int, name:str, age:str")}}
    error = failed(tmp_path, made, {"in.csv": data})
    assert error == ("outputs[0].columns[1].expression: int() could not read 'x1' (in: int(row2.age)); "
                     "1 row failed; the row is line 3 of in.csv (id=2)")
