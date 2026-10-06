"""Python dataframe, against v1 on the same job config and bytes. Its Polars way is v2's own."""
import logging

import pytest

from src.v2 import load_job
from src.v2 import run_job as run_on_v2
from src.v2.components.transform.python_dataframe import PythonDataFrame
from src.v2.errors import JobRefusedError
from tests.v2.answer_key import assert_matches_v1, run_job, run_v1

from .kit import columns, flow, job, reader, writer

SCHEMA = "id:int, name:str, amt:float"
DATA = b"id;name;amt\n1;alice;10.5\n2;bob;\n3;;7\n"
ALL_TYPES = "s:str, i:int, j:int!, f:float, b:bool, d:datetime@%Y-%m-%d, m:Decimal#2"
ALL_DATA = (b"s;i;j;f;b;d;m\na;1;10;1.5;true;2024-01-31;12.345\nb;-2;20;30200.00;false;1999-12-31;7\n"
            b"c;;30;;;;0\n;4;40;;;;-1.005\n")


def coded(code, schema=SCHEMA, out=None, declares=True, **config):
    """file -> python dataframe -> file.

    ``out`` is what the component declares to produce (its input columns when
    not given); with ``declares`` off neither it nor the writer declares any.
    """
    out = out or schema
    component = {"id": "it", "type": "PythonDataFrameComponent", "config": {"python_code": code, **config},
                 "schema": {"input": columns(schema), "output": columns(out) if declares else []},
                 "inputs": ["row1"], "outputs": ["row2"]}
    return job([reader(schema, header_rows=1), component, writer(out if declares else None)],
               [flow("row1", "in", "it"), flow("row2", "it", "out")])


def same(tmp_path, code, data=DATA, schema=SCHEMA, fails=False, made=None, inputs=None, **more):
    """Both engines do the same with the job; ``fails`` says it is one neither finishes."""
    run = assert_matches_v1(made or coded(code, schema, **more), inputs or {"in.csv": data}, tmp_path)
    assert run.succeeded is not fails, run.error
    return run


def alone(tmp_path, code, data=DATA, schema=SCHEMA, made=None, routines=None, **more):
    """Run on v2 only. Returns (the run, v2's result or None when the job was refused)."""
    state = {}

    def on_v2(job_config):
        state["result"] = run_on_v2(job_config, routines=routines)
        state["result"].raise_for_status()

    run = run_job(made or coded(code, schema, **more), {"in.csv": data}, tmp_path / "alone", on_v2)
    return run, state.get("result")


def chained(first, second, schema=SCHEMA, out=None, **second_config):
    """file -> python dataframe -> python dataframe -> file; only the second declares what it produces."""
    out = out or schema
    one = {"id": "one", "type": "python_dataframe", "config": {"python_code": first},
           "schema": {"input": columns(schema), "output": []}, "inputs": ["row1"], "outputs": ["mid"]}
    two = {"id": "two", "type": "python_dataframe", "config": {"python_code": second, **second_config},
           "schema": {"input": [], "output": columns(out)}, "inputs": ["mid"], "outputs": ["row2"]}
    return job([reader(schema, header_rows=1), one, two, writer(out)],
               [flow("row1", "in", "one"), flow("mid", "one", "two"), flow("row2", "two", "out")])


def out(run):
    return run.files["out.csv"].decode().splitlines()


# ------------------------------------------------------------------
# What the code is handed
# ------------------------------------------------------------------

DESCRIBE = '''
df = pd.DataFrame({
    "column": [str(name) for name in df.columns],
    "dtype": [str(dtype) for dtype in df.dtypes],
    "kinds": [",".join(type(value).__name__ for value in df[name].tolist()) for name in df.columns],
    "held": ["|".join(repr(value) for value in df[name].tolist()) for name in df.columns],
})
'''
DESCRIBED = "column:str, dtype:str, kinds:str, held:str"


def test_code_is_handed_the_frame_v1_hands_it(tmp_path):
    data = b"s;i;j;f;b;d;m\na;1;10;1.5;true;2024-01-31;12.345\n;;20;;;;7\n"
    run = same(tmp_path, DESCRIBE, data, ALL_TYPES, out=DESCRIBED)
    assert out(run) == [
        "column;dtype;kinds;held",
        "s;str;str,str;'a'|''",
        "i;Int64;int,NAType;1|<NA>",
        "j;int64;int,int;10|20",
        "f;float64;float,float;1.5|nan",
        "b;bool;bool,bool;True|False",
        "d;datetime64[us];Timestamp,NaTType;Timestamp('2024-01-31 00:00:00')|NaT",
        "m;object;Decimal,Decimal;Decimal('12.35')|Decimal('7.00')",
    ]


def test_code_may_change_the_frame_in_place(tmp_path):
    code = '''
df.loc[df["i"] == 1, "i"] = 100
df.loc[df["j"] == 10, "j"] = 100
df.loc[df["s"] == "a", "s"] = "changed"
df.loc[df["f"] > 2, "f"] = 0.5
df.loc[df["j"] == 20, "b"] = True
df.loc[df["j"] == 20, "d"] = pd.Timestamp("2000-01-01")
df.iloc[0, df.columns.get_loc("m")] = df["m"].iloc[1]
df.at[1, "i"] = 7
df["j"] += 1
df.sort_values("j", ascending=False, inplace=True)
df.drop(columns=["s"], inplace=True)
df.rename(columns={"f": "g"}, inplace=True)
'''
    data = b"s;i;j;f;b;d;m\na;1;10;1.5;true;2024-01-31;12.345\nb;-2;20;30200.00;false;1999-12-31;7\n"
    run = same(tmp_path, code, data, ALL_TYPES, out="i:int, j:int!, g:float, b:bool, d:datetime@%Y-%m-%d, m:Decimal#2")
    assert out(run) == ["i;j;g;b;d;m", "100;101;1.5;true;2024-01-31;7.00", "7;21;0.5;true;2000-01-01;7.00"]


