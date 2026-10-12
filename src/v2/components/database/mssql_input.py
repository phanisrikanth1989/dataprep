"""SQL Server input: the rows of a query."""
from __future__ import annotations

from typing import Any, List, Tuple

from ... import mssql, statements
from ...job.keys import Key
from ...sessions import Session
from ..registry import REGISTRY
from .reading import READING_KEYS, DatabaseInput


def _seconds(value: Any) -> int:
    text = str(value).strip() if isinstance(value, (str, int)) else "?"
    if not text.isdigit() or int(text) < 1:
        raise ValueError(f"{value!r} is no number of seconds: give a whole number, 1 or more")
    return int(text)


@REGISTRY.register
class MssqlInput(DatabaseInput):
    """Read the rows of a query from a SQL Server database.

    The query is run once, as it is written: with its `ORDER BY`, its
    `WITH`, or as the call of a procedure (`exec dbo.p '${context.d}'`).
    Its rows rest in a scratch file, and the engine reads that: however
    often it reads a source again, the database is asked once. It reads
    on the session of the connection component `connection` names when
    `use_existing_connection` is on, and otherwise on one it opens with
    its own connection block and closes when the rows are in.

    Of what a statement hands back, the first thing that has columns is
    read. What comes before it (the count of rows a procedure changed) is
    passed over, and so is what comes after it; a failure after the rows
    fails the job.

    Columns are taken by their place, and each is made what the job
    declares the way SQL Server's own `CAST` would: a whole number is cut
    off at its point, a `Decimal` is rounded to its places with a half
    going away from nought, a float goes by the number it exactly is. A
    number too large for what is declared fails the job and names the
    row. Text that is declared as anything else is read as the text of a
    file is. A `time` is read as text. A `datetime2` is cut to the
    millionth of a second. A `datetimeoffset`, binary data and a
    `sql_variant` are not read: the query has to turn them into text.

    A context variable or an entry of globalMap in the query is a value:
    one in quotes is bound, and one outside quotes has to be a name, a
    number or a list of those. The query is left in `<id>_QUERY` as it
    was sent: with a `?` where each bound value goes, and no value.

    A failure names a row as `row 3 of the result of <id>`.
    """

    names = ("mssql_input", "MSSqlInput", "tMSSqlInput")
    uses_session = "SQL Server"
    dialect = statements.TSQL
    keys = READING_KEYS + mssql.WORKING_KEYS + mssql.CONNECTION_KEYS + (
        Key("set_query_timeout", type=bool, default=False,
            doc="Whether the query is given no more time than `query_timeout_in_seconds`."),
        Key("query_timeout_in_seconds", type=object, default=30, convert=_seconds,
            doc="The seconds the query is given before its first rows come, with `set_query_timeout`. One that takes "
                "longer fails the job."),
    )

    def problems(self) -> List[str]:
        return super().problems() + mssql.working_problems(self.config)

    def session(self) -> Tuple[Session, bool]:
        session, own = mssql.session_of(self)
        session.limit = self.config["query_timeout_in_seconds"] if self.config["set_query_timeout"] else 0
        return session, own
