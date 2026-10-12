"""SQL Server: what of a job config a session is opened with, and a session over Microsoft's mssql-python.

The driver is imported when the first session is opened, so that a job
with no SQL Server component needs none.

A query is run as it is written, and once. SQL Server takes no query
inside another the way Oracle does (no ``ORDER BY``, no ``WITH`` and no
call of a procedure can stand in one), so nothing is wrapped round it:
the driver hands each column out in the type the database has it in, and
the session makes of that what the job declares, the way SQL Server's own
``CAST`` would.

What the driver was seen to do against a real database, and what it gets
wrong, is in
``.scratch/engine-v2/issues/126-sql-server-connection-and-input.md``.
"""
from __future__ import annotations

import decimal
import importlib
import logging
import re
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterator, List, Mapping, Optional, Tuple

from .column_types import DEFAULT_DECIMAL_SCALE, to_text
from .errors import ConfigurationError, DatabaseError
from .job.keys import Key, Kind
from .sessions import (  # noqa: F401
    DATE, NUMBER, OTHER, TEXT, WORKING_KEYS, Field, Session, filled, in_ascii, listed, password_problems,
)

if TYPE_CHECKING:
    from .components.base import Component
    from .job.model import Column
    from .statements import Statement

logger = logging.getLogger(__name__)

# The oldest driver v2 was tried with.
_OLDEST = (1, 15, 0)
_BLANKS = re.compile(r"[ \t\r\n\f\v]+")
# Who passed a message on, as the driver writes it before the message: [Microsoft][SQL Server].
_PASSED_ON = re.compile(r"^(?:\[[^\]]*\])+")
# How what the driver says begins when it has lost the reason of a failure.
_LOST = ("Unknown DDBC error", "An error occurred with SQLSTATE code")
# The numbers the driver gives for what the network did, in words. They are Windows' own, on every system.
_NETWORK = {"0x2AF9": "no such host is known", "0x274D": "the connection was refused",
            "0x274C": "nothing answered in time", "0x2746": "the other side ended the connection"}
_NETWORK_CODE = re.compile(r"Error code 0x([0-9A-Fa-f]+)$")
_UNTRUSTED = (". The server's certificate is not one this machine trusts: have it signed by an authority this machine "
              "knows, or turn `trust_server_certificate` on, and what is sent is still encrypted but the server is "
              "not checked")


def _port(value: Any) -> Optional[int]:
    text = str(value).strip() if isinstance(value, (str, int)) else "?"
    if text == "":
        # Left to the driver: 1433, or the port of an instance the host names.
        return None
    if not text.isdigit() or not 1 <= int(text) <= 65535:
        raise ValueError(f"{value!r} is no port: give a whole number from 1 to 65535")
    return int(text)


def _said(value: Any) -> str:
    return str(value).strip().lower() if isinstance(value, (str, bool)) else "?"


def _encryption(value: Any) -> str:
    made = {"yes": "yes", "true": "yes", "mandatory": "yes", "no": "no", "false": "no", "optional": "no",
            "strict": "strict"}.get(_said(value))
    if made is None:
        raise ValueError(f"{value!r} is none of yes, no, strict")
    return made


def _switch(value: Any) -> bool:
    said_so = _said(value)
    if said_so not in ("true", "yes", "false", "no"):
        raise ValueError(f"{value!r} is neither true nor false")
    return said_so in ("true", "yes")