def test_frame_starts_at_row_zero_and_is_the_codes_own(tmp_path):
    code = 'df = pd.DataFrame({"index": [repr(df.index)], "kind": [type(df).__name__]})'
    run = same(tmp_path, code, out="index:str, kind:str")
    assert out(run) == ["index;kind", "RangeIndex(start=0, stop=3, step=1);DataFrame"]


def test_names_the_code_may_use(tmp_path):
    code = '''
df["rows"] = len(df)
df["top"] = max(df["id"])
df["mean"] = np.mean([1.0, 2.0])
df["kind"] = type(context).__name__ + "/" + str(isinstance(routines, dict))
df["has"] = str(sorted(name for name in ("df", "pd", "np", "context", "globalMap", "routines") if name in globals()))
'''
    run = same(tmp_path, code, out=SCHEMA + ", rows:int, top:int, mean:float, kind:str, has:str")
    assert out(run)[1] == "1;alice;10.5;3;3;1.5;dict/True;['context', 'df', 'globalMap', 'np', 'pd', 'routines']"


def test_code_may_import(tmp_path):
    code = """
import math
from decimal import Decimal
df['root'] = df['id'].apply(math.sqrt)
df['dec'] = str(Decimal('1.50'))
"""
    same(tmp_path, code, out=SCHEMA + ", root:float, dec:str")


def with_context(made, **variables):
    made["context"] = {"Default": variables}
    return made


def test_context_values_are_read_with_their_types(tmp_path):
    code = '''
df["limit"] = context["limit"]
df["kind"] = type(context["limit"]).__name__
df["who"] = context.get("who", "?")
'''
    made = with_context(coded(code, out=SCHEMA + ", limit:int, kind:str, who:str"),
                        limit={"value": "5", "type": "int"}, who={"value": "me", "type": "str"})
    assert out(same(tmp_path, None, made=made))[1] == "1;alice;10.5;5;int;me"


def test_context_changed_by_the_code_stays_with_the_code(tmp_path):
    made = with_context(coded('context["name"] = "changed"\ncontext["fresh"] = 1'),
                        name={"value": "kept", "type": "str"})
    made["components"][2]["config"]["filepath"] = "${context.name}.csv"
    run = same(tmp_path, None, made=made)
    assert list(run.files) == ["kept.csv"]
    _, result = alone(tmp_path, None, made=made)
    assert result.context == {"name": "kept"}


def test_global_map_is_read_and_written_as_in_v1(tmp_path):
    code = '''
df["seen"] = globalMap.get("in_NB_LINE")
df["none"] = str(globalMap.get("nope"))
df["other"] = globalMap.get("nope", "fallback")
globalMap.put("rows", len(df))
df["has"] = globalMap.contains("rows")
globalMap.put("gone", 1)
globalMap.remove("gone")
df["gone"] = globalMap.contains("gone")
df["all"] = "rows" in globalMap.get_all()
globalMap.get_all()["sneaked"] = 1
df["sneaked"] = globalMap.contains("sneaked")
'''
    made = coded(code, out=SCHEMA + ", seen:int, none:str, other:str, has:bool, gone:bool, all:bool, sneaked:bool")
    made["components"] += [reader("a:str", component_id="in2", path="in.csv", outputs=("row3",)),
                           writer("a:str", component_id="out2", path="after.csv", inputs=("row3",))]
    made["flows"].append(flow("row3", "in2", "out2"))
    made["triggers"] = [{"type": "RunIf", "from": "it", "to": "in2", "condition": 'globalMap.get("rows") == 3'}]
    run = same(tmp_path, None, made=made)
    assert out(run)[1] == "1;alice;10.5;3;None;fallback;true;false;true;false"
    assert "after.csv" in run.files


@pytest.mark.parametrize(
    "put, condition",
    [
        ('df["id"].sum()', 'globalMap.get("seen") == 6'),
        ('df["id"].astype("int64").max()', 'globalMap.get("seen") == 3'),
        ('df["amt"].sum()', 'globalMap.get("seen") > 17'),
        ('df["amt"].notna().all()', 'globalMap.get("seen") == False'),
        ('df["name"].to_numpy()[0]', 'globalMap.get("seen") == "alice"'),
        ("len(df)", '((Integer)globalMap.get("seen")) == 3'),
    ],
)
def test_numbers_pandas_hands_out_can_be_put_in_the_global_map_and_read_by_a_trigger(tmp_path, put, condition):
    made = coded(f'globalMap.put("seen", {put})')
    made["components"] += [reader("a:str", component_id="in2", path="in.csv", outputs=("row3",)),
                           writer("a:str", component_id="out2", path="after.csv", inputs=("row3",))]
    made["flows"].append(flow("row3", "in2", "out2"))
    made["triggers"] = [{"type": "RunIf", "from": "it", "to": "in2", "condition": condition}]
    assert "after.csv" in same(tmp_path, None, made=made).files
    _, result = alone(tmp_path, None, made=made)
    assert type(result.global_map["seen"]) in (int, float, bool, str)


@pytest.mark.parametrize("condition, runs", [
    ('((Integer)globalMap.get("it_NB_LINE")) == 3 && ((Integer)globalMap.get("it_NB_LINE_OK")) == 2', True),
    ('((Integer)globalMap.get("it_NB_LINE_OK")) == 3', False),
])
def test_rows_in_and_out_are_counted_as_in_v1(tmp_path, condition, runs):
    made = coded('df = df[df["id"] > 1]')
    made["components"] += [reader("a:str", component_id="in2", path="in.csv", outputs=("row3",)),
                           writer("a:str", component_id="out2", path="after.csv", inputs=("row3",))]
    made["flows"].append(flow("row3", "in2", "out2"))
    made["triggers"] = [{"type": "RunIf", "from": "it", "to": "in2", "condition": condition}]
    assert ("after.csv" in same(tmp_path, None, made=made).files) is runs


