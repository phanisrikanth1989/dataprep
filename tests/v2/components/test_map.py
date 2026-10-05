"""Map, against v1's PyMap on the same job config and, for a few jobs, against v1's Java tMap.

Where a test runs v2 alone, v1 cannot run the job or gets it wrong; the
comment on the test says how.
"""
import json
import os

import polars as pl
import pytest

from src.v2 import load_job, run_job
from src.v2.components.transform.map_joins import joined_with
from src.v2.errors import JobRefusedError
from tests.v2.answer_key import assert_matches_v1

from .kit import columns, flow, job, reader, writer

JAVA = {"enabled": True, "routines": [], "libraries": []}


# ------------------------------------------------------------------
# Building and running job configs
# ------------------------------------------------------------------

def out(name, cols, **more):
    """One output of a map: ``cols`` is a list of (name, expression, type)."""
    made = {"name": name, "is_reject": False, "inner_join_reject": False, "filter": "", "activate_filter": False,
            "columns": [{"name": n, "expression": e, "type": t, "nullable": True} for n, e, t in cols]}
    made.update(more)
    return made


def lookup(name, keys, **more):
    """One lookup of a map: ``keys`` is a list of (lookup column, expression on the main side)."""
    made = {"name": name, "matching_mode": "UNIQUE_MATCH", "lookup_mode": "LOAD_ONCE", "filter": "",
            "activate_filter": False, "join_mode": "LEFT_OUTER_JOIN",
            "join_keys": [{"lookup_column": c, "expression": e, "type": "str", "nullable": True, "operator": "="}
                          for c, e in keys]}
    made.update(more)
    return made


def config(outputs, lookups=(), variables=(), main_filter=None, **more):
    """A map's config in v1's shape; ``variables`` is a list of (name, expression)."""
    main = {"name": "row1", "filter": main_filter or "", "activate_filter": main_filter is not None}
    made = {"inputs": {"main": main, "lookups": list(lookups)},
            "variables": [{"name": n, "expression": e, "type": "str", "nullable": True} for n, e in variables],
            "outputs": list(outputs)}
    made.update(more)
    return made


def mapping(map_config, sources, sinks, kind="PyMap", context=None, **more):
    """files -> a map -> files.

    ``sources`` maps each flow into the map to its schema shorthand; the flow
    ``row1`` is read from ``row1.csv``. ``sinks`` maps each output to the
    schema its writer declares (None for none); it is written to
    ``<output>.csv``.
    """
    components, flows = [], []
    for name, schema in sources.items():
        components.append(
            reader(schema, component_id=f"in_{name}", path=f"{name}.csv", outputs=(name,), header_rows=1)
        )
        flows.append(flow(name, f"in_{name}", "map"))
    components.append({"id": "map", "type": kind, "config": map_config,
                       "schema": {"inputs": {name: columns(schema) for name, schema in sources.items()}},
                       "inputs": list(sources), "outputs": list(sinks)})
    for name, schema in sinks.items():
        components.append(writer(schema, component_id=f"out_{name}", path=f"{name}.csv", inputs=(name,)))
        flows.append(flow(name, "map", f"out_{name}"))
    made = job(components, flows, **more)
    if context is not None:
        made["context"] = {"Default": context}
    return made


def same(tmp_path, made, inputs, **kwargs):
    """Both engines finish the job and write the same bytes. Returns v2's run."""
    run = assert_matches_v1(made, inputs, tmp_path, **kwargs)
    assert run.succeeded, run.error
    return run


def v2(tmp_path, made, inputs, engine=None):
    """Run on v2 alone, inside tmp_path; returns (result, the files written by name)."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    for name, data in inputs.items():
        (tmp_path / name).write_bytes(data)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = run_job(made, engine=engine)
    finally:
        os.chdir(previous)
    written = {path.name: path.read_bytes() for path in sorted(tmp_path.iterdir()) if path.name not in inputs}
    return result, written


def direct(tmp_path, map_config, sources, sinks, inputs, **more):
    """Run a map job on v2 alone and to the end; returns the files it wrote."""
    result, written = v2(tmp_path, mapping(map_config, sources, sinks, **more), inputs)
    assert result.status == "success", result.error
    return written


def refused(made):
    """What v2 says when it refuses the job at load."""
    with pytest.raises(JobRefusedError) as caught:
        load_job(made)
    return caught.value.report.format()


def declared(cols):
    """The schema shorthand of a writer that declares the columns as the map does."""
    return ", ".join(f"{name}:{kind}" for name, _, kind in cols)


# ------------------------------------------------------------------
# Plain mapping
# ------------------------------------------------------------------

PEOPLE = "id:int, name:str, price:float, qty:int, d:datetime@%Y-%m-%d, flag:bool, amt:Decimal#2"
PEOPLE_DATA = (
    b"id;name;price;qty;d;flag;amt\n"
    b"1;alice;10.5;2;2024-01-31;true;12.50\n"
    b"2;bob;;;;false;\n"
    b"3;;3.25;7;2023-12-01;true;0.10\n"
)
EVERY_COLUMN = [("id", "row1['id']", "int"), ("name", "row1.name", "str"), ("price", "row1['price']", "float"),
                ("qty", "row1.qty", "int"), ("d", "row1.d", "datetime"), ("flag", "row1.flag", "bool"),
                ("amt", "row1.amt", "Decimal")]


def test_every_type_passes_through_with_its_missing_values(tmp_path):
    made = mapping(config([out("o", EVERY_COLUMN)]), {"row1": PEOPLE}, {"o": PEOPLE})
    run = same(tmp_path, made, {"row1.csv": PEOPLE_DATA})
    assert run.files["o.csv"] == PEOPLE_DATA


def test_writer_that_declares_nothing_writes_the_values_as_python_prints_them(tmp_path):
    made = mapping(config([out("o", EVERY_COLUMN)]), {"row1": PEOPLE}, {"o": None})
    same(tmp_path, made, {"row1.csv": PEOPLE_DATA})


def test_columns_are_renamed_reordered_dropped_and_repeated(tmp_path):
    cols = [("label", "row1.name", "str"), ("ident", "row1.id", "int"), ("again", "row1.id", "int")]
    made = mapping(config([out("o", cols)]), {"row1": PEOPLE}, {"o": declared(cols)})
    run = same(tmp_path, made, {"row1.csv": PEOPLE_DATA})
    assert run.files["o.csv"] == b"label;ident;again\nalice;1;1\nbob;2;2\n;3;3\n"


def test_constants_and_columns_without_an_expression(tmp_path):
    cols = [("id", "row1.id", "int"), ("text", "'fixed'", "str"), ("n", "7", "int"), ("f", "1.5", "float"),
            ("yes", "True", "bool"), ("nothing", "None", "str"), ("blank", "", "str"), ("blank_n", "", "int")]
    made = mapping(config([out("o", cols)]), {"row1": PEOPLE}, {"o": declared(cols)})
    run = same(tmp_path, made, {"row1.csv": PEOPLE_DATA})
    assert run.files["o.csv"].splitlines()[1] == b"1;fixed;7;1.5;true;;;"


def test_columns_without_a_declared_type_keep_the_type_of_their_expression(tmp_path):
    made = config([out("o", EVERY_COLUMN)])
    for column in made["outputs"][0]["columns"]:
        del column["type"], column["nullable"]
    run = same(tmp_path, mapping(made, {"row1": PEOPLE}, {"o": PEOPLE}), {"row1.csv": PEOPLE_DATA})
    assert run.files["o.csv"] == PEOPLE_DATA


@pytest.mark.parametrize("die_on_error", [True, False])
def test_die_on_error_changes_nothing_when_no_value_is_unreadable(tmp_path, die_on_error):
    made = mapping(config([out("o", EVERY_COLUMN)], die_on_error=die_on_error), {"row1": PEOPLE}, {"o": PEOPLE})
    assert same(tmp_path, made, {"row1.csv": PEOPLE_DATA}).files["o.csv"] == PEOPLE_DATA


# ------------------------------------------------------------------
# Expressions
# ------------------------------------------------------------------

def computed(tmp_path, cases, schema, data):
    """One output holding ``id`` and a column per (expression, type); both engines agree on it."""
    cols = [("id", "row1.id", "int")] + [(f"c{n}", expr, kind) for n, (expr, kind) in enumerate(cases)]
    made = mapping(config([out("o", cols)]), {"row1": schema}, {"o": declared(cols)})
    return same(tmp_path, made, {"row1.csv": data}).files["o.csv"].decode().splitlines()


STAFF = "id:int, name:str, code:str, price:float, qty:int, flag:bool, amt:Decimal#2"
STAFF_DATA = (
    b"id;name;code;price;qty;flag;amt\n"
    b"1;alice; ab-1 ;10.5;2;true;12.50\n"
    b"2;Bob Lee;XY-22;4;5;false;7\n"
    b"3;carol;zz;3.25;-7;true;0.10\n"
)
TEXT = [
    ("row1.name.upper()", "str"), ("row1.name.lower()", "str"), ("row1.name.title()", "str"),
    ("row1.name.capitalize()", "str"), ("row1.code.strip()", "str"), ("row1.code.lstrip()", "str"),
    ("row1.code.rstrip()", "str"), ("row1['name'] + '-' + row1['code']", "str"),
    ("row1.name + '-' + str(row1.id)", "str"), ("f'{row1.name}:{row1.id}'", "str"), ("len(row1.name)", "int"),
    ("row1.name[0:3]", "str"), ("row1.name[:1]", "str"), ("row1.name[2:]", "str"), ("row1.name[-2:]", "str"),
    ("row1.name.replace('a', 'A')", "str"), ("row1.name.startswith('a')", "bool"), ("'li' in row1.name", "bool"),
    ("row1.name.find('o')", "int"), ("row1.code.strip().split('-')[0]", "str"), ("row1.name.zfill(8)", "str"),
    ("'big' if row1.price > 5 else 'small'", "str"), ("row1.name if row1.flag else row1.code", "str"),
    ("re.sub(r'[aeiou]', '*', row1.name)", "str"), ("row1.name == 'alice'", "bool"),
    ("row1.name in ('alice', 'carol')", "bool"), ("'-'.join([row1.name, row1.code])", "str"),
    ("'{}/{}'.format(row1.name, row1.id)", "str"), ("str(row1.price)", "str"), ("str(row1.flag)", "str"),
]
NUMBERS = [
    ("row1['price'] * 2", "float"), ("row1.qty * 2", "int"), ("row1.price + row1.qty", "float"),
    ("row1.qty - 10", "int"), ("row1.price / row1.qty", "float"), ("row1.qty / 2", "float"),
    ("row1.qty // 2", "int"), ("row1.qty % 3", "int"), ("row1.price // 2", "float"), ("row1.qty ** 2", "int"),
    ("-row1.qty", "int"), ("abs(row1.qty)", "int"), ("round(row1.price)", "int"),
    ("round(row1.price * 1.1, 2)", "float"), ("int(row1.price)", "int"), ("float(row1.qty)", "float"),
    ("max(row1.price, row1.qty)", "float"), ("min(row1.qty, 3)", "int"), ("row1.price > 5", "bool"),
    ("row1.qty == 5", "bool"), ("row1.qty < 0 or row1.price > 10", "bool"), ("not row1.flag", "bool"),
    ("row1.qty if row1.qty > 0 else 0", "int"), ("row1.price * row1.qty if row1.flag else 0.0", "float"),
    ("math.floor(row1.price)", "int"), ("math.sqrt(row1.price)", "float"), ("row1.amt * 2", "Decimal"),
    ("row1.amt + row1.amt", "Decimal"), ("row1.amt > 5", "bool"), ("1 if row1.flag else 0", "int"),
]


def test_text_expressions(tmp_path):
    lines = computed(tmp_path, TEXT, STAFF, STAFF_DATA)
    assert lines[2].split(";")[:5] == ["2", "BOB LEE", "bob lee", "Bob Lee", "Bob lee"]


def test_number_expressions(tmp_path):
    lines = computed(tmp_path, NUMBERS, STAFF, STAFF_DATA)
    assert lines[3].split(";")[:8] == ["3", "6.5", "-14", "-3.75", "-17", "-0.4642857142857143", "-3.5", "-4"]


DATED = "id:int, d:datetime@%Y-%m-%d, e:datetime@%Y-%m-%d %H:%M:%S"
DATED_DATA = (
    b"id;d;e\n"
    b"1;2024-01-31;2024-02-01 10:30:00\n"
    b"2;2024-02-29;2024-03-01 00:00:00\n"
    b"3;2023-12-01;2023-12-31 23:59:59\n"
)
DATES = [
    ("row1.d", "datetime"), ("row1.d.year", "int"), ("row1.d.month", "int"), ("row1.d.day", "int"),
    ("row1.e.hour", "int"), ("(row1.e - row1.d).days", "int"), ("(row1.e - row1.d).total_seconds()", "float"),
    ("row1.d + datetime.timedelta(days=1)", "datetime"), ("row1.d - datetime.timedelta(days=30)", "datetime"),
    ("row1.d > datetime.datetime(2024, 1, 1)", "bool"), ("row1.d < row1.e", "bool"), ("row1.d.weekday()", "int"),
    ("datetime.datetime(2024, 1, 15)", "datetime"), ("row1.d.year * 100 + row1.d.month", "int"),
    ("'Q' + str((row1.d.month - 1) // 3 + 1)", "str"),
]


def test_date_expressions(tmp_path):
    lines = computed(tmp_path, DATES, DATED, DATED_DATA)
    assert lines[1].split(";")[:7] == ["1", "2024-01-31 00:00:00", "2024", "1", "31", "10", "1"]


MISSING = [
    ("row1.price * 2", "float"), ("row1.qty * 2", "int"), ("row1.price + row1.qty", "float"),
    ("row1.price / row1.qty", "float"), ("row1.qty // 2", "int"), ("-row1.qty", "int"),
    ("abs(row1.price)", "float"), ("round(row1.price, 1)", "float"), ("pd.isna(row1.price)", "bool"),
    ("pd.notna(row1.qty)", "bool"), ("pd.isnull(row1.d)", "bool"), ("0 if pd.isna(row1.qty) else row1.qty", "int"),
    ("'none' if pd.isna(row1.price) else 'some'", "str"),
    ("row1.price * 2 if pd.notna(row1.price) else 0.0", "float"),
    ("row1.d + datetime.timedelta(days=1)", "datetime"), ("row1.name + '!'", "str"), ("len(row1.name)", "int"),
    ("row1.name or 'none'", "str"), ("row1.amt * 2", "Decimal"), ("row1.price > 5 or row1.id == 2", "bool"),
    ("not (row1.price > 5)", "bool"), ("row1.price > 100 or pd.isna(row1.price)", "bool"),
]


def test_expressions_over_missing_values(tmp_path):
    lines = computed(tmp_path, MISSING, PEOPLE, PEOPLE_DATA)
    assert lines[2].split(";")[:10] == ["2", "", "", "", "", "", "", "", "", "true"]


def test_part_of_a_date_stays_whole_beside_a_missing_date(tmp_path):
    # v1 writes 2024.0: one missing date turns the whole column into floats.
    cols = [("id", "row1.id", "int"), ("y", "row1.d.year", "int")]
    files = direct(tmp_path, config([out("o", cols)]), {"row1": PEOPLE}, {"o": declared(cols)},
                   {"row1.csv": PEOPLE_DATA})
    assert files["o.csv"] == b"id;y\n1;2024\n2;\n3;2023\n"


def test_whole_numbers_stay_whole_when_every_column_is_a_number(tmp_path):
    # v1's PyMap reads a row of numbers only as floats and writes 1.0 for the id.
    cols = [("id", "row1.id", "int"), ("twice", "row1.price * 2", "float")]
    files = direct(tmp_path, config([out("o", cols)]), {"row1": "id:int, price:float"}, {"o": declared(cols)},
                   {"row1.csv": b"id;price\n1;1.5\n2;4\n"})
    assert files["o.csv"] == b"id;twice\n1;3.0\n2;8.0\n"


# ------------------------------------------------------------------
# Output filters and reject outputs
# ------------------------------------------------------------------

ITEMS = "id:int, name:str, price:float"
ITEMS_DATA = b"id;name;price\n1;alice;10.5\n2;bob;4\n3;carol;\n4;dave;1\n"
ITEM_COLUMNS = [("id", "row1.id", "int"), ("name", "row1.name", "str"), ("price", "row1.price", "float")]
DEAR = {"filter": "row1.price > 3", "activate_filter": True}


def items(tmp_path, outputs, **kwargs):
    """A map over the items, every output written with the items' own columns; both engines agree."""
    made = mapping(config(outputs, **kwargs), {"row1": ITEMS}, {output["name"]: ITEMS for output in outputs})
    return same(tmp_path, made, {"row1.csv": ITEMS_DATA}).files


