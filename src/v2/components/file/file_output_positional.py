"""File output positional: every column written to a fixed width, padded or cut."""
from __future__ import annotations

import logging
import os
import shutil
import zipfile
from typing import Any, Dict, List, Optional

import polars as pl

from ...errors import ConfigurationError
from ...files import cleared, encoded, put_in_place, to_encoding
from ...job.keys import Key, Kind
from ..base import Sink, Write
from ..registry import REGISTRY
from .file_input_delimited import encoding, unescape
from .file_output_delimited import _as_written

logger = logging.getLogger(__name__)

# v1's spellings of where a value stands in its width and of what is kept of one that is too long.
_ALIGN = {"L": "L", "R": "R", "C": "C", "LEFT": "L", "RIGHT": "R", "CENTER": "C", "CENTRE": "C"}
_KEEP = {"A": "A", "L": "L", "M": "M", "R": "R", "ALL": "A", "LEFT": "L", "MIDDLE": "M", "RIGHT": "R", "C": "L"}
_UNREAD = ("flushonrow", "flushonrow_num", "flush_on_row", "flush_on_row_num", "row_mode", "streamname", "dynamic",
           "die_on_error")


def _size(value: Any) -> int:
    try:
        size = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{value!r} is no width: give a whole number, 1 or more") from None
    if size <= 0:
        raise ValueError(f"{size} is no width: give 1 or more")
    return size


def _pad(value: Optional[str]) -> str:
    """The character a value is padded with: a blank when none is given; quotes around it are no part of it."""
    value = value or " "
    if len(value) == 3 and value[0] == value[-1] == "'":
        value = value[1]
    if len(value) != 1:
        raise ValueError(f"{value!r} is {len(value)} characters, and a value is padded with one")
    return value


def _one_of(known: Dict[str, str], default: str):
    def convert(value: Optional[str]) -> str:
        word = (value or default).upper()
        if word not in known:
            raise ValueError(f"{value!r} is none of {', '.join(known)}")
        return known[word]
    return convert


def _formats(value: List[Any]) -> List[Any]:
    if not value:
        raise ValueError("names no column to write")
    return value


