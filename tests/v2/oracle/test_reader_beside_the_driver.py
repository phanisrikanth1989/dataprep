"""The statement reader beside the driver's own reading of a statement, at every place of many small ones.

Where the reader takes a place for the statement itself, a value there is
bound or written in; where it takes it for a text or a remark, it is not.
The driver reads a statement too, to find what is bound in it. The two
are held side by side: after the same text, does each think a bound value
would be one?
"""
import itertools
import random
import re

import pytest

from src.v2 import statements

pytestmark = pytest.mark.oracle

MARK = " , :zzmark , "
PARTS = ["q", "Q", "n", "N", "'", "'", "'", "'", "!", "!", "[", "]", "(", ")", "<", ">", "{", "}", "-", "/", "*", '"', "\n", " ",
         "a", "''", "q'", "q'", "nq'", "Nq'", "--", "/*", "*/", "|", "q'!", "q'[", "]'", "!'", "x"]
# The driver takes any q before a quote for the start of a text written q'...'. Oracle itself, asked on 2026-10-12,
# takes a q that ends a word for the end of that word, as the reader does (ORA-03046 names the plain text after
# it), and takes no statement that has a word against a quote. Such statements are left out.
WORD_THEN_Q = re.compile(r"[A-Za-z0-9_$#][nN]?[qQ]'")
# A q before a quote whose mark would be a blank, a tab or a line break. Oracle takes no such statement (ORA-00911,
# asked on 2026-10-13), and of one with no end the thin driver says so while Oracle's own client says nothing. Left
# out too.
Q_THEN_BLANK = re.compile(r"[qQ]'(?:\s|\Z)")


def _state(text):
    writer = statements._Writer(False, None, statements.ORACLE)
    writer._text(text)
    return writer.state


def _small_statements():
    """Every text of a few characters that matter, and many longer ones put together at random."""
    made = set()
    # Every one of up to six of these, and of up to seven of those: a text whose mark is followed by a quote, and
    # one that starts a line after a word, are among them. The reader once took each for something else.
    for letters, longest in ((["q", "'", "!", "[", "]", "a"], 6), (["a", "\n", "q", "'"], 7)):
        for size in range(1, longest + 1):
            made.update("".join(parts) for parts in itertools.product(letters, repeat=size))
    chosen = random.Random(20261012)
    while len(made) < 100000:
        made.add("".join(chosen.choice(PARTS) for _ in range(chosen.randint(1, 12))))
    return sorted(made)


def test_the_reader_and_the_driver_agree_where_a_statement_is_itself(oracle_db):
    import oracledb

    with oracle_db.connect() as held, held.cursor() as cursor:
        def finds(text):
            try:
                cursor.prepare(text)
                return "ZZMARK" in cursor.bindnames()
            except oracledb.Error:
                return None  # a quote with no end: the driver reads none of it

        compared, differ = 0, []
        for soup in _small_statements():
            whole = "select " + soup
            if WORD_THEN_Q.search(soup) or Q_THEN_BLANK.search(soup) or finds(whole + " ") is None:
                continue
            final = _state(whole)
            if final == "block":
                continue  # the driver takes a remark with no end for no remark; Oracle takes neither
            if final not in ("code", "line"):
                differ.append((soup, len(soup), final, "read whole"))
                continue
            for at in range(len(soup) + 1):
                before = "select " + soup[:at]
                found = finds(before + MARK + soup[at:])
                if found is None or _state(before + MARK + soup[at:]) == "block":
                    continue
                compared += 1
                state = _state(before + " , ")
                if (state == "code") != found:
                    differ.append((soup, at, state, found))
    assert differ == []
    # Enough of them were of a kind both could read.
    assert compared > 50000
