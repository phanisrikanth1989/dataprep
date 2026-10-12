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


# ------------------------------------------------------------------
# A statement run for each row of a flow: a value of the row is bound, wherever it stands
# ------------------------------------------------------------------

def for_rows(written, row="row1", columns=("id", "name", "d"), **more):
    return statements.read(written, CONTEXT, HELD, row=(row, list(columns)), **more)


def test_a_value_of_the_row_is_bound_wherever_it_stands():
    made = for_rows('"update t set name = \'" + row1.name + "\', d = \'" + context.d + "\' where id = " + row1.id')
    text, bound = made.by_place()
    assert text == "update t set name = :1, d = :2 where id = :3"
    assert [(part.column, part.value) for part in bound] == [("name", None), (None, "2024-01-31"), ("id", None)]
    assert made.shown() == "update t set name = :row1_name, d = :context_d where id = :row1_id"


def test_a_value_of_the_row_inside_a_longer_text_is_joined_by_the_database():
    made = for_rows('"select 1 from t where name like \'%" + row1.name + "%\' or id = " + row1.id + " or id = " + row1.id')
    text, bound = made.by_place()
    assert text == "select 1 from t where name like '%' || :1 || '%' or id = :2 or id = :3"
    assert [part.column for part in bound] == ["name", "id", "id"]


def test_a_column_the_row_does_not_have_is_said():
    with pytest.raises(ConfigurationError) as failed:
        for_rows('"delete from t where id = " + row1.nope')
    assert str(failed.value) == "the rows of row1 have no column 'nope'; they have: id, name, d"


def test_a_name_with_a_dot_inside_the_text_of_the_statement_is_no_value_of_the_row():
    # Between Java's quotes it is SQL: a table called row1, or one given that name.
    made = for_rows('"delete from t row1 where row1.id = " + row1.id')
    assert made.by_place()[0] == "delete from t row1 where row1.id = :1"
    assert for_rows("delete from t row1 where row1.id = 5").by_place() == ("delete from t row1 where row1.id = 5", [])


def test_without_rows_a_name_like_that_of_a_row_is_java_that_is_not_read():
    assert "joined as Java joins text" in refused('"delete from t where id = " + row1.id')


def test_a_statement_for_rows_cannot_be_one_that_defines_with_a_value_of_the_row():
    with pytest.raises(ConfigurationError) as failed:
        for_rows('"create table x as select * from t where id = \'" + row1.id + "\'"')
    assert str(failed.value) == ("a statement that defines takes no bound value, and a value of a row can only be "
                                 "bound: row1.id cannot stand in this one")


def test_a_value_of_the_row_stands_only_where_a_value_can_be_bound():
    for written in ('"delete from t -- " + row1.id', '"delete from t /* " + row1.id + " */"', '"delete from \\"" + row1.name + "\\""'):
        with pytest.raises(ConfigurationError) as failed:
            for_rows(written)
        assert "stands where no value can be bound: in a remark, or between the quotes of a name" in str(failed.value)


def test_a_statement_that_defines_has_no_mark():
    with pytest.raises(ConfigurationError) as failed:
        statements.read("create table x as select * from t where a = ?", {}, {}, parameters=[statements.Given(value=1)])
    assert str(failed.value) == "a statement that defines takes no bound value, and this one has a mark (?)"


def test_by_place_every_value_has_a_place_of_its_own():
    made = read("select * from t where a = '${context.d}' or b = '${context.d}' or c = '${context.s}'")
    text, bound = made.by_place()
    assert text == "select * from t where a = :1 or b = :2 or c = :3"
    assert [part.value for part in bound] == ["2024-01-31", "2024-01-31", "bri"]


# ------------------------------------------------------------------
# A prepared statement: a value for each mark
# ------------------------------------------------------------------

def test_each_mark_takes_the_value_given_for_its_place():
    made = statements.read("update t set a = ?, b = ? where c = ? and d = '?' -- why?", {}, {},
                           parameters=[statements.Given(value="x"), statements.Given(value=5), statements.Given(column="id")],
                           row=("row1", ["id"]))
    text, bound = made.by_place()
    assert text == "update t set a = :1, b = :2 where c = :3 and d = '?' -- why?"
    assert [(part.column, part.value) for part in bound] == [(None, "x"), (None, 5), ("id", None)]
    assert made.shown() == "update t set a = :p1, b = :p2 where c = :p3 and d = '?' -- why?"