# The connection block: what a converted job carries on every component that can open a session.
CONNECTION_KEYS: Tuple[Key, ...] = (
    Key("host", default="",
        doc="The database server. An instance of its own is named after a backslash (`server\\instance`)."),
    Key("port", type=object, default=1433, convert=_port,
        doc="Its port. Left empty, the port is the driver's to find: 1433, or the one of an instance `host` names."),
    Key("dbname", default="", doc="The database. Left empty, it is the one the user has by default."),
    Key("schema_db", default="", doc="The schema Talend names beside the database. A query says itself where its "
                                     "tables are."),
    Key("user", default="", doc="The user: a login of SQL Server's own."),
    Key("password", default="", secret=True, doc="The password. It is shown in no log and kept nowhere."),
    Key("encrypt", type=object, default=None, convert=_encryption,
        doc="Whether what is sent is encrypted: `yes` (what it is when nothing says otherwise), `no`, or `strict`."),
    Key("trust_server_certificate", type=object, default=None, convert=_switch,
        doc="Whether the server's certificate is taken unchecked. It is checked when nothing says otherwise."),
    Key("properties", default="",
        doc="Talend's JDBC parameters (`name=value;name=value`). Read are `encrypt`, `trustServerCertificate`, "
            "`hostNameInCertificate`, `applicationIntent`, `multiSubnetFailover` and `loginTimeout`; the ones that "
            "say how a JDBC driver works are passed over; any other refuses the job."),
    Key("active_dir_auth", kind=Kind.REFUSED, type=object,
        reason="v2 signs in to SQL Server with a user and a password of the database's own; signing in through "
               "Microsoft Entra was not at hand to be tried, and is not built"),
    Key("use_shared_connection", kind=Kind.REFUSED, type=object,
        reason="a session is not shared between a job and the jobs it runs: each opens its own"),
    Key("driver", kind=Kind.IGNORED, type=object, doc="Which JDBC driver Talend loads."),
    Key("encoding", kind=Kind.IGNORED, type=object, doc="The driver speaks to the database in Unicode."),
    Key("shared_connection_name", kind=Kind.IGNORED, type=object, doc="See `use_shared_connection`."),
    Key("specify_datasource_alias", kind=Kind.IGNORED, type=object, doc="For Talend's own runtime."),
    Key("datasource_alias", kind=Kind.IGNORED, type=object, doc="For Talend's own runtime."),
)


def _held(what: str, read: Callable[[str], Any]) -> Callable[[str], Any]:
    """A reader of a parameter's value that says of a value it cannot read only `what`, and never the value."""
    def reading(value: str) -> Any:
        try:
            return read(value)
        except ValueError:
            raise ValueError(what) from None
    return reading


def _text(value: str) -> str:
    if not value:
        raise ValueError
    return value


def _seconds(value: str) -> int:
    if not value.isdigit():
        raise ValueError
    return int(value)


# Talend's JDBC parameters that mean something here, by their names in lower case: what the driver is given for
# each, and how its value is read.
_READ: Dict[str, Tuple[str, Callable[[str], Any]]] = {
    "encrypt": ("encrypt", _held("what is none of yes, no, strict", _encryption)),
    "trustservercertificate": ("trust_server_certificate", _held("what is neither true nor false", _switch)),
    "hostnameincertificate": ("hostnameincertificate", _held("nothing", _text)),
    "applicationintent": ("applicationintent", _held("nothing", _text)),
    "multisubnetfailover": ("multisubnetfailover", _held("what is neither true nor false", _switch)),
    "logintimeout": ("timeout", _held("no whole number of seconds", _seconds)),
}
_READ_NAMES = "encrypt, trustServerCertificate, hostNameInCertificate, applicationIntent, multiSubnetFailover and loginTimeout"
# The ones that say how a JDBC driver works inside, or what a session is called: nothing here answers to them.
# `noDatetimeStringSync` is what Talend's own input carries when nothing was said, and is MySQL's.
_PASSED_OVER = frozenset((
    "nodatetimestringsync", "sendstringparametersasunicode", "selectmethod", "responsebuffering", "applicationname",
    "appname",
))

# What to write in a query for a column of a kind that is not read.
ADVICE = {OTHER: "turn it into text, a number or a date in the query"}
_ZONED = ("the driver hands it on without its zone. Write in the query what is wanted: "
          "`convert(varchar(34), <column>, 121)` for its text with the zone, "
          "`cast(<column> at time zone 'UTC' as datetime2)` for its clock in UTC, or `cast(<column> as datetime2)` "
          "for the clock of its own zone")
_BINARY = "write it as text in the query, `convert(varchar(max), <column>, 2)` for its hexadecimal digits"
# How SQL Server names the whole numbers the driver hands out.
_WHOLE = {"int64": "BIGINT", "int32": "INT", "int16": "SMALLINT", "uint8": "TINYINT"}