# ------------------------------------------------------------------
# What comes back
# ------------------------------------------------------------------

def test_every_type_comes_back_as_it_went_in(tmp_path):
    run = same(tmp_path, "pass", ALL_DATA, ALL_TYPES)
    assert out(run) == [
        "s;i;j;f;b;d;m",
        "a;1;10;1.5;true;2024-01-31;12.35",
        "b;-2;20;30200.0;false;1999-12-31;7.00",
        "c;;30;;false;;0.00",
        ";4;40;;false;;-1.01",
    ]


@pytest.mark.parametrize("declares", [True, False])
def test_every_type_comes_back_whatever_is_declared(tmp_path, declares):
    same(tmp_path, "df = df.copy()", ALL_DATA, ALL_TYPES, declares=declares)


@pytest.mark.parametrize(
    "code, added",
    [
        ('df["up"] = df["name"].str.upper()', "up:str"),
        ('df["text"] = df["id"].astype(str) + "-" + df["name"]', "text:str"),
        ('df["name"] = df["name"].replace("", "unknown")', ""),
        ('df["size"] = df["name"].str.len()', "size:int"),
        ('df["dbl"] = df["amt"] * 2', "dbl:float"),
        ('df["half"] = df["id"] / 2', "half:float"),
        ('df["next"] = df["id"] + 1', "next:int"),
        ('df["next"] = df["id"] + 1', "next:float"),
        ('df["next"] = df["id"] + 1', "next:str"),
        ('df["big"] = df["amt"] > 8', "big:bool"),
        ('df["size"] = np.where(df["amt"] > 8, "big", "small")', "size:str"),
        ('df["amt"] = df["amt"].fillna(0)', ""),
        ('df["amt"] = df["amt"].round(0)', ""),
        ('df["twice"] = df["amt"].apply(lambda value: value * 2 if value == value else -1)', "twice:float"),
        ('df["const"] = 7', "const:int"),
        ('df["const"] = "x"', "const:str"),
        ('df["const"] = 1.5', "const:float"),
        ('df["const"] = True', "const:bool"),
        ('df["none"] = None', "none:str"),
        ('df["when"] = pd.Timestamp("2024-01-31") + pd.to_timedelta(df["id"].astype("int64"), unit="D")',
         "when:datetime@%Y-%m-%d"),
        ('df["when"] = pd.to_datetime(df["name"].map({"alice": "2024-01-31 10:11:12"}))',
         "when:datetime@%d/%m/%Y %H:%M:%S"),
        ('df["rank"] = df["amt"].rank()', "rank:float"),
        ('df["total"] = df["amt"].sum()', "total:float"),
        ('df["share"] = df["amt"] / df["amt"].sum()', "share:float#3"),
    ],
)
def test_columns_the_code_adds_or_changes(tmp_path, code, added):
    same(tmp_path, code, out=SCHEMA + (", " + added if added else ""))


@pytest.mark.parametrize(
    "code, declared",
    [
        ('df = df[df["id"] > 1]', SCHEMA),
        ('df = df[df["name"] != ""].reset_index(drop=True)', SCHEMA),
        ('df = df.sort_values("id", ascending=False)', SCHEMA),
        ('df = df.head(2)', SCHEMA),
        ('df = pd.concat([df, df])', SCHEMA),
        ('df = df.drop(columns=["name"])', "id:int, amt:float"),
        ('df = df[["amt", "id"]]', "amt:float, id:int"),
        ('df = df.rename(columns={"name": "who"})', "id:int, who:str, amt:float"),
        ('df = df.groupby("name", dropna=False, as_index=False).agg(total=("amt", "sum"), rows=("id", "count"))',
         "name:str, total:float, rows:int"),
        ('df = df.set_index("id")', "name:str, amt:float"),
        ('df = df.drop_duplicates(subset=["name"]).assign(rows=len(df))', SCHEMA + ", rows:int"),
    ],
)
def test_rows_and_columns_the_code_rearranges(tmp_path, code, declared):
    same(tmp_path, code, out=declared)


def test_column_names_that_are_not_text_become_text(tmp_path):
    run = same(tmp_path, 'df = df.rename(columns={"id": 7, "amt": 1.5})\ndf[8] = [1, "a", None]', declares=False)
    assert out(run)[:2] == ["7;name;1.5;8", "1;alice;10.5;1"]
    run, _ = alone(tmp_path, 'df[7] = 1\ndf["7"] = 2', declares=False)
    assert not run.succeeded and "python_code left more than one column named '7'" in run.error


def test_columns_nobody_declared_follow_the_declared_ones(tmp_path):
    run = same(tmp_path, 'df.insert(0, "first", "x")\ndf["last"] = df["amt"] * 2')
    assert out(run)[:2] == ["id;name;amt;first;last", "1;alice;10.5;x;21.0"]


def test_declared_columns_the_code_does_not_produce_are_added(tmp_path):
    run = same(tmp_path, "pass", out="amt:float, id:int, absent:str, zero:int!, name:str")
    assert out(run)[:2] == ["amt;id;absent;zero;name", "10.5;1;;0;alice"]


def test_frame_with_nothing_declared_is_written_as_the_code_left_it(tmp_path):
    run = same(tmp_path, 'df["up"] = df["name"].str.upper()\ndf = df[["up", "id", "amt"]]', declares=False)
    assert out(run) == ["up;id;amt", "ALICE;1;10.5", "BOB;2;", ";3;7.0"]


