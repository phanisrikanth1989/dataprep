"""Reading XML: a parser that reads nothing but the document, records found by a path, columns found from them.

The parser is set up in one place and no key of a job weakens it: it
resolves no entity, loads no DTD and asks for no other file, whatever the
document says. Rows are made when a snapshot element ends, and the snapshot
is then freed with all that stands before it, so memory follows the largest
record and not the file. The snapshot is the record, or the element above
it that a column climbs to.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Iterator, List, Mapping, Optional, Tuple

try:
    from lxml import etree
except ImportError:  # A job without XML runs on a machine without the library.
    etree = None

# XML Schema's own mark of a value that is missing.
_NIL = "{http://www.w3.org/2001/XMLSchema-instance}nil"
_NAME = r"[A-Za-z_][\w.\-]*"
_STEP = re.compile(rf"(?:({_NAME}):)?({_NAME}|\*)")
_LITERAL = re.compile(r"""('[^']*'|"[^"]*")""")
# The axes that look outside the record: what they find depends on how much of the document is in memory.
_AXES = re.compile(r"(ancestor-or-self|ancestor|preceding-sibling|preceding|following-sibling|following|parent)\s*::")
_PREFIX = re.compile(rf"(?<![:\w.\-])({_NAME}):(?!:)(?=[A-Za-z_*])")
# A run of steps up (`../..`) that starts a path, and an attribute and nothing more after one.
_CLIMB = re.compile(r"(?<![\w.\]@*])((?:\.\./)*\.\.)(?![\w.])")
_ATTRIBUTE_ALONE = re.compile(rf"/@(?:{_NAME}:)?(?:{_NAME}|\*)(?![\w.\-:/\[(])")


class Fault(Exception):
    """What is wrong with a document or with a path, in plain words."""


@dataclass(frozen=True)
class RecordPath:
    """The path that finds the records.

    Attributes:
        written: The path as the job has it.
        steps: The names from the root down, `*` for any name. A name is a
            local name; with namespaces given it is `{uri}name`.
        anywhere: Whether the first name may stand at any depth (`//name`).
        strict: Whether names are read with their namespaces.
    """

    written: str
    steps: Tuple[str, ...]
    anywhere: bool
    strict: bool


@dataclass(frozen=True)
class ColumnPath:
    """The path that finds one column's value from a record.

    Attributes:
        name: The column.
        written: The path as the job has it.
        climb: How many levels above the record have to be whole before the
            path can be answered: 0 for a path that stays in the record, or
            that reads an attribute of something above it.
        as_node: Whether the value is the node as XML text, and not its text.
        find: The compiled path.
        up: For a path that is nothing but steps up and then a path down
            (`../../customer/name`): how many steps up. Its value is the
            same for every record under one element, and is found once.
        find_from_above: For such a path: the path down, from up there.
    """

    name: str
    written: str
    climb: int
    as_node: bool
    find: Any
    up: int = 0
    find_from_above: Any = None


def needs_lxml() -> None:
    """Say so in plain words when the library that reads XML is not there."""
    if etree is None:
        raise Fault("reading XML needs the lxml package (pip install 'dataprep[v2]')")


# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------

def record_path(written: str, namespaces: Optional[Mapping[str, str]] = None) -> RecordPath:
    """Read the path that finds the records: names from the root, `*` for any name, `//` before a name anywhere.

    Raises:
        ValueError: The path is not such a path; the message says why.
    """
    text = written.strip()
    if not text:
        raise ValueError("there is no path")
    if not text.startswith("/"):
        raise ValueError(f"a record path starts at the root: write it as /{text}")
    anywhere = text.startswith("//")
    body = text[2:] if anywhere else text[1:]
    if "[" in body:
        condition = body[body.index("["):body.index("]") + 1] if "]" in body else body[body.index("["):]
        raise ValueError(
            f"holds a condition ({condition}): the records are found by names alone; turn rows away with a filter "
            "after the reader")
    if "//" in body:
        raise ValueError("holds // in its middle: only the first name of a record path may stand at any depth")
    parts = body.split("/")
    if not body or not all(parts):
        raise ValueError("names no element")
    steps = []
    for part in parts:
        match = _STEP.fullmatch(part)
        if match is None:
            raise ValueError(f"'{part}' is no element name")
        prefix, name = match.groups()
        if namespaces and prefix:
            if prefix not in namespaces:
                raise ValueError(
                    f"the prefix '{prefix}' is bound to no namespace: `namespaces` has {', '.join(sorted(namespaces))}")
            name = f"{{{namespaces[prefix]}}}{name}"
        steps.append(name)
    return RecordPath(text, tuple(steps), anywhere, bool(namespaces))


