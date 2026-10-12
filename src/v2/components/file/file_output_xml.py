"""XML file output: rows written as the elements of a document."""
from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

import polars as pl

from ... import xml_reader, xml_writer
from ...errors import ConfigurationError
from ...files import put_in_place, to_encoding
from ...job.keys import Key, Kind
from ..base import Sink, Write
from ..registry import REGISTRY
from .file_input_delimited import encoding
from .file_output_delimited import _as_written

logger = logging.getLogger(__name__)

# The working column that numbers the rows as they are written, for a message.
_ROW = "__n"


def _name_of(what: str, may_be_none: bool = False) -> Callable[[str], str]:
    def check(value: str) -> str:
        if not (may_be_none and not value) and not xml_writer.is_name(value):
            raise ValueError(f"{value!r} is no name {what} may have")
        return value
    return check


_ROOT = (Key("name", required=True, aliases=("tag",), convert=_name_of("an element"), doc="The element's name."),)
_MAPPING = (
    Key("column", required=True, doc="The column."),
    Key("as_attribute", type=bool, default=False,
        doc="Whether the column is an attribute of the row's element, and not an element in it."),
    Key("label", default="", convert=_name_of("an element", may_be_none=True),
        doc="The name the element or attribute has, when it is not the column's."),
)
_GROUP = (
    Key("column", required=True, doc="The column whose value the rows of a group share."),
    Key("label", default="name", convert=_name_of("an attribute"),
        doc="The attribute of the group's element that holds the value."),
)