def test_missing_numbers_come_back_missing(tmp_path):
    code = '''
df["nan"] = np.nan
df["inf"] = np.inf
df["zero"] = df["amt"] * 0 / 0
df["na"] = pd.array([1, None, 3], dtype="Int64")
'''
    run = same(tmp_path, code, out=SCHEMA + ", nan:float, inf:float, zero:float, na:int")
    assert out(run)[1:] == ["1;alice;10.5;;inf;;1", "2;bob;;;inf;;", "3;;7.0;;inf;;3"]


def test_number_that_is_not_one_counts_as_missing_where_none_is_allowed(tmp_path):
    run = same(tmp_path, 'df["v"] = df["amt"] * 0 / 0', out=SCHEMA + ", v:float!", fails=True)
    assert "Column 'v' has NULL values but is not nullable" in run.error


def test_decimals_go_through_python(tmp_path):
    code = '''
from decimal import Decimal
df["twice"] = df["m"] * 2
df["plus"] = df["m"].apply(lambda value: value + Decimal("0.005"))
'''
    run = same(tmp_path, code, b"k;m\na;12.345\nb;7\nc;-1.005\n", "k:str, m:Decimal#2",
               out="k:str, m:Decimal#2, twice:Decimal#2, plus:Decimal#4")
    assert out(run)[1:] == ["a;12.35;24.70;12.3550", "b;7.00;14.00;7.0050", "c;-1.01;-2.02;-1.0050"]


def test_dates_go_through_python(tmp_path):
    code = '''
df["year"] = df["d"].dt.year
df["next"] = df["d"] + pd.Timedelta(days=1)
df["text"] = df["d"].dt.strftime("%d.%m.%Y")
'''
    data = b"k;d\na;2024-01-31 10:11:12\nb;\nc;1999-12-31 00:00:00\n"
    same(tmp_path, code, data, "k:str, d:datetime@%Y-%m-%d %H:%M:%S",
         out="k:str, d:datetime@%Y-%m-%d %H:%M:%S, year:int, next:datetime@%Y-%m-%d %H:%M:%S, text:str")


def test_column_of_mixed_values_is_written_value_by_value(tmp_path):
    code = 'df["mixed"] = [1, "a", 2.5]\ndf["texts"] = ["x", None, "z"]'
    run = same(tmp_path, code, out=SCHEMA + ", mixed:str, texts:str")
    assert out(run)[1:] == ["1;alice;10.5;1;x", "2;bob;;a;", "3;;7.0;2.5;z"]


# ------------------------------------------------------------------
# output_columns
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "names, declared",
    [
        (["up", "id"], "up:str, id:int"),
        (["id", "up", "nope"], "id:int, up:str"),
        (["name", "amt"], "amt:float, name:str, id:int"),
        (["nope"], SCHEMA + ", up:str"),
        ([], SCHEMA + ", up:str"),
        (None, SCHEMA + ", up:str"),
    ],
)
def test_output_columns_keep_the_listed_columns_that_exist(tmp_path, names, declared):
    same(tmp_path, 'df["up"] = df["name"].str.upper()', out=declared, output_columns=names)


