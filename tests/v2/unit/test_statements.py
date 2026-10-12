"""A statement as a job writes it, and what the database is given: values bound, never written into the text."""
import pytest

from src.v2 import statements
from src.v2.errors import ConfigurationError

CONTEXT = {"d": "2024-01-31", "t": "EMP", "schema": "HR", "n": 5, "who": "o'brien", "s": "bri", "codes": "'A', 'B'",
           "ids": "1, 2,3", "cols": "ID, NAME", "sql": "select * from dual where 1 = ${context.n}", "none": None,
           "evil": "1; drop table emp", "f": 1.5, "part": "202401"}
HELD = {"tFileList_1_CURRENT_FILE": "a.csv", "k": "x'y", "row1.id": 7}


def read(written, **more):
    return statements.read(written, CONTEXT, HELD, **more)


def oracle(written, **more):
    """The text Oracle is given, and the values it is given beside it."""
    return read(written, **more).named()


def refused(written):
    with pytest.raises(ConfigurationError) as failed:
        read(written)
    return str(failed.value)


# ------------------------------------------------------------------
# A value in quotes is bound
# ------------------------------------------------------------------

@pytest.mark.parametrize("written", [
    "select * from emp where d = '${context.d}'",
    "select * from emp where d = 'context.d'",
    # As Talend joins it. The converter takes the outermost quotes off a statement that starts and ends with one.
    '"select * from emp where d = \'" + context.d + "\'"',
    'select * from emp where d = \'" + context.d + "\'',
])
def test_a_value_that_is_all_of_a_text_in_quotes_is_bound_in_its_place(written):
    assert oracle(written) == ("select * from emp where d = :context_d", {"context_d": "2024-01-31"})


def test_a_value_inside_a_longer_text_is_joined_to_the_rest_by_the_database():
    assert oracle("select * from emp where name like '%${context.s}%'") == (
        "select * from emp where name like '%' || :context_s || '%'", {"context_s": "bri"})
    assert oracle("select * from emp where name like '${context.s}%'") == (
        "select * from emp where name like :context_s || '%'", {"context_s": "bri"})
    assert oracle("select * from emp where name like '%${context.s}'") == (
        "select * from emp where name like '%' || :context_s", {"context_s": "bri"})
    assert oracle("select '${context.s}-${context.d}' from dual") == (
        "select :context_s || '-' || :context_d from dual", {"context_s": "bri", "context_d": "2024-01-31"})
    assert oracle("select '${context.s}${context.d}' from dual") == (
        "select :context_s || :context_d from dual", {"context_s": "bri", "context_d": "2024-01-31"})


def test_a_quote_in_a_value_is_a_quote_and_ends_nothing():
    text, binds = oracle("select * from emp where name = '${context.who}' or note = 'it''s ${context.who}'")
    assert text == "select * from emp where name = :context_who or note = 'it''s ' || :context_who"
    assert binds == {"context_who": "o'brien"}


def test_a_value_in_quotes_is_bound_as_text_whatever_it_is():
    assert oracle("select '${context.n}', '${context.none}', '${context.f}' from dual")[1] == {
        "context_n": "5", "context_none": "", "context_f": "1.5"}


def test_one_value_named_twice_is_bound_once():
    assert oracle("select * from t where a = '${context.d}' or b = 'context.d'") == (
        "select * from t where a = :context_d or b = :context_d", {"context_d": "2024-01-31"})


def test_an_entry_of_globalmap_is_bound_as_a_context_variable_is():
    written = '"select * from loads where file = \'" + ((String)globalMap.get("tFileList_1_CURRENT_FILE")) + "\' and k = \'" + globalMap.get("k") + "\'"'
    assert oracle(written) == (
        "select * from loads where file = :entry_tFileList_1_CURRENT_FILE and k = :entry_k",
        {"entry_tFileList_1_CURRENT_FILE": "a.csv", "entry_k": "x'y"})


def test_a_name_that_is_no_bind_name_is_made_one_and_two_that_would_be_one_are_told_apart():
    text, binds = statements.read(
        '"select \'" + globalMap.get("row1.id") + "\', \'" + globalMap.get("row1_id") + "\' from dual"', {},
        {"row1.id": 7, "row1_id": 8}).named()
    assert text == "select :entry_row1_id, :entry_row1_id_2 from dual"
    assert binds == {"entry_row1_id": "7", "entry_row1_id_2": "8"}
    long = "x" * 40
    text, binds = statements.read("select '${context." + long + "}' from dual", {long: "v"}, {}).named()
    assert text == "select :v2_1 from dual" and binds == {"v2_1": "v"}


# ------------------------------------------------------------------
# A value outside quotes is written in, and has to be a name, a number or a list
# ------------------------------------------------------------------