def test_a_value_for_a_mark_keeps_its_kind_and_is_handed_over_by_name_too():
    made = statements.read("delete from t where a = ? and b = ?", {}, {},
                           parameters=[statements.Given(value=5), statements.Given(value=None)])
    assert made.named() == ("delete from t where a = :p1 and b = :p2", {"p1": 5, "p2": None})


@pytest.mark.parametrize("written, given, said", [
    ("delete from t where a = ? and b = ?", 1, "the statement has 2 marks (?) and 1 value(s) are given for them"),
    ("delete from t where a = ?", 2, "the statement has 1 marks (?) and 2 value(s) are given for them"),
    ("delete from t", 1, "the statement has 0 marks (?) and 1 value(s) are given for them"),
])
def test_as_many_values_as_marks(written, given, said):
    with pytest.raises(ConfigurationError) as failed:
        statements.read(written, {}, {}, parameters=[statements.Given(value=1)] * given)
    assert str(failed.value) == said


def test_without_values_given_a_mark_is_left_to_the_database():
    assert oracle("select * from t where a = ?") == ("select * from t where a = ?", {})


# ------------------------------------------------------------------
# A text of the national set (N'...')
# ------------------------------------------------------------------

def test_a_value_that_is_all_of_a_national_text_takes_the_place_of_its_n_too():
    assert oracle("select * from emp where name = N'${context.s}'") == (
        "select * from emp where name = :context_s", {"context_s": "bri"})


def test_a_national_text_keeps_its_n_on_both_sides_of_a_value():
    # Without it the part after the value is a plain text, and a database keeps of that only what its own set of
    # characters has.
    binds = {"context_s": "bri"}
    assert oracle("select N'a${context.s}b' from dual") == ("select N'a' || :context_s || N'b' from dual", binds)
    assert oracle("select n'a${context.s}' from dual") == ("select n'a' || :context_s from dual", binds)
    assert oracle("select n'a${context.s}b' from dual") == ("select n'a' || :context_s || n'b' from dual", binds)
    assert oracle("select N'${context.s}b' from dual") == ("select :context_s || N'b' from dual", binds)
    assert oracle("select N'${context.s}-${context.d}!' from dual") == (
        "select :context_s || N'-' || :context_d || N'!' from dual", {"context_s": "bri", "context_d": "2024-01-31"})


def test_the_last_letter_of_a_word_before_a_quote_is_no_n_of_a_text():
    assert oracle("select case when a = 1 then'${context.s}' end from t") == (
        "select case when a = 1 then:context_s end from t", {"context_s": "bri"})
    assert oracle("select case when a = 1 then'a${context.s}b' end from t") == (
        "select case when a = 1 then'a' || :context_s || 'b' end from t", {"context_s": "bri"})


def test_in_a_statement_that_defines_a_national_text_keeps_its_n():
    made = read("create table t2 as select N'${context.who}' x, N'a${context.s}' y from dual")
    assert made.named() == ("create table t2 as select N'o''brien' x, N'abri' y from dual", {})


# ------------------------------------------------------------------
# As SQL Server reads a statement
# ------------------------------------------------------------------

def tsql(written, context=None, **more):
    """The text SQL Server is given, and the values it is given beside it, in the order of their marks."""
    return statements.read(written, CONTEXT if context is None else context, HELD, dialect=statements.TSQL,
                           **more).placed()


def test_for_sql_server_a_value_in_quotes_is_bound_at_a_mark_and_texts_are_joined_with_a_plus():
    assert tsql("select * from emp where d = '${context.d}' and name like N'%${context.s}%' and c = N'${context.s}'") == (
        "select * from emp where d = ? and name like N'%' + ? + N'%' and c = ?", ["2024-01-31", "bri", "bri"])


def test_a_quote_between_square_brackets_opens_no_text():
    written = "select [it's] from emp where d = '${context.d}'"
    assert tsql(written) == ("select [it's] from emp where d = ?", ["2024-01-31"])
    # Oracle knows no such name: there the quote opens a text, and the value stands outside it.
    assert refused(written).startswith("what context.d holds is written into the statement")


def test_a_doubled_bracket_ends_no_name():
    assert tsql("select [a]]'b] from emp where d = '${context.d}'") == (
        "select [a]]'b] from emp where d = ?", ["2024-01-31"])


def test_a_value_between_square_brackets_is_written_in_and_cannot_end_them():
    assert tsql("select * from [${context.schema}].[${context.t}] where d = '${context.d}'") == (
        "select * from [HR].[EMP] where d = ?", ["2024-01-31"])
    with pytest.raises(ConfigurationError) as failed:
        tsql("select * from [${context.v}]", {"v": "a] union select"})
    assert "between the quotes of a name" in str(failed.value) and "union" not in str(failed.value)


