"""Positional file input: read a text file whose fields sit at fixed places in each line.

Every field is cut out as text and then turned into its declared type, so a
field that cannot be read is a rejected row and never a failed read.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from ...errors import ConfigurationError
from ...files import as_utf8
from ...job.keys import Key, Kind
from ...job.model import Column
from ...types import from_text
from ...rows import first_of, hidden
from ..base import Source
from ..registry import REGISTRY
from .file_input_delimited import encoding, fatal, unreadable_text
from .file_input_fullrow import (
    BYTE_ORDER_MARK,
    DEFAULT_ENCODING,
    count_rows,
    scan_text_lines,
    starts_with_byte_order_mark,
)

logger = logging.getLogger(__name__)

_VALUE = "__v_"
_BAD, _LINE = "__bad", "__line"
# What pandas, which reads the file for v1, strips from both ends of every field.
_BLANKS = " \t"
_SEPARATED_TYPES = ("float", "Decimal")


def _widths(value: str) -> List[Optional[int]]:
    """A pattern as field widths; None stands for ``*``, the rest of the line."""
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if not parts:
        raise ValueError("needs at least one width")
    widths: List[Optional[int]] = []
    for index, part in enumerate(parts):
        if part == "*" and index == len(parts) - 1:
            widths.append(None)
            continue
        try:
            width = int(part)
        except ValueError:
            width = 0
        if width <= 0:
            raise ValueError(f"{part!r} is not a width; use whole numbers above zero, and * only for the last field")
        widths.append(width)
    return widths


def _count(value: int) -> int:
    if value < 0:
        raise ValueError("must not be negative")
    return value


def _limit(value: Any) -> Optional[int]:
    """v1's reading of a limit: nothing, blanks or the number 0 for every row, else a number above zero."""
    if not value or not str(value).strip():
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{value!r} is not a whole number") from None
    if number <= 0:
        raise ValueError("must be above zero; leave it empty to read every row")
    return number