def test_output_columns_the_result_has_none_of_are_warned_about(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    run, _ = alone(tmp_path, "pass", output_columns=["nope"])
    assert run.succeeded and out(run)[0] == "id;name;amt"
    assert ("WARNING", "[it] the result has none of the output_columns; every column is kept") in [
        (record.levelname, record.getMessage()) for record in caplog.records]
    caplog.clear()
    assert alone(tmp_path / "some", "pass", output_columns=["id", "nope"])[0].succeeded
    assert alone(tmp_path / "unset", "pass")[0].succeeded
    assert not [record for record in caplog.records if record.levelname == "WARNING"]


def test_output_columns_exactly(tmp_path):
    run = same(tmp_path, 'df["up"] = df["name"].str.upper()', declares=False, output_columns=["up", "nope", "id"])
    assert out(run) == ["up;id", "ALICE;1", "BOB;2", ";3"]


# ------------------------------------------------------------------
# No rows
# ------------------------------------------------------------------

@pytest.mark.parametrize("declared", [SCHEMA, SCHEMA + ", made:int", "made:int!, id:int"])
def test_code_is_not_run_on_a_flow_with_no_rows(tmp_path, declared):
    code = 'df["made"] = 1\nglobalMap.put("ran", True)\nraise RuntimeError("never")'
    run = same(tmp_path, code, b"id;name;amt\n", out=declared)
    assert out(run) == [declared.replace(":int!", "").replace(":int", "").replace(":str", "").replace(":float", "")
                        .replace(", ", ";")]
    _, result = alone(tmp_path, code, b"id;name;amt\n", out=declared)
    assert "ran" not in result.global_map


def test_code_that_was_not_run_is_said_so(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    assert alone(tmp_path, "pass", b"id;name;amt\n")[0].succeeded
    assert "[it] no rows: python_code was not run" in [record.getMessage() for record in caplog.records]


def test_code_that_removes_every_row_leaves_the_columns(tmp_path):
    run = same(tmp_path, 'df = df[df["id"] > 100]\ndf["made"] = "x"')
    assert out(run) == ["id;name;amt;made"]


# ------------------------------------------------------------------
# When the code or its result is wrong
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "code, said",
    [
        ('df["x"] = df["nope"] + 1', "python_code line 1: KeyError: 'nope'"),
        ('value = 1\n\ndf["x"] = value / 0', "python_code line 3: ZeroDivisionError: division by zero"),
        ('def boom(value):\n    raise ValueError("no " + str(value))\ndf["id"].apply(boom)',
         "python_code line 2: ValueError: no 1"),
        ("df = None", "python_code must leave a pandas DataFrame in 'df', found NoneType"),
        ('df = df["id"]', "python_code must leave a pandas DataFrame in 'df', found Series"),
        ("del df", "python_code must leave a pandas DataFrame in 'df', found nothing"),
    ],
)
def test_failing_code_fails_the_component(tmp_path, code, said):
    run = same(tmp_path, code, fails=True)
    assert f"failed at component it: {said}" in run.error


@pytest.mark.parametrize(
    "code, said",
    [
        ("df['x'] = = 1", "python_code: line 1: invalid syntax"),
        ("df['x'] = 1\n  df['y'] = 2", "python_code: line 2: unexpected indent"),
        ("", "python_code: must not be empty"),
    ],
)
def test_code_that_is_not_python_is_refused_before_anything_runs(tmp_path, code, said):
    run = same(tmp_path, code, fails=True)
    assert "JobRefusedError" in run.error and said in run.error


def test_blank_code_passes_the_rows_on(tmp_path):
    assert out(same(tmp_path, "   \n"))[1] == "1;alice;10.5"


def test_two_columns_of_one_name_cannot_be_passed_on(tmp_path):
    # v1 writes both; a Polars frame holds a name once.
    run, _ = alone(tmp_path, 'df = pd.concat([df, df[["id"]]], axis=1)')
    assert not run.succeeded and "python_code left more than one column named 'id'" in run.error


# ------------------------------------------------------------------
# Missing values where the schema allows none
# ------------------------------------------------------------------

def test_missing_value_where_none_is_allowed_fails_the_component_by_default(tmp_path):
    run = same(tmp_path, "pass", out="id:int, name:str, amt:float!", fails=True)
    assert "Column 'amt' has NULL values but is not nullable" in run.error


def test_missing_value_where_none_is_allowed_drops_the_row_when_errors_are_tolerated(tmp_path):
    run = same(tmp_path, "pass", out="id:int, name:str, amt:float!", die_on_error=False)
    assert out(run) == ["id;name;amt", "1;alice;10.5", "3;;7.0"]


def test_failing_code_fails_whatever_die_on_error_says(tmp_path):
    same(tmp_path, 'df["x"] = df["nope"]', die_on_error=False, fails=True)


# ------------------------------------------------------------------
# What v2 says no to, and what it lets pass
# ------------------------------------------------------------------

def refused(made):
    with pytest.raises(JobRefusedError) as caught:
        load_job(made)
    return caught.value.report.format()


@pytest.mark.parametrize(
    "config, said",
    [
        ({"dataframe": "arrow"}, "dataframe: 'arrow' is not allowed; use one of 'pandas', 'polars'"),
        ({"output_columns": "id"}, "output_columns: expected a list"),
        ({"output_columns": ["id", 7]}, "output_columns: 7 is not a column name"),
        ({"output_columns": ["id", "id"]}, "output_columns: 'id' is listed more than once"),
        ({"die_on_error": "maybe"}, "die_on_error: expected true or false"),
        ({"code": "pass"}, "code: unknown config key"),
        ({"imports": "import os"}, "imports: unknown config key"),
    ],
)
def test_refused_config(config, said):
    made = coded("pass")
    made["components"][1]["config"].update(config)
    assert said in refused(made)


def test_code_is_required():
    made = coded("pass")
    del made["components"][1]["config"]["python_code"]
    assert "python_code: required config key is missing" in refused(made)


def test_python_dataframe_takes_one_flow():
    made = coded("pass")
    made["components"].append(reader(SCHEMA, component_id="in2", outputs=("more",)))
    made["flows"].append(flow("more", "in2", "it"))
    assert "takes at most 1 input(s)" in refused(made)
    made = coded("pass")
    made["flows"] = made["flows"][1:]
    assert "needs 1 input(s), but 0 flows arrive" in refused(made)


@pytest.mark.parametrize("name", ["PythonDataFrameComponent", "tPythonDataFrame", "python_dataframe"])
def test_what_the_converter_writes_loads(name):
    made = coded("df['x'] = 1", die_on_error=False, tstatcatcher_stats=False, label="", execution_mode="batch",
                 chunk_size=10000)
    made["components"][1].update({"type": name, "original_type": "tPythonDataFrame", "position": {"x": 1, "y": 2}})
    spec = load_job(made).components["it"]
    assert spec.cls is PythonDataFrame
    assert spec.config == {"python_code": "df['x'] = 1", "dataframe": "pandas", "output_columns": [],
                           "die_on_error": False}


def test_context_names_in_the_code_are_left_to_the_code(tmp_path):
    made = with_context(coded('df["v"] = "${context.name}" + str(len("context.name"))', out=SCHEMA + ", v:str"),
                        name={"value": "kept", "type": "str"})
    assert out(same(tmp_path, None, made=made))[1] == "1;alice;10.5;${context.name}12"


# ------------------------------------------------------------------
# Kinds of column no v2 schema declares
# ------------------------------------------------------------------

@pytest.mark.parametrize(
    "code",
    [
        'df["v"] = pd.to_timedelta(df["id"].astype("int64"), unit="h")',
        'df["v"] = pd.Timestamp("2024-01-31").to_period("M")',
        'df["v"] = pd.interval_range(0, 3)',
        'df["v"] = [[1, 2], [3], []]',
        'df["v"] = [{"a": 1}, {"a": 2}, None]',
        'df["v"] = [b"a", b"b", None]',
        'df["v"] = pd.Timestamp("2024-01-31 10:00:00", tz="UTC")',
        'df["v"] = pd.Categorical(["x", "y", "x"])',
        'df["v"] = 1 + 2j',
        'df["v"] = [2**70, 1, 2]',
        'df["v"] = [1, "a", None]',
        'df["v"] = [1, "a", np.nan]',
        'df["v"] = [pd.NA, "a", 2.5]',
        'df["v"] = pd.to_timedelta([1, None, 3], unit="h")',
        'df["v"] = pd.PeriodIndex(["2024-01", None, "2024-03"], freq="M")',
        'import datetime\ndf["v"] = [datetime.date(2024, 1, 31), None, datetime.date(2024, 2, 1)]',
    ],
)
@pytest.mark.parametrize("declares", [True, False])
def test_other_kinds_of_column_come_back_as_the_text_v1_writes(tmp_path, code, declares):
    same(tmp_path, code, out=SCHEMA + ", v:str", declares=declares)


def test_other_kinds_of_column_exactly(tmp_path):
    code = 'df["gap"] = pd.to_timedelta(df["id"].astype("int64"), unit="h")\ndf["list"] = [[1, 2], [3], []]'
    assert out(same(tmp_path, code, declares=False))[1] == "1;alice;10.5;0 days 01:00:00;[1, 2]"


# ------------------------------------------------------------------
# Where v1 is not the answer
# ------------------------------------------------------------------

KINDS = 'df = pd.DataFrame({"column": list(df.columns), "dtype": [str(t) for t in df.dtypes], ' \
        '"kinds": [",".join(sorted({type(v).__name__ for v in df[c].tolist()})) for c in df.columns]})'
SCHEMA_OF = 'names = df.collect_schema()\n' \
            'df = pl.LazyFrame({"column": names.names(), "dtype": [str(t) for t in names.dtypes()]})'


def test_missing_decimal_is_handed_over_as_none(tmp_path):
    # v1's file input leaves the empty text of the field in the column instead.
    run, _ = alone(tmp_path, KINDS, b"k;m\na;1.5\nb;\n", "k:str, m:Decimal#2", out="column:str, dtype:str, kinds:str")
    assert out(run)[2] == "m;object;Decimal,NoneType"


def test_decimal_with_no_declared_places_is_handed_over_with_the_ten_v2_holds(tmp_path):
    # v1 hands over the digits of the source text: Decimal('1.50'), Decimal('7').
    code, data = 'df["text"] = df["n"].astype(str)\ndf["sum"] = df["n"] + df["n"]', b"k;n\na;1.50\nb;7\n"
    run, _ = alone(tmp_path, code, data, "k:str, n:Decimal", out="k:str, n:Decimal, text:str, sum:Decimal")
    assert out(run)[1:] == ["a;1.5;1.5000000000;3", "b;7;7.0000000000;14"]
    declared = same(tmp_path, code, data, "k:str, n:Decimal#2", out="k:str, n:Decimal#2, text:str, sum:Decimal#2")
    assert out(declared)[1:] == ["a;1.50;1.50;3.00", "b;7.00;7.00;14.00"]


def test_whole_numbers_are_nullable_unless_the_component_declares_otherwise(tmp_path):
    # v1 goes by the schema of the component before; v2's component is handed only its own.
    made = coded(KINDS, "i:int, j:int!", out="column:str, dtype:str, kinds:str")
    run, _ = alone(tmp_path, None, b"i;j\n1;2\n", made=made)
    assert out(run)[1:] == ["i;Int64;int", "j;int64;int"]
    made["components"][1]["schema"]["input"] = []
    run, _ = alone(tmp_path / "undeclared", None, b"i;j\n1;2\n", made=made)
    assert out(run)[1:] == ["i;Int64;int", "j;Int64;int"]
    made["components"][1]["schema"]["input"] = columns("i:int!, j:int!")
    run, _ = alone(tmp_path / "missing", None, b"i;j\n;2\n", made=made)
    assert out(run)[1:] == ["i;Int64;NAType", "j;int64;int"]


def test_missing_true_or_false_is_handed_over_as_pandas_missing(tmp_path):
    first = 'df["flag"] = pd.array([True, None, False], dtype="boolean")\ndf["sure"] = df["id"] > 1'
    run, _ = alone(tmp_path, None, made=chained(first, KINDS, out="column:str, dtype:str, kinds:str"))
    assert out(run)[4:] == ["flag;boolean;NAType,bool", "sure;bool;bool"]


def test_date_column_is_handed_over_as_dates_and_comes_back_one(tmp_path):
    data = b"k;d\na;2024-01-31\nb;\n"
    run, _ = alone(tmp_path, KINDS, data, "k:str, d:date", out="column:str, dtype:str, kinds:str")
    assert out(run)[2] == "d;object;NoneType,date"
    made = chained("pass", SCHEMA_OF, "k:str, d:date", out="column:str, dtype:str", dataframe="polars")
    run, _ = alone(tmp_path / "back", None, data, made=made)
    assert out(run)[1:] == ["k;String", "d;Date"]


def test_types_the_frame_comes_back_with(tmp_path):
    schema = "s:str, i:int, j:int!, f:float, b:bool, d:datetime@%Y-%m-%d, m:Decimal#2, n:Decimal"
    data = b"s;i;j;f;b;d;m;n\na;1;10;1.5;true;2024-01-31;12.345;1.5\n;;20;;;;;\n"
    code = '''from decimal import Decimal
df["text"] = df["s"] + "!"
df["whole"] = df["j"] * 2
df["part"] = df["j"] / 4
df["sure"] = df["j"] > 10
df["when"] = pd.Timestamp("2024-01-31")
df["money"] = [Decimal("1.50"), Decimal("2.25")]
df["own"] = [Decimal("1.5"), Decimal("2.25")]
df["none"] = None
df["small"] = np.array([1, 2], dtype="int32")
'''
    made = chained(code, SCHEMA_OF, schema, out="column:str, dtype:str", dataframe="polars")
    run, _ = alone(tmp_path, None, data, made=made)
    assert out(run)[1:] == [
        "s;String", "i;Int64", "j;Int64", "f;Float64", "b;Boolean", "d;Datetime(time_unit='us', time_zone=None)",
        "m;Decimal(precision=38, scale=2)", "n;Decimal(precision=38, scale=10)",
        "text;String", "whole;Int64", "part;Float64", "sure;Boolean", "when;Datetime(time_unit='us', time_zone=None)",
        "money;Decimal(precision=38, scale=2)", "own;String", "none;String", "small;Int32",
    ]


def test_column_that_comes_back_holding_nothing_keeps_its_type(tmp_path):
    schema = "k:str, i:int, m:Decimal#2, d:datetime@%Y-%m-%d"
    code = 'df["m"] = df["m"].apply(lambda value: value)\ndf["new"] = None\ndf["na"] = pd.NA\ndf["number"] = np.nan\n' \
           'df["i"] = df["i"].astype("float64")'
    made = chained(code, SCHEMA_OF, schema, out="column:str, dtype:str", dataframe="polars")
    run, _ = alone(tmp_path, None, b"k;i;m;d\na;;;\nb;;;\n", made=made)
    assert out(run)[1:] == ["k;String", "i;Float64", "m;Decimal(precision=38, scale=2)",
                            "d;Datetime(time_unit='us', time_zone=None)", "new;String", "na;String", "number;Float64"]
    made = chained('df = df[df["k"] == "nobody"]', SCHEMA_OF, schema, out="column:str, dtype:str", dataframe="polars")
    run, _ = alone(tmp_path / "no_rows", None, b"k;i;m;d\na;1;1.5;2024-01-31\n", made=made)
    assert out(run)[3] == "m;Decimal(precision=38, scale=2)"


@pytest.mark.parametrize("code", ["df = df[[]]", "df = pd.DataFrame()", "df = pd.DataFrame(index=range(5))"])
def test_result_with_no_columns_is_a_result_with_no_rows(tmp_path, code):
    # v1 writes a row of missing values for every row of an index that came without columns.
    run, _ = alone(tmp_path, code)
    assert out(run) == ["id;name;amt"]


def test_decimals_of_different_places_are_written_each_with_its_own_digits(tmp_path):
    # One Polars column has one number of places, so these are carried as text when nothing declares the column.
    run = same(tmp_path, 'from decimal import Decimal\ndf["v"] = [Decimal("1.5"), Decimal("2.25"), Decimal("3")]',
               declares=False)
    assert [line.split(";")[-1] for line in out(run)[1:]] == ["1.5", "2.25", "3"]


def test_missing_value_v1_writes_as_a_marker_is_written_empty(tmp_path):
    # v1 writes <NA> for a missing Decimal and <na> for a missing true-or-false value it could not convert.
    code = 'from decimal import Decimal\ndf["dec"] = [Decimal("1.5"), None, Decimal("2")]\n' \
           'df["flag"] = pd.array([True, None, False], dtype="boolean")'
    made = coded(code, out=SCHEMA + ", dec:Decimal#2, flag:bool")
    assert b"<NA>" in run_job(made, {"in.csv": DATA}, tmp_path / "v1", run_v1).files["out.csv"]
    run, _ = alone(tmp_path, None, made=made)
    assert out(run)[1:] == ["1;alice;10.5;1.50;true", "2;bob;;;", "3;;7.0;2.00;false"]


def test_routines_of_the_run_are_handed_to_the_code(tmp_path):
    code = '''
df["by_name"] = Tax.vat(df["amt"])
df["by_key"] = routines["Tax"].vat(df["amt"])
df["by_attribute"] = routines.Tax.vat(df["amt"])
df["known"] = ",".join(sorted(routines)) + "/" + ",".join(sorted(Tax))
try:
    routines.Nope
except AttributeError as error:
    df["said"] = str(error)
'''
    routines = {"Tax": {"vat": lambda amount: amount * 2}, "Other": {}}
    run, _ = alone(tmp_path, code, routines=routines,
                   out=SCHEMA + ", by_name:float, by_key:float, by_attribute:float, known:str, said:str")
    assert out(run)[1] == "1;alice;10.5;21.0;21.0;21.0;Other,Tax/vat;there is no 'Nope' here; known: Other, Tax"


# ------------------------------------------------------------------
# The Polars way
# ------------------------------------------------------------------

def test_polars_code_is_handed_a_lazy_frame_and_the_component_stays_lazy(tmp_path, monkeypatch):
    monkeypatch.setattr(PythonDataFrame, "run", lambda self, inputs: pytest.fail("the rows were taken in hand"))
    code = '''
globalMap.put("handed", type(df).__name__ + " " + str(isinstance(context, dict)))
df = df.filter(pl.col("id") > 1).with_columns((pl.col("amt") * 2).alias("dbl"))
'''
    run, result = alone(tmp_path, code, out=SCHEMA + ", dbl:float", dataframe="polars")
    assert out(run) == ["id;name;amt;dbl", "2;bob;;", "3;;7.0;14.0"]
    assert result.global_map["handed"] == "LazyFrame True"


@pytest.mark.parametrize(
    "pandas_code, polars_code, declared",
    [
        ('df["up"] = df["name"].str.upper()', 'df = df.with_columns(pl.col("name").str.to_uppercase().alias("up"))',
         SCHEMA + ", up:str"),
        ('df = df[df["id"] > 1]', 'df = df.filter(pl.col("id") > 1)', SCHEMA),
        ('df = df.sort_values("id", ascending=False)', 'df = df.sort("id", descending=True)', SCHEMA),
        ('df["dbl"] = df["amt"] * 2\ndf = df[["dbl", "id"]]',
         'df = df.select((pl.col("amt") * 2).alias("dbl"), "id")', "dbl:float, id:int"),
        ('df = df.groupby("name", as_index=False, sort=True).agg(total=("amt", "sum"))',
         'df = df.group_by("name").agg(pl.col("amt").sum().alias("total")).sort("name")', "name:str, total:float"),
        ("pass", "pass", SCHEMA),
        ('df["limit"] = context["limit"]', 'df = df.with_columns(pl.lit(context["limit"]).alias("limit"))',
         SCHEMA + ", limit:int"),
    ],
)
def test_polars_code_gives_what_the_pandas_code_gives_on_v1(tmp_path, pandas_code, polars_code, declared):
    limit = {"value": "5", "type": "int"}
    v1_job = with_context(coded(pandas_code, out=declared), limit=limit)
    v2_job = with_context(coded(polars_code, out=declared, dataframe="polars"), limit=limit)
    run = assert_matches_v1(v1_job, {"in.csv": DATA}, tmp_path, v2_job=v2_job)
    assert run.succeeded, run.error


def test_polars_code_may_leave_a_dataframe(tmp_path):
    run, _ = alone(tmp_path, "df = df.head(2).collect()", dataframe="polars")
    assert out(run) == ["id;name;amt", "1;alice;10.5", "2;bob;"]


def test_polars_code_runs_when_the_job_is_loaded_and_again_when_it_runs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "in.csv").write_bytes(DATA)
    note = 'with open("{}", "a") as handle:\n    handle.write("x")'
    loaded = load_job(coded(note.format("ran.txt"), dataframe="polars"))
    assert (tmp_path / "ran.txt").read_text() == "x"
    assert run_on_v2(loaded).status == "success"
    assert (tmp_path / "ran.txt").read_text() == "xx"
    assert load_job(coded(note.format("pandas.txt"))) and not (tmp_path / "pandas.txt").exists()


