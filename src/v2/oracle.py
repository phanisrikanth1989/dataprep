"""Oracle: what of a job config a session is opened with, and a session over python-oracledb.

The driver is imported when the first session is opened, so that a job
with no Oracle component needs none. It is used in thin mode, with no
client of Oracle's to install, unless the job config asks for the other
(``oracle_config.thick_mode``).

What the driver was seen to do against a real database, and what it gets
wrong, is in ``.scratch/engine-v2/issues/118-databases-the-decisions.md``.
"""
from __future__ import annotations

import logging
import os
import re
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Mapping, Optional, Tuple

import polars as pl

from .column_types import DEFAULT_DECIMAL_SCALE
from .errors import DatabaseError
from .job.keys import Key, Kind
from .sessions import (  # noqa: F401
    DATE, NUMBER, OTHER, TEXT, WORKING_KEYS, ZONED, CallFailed, Field, Session, filled, in_ascii, listed,
    password_problems,
)

if TYPE_CHECKING:
    from .components.base import Component
    from .job.model import Column
    from .statements import Statement

logger = logging.getLogger(__name__)

# How a session says in the database which program it is, for whoever looks at what runs there.
MODULE = "dataprep-v2"
# The most bytes of a job's name the database keeps beside it.
_ACTION_BYTES = 64
# Earlier drivers hand on wrong decimals across batches and lose dates read as dates.
_OLDEST = (26, 0, 1)
_JDBC = re.compile(r"\s*jdbc:oracle:\w+:", re.IGNORECASE)
# Oracle's old way of writing a SID in a JDBC URL: host, port, SID.
_OLD_SID = re.compile(r"([^:/@()\s]+):(\d+):([\w$#.]+)")
_BLANKS = re.compile(r"[ \t\r\n\f\v]+")
# The most characters of a connect string that a log line shows.
_SHOWN = 80

SID, SERVICE, OCI, CUSTOM, WALLET = "ORACLE_SID", "ORACLE_SERVICE_NAME", "ORACLE_OCI", "ORACLE_RAC", "ORACLE_WALLET"


def _port(value: Any) -> int:
    text = str(value).strip() if isinstance(value, (str, int)) else "?"
    if text == "":
        return 1521
    if not text.isdigit() or not 1 <= int(text) <= 65535:
        raise ValueError(f"{value!r} is no port: give a whole number from 1 to 65535")
    return int(text)


# The connection block: what a converted job carries on every component that can open a session.
CONNECTION_KEYS: Tuple[Key, ...] = (
    Key("connection_type", default=SID, choices=(SID, SERVICE, OCI, CUSTOM, WALLET),
        doc="How the database is named: by `host`, `port` and a SID in `dbname` (`ORACLE_SID`), by those and a "
            "service name in `dbname` (`ORACLE_SERVICE_NAME`), by a name of tnsnames.ora in `local_service_name` "
            "(`ORACLE_OCI`), or by a connect string in `rac_url` (`ORACLE_RAC`)."),
    Key("host", default="", doc="The database server."),
    Key("port", type=object, default=1521, convert=_port, doc="Its port."),
    Key("dbname", default="", doc="The SID or the service name, as `connection_type` says."),
    Key("local_service_name", default="", doc="For `ORACLE_OCI`: the name the database has in tnsnames.ora."),
    Key("rac_url", default="",
        doc="For `ORACLE_RAC`: a connect string, as Oracle writes one or as a JDBC URL. It carries no user and "
            "no password."),
    Key("use_tns_file", type=bool, default=False, doc="For `ORACLE_OCI`: whether tnsnames.ora is the file `tns_file` names."),
    Key("tns_file", default="", doc="That file. Without it the driver looks where `TNS_ADMIN` says."),
    Key("schema_db", default="", aliases=("table_schema", "dbschema"),
        doc="The schema a table is looked for in, when it is not the user's own."),
    Key("user", default="", doc="The user."),
    Key("password", default="", secret=True, doc="The password. It is shown in no log and kept nowhere."),
    Key("properties", default="", doc="Talend's JDBC parameters. None is read: any that is given refuses the job."),
    Key("use_ssl", kind=Kind.REFUSED, type=object,
        reason="Java key stores are not read; a `rac_url` that says `tcps` opens a session over TLS, with the "
               "server's certificate in the system's store"),
    Key("use_shared_connection", kind=Kind.REFUSED, type=object,
        reason="a session is not shared between a job and the jobs it runs: each opens its own"),
    Key("jdbc_url", kind=Kind.IGNORED, type=object, doc="Talend's URL for a wallet; see `connection_type`."),
    Key("db_version", kind=Kind.IGNORED, type=object, doc="Which JDBC driver Talend loads."),
    Key("encoding", kind=Kind.IGNORED, type=object, doc="The driver speaks to the database in Unicode."),
    Key("support_nls", kind=Kind.IGNORED, type=object, doc="A JDBC library Talend loads."),
    Key("shared_connection_name", kind=Kind.IGNORED, type=object, doc="See `use_shared_connection`."),
    Key("specify_datasource_alias", kind=Kind.IGNORED, type=object, doc="For Talend's own runtime."),
    Key("datasource_alias", kind=Kind.IGNORED, type=object, doc="For Talend's own runtime."),
    Key("ssl_trustserver_truststore", kind=Kind.IGNORED, type=object, doc="See `use_ssl`."),
    Key("need_client_auth", kind=Kind.IGNORED, type=object, doc="See `use_ssl`."),
    Key("ssl_keystore", kind=Kind.IGNORED, type=object, doc="See `use_ssl`."),
    Key("disable_cbc_protection", kind=Kind.IGNORED, type=object, doc="See `use_ssl`."),
)