def column_path(
    name: str, written: str, as_node: bool = False, namespaces: Optional[Mapping[str, str]] = None
) -> ColumnPath:
    """Read the XPath 1.0 path that finds a column's value from its record; no path is the child of the column's name.

    Raises:
        ValueError: The path is no XPath, or its answer would depend on how
            much of the document is in memory; the message says which.
    """
    needs_lxml()
    path = written.strip() or name
    bare = _LITERAL.sub("''", path)
    if bare.startswith("/"):
        raise ValueError("starts at the root: a column is found from its record, by a path without the leading /")
    axis = _AXES.search(bare)
    if axis is not None:
        raise ValueError(
            f"uses the axis '{axis.group(1)}', whose answer would depend on how much of the document is in memory")
    climb = 0
    for run in _CLIMB.finditer(bare):
        if bare[:run.start()].rstrip().endswith("/"):
            raise ValueError("climbs (..) after going down: a path may climb only where it starts")
        if not _ATTRIBUTE_ALONE.match(bare, run.end()):
            # The start tag of an element is whole before anything in it is read, so its attributes need no
            # waiting for. Anything else up there does.
            climb = max(climb, run.group(1).count(".."))
    path, find = _compiled(path, namespaces)
    # Steps up and then a path down that holds no step up: the same value for every record under one element.
    whole = re.fullmatch(r"((?:\.\./)+)(.+)", path)
    if whole is not None and ".." not in _LITERAL.sub("''", whole.group(2)):
        return ColumnPath(name, written, climb, as_node, find, whole.group(1).count(".."),
                          etree.XPath(whole.group(2), namespaces=dict(namespaces) if namespaces else None))
    return ColumnPath(name, written, climb, as_node, find)


def path(written: str, namespaces: Optional[Mapping[str, str]] = None) -> Any:
    """Read any XPath 1.0 path, for a document that is held whole.

    Where a document is gone through a piece at a time a path is held to
    more (`record_path`, `column_path`): its answer must not depend on how
    much of the document is in memory. Here all of it is, and nothing is
    out of a path's reach.

    Raises:
        ValueError: The path is no XPath; the message says why.
    """
    needs_lxml()
    if not written.strip():
        raise ValueError("there is no path")
    return _compiled(written.strip(), namespaces)[1]


def _compiled(path: str, namespaces: Optional[Mapping[str, str]]) -> Tuple[str, Any]:
    """A path as it is asked, and compiled. Without namespaces a prefix says nothing, and is left out."""
    if not namespaces:
        # Names are matched by their local name.
        path = "".join(piece if at % 2 else _PREFIX.sub("", piece) for at, piece in enumerate(_LITERAL.split(path)))
    try:
        find = etree.XPath(path, namespaces=dict(namespaces) if namespaces else None)
        find(etree.Element("r"))
    except etree.XPathError as fault:
        raise ValueError(f"is no XPath ({_said(fault)})") from None
    return path, find


def _said(fault: BaseException) -> str:
    text = " ".join(str(fault).split())
    return text or type(fault).__name__


def not_well_formed(fault: Any) -> str:
    """What the parser says is wrong with a document, with the job's key where it names a switch of its own."""
    return str(fault.msg).replace("use XML_PARSE_HUGE option", "set `large_values` to read it")


# ------------------------------------------------------------------
# The parser
# ------------------------------------------------------------------

def settings(large_values: bool = False) -> Dict[str, Any]:
    """How every parser of v2 is set: it reads the document and nothing else."""
    return {
        # No entity is resolved, so none can name another file: one that is used is found in the tree and fails.
        "resolve_entities": False,
        # Each of these would load the DTD a document names.
        "load_dtd": False, "dtd_validation": False, "attribute_defaults": False,
        "no_network": True,
        # A document that is not well formed is no document: nothing is guessed.
        "recover": False,
        # The parser's own limits (256 levels, 10 MB a value) hold unless the job asks for large values.
        "huge_tree": large_values,
    }