@REGISTRY.register
class FileOutputXML(Sink):
    """Write the rows as a document: a row is an element, its columns are the elements in it or its attributes.

    The document starts with its declaration and the `root_tags`, one inside
    the other in the order given (`root` when none is given). Each row is
    one `row_tag` element on one line. A column is an element named after
    it, or an attribute of the row when its `mapping` entry says so; an
    entry's `label` gives it another name. `missing` says what is written
    for a value that is missing: the element or attribute with nothing in
    it (`empty`), nothing at all (`omit`), or the element marked
    `xsi:nil="true"` (`nil`).

    With `use_dynamic_grouping`, the rows that follow each other with the
    same value in a `group_by` column stand in one element, named after the
    column, which holds the value in the attribute `label`. The rows of a
    group have to arrive together.

    Whatever a value holds is read back as it was: `&`, `<`, `>`, quotes and
    line ends are escaped, and a character the `encoding` lacks is written
    by its number. A character XML cannot hold fails the job. Before the
    file is put in place it is read once, as a reader would read it.

    With `input_is_document`, the column `document_col` holds a whole
    document, and the file is that document; there has to be one row.
    """

    names = ("file_output_xml", "FileOutputXML", "tFileOutputXML")
    keys = (
        Key("path", default="", aliases=("filename", "filepath"), doc="The file to write."),
        Key("row_tag", default="row", convert=_name_of("an element"), doc="The name of a row's element."),
        Key("root_tags", type=list, default=[], items=_ROOT,
            doc="The elements around all the rows, the first outermost; `root` when none is given."),
        Key("mapping", type=list, default=[], items=_MAPPING, doc="How a column is written, where not as an element of its name."),
        Key("missing", default="empty", choices=("empty", "omit", "nil"),
            doc="What is written for a missing value: `empty`, `omit` or `nil`."),
        Key("use_dynamic_grouping", type=bool, default=False, doc="Whether the rows are grouped by `group_by`."),
        Key("group_by", type=list, default=[], items=_GROUP, doc="The columns the rows are grouped by, the first outermost."),
        Key("encoding", default="ISO-8859-15", convert=encoding, doc="The encoding of the file, which its declaration names."),
        Key("create", type=bool, default=True, doc="Whether the folder of the file is made when it is not there."),
        Key("delete_empty_file", type=bool, default=False, doc="Whether no file is left when no row arrives."),
        Key("input_is_document", type=bool, default=False, doc="Whether a column holds the document to write."),
        Key("document_col", default="", doc="With `input_is_document`: that column."),
        Key("trim", type=bool, default=False, doc="With `input_is_document`: whether white space around the document goes."),
        Key("split", kind=Kind.REFUSED, type=bool, reason="v2 writes one file: split the rows before the output"),
        Key("split_every", kind=Kind.IGNORED, type=object, doc="Only read with `split`."),
        Key("advanced_separator", kind=Kind.REFUSED, type=bool,
            reason="v2 writes a number one way: write it as text of the form wanted before the output"),
        Key("thousands_separator", kind=Kind.IGNORED, type=object, doc="Only read with `advanced_separator`."),
        Key("decimal_separator", kind=Kind.IGNORED, type=object, doc="Only read with `advanced_separator`."),
        Key("flushonrow", kind=Kind.IGNORED, type=object, doc="Talend's buffer; v2 writes as it goes."),
        Key("flushonrow_num", kind=Kind.IGNORED, type=object, doc="Talend's buffer; v2 writes as it goes."),
        Key("die_on_error", kind=Kind.IGNORED, type=object, doc="What cannot be written fails the job; v1 reads it on every component."),
    )

    # ------------------------------------------------------------------
    # What is written under which name
    # ------------------------------------------------------------------

    def _groups(self) -> List[Dict[str, Any]]:
        return self.config["group_by"] if self.config["use_dynamic_grouping"] else []

    def _named(self, names: List[str]) -> Dict[str, Tuple[str, bool]]:
        """For each column: the name it has in the document, and whether it is an attribute."""
        said = {entry["column"]: entry for entry in self.config["mapping"]}
        return {name: (said[name]["label"] or name if name in said else name, name in said and said[name]["as_attribute"])
                for name in names}

    def problems(self) -> List[str]:
        config = self.config
        found = [] if config["path"] else ["path: the file to write has no name"]
        declared = [column.name for column in self.input_schema]
        if not declared:
            return found
        listed = ", ".join(declared)
        for at, entry in enumerate(config["mapping"]):
            if entry["column"] not in declared:
                found.append(f"mapping[{at}].column: there is no column '{entry['column']}'; the columns are: {listed}")
        for at, entry in enumerate(self._groups()):
            if entry["column"] not in declared:
                found.append(f"group_by[{at}].column: there is no column '{entry['column']}'; the columns are: {listed}")
        if config["input_is_document"]:
            if config["document_col"] not in declared:
                found.append(f"document_col: there is no column '{config['document_col']}'; the columns are: {listed}")
            return found
        for name, (shown, _) in self._named(declared).items():
            if not xml_writer.is_name(shown):
                found.append(f"schema: the column '{name}' has no name an element may have: give it one with a `label` "
                             "in `mapping`")
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
        types = frame.collect_schema()
        declared = {column.name: column for column in self.input_schema}

        def as_text(name: str) -> pl.Expr:
            return _as_written(name, types[name], declared.get(name)).cast(pl.String)

        whole = config["input_is_document"]
        if whole:
            document = as_text(config["document_col"])
            if config["trim"]:
                document = document.str.strip_chars()
            # The document's own declaration goes: the file says itself how it is written.
            body = frame.select(document.str.replace(r"^\s*<\?xml[^>]*\?>\s*", "").fill_null("").alias("line"))
            head, foot, read = [xml_writer.declaration(config["encoding"])], [], [config["document_col"]]
        else:
            body, read = self._rows(frame, as_text, list(types.names()))
            roots = [entry["name"] for entry in config["root_tags"]] or ["root"]
            marked = xml_writer.NIL_NAMESPACE if config["missing"] == "nil" else ""
            head = [xml_writer.declaration(config["encoding"])] + [
                f"<{name}{marked if at == 0 else ''}>" for at, name in enumerate(roots)]
            foot = [f"</{name}>" for name in reversed(roots)]
        self._no_character_xml_cannot_hold(frame, [name for name in read if types[name] == pl.String])
        parts = [pl.LazyFrame({"line": head}, schema={"line": pl.String}), body]
        if foot:
            parts.append(pl.LazyFrame({"line": foot}, schema={"line": pl.String}))
        document_lines = xml_writer.lines(parts)

        def sink(written: str) -> pl.LazyFrame:
            return document_lines.sink_csv(written, include_header=False, line_terminator="\n", quote_style="never", lazy=True)

        def ready(written: str, rows: int) -> None:
            if not rows and config["delete_empty_file"]:
                return
            if whole and rows != 1:
                raise ConfigurationError(
                    f"{rows} rows arrive, and a file holds one document: `input_is_document` writes the document of one row")
            to_encoding(written, config["encoding"], by_number=True)
            try:
                # A writer written by hand earns one reading of what it wrote, before anyone else reads it.
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

    def _rows(
        self, frame: pl.LazyFrame, as_text: Callable[[str], pl.Expr], names: List[str]
    ) -> Tuple[pl.LazyFrame, List[str]]:
        """The line of each row, with the tags of the groups that open before it and close after it."""
        config = self.config
        missing, tag = config["missing"], config["row_tag"]
        named = self._named(names)
        groups = [entry for entry in self._groups() if entry["column"] in names]
        grouped = [entry["column"] for entry in groups]
        attributes: List[pl.Expr] = []
        elements: List[pl.Expr] = []
        for name in names:
            if name in grouped:
                # In the element of its group, and not in the row.
                continue
            shown, as_attribute = named[name]
            value = as_text(name)
            if as_attribute:
                opens, closes, there = f' {shown}="', '"', xml_writer.attribute(value)
                nothing = f' {shown}=""' if missing == "empty" else ""
            else:
                opens, closes, there = f"<{shown}>", f"</{shown}>", xml_writer.text(value)
                nothing = {"empty": f"<{shown}></{shown}>", "omit": "", "nil": f"<{shown}{xml_writer.NIL}/>"}[missing]
            written = pl.when(value.is_null()).then(pl.lit(nothing)).otherwise(pl.concat_str([pl.lit(opens), there, pl.lit(closes)]))
            (attributes if as_attribute else elements).append(written)
        line = pl.concat_str([pl.lit(f"<{tag}"), *attributes, pl.lit(">"), *elements, pl.lit(f"</{tag}>")])
        if groups:
            # The first row: nothing stands before it.
            first = pl.col(grouped[0]).is_null().shift(1).is_null()
            before: List[pl.Expr] = []
            after: List[pl.Expr] = []
            for at, entry in enumerate(groups):
                # A group starts anew where its value, or that of a group around it, is not the row before's.
                starts = first | pl.any_horizontal([pl.col(name).ne_missing(pl.col(name).shift(1)) for name in grouped[:at + 1]])
                element = named[entry["column"]][0]
                value = xml_writer.attribute(as_text(entry["column"]).fill_null(""))
                before.append(pl.when(starts).then(
                    pl.concat_str([pl.lit(f'<{element} {entry["label"]}="'), value, pl.lit('">\n')])).otherwise(pl.lit("")))
                # And ends where the row after starts one anew, or there is no row after.
                after.insert(0, pl.when(starts.shift(-1).fill_null(True)).then(pl.lit(f"\n</{element}>")).otherwise(pl.lit("")))
            line = pl.concat_str([*before, line, *after])
        return frame.select(line.alias("line")), names

    def _no_character_xml_cannot_hold(self, frame: pl.LazyFrame, texts: List[str]) -> None:
        """Have the subjob fail when a text holds a character XML cannot hold, naming the first such row."""
        if not texts:
            return
        numbered = frame.with_row_index(_ROW, offset=1)
        wrong = {name: pl.col(name).str.contains(xml_writer.NOT_IN_XML).fill_null(False) for name in texts}
        found = numbered.select(
            *[pl.col(_ROW).filter(wrong[name]).first().alias(f"{_ROW}_{name}") for name in texts],
            *[pl.col(name).filter(wrong[name]).first().alias(name) for name in texts],
        )

        def problem(result: pl.DataFrame) -> Optional[str]:
            first = min(((result[f"{_ROW}_{name}"].item(), name) for name in texts
                         if result[f"{_ROW}_{name}"].item() is not None), default=None)
            if first is None:
                return None
            row, name = first
            return f"column '{name}' of row {row} holds a character XML cannot hold: {result[name].item()!r}"

        self.check(found, problem)
