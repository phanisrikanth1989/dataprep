"""What every database input shares: one query, run once, whose rows rest in a scratch file."""
from __future__ import annotations

import dataclasses
import logging
from typing import Any, ClassVar, Dict, Iterable, Iterator, List, Tuple

import polars as pl

from ... import statements
from ...job.keys import CODE, Key, Kind
from ...sessions import Session, taken
from ..base import DIE_ON_ERROR, Source, one_line
from ..file.file_input_xml import typed_rows

logger = logging.getLogger(__name__)

# Rows a round trip, when the job says nothing: enough for the network to matter little, few enough to hold.
_BATCH = 50_000
# Rows a group of the scratch file, whatever a round trip brings. Polars reads the file's groups ahead of what
# writes the rows out, and holds what it has read: the fewer rows a group has, the less. A query of thirty million
# rows written to a CSV file held 1.5 GB with 50,000 rows a group, 0.6 GB with 10,000 and 0.4 GB with 5,000, in the
# same time. Fewer still buys little and costs a file of very many groups: a group for every thousand rows
# (Talend's cursor size) made writing ten million rows take 24 seconds where 14 do. Measured on 2026-10-12, polars
# 1.44.2.
_GROUP = 10_000


def _size(value: Any) -> int:
    try:
        rows = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{value!r} is no number of rows") from None
    if rows < 1:
        raise ValueError(f"{rows} rows cannot be fetched at a time; give 1 or more")
    return rows


def _groups(batches: Iterable[Any], size: int) -> Iterator[Any]:
    """The rows of Arrow tables of any size, in their order, as tables of `size` rows; the last holds what is left."""
    import pyarrow

    held: List[Any] = []
    waiting = 0
    for batch in batches:
        held.append(batch)
        waiting += batch.num_rows
        while waiting >= size:
            whole = pyarrow.concat_tables(held) if len(held) > 1 else held[0]
            yield whole.slice(0, size)
            waiting -= size
            held = [whole.slice(size)] if waiting else []
    if waiting:
        yield pyarrow.concat_tables(held) if len(held) > 1 else held[0]


def _trims(value: List[Any]) -> Dict[str, bool]:
    """Which columns are stripped, from the list as the converter writes it: a column's name, then its switch."""
    asked: Dict[str, bool] = {}
    name = None
    for entry in value:
        if not isinstance(entry, dict):
            raise ValueError(f"{entry!r} is no entry: give objects with `schema_column` and `trim`")
        if "schema_column" in entry or "column" in entry:
            name = str(entry.get("schema_column", entry.get("column")))
            asked.setdefault(name, False)
        if "trim" in entry:
            if name is None:
                raise ValueError("a `trim` stands before any `schema_column`: say which column it is for")
            asked[name] = entry["trim"] is True or str(entry["trim"]).strip().lower() == "true"
    return asked


READING_KEYS: Tuple[Key, ...] = (
    Key("query", type=CODE, required=True,
        doc="The query. A context variable or an entry of globalMap in it is a value: one in quotes is bound, one "
            "outside quotes has to be a name, a number or a list of those."),
    Key("use_cursor", type=bool, default=False, doc="Whether `cursor_size` says how many rows a round trip brings."),
    Key("cursor_size", type=object, default=1000, convert=_size,
        doc=f"That many rows, with `use_cursor`. Without it a round trip brings {_BATCH:,}."),
    Key("trim_all_column", type=bool, default=False, doc="Whether every text column is stripped of surrounding blanks."),
    Key("trim_column", type=list, default=[], convert=_trims, doc="Text columns to strip, one by one."),
    Key("no_null_values", type=bool, default=False, doc="Whether a text column that is missing is empty text."),
    DIE_ON_ERROR,
    Key("table", kind=Kind.IGNORED, type=object, doc="For Talend's query builder; the query says what is read."),
)