@lru_cache(maxsize=None)
def _refusing() -> Any:
    """A resolver that fails whatever asks for another file, and names it."""

    class Refuses(etree.Resolver):  # type: ignore[misc]
        def resolve(self, url: str, public_id: str, context: Any) -> Any:
            raise Fault(f"the document asks for another file ({url}): v2 reads the document and nothing else")

    return Refuses()


def parser(large_values: bool = False) -> Any:
    """A parser for documents that are held whole as text, set as every parser of v2 is."""
    needs_lxml()
    # The text is text already: what a declaration in it says of an encoding is what it was once written in.
    made = etree.XMLParser(encoding="utf-8", **settings(large_values))
    made.resolvers.add(_refusing())
    return made


def document(text: str, with_parser: Any, strict: bool = False) -> Any:
    """A document held as text, parsed whole: its root element, ready to be asked.

    Args:
        text: The document.
        with_parser: A parser made by `parser`; one serves every document of a run.
        strict: Whether names are read with their namespaces.

    Raises:
        Fault: The document uses an entity it declares, or asks for another file.
        lxml.etree.XMLSyntaxError: The document is not well formed.
    """
    root = etree.fromstring(text.encode("utf-8"), with_parser)
    prepared(root, strict)
    return root


def prepared(snapshot: Any, strict: bool, spaced: bool = True) -> None:
    """Make an element ready to be asked: no entity in it, and its names local unless namespaces are given.

    Args:
        snapshot: The element, with all that is in it.
        strict: Whether names are read with their namespaces.
        spaced: Whether a name in it may be in a namespace at all.
    """
    for entity in snapshot.iter(etree.Entity):
        raise Fault(
            f"the document uses the entity '{entity.text}' (near line {entity.sourceline}): v2 reads no entity a "
            "document declares, since one may name another file")
    if spaced and not strict:
        for element in snapshot.iter("{*}*"):
            if element.tag[0] == "{":
                element.tag = element.tag.rpartition("}")[2]
            for key in [key for key in element.attrib if key[0] == "{"]:
                local = key.rpartition("}")[2]
                if key == _NIL:
                    # Kept under its own name as well: it says the value is missing.
                    continue
                if local not in element.attrib:
                    element.set(local, element.attrib.pop(key))


def value(found: Any, as_node: bool, strict: bool) -> Tuple[Optional[str], bool]:
    """What a path found, as a column's value, and whether it found more than one node; the first is the value."""
    several = False
    if isinstance(found, list):
        if not found:
            return None, False
        several = len(found) > 1
        found = found[0]
    return _value(found, as_node, strict), several


def _says_its_encoding(head: bytes) -> bool:
    """Whether a document says how it is written: by a byte order mark, or in its declaration."""
    if head.startswith((b"\xef\xbb\xbf", b"\xff\xfe", b"\xfe\xff", b"\x00\x00\xfe\xff")):
        return True
    if head.startswith((b"<\x00?\x00", b"\x00<\x00?", b"<\x00\x00\x00", b"\x00\x00\x00<")):
        # UTF-16 or UTF-32 with no mark: the parser tells by these bytes.
        return True
    return re.match(rb"\s*<\?xml[^>]*\bencoding\s*=", head) is not None


# ------------------------------------------------------------------
# Records
# ------------------------------------------------------------------