def _fitted(text: str, size: int, pad: str, align: str, keep: str) -> str:
    """A text in its width, as Talend has it. The rule the rows are held to as well (``_fitted_column``)."""
    surplus = len(text) - size
    if surplus > 0:
        if keep == "A":
            return text
        if keep == "R":
            return text[surplus:]
        if keep == "M":
            return text[surplus // 2:surplus // 2 + size]
        return text[:size]
    if align == "L":
        return text.ljust(size, pad)
    if align == "R":
        return text.rjust(size, pad)
    # Centred: where the padding does not divide evenly, the one more is on the right.
    return (pad * (-surplus // 2) + text).ljust(size, pad)


def _fitted_column(text: pl.Expr, size: int, pad: str, align: str, keep: str) -> pl.Expr:
    """A column of texts, none missing, each in its width: ``_fitted`` for every row."""
    length = text.str.len_chars().cast(pl.Int64)
    if keep == "R":
        text = text.str.tail(size)
    elif keep == "M":
        text = pl.when(length > size).then(text.str.slice((length - size) // 2, size)).otherwise(text)
    elif keep == "L":
        text = text.str.head(size)
    if align == "L":
        return text.str.pad_end(size, pad)
    if align == "R":
        return text.str.pad_start(size, pad)
    before = pl.when(length < size).then(pl.lit(pad * size).str.head((size - length) // 2)).otherwise(pl.lit(""))
    return (before + text).str.pad_end(size, pad)


_FORMAT = (
    Key("schema_column", required=True, aliases=("SCHEMA_COLUMN",), doc="The column."),
    Key("size", type=object, required=True, aliases=("SIZE",), convert=_size, doc="Its width, in characters."),
    Key("padding_char", default=" ", aliases=("PADDING_CHAR",), convert=_pad,
        doc="What a shorter value is padded with: one character."),
    Key("align", default="L", aliases=("ALIGN",), convert=_one_of(_ALIGN, "L"),
        doc="Where a shorter value stands in its width: L, R or C."),
    Key("keep", default="A", aliases=("KEEP",), convert=_one_of(_KEEP, "A"),
        doc="What is kept of a longer value: A all of it, L its left, M its middle, R its right."),
)


@REGISTRY.register
class FileOutputPositional(Sink):
    """Write every row as one line of fixed-width fields, the columns `formats` names, in that order.

    A value shorter than its `size` is padded with `padding_char`, on the
    right (`align` L), on the left (R) or on both sides (C; where the
    padding does not divide evenly, the one more is on the right). Of a
    value longer than its size `keep` says what stays: all of it (A, which
    makes the line longer), its left, its middle or its right. A missing
    value, and a column that does not arrive, is all padding. With
    `include_header` the column names come first, fitted the same way.

    A value is written as the delimited output writes it: a date by its
    column's pattern, true and false as `true` and `false`, a Decimal to
    its declared places, a float as it prints.

    With `append` the rows are added to a file that is there, and the
    header is written only into a new or empty file. With `compress`, and
    not when appending, the file goes into a zip beside its name
    (`out.txt` into `out.zip`), as in Talend.
    """

    names = ("file_output_positional", "FileOutputPositional", "tFileOutputPositional")
    keys = (
        Key("path", required=True, aliases=("filepath",), doc="The file to write."),
        Key("formats", type=list, required=True, items=_FORMAT, convert=_formats,
            doc="The columns to write, each with its width and how it is fitted to it."),
        Key("row_separator", default="\n", convert=unescape, doc="What ends a row."),
        Key("append", type=bool, default=False, doc="Whether the rows are added to a file that is there."),
        Key("include_header", type=bool, default=False, doc="Whether the column names are written first."),
        Key("compress", type=bool, default=False, doc="Whether the file goes into a zip beside its name; never when appending."),
        Key("encoding", default="ISO-8859-15", convert=encoding, doc="The file's character encoding."),
        Key("create", type=bool, default=True, doc="Whether folders that are missing are made."),
        Key("delete_empty_file", type=bool, default=False, doc="Whether no file is left when there is no row to write."),
        Key("use_byte", kind=Kind.REFUSED, type=object, reason="widths counted in bytes are not built; v2 counts characters, as v1 does"),
        Key("usestream", kind=Kind.REFUSED, type=object, reason="v2 writes to a file, not to a stream"),
        Key("use_existing_dynamic", kind=Kind.REFUSED, type=object, reason="v2 has no dynamic schema"),
        Key("advanced_separator", kind=Kind.IGNORED, type=object, doc="Not acted on by v1."),
        Key("thousands_separator", kind=Kind.IGNORED, type=object, doc="Not acted on by v1."),
        Key("decimal_separator", kind=Kind.IGNORED, type=object, doc="Not acted on by v1."),
    ) + tuple(Key(name, kind=Kind.IGNORED, type=object, doc="Changes nothing in what is written.") for name in _UNREAD)

    def problems(self) -> List[str]:
        return [] if self.config["path"] else ["path: the file to write has no name"]

    def write(self, frame: pl.LazyFrame) -> Write:
        config = self.config
        path, formats, row_end = config["path"], config["formats"], config["row_separator"]
        folder = os.path.dirname(path)
        if folder and config["create"]:
            os.makedirs(folder, exist_ok=True)
        if folder and not os.path.isdir(folder):
            raise ConfigurationError(f"Failed to write file '{path}': folder '{folder}' does not exist")

        types = frame.collect_schema()
        declared = {column.name: column for column in self.input_schema}
        def fitted(entry: Dict[str, Any]) -> pl.Expr:
            name = entry["schema_column"]
            if name in types:
                text = _as_written(name, types[name], declared.get(name)).cast(pl.String).fill_null("")
            else:
                # Nothing, once for every row: a plain literal would make one row of however many arrive.
                text = pl.repeat("", pl.len(), dtype=pl.String)
            return _fitted_column(text, entry["size"], entry["padding_char"], entry["align"], entry["keep"])

        lines = frame.select(pl.concat_str([fitted(entry) for entry in formats]).alias("line"))
        header = b""
        if config["include_header"]:
            names = [_fitted(entry["schema_column"], entry["size"], entry["padding_char"], entry["align"], entry["keep"])
                     for entry in formats]
            header = encoded("".join(names) + row_end, config["encoding"])

        # As in Talend: adding to a file is never compressed, and the zip stands beside the file's name.
        zipped = config["compress"] and not config["append"]
        target = _zip_name(path) if zipped else path
        settled = {"mark": b""}

        def sink(written: str) -> pl.LazyFrame:
            return lines.sink_csv(written, include_header=False, line_terminator=row_end, quote_style="never", lazy=True)

        def ready(written: str, rows: int) -> None:
            settled["mark"] = to_encoding(written, config["encoding"])

        def place(written: str, rows: int) -> None:
            if not rows and config["delete_empty_file"]:
                os.remove(written)
                # As in Talend: a file nothing was added to is kept; one this run would have replaced is not.
                if not config["append"] and os.path.exists(target):
                    os.remove(target)
                return
            if not zipped:
                put_in_place(written, path, config["append"], settled["mark"], header)
                return
            packed = written + ".zip"
            try:
                with zipfile.ZipFile(cleared(packed), "w", zipfile.ZIP_DEFLATED) as held:
                    with open(written, "rb") as source, held.open(os.path.basename(path), "w") as entry:
                        entry.write(settled["mark"] + header)
                        source.seek(len(settled["mark"]))
                        shutil.copyfileobj(source, entry)
            finally:
                os.remove(written)
            put_in_place(packed, target)

        def as_text(rows: pl.DataFrame) -> pl.DataFrame:
            # Each column as its first entry of `formats` fits it; one that is not written, as it stands.
            first = {entry["schema_column"]: entry for entry in reversed(formats)}
            return rows.select([
                fitted(first[name]).alias(name) if name in first else pl.col(name).cast(pl.String)
                for name in rows.columns
            ])

        return Write(path=target, sink=sink, ready=ready, place=place,
                     empty_leaves_none=config["delete_empty_file"], as_text=as_text)


def _zip_name(path: str) -> str:
    """Where Talend puts the zip: the file's name with what follows its last dot replaced by `.zip`."""
    plain = path.replace("\\", "/")
    dot = plain.rfind(".")
    return (path if dot < plain.rfind("/") or dot == -1 else path[:dot]) + ".zip"
