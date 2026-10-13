"""Advanced XML output: rows written into a document whose shape is a tree of root, group and loop elements."""
from __future__ import annotations

import itertools
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import polars as pl

from ... import xml_reader, xml_writer
from ...errors import ConfigurationError
from ...files import encoded, put_in_place, to_encoding
from ...job.keys import Key, Kind
from ..base import Sink, Write
from ..registry import REGISTRY
from .file_input_delimited import encoding
from .file_output_delimited import _as_written

logger = logging.getLogger(__name__)

_TABLES = ("root", "group", "loop")
_NOT_READ = "v2 writes as it goes, a row a line."
# A piece of a line: a text that is the same for every row, or an expression over the row.
_Piece = Union[str, pl.Expr]

_ROW = (
    Key("path", default="", doc="An element's full path (`/root/group/loop/child`), or the name of an attribute or the "
                                "prefix of a namespace."),
    Key("column", default="", doc="The column whose value it holds."),
    Key("value", type=object, default="", doc="A fixed value, written where no column is named; for a namespace, what "
                                              "the prefix stands for."),
    Key("attribute", type=object, default="branch",
        doc="What the row is: `main` for the element its table is about, `branch` for any other element, `attri` for "
            "an attribute and `ns` for a namespace of the element before it."),
    Key("order", type=object, default="", doc="Its place among the elements beside it."),
)


@dataclass(eq=False)
class _Node:
    """An element of the document, or an attribute of one.

    Attributes:
        name: Its name in the document, with its prefix when it has one.
        path: Its full path, by which the elements in it find it.
        table: The table whose element it is (`root`, `group`, `loop`), for
            the element a table is about; empty for any other.
        column: The column whose value it holds, when it holds one.
        value: Its fixed value.
        order: Its place among the elements beside it.
        where: The row of the job config it was read from, for a message.
    """

    name: str
    path: str
    table: str
    column: str
    value: str
    order: int
    where: str
    parent: Optional["_Node"] = None
    attributes: List["_Node"] = field(default_factory=list)
    namespaces: List[Tuple[str, str]] = field(default_factory=list)
    children: List["_Node"] = field(default_factory=list)

    def above(self) -> List["_Node"]:
        """The elements it stands in, the root first."""
        return [] if self.parent is None else self.parent.above() + [self.parent]

    def below(self, but: Optional["_Node"] = None) -> List["_Node"]:
        """Itself, its attributes, and the same of every element in it; one element in it may be left out."""
        found = [self] + self.attributes
        for child in self.children:
            if child is not but:
                found += child.below()
        return found


def _what(value: Any) -> str:
    """What a row is: Talend's four words, and the two a job made by hand has for them."""
    text = str(value).strip().lower()
    if text in ("attri", "true"):
        return "attri"
    return text if text in ("ns", "main") else "branch"


