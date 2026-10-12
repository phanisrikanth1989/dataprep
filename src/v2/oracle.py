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

from .column_types import DEFAULT_DECIMAL_SCALE
from .errors import DatabaseError
from .job.keys import Key, Kind
from .sessions import DATE, NUMBER, OTHER, TEXT, ZONED, CallFailed, Field, Session

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
# How Talend writes a password it has encrypted with a key of its own.
_ENCRYPTED = "enc:system.encryption.key.v1:"
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


# Beside the connection block, on every component that works in the database: whose session it works on.
WORKING_KEYS: Tuple[Key, ...] = (
    Key("use_existing_connection", type=bool, default=False,
        doc="Whether it works on the session of the connection component `connection` names. Without it, it "
            "opens a session of its own with its connection block."),
    Key("connection", default="", doc="The id of that connection component. It has to be one of the job."),
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
                  if not _given(config[key])]
    else:
        key = "rac_url" if kind == CUSTOM else "local_service_name"
        if not _given(config[key]):
            found.append(f"{key}: is empty; `connection_type` {kind} opens a session with it")
        elif kind == CUSTOM and _address(config[key])[0]:
            found.append("rac_url: carries a user and a password; give them in `user` and `password`, and the URL "
                         "from the `@` on")
    if not _given(config["user"]):
        found.append("user: is empty")
    if isinstance(config["password"], str) and config["password"].startswith(_ENCRYPTED):
        found.append("password: is text Talend encrypted with a key of its own, which v2 cannot read; give the "
                     "password itself, from a context variable (`${context.db_password}`)")
    named = [part.split("=", 1)[0].strip() for part in str(config["properties"] or "").split("&&") if part.strip()]
    if named:
        are = "is a parameter" if len(named) == 1 else "are parameters"
        it = "it" if len(named) == 1 else "them"
        found.append(f"properties: {_listed(named)} {are} of Oracle's JDBC driver, which v2 does not use; take {it} out")
    return found


def arguments(config: Mapping[str, Any]) -> Dict[str, Any]:
    """What the driver is given to open a session with a connection block. The password is one of them, by itself."""
    kind = config["connection_type"]
    given: Dict[str, Any] = {"user": config["user"], "password": config["password"]}
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
        held = driver.connect(**given)
        held.module = MODULE
        held.action = job_name.encode("utf-8")[:_ACTION_BYTES].decode("utf-8", "ignore")
    except driver.Error as fault:
        raise DatabaseError(f"no session was opened as {what}: {said(fault)}") from None
    client = "" if held.thin else ", with Oracle's own client"
    logger.info(_ascii(f"[{opened_by}] session opened: {what} (Oracle {held.version}{client})"))
    return OracleSession(held, driver, opened_by, what, schema=config["schema_db"], **more)


def said(fault: Any) -> str:
    """What the driver said, on one line of plain ASCII, without the link to Oracle's help that follows it."""
    text = _BLANKS.sub(" ", str(fault).split("\nHelp:")[0]).strip()
    return _ascii(text) or type(fault).__name__


class OracleSession(Session):
    """A session with an Oracle database, over python-oracledb."""

    advice = ADVICE

    def __init__(self, held: Any, driver: Any, opened_by: str, what: str, **more: Any) -> None:
        super().__init__(opened_by, what, **more)
        self._held = held
        self._driver = driver

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
        with self._asked(), self._held.cursor() as cursor:
            cursor.executemany(statement, rows, batcherrors=True, arraydmlrowcounts=counts)
            refused = [(error.offset, said(error.message)) for error in cursor.getbatcherrors()]
            return sorted(refused), list(cursor.getarraydmlrowcounts()) if counts else []

    def call(self, block: str, rows: List[Tuple[Any, ...]], outs: Mapping[int, str]) -> Dict[int, List[Any]]:
        import decimal

        driver = self._driver
        # A number comes out as every digit it has: left to itself the driver makes it a float.
        kinds = {"number": decimal.Decimal, "text": _TEXT_OUT, "date": driver.DB_TYPE_DATE,
                 "datetime": driver.DB_TYPE_TIMESTAMP, "large text": driver.DB_TYPE_CLOB}
        width = len(rows[0]) if rows else 0
        with self._held.cursor() as cursor:
            try:
                if width:
                    cursor.setinputsizes(*[kinds[outs[place]] if place in outs else None for place in range(width)])
                    cursor.executemany(block, rows)
                else:
                    cursor.executemany(block, len(rows))
                return {place: [cursor.bindvars[place].getvalue(at) for at in range(len(rows))] for place in outs}
            except driver.Error as fault:
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
        return bool(self._held.transaction_in_progress)

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


def _given(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _listed(names: List[str]) -> str:
    quoted = [f"`{name}`" for name in names]
    return quoted[0] if len(quoted) == 1 else f"{', '.join(quoted[:-1])} and {quoted[-1]}"


def _ascii(text: str) -> str:
    return text.encode("ascii", "backslashreplace").decode("ascii")