def test_a_remark_inside_a_remark_ends_only_itself():
    written = "select 1 /* a /* b */ it's still a remark */ from emp where d = '${context.d}'"
    assert tsql(written) == ("select 1 /* a /* b */ it's still a remark */ from emp where d = ?", ["2024-01-31"])
    # For Oracle the remark ends where the first one does, and the quote after it opens a text.
    assert refused(written).startswith("what context.d holds is written into the statement")


def test_a_value_in_a_remark_inside_a_remark_is_held_to_what_stands_outside_quotes():
    assert tsql("select 1 /* a /* b */ ${context.t} */ from emp") == ("select 1 /* a /* b */ EMP */ from emp", [])
    with pytest.raises(ConfigurationError):
        tsql("select 1 /* a /* b */ ${context.evil} */ from emp")


def test_sql_server_knows_no_text_written_oracles_other_way():
    written = "select 1 q'${context.s}'"
    assert tsql(written) == ("select 1 q?", ["bri"])
    assert "q'...'" in refused(written)


@pytest.mark.parametrize("held", ["#stage", "_work", "tempdb.dbo.#stage", "a@b"])
def test_a_name_of_sql_servers_may_start_with_an_underline_or_a_hash(held):
    assert tsql("select * from ${context.v}", {"v": held}) == (f"select * from {held}", [])
    with pytest.raises(ConfigurationError):
        statements.read("select * from ${context.v}", {"v": held}, {})


@pytest.mark.parametrize("held", ["@x", "@@version", "dbo.@x", "1; drop table emp", "a b"])
def test_what_is_no_name_of_sql_servers_outside_quotes(held):
    with pytest.raises(ConfigurationError) as failed:
        tsql("select * from ${context.v}", {"v": held})
    assert held not in str(failed.value)


def test_for_sql_server_no_statement_takes_its_values_as_text():
    made = statements.read("create table #t (d date); select * from emp where d = '${context.d}'", CONTEXT, HELD,
                           dialect=statements.TSQL)
    assert (made.defines, made.pasted) == (False, None)
    assert made.placed() == ("create table #t (d date); select * from emp where d = ?", ["2024-01-31"])


def test_a_statement_for_sql_server_that_is_one_reference_is_what_that_holds():
    made = statements.read("context.sql", {"sql": "create table t (n int)"}, {}, dialect=statements.TSQL)
    assert (made.placed(), made.defines, made.dialect) == (("create table t (n int)", []), False, statements.TSQL)


def test_what_a_log_shows_of_a_statement_for_sql_server_has_marks_and_no_values():
    made = statements.read("select * from emp where name = '${context.who}' and note like 'a${context.s}'", CONTEXT,
                           HELD, dialect=statements.TSQL)
    assert made.shown() == "select * from emp where name = ? and note like 'a' + ?"
    assert made.shown() == made.placed()[0]


def test_by_name_a_statement_is_handed_over_one_way_whatever_database_it_was_read_for():
    made = statements.read("select * from [emp] where note like 'a${context.s}'", CONTEXT, HELD, dialect=statements.TSQL)
    assert made.named() == ("select * from [emp] where note like 'a' || :context_s", {"context_s": "bri"})


def test_a_bound_value_between_an_n_and_a_quote_stays_where_it_is():
    # No statement a database takes, but nothing bound may go missing from one, whatever it is.
    made = statements.read("select N?'a', ?N'b${context.s}' from dual", CONTEXT, HELD,
                           parameters=[statements.Given(value=1), statements.Given(value=2)])
    assert made.named() == ("select N:p1'a', :p2N'b' || :context_s from dual", {"p1": 1, "p2": 2, "context_s": "bri"})


# ------------------------------------------------------------------
# A value written into a statement cannot end a remark, start one, or make one with what stands before it
# ------------------------------------------------------------------

BOTH = [statements.ORACLE, statements.TSQL]
NO_REMARK_MARKS = (
    "what context.v holds is written into the statement, since no quotes stand round it, and there it may hold no "
    "line break or other control character, and no /* or */: any of these could end a remark it stands in, or start "
    "one. A value in quotes is bound, whatever it holds")