def _tree(config: Dict[str, Any]) -> Tuple[Optional[_Node], Optional[_Node], List[str]]:
    """Build the document's tree from the three tables.

    The tables are gone through in order, as Talend goes through them. An
    element stands in the element its path names, the last one written
    with that path; a row that is an attribute or a namespace belongs to
    the element before it. A bare name, as a job made by hand has it,
    stands in the element its table is about, and that one in the element
    the table before is about.

    Returns:
        The root, the loop element, and what is wrong with the tables.
    """
    problems = [f"{table}: names no element: {why}" for table, why in (
        ("root", "a document has one root element"), ("loop", "the loop element is the one written for each row"))
        if not any(_what(row["attribute"]) in ("main", "branch") for row in config[table])]
    if problems:
        return None, None, problems
    root: Optional[_Node] = None
    loop: Optional[_Node] = None
    main: Optional[_Node] = None
    by_path: Dict[str, _Node] = {}
    count = 0
    for table in _TABLES:
        rows = config[table]
        says_main = any(_what(row["attribute"]) == "main" for row in rows)
        of_table: Optional[_Node] = None
        last = main
        for at, row in enumerate(rows):
            count += 1
            where, what, path = f"{table}[{at}]", _what(row["attribute"]), row["path"].strip()
            given = str(row["order"]).strip()
            order = count
            if given:
                try:
                    order = int(given)
                except ValueError:
                    problems.append(f"{where}.order: {given!r} is no place among elements: give a whole number")
            value = str(row["value"])
            if what in ("attri", "ns"):
                if last is None:
                    kind = "attribute" if what == "attri" else "namespace"
                    problems.append(f"{where}.path: the {kind} '{path}' stands before any element it could belong to")
                elif what == "attri":
                    last.attributes.append(_Node(path, path, "", row["column"], value, order, where, last))
                elif row["column"]:
                    problems.append(f"{where}.column: a namespace is what its `value` says, the same for every row: it "
                                    "cannot come from a column")
                elif path and (not xml_writer.is_name(path) or path.lower().startswith("xml")):
                    problems.append(f"{where}.path: {path!r} is no prefix a namespace may have")
                elif value:
                    last.namespaces.append((path, value))
                continue
            if root is None:
                parent, name = None, path.rsplit("/", 1)[-1]
                full = path if "/" in path else "/" + path
            elif "/" in path:
                parent_path, name = path.rsplit("/", 1)
                full = path
                if not parent_path:
                    problems.append(f"{where}.path: '{path}' is a second root, and a document has one")
                    continue
                parent = by_path.get(parent_path)
                if parent is None:
                    problems.append(f"{where}.path: '{path}' stands in '{parent_path}', and no element before it has "
                                    "that path")
                    continue
            else:
                # The element the table is about, or the one the table before is about until this one has its own.
                parent = main
                name, full = path, f"{parent.path}/{path}"  # type: ignore[union-attr]
            is_main = what == "main" or (not says_main and of_table is None)
            if is_main and table == "loop" and loop is not None:
                problems.append(f"{where}.path: '{path}' is a second loop element, and the rows are written as one")
                continue
            node = _Node(name, full, table if is_main else "", row["column"], value, order, where, parent)
            by_path[full] = last = node
            if parent is None:
                root = main = node
            else:
                parent.children.append(node)
            if is_main:
                of_table = main = node
                if table == "loop":
                    loop = node
    return root, loop, problems


def _joined(pieces: List[_Piece]) -> pl.Expr:
    """Pieces one after another as one text, the fixed texts that touch joined before any row is read."""
    merged: List[_Piece] = []
    for piece in pieces:
        if isinstance(piece, str) and merged and isinstance(merged[-1], str):
            merged[-1] += piece
        else:
            merged.append(piece)
    texts = [pl.lit(piece) if isinstance(piece, str) else piece for piece in merged]
    return texts[0] if len(texts) == 1 else pl.concat_str(texts)


def _in_order(nodes: List[_Node]) -> List[_Node]:
    """Elements beside each other by their `order`, and as written where two have the same."""
    return sorted(nodes, key=lambda node: node.order)


def _twice(names: List[str]) -> List[str]:
    """The names a list holds more than once, each once."""
    return sorted({name for name in names if names.count(name) > 1})