# How Oracle's driver names the types of a result, by the kind each is to a job's declared types.
_FAMILIES = {
    NUMBER: ("DB_TYPE_NUMBER", "DB_TYPE_BINARY_FLOAT", "DB_TYPE_BINARY_DOUBLE", "DB_TYPE_BINARY_INTEGER"),
    TEXT: ("DB_TYPE_VARCHAR", "DB_TYPE_NVARCHAR", "DB_TYPE_CHAR", "DB_TYPE_NCHAR", "DB_TYPE_CLOB", "DB_TYPE_NCLOB"),
    DATE: ("DB_TYPE_DATE", "DB_TYPE_TIMESTAMP"),
    ZONED: ("DB_TYPE_TIMESTAMP_TZ", "DB_TYPE_TIMESTAMP_LTZ"),
}
_FAMILY = {said: family for family, names in _FAMILIES.items() for said in names}
ADVICE = {
    ZONED: "say in the query which clock is meant, `sys_extract_utc(...)` for UTC or `cast(... as timestamp)` for "
           "the clock of the value's own zone",
    OTHER: "turn it into text, a number or a date in the query",
}
# The name the query has inside the one that converts its columns.
_INNER = "v2q"
# What the driver says, before it sends anything, of a statement that is no insert, update, delete or merge and is
# handed over for many rows the way those are.
_NOT_FOR_MANY = "DPY-2040"
# The session data unit a session asks for: the most there is, which is Oracle's own advice for moving data in bulk.
# The two sides settle on the smaller of what each asks for, and the driver's own is 8 KB: ten million rows were
# read in 5.3 seconds with that and in 4.6 with the 64 KB the database allowed. A connect string that names a unit of
# its own keeps it. Oracle's own client takes its unit from its own files and is asked in vain. Measured on
# 2026-10-13, python-oracledb 26.0.1.
_UNIT = 2_097_152
# What the driver says, in its own mode, of a database that asks for what only Oracle's own client does: Native
# Network Encryption, and a password kept the way Oracle 10 kept one.
_ONLY_ITS_OWN_CLIENT = ("DPY-3001", "DPY-3015")
# Rows a round trip when a session of Oracle's own client reads and the job does not say. Ten million rows of eight
# columns took 22 seconds and 1.5 GB at 50,000 rows a round trip, 14 seconds and 0.9 GB at 2,000, 15 seconds at
# 1,000: the client keeps room for each column's widest value, for as many rows as a round trip brings. Without
# the client the number hardly matters (12 to 14 seconds), and the reader's own stands. Measured on 2026-10-13,
# python-oracledb 26.0.1, Instant Client 23.26.
_CLIENTS_ROUND_TRIP = 2_000
# What Oracle's own client says (thick mode) of a query handed over for many rows: "not supported". Of a block it
# says what the driver says above. Seen on 2026-10-13, Instant Client 23.26.
_NO_QUERY_FOR_MANY = "DPI-1013"
# What Oracle says of a block or a call that cannot be compiled: the statement's own fault, and no row's. The place
# the driver gives with it is one in the statement's text, and no row. (The same from inside a block while it
# runs, in text the block put together, has the lines of where it was raised, ORA-06512, and is its row's.)
_NOT_COMPILED = ("ORA-06550", "ORA-06576", "ORA-06553")
# An insert of given values with a query among them. Sent for many rows at once, Oracle works out the query of
# every row from the table as it was before the first, so that a row does not see what the rows before it put
# there (three rows of `max(n) + 1` get one number). Every other statement is run for a row after the row before
# it is done. What the word is found in besides (a text, a name) only costs round trips.
_READS_AS_IT_WRITES = re.compile(r"\binsert\b.*\bvalues\b.*\bselect\b", re.IGNORECASE | re.DOTALL)
# The most characters a procedure hands out as text: what PL/SQL's own text holds.
_TEXT_OUT = 32767
# A number as text: the same digits in every session, whatever its language says a decimal point is.
_NUMBER_AS_TEXT = "'TM9', 'nls_numeric_characters=" + "''.,''" + "'"