def test_output_filter_keeps_the_rows_that_match(tmp_path):
    files = items(tmp_path, [out("o", ITEM_COLUMNS, **DEAR)])
    assert files["o.csv"] == b"id;name;price\n1;alice;10.5\n2;bob;4.0\n"


def test_output_filter_that_is_not_activated_is_not_applied(tmp_path):
    files = items(tmp_path, [out("o", ITEM_COLUMNS, filter="row1.price > 3", activate_filter=False)])
    assert files["o.csv"].count(b"\n") == 5


def test_activated_filter_that_is_empty_keeps_every_row(tmp_path):
    files = items(tmp_path, [out("o", ITEM_COLUMNS, filter="", activate_filter=True)])
    assert files["o.csv"].count(b"\n") == 5


@pytest.mark.parametrize(
    "condition",
    ["row1.price > 3", "pd.isna(row1.price)", "not (row1.price > 3)", "row1.price != 4", "row1.name",
     "row1.name == 'bob' or row1.id > 3", "row1.id % 2 == 0 and row1.price < 5", "row1.id"],
)
def test_filter_conditions_follow_python_truth(tmp_path, condition):
    items(tmp_path, [out("o", ITEM_COLUMNS, filter=condition, activate_filter=True),
                     out("rej", ITEM_COLUMNS, is_reject=True)])


def test_reject_output_takes_the_rows_the_filter_turned_away(tmp_path):
    files = items(tmp_path, [out("o", ITEM_COLUMNS, **DEAR), out("rej", ITEM_COLUMNS, is_reject=True)])
    assert files["rej.csv"] == b"id;name;price\n3;carol;\n4;dave;1.0\n"


def test_reject_output_as_the_converter_writes_it(tmp_path):
    # The converter sets catch_output_reject beside is_reject. v1's Java tMap then sends the output only
    # rows whose expressions failed; PyMap and v2 send it the rows the filter turned away.
    files = items(tmp_path, [out("o", ITEM_COLUMNS, **DEAR),
                             out("rej", ITEM_COLUMNS, is_reject=True, catch_output_reject=True)])
    assert files["rej.csv"] == b"id;name;price\n3;carol;\n4;dave;1.0\n"


def test_reject_output_listed_before_the_output_it_serves(tmp_path):
    files = items(tmp_path, [out("rej", ITEM_COLUMNS, is_reject=True), out("o", ITEM_COLUMNS, **DEAR)])
    assert files["rej.csv"] == b"id;name;price\n3;carol;\n4;dave;1.0\n"


def test_reject_output_is_an_empty_file_when_nothing_is_rejected(tmp_path):
    files = items(tmp_path, [out("o", ITEM_COLUMNS, filter="row1.id > 0", activate_filter=True),
                             out("rej", ITEM_COLUMNS, is_reject=True)])
    assert files["rej.csv"] == b"id;name;price\n"


def test_reject_output_takes_every_row_when_the_filter_takes_none(tmp_path):
    files = items(tmp_path, [out("o", ITEM_COLUMNS, filter="row1.id > 100", activate_filter=True),
                             out("rej", ITEM_COLUMNS, is_reject=True)])
    assert files["o.csv"] == b"id;name;price\n" and files["rej.csv"].count(b"\n") == 5


def test_several_outputs_each_with_its_own_columns_and_filter(tmp_path):
    cheap = [("id", "row1.id", "int"), ("half", "row1.price / 2", "float")]
    names = [("name", "row1.name.upper()", "str")]
    outputs = [out("cheap", cheap, filter="row1.price < 5", activate_filter=True), out("names", names),
               out("dear", ITEM_COLUMNS, filter="row1.price >= 5", activate_filter=True)]
    made = mapping(config(outputs), {"row1": ITEMS},
                   {"cheap": declared(cheap), "names": declared(names), "dear": ITEMS})
    files = same(tmp_path, made, {"row1.csv": ITEMS_DATA}).files
    assert files["cheap.csv"] == b"id;half\n2;2.0\n4;0.5\n"
    assert files["names.csv"] == b"name\nALICE\nBOB\nCAROL\nDAVE\n"
    assert files["dear.csv"] == b"id;name;price\n1;alice;10.5\n"


def test_reject_output_computes_its_own_columns(tmp_path):
    # v1's PyMap hands the reject output the rejecting output's columns instead.
    reasons = [("ident", "row1.id", "int"), ("why", "'low: ' + row1.name", "str")]
    files = direct(tmp_path, config([out("o", ITEM_COLUMNS, **DEAR), out("rej", reasons, is_reject=True)]),
                   {"row1": ITEMS}, {"o": ITEMS, "rej": declared(reasons)}, {"row1.csv": ITEMS_DATA})
    assert files["rej.csv"] == b"ident;why\n3;low: carol\n4;low: dave\n"


def test_reject_outputs_take_only_the_rows_no_output_took(tmp_path):
    # v1's PyMap sends a row to the first reject output only, once for every output that turned it away.
    outputs = [out("o", ITEM_COLUMNS, **DEAR), out("p", ITEM_COLUMNS, filter="row1.price < 2", activate_filter=True),
               out("rej", ITEM_COLUMNS, is_reject=True), out("rej2", [("id", "row1.id", "int")], is_reject=True)]
    files = direct(tmp_path, config(outputs), {"row1": ITEMS},
                   {"o": ITEMS, "p": ITEMS, "rej": ITEMS, "rej2": "id:int"}, {"row1.csv": ITEMS_DATA})
    assert files["p.csv"] == b"id;name;price\n4;dave;1.0\n"
    assert files["rej.csv"] == b"id;name;price\n3;carol;\n"
    assert files["rej2.csv"] == b"id\n3\n"


def test_output_that_no_flow_carries_still_takes_its_rows_from_the_reject_output(tmp_path):
    outputs = [out("o", ITEM_COLUMNS, **DEAR),
               out("unwired", ITEM_COLUMNS, filter="row1.price < 2", activate_filter=True),
               out("rej", ITEM_COLUMNS, is_reject=True)]
    files = direct(tmp_path, config(outputs), {"row1": ITEMS}, {"o": ITEMS, "rej": ITEMS}, {"row1.csv": ITEMS_DATA})
    assert files == {"o.csv": b"id;name;price\n1;alice;10.5\n2;bob;4.0\n", "rej.csv": b"id;name;price\n3;carol;\n"}


def test_reject_output_is_empty_when_an_output_without_a_filter_takes_every_row(tmp_path):
    # v1's PyMap fills it with the rows the filtered output turned away all the same.
    outputs = [out("o", ITEM_COLUMNS, **DEAR), out("all", ITEM_COLUMNS), out("rej", ITEM_COLUMNS, is_reject=True)]
    files = direct(tmp_path, config(outputs), {"row1": ITEMS}, {"o": ITEMS, "all": ITEMS, "rej": ITEMS},
                   {"row1.csv": ITEMS_DATA})
    assert files["rej.csv"] == b"id;name;price\n"


def test_reject_output_alone_takes_every_row_and_its_own_filter_is_not_read(tmp_path):
    # v1's PyMap leaves a reject output empty when no other output has a filter.
    for number, condition in enumerate(["row1.id > 3", "row1.no_such_column > 3"]):
        outputs = [out("rej", ITEM_COLUMNS, is_reject=True, filter=condition, activate_filter=True)]
        files = direct(tmp_path / str(number), config(outputs), {"row1": ITEMS}, {"rej": ITEMS},
                       {"row1.csv": ITEMS_DATA})
        assert files["rej.csv"].count(b"\n") == 5


# ------------------------------------------------------------------
# The main input: its filter, and no rows at all
# ------------------------------------------------------------------

