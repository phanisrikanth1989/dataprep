"""Full-row file input: read every line of a text file as one text column."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import polars as pl

from ...errors import ConfigurationError
from ...files import as_utf8, codec_name
from ...job.keys import Key, Kind
from ..base import Source
from ..registry import REGISTRY
from .file_input_delimited import encoding, unescape

logger = logging.getLogger(__name__)

DEFAULT_ENCODING = "ISO-8859-15"
BYTE_ORDER_MARK = "\ufeff"
_COLUMN = "line"


def scan_text_lines(source: str, name: str, lone_cr: bool = True) -> pl.LazyFrame:
    """The lines of a UTF-8 text file as one text column, read lazily.

    A line ends at ``\\n`` or ``\\r\\n``.

    Args:
        source: The file. Its name is taken as it is, never as a pattern.
        name: The name of the column.
        lone_cr: Whether a ``\\r`` that no ``\\n`` follows ends a line too.
    """
    lines = pl.scan_lines(source, name=name, glob=False)
    if lone_cr:
        lines = lines.select(pl.col(name).str.split("\r")).explode(name, empty_as_null=False)
    return lines


def count_rows(frame: pl.LazyFrame) -> int:
    """How many rows a lazy frame holds, found by running it without keeping them."""
    return frame.select(pl.len()).collect(engine="streaming").item()


def starts_with_byte_order_mark(source: str) -> bool:
    """Whether a UTF-8 file opens with a byte order mark."""
    with open(source, "rb") as handle:
        return handle.read(3) == BYTE_ORDER_MARK.encode("utf-8")


def _encoding(value: str) -> str:
    """Refuse an encoding Python does not know; none at all is v1's default."""
    return encoding(value or DEFAULT_ENCODING)


def _row_separator(value: str) -> str:
    value = unescape(value)
    if value not in ("\n", "\r\n", "\r"):
        raise ValueError("v2 reads rows separated by \\n, \\r\\n or \\r only")
    return value


def _limit(value: Any) -> Optional[int]:
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    try:
        number = int(text)
    except ValueError:
        raise ValueError(f"{value!r} is not a whole number") from None
    return number if number > 0 else None


def _ends_in_line_end(source: str, lone_cr: bool) -> bool:
    """Whether a file is empty or its last byte ends a line."""
    with open(source, "rb") as handle:
        if handle.seek(0, os.SEEK_END) == 0:
            return True
        handle.seek(-1, os.SEEK_END)
        last = handle.read(1)
    return last == b"\n" or (lone_cr and last == b"\r")


@REGISTRY.register
class FileInputFullRow(Source):
    """Read a text file line by line, each line whole in one text column.

    The column takes the name of the first declared column, or ``line``.
    As in v1, what follows the last line end of a file counts as a line even
    when it is empty: it is dropped with the other empty lines, kept with
    them when ``remove_empty_row`` is off, and is the first line the footer
    takes.
    """

    names = ("file_input_full_row", "FileInputFullRowComponent", "FileInputFullRow", "tFileInputFullRow")
    keys = (
        Key("path", required=True, aliases=("filename",), doc="The file to read."),
        Key("row_separator", default="\n", convert=_row_separator,
            doc="What ends a line: `\\n` or `\\r` (either reads lines ending in \\n, \\r\\n or \\r), "
                "or `\\r\\n` (reads lines ending in \\r\\n or \\n and keeps a lone \\r in the line)."),
        Key("header_rows", type=int, default=0, doc="Lines to skip at the top of the file."),
        Key("footer_rows", type=int, default=0, doc="Lines to skip at the end of the file."),
        Key("limit", type=object, default=None, convert=_limit,
            doc="The most lines to read, counted after empty ones are removed; empty, zero or negative for all."),
        Key("remove_empty_row", type=bool, default=True,
            doc="Whether lines with nothing in them are dropped. A line of blanks is not empty."),
        Key("encoding", default=DEFAULT_ENCODING, convert=_encoding,
            doc="The file's character encoding."),
        Key("random", kind=Kind.REFUSED, type=bool,
            reason="lines picked at random differ from one run to the next; v2 does not pick them",
            doc="Read `nb_random` lines picked at random instead of the file in order."),
        Key("nb_random", kind=Kind.IGNORED, type=object, doc="Only read by `random`."),
    )

    def declared_outputs(self) -> Dict[str, pl.LazyFrame]:
        if not self.schema:
            return {"main": pl.LazyFrame(schema={_COLUMN: pl.String})}
        return super().declared_outputs()

    def line_counts(
        self, inputs: Dict[str, pl.LazyFrame], outputs: Dict[str, pl.LazyFrame]
    ) -> Dict[str, List[pl.LazyFrame]]:
        """v1's full-row input counts as read every line the file splits into, whatever it then skips."""
        counts = super().line_counts(inputs, outputs)
        counts["NB_LINE"] = self._split
        return counts

    def read(self) -> Dict[str, pl.LazyFrame]:
        config = self.config
        path = config["path"]
        if not os.path.isfile(path):
            raise ConfigurationError(f"File not found: '{path}'")
        name = self.schema[0].name if self.schema else _COLUMN
        # A byte that is not valid in the declared encoding fails the read, as in v1's full-row input.
        source = as_utf8(path, config["encoding"], self.run_context)
        lone_cr = config["row_separator"] != "\r\n"
        lines = scan_text_lines(source, name, lone_cr)
        if codec_name(config["encoding"]) == "utf-8-sig" and starts_with_byte_order_mark(source):
            lines = lines.with_columns(pl.col(name).str.strip_prefix(BYTE_ORDER_MARK))

        header, footer = max(config["header_rows"], 0), max(config["footer_rows"], 0)
        # v1 splits the text at its line ends, so what follows the last of them is one more line, of nothing.
        last_is_empty = _ends_in_line_end(source, lone_cr)
        self._split = [lines, pl.LazyFrame({name: [""]})] if last_is_empty else [lines]
        length: Optional[int] = None
        if footer:
            length = max(count_rows(lines) + int(last_is_empty) - header - footer, 0)
        elif last_is_empty and not config["remove_empty_row"]:
            lines = pl.concat([lines, pl.LazyFrame({name: [""]})])
        lines = lines.slice(header, length)
        if config["remove_empty_row"]:
            lines = lines.filter(pl.col(name) != "")
        if config["limit"] is not None:
            lines = lines.head(config["limit"])
        return {"main": lines}
