"""XML map: a document a column holds taken apart into rows, or the columns of a row handed on under other names."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from ... import xml_reader
from ...column_types import polars_schema
from ...errors import ConfigurationError
from ...job.columns import COLUMN_KEYS, column_of
from ...job.keys import Key, Kind
from ...job.model import TYPE_NAMES, Column
from ...rows import hidden, visible
from ..base import Transform
from ..file.file_input_xml import namespaces
from ..registry import REGISTRY
from .extract_xml_field import Extraction, Plan

logger = logging.getLogger(__name__)

# A place in a document, as Talend writes one: `[row1.doc:/order/line/sku]`. And a column of the row: `row1.note`.
_PLACE = re.compile(r"\[\s*([A-Za-z_]\w*)\.([A-Za-z_]\w*)\s*:(.*)\]", re.DOTALL)
_COLUMN = re.compile(r"([A-Za-z_]\w*)\.([A-Za-z_]\w*)")
_NOT_READ = "The trees say what the map does; this is the converter's reading of them, which v2 does not go by."


@dataclass
class _Mapped:
    """What the trees say the map does.

    Attributes:
        columns: The columns handed on.
        document: The column that holds the document; None when the rows
            are handed on as they arrive.
        loop: The path, from the root of the document, of the element that
            gives a row.
        places: For each column read from the document: its path from the
            loop element.
        handed: For each column handed on from the row: that column of the row.
    """

    columns: List[Column]
    document: Optional[str]
    loop: str
    places: Dict[str, str]
    handed: Dict[str, str]


def _listed(value: Any) -> List[Dict[str, Any]]:
    return [one for one in value if isinstance(one, dict)] if isinstance(value, list) else []


def _local(step: str) -> str:
    """The name of an element in a path, without its prefix: names are matched by their local name."""
    return step.rpartition(":")[2]


def _from_the_loop(loop: str, place: str) -> str:
    """A place written from the root of the document, as the path that leads to it from the loop element."""
    here, there = loop.strip("/").split("/"), place.strip("/").split("/")
    shared = 0
    while shared < min(len(here), len(there)) and _local(here[shared]) == _local(there[shared]):
        shared += 1
    steps = [".."] * (len(here) - shared) + there[shared:]
    return "/".join(steps) or "."


@REGISTRY.register
class XMLMap(Transform):
    """Take the XML document a column holds apart into rows, as the trees of a Talend XML map say.

    `input_trees` is the tree of the rows that arrive: their columns, one
    of which may hold a document, drawn with its elements and attributes
    and one element marked as the loop element. Each loop element of a
    row's document gives a row. `output_trees` is the tree of the rows
    handed on: each column has an expression that is a place in the
    document (`[row1.doc:/order/line/sku]`), a column of the row
    (`row1.note`), or nothing. A place is read from where the loop
    element stands, so one outside it (`/order/@id`) is the same for
    every row of a document. A value is what extract XML field makes of
    it, and names are matched by their local name.

    With no document in the tree, the columns of a row are handed on
    under the names of the output, and nothing is held in memory.

    A converted job cannot say more than this rightly. What it has more
    refuses the job with its reason: a lookup, a second output, a filter,
    a document to build, and an expression that is more than a place or
    a column.
    """

    names = ("xml_map", "XMLMap", "tXMLMap")
    max_inputs = None
    may_need_rows = True
    keys = (
        Key("input_trees", type=list, default=[], doc="The tree of the rows that arrive, as Talend's editor drew it."),
        Key("output_trees", type=list, default=[], doc="The tree of the rows handed on, each column with its expression."),
        Key("output_schema", type=list, default=[], items=COLUMN_KEYS,
            doc="The columns handed on, where the component declares none."),
        Key("die_on_error", type=bool, default=True,
            doc="Whether a document that cannot be read, or a value that is none of its column's type, fails the job; "
                "when off, the row is dropped with a warning."),
        Key("namespaces", type=dict, default={}, convert=namespaces,
            doc="Prefixes and the namespaces they stand for. With it, a place is read as XPath says."),
        Key("large_values", type=bool, default=False,
            doc="Whether a value may be larger than 10 MB and a document deeper than 256 levels."),
        Key("activate_expression_filter", kind=Kind.REFUSED, type=bool,
            reason="a filter is not read here: filter the rows with a step after this one"),
        Key("expression_filter", kind=Kind.IGNORED, type=object, doc="Only read with `activate_expression_filter`."),
        Key("expressions", kind=Kind.IGNORED, type=object, doc=_NOT_READ),
        Key("looping_element", kind=Kind.IGNORED, type=object, doc=_NOT_READ),
        Key("connections", kind=Kind.IGNORED, type=object, doc="The lines of Talend's editor; the expressions say the same."),
        Key("var_tables", kind=Kind.IGNORED, type=object, doc="The converter writes the name of the table only."),
        Key("keep_order_for_document", kind=Kind.IGNORED, type=object, doc="The rows keep the order of the documents."),
    )

    # ------------------------------------------------------------------
    # What the trees say
    # ------------------------------------------------------------------

    def _mapped(self) -> Tuple[Optional[_Mapped], List[str]]:
        """What the trees say the map does, and what in them v2 will not run with."""
        config = self.config
        arriving, leaving = _listed(config["input_trees"]), _listed(config["output_trees"])
        if not arriving:
            return None, ["input_trees: names no input: the tree of the rows that arrive"]
        if not leaving:
            return None, ["output_trees: names no output: the tree of the rows that are handed on"]
        wrong: List[str] = []
        lookups = set()
        for at, tree in enumerate(arriving[1:], start=1):
            lookups.add(str(tree.get("name", "")))
            wrong.append(f"input_trees[{at}]: '{tree.get('name', '')}' is a lookup. A lookup has to say whether a row with "
                         "no match is kept, and a converted job does not say it: join with a map before this step")
        if not lookups and self.fed > 1:
            wrong.append(f"inputs: {self.fed} flows arrive, and the trees draw one: a map takes its rows from one flow")
        main, nodes = str(arriving[0].get("name", "")), _listed(arriving[0].get("nodes"))
        names = [str(node.get("name", "")) for node in nodes]
        documents = [(at, node) for at, node in enumerate(nodes) if _listed(node.get("children"))]
        for at, node in documents[1:]:
            wrong.append(f"input_trees[0].nodes[{at}]: '{node.get('name', '')}' is a second document "
                         f"('{documents[0][1].get('name', '')}' is the first). v2 takes one document apart in a step: "
                         "take the other apart in a step of its own")
        document = str(documents[0][1].get("name", "")) if documents else None
        loop = self._loop(documents[0][1], f"input_trees[0].nodes[{documents[0][0]}]", wrong) if documents else ""
        for at, tree in enumerate(leaving[1:], start=1):
            wrong.append(f"output_trees[{at}]: a second output ('{tree.get('name', '')}'). v2 takes a document apart "
                         "into one flow: what more is wanted of it is a step after this one")
        out = leaving[0]
        if str(out.get("activateExpressionFilter", "")).lower() == "true":
            wrong.append("output_trees[0].expressionFilter: a filter is not read here: filter the rows with a step "
                         "after this one")
        said = _listed(out.get("nodes"))
        columns = self.schema or [column_of(fields) for fields in config["output_schema"]] or [
            Column(str(node.get("name", "")), TYPE_NAMES.get(str(node.get("type", "str")), "str")) for node in said]
        declared = [column.name for column in columns]
        places: Dict[str, str] = {}
        handed: Dict[str, str] = {}
        for at, node in enumerate(said):
            where, name = f"output_trees[0].nodes[{at}]", str(node.get("name", ""))
            written = str(node.get("expression") or "").strip()
            if _listed(node.get("children")):
                wrong.append(f"{where}: '{name}' is a document to build. v2 builds documents with the XML outputs, "
                             "not here")
                continue
            if name not in declared:
                wrong.append(f"{where}.name: there is no column '{name}'; the columns are: {', '.join(declared)}")
                continue
            if not written:
                continue
            place, column = _PLACE.fullmatch(written), _COLUMN.fullmatch(written)
            if place is None and column is None:
                wrong.append(f"{where}.expression: '{written}' is more than a place in the document or a column of "
                             "the row: work it out with a map after this step")
                continue
            source = (place or column).group(1)  # type: ignore[union-attr]
            if source in lookups:
                # Said once, of the lookup itself.
                continue
            if source == "Var" and main != "Var":
                wrong.append(f"{where}.expression: '{written}' is a variable of the map, and a converted job does not "
                             "say what it holds: work it out with a map after this step")
            elif source != main:
                wrong.append(f"{where}.expression: '{source}' is not the input of this map, which is '{main}'")
            elif column is not None:
                if column.group(2) not in names:
                    wrong.append(f"{where}.expression: there is no column '{column.group(2)}' in '{main}'; its columns "
                                 f"are: {', '.join(names)}")
                handed[name] = column.group(2)
            elif place.group(2) != document:  # type: ignore[union-attr]
                where_it_is = f"the document is in '{document}'" if document else "the tree has no document"
                wrong.append(f"{where}.expression: '{place.group(2)}' holds no document in the tree of '{main}'; "  # type: ignore[union-attr]
                             f"{where_it_is}")
            else:
                path = place.group(3).strip()  # type: ignore[union-attr]
                if not path.startswith("/"):
                    wrong.append(f"{where}.expression: '{path}' does not start at the root of the document: a place "
                                 f"is written from the root, as /{path}")
                    continue
                places[name] = _from_the_loop(loop, path)
                try:
                    xml_reader.path(places[name], config["namespaces"] or None)
                except ValueError as exc:
                    wrong.append(f"{where}.expression: {exc}")
        return _Mapped(columns, document, loop, places, handed), wrong

    @staticmethod
    def _loop(document: Dict[str, Any], where: str, wrong: List[str]) -> str:
        """The path of the loop element of a document's tree: the element marked so, or the root element."""
        marked: List[str] = []

        def walk(node: Dict[str, Any], above: str) -> None:
            path = f"{above}/{node.get('name', '')}"
            if node.get("loop") is True or str(node.get("loop", "")).lower() == "true":
                marked.append(path)
            for child in _listed(node.get("children")):
                walk(child, path)

        roots = [child for child in _listed(document.get("children")) if str(child.get("nodeType", "ELEMENT")).upper() == "ELEMENT"]
        if not roots:
            wrong.append(f"{where}: the document '{document.get('name', '')}' has no root element in its tree")
            return ""
        walk(roots[0], "")
        if len(marked) > 1:
            wrong.append(f"{where}: the document '{document.get('name', '')}' has {len(marked)} loop elements "
                         f"({', '.join(marked)}). v2 takes a document apart by one")
        return marked[0] if marked else f"/{roots[0].get('name', '')}"

    def problems(self) -> List[str]:
        return self._mapped()[1]

    def needs_rows(self) -> bool:
        mapped = self._mapped()[0]
        return mapped is not None and mapped.document is not None

    # ------------------------------------------------------------------
    # Rows handed on as they arrive, under other names
    # ------------------------------------------------------------------

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        (frame,) = inputs.values()
        mapped = self._mapped()[0]
        assert mapped is not None, "the job was loaded, so the trees say what the map does"
        there = frame.collect_schema().names()
        self._all_there(mapped, visible(there))
        declared = polars_schema(mapped.columns)
        made = [pl.col(mapped.handed[column.name]).alias(column.name) if column.name in mapped.handed
                else pl.lit(None, dtype=declared[column.name]).alias(column.name) for column in mapped.columns]
        return {"main": frame.select(made + hidden(there))}

    # ------------------------------------------------------------------
    # A document taken apart
    # ------------------------------------------------------------------

    def run(self, inputs: Dict[str, pl.DataFrame]) -> Dict[str, pl.DataFrame]:
        (frame,) = inputs.values()
        mapped = self._mapped()[0]
        assert mapped is not None and mapped.document is not None, "asked for rows, so there is a document to read"
        self._all_there(mapped, visible(frame.columns))
        config = self.config
        plan = Plan(mapped.document, mapped.loop, mapped.columns, {name: (path, False) for name, path in mapped.places.items()},
                    mapped.handed, None, config["namespaces"] or None, config["large_values"], config["die_on_error"],
                    with_rejects=False)
        return Extraction(self, plan).of(frame)

    def _all_there(self, mapped: _Mapped, there: List[str]) -> None:
        """Fail in plain words when the rows that arrive lack a column the trees draw."""
        wanted = list(mapped.handed.values()) + ([mapped.document] if mapped.document else [])
        for name in wanted:
            if name not in there:
                raise ConfigurationError(f"the rows that arrive have no column '{name}', which the tree of the input "
                                         f"draws; their columns are: {', '.join(there)}")
