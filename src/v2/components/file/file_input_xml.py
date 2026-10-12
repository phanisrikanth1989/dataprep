"""XML file input: the records a path finds in a document, as rows."""
from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

import polars as pl

from ... import xml_reader
from ...column_types import finish_value, parse_text, polars_schema, unreadable
from ...errors import ConfigurationError
from ...files import not_a_file
from ...job.keys import Key, Kind
from ...job.model import Column
from ...rows import first_of
from ..base import DIE_ON_ERROR, FAULTS, Source, one_line
from ..registry import REGISTRY
from .file_input_delimited import encoding, fatal, first_reason, unreadable_text
from .file_row_count import unreadable as unreadable_file

logger = logging.getLogger(__name__)

# How many rows wait in memory before they go to a scratch file, and how many characters of them at the most.
_BATCH_ROWS = 50_000
_BATCH_CHARACTERS = 32 * 1024 * 1024
# Working columns: the line a record starts on, a column's value read from its text, and whether a row is turned away.
_LINE, _VALUE, _BAD = "__xml_line", "__v_", "__bad"
_NOT_READ = "v2 has one way of reading XML, and reads no DTD."


def unquoted(value: str) -> str:
    """A path as written, less the double quotes Talend may put around it."""
    return value[1:-1] if len(value) > 1 and value.startswith('"') and value.endswith('"') else value


def most(what: str) -> Callable[[Any], Optional[int]]:
    """A check for a key that says how many of something are made at the most; nothing given is no limit."""
    def limit(value: Any) -> Optional[int]:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        if isinstance(value, bool) or not isinstance(value, (int, str)) or (isinstance(value, str) and not value.strip().isdigit()):
            raise ValueError(f"{value!r} is no number of {what}")
        if int(value) < 0:
            raise ValueError(f"{value} is no number of {what}")
        return int(value)
    return limit


def namespaces(value: Dict[str, Any]) -> Dict[str, str]:
    for prefix, uri in value.items():
        if not isinstance(uri, str) or not uri:
            raise ValueError(f"the namespace of the prefix '{prefix}' is no text")
    return dict(value)


_MAPPING = (
    Key("column", required=True, aliases=("schema_column",), doc="The column the value goes to."),
    Key("xpath", default="", aliases=("query",), convert=unquoted,
        doc="The XPath 1.0 path of the value, from the record; none: the child of the column's own name."),
    Key("nodecheck", type=bool, default=False,
        doc="Talend's \"Get Nodes\": the value is the node as XML text, and not the text in it."),
)


def typed_rows(component: Source, frame: pl.LazyFrame, columns: List[Column]) -> Dict[str, pl.LazyFrame]:
    """The values of a reader of XML read as their columns declare them, and the rows whose values are none of that type.

    Args:
        component: The reader. With its `die_on_error` on, such a row fails
            its subjob; with it off, the row is among the rejects, and is
            told of in the log where no flow takes them.
        frame: The rows, every value as the text that was read.
        columns: The columns, as they are declared.

    Returns:
        The rows that could be read under `main`, the others under `reject`.
    """
    names = [column.name for column in columns]
    carried = [name for name in frame.collect_schema().names() if name not in names]
    typed = [column for column in columns if column.type != "str"]
    none = pl.LazyFrame(schema={name: pl.String for name in names + ["errorCode", "errorMessage"]})
    if not typed:
        return {"main": frame, "reject": none}
    frame = frame.with_columns([parse_text(pl.col(column.name), column).alias(_VALUE + column.name) for column in typed])
    cases = [
        (unreadable(pl.col(_VALUE + column.name), pl.col(column.name), column),
         pl.format(unreadable_text(column), pl.col(column.name)))
        for column in typed
    ]
    held = {column.name: column for column in typed}
    values = [
        finish_value(pl.col(_VALUE + name), pl.col(name), held[name]).alias(name) if name in held else pl.col(name)
        for name in names
    ]
    message = pl.coalesce([pl.when(wrong).then(text) for wrong, text in cases])
    flagged = frame.with_columns(pl.any_horizontal([wrong for wrong, _ in cases]).alias(_BAD))
    reason = {"errorCode": pl.lit("TYPE_CONVERSION").alias("errorCode"), "errorMessage": message.alias("errorMessage")}
    # A data column with one of the two names gives its place to the reason, as in the other readers.
    reject = flagged.filter(pl.col(_BAD)).select(
        *[reason.get(name, pl.col(name)) for name in names],
        *[expr for name, expr in reason.items() if name not in names],
        *carried,
    )
    if component.config["die_on_error"]:
        component.check(reject.select(pl.len().alias("rows"), first_reason(), *first_of(reject)),
                        lambda found: fatal(found, component.where(found)))
    else:
        flagged = component.tell_dropped(flagged, pl.col(_BAD), message)
    return {"main": flagged.filter(~pl.col(_BAD)).select(values + carried), "reject": reject}


