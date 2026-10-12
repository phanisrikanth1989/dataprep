"""Oracle output: rows stored in a table when the whole subjob has succeeded."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, List, Sequence, Tuple

import polars as pl

from ... import oracle
from ...errors import ConfigurationError, DatabaseError
from ...job.keys import Key, Kind
from ...rows import shown
from ...sessions import Session
from ..base import DIE_ON_ERROR, FAULTS, Sink, Write, one_line
from ..registry import REGISTRY

if TYPE_CHECKING:
    from ...job.model import Column

logger = logging.getLogger(__name__)

INSERT, UPDATE, DELETE = "INSERT", "UPDATE", "DELETE"
INSERT_OR_UPDATE, UPDATE_OR_INSERT = "INSERT_OR_UPDATE", "UPDATE_OR_INSERT"
_BY_KEY = (UPDATE, DELETE, INSERT_OR_UPDATE, UPDATE_OR_INSERT)
# What is done to the table before the rows go in. All but the first two are statements that define: Oracle
# stores what waits on the session before one, and none is taken back.
NONE, CLEAR = "NONE", "CLEAR"
_DEFINING = ("TRUNCATE", "TRUNCATE_REUSE_STORAGE", "CREATE", "CREATE_IF_NOT_EXISTS", "DROP_CREATE",
             "DROP_IF_EXISTS_AND_CREATE")
# A name Oracle takes without quotes.
_NAME = re.compile(r"[A-Za-z][\w$#]*")
# The place this component's work on a session is marked at: where it goes back to when the job is to go on.
_MARK = "v2_output"
# Where in a batch a row stands, while the batch is taken apart.
_AT = "__v2_at"


def _rows(value: Any) -> int:
    try:
        rows = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{value!r} is no number of rows") from None
    if rows < 1:
        raise ValueError(f"{rows} rows cannot be sent at a time; give 1 or more")
    return rows


def insert_statement(table: str, names: Sequence[str]) -> str:
    places = ", ".join(f":{at}" for at in range(1, len(names) + 1))
    return f"insert into {table} ({', '.join(names)}) values ({places})"


def update_statement(table: str, sets: Sequence[str], keys: Sequence[str], dates: Sequence[str] = ()) -> str:
    """An update of one row by its key: the values to set by place, then the key's."""
    changed = ", ".join(f"{name} = :{at}" for at, name in enumerate(sets, start=1))
    return f"update {table} set {changed} where {_found(keys, dates, len(sets) + 1)}"


def delete_statement(table: str, keys: Sequence[str], dates: Sequence[str] = ()) -> str:
    return f"delete from {table} where {_found(keys, dates, 1)}"


def _found(keys: Sequence[str], dates: Sequence[str], first: int) -> str:
    """The row a key names. A key the table holds as a DATE is compared as one: handed a value with a fraction of
    a second, Oracle would turn the column into such values row by row, and use no index."""
    return " and ".join(f"{name} = cast(:{at} as date)" if name in dates else f"{name} = :{at}"
                        for at, name in enumerate(keys, start=first))


def column_type(column: "Column") -> str:
    """The type a column gets in a table made from the job's schema, which says no more than this of it."""
    if column.type == "str":
        if column.length and column.length > 4000:
            return "CLOB"
        return f"VARCHAR2({column.length or 4000} CHAR)"
    if column.type == "int":
        return f"NUMBER({column.length or 19})"
    if column.type == "Decimal":
        if column.length:
            return f"NUMBER({column.length}, {column.precision or 0})"
        return "NUMBER" if column.precision is None else f"NUMBER(38, {column.precision})"
    return {"float": "BINARY_DOUBLE", "bool": "NUMBER(1)", "datetime": "TIMESTAMP(6)", "date": "DATE"}[column.type]


def create_statement(table: str, columns: Sequence["Column"]) -> str:
    made = [f"{column.name} {column_type(column)}{'' if column.nullable else ' not null'}" for column in columns]
    keys = [column.name for column in columns if column.key]
    if keys:
        made.append(f"primary key ({', '.join(keys)})")
    return f"create table {table} ({', '.join(made)})"


