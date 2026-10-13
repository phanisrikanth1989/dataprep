"""Extract XML field: the records a path finds in the document a column holds, as rows."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from ... import xml_reader
from ...column_types import finish_value, parse_text, polars_schema, unreadable
from ...errors import ConfigurationError
from ...job.keys import Key, Kind
from ...job.model import Column
from ...rows import hidden, shown, visible
from ..base import Transform, one_line
from ..file.file_input_delimited import unreadable_text
from ..file.file_input_xml import most, namespaces, unquoted
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# What a row that is turned away says of itself, after its columns.
_REASON = ("errorXMLField", "errorCode", "errorMessage")
# Working columns: a value read as its column's type, where a record came from, and what is wrong with it.
_VALUE, _ROW, _PLACE, _WHY = "__v_", "__xml_row", "__xml_place", "__xml_why"
# How many records wait as Python's own texts before they are put into a frame, which holds them in less.
_BATCH = 50_000
# A path that starts with a name and not at the root; a name with a bracket after it is a function, and no path.
_FROM_NOWHERE = re.compile(r"\s*(?![/(])(?![A-Za-z_][\w.\-]*\s*\()")

_ENTRY = (
    Key("schema_column", default="", aliases=("column",),
        doc="The column to fill. Entries that name none are those of the output columns, in their order."),
    Key("query", default="", aliases=("xpath",), convert=unquoted,
        doc="The XPath 1.0 path of its value, from the record or from the root. With none, the input column of the "
            "same name is handed on."),
    Key("nodecheck", type=bool, default=False,
        doc="Talend's \"Get Nodes\": the value is the node as XML text, and not the text in it."),
)


@REGISTRY.register
class ExtractXMLField(Transform):
    """Read the XML document in the column `xmlfield` and hand on one row for each record `loop_query` finds in it.

    `loop_query` is an XPath 1.0 path that finds elements: each is a
    record and gives a row, and a document it finds none in gives no row.
    Each `mapping` entry fills a column from its path, followed from the
    record (`sku`, `@id`, `../@region`) or from the root (`/order/@id`).
    One node gives its text, no node a missing value, an empty element
    empty text, `xsi:nil="true"` a missing value; of several nodes the
    first is the value, and a warning says so. A column with no path is
    the input column of its name. Values are text until they are read as
    the type their column declares.

    A row with no document gives no row. A document that is not
    well-formed XML, an empty text among them, leaves by the reject
    output with the text in `errorXMLField` (`PARSE_ERROR`). A record
    with a value that is none of its column's type leaves by it too, with
    the record in `errorXMLField` (`TYPE_CONVERSION`); the other records
    of its document go on. With `die_on_error` the first such fault fails
    the job.

    Nothing but the document is read: no DTD, and no entity it declares.
    Names are matched by their local name, unless `namespaces` binds
    prefixes; then a path is read as XPath says.

    A document is read out of every row in Python, so this component
    holds its rows in memory.
    """

    names = ("extract_xml_field", "ExtractXMLField", "tExtractXMLField")
    outputs = {"main": ("flow", "main"), "reject": ("reject",)}
    may_need_rows = True
    keys = (
        Key("xmlfield", default="", doc="The column that holds the document; the first column when none is named."),
        Key("loop_query", required=True, convert=unquoted, doc="The XPath 1.0 path that finds the records of a document."),
        Key("mapping", type=list, default=[], items=_ENTRY, doc="The columns to fill, each with its path."),
        Key("limit", type=object, default=None, convert=most("rows"),
            doc="The most rows to make, over all the documents; none given: all. The rows after it are not read."),
        Key("namespaces", type=dict, default={}, convert=namespaces,
            doc="Prefixes and the namespaces they stand for. With it, paths are read as XPath says: a name without a "
                "prefix is in no namespace."),
        Key("large_values", type=bool, default=False,
            doc="Whether a value may be larger than 10 MB and a document deeper than 256 levels."),
        Key("die_on_error", type=bool, default=False,
            doc="Whether a document that cannot be read, or a value that is none of its column's type, fails the job; "
                "when off, the row leaves by the reject output."),
        Key("ignore_ns", kind=Kind.IGNORED, type=object,
            doc="Names are matched by their local name already, unless `namespaces` is given."),
    )

    def needs_rows(self) -> bool:
        return True

    # ------------------------------------------------------------------
    # The columns and their paths
    # ------------------------------------------------------------------

    def _entries(self) -> Tuple[List[Dict[str, Any]], List[str]]:
        """The entries of the mapping, each with its column, and what is wrong with them."""
        mapping = self.config["mapping"]
        declared = [column.name for column in self.schema]
        if mapping and not any(entry["schema_column"] for entry in mapping):
            # As an older converted job has them: one for each output column, in their order.
            if len(mapping) > len(declared):
                return [], [f"mapping: {len(mapping)} entries that name no column, and the output has {len(declared)} "
                            "columns: an entry for each, in their order"]
            return [dict(entry, schema_column=name) for entry, name in zip(mapping, declared)], []
        wrong: List[str] = []
        seen: Dict[str, int] = {}
        for at, entry in enumerate(mapping):
            name = entry["schema_column"]
            if not name:
                wrong.append(f"mapping[{at}].schema_column: this entry names no column, and others do: name the "
                             "column of each")
            elif declared and name not in declared:
                wrong.append(f"mapping[{at}].schema_column: there is no column '{name}'; the columns are: "
                             f"{', '.join(declared)}")
            elif name in seen:
                wrong.append(f"mapping[{at}].schema_column: '{name}' has an entry already (mapping[{seen[name]}])")
            seen.setdefault(name, at)
        return mapping, wrong

    def _columns(self, entries: List[Dict[str, Any]]) -> List[Column]:
        """The columns handed on: the declared ones, or those of the mapping, as text, when none is declared."""
        return self.schema or [Column(entry["schema_column"], "str") for entry in entries]

    def problems(self) -> List[str]:
        config = self.config
        given = config["namespaces"] or None
        found: List[str] = []
        names = [column.name for column in self.input_schema]
        if names and config["xmlfield"] and config["xmlfield"] not in names:
            found.append(f"xmlfield: there is no column '{config['xmlfield']}'; the columns are: {', '.join(names)}")
        try:
            xml_reader.path(config["loop_query"], given)
            if _FROM_NOWHERE.match(config["loop_query"]):
                # Talend follows such a path from the document, and the library here from the root element: one
                # of the two would find nothing, without a word.
                found.append("loop_query: does not start at the root, where the records of a document are found "
                             f"from: write it as /{config['loop_query'].strip()}")
        except ValueError as exc:
            found.append(f"loop_query: {exc}")
        except xml_reader.Fault as exc:
            # The library is not there: said once, and no path is at fault.
            return [f"config: {exc}"]
        entries, wrong = self._entries()
        found += wrong
        for at, entry in enumerate(entries):
            if entry["query"]:
                try:
                    xml_reader.path(entry["query"], given)
                except ValueError as exc:
                    found.append(f"mapping[{at}].query: {exc}")
        return found

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def run(self, inputs: Dict[str, pl.DataFrame]) -> Dict[str, pl.DataFrame]:
        (frame,) = inputs.values()
        config = self.config
        names = visible(frame.columns)
        field = config["xmlfield"] or (names[0] if names else "")
        if field not in names:
            raise ConfigurationError(f"xmlfield: there is no column '{field}'; the columns are: {', '.join(names)}")
        entries, _ = self._entries()
        columns = self._columns(entries)
        by_column = {entry["schema_column"]: entry for entry in entries}
        paths = {column.name: (by_column[column.name]["query"], by_column[column.name]["nodecheck"])
                 for column in columns if by_column.get(column.name, {}).get("query")}
        # Every column no path fills is handed on from the row, where the row has one of its name.
        handed = {column.name: column.name for column in columns if column.name not in paths}
        plan = Plan(field, config["loop_query"], columns, paths, handed, config["limit"], config["namespaces"] or None,
                    config["large_values"], config["die_on_error"])
        return Extraction(self, plan).of(frame)


@dataclass
class Plan:
    """What is taken out of the documents of a column, and how.

    Attributes:
        field: The column that holds the document.
        loop_query: The XPath that finds the records of a document.
        columns: The columns handed on.
        paths: For each column a path fills: its XPath, and whether the
            node itself is the value.
        handed: For each other column: the column of the row it is handed
            on from. One the row does not have is missing.
        limit: The most rows to make, over all the documents; None for all.
        namespaces: Prefixes and their namespaces, when names are read with them.
        large_values: Whether the parser's own limits are lifted.
        die_on_error: Whether the first fault fails the job.
        with_rejects: Whether the rows that are turned away are wanted.
    """

    field: str
    loop_query: str
    columns: List[Column]
    paths: Dict[str, Tuple[str, bool]]
    handed: Dict[str, str]
    limit: Optional[int]
    namespaces: Optional[Dict[str, str]]
    large_values: bool
    die_on_error: bool
    with_rejects: bool = True


class Extraction:
    """The records of the documents a column holds, as rows: the work of extract XML field, which XML map does too.

    Args:
        component: The component the work is done for: its id is in the
            log, and what it is told of the rows that arrive names a row.
        plan: What is taken out, and how.
    """

    def __init__(self, component: Transform, plan: Plan) -> None:
        self.component, self.plan = component, plan
        self.strict = bool(plan.namespaces)

    def of(self, frame: pl.DataFrame) -> Dict[str, pl.DataFrame]:
        """The rows of the main output and of the reject output, for the rows that arrive."""
        plan, component = self.plan, self.component
        carried = hidden(frame.columns)
        columns = plan.columns
        # The columns a path fills, each with its path compiled.
        paths = [(column.name, xml_reader.path(plan.paths[column.name][0], plan.namespaces), plan.paths[column.name][1])
                 for column in columns if column.name in plan.paths]
        found, turned = self._read(frame[plan.field], paths)

        filled = {name for name, _, _ in paths}
        typed = [column for column in columns if column.name in filled and column.type != "str"]
        found = found.with_columns([parse_text(pl.col(column.name), column).alias(_VALUE + column.name) for column in typed])
        cases = [(unreadable(pl.col(_VALUE + column.name), pl.col(column.name), column),
                  pl.format(unreadable_text(column), pl.col(column.name))) for column in typed]
        why = pl.coalesce([pl.when(wrong).then(text) for wrong, text in cases]) if cases else pl.lit(None, dtype=pl.String)
        found = found.with_columns(why.alias(_WHY))
        good, bad = found.filter(pl.col(_WHY).is_null()), found.filter(pl.col(_WHY).is_not_null())

        # What is turned away, in the order of the rows: a document as a whole, or one record of it.
        faults = sorted(
            [(at, -1, code, said) for at, _, code, said in turned]
            + [(at, place, "TYPE_CONVERSION", said) for at, place, said in bad.select(_ROW, _PLACE, _WHY).iter_rows()])
        if faults and plan.die_on_error:
            at, _, _, said = faults[0]
            raise ConfigurationError(f"{shown(said)}{component.where(frame[[at]].select(carried))}")
        if faults:
            component.tell_rows_dropped(len(faults), faults[0][3], frame[[faults[0][0]]].select(carried))

        held = {column.name: column for column in typed}
        main = self._beside(good, frame, [
            finish_value(pl.col(_VALUE + column.name), pl.col(column.name), held[column.name]).alias(column.name)
            if column.name in held else pl.col(column.name) if column.name in filled
            else None for column in columns]).hstack(_taken(frame.select(carried), good[_ROW].to_list()))
        if not plan.with_rejects:
            return {"main": main}
        return {"main": main, "reject": self._turned_away(frame, filled, turned, bad, carried)}

    def _read(
        self, documents: pl.Series, paths: List[Tuple[str, Any, bool]]
    ) -> Tuple[pl.DataFrame, List[Tuple[int, str, str, str]]]:
        """Go through the documents: the values of every record, as text, and the documents that cannot be read.

        Returns:
            The records, a row each: the text of each column a path fills,
            the place of the row it came from, and its place among the
            records of its document. And for each document that cannot be
            read: the place of its row, its text, a code and what is wrong.
        """
        plan, strict, limit = self.plan, self.strict, self.plan.limit
        loop = xml_reader.path(plan.loop_query, plan.namespaces)
        parser = xml_reader.parser(plan.large_values)
        etree = xml_reader.etree
        texts: Dict[str, List[Optional[str]]] = {name: [] for name, _, _ in paths}
        origin: List[int] = []
        places: List[int] = []
        batches: List[pl.DataFrame] = []
        turned: List[Tuple[int, str, str, str]] = []
        many: Dict[str, Tuple[int, int]] = {}
        none = made = 0

        def put_away() -> None:
            batches.append(pl.DataFrame(texts, schema={name: pl.String for name in texts}).with_columns(
                pl.Series(_ROW, origin, dtype=pl.UInt32), pl.Series(_PLACE, places, dtype=pl.UInt32)))
            for values in (*texts.values(), origin, places):
                values.clear()

        for at, held in enumerate(documents):
            if limit is not None and made >= limit:
                break
            if held is None:
                none += 1
                continue
            text = held if isinstance(held, str) else str(held)
            if not text.strip():
                turned.append((at, text, "PARSE_ERROR", "the document is empty"))
                continue
            try:
                root = xml_reader.document(text, parser, strict)
            except etree.XMLSyntaxError as exc:
                turned.append((at, text, "PARSE_ERROR",
                               f"the document is not well-formed XML: {xml_reader.not_well_formed(exc)}"))
                continue
            except xml_reader.Fault as exc:
                turned.append((at, text, "PARSE_ERROR", str(exc)))
                continue
            for place, record in enumerate(self._records(loop, root)):
                if limit is not None and made >= limit:
                    break
                made += 1
                origin.append(at)
                places.append(place)
                for name, find, as_node in paths:
                    value, several = xml_reader.value(find(record), as_node, strict)
                    if several:
                        records, first = many.get(name, (0, made))
                        many[name] = (records + 1, first)
                    texts[name].append(value)
            if len(origin) >= _BATCH:
                put_away()
        where = self.component.id
        if none:
            one = none == 1
            logger.info(one_line(f"[{where}] {none} row{'' if one else 's'} hold{'s' if one else ''} no document in "
                                 f"'{plan.field}' and give{'s' if one else ''} no row"))
        for name, (records, first) in many.items():
            logger.warning(one_line(
                f"[{where}] the path of column '{name}' found more than one node in {records} "
                f"record{'s' if records > 1 else ''} (the first: record {first}); the first node is the value"))
        put_away()
        return pl.concat(batches), turned

    def _records(self, loop: Any, root: Any) -> List[Any]:
        """The records of a document: the elements the loop query finds, asked from the document itself."""
        found = loop(root.getroottree())
        if not isinstance(found, list) or not all(isinstance(getattr(node, "tag", None), str) for node in found):
            raise ConfigurationError(
                f"loop_query: '{self.plan.loop_query}' finds what is no element (an attribute, a text, a number): "
                "a record is an element")
        return found

    def _beside(self, records: pl.DataFrame, frame: pl.DataFrame, values: List[Optional[pl.Expr]]) -> pl.DataFrame:
        """The records with the columns of the rows they came from beside them, as the output has them.

        Args:
            records: The records, with the place of the row each came from.
            frame: The rows that arrived.
            values: For each output column, its value from the record; None
                for one that is handed on from the row, or is missing.
        """
        plan = self.plan
        declared = polars_schema(plan.columns)
        # Only the columns that are handed on: the document itself, taken once for each of its records, would
        # be the largest thing in memory.
        handed = sorted({plan.handed[column.name] for column, value in zip(plan.columns, values)
                         if value is None and plan.handed.get(column.name) in frame.columns})
        rows = _taken(frame.select(handed), records[_ROW].to_list())
        made = []
        for column, value in zip(plan.columns, values):
            if value is not None:
                made.append(records.select(value).to_series())
            elif plan.handed.get(column.name) in rows.columns:
                made.append(rows[plan.handed[column.name]].alias(column.name))
            else:
                made.append(pl.Series(column.name, [None] * records.height, dtype=declared[column.name]))
        return pl.DataFrame(made) if made else records.select([])

    def _turned_away(
        self, frame: pl.DataFrame, filled: set, turned: List[Tuple[int, str, str, str]], bad: pl.DataFrame,
        carried: List[str],
    ) -> pl.DataFrame:
        """The rows of the reject output: the output columns as text, and what is wrong.

        A document that cannot be read has its own text in `errorXMLField`,
        and nothing in the columns a path fills. A record with a value that
        is none of its column's type has the record there, and the values
        as they were read.
        """
        plan = self.plan
        texts = [column.name for column in plan.columns if column.name not in _REASON]
        # For each column that is handed on: the column of the row it comes from.
        sources = {name: plan.handed[name] for name in texts
                   if name not in filled and plan.handed.get(name) in frame.columns}
        taken = frame.select(sorted(set(sources.values())) + carried)

        def as_text(rows: pl.DataFrame, name: str, height: int) -> pl.Series:
            if name in sources:
                return rows[sources[name]].cast(pl.String).alias(name)
            return pl.Series(name, [None] * height, dtype=pl.String)

        # The documents that cannot be read.
        whole = _taken(taken, [at for at, _, _, _ in turned])
        parts = [pl.DataFrame(
            [as_text(whole, name, len(turned)) for name in texts]
            + [pl.Series("errorXMLField", [text for _, text, _, _ in turned], dtype=pl.String),
               pl.Series("errorCode", [code for _, _, code, _ in turned], dtype=pl.String),
               pl.Series("errorMessage", [said for _, _, _, said in turned], dtype=pl.String),
               pl.Series(_ROW, [at for at, _, _, _ in turned], dtype=pl.UInt32),
               pl.Series(_PLACE, [0] * len(turned), dtype=pl.UInt32)]
        ).hstack(whole.select(carried))]
        # The records with a value that is none of its column's type: found again in their documents, which are
        # few, to be written down as they are.
        rows = _taken(taken, bad[_ROW].to_list())
        parts.append(pl.DataFrame(
            [bad[name] if name in filled else as_text(rows, name, bad.height) for name in texts]
            + [pl.Series("errorXMLField", self._as_written(frame[plan.field], bad), dtype=pl.String),
               pl.Series("errorCode", ["TYPE_CONVERSION"] * bad.height, dtype=pl.String),
               bad[_WHY].alias("errorMessage"), bad[_ROW], bad[_PLACE]]
        ).hstack(rows.select(carried)))
        return pl.concat(parts).sort([_ROW, _PLACE], maintain_order=True).drop([_ROW, _PLACE])

    def _as_written(self, documents: pl.Series, bad: pl.DataFrame) -> List[str]:
        """Each record that is turned away, as XML text."""
        plan = self.plan
        loop = xml_reader.path(plan.loop_query, plan.namespaces)
        parser = xml_reader.parser(plan.large_values)
        written: List[str] = []
        records: List[Any] = []
        last = None
        for at, place in bad.select(_ROW, _PLACE).iter_rows():
            if at != last:
                held = documents[at]
                records = self._records(loop, xml_reader.document(held if isinstance(held, str) else str(held), parser,
                                                                  self.strict))
                last = at
            written.append(xml_reader.as_xml(records[place], self.strict))
        return written


def _taken(frame: pl.DataFrame, places: List[int]) -> pl.DataFrame:
    """The rows of a frame at these places, each as often as it is named. A frame of no columns has no rows to take."""
    if not frame.width:
        return frame
    return frame[places] if places else frame.clear()