@pytest.mark.parametrize("condition", ["row1.price > 3", "price > 3 and name != 'alice'", "row1['id'] in (1, 4)"])
def test_main_filter_decides_which_rows_are_mapped_at_all(tmp_path, condition):
    outputs = [out("o", ITEM_COLUMNS, filter="row1.id < 4", activate_filter=True),
               out("rej", ITEM_COLUMNS, is_reject=True)]
    items(tmp_path, outputs, main_filter=condition)


def test_main_filter_that_is_not_activated_is_not_applied(tmp_path):
    made = config([out("o", ITEM_COLUMNS)], main_filter="row1.price > 3")
    made["inputs"]["main"]["activate_filter"] = False
    run = same(tmp_path, mapping(made, {"row1": ITEMS}, {"o": ITEMS}), {"row1.csv": ITEMS_DATA})
    assert run.files["o.csv"].count(b"\n") == 5


def test_main_filter_that_takes_no_row_leaves_every_output_empty(tmp_path):
    files = items(tmp_path, [out("o", ITEM_COLUMNS), out("rej", ITEM_COLUMNS, is_reject=True)],
                  main_filter="row1.price > 300")
    assert files == {"o.csv": b"id;name;price\n", "rej.csv": b"id;name;price\n"}


def test_main_input_without_rows_gives_empty_outputs(tmp_path):
    outputs = [out("o", ITEM_COLUMNS, **DEAR), out("rej", ITEM_COLUMNS, is_reject=True)]
    made = mapping(config(outputs), {"row1": ITEMS}, {"o": ITEMS, "rej": ITEMS})
    run = same(tmp_path, made, {"row1.csv": b"id;name;price\n"})
    assert run.files == {"o.csv": b"id;name;price\n", "rej.csv": b"id;name;price\n"}


def test_flow_the_config_does_not_name_is_left_alone(tmp_path):
    made = mapping(config([out("o", ITEM_COLUMNS)]), {"row1": ITEMS, "row9": "x:str"}, {"o": ITEMS})
    run = same(tmp_path, made, {"row1.csv": ITEMS_DATA, "row9.csv": b"x\nunused\n"})
    assert run.files["o.csv"].count(b"\n") == 5


# ------------------------------------------------------------------
# Variables
# ------------------------------------------------------------------

def test_variables_build_on_each_other_and_feed_columns_and_filters(tmp_path):
    cols = [("id", "row1.id", "int"), ("total", "Var['total']", "float"), ("taxed", "Var['taxed']", "float"),
            ("label", "Var['label']", "str")]
    variables = [("total", "row1.price * row1.id"), ("taxed", "Var['total'] * 2"),
                 ("label", "row1.name.upper() + '!'")]
    outputs = [out("o", cols, filter="Var['total'] > 5", activate_filter=True), out("rej", cols, is_reject=True)]
    made = mapping(config(outputs, variables=variables), {"row1": ITEMS}, {"o": declared(cols), "rej": declared(cols)})
    files = same(tmp_path, made, {"row1.csv": ITEMS_DATA}).files
    assert files["o.csv"] == b"id;total;taxed;label\n1;10.5;21.0;ALICE!\n2;8.0;16.0;BOB!\n"
    assert files["rej.csv"] == b"id;total;taxed;label\n3;;;CAROL!\n4;4.0;8.0;DAVE!\n"


def test_variable_declared_type_is_not_applied(tmp_path):
    cols = [("id", "row1.id", "int"), ("v", "Var['v']", "float")]
    made = config([out("o", cols)], variables=[("v", "row1.price * 2")])
    made["variables"][0]["type"] = "int"
    run = same(tmp_path, mapping(made, {"row1": ITEMS}, {"o": declared(cols)}), {"row1.csv": ITEMS_DATA})
    assert run.files["o.csv"] == b"id;v\n1;21.0\n2;8.0\n3;\n4;2.0\n"


def test_variables_can_be_read_as_attributes(tmp_path):
    # v1's PyMap holds the variables in a dict, so there only Var['total'] works.
    cols = [("id", "row1.id", "int"), ("total", "Var.total", "float")]
    made = config([out("o", cols, filter="Var.total > 5", activate_filter=True)],
                  variables=[("total", "row1.price * 2")])
    files = direct(tmp_path, made, {"row1": ITEMS}, {"o": declared(cols)}, {"row1.csv": ITEMS_DATA})
    assert files["o.csv"] == b"id;total\n1;21.0\n2;8.0\n"


def test_variable_defined_twice_is_read_as_last_defined_above_the_reader(tmp_path):
    cols = [("v", "Var.v", "int"), ("w", "Var.w", "int")]
    made = config([out("o", cols)], variables=[("v", "row1.id * 10"), ("w", "Var.v + 1"), ("v", "Var.v + 5")])
    files = direct(tmp_path, made, {"row1": ITEMS}, {"o": declared(cols)}, {"row1.csv": ITEMS_DATA})
    assert files["o.csv"] == b"v;w\n15;11\n25;21\n35;31\n45;41\n"


def test_variable_without_an_expression_is_a_missing_value(tmp_path):
    # v1's PyMap does not define such a variable at all, and reading it fails the job.
    cols = [("id", "row1.id", "int"), ("v", "Var.v", "str")]
    files = direct(tmp_path, config([out("o", cols)], variables=[("v", "")]), {"row1": ITEMS}, {"o": declared(cols)},
                   {"row1.csv": ITEMS_DATA})
    assert files["o.csv"] == b"id;v\n1;\n2;\n3;\n4;\n"


def test_variable_that_is_not_defined_yet_is_refused():
    made = config([out("o", [("v", "Var.later", "int")])], variables=[("v", "Var.later + 1"), ("later", "1")])
    said = refused(mapping(made, {"row1": ITEMS}, {"o": "v:int"}))
    assert "variables[0].expression: `Var.later`: no variable 'later' is defined before this expression" in said


# ------------------------------------------------------------------
# Lookups
# ------------------------------------------------------------------

ORDERS = "id:int, name:str, code:str, price:float"
ORDERS_DATA = b"id;name;code;price\n1;alice;A;10.5\n2;bob;B;4\n3;carol;;3.25\n4;dave;Z;1\n5;erin;A;2\n"
CODES = "code:str, label:str, rate:float, n:int"
CODES_DATA = (
    b"code;label;rate;n\nA;first-A;1.5;10\nB;only-B;2.5;20\nA;second-A;3.5;30\nC;unused;9;90\n;empty-key;7;70\n"
)
JOINED_COLUMNS = [("id", "row1.id", "int"), ("name", "row1.name", "str"), ("label", "row2.label", "str"),
                  ("rate", "row2['rate']", "float"), ("n", "row2.n", "int")]
JOINED = declared(JOINED_COLUMNS)
BY_CODE = [("code", "row1.code")]
TWO = {"row1": ORDERS, "row2": CODES}
TWO_DATA = {"row1.csv": ORDERS_DATA, "row2.csv": CODES_DATA}


def joined(tmp_path, lookups, outputs=None, sinks=None, inputs=None, **kwargs):
    """The orders (row1) with the codes (row2) looked up; both engines agree."""
    made = config(outputs or [out("o", JOINED_COLUMNS)], lookups=lookups, **kwargs)
    return same(tmp_path, mapping(made, TWO, sinks or {"o": JOINED}), inputs or TWO_DATA).files


def joined_direct(tmp_path, lookups, outputs=None, sinks=None, inputs=None, context=None, **kwargs):
    """The same job as ``joined``, on v2 alone."""
    made = config(outputs or [out("o", JOINED_COLUMNS)], lookups=lookups, **kwargs)
    return direct(tmp_path, made, TWO, sinks or {"o": JOINED}, inputs or TWO_DATA, context=context)


@pytest.mark.parametrize(
    "mode, alice",
    [("UNIQUE_MATCH", [b"1;alice;second-A;3.5;30"]), ("FIRST_MATCH", [b"1;alice;first-A;1.5;10"]),
     ("LAST_MATCH", [b"1;alice;second-A;3.5;30"]),
     ("ALL_MATCHES", [b"1;alice;first-A;1.5;10", b"1;alice;second-A;3.5;30"])],
)
def test_left_join_by_matching_mode(tmp_path, mode, alice):
    lines = joined(tmp_path, [lookup("row2", BY_CODE, matching_mode=mode)])["o.csv"].splitlines()
    assert lines[1:1 + len(alice)] == alice
    assert lines[-2:] == ([b"4;dave;;;"] + [line.replace(b"1;alice", b"5;erin") for line in alice])[-2:]


def test_left_join_matches_an_empty_text_key_and_leaves_unmatched_rows_in_place(tmp_path):
    files = joined(tmp_path, [lookup("row2", BY_CODE)])
    assert files["o.csv"] == (
        b"id;name;label;rate;n\n1;alice;second-A;3.5;30\n2;bob;only-B;2.5;20\n3;carol;empty-key;7.0;70\n"
        b"4;dave;;;\n5;erin;second-A;3.5;30\n"
    )


def test_matching_mode_defaults_to_the_last_match_and_join_mode_to_left(tmp_path):
    plain = {"name": "row2", "join_keys": [{"lookup_column": "code", "expression": "row1.code"}],
             "join_mode": "LEFT_OUTER_JOIN"}
    files = joined(tmp_path, [plain])
    assert files["o.csv"].splitlines()[1] == b"1;alice;second-A;3.5;30"
    # v1's PyMap refuses a lookup that does not say its join mode; its Java tMap takes it for a left join.
    del plain["join_mode"]
    assert joined_direct(tmp_path / "no-join-mode", [plain]) == files


def test_join_on_several_keys(tmp_path):
    cols = [("id", "row1.id", "int"), ("v", "row2.v", "str")]
    made = mapping(config([out("o", cols)], lookups=[lookup("row2", [("a", "row1.a"), ("b", "row1.b")])]),
                   {"row1": "id:int, a:str, b:str", "row2": "a:str, b:str, v:str"}, {"o": declared(cols)})
    run = same(tmp_path, made, {"row1.csv": b"id;a;b\n1;x;y\n2;x;z\n3;y;x\n4;x;\n",
                                "row2.csv": b"a;b;v\nx;y;xy\nx;z;xz-old\nx;z;xz\nx;;x-\n"})
    assert run.files["o.csv"] == b"id;v\n1;xy\n2;xz\n3;\n4;x-\n"


def test_lookup_without_rows_leaves_its_columns_missing(tmp_path):
    files = joined(tmp_path, [lookup("row2", BY_CODE)],
                   inputs={"row1.csv": ORDERS_DATA, "row2.csv": b"code;label;rate;n\n"})
    assert files["o.csv"].splitlines()[1:3] == [b"1;alice;;;", b"2;bob;;;"]


def test_main_input_without_rows_with_a_lookup(tmp_path):
    files = joined(tmp_path, [lookup("row2", BY_CODE)],
                   inputs={"row1.csv": b"id;name;code;price\n", "row2.csv": CODES_DATA})
    assert files["o.csv"] == b"id;name;label;rate;n\n"


def test_lookup_columns_feed_expressions_filters_and_variables(tmp_path):
    cols = [("id", "row1.id", "int"), ("cost", "Var['cost']", "float"),
            ("tag", "row1.name + '/' + row2.label", "str")]
    outputs = [out("o", cols, filter="row2.rate > 2 and Var['cost'] < 30", activate_filter=True),
               out("rej", cols, is_reject=True)]
    files = joined(tmp_path, [lookup("row2", BY_CODE, matching_mode="FIRST_MATCH")], outputs,
                   {"o": declared(cols), "rej": declared(cols)},
                   inputs={"row1.csv": b"id;name;code;price\n1;alice;A;10.5\n2;bob;B;4\n5;erin;C;2\n",
                           "row2.csv": CODES_DATA},
                   variables=[("cost", "row1.price * row2.rate")])
    assert files["o.csv"] == b"id;cost;tag\n2;10.0;bob/only-B\n5;18.0;erin/unused\n"
    assert files["rej.csv"] == b"id;cost;tag\n1;15.75;alice/first-A\n"