def session_of(component: "Component") -> Tuple[Session, bool]:
    """The session a component reads on: its connection's, or one it opens with its own connection block.

    Returns:
        The session, and whether it is the component's own to close.
    """
    config, run = component.config, component.run_context
    if config["use_existing_connection"]:
        session, own = run.sessions.shared(config["connection"]), False
    else:
        session, own = opened(config, component.id), True
    session.asking = component.id
    return session, own


def working_problems(config: Mapping[str, Any]) -> List[str]:
    """What is wrong with the connection block of a component that works in the database: nothing, when it works
    on the session of a connection component and its own block is not read."""
    return [] if config["use_existing_connection"] else problems(config)


def problems(config: Mapping[str, Any]) -> List[str]:
    """What is wrong with a connection block that a session is to be opened with. Nothing here shows a secret."""
    found: List[str] = []
    if not filled(config["host"]):
        found.append("host: is empty; a session is opened with a host")
    elif "," in config["host"]:
        found.append("host: holds a comma; give the port in `port`")
    if not filled(config["user"]):
        found.append("user: is empty; v2 signs in to SQL Server with a user and a password")
    return found + password_problems(config["password"]) + _parameters(config)[1]


def arguments(config: Mapping[str, Any]) -> Dict[str, Any]:
    """What the driver is given to open a session with a connection block. The password is one of them, by itself:
    the driver writes its own connection string, and no text is made of the password here."""
    said_so = _parameters(config)[0]
    # A key of v2's own goes before what Talend's parameters say.
    for key in ("encrypt", "trust_server_certificate"):
        if config[key] is not None:
            said_so[key] = config[key]
    host, port, database = config["host"].strip(), config["port"], config["dbname"].strip()
    made: Dict[str, Any] = {"server": host if port is None else f"{host},{port}"}
    if database:
        made["database"] = database
    made.update(uid=config["user"], pwd=config["password"], encrypt=said_so.pop("encrypt", "yes"),
                trust_server_certificate=said_so.pop("trust_server_certificate", False))
    made.update(said_so)
    return {keyword: ("yes" if value else "no") if isinstance(value, bool) else value for keyword, value in made.items()}


def opened(config: Mapping[str, Any], opened_by: str, **more: Any) -> "MssqlSession":
    """Open a session with a connection block.

    Every statement on it is stored by itself: v2 has no SQL Server
    component that changes anything, and none that commits.

    Args:
        config: The block, checked against ``CONNECTION_KEYS`` and with
            nothing ``problems`` finds.
        opened_by: The id of the component that opens it.
        **more: What else the session is to hold (``Session``).

    Raises:
        DatabaseError: When no session could be opened. It says where and
            as whom, and never the password.
    """
    driver = _driver()
    made = arguments(config)
    what = f"{config['user']}@{made['server']}" + (f"/{made['database']}" if "database" in made else "")
    try:
        held = driver.connect("", autocommit=True, **made)
    except driver.Error as fault:
        raise DatabaseError(f"no session was opened as {what}: {_why_not(fault)}") from None
    logger.info(in_ascii(f"[{opened_by}] session opened: {what}"))
    return MssqlSession(held, driver, opened_by, what, schema=config["schema_db"], **more)


def said(fault: Any) -> str:
    """What the database said of a failure, or else the driver, on one line of plain ASCII; nothing, when the
    driver has lost the reason."""
    words = [str(fault)]
    if hasattr(fault, "ddbc_error") or hasattr(fault, "driver_error"):
        words = [_PASSED_ON.sub("", str(getattr(fault, "ddbc_error", "") or "")),
                 str(getattr(fault, "driver_error", "") or "")]
    for text in words:
        text = _BLANKS.sub(" ", text).strip()
        if text and not text.startswith(_LOST):
            return in_ascii(text)
    return ""


@dataclass
class _Waiting:
    """What a statement that was run hands back, while nobody has taken its rows.

    Attributes:
        statement: The statement, and ``binds`` the values it was run with.
        cursor: The driver's cursor, at the first of its rows.
        digits: For each column, the digits after the second its type has.
    """

    statement: str
    binds: List[Any]
    cursor: Any
    digits: List[int]