class Several:
    """The records of several kinds in one document, gone through once.

    For each record, in the order they are whole: its kind, the line its
    start tag is on, and its values as text. A record is whole when it
    ends, or when the element above it that a column climbs to does. What
    has been read is let go of, unless it stands in an element that
    another kind still has to read.

    Args:
        source: The document, open for reading bytes.
        kinds: For each kind of record: the path that finds its records,
            and the paths that find its values, in the order of the values.
        encoding: How the document is written when it does not say so itself.
        large_values: Whether a value may be larger than 10 MB and the
            document deeper than 256 levels.
        limit: The most records to read, of all kinds; None for all.

    Attributes:
        many: For each kind and each of its columns whose path found more
            than one node in a record: in how many records, and the number
            of the first. The first node is the value.

    Raises:
        Fault: While it is gone through: the document uses an entity, or a
            column climbs above the document.
        lxml.etree.XMLSyntaxError: While it is gone through: the document
            is not well formed.
    """

    def __init__(
        self,
        source: Any,
        kinds: List[Tuple[RecordPath, List[ColumnPath]]],
        encoding: Optional[str] = None,
        large_values: bool = False,
        limit: Optional[int] = None,
    ) -> None:
        needs_lxml()
        self.source, self.kinds = source, kinds
        self.encoding, self.large_values, self.limit = encoding, large_values, limit
        self.many: Dict[Tuple[int, str], Tuple[int, int]] = {}
        self._made = 0
        # For each column that only climbs and goes down: the element it last climbed to, and what it found there.
        self._above: List[List[Tuple[Any, Any]]] = [[(None, None)] * len(columns) for _, columns in kinds]

    def __iter__(self) -> Iterator[Tuple[int, int, List[Optional[str]]]]:
        # For each kind: its record path, how far its columns climb, and its snapshot: what has to be whole
        # before its rows are made.
        read: List[Tuple[RecordPath, int, Tuple[str, ...]]] = []
        tags = set()
        for record, columns in self.kinds:
            steps = record.steps
            climb = max((column.climb for column in columns), default=0)
            if climb:
                highest = max(columns, key=lambda column: column.climb)
                if record.anywhere:
                    raise Fault(
                        f"the column '{highest.name}' climbs above its record, and '{record.written}' may be at any "
                        "depth: with //, a column reads its record and the attributes of what is above it")
                if climb >= len(steps):
                    raise Fault(
                        f"the column '{highest.name}' climbs {climb} levels above its record, and '{record.written}' is "
                        f"{len(steps)} deep")
            above = steps[:len(steps) - climb]
            read.append((record, climb, above))
            tags |= {_tag(steps[-1], record.strict), _tag(above[-1], record.strict)}
        if self.limit == 0 or not read:
            return
        strict = read[0][0].strict
        # Whether what one kind waits for may stand in what another does: only then is it asked, before an
        # element is let go of, whether something above it is still to be read.
        snapshots = [(above, record.anywhere) for record, _, above in read]
        nested = any(_may_hold(outer, inner) for outer in snapshots for inner in snapshots)
        head = self.source.read(256)
        self.source.seek(0)
        walker = etree.iterparse(
            self.source, events=("start-ns", "end"), tag=sorted(tags),
            encoding=None if _says_its_encoding(head) else self.encoding, **settings(self.large_values),
        )
        walker.resolvers.add(_refusing())
        spaced = False
        waiting: List[List[Any]] = [[] for _ in read]
        for event, node in walker:
            if event == "start-ns":
                # From here on a name may be in a namespace.
                spaced = True
                continue
            done = False
            for kind, (record, climb, above) in enumerate(read):
                if _is_at(node, record.steps, record.anywhere, strict):
                    if climb:
                        waiting[kind].append(node)
                        continue
                    prepared(node, strict, spaced)
                    yield self._row(kind, node)
                    done = True
                    if self._made == self.limit:
                        return
                elif climb and _is_at(node, above, False, strict):
                    prepared(node, strict, spaced)
                    for held in waiting[kind]:
                        yield self._row(kind, held)
                        if self._made == self.limit:
                            return
                    waiting[kind].clear()
                    done = True
            # What stands in an element that is still to be read stays until that one has been read too.
            if done and not (nested and _held_above(node, snapshots, strict)):
                _free(node)

    def _row(self, kind: int, node: Any) -> Tuple[int, int, List[Optional[str]]]:
        self._made += 1
        values: List[Optional[str]] = []
        record, columns = self.kinds[kind]
        strict, above = record.strict, self._above[kind]
        for at, column in enumerate(columns):
            if column.up:
                # Found once for all the records under the element it climbs to.
                top = node
                for _ in range(column.up):
                    top = top.getparent()
                if above[at][0] is not top:
                    above[at] = (top, value(column.find_from_above(top), column.as_node, strict))
                found, several = above[at][1]
            else:
                found, several = value(column.find(node), column.as_node, strict)
            if several:
                records, first = self.many.get((kind, column.name), (0, self._made))
                self.many[(kind, column.name)] = (records + 1, first)
            values.append(found)
        return kind, node.sourceline, values