def session_of(component: "Component") -> Tuple[Session, bool]:
    """The session a component works on: its connection's, or one it opens with its own connection block.

    Returns:
        The session, and whether it is the component's own: one it opened,
        which nothing else knows of yet.
    """
    config, run = component.config, component.run_context
    if config["use_existing_connection"]:
        return run.sessions.shared(config["connection"]), False
    return opened(config, component.id, run.job_name, run.oracle), True


def working_problems(config: Mapping[str, Any]) -> List[str]:
    """What is wrong with the connection block of a component that works in the database: nothing, when it works
    on the session of a connection component and its own block is not read."""
    return [] if config["use_existing_connection"] else problems(config)


def reading(statement: str, columns: List["Column"], fields: List[Field]) -> Tuple[str, List[Any]]:
    """The query that has Oracle hand each column on as the job declares it, and the Arrow type each is asked for in.

    The job's query is given a name, and its columns names by their place
    (`"C1"`...), so that two columns of one name, or one of none, are told
    apart. What it holds stays as it is written: its own `WITH`, its
    `ORDER BY`, its hints, and the names of its bound values.
    """
    import pyarrow

    names = [f'"C{at}"' for at in range(1, len(fields) + 1)]
    selected: List[str] = []
    types: List[Any] = []
    for column, field, name in zip(columns, fields, names):
        made, kind = name, pyarrow.large_string()
        if field.family == NUMBER:
            if column.type == "int":
                # Cut, as everywhere a whole-number column is filled. One too large for 64 bits fails the query.
                made, kind = f"trunc({name})", pyarrow.int64()
            elif column.type == "float":
                made, kind = f"cast({name} as binary_double)", pyarrow.float64()
            elif column.type == "Decimal":
                places = DEFAULT_DECIMAL_SCALE if column.precision is None else column.precision
                # Rounded as Oracle rounds. One too wide fails the query (ORA-01438), where the driver would
                # hand on another number.
                made, kind = f"cast({name} as number(38, {places}))", pyarrow.decimal128(38, places)
            elif column.type == "bool":
                made = f"case when {name} is null then null when {name} = 0 then 0 else 1 end"
                kind = pyarrow.int8()
            else:
                # Oracle writes a half as `.5`: the nought it leaves out is put before the point.
                made = f"regexp_replace(to_char({name}, {_NUMBER_AS_TEXT}), '^(-?)[.]', '\\10.')"
        elif field.family == DATE:
            if column.type == "datetime":
                made, kind = f"cast({name} as timestamp(6))", pyarrow.timestamp("us")
            elif column.type == "date":
                made, kind = f"trunc(cast({name} as date))", pyarrow.date32()
            elif "TIMESTAMP" in field.said:
                # Rounded to the millionth first, as a datetime of the same column is: written out, Oracle cuts.
                made = f"to_char(cast({name} as timestamp(6)), 'YYYY-MM-DD HH24:MI:SS.FF6')"
            else:
                made = f"to_char({name}, 'YYYY-MM-DD HH24:MI:SS')"
        elif field.family == ZONED:
            made = f"to_char({name}, 'YYYY-MM-DD HH24:MI:SS.FF6 TZH:TZM')"
        selected.append(f"{made} {name}")
        types.append(kind)
    inner = statement.rstrip()
    if inner.endswith(";"):
        inner = inner[:-1]
    # The query ends on a line of its own: a remark at its end must not take the bracket with it.
    text = f"with {_INNER} ({', '.join(names)}) as (\n{inner}\n) select {', '.join(selected)} from {_INNER}"
    return text, types