class MssqlSession(Session):
    """A session with a SQL Server database, over mssql-python.

    It reads. A statement is run once, when its columns are asked for,
    and its rows wait at the server until they are taken: the connection
    takes one statement at a time, so a result nobody took is let go when
    the next statement is run.

    Attributes:
        limit: The seconds a query is given before its first rows come;
            none when 0. A component says it before it reads.
        asking: The id of the component that reads on the session now:
            what the session has to say is said under it.
    """

    advice = ADVICE

    def __init__(self, held: Any, driver: Any, opened_by: str, what: str, **more: Any) -> None:
        super().__init__(opened_by, what, **more)
        self._held = held
        self._driver = driver
        self._waiting: Optional[_Waiting] = None
        self.limit = 0
        self.asking = opened_by

    def bound(self, statement: "Statement") -> Tuple[str, Any]:
        return statement.placed()

    def fields(self, statement: str, binds: Any = None) -> List[Field]:
        """What a query hands back, column by column. The query is run for it, and its rows wait for ``batches``."""
        waiting = self._run(statement, binds)
        try:
            with self._asked():
                schema = waiting.cursor.arrow_batch(0).schema
        except RuntimeError as fault:
            # A type the driver's own path to Arrow does not know. It is no error of the driver's own kind.
            self._let_go()
            raise ConfigurationError(
                f"the driver cannot hand on a column of the query ({said(fault)}): {ADVICE[OTHER]}; a sql_variant "
                "is cast to the type it holds") from None
        except DatabaseError:
            self._let_go()
            raise
        waiting.digits = [described[5] or 0 for described in waiting.cursor.description]
        return [_field(one.name, one.type) for one in schema]

    def typed(self, statement: str, columns: List["Column"], fields: List[Field]) -> Tuple[str, List[Any]]:
        """The query as it is written, and the Arrow type each column is handed on in: what the job declares."""
        import pyarrow

        kinds: List[Any] = []
        for column, field in zip(columns, fields):
            kind = pyarrow.large_string()
            if field.family == NUMBER:
                places = DEFAULT_DECIMAL_SCALE if column.precision is None else column.precision
                kind = {"int": pyarrow.int64(), "float": pyarrow.float64(), "bool": pyarrow.int8(),
                        "Decimal": pyarrow.decimal128(38, places)}.get(column.type, kind)
            elif field.family == DATE:
                kind = {"datetime": pyarrow.timestamp("us"), "date": pyarrow.date32()}.get(column.type, kind)
            kinds.append(kind)
        return statement, kinds

    def batches(self, statement: str, binds: Any, types: List[Any], size: int) -> Iterator[Any]:
        waiting = self._waiting
        if waiting is None or (waiting.statement, waiting.binds) != (statement, list(binds or [])):
            self.fields(statement, binds)
            waiting = self._waiting
        cursor, read, more = waiting.cursor, 0, 0
        try:
            while True:
                batch = cursor.arrow_batch(size)
                if not batch.num_rows:
                    break
                yield as_asked(batch, types, waiting.digits, read)
                read += batch.num_rows
            # What the statement does after its rows is drawn to its end: a failure there is the statement's, and
            # is seen no other way.
            while cursor.nextset():
                more += cursor.description is not None
        except self._driver.Error as fault:
            why = self._why(fault, "")
            raise DatabaseError(
                f"the query failed after {read} row(s) were read: {why}" if why else
                f"the database ended the query after {read} row(s) were read, and the driver hands on no reason "
                "for it: run the query in another client to see what it was") from None
        finally:
            self._let_go()
        if more:
            passed = "other is" if more == 1 else "others are"
            logger.info(f"[{self.asking}] the query handed back {more + 1} results: the first is read and the "
                        f"{passed} passed over")

    def close(self) -> None:
        self._let_go()
        held, self._held = self._held, None
        if held is not None:
            with self._asked():
                held.close()

    # ------------------------------------------------------------------

    def _run(self, statement: str, binds: Any) -> _Waiting:
        """Run a statement and go to the first thing it hands back that has columns.

        A procedure that changes something hands back a count of rows
        first, and a ``PRINT`` a result with nothing in it.
        """
        self._let_go()
        self._held.timeout = self.limit
        cursor = self._held.cursor()
        self._waiting = _Waiting(statement, list(binds or []), cursor, [])
        try:
            if binds:
                cursor.execute(statement, list(binds))
            else:
                cursor.execute(statement)
            while cursor.description is None:
                if not cursor.nextset():
                    raise ConfigurationError(
                        "the statement was run and handed back no rows to read: an input reads the rows of a query")
        except BaseException as fault:
            self._let_go()
            if isinstance(fault, self._driver.Error):
                raise DatabaseError(self._why(fault)) from None
            if isinstance(fault, TypeError):
                # The driver reads %(name)s in a statement as a mark of its own, and refuses one before it runs it.
                raise DatabaseError(f"the driver did not take the statement: {said(fault)}") from None
            raise
        return self._waiting

    def _let_go(self) -> None:
        """Let go of a result that waits. Whatever the driver says to that, the result is gone with its statement."""
        waiting, self._waiting = self._waiting, None
        if waiting is not None:
            try:
                waiting.cursor.close()
            except self._driver.Error:
                pass

    def _why(self, fault: Any, unsaid: str = "the driver gave no reason") -> str:
        """What a failure of the driver's says; `unsaid`, when it says nothing."""
        why = said(fault) or unsaid
        if self.limit and "timeout expired" in why.lower():
            why += f": the query was given {self.limit} second(s) (`query_timeout_in_seconds`)"
        return why

    @contextmanager
    def _asked(self) -> Iterator[None]:
        """What the driver refuses while this is open is said in its words, as the engine's own error."""
        try:
            yield
        except self._driver.Error as fault:
            raise DatabaseError(self._why(fault)) from None


