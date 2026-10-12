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
from typing import Any, Dict, Iterator, List, Mapping, Optional, Tuple

from .errors import DatabaseError
from .job.keys import Key, Kind
from .sessions import Session

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


def said(fault: BaseException) -> str:
    """What the driver said, on one line of plain ASCII, without the link to Oracle's help that follows it."""
    text = _BLANKS.sub(" ", str(fault).split("\nHelp:")[0]).strip()
    return _ascii(text) or type(fault).__name__


class OracleSession(Session):
    """A session with an Oracle database, over python-oracledb."""

    def __init__(self, held: Any, driver: Any, opened_by: str, what: str, **more: Any) -> None:
        super().__init__(opened_by, what, **more)
        self._held = held
        self._driver = driver

    def run(self, statement: str, binds: Optional[Mapping[str, Any]] = None) -> int:
        with self._asked(), self._held.cursor() as cursor:
            cursor.execute(statement, dict(binds or {}))
            return cursor.rowcount

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
