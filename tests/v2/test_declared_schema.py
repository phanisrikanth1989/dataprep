"""What v1 does to every component's output to make it match the declared
schema, and v2 does too. A sort that changes nothing is the component here;
its declared output differs from its input in the way each test names."""
import pytest

from tests.v2.answer_key import assert_matches_v1
from tests.v2.components.kit import columns, through

SORT = {"type": "SortRow", "config": {"criteria": [{"column": "id", "sort_type": "num", "order": "asc"}]}}
DATA = b"id;name;amount;day\n1;alice;10.5;2024-01-31\n2;bob;20;2024-02-01\n3;;;\n"
IN = "id:int, name:str, amount:float, day:datetime@%Y-%m-%d"


def same(tmp_path, out_schema, data=DATA, in_schema=IN, writer_schema=None, fails=False, **config):
    job = through(dict(SORT, config=dict(SORT["config"], **config)), in_schema, out_schema)
    if writer_schema is not None:
        job["components"][2]["schema"]["input"] = columns(writer_schema)
    run = assert_matches_v1(job, {"in.csv": data}, tmp_path)
    assert run.succeeded is not fails, run.error
    return run.files.get("out.csv")


def only_v2(tmp_path, job, data):
    """Run a job on v2 alone, where v1's result is one v2 does not copy."""
    from tests.v2.answer_key import run_job, run_v2

    run = run_job(job, {"in.csv": data}, tmp_path / "v2", run_v2)
    assert run.succeeded, run.error
    return run.files["out.csv"]


def test_declared_order_wins_and_undeclared_columns_follow(tmp_path):
    out = same(tmp_path, "day:datetime@%Y-%m-%d, id:int")
    assert out.splitlines()[0] == b"day;id;name;amount"


def test_declared_column_nobody_produced_is_added(tmp_path):
    schema = IN + ", extra:str, count:int, ratio:float, seen:datetime@%Y-%m-%d"
    out = same(tmp_path, schema, writer_schema=schema)
    assert out.splitlines()[1] == b"1;alice;10.5;2024-01-31;;;;"


def test_added_decimal_and_bool_columns_are_empty(tmp_path):
    # v1 writes the text <NA> for the Decimal column and <na> for the bool one.
    schema = IN + ", total:Decimal#2, ok:bool"
    job = through(dict(SORT), IN, schema)
    job["components"][2]["schema"]["input"] = columns(schema)
    out = only_v2(tmp_path, job, DATA)
    assert out.splitlines()[1] == b"1;alice;10.5;2024-01-31;;"


def test_added_column_that_may_not_be_missing_is_zero(tmp_path):
    schema = IN + ", extra:str!, count:int!, ratio:float!, ok:bool!"
    out = same(tmp_path, schema, writer_schema=schema)
    assert out.splitlines()[1] == b"1;alice;10.5;2024-01-31;;0;0.0;false"


@pytest.mark.parametrize(
    "declared, amounts",
    [("id:str", "10.25 20.75"), ("id:float", "10.25 20.75"), ("amount:int", "10.0 20.0"), ("name:int", "10.25 20.75"),
     ("amount:str", "10.25 20.75"), ("day:str", "10.25 20.75"), ("amount:float#0", "10.25 20.75"),
     ("amount:float#1", "10.25 20.75")],
)
def test_declaring_another_type_for_a_column(tmp_path, declared, amounts):
    name = declared.split(":")[0]
    kept = ", ".join(part for part in IN.split(", ") if not part.startswith(name + ":"))
    first, second = amounts.split()
    data = f"id;name;amount;day\n1;7;{first};2024-01-31\n2;8;{second};2024-02-01\n".encode()
    same(tmp_path, f"{declared}, {kept}", data=data)


def test_fraction_in_a_column_declared_int_is_cut(tmp_path):
    # v1 cuts it only when the column may not be missing; otherwise it leaves the whole column as floats.
    kept = ", ".join(part for part in IN.split(", ") if not part.startswith("amount:"))
    job = through(dict(SORT), IN, f"amount:int, {kept}")
    out = only_v2(tmp_path, job, b"id;name;amount;day\n1;7;10.75;2024-01-31\n2;8;-20.75;2024-02-01\n")
    assert out == b"amount;id;name;day\n10;1;7;2024-01-31\n-20;2;8;2024-02-01\n"


def test_text_declared_a_number_or_a_date_is_read(tmp_path):
    data = b"id;a;b;c\n1;12;1.5;2024-01-31\n2;7;2;2024-02-01\n"
    out_schema = "id:int, a:int, b:float, c:datetime@%Y-%m-%d"
    out = same(tmp_path, out_schema, data=data, in_schema="id:int, a:str, b:str, c:str", writer_schema=out_schema)
    assert out.splitlines()[1] == b"1;12;1.5;2024-01-31"


def test_decimal_is_rounded_to_the_declared_places(tmp_path):
    data = b"id;m\n1;1.005\n2;2.675\n3;7\n"
    out = same(tmp_path, "id:int, m:Decimal#2", data=data, in_schema="id:int, m:Decimal#4", writer_schema="id:int, m:Decimal#2")
    assert out == b"id;m\n1;1.01\n2;2.68\n3;7.00\n"


def test_missing_value_where_the_declared_schema_allows_none_fails_the_component(tmp_path):
    same(tmp_path, "id:int, name:str, amount:float!, day:datetime@%Y-%m-%d", fails=True)


ERRORS = b"id;errorCode;errorMessage\n2;E2;second\n1;E1;first\n"
ERRORS_IN = "id:int, errorCode:str, errorMessage:str"


@pytest.mark.parametrize("declared", ["id:int", "id:int, errorCode_user:str, errorMessage_user:str"])
def test_error_columns_are_renamed_when_they_pass_through_a_component(tmp_path, declared):
    out = same(tmp_path, declared, data=ERRORS, in_schema=ERRORS_IN, writer_schema="id:int")
    assert out == b"id;errorCode_user;errorMessage_user\n1;E1;first\n2;E2;second\n"


def test_renamed_error_column_stands_in_for_the_name_the_schema_still_declares(tmp_path):
    # v1 adds an empty column under the declared name and then renames it too: each column twice.
    job = through(dict(SORT), ERRORS_IN, ERRORS_IN)
    job["components"][2]["schema"]["input"] = []
    out = only_v2(tmp_path, job, ERRORS)
    assert out == b"id;errorCode_user;errorMessage_user\n1;E1;first\n2;E2;second\n"