def as_asked(batch: Any, asked: List[Any], digits: List[int], before: int = 0) -> Any:
    """Rows as the driver hands them out, made what the job declares.

    Each value is converted as SQL Server's own ``CAST`` converts it: a
    whole number is cut off at its point, a Decimal is rounded to its
    places with a half going away from nought, and a float goes by the
    number it exactly is. Columns are taken by their place.

    Args:
        batch: The rows, in the Arrow types the driver hands out.
        asked: The Arrow type each column is to have.
        digits: For each column, the digits after the second its type
            has, which a moment or a time of day is written with as text.
        before: How many rows of the result came before these.

    Returns:
        An Arrow table of the types asked for, its columns named by
        their place (`C1`...).

    Raises:
        DatabaseError: A value does not fit what its column declares. It
            names the row, the column and the value.
    """
    import pyarrow

    made = []
    for place, (kind, places) in enumerate(zip(asked, digits)):
        values = batch.column(place)
        try:
            made.append(_made(values, kind, places))
        except pyarrow.ArrowInvalid as fault:
            raise DatabaseError(_unfit(values, kind, before, place, fault)) from None
    return pyarrow.Table.from_arrays(made, names=[f"C{place}" for place in range(1, len(made) + 1)])


# ------------------------------------------------------------------
# Internals
# ------------------------------------------------------------------

def _driver() -> Any:
    """mssql-python, new enough to have been tried, and with its keeping of closed sessions turned off."""
    try:
        driver = importlib.import_module("mssql_python")
    except (ImportError, OSError) as fault:
        if isinstance(fault, ImportError) and fault.name == "mssql_python":
            raise DatabaseError("mssql-python is not installed, and a SQL Server component needs it: "
                                "pip install 'dataprep[v2-mssql]'") from None
        # It is there, and a library of the system's that it loads is not (on RHEL: libtool-ltdl, krb5-libs).
        raise DatabaseError(f"mssql-python is installed and could not be loaded: {said(fault)}") from None
    version = driver.__version__
    if tuple(int(part) for part in re.findall(r"\d+", version)[:3]) < _OLDEST:
        raise DatabaseError(f"mssql-python {version} is installed, and 1.15.0 or later is needed: v2 was tried with "
                            "no earlier one")
    if not driver.PoolingManager.is_initialized():
        # Left to itself the driver keeps a session it was told to close, for whoever opens the next: a job's
        # session would outlive the job's word that it is closed. A process that has said itself how sessions
        # are kept is left with what it said.
        driver.pooling(enabled=False)
    return driver