def test_outputs_of_maps_feed_another_map_as_its_main_input_and_as_a_lookup(tmp_path):
    def step(component_id, settings, inputs, outputs):
        return {"id": component_id, "type": "PyMap", "config": settings, "schema": {}, "inputs": inputs,
                "outputs": outputs}

    doubled = [("id", "row1.id", "int"), ("name", "row1.name", "str"), ("code", "row1.code", "str"),
               ("twice", "row1.price * 2", "float")]
    tidy = [("code", "row2.code", "str"), ("label", "row2.label.upper()", "str"), ("rate", "row2.rate", "float")]
    costed = [("id", "big.id", "int"), ("label", "tidy.label", "str"), ("cost", "big.twice * tidy.rate", "float")]
    lost = [("id", "big.id", "int"), ("name", "big.name", "str")]
    split = config([out("big", doubled, filter="row1.price > 1.5", activate_filter=True),
                    out("small", doubled, is_reject=True)])
    cleaned = config([out("tidy", tidy, filter="row2.rate < 9", activate_filter=True)])
    cleaned["inputs"]["main"]["name"] = "row2"
    priced = config([out("o", costed), out("lost", lost, inner_join_reject=True)],
                    lookups=[lookup("tidy", [("code", "big.code")], matching_mode="FIRST_MATCH", **INNER)])
    priced["inputs"]["main"]["name"] = "big"
    made = job(
        [reader(ORDERS, component_id="in1", path="row1.csv", outputs=("row1",), header_rows=1),
         reader(CODES, component_id="in2", path="row2.csv", outputs=("row2",), header_rows=1),
         step("split", split, ["row1"], ["big", "small"]), step("clean", cleaned, ["row2"], ["tidy"]),
         step("price", priced, ["big", "tidy"], ["o", "lost"]),
         writer(declared(costed), component_id="w1", path="o.csv", inputs=("o",)),
         writer(declared(lost), component_id="w2", path="lost.csv", inputs=("lost",)),
         writer(declared(doubled), component_id="w3", path="small.csv", inputs=("small",))],
        [flow("row1", "in1", "split"), flow("row2", "in2", "clean"), flow("big", "split", "price"),
         flow("tidy", "clean", "price"), flow("o", "price", "w1"), flow("lost", "price", "w2"),
         flow("small", "split", "w3")],
    )
    files = same(tmp_path, made, TWO_DATA).files
    assert files["o.csv"] == b"id;label;cost\n1;FIRST-A;31.5\n2;ONLY-B;20.0\n3;EMPTY-KEY;45.5\n5;FIRST-A;6.0\n"
    assert files["small.csv"] == b"id;name;code;twice\n4;dave;Z;2.0\n" and files["lost.csv"] == b"id;name\n"


EVERY_TYPE = "k:str, n:int, f:float, d:datetime@%Y-%m-%d, b:bool, m:Decimal#2, s:str"
EVERY_TYPE_DATA = b"k;n;f;d;b;m;s\nA;10;1.5;2024-01-31;true;12.50;x\nB;20;2;2024-02-01;false;7;y\n"
EVERY_TYPE_COLUMNS = [("id", "row1.id", "int"), ("n", "row2.n", "int"), ("f", "row2.f", "float"),
                      ("d", "row2.d", "datetime"), ("b", "row2.b", "bool"), ("m", "row2.m", "Decimal"),
                      ("s", "row2.s", "str")]


def test_lookup_columns_of_every_type_are_missing_on_an_unmatched_row(tmp_path):
    made = mapping(config([out("o", EVERY_TYPE_COLUMNS)], lookups=[lookup("row2", [("k", "row1.k")])]),
                   {"row1": "id:int, k:str", "row2": EVERY_TYPE}, {"o": "id:int" + EVERY_TYPE[5:]})
    run = same(tmp_path, made, {"row1.csv": b"id;k\n1;A\n2;B\n3;Q\n", "row2.csv": EVERY_TYPE_DATA})
    assert run.files["o.csv"] == (
        b"id;n;f;d;b;m;s\n1;10;1.5;2024-01-31;true;12.50;x\n2;20;2.0;2024-02-01;false;7.00;y\n3;;;;;;\n"
    )


def test_whole_numbers_of_a_lookup_stay_whole_beside_an_unmatched_row(tmp_path):
    # v1 writes 10.0 and 20.0: its lookup column may not hold a missing value, so the unmatched row
    # turns the whole column into floats.
    made = config([out("o", EVERY_TYPE_COLUMNS[:2])], lookups=[lookup("row2", [("k", "row1.k")])])
    files = direct(tmp_path, made, {"row1": "id:int, k:str", "row2": EVERY_TYPE.replace("n:int", "n:int!")},
                   {"o": "id:int, n:int"}, {"row1.csv": b"id;k\n1;A\n2;B\n3;Q\n", "row2.csv": EVERY_TYPE_DATA})
    assert files["o.csv"] == b"id;n\n1;10\n2;20\n3;\n"


# ------------------------------------------------------------------
# Inner joins and their rejects
# ------------------------------------------------------------------

MISSES = [("id", "row1.id", "int"), ("name", "row1.name", "str"), ("code", "row1.code", "str")]
MISSED = declared(MISSES)
WITH_REJECTS = [out("o", JOINED_COLUMNS), out("rej", MISSES, inner_join_reject=True)]
BOTH = {"o": JOINED, "rej": MISSED}
INNER = {"join_mode": "INNER_JOIN"}


@pytest.mark.parametrize("mode", ["UNIQUE_MATCH", "FIRST_MATCH", "LAST_MATCH", "ALL_MATCHES"])
def test_inner_join_by_matching_mode(tmp_path, mode):
    files = joined(tmp_path, [lookup("row2", BY_CODE, matching_mode=mode, **INNER)], WITH_REJECTS, BOTH)
    assert files["rej.csv"] == b"id;name;code\n4;dave;Z\n"
    assert b"dave" not in files["o.csv"] and files["o.csv"].count(b"\n") == (7 if mode == "ALL_MATCHES" else 5)


def test_inner_join_drops_unmatched_rows_when_no_output_catches_them(tmp_path):
    files = joined(tmp_path, [lookup("row2", BY_CODE, **INNER)])
    assert files["o.csv"] == (
        b"id;name;label;rate;n\n1;alice;second-A;3.5;30\n2;bob;only-B;2.5;20\n3;carol;empty-key;7.0;70\n"
        b"5;erin;second-A;3.5;30\n"
    )


def test_inner_join_reject_output_is_empty_when_every_row_matches(tmp_path):
    files = joined(tmp_path, [lookup("row2", BY_CODE, **INNER)], WITH_REJECTS, BOTH,
                   inputs={"row1.csv": b"id;name;code;price\n1;alice;A;10.5\n2;bob;B;4\n", "row2.csv": CODES_DATA})
    assert files["rej.csv"] == b"id;name;code\n"


def test_inner_join_reject_output_is_empty_when_no_lookup_is_an_inner_join(tmp_path):
    files = joined(tmp_path, [lookup("row2", BY_CODE)], WITH_REJECTS, BOTH)
    assert files["rej.csv"] == b"id;name;code\n" and files["o.csv"].count(b"\n") == 6


def test_filter_rejects_and_inner_join_rejects_go_to_their_own_outputs(tmp_path):
    outputs = [out("o", JOINED_COLUMNS, filter="row2.rate > 3", activate_filter=True),
               out("low", JOINED_COLUMNS, is_reject=True), out("rej", MISSES, inner_join_reject=True)]
    files = joined(tmp_path, [lookup("row2", BY_CODE, **INNER)], outputs, {"o": JOINED, "low": JOINED, "rej": MISSED})
    assert files["low.csv"] == b"id;name;label;rate;n\n2;bob;only-B;2.5;20\n"
    assert files["rej.csv"] == b"id;name;code\n4;dave;Z\n"
    assert files["o.csv"].count(b"\n") == 4


def test_lookup_whose_filter_takes_no_row_rejects_every_main_row_of_an_inner_join(tmp_path):
    files = joined(tmp_path, [lookup("row2", BY_CODE, filter="row2.rate > 100", activate_filter=True, **INNER)],
                   WITH_REJECTS, BOTH)
    assert files["o.csv"] == b"id;name;label;rate;n\n" and files["rej.csv"].count(b"\n") == 6


def test_inner_join_reject_output_computes_its_own_columns_and_applies_its_filter(tmp_path):
    # v1's PyMap copies the columns of that name from the main row and reads no expression and no filter.
    reasons = [("ident", "row1.id * 10", "int"), ("who", "row1.name.upper()", "str"),
               ("why", "'no code ' + row1.code", "str"), ("label", "row2.label", "str")]
    outputs = [out("o", JOINED_COLUMNS),
               out("rej", reasons, inner_join_reject=True, filter="row1.id != 3", activate_filter=True)]
    files = joined_direct(
        tmp_path, [lookup("row2", BY_CODE, **INNER)], outputs, {"o": JOINED, "rej": declared(reasons)},
        inputs={"row1.csv": b"id;name;code;price\n1;alice;A;1\n3;carol;Q;1\n4;dave;Z;1\n", "row2.csv": CODES_DATA},
    )
    assert files["rej.csv"] == b"ident;who;why;label\n40;DAVE;no code Z;\n"


def test_inner_join_on_a_lookup_without_rows_rejects_every_main_row(tmp_path):
    # v1's PyMap skips a lookup that has no rows and so keeps every main row.
    files = joined_direct(tmp_path, [lookup("row2", BY_CODE, **INNER)], WITH_REJECTS, BOTH,
                          inputs={"row1.csv": ORDERS_DATA, "row2.csv": b"code;label;rate;n\n"})
    assert files["o.csv"] == b"id;name;label;rate;n\n"
    assert files["rej.csv"] == b"id;name;code\n1;alice;A\n2;bob;B\n3;carol;\n4;dave;Z\n5;erin;A\n"


def test_output_that_is_both_kinds_of_reject_takes_both_kinds(tmp_path):
    # v1's Java tMap crashes on such an output; its PyMap gives it the inner-join rejects only.
    outputs = [out("o", JOINED_COLUMNS, filter="row2.rate > 3", activate_filter=True),
               out("rej", MISSES, is_reject=True, inner_join_reject=True)]
    files = joined_direct(tmp_path / "inner", [lookup("row2", BY_CODE, **INNER)], outputs, BOTH)
    assert files["rej.csv"] == b"id;name;code\n2;bob;B\n4;dave;Z\n"
    files = joined_direct(tmp_path / "left", [lookup("row2", BY_CODE)], outputs, BOTH)
    assert files["rej.csv"] == b"id;name;code\n2;bob;B\n4;dave;Z\n"
    outputs[0] = out("o", JOINED_COLUMNS)
    files = joined_direct(tmp_path / "all-taken", [lookup("row2", BY_CODE, **INNER)], outputs, BOTH)
    assert files["rej.csv"] == b"id;name;code\n4;dave;Z\n"


@pytest.mark.parametrize("pets, later", [(b"dave;cat\ndave;dog\nbob;fish\nbob;bird\n", [("name", "row1.name")]),
                                         (b"x;cat\ny;dog\n", [])])
def test_row_an_inner_join_missed_is_joined_to_no_later_lookup(tmp_path, pets, later):
    # In v1 too the row leaves when the inner join misses it; v1's PyMap cannot key a lookup on nothing.
    lookups = [lookup("row2", BY_CODE, **INNER), lookup("row3", later, matching_mode="ALL_MATCHES")]
    cols = [("id", "row1.id", "int"), ("label", "row2.label", "str"), ("pet", "row3.pet", "str")]
    files = direct(
        tmp_path, config([out("o", cols), out("rej", cols, inner_join_reject=True)], lookups=lookups),
        {"row1": ORDERS, "row2": CODES, "row3": "name:str, pet:str"}, {"o": declared(cols), "rej": declared(cols)},
        {"row1.csv": ORDERS_DATA, "row2.csv": CODES_DATA, "row3.csv": b"name;pet\n" + pets},
    )
    assert files["rej.csv"] == b"id;label;pet\n4;;\n"
    if later:
        assert files["o.csv"] == (
            b"id;label;pet\n1;second-A;\n2;only-B;fish\n2;only-B;bird\n3;empty-key;\n5;second-A;\n"
        )
    else:
        assert files["o.csv"].splitlines()[1:3] == [b"1;second-A;cat", b"1;second-A;dog"]


# ------------------------------------------------------------------
# Several lookups, and what a key can be
# ------------------------------------------------------------------