@REGISTRY.register
class FileInputPositional(Source):
    """Read a text file of fixed-width fields.

    A line shorter than the pattern gives empty fields; what lies beyond the
    pattern is not read. Rows that cannot be read as the declared schema
    leave by the reject output with ``errorCode`` and ``errorMessage``, or
    fail the component when ``die_on_error`` is set.
    """

    names = ("file_input_positional", "FileInputPositional", "tFileInputPositional")
    outputs = {"main": ("flow", "main"), "reject": ("reject",)}
    conforms = False
    keys = (
        Key("path", required=True, aliases=("filepath",), doc="The file to read."),
        Key("pattern", required=True, convert=_widths,
            doc="The width of each field in characters, one per declared column, separated by commas: `5,4,5`. "
                "A last width of `*` takes the rest of the line."),
        Key("header_rows", type=int, default=0, convert=_count, doc="Lines to skip at the top of the file."),
        Key("footer_rows", type=int, default=0, convert=_count, doc="Lines to skip at the end of the file."),
        Key("limit", type=object, default=None, convert=_limit,
            doc="The most rows to read, blank rows not counted; empty, or the number 0, for all of them."),
        Key("encoding", default=DEFAULT_ENCODING, convert=encoding, doc="The file's character encoding."),
        Key("trim_all", type=bool, default=True,
            doc="Whether white space of every kind is dropped around a field. Blanks and tabs always are."),
        Key("die_on_error", type=bool, default=False,
            doc="Whether a row that cannot be read, or a file that is not there, fails the job. "
                "When off, such a row leaves by reject and a missing file reads as no rows."),
        Key("advanced_separator", type=bool, default=False,
            doc="Whether float and Decimal fields hold the two separators below."),
        Key("thousands_separator", default=",",
            doc="Taken out of float and Decimal fields under `advanced_separator`."),
        Key("decimal_separator", default=".",
            doc="Read as the decimal point of float and Decimal fields under `advanced_separator`."),
        Key("row_separator", kind=Kind.IGNORED, type=object,
            doc="A line ends at \\n, \\r\\n or \\r whatever this says, as in v1."),
        Key("pattern_units", kind=Kind.IGNORED, type=object,
            doc="Widths are counted in characters whatever this says, as in v1."),
        Key("remove_empty_row", kind=Kind.IGNORED, type=object,
            doc="A row whose fields are all blank is dropped whatever this says, as in v1."),
        Key("check_date", kind=Kind.IGNORED, type=object, doc="Dates are always checked against their pattern."),
        Key("uncompress", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well."),
        Key("advanced_option", kind=Kind.IGNORED, type=object,
            doc="Ignored by v1 as well: `pattern` gives the widths."),
        Key("formats", kind=Kind.IGNORED, type=object, doc="Only read by `advanced_option`."),
        Key("process_long_row", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well."),
        Key("trim_select", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well: see `trim_all`."),
    )

    def problems(self) -> List[str]:
        if not self.schema:
            return ["schema: a positional file input needs its columns declared"]
        widths = len(self.config["pattern"])
        if widths != len(self.schema):
            return [f"pattern: gives {widths} width(s) for {len(self.schema)} declared column(s)"]
        return []

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def read(self) -> Dict[str, pl.LazyFrame]:
        config = self.config
        path = config["path"]
        if not os.path.isfile(path):
            if config["die_on_error"]:
                raise ConfigurationError(f"Input file not found: {path}")
            logger.warning(f"[{self.id}] input file not found: {path}; no rows are read")
            return self.declared_outputs()
        names = [column.name for column in self.schema]
        source = as_utf8(path, config["encoding"], self.run_context, exact=True)
        lines = scan_text_lines(source, _LINE)
        length: Optional[int] = None
        if config["footer_rows"] > 0:
            length = max(count_rows(lines) - config["header_rows"] - config["footer_rows"], 0)
        # Numbered before a blank line is dropped: a row's number plus the header rows is its line in the file.
        lines = lines.slice(config["header_rows"], length).with_row_index(self.row_number, offset=1)

        frame = lines.select(*self._fields(names, starts_with_byte_order_mark(source)), self.row_number)
        frame = frame.filter(pl.any_horizontal([pl.col(name).str.strip_chars() != "" for name in names]))
        if config["limit"] is not None:
            frame = frame.head(config["limit"])
        return self._typed(frame.with_columns(self.key_copies()), names)

    def locate(self, number: int) -> str:
        return f"line {number + self.config['header_rows']} of {self.config['path']}"

    def _fields(self, names: List[str], marked: bool) -> List[pl.Expr]:
        """Each declared column cut out of the line, by position."""
        line = pl.col(_LINE).str.strip_prefix(BYTE_ORDER_MARK) if marked else pl.col(_LINE)
        fields, start = [], 0
        for name, width in zip(names, self.config["pattern"]):
            field = line.str.slice(start, width)
            field = field.str.strip_chars() if self.config["trim_all"] else field.str.strip_chars(_BLANKS)
            fields.append(field.alias(name))
            start += width or 0
        return fields

    def _number_text(self, column: Column) -> pl.Expr:
        """A field as the text its number is read from."""
        config, text = self.config, pl.col(column.name)
        if not config["advanced_separator"] or column.type not in _SEPARATED_TYPES:
            return text
        if config["thousands_separator"]:
            text = text.str.replace_all(config["thousands_separator"], "", literal=True)
        if config["decimal_separator"] not in ("", "."):
            text = text.str.replace_all(config["decimal_separator"], ".", literal=True)
        return text

    # ------------------------------------------------------------------
    # Text to the declared types, and what could not be read
    # ------------------------------------------------------------------

    def _typed(self, frame: pl.LazyFrame, names: List[str]) -> Dict[str, pl.LazyFrame]:
        typed = [column for column in self.schema if column.type != "str"]
        if not typed:
            return {"main": frame, "reject": _no_rejects(names)}

        values: List[pl.Expr] = []
        unreadable: List[Tuple[pl.Expr, str, pl.Expr]] = []
        missing: List[Tuple[pl.Expr, str, pl.Expr]] = []
        for column in typed:
            value, wrong = from_text(self._number_text(column), column)
            values.append(value.alias(_VALUE + column.name))
            unreadable.append((wrong, "TYPE_CONVERSION", pl.format(unreadable_text(column), pl.col(column.name))))
            if not column.nullable:
                reason = pl.lit(f"Column '{column.name}': non-nullable column has null")
                missing.append((value.is_null(), "SCHEMA_VIOLATION", reason))
        # The first thing wrong with a row, in v1's words: what cannot be read comes before what is missing.
        cases = unreadable + missing
        flagged = frame.with_columns(*values, pl.any_horizontal([wrong for wrong, _, _ in cases]).alias(_BAD))

        held = {column.name for column in typed}
        carried = hidden(frame.collect_schema().names())
        main = flagged.filter(~pl.col(_BAD)).select(
            [pl.col(_VALUE + name).alias(name) if name in held else pl.col(name) for name in names] + carried
        )
        reject = flagged.filter(pl.col(_BAD)).select(
            *[pl.col(name) for name in names],
            pl.coalesce([pl.when(wrong).then(pl.lit(code)) for wrong, code, _ in cases]).alias("errorCode"),
            pl.coalesce([pl.when(wrong).then(reason) for wrong, _, reason in cases]).alias("errorMessage"),
            *carried,
        )
        if self.config["die_on_error"]:
            self.check(
                reject.select(pl.len().alias("rows"), pl.col("errorMessage").first().alias("why"), *first_of(reject)),
                lambda found: fatal(found, self.where(found)),
            )
        else:
            self.tell_dropped(reject, pl.col("errorMessage"))
        return {"main": main, "reject": reject}


def _no_rejects(names: List[str]) -> pl.LazyFrame:
    return pl.LazyFrame(schema={name: pl.String for name in names + ["errorCode", "errorMessage"]})