class DatabaseInput(Source):
    """The rows of one query, as the columns the job declares.

    The query is run once. Its rows are written to a scratch file a batch
    at a time, each with its number, the session is done with, and the
    engine reads the file: however often it reads a source again (for a
    second attempt, to find a row at fault, for a run of a few rows), the
    database is asked once, and the rows are the ones it handed back that
    once.

    Columns are taken by their place. Each is made the type the job
    declares by the database, or the way the database itself would make
    it so; a column of text that is declared as anything else is read as
    the text of a file is, and a value that is none of its type fails the
    job, or leaves by the reject output with `die_on_error` off.

    A failure names a row as `row 3 of the result of <id>`. The rows come
    in the order the database hands them: with an `ORDER BY` in the query,
    in that order.
    """

    outputs = {"main": ("flow", "main"), "reject": ("reject",)}
    # How the database the query is for reads a statement.
    dialect: ClassVar[statements.Dialect] = statements.ORACLE

    def problems(self) -> List[str]:
        found = [] if self.schema else ["schema: a database input needs its columns declared"]
        wrong = statements.unreadable(self.config["query"] or "")
        return found + ([f"query: {wrong}"] if wrong else [])

    def session(self) -> Tuple[Session, bool]:
        """The session to read on, and whether it is this component's own to close."""
        raise NotImplementedError

    def read(self) -> Dict[str, pl.LazyFrame]:
        made = self.run_context.made
        if self.id not in made:
            made[self.id] = self._spooled()
        path, from_text = made[self.id]
        # Each row's number is in the file. Polars is not asked to number the rows as it scans: on 1.44 its pass
        # then holds about twice as much (1.1 GB for ten million rows where half a GB does).
        frame = pl.scan_parquet(path)
        frame = self.picked(frame)
        # A true/false was asked of the database as 0 or 1; the engine makes it true or false, as any number in
        # such a column.
        # Only what arrived as text is read as its declared type here: the database has made the others so.
        as_read = [column if column.name in from_text else dataclasses.replace(column, type="str") for column in self.schema]
        outputs = typed_rows(self, frame, as_read)
        main = outputs["main"]
        texts = [column.name for column in self.schema if column.type == "str"]
        # With no list given there is none to read: the key holds its empty default.
        asked = self.config["trim_column"] or {}
        stripped = [name for name in texts if self.config["trim_all_column"] or asked.get(name)]
        if stripped:
            main = main.with_columns([pl.col(name).str.strip_chars() for name in stripped])
        if self.config["no_null_values"] and texts:
            main = main.with_columns([pl.col(name).fill_null("") for name in texts])
        return {"main": main.with_columns(self.key_copies()), "reject": outputs["reject"]}

    def locate(self, number: int) -> str:
        return f"row {number} of the result of {self.id}"

    @property
    def place_kind(self) -> str:
        return "rows"

    @property
    def place_why(self) -> str:
        return "reads the rows of a query"

    def number_at(self, place: int, sheet: Any = None) -> int:
        return place

    # ------------------------------------------------------------------

    def _spooled(self) -> Tuple[str, List[str]]:
        """Run the query and write its rows to a scratch file. Returns the file, and the columns the engine reads
        from text."""
        import pyarrow
        from pyarrow import parquet

        made = statements.read(self.config["query"], self.context, self.global_map, dialect=self.dialect)
        size = self.config["cursor_size"] if self.config["use_cursor"] else _BATCH
        names = [column.name for column in self.schema]
        session, own = self.session()
        try:
            text, binds = session.bound(made)
            fields = session.fields(text, binds)
            from_text = taken(self.schema, fields, session.advice)
            query, types = session.typed(text, self.schema, fields)
            path = self.run_context.temp_path(".parquet")
            rows = 0
            index = pl.get_index_type()
            numbered = pyarrow.field(self.row_number, pl.int_range(0, 0, dtype=index, eager=True).to_arrow().type)
            schema = pyarrow.schema([numbered] + [pyarrow.field(name, kind) for name, kind in zip(names, types)])
            # The numbers go one up at a time: packed as the step from the one before, they take next to nothing.
            # (A column that is packed so can hold no dictionary; the others keep theirs.)
            with parquet.ParquetWriter(path, schema, compression="zstd", compression_level=1, use_dictionary=names,
                                       column_encoding={self.row_number: "DELTA_BINARY_PACKED"}) as scratch:
                for group in _groups(session.batches(query, binds, types, size), _GROUP):
                    numbers = pl.int_range(rows + 1, rows + group.num_rows + 1, dtype=index, eager=True).to_arrow()
                    scratch.write_table(group.rename_columns(names).add_column(0, numbered, numbers))
                    rows += group.num_rows
        finally:
            if own:
                session.close()
        # The query as it was sent: the names of its values or their marks, and never a value.
        self.global_map[f"{self.id}_QUERY"] = made.shown()
        logger.info(one_line(f"[{self.id}] the query handed back {rows} row(s) from {session.what}"))
        return path, [name for name, text_read in zip(names, from_text) if text_read]