class Records:
    """The records of a document, one after another: for each, the line its start tag is on and its values as text.

    One kind of record: see `Several`, which this is the case of one of.

    Args:
        source: The document, open for reading bytes.
        record: The path that finds the records.
        columns: The paths that find the values, in the order of the values.
        encoding: How the document is written when it does not say so itself.
        large_values: Whether a value may be larger than 10 MB and the
            document deeper than 256 levels.
        limit: The most records to read; None for all.

    Attributes:
        many: For each column whose path found more than one node in a
            record: in how many records, and the number of the first. The
            first node is the value.

    Raises:
        Fault: While it is gone through: the document uses an entity, or a
            column climbs above the document.
        lxml.etree.XMLSyntaxError: While it is gone through: the document
            is not well formed.
    """

    def __init__(
        self,
        source: Any,
        record: RecordPath,
        columns: List[ColumnPath],
        encoding: Optional[str] = None,
        large_values: bool = False,
        limit: Optional[int] = None,
        namespaces: Optional[Mapping[str, str]] = None,
    ) -> None:
        self._all = Several(source, [(record, columns)], encoding, large_values, limit)

    @property
    def many(self) -> Dict[str, Tuple[int, int]]:
        return {name: told for (_, name), told in self._all.many.items()}

    def __iter__(self) -> Iterator[Tuple[int, List[Optional[str]]]]:
        for _, line, values in self._all:
            yield line, values


def _may_hold(outer: Tuple[Tuple[str, ...], bool], inner: Tuple[Tuple[str, ...], bool]) -> bool:
    """Whether an element at one path may stand in an element at another."""
    (above, above_anywhere), (below, below_anywhere) = outer, inner
    if above_anywhere or below_anywhere:
        return True
    return len(above) < len(below) and all("*" in (one, other) or one == other for one, other in zip(above, below))


def _held_above(node: Any, snapshots: List[Tuple[Tuple[str, ...], bool]], strict: bool) -> bool:
    """Whether an element stands in one that some kind of record still waits for."""
    return any(_is_at(above, steps, anywhere, strict) for above in node.iterancestors() for steps, anywhere in snapshots)


def _tag(step: str, strict: bool) -> str:
    """A step of a record path as the parser is asked for it."""
    if step == "*":
        return "{*}*"
    return step if strict else "{*}" + step


def _is_at(node: Any, steps: Tuple[str, ...], anywhere: bool, strict: bool) -> bool:
    """Whether an element stands where a path says: its name and the names above it, up to the root."""
    for step in reversed(steps):
        if node is None:
            return False
        if step != "*" and (node.tag if strict else node.tag.rpartition("}")[2]) != step:
            return False
        node = node.getparent()
    return anywhere or node is None


def _free(element: Any) -> None:
    """Let go of an element that has been read, and of all that stands before it at every level above."""
    element.clear()
    parent = element.getparent()
    while parent is not None:
        while element.getprevious() is not None:
            del parent[0]
        element, parent = parent, parent.getparent()


@lru_cache(maxsize=None)
def _text_of() -> Any:
    return etree.XPath("string()")


def _value(found: Any, as_node: bool, strict: bool) -> Optional[str]:
    """What a path found, as text: an element's text, an attribute, a number as XPath writes it."""
    if isinstance(found, bool):
        return "true" if found else "false"
    if isinstance(found, float):
        return _number(found)
    if isinstance(found, str):
        return str(found)
    if as_node:
        return as_xml(found, strict)
    if len(found) == 0 and isinstance(found.tag, str):
        # An element with nothing in it but text: that text is its value, with no second path asked.
        if found.attrib and found.get(_NIL) == "true":
            return None
        return found.text or ""
    if found.get(_NIL) == "true":
        return None
    return str(_text_of()(found))


def _number(value: float) -> str:
    """A number as XPath writes it: a whole one without a point."""
    if value != value:
        return "NaN"
    if value in (float("inf"), float("-inf")):
        return "Infinity" if value > 0 else "-Infinity"
    return str(int(value)) if value == int(value) and abs(value) < 1e15 else repr(value)


def as_xml(node: Any, strict: bool) -> str:
    """A node as XML text. Where names are local, it carries no namespace declaration it has no use for."""
    if not strict:
        node = copy.deepcopy(node)
        etree.cleanup_namespaces(node)
    return etree.tostring(node, encoding="unicode", with_tail=False)
