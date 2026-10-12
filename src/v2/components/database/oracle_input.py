"""Oracle input: the rows of a query."""
from __future__ import annotations

from typing import List, Tuple

from ... import oracle
from ...job.keys import Key, Kind
from ...sessions import Session
from ..registry import REGISTRY
from .reading import READING_KEYS, DatabaseInput


@REGISTRY.register
class OracleInput(DatabaseInput):
    """Read the rows of a query from an Oracle database.

    The query is run once. Its rows rest in a scratch file, and the
    engine reads that: however often it reads a source again, the
    database is asked once. It reads on the session of the connection
    component `connection` names when `use_existing_connection` is on,
    and otherwise on one it opens with its own connection block and
    closes when the rows are in.

    Columns are taken by their place. The database converts each to its
    declared type, so a number keeps every digit: a `Decimal` is rounded
    to its places as Oracle rounds, and one too wide for them fails the
    query. Text that is declared as anything else is read as the text of
    a file is. A date with a time zone is taken as text only: a
    `datetime` has no zone, and the query has to say which clock is
    meant.

    A context variable or an entry of globalMap in the query is a value:
    one in quotes is bound, and one outside quotes has to be a name, a
    number or a list of those. The query is left in `<id>_QUERY` as it
    was sent: with the names of its bound values, and no value.

    A failure names a row as `row 3 of the result of <id>`.
    """
    names = ("oracle_input", "OracleInput", "tOracleInput")
    uses_session = "Oracle"
    keys = READING_KEYS + oracle.WORKING_KEYS + oracle.CONNECTION_KEYS + (
        Key("is_convert_xmltype", kind=Kind.IGNORED, type=object,
            doc="Talend's switch for XMLType columns; say `.getclobval()` in the query to read one as text."),
        Key("convert_xmltype", kind=Kind.IGNORED, type=object, doc="See `is_convert_xmltype`."),
    )

    def problems(self) -> List[str]:
        return super().problems() + oracle.working_problems(self.config)

    def session(self) -> Tuple[Session, bool]:
        return oracle.session_of(self)