@pytest.mark.parametrize("dialect", BOTH)
@pytest.mark.parametrize("written, held", [
    # Each of these was sent to a real database as a statement the job had not written.
    ("select n, v from t /* run for ${context.v} */ where n = 1", "'*/ where 1=0 union all select n, v from secret /*'"),
    ("delete from t where n = 2 -- asked by ${context.v}\n", "'\n or 1=1 --'"),
    ("select n, v from t -- ${context.v}\n order by n", "'\n; drop table victim; select n, v from t --'"),
    ("create table q (n number /* asked by ${context.v} */)", "'*/, injected number /*'"),
    # No text in quotes is needed for it: a list on two lines adds a column to what is selected.
    ("select a -- ${context.v}\nfrom t", "x\n, secret_col"),
    ("select a -- ${context.v}\nfrom t", "x\r, secret_col"),
    ("select a -- ${context.v}\nfrom t", "1,\r\n2"),
    # In SQL Server a remark may stand in a remark: one that is opened there swallows the end of the outer one.
    ("select n /* ${context.v} */ , secret from t", "'/*'"),
])
def test_a_value_in_a_remark_cannot_end_the_remark_or_open_another(written, held, dialect):
    with pytest.raises(ConfigurationError) as failed:
        statements.read(written, {"v": held}, {}, dialect=dialect)
    assert str(failed.value) == NO_REMARK_MARKS
    assert "secret" not in str(failed.value) and "victim" not in str(failed.value)


@pytest.mark.parametrize("dialect", BOTH)
@pytest.mark.parametrize("held", ["'a\nb', 'c'", "1,\n2", "'a*/b'", "'/*'", "'a\x00b'", "'a\x0bb'", "'a\x85b'"])
def test_what_is_written_in_outside_a_remark_is_held_to_the_same(held, dialect):
    # Where a remark ends is each database's own to say. A value that could not end one anywhere is safe wherever
    # the reader and the database might not agree.
    with pytest.raises(ConfigurationError) as failed:
        statements.read("select * from t where c in (${context.v})", {"v": held}, {}, dialect=dialect)
    assert str(failed.value) == NO_REMARK_MARKS


def test_the_separators_of_lines_and_paragraphs_are_line_breaks_too():
    for code in (0x2028, 0x2029):
        with pytest.raises(ConfigurationError) as failed:
            statements.read("select 1 -- ${context.v}\n from t", {"v": "'a" + chr(code) + "b'"}, {})
        assert str(failed.value) == NO_REMARK_MARKS


def test_an_entry_of_globalmap_in_a_remark_is_held_to_the_same():
    with pytest.raises(ConfigurationError) as failed:
        statements.read('"select 1 /* for " + ((String)globalMap.get("f")) + " */ from t"', {}, {"f": "'*/ x /*'"})
    assert str(failed.value) == NO_REMARK_MARKS.replace("context.v", "the entry 'f' of globalMap")


@pytest.mark.parametrize("dialect", BOTH)
@pytest.mark.parametrize("held", ["'a--b', 'c'", "1,\t2", "EMP\n", "\r\n 5 \n", "'a b'", "'it''s'"])
def test_what_a_value_written_in_may_still_hold(held, dialect):
    text = statements.read("select 1 /* ${context.v} */ from t where c in (${context.v})", {"v": held}, {},
                           dialect=dialect).shown()
    assert text == f"select 1 /* {held.strip()} */ from t where c in ({held.strip()})"


@pytest.mark.parametrize("dialect", BOTH)
def test_a_number_below_nought_after_a_minus_does_not_make_a_remark_of_the_rest_of_the_line(dialect):
    made = statements.read("select n from t where a = b -${context.n} and kept = 1", {"n": "-1"}, {}, dialect=dialect)
    assert made.shown() == "select n from t where a = b - -1 and kept = 1"
    made = statements.read("select d-${context.n}, e - ${context.n}, f-${context.m} from t", {"n": "-7", "m": "7"}, {},
                           dialect=dialect)
    assert made.shown() == "select d- -7, e - -7, f-7 from t"
    made = statements.read("select d-${context.n} from t", {"n": "-1, -2"}, {}, dialect=dialect)
    assert made.shown() == "select d- -1, -2 from t"


def test_a_line_remark_ends_where_its_own_database_ends_it():
    written = "select 1 -- it's a remark\r from t where a = '${context.who}'"
    # A carriage return by itself ends such a remark in SQL Server: the quote after it opens a text.
    assert tsql(written) == ("select 1 -- it's a remark\r from t where a = ?", ["o'brien"])
    # In Oracle it does not: the rest of the line is remark still, and the value stands in it.
    assert refused(written).startswith("what context.who holds is written into the statement")
    both = "select 1 -- it's a remark\r\n from t where a = '${context.who}'"
    assert tsql(both) == ("select 1 -- it's a remark\r\n from t where a = ?", ["o'brien"])
    assert oracle(both) == ("select 1 -- it's a remark\r\n from t where a = :context_who", {"context_who": "o'brien"})