def _why_not(fault: Any) -> str:
    """Why no session was opened, with what the driver leaves a reader to look up."""
    why = said(fault) or "the driver gave no reason"
    code = _NETWORK_CODE.search(why)
    if code and f"0x{code.group(1).upper()}" in _NETWORK:
        why += f" ({_NETWORK['0x' + code.group(1).upper()]})"
    if "certificate verify failed" in why:
        why += _UNTRUSTED
    return why


def _parameters(config: Mapping[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """What Talend's JDBC parameters say, under what the driver is given for each; and what is wrong with them."""
    said_so: Dict[str, Any] = {}
    unknown: List[str] = []
    wrong: List[str] = []
    for part in str(config["properties"] or "").split(";"):
        name, equals, value = part.partition("=")
        name = name.strip()
        if not part.strip():
            continue
        if not equals or not name:
            wrong.append("properties: holds a part that is no `name=value`")
        elif name.lower() in _READ:
            keyword, read = _READ[name.lower()]
            try:
                said_so[keyword] = read(value.strip())
            except ValueError as fault:
                wrong.append(f"properties: `{name}` holds {fault}")
        elif name.lower() not in _PASSED_OVER:
            unknown.append(name)
    if unknown:
        are, them = ("is a parameter", "it") if len(unknown) == 1 else ("are parameters", "them")
        wrong.insert(0, f"properties: {listed(unknown)} {are} of a JDBC driver that v2 has no reading for; take "
                        f"{them} out. It reads {_READ_NAMES}")
    return said_so, wrong


def _field(name: str, kind: Any) -> Field:
    """A column of a result, by the Arrow type the driver hands it out in."""
    import pyarrow

    types = pyarrow.types
    if types.is_boolean(kind):
        return Field(name, NUMBER, "BIT")
    if types.is_integer(kind):
        return Field(name, NUMBER, _WHOLE.get(str(kind), str(kind).upper()))
    if types.is_decimal(kind):
        return Field(name, NUMBER, f"DECIMAL({kind.precision},{kind.scale})")
    if types.is_floating(kind):
        return Field(name, NUMBER, "REAL" if types.is_float32(kind) else "FLOAT")
    if types.is_date(kind):
        return Field(name, DATE, "DATE")
    if types.is_timestamp(kind):
        if kind.tz is None:
            return Field(name, DATE, "DATETIME")
        return Field(name, OTHER, "a date with a time zone (DATETIMEOFFSET)", _ZONED)
    if types.is_string(kind) or types.is_large_string(kind):
        return Field(name, TEXT, "text")
    if types.is_time(kind):
        # A time of day is no type a job declares: it is read as its text.
        return Field(name, TEXT, "TIME")
    if types.is_binary(kind) or types.is_large_binary(kind):
        return Field(name, OTHER, "binary data", _BINARY)
    return Field(name, OTHER, str(kind))


def _made(values: Any, to: Any, digits: int) -> Any:
    """One column as the type it is asked for in."""
    import polars as pl
    import pyarrow
    import pyarrow.compute as compute

    types, had = pyarrow.types, values.type
    if types.is_large_string(to):
        return _as_text(values, digits)
    if types.is_int64(to):
        # Cut off at the point, as everywhere a whole-number column is filled. One too large fails the cast.
        if types.is_decimal(had):
            values = compute.round(values, 0, round_mode="towards_zero")
        elif types.is_floating(had):
            values = compute.trunc(values)
        return compute.cast(values, to)
    if types.is_float64(to):
        if types.is_decimal(had):
            # Through its digits: a cast can be one step away from the nearest float.
            return pl.from_arrow(values).cast(pl.String).cast(pl.Float64).to_arrow()
        # The nearest float there is, for a whole number of more digits than a float holds.
        return compute.cast(values, to, safe=False)
    if types.is_decimal(to):
        if types.is_floating(had):
            return _from_float(values, to)
        if not types.is_decimal(had):
            # By way of a whole number of 19 digits: asked for straight away, Arrow counts the digits a number of
            # that kind could have, and not the ones the value has.
            values = compute.cast(compute.cast(values, pyarrow.int64()), pyarrow.decimal128(19, 0))
        elif had.scale > to.scale:
            values = compute.round(values, to.scale, round_mode="half_towards_infinity")
        return compute.cast(values, to)
    if types.is_int8(to) and not types.is_boolean(had):
        # A true/false as nought or one: anything but nought is one.
        values = compute.not_equal(values, 0)
    # What is left is a cast that loses nothing: a day of a moment, a moment of a day, a nought or one.
    return compute.cast(values, to)


def _from_float(values: Any, to: Any) -> Any:
    """Floats as Decimals: each the number it exactly is, rounded to the places, a half going away from nought.

    Arrow makes the exact number and rounds a half to the even digit. A
    float lies exactly halfway at some places when, times two to the
    power of those places and one more, it is a whole odd number; float
    arithmetic says that exactly. Those are rounded again, from all their
    digits.
    """
    import pyarrow
    import pyarrow.compute as compute

    made = compute.cast(values, to)
    doubled = compute.multiply(values, 2.0 ** (to.scale + 1))
    left = compute.subtract(doubled, compute.multiply(compute.floor(compute.divide(doubled, 2.0)), 2.0))
    halfway = compute.fill_null(compute.and_(compute.equal(doubled, compute.floor(doubled)), compute.equal(left, 1.0)),
                                False)
    if not compute.any(halfway).as_py():
        return made
    exact = compute.cast(compute.filter(values, halfway), pyarrow.decimal256(76, to.scale + 1))
    away = compute.round(exact, to.scale, round_mode="half_towards_infinity")
    return compute.replace_with_mask(made, halfway, compute.cast(away, to))


def _as_text(values: Any, digits: int) -> Any:
    """One column as text: a number as the database holds it, a float as v2 writes one, a moment or a time of day
    with the digits after the second that its type has."""
    import polars as pl
    import pyarrow
    import pyarrow.compute as compute

    types, had, text = pyarrow.types, values.type, pyarrow.large_string()
    if types.is_boolean(had):
        return compute.cast(compute.if_else(values, "1", "0"), text)
    if types.is_string(had) or types.is_large_string(had) or types.is_integer(had):
        return compute.cast(values, text)
    held = pl.from_arrow(values)
    if types.is_floating(had):
        made = pl.DataFrame({"v": held}).select(to_text(pl.col("v"), held.dtype)).to_series()
    elif types.is_decimal(had):
        made = held.cast(pl.String)
    elif types.is_date(had):
        made = held.dt.strftime("%Y-%m-%d")
    elif types.is_time(had):
        made = held.dt.to_string("%H:%M:%S%.9f").str.slice(0, 9 + digits if digits else 8)
    else:
        # A millionth of a second is all the driver hands on of the seven digits a datetime2 may have.
        made = held.dt.strftime("%Y-%m-%d %H:%M:%S%.6f").str.slice(0, 20 + min(digits, 6) if digits else 19)
    return compute.cast(made.to_arrow(), text)


def _unfit(values: Any, to: Any, before: int, place: int, fault: Any) -> str:
    """What to say of a column that could not be made what it is asked for: its first value that does not fit."""
    import pyarrow

    whole = pyarrow.types.is_int64(to)
    exact = decimal.Context(prec=400, rounding=decimal.ROUND_HALF_UP)
    for at, value in enumerate(values.to_pylist()):
        if value is None:
            continue
        number = decimal.Decimal(value)
        if whole:
            fits = -(2 ** 63) <= int(number) < 2 ** 63
        else:
            fits = abs(number.quantize(decimal.Decimal(1).scaleb(-to.scale), context=exact)) < 10 ** (38 - to.scale)
        if not fits:
            what = "a whole number of 64 bits" if whole else f"a Decimal of {to.scale} places (it has 38 digits in all)"
            return f"row {before + at + 1} of the result: column {place + 1} holds {value}, which does not fit {what}"
    return f"column {place + 1} of the result could not be made what the job declares: {said(fault)}"