@REGISTRY.register
class AdvancedFileOutputXML(Sink):
    """Write the rows into a document whose shape the job draws as a tree.

    Three tables draw it: `root`, the elements that are written once;
    `group`, an element for each run of rows that share its values; and
    `loop`, the element written for each row, with what is in it. A row
    of a table is an element, by its full path, or an attribute or a
    namespace of the element before it. It holds a `column`'s value, or a
    fixed `value` where it names no column.

    A group's element is opened where a value it holds, or one of a group
    around it, is not the row before's, and closed where the row after
    opens one: the rows of a group have to arrive together. What stands
    before the rows in the document has the values of the first row, what
    stands after them those of the last.

    Each row is one line. Whatever a value holds is read back as it was, a
    character the `encoding` lacks is written by its number, one XML
    cannot hold fails the job, and the file is read once before it is put
    in place, as for the XML file output.
    """

    names = ("advanced_file_output_xml", "AdvancedFileOutputXML", "tAdvancedFileOutputXML")
    keys = (
        Key("path", default="", aliases=("filename", "filepath"), doc="The file to write."),
        Key("root", type=list, default=[], items=_ROW, doc="The elements written once: the root, and what is in it."),
        Key("group", type=list, default=[], items=_ROW, doc="The elements written once for each group of rows."),
        Key("loop", type=list, default=[], items=_ROW, doc="The element written for each row, and what is in it."),
        Key("encoding", default="ISO-8859-15", convert=encoding, doc="The encoding of the file, which its declaration names."),
        Key("create", type=bool, default=True, doc="Whether the folder of the file is made when it is not there."),
        Key("create_empty_element", type=bool, default=True,
            doc="Whether an element with nothing to say is written: one where no column in it holds a value and "
                "nothing in it has a fixed value. The loop element and the elements it stands in always are."),
        Key("add_empty_attribute", type=bool, default=False, doc="Whether an attribute whose column holds no value is written, empty."),
        Key("add_unmapped_attribute", type=bool, default=False,
            doc="Whether an attribute with no column and no fixed value is written, empty."),
        Key("trim", type=bool, default=False, doc="Whether white space around a column's value goes."),
        Key("delete_empty_file", type=bool, default=False, doc="Whether no file is left when no row arrives."),
        Key("file_valid", type=bool, default=False,
            doc="Talend's \"Include DTD or XSL\": whether a line naming one follows the declaration. Nothing is validated."),
        Key("dtd_valid", type=bool, default=True, doc="With `file_valid`: whether the line names a DTD."),
        Key("dtd_name", default="Root", doc="The root element the DTD line names."),
        Key("dtd_systemid", default="Talend.dtd", doc="The file the DTD line names."),
        Key("xsl_valid", type=bool, default=False, doc="With `file_valid` and no DTD: whether the line names a stylesheet."),
        Key("xsl_type", default="text/xsl", doc="The type the stylesheet line gives."),
        Key("xsl_href", default="Talend.xsl", doc="The file the stylesheet line names."),
        Key("merge", kind=Kind.REFUSED, type=bool,
            reason="v2 writes a file whole and beside its place; it does not add to a document that is there"),
        Key("output_as_xsd", kind=Kind.REFUSED, type=bool, reason="v2 writes no XSD"),
        Key("usestream", kind=Kind.REFUSED, type=bool, reason="v2 writes files, not streams a job holds"),
        Key("add_document_as_node", kind=Kind.REFUSED, type=bool,
            reason="a column that holds a document is written as text; v2 does not put it in as elements"),
        Key("split", kind=Kind.REFUSED, type=bool, reason="v2 writes one file: split the rows before the output"),
        Key("advanced_separator", kind=Kind.REFUSED, type=bool,
            reason="v2 writes a number one way: write it as text of the form wanted before the output"),
        Key("split_every", kind=Kind.IGNORED, type=object, doc="Only read with `split`."),
        Key("thousands_separator", kind=Kind.IGNORED, type=object, doc="Only read with `advanced_separator`."),
        Key("decimal_separator", kind=Kind.IGNORED, type=object, doc="Only read with `advanced_separator`."),
        Key("streamname", kind=Kind.IGNORED, type=object, doc="Only read with `usestream`."),
        Key("map", kind=Kind.IGNORED, type=object, doc="Talend's editor of the tree; the tables hold what it drew."),
        Key("pretty_compact", kind=Kind.IGNORED, type=object, doc=_NOT_READ),
        Key("generation_mode", kind=Kind.IGNORED, type=object, doc=_NOT_READ),
        Key("die_on_error", kind=Kind.IGNORED, type=object, doc="What cannot be written fails the job; v1 reads it on every component."),
    )

    # ------------------------------------------------------------------
    # What is wrong with the tree
    # ------------------------------------------------------------------

    def problems(self) -> List[str]:
        config = self.config
        found = [] if config["path"] else ["path: the file to write has no name"]
        root, loop, wrong = _tree(config)
        found += wrong
        if config["file_valid"] and config["dtd_valid"] and not xml_writer.is_name(config["dtd_name"]):
            found.append(f"dtd_name: {config['dtd_name']!r} is no name an element may have")
        if root is None or loop is None or wrong:
            return found
        declared = [column.name for column in self.input_schema]
        for node in root.below():
            is_attribute = node.parent is not None and node in node.parent.attributes
            kind = "an attribute" if is_attribute else "an element"
            prefix, _, local = node.name.rpartition(":")
            if not xml_writer.is_name(local) or (prefix and not xml_writer.is_name(prefix)):
                found.append(f"{node.where}.path: {node.name!r} is no name {kind} may have")
            elif prefix and prefix != "xml" and not any(
                    prefix == given for holder in node.above() + [node] for given, _ in holder.namespaces):
                found.append(f"{node.where}.path: the prefix of '{node.name}' is declared on no element at or above it: "
                             "declare it with a row whose `attribute` is `ns`")
            if node.column and declared and node.column not in declared:
                found.append(f"{node.where}.column: there is no column '{node.column}'; the columns are: {', '.join(declared)}")
            if node.table == "group" and node not in loop.above():
                found.append(f"{node.where}.path: the group '{node.path}' does not stand above the loop element "
                             f"'{loop.path}'")
            for twice in _twice([attribute.name for attribute in node.attributes]):
                found.append(f"{node.where}.path: the attribute '{twice}' is given twice for '{node.name}'")
            for twice in _twice([prefix for prefix, _ in node.namespaces]):
                found.append(f"{node.where}.path: the namespace '{twice}' is given twice for '{node.name}'")
        return found

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def write(self, frame: pl.LazyFrame) -> Write:
        config = self.config
        path = config["path"]
        folder = os.path.dirname(path)
        if folder and config["create"]:
            os.makedirs(folder, exist_ok=True)
        if folder and not os.path.isdir(folder):
            raise ConfigurationError(f"Failed to write file '{path}': folder '{folder}' does not exist")
        root, loop, _ = _tree(config)
        assert root is not None and loop is not None, "the job was loaded, so the tables draw a tree"
        types = frame.collect_schema()
        for node in root.below():
            if node.column and node.column not in types:
                raise ConfigurationError(f"{node.where}.column: there is no column '{node.column}'; the columns are: "
                                         f"{', '.join(types.names())}")
        declared = {column.name: column for column in self.input_schema}

        def as_text(name: str) -> pl.Expr:
            text = _as_written(name, types[name], declared.get(name)).cast(pl.String)
            return text.str.strip_chars() if config["trim"] else text

        drawn = _Drawn(config, as_text)
        # The loop element stands in these, the root first; each with the next one, which it is written around.
        around = list(zip(loop.above(), loop.above()[1:] + [loop]))
        body = frame.select(drawn.line(around, loop, types.names()[0]).alias("line"))
        used = sorted({node.column for node in root.below() if node.column})
        xml_writer.fail_on_what_xml_cannot_hold(self, frame, [name for name in used if types[name] == pl.String])
        head = [xml_writer.declaration(config["encoding"])]
        if config["file_valid"] and config["dtd_valid"]:
            head.append(f'<!DOCTYPE {config["dtd_name"]} SYSTEM "{xml_writer.quoted(config["dtd_systemid"])}">')
        elif config["file_valid"] and config["xsl_valid"]:
            head.append(f'<?xml-stylesheet type="{xml_writer.quoted(config["xsl_type"])}" '
                        f'href="{xml_writer.quoted(config["xsl_href"])}"?>')
        document_lines = xml_writer.lines([pl.LazyFrame({"line": head}, schema={"line": pl.String}), body])

        def sink(written: str) -> pl.LazyFrame:
            return document_lines.sink_csv(written, include_header=False, line_terminator="\n", quote_style="never", lazy=True)

        def ready(written: str, rows: int) -> None:
            if not rows and config["delete_empty_file"]:
                return
            if not rows:
                # No row opened the root: it is written here, with what stands in it up to the first group, and
                # with nothing for a column's value.
                once = list(itertools.takewhile(lambda pair: pair[0].table != "group", around))
                nothing = pl.DataFrame({name: [None] for name in types.names()}, schema=dict(types))
                texts = nothing.select(
                    [_joined(drawn.before(node, then)).alias(f"before {at}") for at, (node, then) in enumerate(once)]
                    + [_joined(drawn.after(node, then)).alias(f"after {at}") for at, (node, then) in enumerate(once)]).row(0)
                lines = texts[:len(once)] + texts[len(once):][::-1]
                with open(written, "ab") as handle:
                    handle.write(encoded("".join(line + "\n" for line in lines), "UTF-8"))
            to_encoding(written, config["encoding"], by_number=True)
            try:
                xml_writer.read_back(written, path)
            except xml_reader.Fault as exc:
                raise ConfigurationError(str(exc)) from None

        def place(written: str, rows: int) -> None:
            if not rows and config["delete_empty_file"]:
                os.remove(written)
                if os.path.exists(path):
                    # No file of an earlier run is left to be taken for this one's.
                    os.remove(path)
                return
            put_in_place(written, path)
            self.global_map[f"{self.id}_FILE_NAME"] = path

        return Write(path=path, sink=sink, ready=ready, place=place, empty_leaves_none=config["delete_empty_file"])