@pytest.mark.parametrize(
    "code, said",
    [
        ('df = df.with_columns(pl.col("nope") + 1)', "nope"),
        ("df = 5", "python_code must leave a Polars frame in 'df', found int"),
        ("df = df.collect().to_pandas()", "python_code must leave a Polars frame in 'df', found DataFrame"),
        ("del df", "python_code must leave a Polars frame in 'df', found nothing"),
        ("df = df.with_columns(nope=pd.NA)", "python_code line 1: NameError: name 'pd' is not defined"),
        ('value = context["later"]', "python_code line 1: KeyError: 'later'"),
        ("df = df.select(\n  1 +\n)", "python_code: line 3: invalid syntax"),
    ],
)
def test_polars_code_that_cannot_build_its_plan_is_refused_at_load(code, said):
    assert said in refused(coded(code, dataframe="polars"))


def test_polars_code_runs_on_a_flow_with_no_rows_too(tmp_path):
    code = 'globalMap.put("ran", True)\ndf = df.with_columns(pl.lit(1).alias("made"))'
    run, result = alone(tmp_path, code, b"id;name;amt\n", dataframe="polars")
    assert out(run) == ["id;name;amt;made"] and result.global_map["ran"] is True


def test_polars_output_columns(tmp_path):
    code = 'df = df.with_columns(pl.col("name").str.to_uppercase().alias("up"))'
    run, _ = alone(tmp_path, code, declares=False, dataframe="polars", output_columns=["up", "nope", "id"])
    assert out(run) == ["up;id", "ALICE;1", "BOB;2", ";3"]
    run, _ = alone(tmp_path / "none", code, declares=False, dataframe="polars", output_columns=["nope"])
    assert out(run)[0] == "id;name;amt;up"