REGIONS = "region:str, zone:str"
REGIONS_DATA = b"region;zone\nnorth;N1\nsouth;S1\n"
PLACES = "code:str, label:str, region:str"
PLACES_DATA = b"code;label;region\nA;la;north\nB;lb;south\nC;lc;west\n"
PLACED_COLUMNS = [("id", "row1.id", "int"), ("label", "row2.label", "str"), ("zone", "row3.zone", "str")]
PLACED = declared(PLACED_COLUMNS)
NAMES = [("id", "row1.id", "int"), ("name", "row1.name", "str")]
# The rows that find no match come last, where v1 moves them anyway.
PLACED_ORDERS = b"id;name;code;price\n1;alice;A;10.5\n2;bob;B;4\n4;dave;C;1\n3;carol;Q;3.25\n"
BY_REGION = [("region", "row2.region")]


def placed(lookups, outputs=None, sinks=None):
    """The orders with their place (row2) looked up, and the place's region (row3)."""
    return mapping(config(outputs or [out("o", PLACED_COLUMNS)], lookups=lookups),
                   {"row1": ORDERS, "row2": PLACES, "row3": REGIONS}, sinks or {"o": PLACED})


def placed_data(orders=PLACED_ORDERS):
    return {"row1.csv": orders, "row2.csv": PLACES_DATA, "row3.csv": REGIONS_DATA}


def test_lookup_keyed_on_a_column_of_an_earlier_lookup(tmp_path):
    run = same(tmp_path, placed([lookup("row2", BY_CODE), lookup("row3", BY_REGION)]), placed_data())
    assert run.files["o.csv"] == b"id;label;zone\n1;la;N1\n2;lb;S1\n4;lc;\n3;;\n"


def test_inner_join_on_a_lookup_keyed_on_an_earlier_lookup(tmp_path):
    made = placed([lookup("row2", BY_CODE), lookup("row3", BY_REGION, **INNER)],
                  [out("o", PLACED_COLUMNS), out("rej", NAMES, inner_join_reject=True)],
                  {"o": PLACED, "rej": declared(NAMES)})
    assert same(tmp_path, made, placed_data()).files["rej.csv"] == b"id;name\n4;dave\n3;carol\n"


def test_two_inner_joins_reject_the_rows_either_one_missed(tmp_path):
    made = placed([lookup("row2", BY_CODE, **INNER), lookup("row3", BY_REGION, **INNER)],
                  [out("o", PLACED_COLUMNS), out("rej", NAMES, inner_join_reject=True)],
                  {"o": PLACED, "rej": declared(NAMES)})
    files = same(tmp_path, made, placed_data(b"id;name;code;price\n1;alice;A;10.5\n3;carol;Q;3.25\n4;dave;C;1\n")).files
    assert files["o.csv"] == b"id;label;zone\n1;la;N1\n" and files["rej.csv"] == b"id;name\n3;carol\n4;dave\n"


def test_two_lookups_each_keyed_on_the_main_row(tmp_path):
    lookups = [lookup("row2", BY_CODE, matching_mode="ALL_MATCHES"),
               lookup("row3", [("region", "row1.name")], matching_mode="ALL_MATCHES")]
    made = mapping(config([out("o", PLACED_COLUMNS)], lookups=lookups),
                   {"row1": ORDERS, "row2": CODES, "row3": REGIONS}, {"o": PLACED})
    run = same(tmp_path, made, {"row1.csv": ORDERS_DATA, "row2.csv": CODES_DATA,
                                "row3.csv": b"region;zone\nalice;z1\nalice;z2\nerin;z3\n"})
    assert run.files["o.csv"].splitlines()[1:5] == [
        b"1;first-A;z1", b"1;first-A;z2", b"1;second-A;z1", b"1;second-A;z2",
    ]


def test_unmatched_rows_keep_their_place_through_a_lookup_keyed_on_an_earlier_lookup(tmp_path):
    # v1 moves the rows the first lookup did not match behind all the others: their key is missing.
    result, files = v2(tmp_path, placed([lookup("row2", BY_CODE), lookup("row3", BY_REGION)]),
                       placed_data(ORDERS_DATA))
    assert files["o.csv"] == b"id;label;zone\n1;la;N1\n2;lb;S1\n3;;\n4;;\n5;la;N1\n"


NUMBERED = "id:int, name:str, k:int"
NUMBERED_COLUMNS = [("id", "row1.id", "int"), ("name", "row1.name", "str"), ("k", "row1.k", "int"),
                    ("label", "row2.label", "str")]
NUMBERS_DATA = b"k;label\n10;ten\n30;thirty\n;no-key\n10;ten-again\n"
SCATTERED = b"id;name;k\n1;alice;10\n2;bob;\n3;carol;30\n4;dave;\n5;erin;99\n"


def numbered(lookup_settings):
    """Rows keyed on a whole number that may be missing, with an output for the rows an inner join misses."""
    outputs = [out("o", NUMBERED_COLUMNS), out("rej", NUMBERED_COLUMNS[:3], inner_join_reject=True)]
    return mapping(config(outputs, lookups=[lookup("row2", [("k", "row1.k")], **lookup_settings)]),
                   {"row1": NUMBERED, "row2": "k:int, label:str"}, {"o": declared(NUMBERED_COLUMNS), "rej": NUMBERED})


@pytest.mark.parametrize("join_mode", ["LEFT_OUTER_JOIN", "INNER_JOIN"])
@pytest.mark.parametrize("mode", ["UNIQUE_MATCH", "ALL_MATCHES"])
def test_missing_key_matches_nothing_not_even_a_missing_key(tmp_path, join_mode, mode):
    # The rows without a key come last in the file, where v1 moves them anyway.
    main = b"id;name;k\n1;alice;10\n3;carol;30\n5;erin;99\n2;bob;\n4;dave;\n"
    run = same(tmp_path, numbered({"join_mode": join_mode, "matching_mode": mode}),
               {"row1.csv": main, "row2.csv": NUMBERS_DATA})
    assert b"no-key" not in run.files["o.csv"]
    if join_mode == "INNER_JOIN":
        assert run.files["rej.csv"] == b"id;name;k\n5;erin;99\n2;bob;\n4;dave;\n"


def test_rows_with_a_missing_key_keep_their_place(tmp_path):
    # v1 moves the main rows whose key is missing behind all the others.
    result, files = v2(tmp_path, numbered({}), {"row1.csv": SCATTERED, "row2.csv": NUMBERS_DATA})
    assert files["o.csv"] == (
        b"id;name;k;label\n1;alice;10;ten-again\n2;bob;;\n3;carol;30;thirty\n4;dave;;\n5;erin;99;\n"
    )


def test_inner_join_rejects_keep_the_order_of_the_main_rows(tmp_path):
    # v1 lists the rows without a key after the unmatched ones, and one lookup's rejects after another's.
    result, files = v2(tmp_path, numbered(INNER), {"row1.csv": SCATTERED, "row2.csv": NUMBERS_DATA})
    assert files["rej.csv"] == b"id;name;k\n2;bob;\n4;dave;\n5;erin;99\n"


def test_key_that_is_a_constant_or_a_context_value(tmp_path):
    # v1's PyMap takes a key only when it is written row.column.
    for number, key in enumerate(["'B'", "context.wanted", "context['wanted']", "globalMap.get('wanted', 'B')"]):
        files = joined_direct(tmp_path / str(number), [lookup("row2", [("code", key)])],
                              context={"wanted": {"value": "B", "type": "str"}})
        assert files["o.csv"].splitlines()[1:] == [
            name + b";only-B;2.5;20" for name in (b"1;alice", b"2;bob", b"3;carol", b"4;dave", b"5;erin")
        ]


def test_constant_key_respects_the_matching_mode_and_the_join_mode(tmp_path):
    first = joined_direct(tmp_path / "first", [lookup("row2", [("code", "'A'")], matching_mode="FIRST_MATCH")])
    assert first["o.csv"].splitlines()[1] == b"1;alice;first-A;1.5;10"
    every = joined_direct(tmp_path / "all", [lookup("row2", [("code", "'A'")], matching_mode="ALL_MATCHES")])
    assert every["o.csv"].count(b"\n") == 11
    none = joined_direct(tmp_path / "inner", [lookup("row2", [("code", "'nope'")], **INNER)], WITH_REJECTS, BOTH)
    assert none["o.csv"] == b"id;name;label;rate;n\n" and none["rej.csv"].count(b"\n") == 6
    missing = joined_direct(tmp_path / "missing", [lookup("row2", [("code", "None")])])
    assert missing["o.csv"].splitlines()[1] == b"1;alice;;;"


def test_key_that_is_computed(tmp_path):
    key = "row1.name[0].upper() if row1.id < 3 else row1['code']"
    files = joined_direct(tmp_path, [lookup("row2", [("code", key)])])
    assert files["o.csv"] == (
        b"id;name;label;rate;n\n1;alice;second-A;3.5;30\n2;bob;only-B;2.5;20\n3;carol;empty-key;7.0;70\n"
        b"4;dave;;;\n5;erin;second-A;3.5;30\n"
    )


def test_key_cannot_read_a_variable_or_a_later_lookup():
    made = config([out("o", JOINED_COLUMNS)], lookups=[lookup("row2", [("code", "Var.v")])],
                  variables=[("v", "row1.code")])
    said = refused(mapping(made, TWO, {"o": JOINED}))
    assert "inputs.lookups[0].join_keys[0].expression: `Var.v`: no variable 'v' is defined" in said
    made = placed([lookup("row2", [("code", "row3.zone")]), lookup("row3", [("region", "row1.name")])])
    assert "inputs.lookups[0].join_keys[0].expression: `row3`: unknown name 'row3'; rows here: row1" in refused(made)


def test_lookup_without_keys_goes_whole_with_every_main_row(tmp_path):
    # v1's PyMap cannot join without keys; its Java tMap does this whatever the matching mode says.
    cols = [("id", "row1.id", "int"), ("zone", "row2.zone", "str")]
    for number, mode in enumerate(["ALL_ROWS", "UNIQUE_MATCH", "ALL_MATCHES"]):
        made = config([out("o", cols)], lookups=[lookup("row2", [], matching_mode=mode)])
        files = direct(tmp_path / str(number), made, {"row1": ITEMS, "row2": REGIONS}, {"o": declared(cols)},
                       {"row1.csv": ITEMS_DATA, "row2.csv": REGIONS_DATA})
        assert files["o.csv"] == b"id;zone\n1;N1\n1;S1\n2;N1\n2;S1\n3;N1\n3;S1\n4;N1\n4;S1\n"


def test_lookup_without_keys_and_without_rows(tmp_path):
    # v1's Java tMap drops every main row of the left join when the lookup's filter leaves it no row.
    cols = [("id", "row1.id", "int"), ("zone", "row2.zone", "str")]
    outputs = [out("o", cols), out("rej", [("id", "row1.id", "int")], inner_join_reject=True)]
    sinks = {"o": declared(cols), "rej": "id:int"}
    data = {"row1.csv": ITEMS_DATA, "row2.csv": REGIONS_DATA}
    nothing = {"filter": "row2.zone == 'nowhere'", "activate_filter": True}
    left = direct(tmp_path / "left", config(outputs, lookups=[lookup("row2", [], **nothing)]),
                  {"row1": ITEMS, "row2": REGIONS}, sinks, data)
    assert left["o.csv"] == b"id;zone\n1;\n2;\n3;\n4;\n" and left["rej.csv"] == b"id\n"
    inner = direct(tmp_path / "inner", config(outputs, lookups=[lookup("row2", [], **nothing, **INNER)]),
                   {"row1": ITEMS, "row2": REGIONS}, sinks, data)
    assert inner["o.csv"] == b"id;zone\n" and inner["rej.csv"] == b"id\n1\n2\n3\n4\n"


# ------------------------------------------------------------------
# Keys of every type, and of two types
# ------------------------------------------------------------------

LABELLED = [("id", "row1.id", "int"), ("label", "row2.label", "str")]


def keyed(tmp_path, main_schema, lookup_schema, main_data, lookup_data, key="row1.k", on_v1=True, **more):
    """A map that looks a label up by one key; returns what it wrote."""
    made = mapping(config([out("o", LABELLED)], lookups=[lookup("row2", [("k", key)])], **more),
                   {"row1": main_schema, "row2": lookup_schema}, {"o": declared(LABELLED)})
    inputs = {"row1.csv": main_data, "row2.csv": lookup_data}
    if on_v1:
        return same(tmp_path, made, inputs).files["o.csv"]
    result, files = v2(tmp_path, made, inputs)
    assert result.status == "success", result.error
    return files["o.csv"]