@dataclass
class _Counted:
    """What became of the rows: how many the table took by each way, and the rows the database refused."""

    inserted: int = 0
    updated: int = 0
    deleted: int = 0
    refused: int = 0
    first: str = ""


@REGISTRY.register
class OracleOutput(Sink):
    """Store rows in a table of an Oracle database.

    The rows rest in a scratch file while the subjob runs. When the whole
    subjob has succeeded they are sent to the table in batches, inside a
    transaction: nothing touches the table for a subjob that fails. On
    the session of a connection component (`use_existing_connection`)
    they then wait for a commit component; with a session of its own
    they are stored when the subjob is done, in one commit.

    `data_action` says what a row does: `INSERT`; `UPDATE` and `DELETE`,
    by the columns the schema marks as key; `UPDATE_OR_INSERT` and
    `INSERT_OR_UPDATE`, which update the row with that key and insert it
    when there is none, as a job that handled its rows one by one would,
    also where one key comes twice.

    `table_action` says what is done to the table first: nothing,
    `CLEAR` (every row deleted, in the same transaction: taken back with
    the rows when the subjob fails), or one of the actions that define:
    `TRUNCATE`, `TRUNCATE_REUSE_STORAGE`, `CREATE`, `CREATE_IF_NOT_EXISTS`,
    `DROP_CREATE`, `DROP_IF_EXISTS_AND_CREATE`. Those are run at the last
    moment, when the rows are known to be whole, and Oracle does not take
    them back. They are refused on a session with work that waits, which
    they would store.

    A value is bound as the kind it arrives as; the database turns it
    into the column's own, or refuses the row. A row the database
    refuses fails the job and names the row. With `die_on_error` off it
    is left out, the others are stored, and one warning says how many
    were refused and what was wrong with the first.

    It leaves `<id>_NB_LINE` (the rows it was handed), `_NB_LINE_INSERTED`,
    `_NB_LINE_UPDATED`, `_NB_LINE_DELETED` and `_NB_LINE_REJECTED` in
    globalMap.
    """

    names = ("oracle_output", "OracleOutput", "tOracleOutput")
    uses_session = "Oracle"
    keys = (
        Key("table", default="", doc="The table. With `schema_db`, or the schema of the connection, it is looked for there."),
        Key("table_action", default=NONE, choices=(NONE, CLEAR) + _DEFINING, doc="What is done to the table first."),
        Key("data_action", default=INSERT, choices=(INSERT,) + _BY_KEY, doc="What each row does."),
        DIE_ON_ERROR,
        Key("use_batch_size", type=bool, default=True, doc="Whether `batch_size` says how many rows a round trip takes."),
        Key("batch_size", type=object, default=10000, convert=_rows, doc="That many rows; without `use_batch_size`, 10,000."),
        Key("commit_every", kind=Kind.IGNORED, type=object,
            doc="Talend's rows between commits. There is one commit, when the subjob has succeeded."),
        Key("use_field_options", kind=Kind.REFUSED, type=object,
            reason="which columns are keys and which are written is said by the schema here (`key`); the table of "
                   "field options is not read"),
        Key("use_hint_options", kind=Kind.REFUSED, type=object, reason="hints for the statements are not read"),
        Key("enable_debug_mode", kind=Kind.IGNORED, type=object, doc="Talend's switch to show statements with their values; no value is shown."),
        Key("convert_column_table_to_uppercase", kind=Kind.IGNORED, type=object,
            doc="Names are written without quotes, and Oracle reads those in capitals."),
        Key("use_timestamp_for_date_type", kind=Kind.IGNORED, type=object,
            doc="A key that is a date is compared as the table's own column is, so that an index on it is used."),
        Key("trim_char", kind=Kind.IGNORED, type=object, doc="A CHAR key is compared as Oracle compares it."),
    ) + oracle.WORKING_KEYS + oracle.CONNECTION_KEYS

    def problems(self) -> List[str]:
        config, columns = self.config, self.input_schema
        found = oracle.working_problems(config)
        for key in ("table", "schema_db"):
            if config[key] and not _NAME.fullmatch(config[key].strip()):
                found.append(f"{key}: '{shown(config[key])}' is no name Oracle takes as it is: letters, digits, `_`, `$` "
                             "and `#`, a letter first")
        if not config["table"].strip():
            found.append("table: names no table")
        if not columns:
            found.append("schema: an output needs the columns it stores declared")
        found += [f"schema: '{shown(column.name)}' is no name Oracle takes as it is" for column in columns
                  if not _NAME.fullmatch(column.name)]
        keys = [column.name for column in columns if column.key]
        if columns and config["data_action"] in _BY_KEY:
            if not keys:
                found.append(f"data_action: {config['data_action']} finds a row by its key, and the schema marks no "
                             "column as `key`")
            elif config["data_action"] != DELETE and len(keys) == len(columns):
                found.append(f"data_action: {config['data_action']} has nothing to set: every column is a key")
        return found

    def write(self, frame: pl.LazyFrame) -> Write:
        names = [column.name for column in self.input_schema]
        have = frame.collect_schema().names()
        lacking = [name for name in names if name not in have]
        if lacking:
            raise ConfigurationError(f"the rows it is handed have no column {', '.join(lacking)}: they have "
                                     f"{', '.join(have)}")
        return Write(
            path=f"table {self._written_table()}", scratch=self.run_context.temp_path(".parquet"),
            sink=lambda path: frame.select(names).sink_parquet(path, compression="zstd", compression_level=1, lazy=True),
            ready=self._stored,
        )

    # ------------------------------------------------------------------
    # Storing, when the subjob's pass has succeeded
    # ------------------------------------------------------------------

    def _stored(self, scratch: str, rows: int) -> int:
        """Send the rows to the table. Returns how many of them the table took."""
        counted = _Counted()
        try:
            self._load(scratch, counted)
        except FAULTS as fault:
            self.fail_or_go_on(fault, " with nothing stored by it")
            counted = _Counted(refused=rows)
        held = self.global_map
        held[f"{self.id}_NB_LINE_INSERTED"] = counted.inserted
        held[f"{self.id}_NB_LINE_UPDATED"] = counted.updated
        held[f"{self.id}_NB_LINE_DELETED"] = counted.deleted
        held[f"{self.id}_NB_LINE_REJECTED"] = counted.refused
        if counted.first:
            told = (f"the database refused {counted.refused} of the {rows} rows it was handed, and they are left out; "
                    f"the first: {counted.first}")
            held[f"{self.id}_ERROR_MESSAGE"] = told
            logger.warning(one_line(f"[{self.id}] {told}"))
        return rows - counted.refused

    def _load(self, scratch: str, counted: _Counted) -> None:
        from pyarrow import parquet

        config, sessions = self.config, self.run_context.sessions
        session, own = oracle.session_of(self)
        if own:
            sessions.own(session)
        table = self._table(session)
        self._defined(session, table)
        sessions.working(session, self.id)
        # What this component does is marked by itself: with `die_on_error` off, a fault takes back its work and
        # no other's.
        session.savepoint(_MARK)
        try:
            if config["table_action"] == CLEAR:
                session.run(f"delete from {table}")
            names = [column.name for column in self.input_schema]
            keys = [column.name for column in self.input_schema if column.key]
            sets = [name for name in names if name not in keys]
            dates = self._date_keys(session, table, keys) if config["data_action"] in _BY_KEY else []
            size = config["batch_size"] if config["use_batch_size"] else 10000
            before = 0
            for batch in parquet.ParquetFile(scratch).iter_batches(batch_size=size):
                frame = pl.from_arrow(batch).with_row_index(_AT)
                self._batch(session, table, frame, names, sets, keys, dates, counted, before)
                before += frame.height
        except FAULTS:
            if session.alive():
                session.rollback_to(_MARK)
            raise

    def _batch(self, session: Session, table: str, frame: pl.DataFrame, names: List[str], sets: List[str],
               keys: List[str], dates: List[str], counted: _Counted, before: int) -> None:
        """Send one batch as `data_action` says."""
        action = self.config["data_action"]
        if action == INSERT:
            refused, _ = session.many(insert_statement(table, names), frame.select(names).to_arrow())
            counted.inserted += frame.height - len(refused)
            self._refused(frame, refused, keys, counted, before)
            return
        if action == DELETE:
            refused, changed = session.many(delete_statement(table, keys, dates), frame.select(keys).to_arrow(), counts=True)
            counted.deleted += sum(changed)
            self._refused(frame, refused, keys, counted, before)
            return
        update = update_statement(table, sets, keys, dates)
        refused, changed = session.many(update, frame.select(sets + keys).to_arrow(), counts=True)
        counted.updated += sum(changed)
        self._refused(frame, refused, keys, counted, before)
        if action == UPDATE:
            return
        # The rows that changed nothing are new. Of several with one key the first is inserted and the others
        # update it, in their order: what a job that handled its rows one by one would have come to.
        turned_away = [at for at, _ in refused]
        new = frame.filter((pl.Series(changed) == 0) & ~pl.col(_AT).is_in(turned_away))
        first = pl.struct(keys).is_first_distinct()
        fresh, again = new.filter(first), new.filter(~first)
        if fresh.height:
            refused, _ = session.many(insert_statement(table, names), fresh.select(names).to_arrow())
            counted.inserted += fresh.height - len(refused)
            self._refused(fresh, refused, keys, counted, before)
        if again.height:
            refused, changed = session.many(update, again.select(sets + keys).to_arrow(), counts=True)
            counted.updated += sum(changed)
            self._refused(again, refused, keys, counted, before)

    def _refused(self, sent: pl.DataFrame, refused: List[Tuple[int, str]], keys: List[str], counted: _Counted,
                 before: int) -> None:
        """Take note of the rows the database refused; the first of them fails the component when it is to die."""
        if not refused:
            return
        at, why = refused[0]
        row = sent.row(at, named=True)
        key = ", ".join(f"{name}={shown(row[name])}" for name in keys)
        first = f"row {before + row[_AT] + 1} of the rows it was handed{f' ({key})' if key else ''}: {why}"
        if self.config["die_on_error"]:
            raise DatabaseError(f"the database refused {first}")
        counted.refused += len(refused)
        counted.first = counted.first or first

    def _defined(self, session: Session, table: str) -> None:
        """Do what `table_action` says of the table when it is a statement that defines."""
        action = self.config["table_action"]
        if action not in _DEFINING:
            return
        waiting = self.run_context.sessions.waiting(session)
        if waiting:
            raise DatabaseError(
                f"`table_action` {action} is a statement that defines, and Oracle stores what waits on a session "
                f"before one: the work of {', '.join(waiting)} would be stored with it. Put a commit before this "
                "output, or use CLEAR, which is taken back with the rows")
        create = create_statement(table, self.input_schema)
        if action in ("TRUNCATE", "TRUNCATE_REUSE_STORAGE"):
            session.run(f"truncate table {table}" + (" reuse storage" if action.endswith("STORAGE") else ""))
        elif action == "CREATE":
            session.run(create)
        elif action == "CREATE_IF_NOT_EXISTS":
            _unless(session.is_there_already, session, create)
        else:
            if action == "DROP_CREATE":
                session.run(f"drop table {table}")
            else:
                _unless(session.is_missing, session, f"drop table {table}")
            session.run(create)
        logger.info(one_line(f"[{self.id}] {action} on {table} is done, and is not taken back if what follows fails"))

    def _date_keys(self, session: Session, table: str, keys: List[str]) -> List[str]:
        """The key columns the table holds as a DATE."""
        fields = session.fields(f"select {', '.join(keys)} from {table}")
        return [name for name, field in zip(keys, fields) if field.said == "DATE"]

    def _table(self, session: Session) -> str:
        """The table as the statements name it: in its schema, the component's own or its connection's."""
        schema = self.config["schema_db"].strip() or session.schema.strip()
        return f"{schema}.{self.config['table'].strip()}" if schema else self.config["table"].strip()

    def _written_table(self) -> str:
        schema = self.config["schema_db"].strip()
        return f"{schema}.{self.config['table'].strip()}" if schema else self.config["table"].strip()


def _unless(forgiven: Any, session: Session, statement: str) -> None:
    """Run a statement that defines; a fault that says the table is as wanted already is none."""
    try:
        session.run(statement)
    except DatabaseError as fault:
        if not forgiven(fault):
            raise