def test_polars_result_with_no_columns_is_a_result_with_no_rows(tmp_path):
    run, _ = alone(tmp_path, "df = pl.LazyFrame()", dataframe="polars")
    assert out(run) == ["id;name;amt"]


def test_polars_code_reads_context_global_map_and_routines(tmp_path):
    code = '''
df = df.with_columns(
    pl.lit(context["limit"]).alias("limit"),
    pl.lit(globalMap.get("nope", "fallback")).alias("other"),
    Tax.vat(pl.col("amt")).alias("vat"),
    routines.Tax.vat(pl.col("amt"), rate=0.5).alias("half"),
)
globalMap.put("built", True)
'''
    made = with_context(coded(code, out=SCHEMA + ", limit:int, other:str, vat:float, half:float", dataframe="polars"),
                        limit={"value": "5", "type": "int"})
    routines = {"Tax": {"vat": lambda amount, rate=0.2: amount * rate}}
    run, result = alone(tmp_path, None, made=made, routines=routines)
    assert out(run)[1] == "1;alice;10.5;5;fallback;2.1;5.25"
    assert result.global_map["built"] is True


def test_decimals_of_different_lengths_made_by_the_code_keep_their_own_digits(tmp_path):
    # Python's Decimals each have their own number of places; one Polars column has one.
    code = "from decimal import Decimal\ndf['m3'] = df['m'].apply(lambda v: v / Decimal(3))\n"
    run = same(tmp_path, code, data=b"k;m\na;10.10\nb;4.00\nc;3.33\nd;0.05\n", schema="k:str, m:Decimal#2",
               declares=False)
    assert out(run)[1].startswith("a;10.10;3.366666666666666666666666667")


def test_decimals_of_one_length_made_by_the_code_stay_numbers(tmp_path):
    code = "from decimal import Decimal\ndf['twice'] = df['m'] * 2\n"
    run, result = alone(tmp_path, code, data=b"k;m\na;10.10\nb;4.00\n", schema="k:str, m:Decimal#2",
                        out="k:str, m:Decimal#2, twice:Decimal#2")
    assert run.succeeded and out(run) == ["k;m;twice", "a;10.10;20.20", "b;4.00;8.00"]
