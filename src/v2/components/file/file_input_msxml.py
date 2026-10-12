"""Multi-schema XML input: the records of several kinds in one document, each kind to a flow of its own."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from ... import xml_reader
from ...column_types import polars_schema
from ...errors import ConfigurationError
from ...files import not_a_file
from ...job.columns import COLUMN_KEYS, column_of
from ...job.keys import Key, Kind
from ...job.model import Column
from ...rows import key_column
from ..base import DIE_ON_ERROR, FAULTS, Source, one_line
from ..registry import REGISTRY
from .file_input_delimited import encoding
from .file_input_xml import namespaces, typed_rows, unquoted
from .file_row_count import unreadable as unreadable_file

logger = logging.getLogger(__name__)

# How many rows of a kind wait in memory before they go to a scratch file, and how many characters of all kinds.
_BATCH_ROWS = 50_000
_BATCH_CHARACTERS = 32 * 1024 * 1024
# The working column that holds the line a record starts on.
_LINE = "__xml_line"
# The output of the one entry that names no flow.
_ONLY = "main"
_NOT_READ = "v2 has one way of reading XML, and reads no DTD."
_ENTRY_KEYS = {"column": "column", "schema_column": "column", "xpath": "xpath", "query": "xpath", "nodecheck": "nodecheck"}

_ENTRY = (
    Key("flow", default="", aliases=("schema",),
        doc="The flow the rows of this kind leave by. One entry alone needs none."),
    Key("loop_path", default="", convert=unquoted,
        doc="The records of this kind: names, from an element `root_loop_query` finds (`line`, `lines/line`)."),
    Key("mapping", type=object, default="",
        doc="The paths of the columns' values, from the record, in the order of the columns: a text with commas "
            "between, as Talend writes it, or a list. A column with no path is the child of its own name."),
    Key("columns", type=list, default=[], items=COLUMN_KEYS,
        doc="The columns of the flow. One entry alone may leave them to the component's own schema."),
    Key("create_empty_row", type=bool, default=False, doc="Whether a record that has no value at all gives a row."),
)


@dataclass
class _Kind:
    """One kind of record: where its rows go, and how they are found.

    Attributes:
        port: The output its rows leave by: its flow's name, or `main` for
            the one entry that names none.
        record: The path that finds its records, from the root.
        columns: Its columns.
        paths: The path of each column's value, in the order of the columns.
        keeps_empty: Whether a record with no value at all gives a row.
    """

    port: str
    record: xml_reader.RecordPath
    columns: List[Column]
    paths: List[xml_reader.ColumnPath]
    keeps_empty: bool


def _split(written: str) -> List[str]:
    """The paths of a text of paths with commas between, as Talend writes them: each may stand in double quotes.

    A comma inside the brackets of a function or inside quotes is part of its path; XPath has a comma nowhere else.
    """
    paths: List[str] = []
    depth, quote, start = 0, "", 0
    for at, char in enumerate(written):
        if quote:
            quote = "" if char == quote else quote
        elif char in "\"'":
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth <= 0:
            paths.append(written[start:at])
            start = at + 1
    paths.append(written[start:])
    return [unquoted(path.strip()) for path in paths]


@REGISTRY.register
class FileInputMSXML(Source):
    """Read an XML document that holds records of several kinds, and hand each kind on by a flow of its own.

    `root_loop_query` is the names from the root down to the elements the
    records stand in (`/shop/order`). Each entry of `schemas` is one kind
    of record: `loop_path` finds its records from there (`line`), `flow`
    names the flow its rows leave by, and `columns` says the columns of
    that flow. `mapping` finds each column's value from the record by an
    XPath 1.0 path, as for the XML file input (`sku`, `@id`, `../@id`,
    `../head/who`). One entry alone needs no `flow`, and may leave its
    columns to the component's own schema.

    The document is gone through once for all the kinds, a piece at a
    time: what is held in memory is the largest record, or the element
    above it that a column climbs to. The rows of each kind wait in
    scratch files. Each flow has its records in the order of the document.

    A value is what the XML file input makes of it. `trim_all` takes the
    white space around every value away. A record with no value at all
    gives no row unless `create_empty_row` is on. A row whose value is
    none of its column's type fails the job, or is dropped with a warning
    where `die_on_error` is off.

    A row's number is the place of its record among the records of every
    kind, from 1.
    """

    names = ("file_input_msxml", "FileInputMSXML", "tFileInputMSXML")
    outputs: Dict[str, Tuple[str, ...]] = {}
    conforms = False
    keys = (
        Key("path", default="", aliases=("filename", "filepath"), doc="The XML file to read."),
        Key("root_loop_query", required=True, convert=unquoted,
            doc="The path, from the root, of the elements the records of every kind stand in."),
        Key("schemas", type=list, default=[], items=_ENTRY, doc="The kinds of record, each with the flow it leaves by."),
        Key("trim_all", type=bool, default=True, doc="Whether the white space around every value goes."),
        Key("encoding", default="ISO-8859-15", convert=encoding,
            doc="The encoding of a document that does not say its own."),
        Key("namespaces", type=dict, default={}, convert=namespaces,
            doc="Prefixes and the namespaces they stand for. With it, paths are read as XPath says: a name without a "
                "prefix is in no namespace."),
        Key("large_values", type=bool, default=False,
            doc="Whether a value may be larger than 10 MB and the document deeper than 256 levels."),
        DIE_ON_ERROR,
        Key("ignore_order", kind=Kind.IGNORED, type=object,
            doc="Each flow has its records in the order of the document either way."),
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
    # Which flow leaves by which entry
    # ------------------------------------------------------------------

    @staticmethod
    def _flows(config: Dict[str, Any]) -> List[str]:
        entries = config.get("schemas") or []
        return [str(entry.get("flow")) for entry in entries if isinstance(entry, dict) and entry.get("flow")]

    @classmethod
    def port_for(cls, flow_type: str, flow_name: str, config: Dict[str, Any]) -> Optional[str]:
        """A flow leaves by the entry that names it; any flow by the one entry that names none."""
        named = cls._flows(config)
        if flow_name in named:
            return flow_name
        entries = config.get("schemas") or []
        return _ONLY if len(entries) == 1 and not named and flow_type in ("flow", "main") else None

    @classmethod
    def no_port_reason(cls, flow_type: str, flow_name: str, config: Dict[str, Any]) -> str:
        return f"has no output named '{flow_name}'; its outputs are: {', '.join(cls._flows(config)) or 'none'}"

    # ------------------------------------------------------------------
    # The kinds of record
    # ------------------------------------------------------------------

    def _kinds(self) -> Tuple[List[_Kind], List[str]]:
        """The kinds of record the entries say, and what is wrong with the entries."""
        config = self.config
        given = config["namespaces"] or None
        entries = config["schemas"]
        wrong: List[str] = []
        try:
            # A `/` at its end says nothing, as in Talend.
            written = config["root_loop_query"].strip()
            root = xml_reader.record_path(written.rstrip("/") if written.strip("/") else written, given)
        except ValueError as exc:
            return [], [f"root_loop_query: {exc}"]
        if not entries:
            return [], ["schemas: names no kind of record: an entry for each flow"]
        kinds: List[_Kind] = []
        seen: Dict[str, int] = {}
        for at, entry in enumerate(entries):
            where = f"schemas[{at}]"
            flow = entry["flow"]
            if not flow and len(entries) > 1:
                wrong.append(f"{where}.flow: names no flow, and there are {len(entries)} entries: name the flow of each")
            elif flow in seen:
                wrong.append(f"{where}.flow: '{flow}' has an entry already (schemas[{seen[flow]}])")
            seen.setdefault(flow, at)
            record = None
            if not entry["loop_path"].strip("/ "):
                wrong.append(f"{where}.loop_path: there is no path")
            else:
                try:
                    record = xml_reader.record_path(
                        f"{root.written.rstrip('/')}/{entry['loop_path'].strip().strip('/')}", given)
                except ValueError as exc:
                    wrong.append(f"{where}.loop_path: {exc}")
            columns, paths = self._columns(at, entry, record, wrong)
            if record is not None:
                kinds.append(_Kind(flow or _ONLY, record, columns, paths, entry["create_empty_row"]))
        return kinds, wrong

    def _columns(
        self, at: int, entry: Dict[str, Any], record: Optional[xml_reader.RecordPath], wrong: List[str]
    ) -> Tuple[List[Column], List[xml_reader.ColumnPath]]:
        """The columns of an entry and the path of each; what is wrong with them is added to `wrong`."""
        where = f"schemas[{at}]"
        given = self.config["namespaces"] or None
        several = len(self.config["schemas"]) > 1
        mapping = entry["mapping"]
        columns = [column_of(fields) for fields in entry["columns"]]
        if not columns and not several:
            columns = list(self.schema)
        # The paths, as (place in the mapping, column, path, whether the node itself is the value).
        said: List[Tuple[str, str, str, bool]] = []
        if isinstance(mapping, str) or (isinstance(mapping, list) and all(isinstance(path, str) for path in mapping)):
            paths = (_split(mapping) if mapping.strip() else []) if isinstance(mapping, str) else [unquoted(path) for path in mapping]
            if not columns:
                wrong.append(self._no_columns(where, several))
                return [], []
            if paths and len(paths) != len(columns):
                wrong.append(f"{where}.mapping: {len(paths)} paths for {len(columns)} columns "
                             f"({', '.join(column.name for column in columns)})")
                return columns, []
            in_a_list = isinstance(mapping, list)
            said = [(f"{where}.mapping[{place}]" if in_a_list else f"{where}.mapping", column.name, path, False)
                    for place, (column, path) in enumerate(zip(columns, paths))]
        elif isinstance(mapping, list) and all(isinstance(one, dict) for one in mapping):
            for place, one in enumerate(mapping):
                unknown = sorted(set(one) - set(_ENTRY_KEYS))
                if unknown:
                    wrong.append(f"{where}.mapping[{place}].{unknown[0]}: unknown config key")
                    return columns, []
            named = [{_ENTRY_KEYS[key]: value for key, value in one.items()} for one in mapping]
            if not columns and not several:
                # No column is declared anywhere: those of the mapping, as text.
                columns = [Column(str(one.get("column", "")), "str") for one in named]
            if not columns:
                wrong.append(self._no_columns(where, several))
                return [], []
            declared = [column.name for column in columns]
            for place, one in enumerate(named):
                if one.get("column") not in declared:
                    wrong.append(f"{where}.mapping[{place}].column: there is no column '{one.get('column', '')}'; the "
                                 f"columns are: {', '.join(declared)}")
                    return columns, []
                said.append((f"{where}.mapping[{place}]", one["column"], unquoted(str(one.get("xpath") or "")),
                             bool(one.get("nodecheck"))))
        else:
            wrong.append(f"{where}.mapping: expected a text of paths with commas between, or a list")
            return columns, []
        by_column = {column: (place, path, as_node) for place, column, path, as_node in said}
        found: List[xml_reader.ColumnPath] = []
        for column in columns:
            place, path, as_node = by_column.get(column.name, (f"{where}.mapping", "", False))
            try:
                read = xml_reader.column_path(column.name, path, as_node, given)
            except ValueError as exc:
                wrong.append(f"{place}: {exc}")
                continue
            if record is not None and read.climb and record.anywhere:
                wrong.append(f"{place}: climbs above its record, and '{record.written}' may be at any depth: with //, "
                             "a column reads its record and the attributes of what is above it")
            elif record is not None and read.climb >= len(record.steps):
                wrong.append(f"{place}: climbs {read.climb} levels above its record, and '{record.written}' is "
                             f"{len(record.steps)} deep")
            found.append(read)
        return columns, found

    def _no_columns(self, where: str, several: bool) -> str:
        if several:
            return (f"{where}.columns: says no columns, and there are {len(self.config['schemas'])} entries: a "
                    "component has one schema of its own, so each entry says the columns of its flow")
        return f"{where}.columns: says no columns, and the component has no schema of its own"

    def problems(self) -> List[str]:
        found = [] if self.config["path"] else ["path: the file to read has no name"]
        return found + self._kinds()[1]

    def declared_outputs(self) -> Dict[str, pl.LazyFrame]:
        if xml_reader.etree is None:
            # Said by `problems`; nothing can be said of the columns without the library that reads the paths.
            return {}
        return {kind.port: pl.LazyFrame(schema=polars_schema(kind.columns)) for kind in self._kinds()[0]}

    def line_counts(
        self, inputs: Dict[str, pl.LazyFrame], outputs: Dict[str, pl.LazyFrame]
    ) -> Dict[str, List[pl.LazyFrame]]:
        """Every row of every flow is a row of this component, as in Talend."""
        return {"NB_LINE": list(outputs.values()), "NB_LINE_OK": list(outputs.values()), "NB_LINE_REJECT": []}

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def read(self) -> Dict[str, pl.LazyFrame]:
        kinds, _ = self._kinds()
        # Only the kinds whose flow something reads are looked for in the document.
        wanted = [kind for kind in kinds if kind.port in self.wired]
        made = self.run_context.made
        if self.id not in made:
            # The document is gone through once in its subjob, however often the engine reads the source.
            made[self.id] = self._held(wanted)
        spools = made[self.id]
        outputs: Dict[str, pl.LazyFrame] = {}
        for kind in wanted:
            files = (spools or {}).get(kind.port)
            if not files:
                outputs[kind.port] = pl.LazyFrame(schema=polars_schema(kind.columns))
                continue
            names = [column.name for column in kind.columns]
            frame = self.picked(pl.scan_ipc(files).select(names + [self.row_number]))
            if self.config["trim_all"]:
                frame = frame.with_columns([pl.col(name).str.strip_chars() for name in names])
            if not kind.keeps_empty:
                frame = frame.filter(~pl.all_horizontal([pl.col(name).is_null() | (pl.col(name) == "") for name in names]))
            frame = frame.with_columns(
                [pl.col(column.name).alias(key_column(self.id, column.name)) for column in kind.columns if column.key])
            outputs[kind.port] = typed_rows(self, frame, kind.columns)["main"]
        return outputs

    def _held(self, kinds: List[_Kind]) -> Optional[Dict[str, List[str]]]:
        """For each flow, the scratch files its rows wait in; None when the document cannot be read and the job goes on."""
        try:
            return self._spooled(kinds)
        except FAULTS as exc:
            self.fail_or_go_on(exc, " with no row")
            return None

    def _spooled(self, kinds: List[_Kind]) -> Dict[str, List[str]]:
        """Go through the document once and write the rows of each kind, as text, to scratch files of a batch each."""
        config = self.config
        path = config["path"]
        if not os.path.exists(path):
            raise ConfigurationError(f"File not found: '{path}'")
        if not_a_file(path):
            raise ConfigurationError(f"'{path}' cannot be read: {not_a_file(path)}")
        files: List[List[str]] = [[] for _ in kinds]
        held: List[List[List[Optional[str]]]] = [[[] for _ in kind.columns] for kind in kinds]
        lines: List[List[int]] = [[] for _ in kinds]
        numbers: List[List[int]] = [[] for _ in kinds]
        made = characters = 0

        def put_away(at: int) -> None:
            names = [column.name for column in kinds[at].columns]
            batch = pl.DataFrame(dict(zip(names, held[at])), schema={name: pl.String for name in names}).with_columns(
                pl.Series(self.row_number, numbers[at], dtype=pl.UInt32), pl.Series(_LINE, lines[at], dtype=pl.UInt32))
            files[at].append(self.run_context.temp_path(".arrow"))
            batch.write_ipc(files[at][-1], compression="zstd")
            for values in (*held[at], lines[at], numbers[at]):
                values.clear()

        etree = xml_reader.etree
        walk = None
        try:
            with open(path, "rb") as source:
                walk = xml_reader.Several(source, [(kind.record, kind.paths) for kind in kinds], encoding=config["encoding"],
                                          large_values=config["large_values"])
                for at, line, values in walk:
                    made += 1
                    numbers[at].append(made)
                    lines[at].append(line or 0)
                    for cell, value in zip(held[at], values):
                        cell.append(value)
                        characters += len(value) if value else 0
                    if characters >= _BATCH_CHARACTERS:
                        for other in range(len(kinds)):
                            if lines[other]:
                                put_away(other)
                        characters = 0
                    elif len(lines[at]) >= _BATCH_ROWS:
                        put_away(at)
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
        for at in range(len(kinds)):
            if lines[at]:
                put_away(at)
        for (at, name), (records, first) in walk.many.items():
            logger.warning(one_line(
                f"[{self.id}] the path of column '{name}' of '{kinds[at].port}' found more than one node in {records} "
                f"record{'s' if records > 1 else ''} (the first: record {first}); the first node is the value"))
        self.global_map[f"{self.id}_FILENAME"] = path
        return {kind.port: files[at] for at, kind in enumerate(kinds)}

    # ------------------------------------------------------------------
    # Where a row is
    # ------------------------------------------------------------------

    def locate(self, number: int) -> str:
        """Where a row's record is: its place among the records, the flow it left by, and the line it starts near."""
        place = f"record {number} of {self.config['path']}"
        for port, files in (self.run_context.made.get(self.id) or {}).items():
            if not files:
                continue
            # The line is the parser's, and exact only up to line 65,535: a hint, not the record's place.
            found = pl.scan_ipc(files).filter(pl.col(self.row_number) == number).select(_LINE).collect()
            if found.height:
                flow = "" if port == _ONLY else f" ({port})"
                return f"{place}{flow}, near line {found.item()}" if found.item() else f"{place}{flow}"
        return place

    @property
    def place_kind(self) -> str:
        return "records"

    @property
    def place_why(self) -> str:
        return "reads the records of a document"

    def number_at(self, place: int, sheet: Optional[str] = None) -> int:
        return place