def problems(config: Mapping[str, Any]) -> List[str]:
    """What is wrong with a connection block that a session is to be opened with. Nothing here shows a secret."""
    found: List[str] = []
    kind = config["connection_type"]
    if kind == WALLET:
        return [
            "connection_type: ORACLE_WALLET keeps the user and the password in a wallet only Oracle's own client "
            "reads, and v2 opens no session that way; give `user` and `password` and one of the other types"
        ]
    if kind in (SID, SERVICE):
        named = "a SID" if kind == SID else "a service name"
        found += [f"{key}: is empty; a session is opened with a host and {named}" for key in ("host", "dbname")
                  if not filled(config[key])]
    else:
        key = "rac_url" if kind == CUSTOM else "local_service_name"
        if not filled(config[key]):
            found.append(f"{key}: is empty; `connection_type` {kind} opens a session with it")
        elif kind == CUSTOM and _address(config[key])[0]:
            found.append("rac_url: carries a user and a password; give them in `user` and `password`, and the URL "
                         "from the `@` on")
    if not filled(config["user"]):
        found.append("user: is empty")
    found += password_problems(config["password"])
    named = [part.split("=", 1)[0].strip() for part in str(config["properties"] or "").split("&&") if part.strip()]
    if named:
        are = "is a parameter" if len(named) == 1 else "are parameters"
        it = "it" if len(named) == 1 else "them"
        found.append(f"properties: {listed(named)} {are} of Oracle's JDBC driver, which v2 does not use; take {it} out")
    return found


def arguments(config: Mapping[str, Any]) -> Dict[str, Any]:
    """What the driver is given to open a session with a connection block. The password is one of them, by itself."""
    kind = config["connection_type"]
    given: Dict[str, Any] = {"user": config["user"], "password": config["password"], "sdu": _UNIT}
    if kind in (SID, SERVICE):
        given.update(host=config["host"].strip(), port=config["port"])
        given["sid" if kind == SID else "service_name"] = config["dbname"].strip()
    elif kind == CUSTOM:
        where = _address(config["rac_url"])[1]
        old = _OLD_SID.fullmatch(where)
        if old:
            given.update(host=old.group(1), port=int(old.group(2)), sid=old.group(3))
        else:
            given["dsn"] = where
    else:
        given["dsn"] = config["local_service_name"].strip()
        if config["use_tns_file"] and config["tns_file"]:
            given["config_dir"] = os.path.dirname(config["tns_file"])
    return given


def opened(
    config: Mapping[str, Any],
    opened_by: str,
    job_name: str,
    settings: Optional[Mapping[str, Any]] = None,
    **more: Any,
) -> "OracleSession":
    """Open a session with a connection block.

    Args:
        config: The block, checked against ``CONNECTION_KEYS`` and with
            nothing ``problems`` finds.
        opened_by: The id of the component that opens it.
        job_name: The job, which the session says in the database it runs.
        settings: The job config's ``oracle_config``.
        **more: What else the session is to hold (``Session``).

    Raises:
        DatabaseError: When no session could be opened. It says where and
            as whom, and never the password.
    """
    driver = _driver(settings or {})
    given = arguments(config)
    what = f"{config['user']}@{_place(given)}"
    try:
        if "config_dir" in given and not driver.is_thin_mode():
            # Oracle's own client looks a name up in the tnsnames.ora of its own folder, and passes over the one a
            # connection names (ORA-12154, seen on 2026-10-13). The driver's reader of that file works in either
            # mode: the name is looked up with it, and the session opened with what the name stands for.
            named = driver.ConnectParams(config_dir=given.pop("config_dir"))
            named.parse_connect_string(given["dsn"])
            given["dsn"] = named.get_connect_string()
        held = driver.connect(**given)
        held.module = MODULE
        held.action = job_name.encode("utf-8")[:_ACTION_BYTES].decode("utf-8", "ignore")
    except (driver.Error, OSError) as fault:
        # Of a host no one knows the driver hands on what the system said, and no error of its own.
        why = said(fault)
        if any(code in why for code in _ONLY_ITS_OWN_CLIENT):
            why = (f"{why.rstrip('.')}. Only Oracle's own client does that: where it is installed, a job asks for it "
                   'with "oracle_config": {"thick_mode": true}')
        raise DatabaseError(f"no session was opened as {what}: {why}") from None
    client = "" if held.thin else ", with Oracle's own client"
    logger.info(in_ascii(f"[{opened_by}] session opened: {what} (Oracle {held.version}{client})"))
    return OracleSession(held, driver, opened_by, what, schema=config["schema_db"], **more)