@pytest.mark.parametrize(
    "kind, main_keys, lookup_keys",
    [
        ("float", b"1.5 2 9.25", b"1.5 2.0"),
        ("datetime@%Y-%m-%d", b"2024-01-31 2024-02-01 2020-01-01", b"2024-01-31 2024-02-01"),
        ("Decimal#2", b"1.50 2.00 9.25", b"1.50 2"),
        ("bool", b"true false true", b"true false"),
        ("int!", b"10 20 99", b"10 20"),
    ],
)
def test_key_of_each_type(tmp_path, kind, main_keys, lookup_keys):
    written = keyed(tmp_path, f"id:int, k:{kind}", f"k:{kind}, label:str",
                    b"id;k\n" + b"".join(b"%d;%s\n" % (n, key) for n, key in enumerate(main_keys.split(), 1)),
                    b"k;label\n" + b"".join(b"%s;L%d\n" % (key, n) for n, key in enumerate(lookup_keys.split(), 1)))
    assert written.splitlines()[1:3] == [b"1;L1", b"2;L2"]


def test_whole_number_key_matches_a_decimal_number_key_by_value(tmp_path):
    written = keyed(tmp_path, "id:int, k:int", "k:float, label:str", b"id;k\n1;10\n2;30\n3;7\n",
                    b"k;label\n10.0;ten\n30;thirty\n7.5;seven-and-a-half\n")
    assert written == b"id;label\n1;ten\n2;thirty\n3;\n"


def test_text_key_and_number_key_are_compared_as_numbers_when_asked(tmp_path):
    # The number columns may not be missing here: v1's PyMap fails on text beside a number column that may.
    asked = {"enable_auto_convert_type": True}
    written = keyed(tmp_path / "text-main", "id:int, k:str", "k:int!, label:str",
                    b"id;k\n1;10\n2; 030 \n5;7.0\n3;x\n4;\n", b"k;label\n10;ten\n30;thirty\n7;seven\n", **asked)
    assert written == b"id;label\n1;ten\n2;thirty\n5;seven\n3;\n4;\n"
    written = keyed(tmp_path / "text-lookup", "id:int, k:int!", "k:str, label:str", b"id;k\n1;10\n2;30\n3;7\n",
                    b"k;label\n10;ten\n030;thirty\nx;bad\n", **asked)
    assert written == b"id;label\n1;ten\n2;thirty\n3;\n"
    written = keyed(tmp_path / "may-be-missing", "id:int, k:str", "k:int, label:str", b"id;k\n1;10\n2;x\n3;30.0\n",
                    b"k;label\n10;ten\n30;thirty\n", on_v1=False, **asked)
    assert written == b"id;label\n1;ten\n2;\n3;thirty\n"


def test_lookup_keys_that_are_the_same_number_are_duplicates_of_each_other(tmp_path):
    # v1's PyMap drops duplicates before it turns the text into numbers, and so matches both rows.
    written = keyed(tmp_path, "id:int, k:int!", "k:str, label:str", b"id;k\n1;10\n",
                    b"k;label\n10;plain\n010;padded\n", on_v1=False, enable_auto_convert_type=True)
    assert written == b"id;label\n1;padded\n"


def test_decimal_keys_are_compared_by_value(tmp_path):
    written = keyed(tmp_path / "places", "id:int, k:Decimal#2", "k:Decimal#4, label:str",
                    b"id;k\n1;1.50\n2;2\n3;1.55\n", b"k;label\n1.5000;one-and-a-half\n2.0000;two\n1.5501;near\n",
                    on_v1=False)
    assert written == b"id;label\n1;one-and-a-half\n2;two\n3;\n"
    written = keyed(tmp_path / "whole", "id:int, k:int", "k:Decimal#2, label:str", b"id;k\n1;2\n2;3\n",
                    b"k;label\n2.00;two\n3.10;three-ten\n", on_v1=False)
    assert written == b"id;label\n1;two\n2;\n"


def test_date_key_matches_a_date_and_time_key(tmp_path):
    written = keyed(tmp_path, "id:int, d:datetime@%Y-%m-%d %H:%M:%S", "k:datetime@%Y-%m-%d, label:str",
                    b"id;d\n1;2024-01-31 10:00:00\n2;2024-02-01 00:00:00\n",
                    b"k;label\n2024-01-31;jan\n2024-02-01;feb\n", key="row1.d.date()", on_v1=False)
    assert written == b"id;label\n1;jan\n2;feb\n"


def test_whole_number_keys_of_different_widths_match(tmp_path):
    written = keyed(tmp_path, "id:int, d:datetime@%Y-%m-%d", "k:int, label:str",
                    b"id;d\n1;2024-01-31\n2;1999-12-31\n", b"k;label\n2024;leap\n1999;last\n", key="row1.d.year",
                    on_v1=False)
    assert written == b"id;label\n1;leap\n2;last\n"


def test_keys_that_cannot_be_compared_are_refused():
    def said(key, lookup_schema, **more):
        made = config([out("o", LABELLED)], lookups=[lookup("row2", [("k", key)])], **more)
        return refused(mapping(made, {"row1": ITEMS, "row2": lookup_schema}, {"o": declared(LABELLED)})) + "\n"

    assert ("inputs.lookups[0].join_keys[0]: the key is a number on the main side and text in row2.k; convert one "
            "side in the expression, or set enable_auto_convert_type to compare them as numbers\n"
            ) in said("row1.id", "k:str, label:str")
    assert ("inputs.lookups[0].join_keys[0]: the key is text on the main side and a date in row2.k; "
            "convert one side in the expression\n") in said("row1.name", "k:datetime, label:str",
                                                              enable_auto_convert_type=True)
    assert "the key is true or false on the main side and a number in row2.k" in said("row1.id > 1", "k:int, label:str")


@pytest.mark.parametrize("engine", ["streaming", "in-memory"])
def test_key_that_is_not_a_number_matches_nothing(engine):
    main = pl.LazyFrame({"id": [1, 2, 3], "x": [0.0, 1.0, None]})
    codes = pl.LazyFrame({"k": [float("nan"), 1.0, None], "label": ["nan", "one", "none"]})
    keys = [(pl.col("x") / pl.col("x"), pl.Float64)]
    frame = joined_with(main, codes, lookup("row2", [("k", "row1.x / row1.x")]), keys, False, False, "lookup")
    assert frame.collect(engine=engine).to_dict(as_series=False) == {
        "id": [1, 2, 3], "x": [0.0, 1.0, None], "row2.k": [None, 1.0, None], "row2.label": [None, "one", None],
    }


# ------------------------------------------------------------------
# Lookup filters
# ------------------------------------------------------------------

@pytest.mark.parametrize("condition", ["row2.rate > 2", "rate > 2 and label != 'second-A'", "row2['n'] in (10, 20)"])
def test_lookup_filter_applies_before_the_match_is_chosen(tmp_path, condition):
    # v1's Java tMap reads the lookup's rows there under the main row's name, so row2.rate matches nothing.
    joined(tmp_path, [lookup("row2", BY_CODE, filter=condition, activate_filter=True)])


def test_lookup_filter_decides_which_duplicate_is_the_last(tmp_path):
    files = joined(tmp_path, [lookup("row2", BY_CODE, filter="row2.rate < 3", activate_filter=True)])
    assert files["o.csv"].splitlines()[1:3] == [b"1;alice;first-A;1.5;10", b"2;bob;only-B;2.5;20"]


def test_lookup_filter_that_is_not_activated_is_not_applied(tmp_path):
    files = joined(tmp_path, [lookup("row2", BY_CODE, filter="row2.rate < 3", activate_filter=False)])
    assert files["o.csv"].splitlines()[1] == b"1;alice;second-A;3.5;30"


def test_lookup_filter_reads_the_lookup_alone():
    # v1's PyMap fails on every lookup row there and silently matches nothing.
    made = config([out("o", JOINED_COLUMNS)],
                  lookups=[lookup("row2", BY_CODE, filter="row1.price > 2", activate_filter=True)])
    said = refused(mapping(made, TWO, {"o": JOINED}))
    assert "inputs.lookups[0].filter: `row1`: unknown name 'row1'; rows here: row2" in said


# ------------------------------------------------------------------
# Context and globalMap
# ------------------------------------------------------------------

def test_context_values_in_columns_filters_and_variables(tmp_path):
    cols = [("id", "row1.id", "int"), ("p", "row1.price * context.factor", "float"),
            ("tag", "context.tag + '-' + row1.name", "str"), ("tag2", "context['tag']", "str"),
            ("v", "Var['v']", "int")]
    made = mapping(
        config([out("o", cols, filter="row1.id >= context.first", activate_filter=True)],
               variables=[("v", "row1.id + context.first")]),
        {"row1": ITEMS}, {"o": declared(cols)},
        context={"factor": {"value": "2", "type": "int"}, "tag": {"value": "T", "type": "str"},
                 "first": {"value": "2", "type": "int"}},
    )
    run = same(tmp_path, made, {"row1.csv": ITEMS_DATA})
    assert run.files["o.csv"] == b"id;p;tag;tag2;v\n2;8.0;T-bob;T;4\n3;;T-carol;T;5\n4;2.0;T-dave;T;6\n"


def test_globalmap_entries_in_expressions(tmp_path):
    cols = [("id", "row1.id", "int"), ("file", "globalMap.get('in_row1_FILENAME', '?')", "str"),
            ("other", "globalMap.get('nothing', 'fallback')", "str")]
    made = mapping(config([out("o", cols)]), {"row1": ITEMS}, {"o": declared(cols)})
    run = same(tmp_path, made, {"row1.csv": ITEMS_DATA})
    assert run.files["o.csv"].splitlines()[1] == b"1;row1.csv;fallback"


# ------------------------------------------------------------------
# Declared column types, and values that do not fit them
# ------------------------------------------------------------------

MIXED = "id:int, text:str, price:float, qty:int, flag:bool"
MIXED_DATA = b"id;text;price;qty;flag\n1; 12 ;10.9;2;true\n2;7.5;-4.5;5;false\n3;;;;true\n"
UNREADABLE = b"id;text;price;qty;flag\n1;12;1;1;true\n2;abc;1;1;true\n3;2024-01-31;1;1;true\n"


def typed(tmp_path, cols, data=MIXED_DATA, **more):
    """Run a map over the mixed rows on v2 alone; returns (result, files)."""
    made = mapping(config([out("o", cols)], **more), {"row1": MIXED}, {"o": declared(cols)})
    return v2(tmp_path, made, {"row1.csv": data})


def test_values_are_turned_into_the_declared_type(tmp_path):
    # v1's PyMap never reads a column's type; its Java tMap applies it as Java would.
    cols = [("whole", "row1.price", "int"), ("stays_whole", "row1.qty", "float"), ("as_text", "row1.qty", "str"),
            ("number", "row1.text", "float"), ("yes", "row1.qty", "bool"),
            ("day", "'2024-03-0' + str(row1.id)", "datetime"), ("money", "row1.price", "Decimal")]
    result, files = typed(tmp_path, cols)
    assert result.status == "success", result.error
    assert files["o.csv"] == (
        b"whole;stays_whole;as_text;number;yes;day;money\n"
        b"10;2;2;12.0;true;2024-03-01 00:00:00;10.9\n"
        b"-4;5;5;7.5;true;2024-03-02 00:00:00;-4.5\n"
        b";;;;;2024-03-03 00:00:00;\n"
    )


def test_text_that_cannot_be_read_as_the_declared_type_fails_the_job(tmp_path):
    result, files = typed(tmp_path, [("id", "row1.id", "int"), ("n", "row1.text", "int")], data=UNREADABLE)
    assert result.status == "failed" and result.failed_component == "map"
    assert result.error == "output 'o' column 'n': 'abc' cannot be read as int (2 rows of the output hold such a value)"
    assert files == {}


def test_text_that_cannot_be_read_goes_missing_when_errors_are_not_fatal(tmp_path):
    cols = [("id", "row1.id", "int"), ("n", "row1.text", "int"), ("d", "row1.text", "datetime")]
    result, files = typed(tmp_path, cols, data=UNREADABLE, die_on_error=False)
    assert result.status == "success", result.error
    assert files["o.csv"] == b"id;n;d\n1;12;\n2;;\n3;;2024-01-31 00:00:00\n"