def test_a_name_and_a_number_outside_quotes_are_written_into_the_statement():
    assert oracle('"select * from " + context.schema + "." + context.t + " where id > " + context.n') == (
        "select * from HR.EMP where id > 5", {})
    assert oracle("select ${context.cols} from ${context.t} where id in (${context.ids}) and c in (${context.codes})") == (
        "select ID, NAME from EMP where id in (1, 2,3) and c in ('A', 'B')", {})
    assert oracle("alter table t truncate partition P_${context.part}") == ("alter table t truncate partition P_202401", {})
    assert oracle("select * from t where x < ${context.f}") == ("select * from t where x < 1.5", {})


@pytest.mark.parametrize("held", ["1; drop table emp", "EMP where 1=1", "a b", "x--", "(select 1 from dual)", "", "'a' or 'b'",
                                  "1 or 1=1", "'unclosed", "a;b", "emp e", "'a''b', (1)", "2024-01-31"])
def test_anything_else_outside_quotes_fails_the_statement_and_is_not_shown(held):
    with pytest.raises(ConfigurationError) as failed:
        statements.read("select * from emp where id = ${context.v}", {"v": held}, {})
    assert str(failed.value) == (
        "what context.v holds is written into the statement, since no quotes stand round it, and there it has to be "
        "a name, a number, or a list of names, numbers and texts in quotes; it is none of these. A value in quotes "
        "is bound, whatever it holds")
    if held:
        assert held not in str(failed.value)


@pytest.mark.parametrize("held", ["EMP", "hr.emp", "HR.EMP_2024$#", "5", "-5", "+5.25", "1, 2 , 3", "'A','it''s'", "A, 2, 'c'",
                                  "  EMP  ", "'x'", ".5", "5."])
def test_what_may_stand_outside_quotes(held):
    text, binds = statements.read("select ${context.v} from dual", {"v": held}, {}).named()
    assert text == f"select {held.strip()} from dual" and binds == {}


def test_a_missing_value_outside_quotes_fails_too():
    assert "what context.none holds is written into the statement" in refused("select * from t where a = ${context.none}")


def test_a_value_in_the_quotes_of_a_name_is_written_in_and_cannot_end_them():
    assert oracle('select * from "${context.t}"') == ('select * from "EMP"', {})
    with pytest.raises(ConfigurationError) as failed:
        statements.read('select * from "${context.v}"', {"v": 'a" union select'}, {})
    assert "what context.v holds is written between the quotes of a name" in str(failed.value)


def test_a_value_in_a_remark_is_held_to_what_stands_outside_quotes():
    assert oracle("select /*+ ${context.t} */ 1 from dual -- ${context.n}") == ("select /*+ EMP */ 1 from dual -- 5", {})
    assert "written into the statement" in refused("select 1 from dual -- ${context.evil}")
    assert "written into the statement" in refused("select /* ${context.evil} */ 1 from dual")


def test_quotes_in_a_remark_open_nothing():
    # The apostrophe is in a remark: what follows it stands outside quotes.
    assert "written into the statement" in refused("select 1 -- it's here\n from t where a = ${context.who}")
    assert "written into the statement" in refused("select 1 /* it's */ from t where a = ${context.who}")
    assert oracle("select 1 /* it's */ from t where a = '${context.who}'") == (
        "select 1 /* it's */ from t where a = :context_who", {"context_who": "o'brien"})


def test_texts_joined_side_by_side_are_one_text():
    # The quote that ends the first text is half of a pair with the one that starts the second: the text goes on,
    # and the value is joined to it.
    assert oracle('"select \'x\'" + "\'" + context.d + "\' from dual"') == (
        "select 'x''' || :context_d from dual", {"context_d": "2024-01-31"})


def test_a_pair_of_quotes_between_two_values_is_a_quote_between_them():
    assert oracle("select '${context.d}''${context.s}' from dual") == (
        "select :context_d || '''' || :context_s from dual", {"context_d": "2024-01-31", "context_s": "bri"})


def test_a_remark_ends_with_its_line():
    assert oracle("select 1 -- it's a remark\n from t where a = '${context.who}'") == (
        "select 1 -- it's a remark\n from t where a = :context_who", {"context_who": "o'brien"})


def test_a_text_written_oracles_other_way_in_the_national_set_takes_no_value_either():
    assert "stands inside a text written q'...'" in refused("select nq'[it's ${context.d}]' from dual")
    assert "stands inside a text written q'...'" in refused("select NQ'<${context.d}>' from dual")
    # A name that ends in q is no such text: the quote after it opens a plain one.
    assert oracle("select faq'${context.d}' from dual") == ("select faq:context_d from dual", {"context_d": "2024-01-31"})


def test_a_text_written_oracles_other_way_takes_no_value():
    assert refused("select q'[it's ${context.d}]' from dual") == (
        "context.d stands inside a text written q'...': write that text with plain quotes, so that the value can "
        "be bound")
    assert oracle("select q'[it's]', '${context.d}' from dual") == ("select q'[it's]', :context_d from dual",
                                                                    {"context_d": "2024-01-31"})