def said(fault: Any) -> str:
    """What the driver said, on one line of plain ASCII, without the link to Oracle's help that follows it."""
    text = _BLANKS.sub(" ", str(fault).split("\nHelp:")[0]).strip()
    return in_ascii(text) or type(fault).__name__


class OracleSession(Session):
    """A session with an Oracle database, over python-oracledb."""

    advice = ADVICE

    def __init__(self, held: Any, driver: Any, opened_by: str, what: str, **more: Any) -> None:
        super().__init__(opened_by, what, **more)
        self._held = held
        self._driver = driver

    @property
    def rows_a_round_trip(self) -> Optional[int]:
        return None if self._held.thin else _CLIENTS_ROUND_TRIP

    def _handed(self, cursor: Any, rows: Any) -> Any:
        """Rows as the driver takes them best: an Arrow table as it is, and for Oracle's own client as tuples.

        Handed to the client as an Arrow table, ten thousand rows of eight
        columns took 2.2 GB, a million rows 3.5 seconds to insert and a
        block of PL/SQL for 100,000 rows 17.6 seconds; as tuples 0.4 GB,
        2.6 seconds and 0.7 seconds. Without the client an Arrow table is
        the faster (1.75 seconds a million rows). Measured on 2026-10-13,
        python-oracledb 26.0.1, Instant Client 23.26.

        Args:
            cursor: The cursor the rows are sent on: it is told what each
                column is where the rows no longer say it themselves.
            rows: An Arrow table; or, for a statement that takes no value,
                how many times it is run.
        """
        if isinstance(rows, int) or self._held.thin:
            return rows
        cursor.setinputsizes(*self._kinds(rows))
        return pl.from_arrow(rows).rows()

    def _kinds(self, rows: Any) -> List[Any]:
        """What the driver is told each column of an Arrow table is when its rows go as plain values: what the
        driver reads from such a table itself.

        By itself a moment is bound as a DATE and loses its fraction of a
        second, and a float as a NUMBER. Seen on 2026-10-13, in either
        mode. A text is left to the driver, which makes room for it.
        """
        import pyarrow

        driver, said = self._driver, pyarrow.types
        told: List[Any] = []
        for field in rows.schema:
            kind = field.type
            if said.is_timestamp(kind):
                told.append(driver.DB_TYPE_TIMESTAMP)
            elif said.is_date(kind):
                told.append(driver.DB_TYPE_DATE)
            elif said.is_floating(kind):
                told.append(driver.DB_TYPE_BINARY_DOUBLE)
            elif said.is_boolean(kind):
                told.append(driver.DB_TYPE_BOOLEAN)
            elif said.is_integer(kind) or said.is_decimal(kind):
                told.append(driver.DB_TYPE_NUMBER)
            else:
                told.append(None)
        return told

    def bound(self, statement: "Statement") -> Tuple[str, Any]:
        return statement.named()

    def fields(self, statement: str, binds: Any = None) -> List[Field]:
        with self._asked(), self._held.cursor() as cursor:
            # Parsed and not run: the columns are known without a value for anything that is bound.
            cursor.parse(statement)
            return [Field(column.name, _FAMILY.get(column.type_code.name, OTHER), _said(column.type_code.name))
                    for column in cursor.description or []]

    def typed(self, statement: str, columns: List["Column"], fields: List[Field]) -> Tuple[str, List[Any]]:
        return reading(statement, columns, fields)

    def batches(self, statement: str, binds: Any, types: List[Any], size: int) -> Iterator[Any]:
        import pyarrow

        asked = pyarrow.schema([pyarrow.field(f"C{at}", kind) for at, kind in enumerate(types, start=1)])
        with self._asked():
            for batch in self._held.fetch_df_batches(statement, parameters=dict(binds or {}), size=size,
                                                     requested_schema=asked):
                yield pyarrow.table(batch)

    def run(self, statement: str, binds: Optional[Mapping[str, Any]] = None) -> int:
        with self._asked(), self._held.cursor() as cursor:
            cursor.execute(statement, dict(binds or {}))
            return cursor.rowcount

    def many(self, statement: str, rows: Any, counts: bool = False) -> Tuple[List[Tuple[int, str]], List[int]]:
        several = not isinstance(rows, int)
        total = rows.num_rows if several else rows
        # An insert that reads as it writes goes one row at a time: see ``_READS_AS_IT_WRITES``.
        step = 1 if _READS_AS_IT_WRITES.search(statement) else max(total, 1)
        refused: List[Tuple[int, str]] = []
        changed: List[int] = []
        with self._asked(), self._held.cursor() as cursor:
            for start in range(0, total, step):
                sent = (rows.slice(start, step) if several else min(step, total - start)) if step < total else rows
                try:
                    cursor.executemany(statement, self._handed(cursor, sent), batcherrors=True, arraydmlrowcounts=counts)
                except self._driver.Error as fault:
                    if start or _code(fault) not in (_NOT_FOR_MANY, _NO_QUERY_FOR_MANY):
                        raise
                    return self._in_turn(cursor, statement, rows, counts, fault)
                refused += [(start + error.offset, said(error.message)) for error in cursor.getbatcherrors()]
                changed += list(cursor.getarraydmlrowcounts()) if counts else []
        return sorted(refused), changed

    def _in_turn(
        self, cursor: Any, statement: str, rows: Any, counts: bool, why: Any
    ) -> Tuple[List[Tuple[int, str]], List[int]]:
        """Run for each row a statement that is no insert, update, delete or merge: a block, a call, a query.

        The driver takes a block or a call for many rows at once and stops
        at the first that fails: it is sent again from the row after that
        one. A query it takes for one row only (sent for many, the session
        is lost), so a query is run row by row, and what it hands back is
        not fetched. What a block changed cannot be counted.

        A failure that leaves the session closed is no row's: it is raised,
        and nothing more is asked.

        Args:
            why: What the driver said of the statement handed over for
                many rows. Oracle's own client says "not supported" of a
                query; the same words of a statement that is no query are
                that statement's own failure, and are raised as they are.
        """
        several = not isinstance(rows, int)
        total = rows.num_rows if several else rows
        refused: List[Tuple[int, str]] = []
        # A query is read here without being run: what is wrong with it is told now, and is no row's fault. (Of a
        # block the driver learns nothing here.)
        cursor.parse(statement)
        if cursor.description is not None:
            if several:
                # The values go as plain values here, in either mode: what each is, is said for them.
                cursor.setinputsizes(*self._kinds(rows))
            for at, given in enumerate([list(row.values()) for row in rows.to_pylist()] if several else [None] * total):
                try:
                    cursor.execute(statement, given)
                except self._driver.Error as fault:
                    if not self._held.is_healthy():
                        raise
                    refused.append((at, said(fault)))
            return refused, [0] * total if counts else []
        if _code(why) == _NO_QUERY_FOR_MANY:
            raise why
        start = 0
        while start < total:
            try:
                cursor.executemany(statement, self._handed(cursor, rows.slice(start)) if several else total - start)
                break
            except self._driver.Error as fault:
                if _not_compiled(fault) or not self._held.is_healthy():
                    raise
                at = start + (getattr(fault.args[0], "offset", 0) or 0)
                refused.append((at, said(fault)))
                start = at + 1
        return refused, [0] * total if counts else []

    def call(
        self, block: str, rows: List[Tuple[Any, ...]], outs: Mapping[int, str], ins: Optional[Mapping[int, str]] = None
    ) -> Dict[int, List[Any]]:
        import decimal

        driver, ins = self._driver, ins or {}
        # A number comes out as every digit it has: left to itself the driver makes it a float.
        kinds = {"number": decimal.Decimal, "text": _TEXT_OUT, "date": driver.DB_TYPE_DATE,
                 "datetime": driver.DB_TYPE_TIMESTAMP, "large text": driver.DB_TYPE_CLOB}
        width = len(rows[0]) if rows else 0
        with self._held.cursor() as cursor:
            try:
                if width:
                    # A value that only goes in is said to be what it is where it would be taken for another: by
                    # itself a moment is bound as a DATE, and loses its fraction of a second.
                    cursor.setinputsizes(*[kinds[outs[place]] if place in outs else kinds.get(ins.get(place))
                                           for place in range(width)])
                    cursor.executemany(block, rows)
                else:
                    cursor.executemany(block, len(rows))
                return {place: [cursor.bindvars[place].getvalue(at) for at in range(len(rows))] for place in outs}
            except driver.Error as fault:
                if _not_compiled(fault) or not self._held.is_healthy():
                    # The call itself is at fault, or the session is closed: no one row of it is.
                    raise DatabaseError(said(fault)) from None
                raise CallFailed(getattr(fault.args[0], "offset", 0) or 0, said(fault)) from None

    def is_missing(self, fault: DatabaseError) -> bool:
        return str(fault).startswith("ORA-00942")

    def is_there_already(self, fault: DatabaseError) -> bool:
        return str(fault).startswith("ORA-00955")

    def commit(self) -> None:
        with self._asked():
            self._held.commit()

    def rollback(self) -> None:
        with self._asked():
            self._held.rollback()

    def savepoint(self, name: str) -> None:
        self.run(f"savepoint {name}")

    def rollback_to(self, name: str) -> None:
        self.run(f"rollback to savepoint {name}")

    def in_transaction(self) -> bool:
        try:
            return bool(self._held.transaction_in_progress)
        except self._driver.Error:
            # Oracle's own client cannot say it of a session the database has closed (DPY-1001), where the thin
            # driver still says what it knew. What waited on such a session is taken to have waited still: it is
            # told as lost, and never dropped without a word.
            return True

    def alive(self) -> bool:
        return bool(self._held.is_healthy())

    def close(self) -> None:
        with self._asked():
            self._held.close()

    @contextmanager
    def _asked(self) -> Iterator[None]:
        """What the driver refuses while this is open is said in its words, as the engine's own error."""
        try:
            yield
        except self._driver.Error as fault:
            raise DatabaseError(said(fault)) from None