def test_rows_an_output_does_not_take_cannot_fail_it(tmp_path):
    made = mapping(config([out("o", [("n", "row1.text", "int")], filter="row1.id == 1", activate_filter=True)]),
                   {"row1": MIXED}, {"o": "n:int"})
    result, files = v2(tmp_path, made, {"row1.csv": UNREADABLE})
    assert result.status == "success" and files["o.csv"] == b"n\n12\n"


@pytest.mark.parametrize("die_on_error", [True, False])
def test_conversion_written_in_an_expression_fails_the_job_whatever_die_on_error_says(tmp_path, die_on_error):
    # The translator makes int(), float() and strptime() strict, and the map cannot see inside an expression.
    result, files = typed(tmp_path, [("id", "row1.id", "int"), ("n", "int(row1.text)", "int")], data=UNREADABLE,
                          die_on_error=die_on_error)
    assert result.status == "failed" and result.failed_component == "map" and files == {}


# ------------------------------------------------------------------
# What v2 says no to
# ------------------------------------------------------------------

def orders_job(lookups=None, outputs=None, **more):
    """The orders with the codes looked up, for changing one thing at a time."""
    lookups = [lookup("row2", BY_CODE)] if lookups is None else lookups
    return mapping(config(outputs or [out("o", JOINED_COLUMNS)], lookups=lookups, **more), TWO, {"o": JOINED})


@pytest.mark.parametrize("mode", ["RELOAD_AT_EACH_ROW", "RELOAD", "CACHE_OR_RELOAD"])
def test_reloading_a_lookup_for_each_row_is_refused(mode):
    said = refused(orders_job([lookup("row2", BY_CODE, lookup_mode=mode)]))
    assert "inputs.lookups[0].lookup_mode" in said and "needs a loop over the rows" in said


@pytest.mark.parametrize(
    "change, said",
    [
        ({"join_mode": "FULL_OUTER_JOIN"}, "inputs.lookups[0].join_mode: 'FULL_OUTER_JOIN' is not allowed"),
        ({"matching_mode": "ANY_MATCH"}, "inputs.lookups[0].matching_mode: 'ANY_MATCH' is not allowed"),
        ({"matching_mode": "ALL_ROWS"}, "inputs.lookups[0].matching_mode: ALL_ROWS is for a lookup without join keys"),
        ({"name": "row1"}, "inputs.lookups[0].name: 'row1' is named twice among the inputs"),
        ({"joinkeys": []}, "inputs.lookups[0].joinkeys: unknown config key; did you mean 'join_keys'?"),
        ({"filter": "{{java}}row2.rate > 2", "activate_filter": True}, "inputs.lookups[0].filter: Java expressions"),
    ],
)
def test_refused_lookup_settings(change, said):
    made = lookup("row2", BY_CODE)
    made.update(change)
    assert said in refused(orders_job([made]))


@pytest.mark.parametrize(
    "key, said",
    [
        ({"operator": "<="}, "inputs.lookups[0].join_keys[0].operator: join keys are compared for equality only"),
        ({"lookup_column": "nope"}, "inputs.lookups[0].join_keys[0].lookup_column: row2 has no column 'nope'"),
        ({"expression": ""}, "inputs.lookups[0].join_keys[0].expression: must not be empty"),
        ({"expression": "row1.nope"}, "inputs.lookups[0].join_keys[0].expression: `row1.nope`: row1 has no column"),
    ],
)
def test_refused_join_keys(key, said):
    made = lookup("row2", BY_CODE)
    made["join_keys"][0].update(key)
    assert said in refused(orders_job([made]))


@pytest.mark.parametrize("operator", ["=", ""])
def test_equality_operator_is_accepted(operator):
    made = lookup("row2", BY_CODE)
    made["join_keys"][0]["operator"] = operator
    load_job(orders_job([made]))


@pytest.mark.parametrize(
    "outputs, said",
    [
        ([], "outputs: a map needs at least one output"),
        ([out("o", JOINED_COLUMNS), out("o", MISSES)], "outputs[1].name: 'o' is the name of more than one output"),
        ([out("o", [])], "outputs[0].columns: an output needs at least one column"),
        ([out("o", [("a", "row1.id", "int"), ("a", "row1.name", "str")])],
         "outputs[0].columns[1].name: 'a' is the name of more than one column"),
        ([out("o", JOINED_COLUMNS, catch_output_reject=True)],
         "outputs[0].catch_output_reject: v2 has no rows whose expressions failed to send here"),
        ([out("o", [("a", "row1.id +", "int")])], "outputs[0].columns[0].expression: not a valid Python expression"),
        ([out("o", [("a", "row9.id", "int")])], "outputs[0].columns[0].expression: `row9`: unknown name 'row9'"),
        ([out("o", [("a", "row1.id", "object")])], "outputs[0].columns[0].type: 'object' is not allowed"),
        ([out("o", JOINED_COLUMNS, filter="row1.nope > 1", activate_filter=True)],
         "outputs[0].filter: `row1.nope`: row1 has no column 'nope'"),
        ([out("o", [("a", "{{java}}row1.id", "int")])], "outputs[0].columns[0].expression: Java expressions"),
        ([dict(out("o", JOINED_COLUMNS), colour="red")], "outputs[0].colour: unknown config key"),
    ],
)
def test_refused_outputs(outputs, said):
    assert said in refused(mapping(config(outputs, lookups=[lookup("row2", BY_CODE)]), TWO, {}))


def test_inputs_named_in_the_config_must_arrive():
    made = orders_job()
    made["components"][2]["config"]["inputs"]["main"]["name"] = "row7"
    assert "inputs.main.name: no flow named 'row7' arrives at the map; arriving: row1, row2" in refused(made)
    made = orders_job([lookup("row5", BY_CODE)])
    assert "inputs.lookups[0].name: no flow named 'row5' arrives at the map" in refused(made)


def test_flow_must_leave_by_a_declared_output():
    made = orders_job()
    made["flows"][-1]["name"] = "other"
    made["components"][-1]["inputs"] = ["other"]
    assert "flows[2].type: a PyMap has no output named 'other'; its outputs are: o" in refused(made)


def test_flow_of_another_name_can_say_which_output_it_carries(tmp_path):
    made = orders_job()
    made["flows"][-1].update(name="other", output="o")
    made["components"][-1]["inputs"] = ["other"]
    result, files = v2(tmp_path, made, TWO_DATA)
    assert result.status == "success" and files["o.csv"].count(b"\n") == 6


def test_missing_and_unknown_top_level_keys_are_refused():
    made = orders_job()
    del made["components"][2]["config"]["outputs"]
    made["components"][2]["config"]["speed"] = "fast"
    said = refused(made)
    assert "outputs: required config key is missing" in said and "speed: unknown config key" in said


def test_keys_v1_does_not_act_on_are_accepted():
    made = orders_job(die_on_error="true", rows_buffer_size="2000000", change_hash_and_equals_for_bigdecimal=True,
                      enable_auto_convert_type=False, tstatcatcher_stats=False, label="", component_type="Map",
                      output_chunk_size=5000)
    editor = {"size_state": "INTERMEDIATE", "persistent": False, "activate_condensed_tool": False,
              "activate_global_map": False}
    settings = made["components"][2]["config"]
    settings["inputs"]["main"].update(matching_mode="UNIQUE_MATCH", lookup_mode="RELOAD_AT_EACH_ROW", **editor)
    settings["inputs"]["lookups"][0].update(editor)
    settings["outputs"][0].update(editor)
    settings["outputs"][0]["columns"][0].update(length=-1, precision=-1, pattern="", date_pattern="", operator="")
    settings["variables"].append({"name": "v", "expression": "1", "type": "id_Object", "nullable": False})
    load_job(made)


# ------------------------------------------------------------------
# The converter's samples, and the names a map goes by
# ------------------------------------------------------------------

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "..", "talend_xml_samples", "converted_jsons")
IN_PYTHON = {
    '{{java}}row1.salary >= 75000 ? "Senior" : "Junior"': '"Senior" if row1.salary >= 75000 else "Junior"',
}


def python_for(value):
    """A sample's config with its Java expressions rewritten in Python."""
    if isinstance(value, str):
        return IN_PYTHON.get(value, value.removeprefix("{{java}}"))
    if isinstance(value, dict):
        return {name: python_for(item) for name, item in value.items()}
    if isinstance(value, list):
        return [python_for(item) for item in value]
    return value


def sample_job(file_name):
    """The sample's map, every key of it, between delimited readers and writers."""
    with open(os.path.join(SAMPLES, file_name), encoding="utf-8") as handle:
        sample = json.load(handle)
    by_flow = {name: component["schema"]["output"] for component in sample["components"]
               for name in component["outputs"] if component["type"] != "Map"}
    (the_map,) = [component for component in sample["components"] if component["type"] == "Map"]
    components, flows = [], []
    for name in the_map["inputs"]:
        source = reader("x:str", component_id=f"in_{name}", path=f"{name}.csv", outputs=(name,), header_rows=1)
        source["schema"]["output"] = by_flow[name]
        components.append(source)
        flows.append(flow(name, f"in_{name}", the_map["id"]))
    components.append(dict(the_map, config=python_for(the_map["config"])))
    for name in the_map["outputs"]:
        components.append(writer(None, component_id=f"out_{name}", path=f"{name}.csv", inputs=(name,)))
        flows.append(flow(name, the_map["id"], f"out_{name}"))
    return job(components, flows, context=sample["context"])


def test_converter_sample_loads_and_runs(tmp_path):
    made = sample_job("Job_tMap_0.1.json")
    assert len(load_job(made).components) == 5
    result, files = v2(tmp_path, made, {
        "row1.csv": b"id;first_name;last_name;department;salary;country_code\n"
                    b"1;Ann;Lee;IT;80000;US\n2;Bo;Ray;HR;50000;FR\n3;Cy;Poe;IT;61000;XX\n",
        "row2.csv": b"country_code;country_name;region\nUS;United States;Americas\nFR;France;Europe\n",
    })
    assert result.status == "success", result.error
    assert files["out.csv"] == (
        b"full_name;department;salary;country;region;salary_grade\n"
        b"Ann Lee;IT;80000;United States;Americas;Senior\nCy Poe;IT;61000;;;Junior\n"
    )
    assert files["out2.csv"] == b"id;first_name;last_name;country_code\n1;Ann;Lee;US\n2;Bo;Ray;FR\n3;Cy;Poe;XX\n"


def test_converter_sample_with_a_constant_key_loads_and_runs(tmp_path):
    made = sample_job("Job_tMap_constant_key_lookup.json")
    load_job(made)
    result, files = v2(tmp_path, made, {
        "row1.csv": b"id;desc\n1;rowA\n2;rowB\n3;rowC\n",
        "row8.csv": b"name;info\nalpha;A_info\nbeta;B_info\nbeta;B_info_dup\ngamma;G_info\n",
    })
    assert result.status == "success", result.error
    assert files["out1.csv"] == b"id;desc;info\n1;rowA;B_info\n2;rowB;B_info\n3;rowC;B_info\n"


@pytest.mark.parametrize("kind", ["map", "Map", "tMap", "PyMap"])
def test_type_names(tmp_path, kind):
    made = mapping(config([out("o", ITEM_COLUMNS)]), {"row1": ITEMS}, {"o": ITEMS}, kind=kind)
    result, files = v2(tmp_path, made, {"row1.csv": ITEMS_DATA})
    assert result.status == "success" and files["o.csv"].count(b"\n") == 5


# ------------------------------------------------------------------
# Against v1's Java tMap: the map written twice, in Java for v1 and in Python for v2
# ------------------------------------------------------------------

def in_java(made):
    """A map config with every expression marked as Java, as the converter writes it."""
    if isinstance(made, dict):
        return {name: "{{java}}" + item if name in ("expression", "filter") and item else in_java(item)
                for name, item in made.items()}
    if isinstance(made, list):
        return [in_java(item) for item in made]
    return made


def pair(tmp_path, java_config, python_config, sources, sinks, inputs, context=None):
    """v1 runs the Java map through its bridge and v2 the Python one; they write the same bytes.

    Skipped where the bridge is not available.
    """
    v1_job = mapping(in_java(java_config), sources, sinks, kind="Map", context=context, java_config=JAVA)
    v2_job = mapping(python_config, sources, sinks, kind="Map", context=context)
    return same(tmp_path, v1_job, inputs, v2_job=v2_job).files