class _Drawn:
    """The text of the tree's elements, as the pieces of a line."""

    def __init__(self, config: Dict[str, Any], as_text: Callable[[str], pl.Expr]) -> None:
        self.config, self.as_text = config, as_text

    def start(self, node: _Node) -> List[_Piece]:
        """An element's start tag, with its namespaces and its attributes."""
        pieces: List[_Piece] = [f"<{node.name}"]
        pieces += [f' xmlns{":" + prefix if prefix else ""}="{xml_writer.quoted(uri)}"' for prefix, uri in node.namespaces]
        for attribute in node.attributes:
            name = attribute.name
            if attribute.column:
                value = self.as_text(attribute.column)
                nothing = f' {name}=""' if self.config["add_empty_attribute"] else ""
                pieces.append(pl.when(value.is_null()).then(pl.lit(nothing)).otherwise(
                    pl.concat_str([pl.lit(f' {name}="'), xml_writer.attribute(value), pl.lit('"')])))
            elif attribute.value:
                pieces.append(f' {name}="{xml_writer.quoted(attribute.value)}"')
            elif self.config["add_unmapped_attribute"]:
                pieces.append(f' {name}=""')
        return pieces + [">"]

    def text(self, node: _Node) -> List[_Piece]:
        """What an element holds itself: its column's value, or its fixed value where it names no column."""
        if node.column:
            return [xml_writer.text(self.as_text(node.column)).fill_null("")]
        return [xml_writer.plain(node.value)]

    def says(self, node: _Node) -> Optional[pl.Expr]:
        """Whether an element has something to say in a row; None when it always has.

        It has where a column it holds, or one that an attribute of it or
        an element in it holds, has a value; and always where something in
        it is fixed: a value, or a namespace.
        """
        held = node.below()
        if any(part.namespaces or (part.value and not part.column) for part in held):
            return None
        columns = sorted({part.column for part in held if part.column})
        return pl.any_horizontal([self.as_text(name).is_not_null() for name in columns]) if columns else pl.lit(False)

    def element(self, node: _Node, always: bool = False) -> List[_Piece]:
        """An element with all that is in it. One with nothing to say is left out where the job says so."""
        pieces = self.start(node) + self.text(node)
        for child in _in_order(node.children):
            pieces += self.element(child)
        pieces.append(f"</{node.name}>")
        says = None if always or self.config["create_empty_element"] else self.says(node)
        return pieces if says is None else [pl.when(says).then(_joined(pieces)).otherwise(pl.lit(""))]

    def before(self, node: _Node, then: _Node) -> List[_Piece]:
        """What an element the loop stands in writes before the next such one: its start, its text, what stands before."""
        beside = _in_order(node.children)
        pieces = self.start(node) + self.text(node)
        for child in beside[:beside.index(then)]:
            pieces += self.element(child)
        return pieces

    def after(self, node: _Node, then: _Node) -> List[_Piece]:
        """And what it writes after: what stands after the next one, and its end."""
        beside = _in_order(node.children)
        pieces: List[_Piece] = []
        for child in beside[beside.index(then) + 1:]:
            pieces += self.element(child)
        return pieces + [f"</{node.name}>"]

    def line(self, around: List[Tuple[_Node, _Node]], loop: _Node, some_column: str) -> pl.Expr:
        """The line of a row: the loop element, with what opens before it and what closes after it."""
        # The first row: nothing stands before it.
        first = pl.col(some_column).is_null().shift(1).is_null()
        opens: List[_Piece] = []
        closes: List[_Piece] = []
        starts = first
        keys: Set[str] = set()
        for node, then in around:
            if node.table == "group":
                # A group starts anew where a value it holds, or one of a group around it, is not the row before's.
                keys |= {held.column for held in node.below(but=then) if held.column}
                changed = [self.as_text(name).ne_missing(self.as_text(name).shift(1)) for name in sorted(keys)]
                starts = first | pl.any_horizontal(changed) if changed else first
            opens.append(pl.when(starts).then(_joined(self.before(node, then) + ["\n"])).otherwise(pl.lit("")))
            # And ends where the row after starts one, or there is no row after.
            ends = starts.shift(-1).fill_null(True)
            closes.insert(0, pl.when(ends).then(_joined(["\n"] + self.after(node, then))).otherwise(pl.lit("")))
        return _joined(opens + self.element(loop, always=True) + closes)