# ------------------------------------------------------------------
# Internals
# ------------------------------------------------------------------

def _driver(settings: Mapping[str, Any]) -> Any:
    """python-oracledb, new enough to be trusted with rows, and with Oracle's own client loaded when asked for."""
    try:
        import oracledb
    except ImportError:
        raise DatabaseError(
            "python-oracledb is not installed, and an Oracle component needs it: pip install 'dataprep[v2-oracle]'"
        ) from None
    version = oracledb.__version__
    if tuple(int(part) for part in re.findall(r"\d+", version)[:3]) < _OLDEST:
        raise DatabaseError(f"python-oracledb {version} is installed, and 26.0.1 or later is needed: earlier ones "
                            "hand on wrong numbers and lose dates")
    if settings.get("thick_mode"):
        where = {"lib_dir": settings["lib_dir"]} if settings.get("lib_dir") else {}
        try:
            oracledb.init_oracle_client(**where)
        except oracledb.Error as fault:
            raise DatabaseError("Oracle's own client, which `oracle_config.thick_mode` asks for, could not be "
                                f"loaded: {said(fault)}") from None
    return oracledb


def _code(fault: Any) -> str:
    """The number of what the driver or the database said: `ORA-06550`, `DPY-2040`."""
    return getattr(fault.args[0] if fault.args else None, "full_code", "") or ""


def _not_compiled(fault: Any) -> bool:
    return _code(fault) in _NOT_COMPILED and "ORA-06512" not in str(fault)


def _said(type_name: str) -> str:
    """The driver's name of a type as a message says it: `DB_TYPE_TIMESTAMP_TZ` is a `TIMESTAMP_TZ`."""
    return type_name.removeprefix("DB_TYPE_")


def _address(url: str) -> Tuple[str, str]:
    """A connect string without what makes it a JDBC URL: what stands before its ``@``, and what after."""
    text = _JDBC.sub("", url, count=1).strip()
    before, at, after = text.partition("@")
    return (before, after.strip()) if at else ("", text)


def _place(given: Mapping[str, Any]) -> str:
    """Where a session is opened, as a log line says it."""
    if "dsn" in given:
        return given["dsn"] if len(given["dsn"]) <= _SHOWN else given["dsn"][:_SHOWN] + "..."
    if "sid" in given:
        return f"{given['host']}:{given['port']}:{given['sid']}"
    return f"{given['host']}:{given['port']}/{given['service_name']}"