FULL_ITEMS = b"id;name;price\n1;alice;10.5\n2;bob;4\n3;carol;2.5\n4;dave;1\n"
MATCHED_COLUMNS = JOINED_COLUMNS[:4]
MATCHED = declared(MATCHED_COLUMNS)


def test_java_reject_output_takes_the_rows_no_output_took_with_its_own_columns(tmp_path):
    def made(reason):
        # v1 does not read a reject output's own filter, and neither does v2.
        return config([out("o", ITEM_COLUMNS, **DEAR),
                       out("p", ITEM_COLUMNS, filter="row1.price < 2", activate_filter=True),
                       out("rej", [("ident", "row1.id", "int"), ("why", reason, "str")], is_reject=True,
                           filter="row1.id > 3", activate_filter=True)])

    files = pair(tmp_path, made('"low: " + row1.name'), made("'low: ' + row1.name"), {"row1": ITEMS},
                 {"o": ITEMS, "p": ITEMS, "rej": "ident:int, why:str"}, {"row1.csv": FULL_ITEMS})
    assert files["rej.csv"] == b"ident;why\n3;low: carol\n"


def test_java_reject_output_is_empty_beside_an_output_without_a_filter(tmp_path):
    made = config([out("o", ITEM_COLUMNS, **DEAR), out("all", ITEM_COLUMNS), out("rej", ITEM_COLUMNS, is_reject=True)])
    files = pair(tmp_path, made, made, {"row1": ITEMS}, {"o": ITEMS, "all": ITEMS, "rej": ITEMS},
                 {"row1.csv": FULL_ITEMS})
    assert files["rej.csv"] == b"id;name;price\n"


def test_java_inner_join_reject_output_computes_its_own_columns_and_applies_its_filter(tmp_path):
    def made(who, why):
        reasons = [("ident", "row1.id * 10", "int"), ("who", who, "str"), ("why", why, "str")]
        return config([out("o", MATCHED_COLUMNS),
                       out("rej", reasons, inner_join_reject=True, filter="row1.id != 3", activate_filter=True)],
                      lookups=[lookup("row2", BY_CODE, **INNER)])

    files = pair(
        tmp_path, made("row1.name.toUpperCase()", '"no code " + row1.code'),
        made("row1.name.upper()", "'no code ' + row1.code"), TWO, {"o": MATCHED, "rej": "ident:int, who:str, why:str"},
        {"row1.csv": b"id;name;code;price\n1;alice;A;1\n3;carol;Q;1\n4;dave;Z;1\n", "row2.csv": CODES_DATA},
    )
    assert files["rej.csv"] == b"ident;who;why\n40;DAVE;no code Z\n"


def test_java_inner_join_on_a_lookup_without_rows_rejects_every_main_row(tmp_path):
    made = config([out("o", MATCHED_COLUMNS), out("rej", MISSES, inner_join_reject=True)],
                  lookups=[lookup("row2", BY_CODE, **INNER)])
    files = pair(tmp_path, made, made, TWO, {"o": MATCHED, "rej": MISSED},
                 {"row1.csv": ORDERS_DATA, "row2.csv": b"code;label;rate;n\n"})
    assert files["o.csv"] == b"id;name;label;rate\n" and files["rej.csv"].count(b"\n") == 6


@pytest.mark.parametrize("mode, label", [("FIRST_MATCH", b"first-A"), ("UNIQUE_MATCH", b"second-A")])
def test_java_key_that_is_a_context_value(tmp_path, mode, label):
    made = config([out("o", MATCHED_COLUMNS)],
                  lookups=[lookup("row2", [("code", "context.wanted")], matching_mode=mode)])
    files = pair(tmp_path, made, made, TWO, {"o": MATCHED}, TWO_DATA, context={"wanted": {"value": "A", "type": "str"}})
    assert files["o.csv"].splitlines()[2].startswith(b"2;bob;" + label)


def test_java_key_that_is_computed(tmp_path):
    def made(key):
        return config([out("o", MATCHED_COLUMNS)], lookups=[lookup("row2", [("code", key)])])

    files = pair(tmp_path, made("row1.name.substring(0, 1).toUpperCase()"), made("row1.name[0].upper()"), TWO,
                 {"o": MATCHED}, TWO_DATA)
    assert files["o.csv"] == (
        b"id;name;label;rate\n1;alice;second-A;3.5\n2;bob;only-B;2.5\n3;carol;unused;9.0\n4;dave;;\n5;erin;;\n"
    )


def test_java_lookup_without_keys_goes_whole_with_every_main_row(tmp_path):
    cols = [("id", "row1.id", "int"), ("zone", "row2.zone", "str")]
    made = config([out("o", cols)], lookups=[lookup("row2", [], matching_mode="ALL_ROWS")])
    files = pair(tmp_path, made, made, {"row1": ITEMS, "row2": REGIONS}, {"o": declared(cols)},
                 {"row1.csv": FULL_ITEMS, "row2.csv": REGIONS_DATA})
    assert files["o.csv"] == b"id;zone\n1;N1\n1;S1\n2;N1\n2;S1\n3;N1\n3;S1\n4;N1\n4;S1\n"


def test_java_variables_and_a_value_cut_to_its_declared_type(tmp_path):
    cols = [("id", "row1.id", "int"), ("total", "Var.total", "float"), ("label", "Var.label", "str"),
            ("whole", "row1.price", "int")]

    def made(label):
        return config([out("o", cols, filter="Var.total > 5", activate_filter=True)],
                      variables=[("total", "row1.price * 2"), ("label", label)])

    files = pair(tmp_path, made('row1.name.toUpperCase() + "!"'), made("row1.name.upper() + '!'"), {"row1": ITEMS},
                 {"o": declared(cols)}, {"row1.csv": FULL_ITEMS})
    assert files["o.csv"] == b"id;total;label;whole\n1;21.0;ALICE!;10\n2;8.0;BOB!;4\n"


# ------------------------------------------------------------------
# One pass, and order on inputs of some size
# ------------------------------------------------------------------

@pytest.mark.parametrize("several", [True, False])
def test_every_input_is_read_once_however_many_outputs_there_are(tmp_path, monkeypatch, several):
    """Polars shares what the outputs have in common by itself; the map never marks a frame as cached.

    One level of sharing is what Polars finds. Several outputs share the
    joined rows; one output and the check on its unreadable text share that
    output's rows. Both at once (several outputs and such a check) is two
    levels, and the inputs are then read twice: correct, and slower.
    """
    if not hasattr(pl, "explain_all"):
        pytest.skip("this Polars cannot print the plan of several frames collected together")
    plans = []
    collect_all = pl.collect_all
    monkeypatch.setattr(
        pl, "collect_all", lambda frames, **more: plans.append(pl.explain_all(frames)) or collect_all(frames, **more)
    )
    if several:
        outputs = [out("o", JOINED_COLUMNS, filter="row2.rate > 3", activate_filter=True),
                   out("p", JOINED_COLUMNS, filter="row1.price < 3", activate_filter=True),
                   out("low", JOINED_COLUMNS, is_reject=True), out("rej", MISSES, inner_join_reject=True)]
        sinks = {"o": JOINED, "p": JOINED, "low": JOINED, "rej": MISSED}
    else:
        unreadable = JOINED_COLUMNS + [("price", "row1.name", "float")]
        outputs = [out("o", unreadable, filter="row2.rate > 3", activate_filter=True)]
        sinks = {"o": declared(unreadable)}
    made = mapping(config(outputs, lookups=[lookup("row2", BY_CODE, **INNER)]), TWO, sinks)
    result, files = v2(tmp_path, made, TWO_DATA)
    if several:
        assert result.status == "success" and sorted(files) == ["low.csv", "o.csv", "p.csv", "rej.csv"]
    else:
        assert result.status == "failed" and "cannot be read as float" in result.error
    (plan,) = plans
    assert plan.count("row1.csv") == 1 and plan.count("row2.csv") == 1


@pytest.mark.parametrize("engine", ["streaming", "in-memory"])
@pytest.mark.parametrize("mode", ["FIRST_MATCH", "UNIQUE_MATCH", "ALL_MATCHES"])
def test_main_order_and_matches_hold_on_larger_inputs(tmp_path, engine, mode):
    rows, keys = 60_000, 4_000
    main_keys = [(n * 7919) % (keys + 300) for n in range(rows)]
    labels = {}
    for n in range(3 * keys):
        labels.setdefault((n * 31) % keys, []).append(f"L{n}")
    inputs = {
        "row1.csv": "id;k\n" + "".join(f"{n};{key}\n" for n, key in enumerate(main_keys)),
        "row2.csv": "k;label\n" + "".join(f"{(n * 31) % keys};L{n}\n" for n in range(3 * keys)),
    }
    cols = [("id", "row1.id", "int"), ("label", "row2.label", "str")]
    outputs = [out("o", cols, filter="row1.id % 3 != 0", activate_filter=True), out("low", cols, is_reject=True),
               out("rej", [("id", "row1.id", "int")], inner_join_reject=True)]
    made = mapping(config(outputs, lookups=[lookup("row2", [("k", "row1.k")], matching_mode=mode, **INNER)]),
                   {"row1": "id:int, k:int", "row2": "k:int, label:str"},
                   {"o": declared(cols), "low": declared(cols), "rej": "id:int"})
    result, files = v2(tmp_path, made, {name: text.encode() for name, text in inputs.items()}, engine=engine)
    assert result.status == "success", result.error

    pick = {"FIRST_MATCH": lambda found: found[:1], "UNIQUE_MATCH": lambda found: found[-1:],
            "ALL_MATCHES": lambda found: found}[mode]
    expected = {"o.csv": ["id;label"], "low.csv": ["id;label"], "rej.csv": ["id"]}
    for n, key in enumerate(main_keys):
        if key in labels:
            expected["o.csv" if n % 3 else "low.csv"] += [f"{n};{label}" for label in pick(labels[key])]
        else:
            expected["rej.csv"].append(str(n))
    assert {name: data.decode().splitlines() for name, data in files.items()} == expected


# ------------------------------------------------------------------
# Row counts
# ------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["PyMap"])
@pytest.mark.parametrize("counts, fires", [((5, 2, 3), True), ((5, 5, 0), False), ((7, 0, 0), False)])
def test_row_counts_are_taken_over_the_outputs_as_in_v1(tmp_path, kind, counts, fires):
    """NB_LINE is every row that left by any output, OK the ordinary outputs, REJECT the reject outputs."""
    cols = [("id", "row1.id", "int")]
    outputs = [out("o", cols, filter="row1.id > 3", activate_filter=True), out("low", cols, is_reject=True)]
    made = mapping(config(outputs), {"row1": "id:int"}, {"o": "id:int", "low": "id:int"}, kind=kind)
    made["components"] += [reader("id:int", component_id="again", path="row1.csv", outputs=("row9",), header_rows=1),
                           writer("id:int", component_id="marker", path="marker.csv", inputs=("row9",))]
    made["flows"].append(flow("row9", "again", "marker"))
    lines, ok, reject = counts
    condition = (f'((Integer)globalMap.get("map_NB_LINE")) == {lines} && ((Integer)globalMap.get("map_NB_LINE_OK")) == {ok}'
                 f' && ((Integer)globalMap.get("map_NB_LINE_REJECT")) == {reject}')
    made["triggers"] = [{"type": "RunIf", "from": "map", "to": "again", "condition": condition}]
    run = same(tmp_path, made, {"row1.csv": b"id\n1\n2\n3\n4\n5\n"})
    assert ("marker.csv" in run.files) is fires


def test_java_left_in_a_filter_that_is_off_does_not_refuse_the_job():
    cols = [("id", "row1.id", "int")]
    outputs = [out("o", cols, filter="{{java}}row1.id > 3", activate_filter=False)]
    made = mapping(config(outputs, main_filter=None), {"row1": "id:int"}, {"o": "id:int"})
    made["components"][1]["config"]["inputs"]["main"]["filter"] = "{{java}}row1.id != null"
    load_job(made)

    made["components"][1]["config"]["outputs"][0]["activate_filter"] = True
    assert "outputs[0].filter: Java expressions are not run by v2" in refused(made)