@REGISTRY.register
class FileInputXML(Source):
    """Read an XML document and hand on one row for each record `loop_query` finds in it.

    `loop_query` is the names from the root down to the record
    (`/orders/order/line`), `*` for any name, or `//line` for a name at any
    depth. Each `mapping` entry finds a column's value from the record by
    an XPath 1.0 path: `sku`, `@id`, `../status`, `../../@region`. One
    node gives its text, no node a missing value, an empty element empty
    text, `xsi:nil="true"` a missing value; of several nodes the first is
    the value, and a warning says so. Values are text until they are read
    as the type their column declares; a row whose value is none of that
    type leaves by the reject output, or fails the job.

    The document is gone through once, a piece at a time: what is held in
    memory is the largest record, or the element above it that a column
    climbs to, and not the file. The rows wait in scratch files, so
    scratch space of about the size of the values is needed. Nothing but
    the document is read: no DTD, and no entity it declares, which fails
    the job. Names are matched by their local name, unless `namespaces`
    binds prefixes; then a path is read as XPath says. What the document
    says of its own encoding decides; `encoding` is for one that says
    nothing.

    A row's number is the place of its record among the records, from 1.
    """

    names = ("file_input_xml", "FileInputXML", "tFileInputXML")
    outputs = {"main": ("flow", "main"), "reject": ("reject",)}
    keys = (
        Key("path", required=True, aliases=("filepath", "filename"), doc="The XML file to read."),
        Key("loop_query", required=True, convert=unquoted, doc="The path that finds the records, from the root."),
        Key("mapping", type=list, default=[], items=_MAPPING, doc="Which value of a record goes to which column."),
        Key("limit", type=object, default=None, convert=most("records"), doc="The most records to read; none given: all."),
        Key("encoding", default="ISO-8859-15", convert=encoding,
            doc="The encoding of a document that does not say its own."),
        Key("namespaces", type=dict, default={}, convert=namespaces,
            doc="Prefixes and the namespaces they stand for. With it, paths are read as XPath says: a name without a "
                "prefix is in no namespace."),
        Key("large_values", type=bool, default=False,
            doc="Whether a value may be larger than 10 MB and the document deeper than 256 levels."),
        DIE_ON_ERROR,
        Key("use_separator", kind=Kind.REFUSED, type=bool,
            reason="v2 reads a node's text as it is: split it with a step after the reader"),
        Key("field_separator", kind=Kind.IGNORED, type=object, doc="Only read with `use_separator`."),
        Key("ignore_ns", kind=Kind.IGNORED, type=object,
            doc="Names are matched by their local name already, unless `namespaces` is given."),
        Key("ignore_dtd", kind=Kind.IGNORED, type=object, doc=_NOT_READ),
        Key("generation_mode", kind=Kind.IGNORED, type=object, doc=_NOT_READ),
        Key("check_date", kind=Kind.IGNORED, type=object, doc="A date is read by its column's pattern either way."),
        Key("advanced_separator", kind=Kind.IGNORED, type=object, doc="Numbers are read as the engine reads them."),
        Key("thousands_separator", kind=Kind.IGNORED, type=object, doc="Only read with `advanced_separator`."),
        Key("decimal_separator", kind=Kind.IGNORED, type=object, doc="Only read with `advanced_separator`."),
        Key("xml_streaming_threshold_mb", kind=Kind.IGNORED, type=object,
            doc="v1's switch between its two ways of reading; v2 has one."),
    )

    # ------------------------------------------------------------------
    # The paths
    # ------------------------------------------------------------------

    def _columns(self) -> List[Column]:
        """The columns handed on: the declared ones, or those of the mapping, as text, when none is declared."""
        if self.schema:
            return self.schema
        return [Column(name, "str") for name in dict.fromkeys(entry["column"] for entry in self.config["mapping"])]

    def _paths(self) -> Tuple[xml_reader.RecordPath, List[xml_reader.ColumnPath]]:
        config = self.config
        given = config["namespaces"] or None
        by_column = {entry["column"]: entry for entry in config["mapping"]}
        columns = []
        for column in self._columns():
            entry = by_column.get(column.name, {"xpath": "", "nodecheck": False})
            columns.append(xml_reader.column_path(column.name, entry["xpath"], entry["nodecheck"], given))
        return xml_reader.record_path(config["loop_query"], given), columns

    def problems(self) -> List[str]:
        config = self.config
        given = config["namespaces"] or None
        found: List[str] = []
        record = None
        try:
            xml_reader.needs_lxml()
            record = xml_reader.record_path(config["loop_query"], given)
        except ValueError as exc:
            found.append(f"loop_query: {exc}")
        except xml_reader.Fault as exc:
            # The library is not there: said once, and no path is at fault.
            return [f"config: {exc}"]
        declared = [column.name for column in self._columns()]
        for at, entry in enumerate(config["mapping"]):
            if entry["column"] not in declared:
                found.append(f"mapping[{at}].column: there is no column '{entry['column']}'; the columns are: "
                             f"{', '.join(declared)}")
                continue
            try:
                path = xml_reader.column_path(entry["column"], entry["xpath"], entry["nodecheck"], given)
            except ValueError as exc:
                found.append(f"mapping[{at}].xpath: {exc}")
                continue
            if record is None or not path.climb:
                continue
            if record.anywhere:
                found.append(f"mapping[{at}].xpath: climbs above its record, and '{record.written}' may be at any "
                             "depth: with //, a column reads its record and the attributes of what is above it")
            elif path.climb >= len(record.steps):
                found.append(f"mapping[{at}].xpath: climbs {path.climb} levels above its record, and "
                             f"'{record.written}' is {len(record.steps)} deep")
        return found

    def declared_outputs(self) -> Dict[str, pl.LazyFrame]:
        columns = self._columns()
        return {"main": pl.LazyFrame(schema=polars_schema(columns)), "reject": self._no_rejects(columns)}

    @staticmethod
    def _no_rejects(columns: List[Column]) -> pl.LazyFrame:
        names = [column.name for column in columns]
        return pl.LazyFrame(schema={name: pl.String for name in names + ["errorCode", "errorMessage"]})

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def read(self) -> Dict[str, pl.LazyFrame]:
        made = self.run_context.made
        if self.id not in made:
            # The document is gone through once in its subjob, however often the engine reads the source.
            made[self.id] = self._held()
        files = made[self.id]
        columns = self._columns()
        if not files:
            return self.declared_outputs()
        names = [column.name for column in columns]
        frame = self.picked(pl.scan_ipc(files).select(names + [self.row_number]))
        frame = frame.with_columns(self.key_copies())
        return self._typed(frame, columns)

    def _held(self) -> Optional[List[str]]:
        """The scratch files the rows wait in; None when the document cannot be read and the job is to go on."""
        try:
            return self._spooled()
        except FAULTS as exc:
            self.fail_or_go_on(exc, " with no row")
            return None

    def _spooled(self) -> List[str]:
        """Go through the document once and write its rows, as text, to scratch files of a batch each."""
        config = self.config
        path = config["path"]
        if not os.path.exists(path):
            raise ConfigurationError(f"File not found: '{path}'")
        if not_a_file(path):
            raise ConfigurationError(f"'{path}' cannot be read: {not_a_file(path)}")
        record, columns = self._paths()
        names = [column.name for column in columns]
        files: List[str] = []
        held: List[List[Optional[str]]] = [[] for _ in names]
        lines: List[int] = []
        made = characters = 0

        def put_away() -> None:
            first = made - len(lines) + 1
            batch = pl.DataFrame(dict(zip(names, held)), schema={name: pl.String for name in names}).with_columns(
                pl.int_range(first, made + 1, dtype=pl.UInt32).alias(self.row_number),
                pl.Series(_LINE, lines, dtype=pl.UInt32),
            )
            files.append(self.run_context.temp_path(".arrow"))
            batch.write_ipc(files[-1], compression="zstd")
            for values in held:
                values.clear()
            lines.clear()

        etree = xml_reader.etree
        try:
            with open(path, "rb") as source:
                walk = xml_reader.Records(source, record, columns, encoding=config["encoding"],
                                          large_values=config["large_values"], limit=config["limit"])
                for line, values in walk:
                    made += 1
                    lines.append(line or 0)
                    for cell, value in zip(held, values):
                        cell.append(value)
                        characters += len(value) if value else 0
                    if len(lines) >= _BATCH_ROWS or characters >= _BATCH_CHARACTERS:
                        put_away()
                        characters = 0
        except etree.XMLSyntaxError as exc:
            raise ConfigurationError(f"'{path}' is not well-formed XML: {xml_reader.not_well_formed(exc)}") from None
        except xml_reader.Fault as exc:
            raise ConfigurationError(f"'{path}' cannot be read: {exc}") from None
        except LookupError:
            raise ConfigurationError(
                f"'{path}' says nothing of its encoding, and the parser of XML does not know '{config['encoding']}': "
                "name the encoding in a way it knows (UTF-8, ISO-8859-15, windows-1252 and the like)") from None
        except OSError as exc:
            raise ConfigurationError(f"'{path}' cannot be read: {unreadable_file(path, exc)}") from None
        if lines:
            put_away()
        for name, (records, first) in walk.many.items():
            logger.warning(one_line(
                f"[{self.id}] the path of column '{name}' found more than one node in {records} "
                f"record{'s' if records > 1 else ''} (the first: record {first}); the first node is the value"))
        self.global_map[f"{self.id}_FILENAME"] = path
        return files

    def _typed(self, frame: pl.LazyFrame, columns: List[Column]) -> Dict[str, pl.LazyFrame]:
        return typed_rows(self, frame, columns)

    # ------------------------------------------------------------------
    # Where a row is
    # ------------------------------------------------------------------

    def locate(self, number: int) -> str:
        """Where a row's record is: its place among the records, and the line it starts near."""
        place = f"record {number} of {self.config['path']}"
        files = self.run_context.made.get(self.id)
        if files:
            # The line is the parser's, and exact only up to line 65,535: a hint, not the record's place.
            found = pl.scan_ipc(files).filter(pl.col(self.row_number) == number).select(_LINE).collect()
            if found.height and found.item():
                place += f", near line {found.item()}"
        return place

    @property
    def place_kind(self) -> str:
        return "records"

    @property
    def place_why(self) -> str:
        return "reads the records of a document"

    def number_at(self, place: int, sheet: Optional[str] = None) -> int:
        return place