# ------------------------------------------------------------------
# What the whole statement may be
# ------------------------------------------------------------------

def test_a_statement_with_no_reference_is_as_it_is_written():
    plain = "select id, name\r\n  from employee\nwhere note = 'a ''quoted'' thing' -- done"
    assert oracle(plain) == (plain, {})


def test_a_statement_that_is_nothing_but_one_reference_is_what_that_holds_as_it_is():
    assert oracle("context.sql") == ("select * from dual where 1 = ${context.n}", {})
    assert oracle("${context.sql}") == ("select * from dual where 1 = ${context.n}", {})
    assert statements.read('((String)globalMap.get("q"))', {}, {"q": "delete from t"}).named() == ("delete from t", {})
    assert "what context.n holds is no statement: it is no text" in refused("context.n")
    assert "what context.none holds is no statement: it is no text" in refused("${context.none}")


def test_a_reference_to_what_is_not_there_fails():
    assert refused("select '${context.nope}' from dual") == "context has no variable 'nope'"
    assert refused('"select \'" + globalMap.get("nope") + "\' from dual"') == "globalMap has no entry 'nope'"
    assert refused('"select \'" + context.nope + "\' from dual"') == "context has no variable 'nope'"
    # Written bare in plain text, it may be a column of a table called context: left as it is.
    assert oracle("select context.nope from context") == ("select context.nope from context", {})


def test_java_that_is_more_than_joining_is_refused():
    said = ("the statement is joined as Java joins text, and holds more than text, context variables and entries of "
            "globalMap: v2 runs no Java. Write it as one text, with ${context.name} where a value goes")
    assert refused('"select * from t where d = \'" + TalendDate.formatDate("yyyy", context.d) + "\'"') == said
    assert refused('select * from t where d = \'" + context.d.substring(1) + "\'') == said
    assert refused('"select * from t where n = " + (context.n + 1)') == said


def test_a_name_in_double_quotes_is_no_java_and_one_next_to_a_plus_is_taken_for_it():
    assert oracle('select "A", b + 1 from t') == ('select "A", b + 1 from t', {})
    # What the converter leaves of Talend's joining looks the same as this. It is refused, and says how to write it.
    assert "joined as Java joins text" in refused('select "A" + 1 from t')
    assert "joined as Java joins text" in refused("select a, '\" + ' from t")


# ------------------------------------------------------------------
# A statement that defines takes no bound value
# ------------------------------------------------------------------

@pytest.mark.parametrize("first", ["create", "ALTER", " drop", "truncate", "/* a remark */ Create", "-- remark\n grant",
                                   "rename", "revoke", "comment", "analyze", "purge", "flashback"])
def test_a_statement_that_defines_is_known_by_its_first_word(first):
    assert read(f"{first} table t").defines is True


@pytest.mark.parametrize("first", ["select", "insert", "update", "delete", "merge", "begin", "declare", "call", "with",
                                   "(select", "", "createx", "lock"])
def test_any_other_statement_does_not_define(first):
    assert read(f"{first} 1").defines is False


def test_in_a_statement_that_defines_a_value_in_quotes_is_written_as_text_with_its_quotes_doubled():
    made = read("create table t2 as select * from t where name = '${context.who}' and d like '${context.d}%'")
    assert made.named() == ("create table t2 as select * from t where name = 'o''brien' and d like '2024-01-31%'", {})
    # What a log shows has the name of the value, never the value.
    assert made.shown() == "create table t2 as select * from t where name = :context_who and d like :context_d || '%'"


def test_what_a_log_shows_of_any_statement_has_names_and_no_values():
    made = read("delete from t where name = '${context.who}' and id in (${context.ids})")
    assert made.shown() == "delete from t where name = :context_who and id in (1, 2,3)"
    assert "o'brien" not in made.shown()


# ------------------------------------------------------------------
# The same statement for a database that binds by place
# ------------------------------------------------------------------

def test_values_by_place_and_text_joined_with_a_plus():
    made = read("select * from t where a = '${context.d}' and b like '%${context.s}%' or c = '${context.d}'")
    assert made.placed() == ("select * from t where a = ? and b like '%' + ? + '%' or c = ?",
                             ["2024-01-31", "bri", "2024-01-31"])


def test_what_cannot_be_read_whatever_the_context_holds_is_told_when_the_job_loads():
    assert statements.unreadable("select 1 from dual") is None
    assert statements.unreadable("select * from ${context.nope} where d = '${context.also_not}'") is None
    assert statements.unreadable('"select * from " + context.t') is None
    assert statements.unreadable('select * from t where d = \'" + context.d + "\'') is None
    assert statements.unreadable("context.sql") is None
    assert statements.unreadable('"select \'" + TalendDate.getDate("yyyy") + "\' from dual"').startswith(
        "the statement is joined as Java joins text")
