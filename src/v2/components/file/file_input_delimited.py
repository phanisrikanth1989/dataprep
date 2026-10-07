"""Delimited file input: read a delimited text file as rows.

Every field is read as text and then turned into its declared type, so a
field that cannot be read is a rejected row and never a failed read.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from ...errors import ConfigurationError
from ...files import as_utf8, codec_name
from ...job.keys import Key, Kind
from ...job.model import Column
from ...rows import first_of
from ...types import finish_value, parse_text, polars_schema, unreadable
from ..base import Source, ascii_only
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# The row separators Polars can split on, and the end-of-line byte each one needs.
_ROW_SEPARATORS = {"\n": "\n", "\r\n": "\n", "\r": "\r"}
_VALUE = "__v_"
_BAD, _FIELDS, _LINE = "__bad", "__fields", "__line"


def unescape(value: str) -> str:
    """Turn the two characters backslash-n (and -t, -r) into the one they mean."""
    return value.replace("\\r", "\r").replace("\\n", "\n").replace("\\t", "\t")


def encoding(value: str) -> str:
    """Refuse an encoding Python does not know."""
    try:
        codec_name(value)
    except ConfigurationError as exc:
        raise ValueError(str(exc)) from None
    return value


def _delimiter(value: str) -> str:
    value = unescape(value)
    if not value:
        raise ValueError("must not be empty")
    return value


def _row_separator(value: str) -> str:
    value = unescape(value)
    if value not in _ROW_SEPARATORS:
        raise ValueError("v2 reads rows separated by \\n, \\r\\n or \\r only")
    return value


def _not_negative(value: int) -> int:
    if value < 0:
        raise ValueError("must not be negative")
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


@REGISTRY.register
class FileInputDelimited(Source):
    """Read a delimited text file.

    Rows that cannot be read as the declared schema leave by the reject
    output with ``errorCode`` and ``errorMessage``, or fail the component
    when ``die_on_error`` is set.
    """

    names = ("file_input_delimited", "FileInputDelimited", "tFileInputDelimited")
    outputs = {"main": ("flow", "main"), "reject": ("reject",)}
    conforms = False
    keys = (
        Key("path", required=True, aliases=("filepath",), doc="The file to read."),
        Key("delimiter", default=";", aliases=("fieldseparator",), convert=_delimiter,
            doc="What separates fields. More than one character is allowed when `csv_option` is off."),
        Key("row_separator", default="\n", convert=_row_separator,
            doc="What ends a row when `csv_option` is off: `\\n` (also reads `\\r\\n`), `\\r\\n` or `\\r`."),
        Key("csv_row_separator", default="\n", convert=_row_separator,
            doc="What ends a row when `csv_option` is on."),
        Key("header_rows", type=int, default=0, convert=_not_negative, doc="Lines to skip at the top of the file."),
        Key("footer_rows", type=int, default=0, convert=_not_negative, doc="Lines to skip at the end of the file."),
        Key("limit", type=object, default=None, convert=_limit,
            doc="The most rows to read; empty, zero or negative for all of them."),
        Key("encoding", default="ISO-8859-15", convert=encoding, doc="The file's character encoding."),
        Key("csv_option", type=bool, default=False,
            doc="Whether fields may be enclosed, so that they can hold the delimiter or a line break."),
        Key("text_enclosure", default='"', doc="The character that encloses a field when `csv_option` is on."),
        Key("escape_char", default='"',
            doc="Must equal `text_enclosure`: an enclosure inside a field is written twice."),
        Key("remove_empty_row", type=bool, default=True, doc="Whether rows whose fields are all blank are dropped."),
        Key("trim_all", type=bool, default=False, doc="Whether every text column is stripped of surrounding blanks."),
        Key("trim_select", type=list, default=[], doc="Text columns to strip, one by one.",
            items=(Key("column", required=True, doc="The column."),
                   Key("trim", type=bool, default=False, doc="Whether it is stripped."))),
        Key("check_fields_num", type=bool, default=False,
            doc="Whether a row with more or fewer fields than the schema is rejected."),
        Key("die_on_error", type=bool, default=False,
            doc="Whether a row that cannot be read fails the job instead of leaving by reject."),
        Key("check_date", kind=Kind.IGNORED, type=object, doc="Dates are always checked against their pattern."),
        Key("uncompress", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well."),
        Key("split_record", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well."),
        Key("random", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well."),
        Key("nb_random", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well."),
        Key("advanced_separator", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well."),
        Key("thousands_separator", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well."),
        Key("decimal_separator", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well."),
        Key("enable_decode", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well."),
        Key("decode_cols", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well."),
    )

    def problems(self) -> List[str]:
        config, found = self.config, []
        if not self.schema:
            found.append("schema: a delimited file input needs its columns declared")
        if config["csv_option"]:
            if len(config["text_enclosure"]) != 1:
                found.append("text_enclosure: must be one character")
            elif config["escape_char"] not in (config["text_enclosure"], ""):
                found.append("escape_char: v2 reads an enclosure inside a field only when it is written twice")
            if config["check_fields_num"]:
                found.append("check_fields_num: field counts are not checked on files read with csv_option")
            if len(config["delimiter"][0].encode()) != 1:
                found.append("delimiter: with csv_option, v2 reads a separator of one byte only")
        elif self._by_line() and config["row_separator"] == "\r":
            found.append("row_separator: \\r cannot be combined with check_fields_num or a delimiter of several characters")
        return found

    def _by_line(self) -> bool:
        """Whether rows are split by v2 itself instead of by Polars' delimited reader.

        Polars' reader cannot count the fields of a row or split on more
        than one byte. Nor can it tell a blank line from a row of empty
        fields, and v1 never takes a blank line for a row: that shows where
        rows of empty fields are kept (``remove_empty_row`` off) or counted
        (a ``limit``).
        """
        config = self.config
        if config["csv_option"]:
            return False
        if config["check_fields_num"] or len(config["delimiter"].encode()) != 1:
            return True
        return (config["limit"] is not None or not config["remove_empty_row"]) and config["row_separator"] != "\r"

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def read(self) -> Dict[str, pl.LazyFrame]:
        config = self.config
        path = config["path"]
        if not os.path.isfile(path):
            raise ConfigurationError(f"File not found: '{path}'")
        self.global_map[f"{self.id}_FILENAME"] = path
        self.global_map[f"{self.id}_ENCODING"] = config["encoding"]
        names = [column.name for column in self.schema]
        source = as_utf8(path, config["encoding"], self.run_context, exact=self._by_line())
        native, why_text = self._native()
        if native:
            self.run_context.used_fast_read = True
        if logger.isEnabledFor(logging.DEBUG):
            how = f"every column is read as text: {why_text}"
            if native:
                how = f"Polars parses the numbers of {', '.join(native)} itself; every other column is read as text"
            logger.debug(ascii_only(f"[{self.id}] {how}"))
        frame = self._lines(source, names) if self._by_line() else self._fields(source, names, native)

        if config["remove_empty_row"]:
            blank = [pl.col(name).is_null() if name in native else pl.col(name).str.strip_chars() == "" for name in names]
            # Hardly any row is empty, and a row whose first field is not blank is not: only the others
            # have the rest of their fields looked at.
            empty = pl.when(blank[0]).then(pl.all_horizontal(blank)).otherwise(False) if len(blank) > 1 else blank[0]
            frame = frame.filter(~empty)
        if self._by_line():
            frame = frame.with_row_index(_LINE, offset=1)
        # Copied before a field is trimmed or typed: a key is shown as it stands in the file.
        frame = frame.with_columns(self.key_copies())
        trimmed = self._trimmed()
        if trimmed:
            frame = frame.with_columns([pl.col(name).str.strip_chars() for name in trimmed])
        return self._typed(frame, names, native)

    def locate(self, number: int) -> str:
        """Where a row is: its line, or its place among the records where a record can span lines."""
        path = self.config["path"]
        if self.config["csv_option"]:
            return f"record {number} of {path}"
        return f"line {number + self.config['header_rows']} of {path}"

    def _native(self) -> Tuple[Dict[str, pl.DataType], str]:
        """The columns Polars parses itself, with their types; the others arrive as text.

        Polars reads a whole number or a float much faster than this
        component can from text, and gives the same value wherever it gives
        one. Where the tolerant reader would take a value Polars does not
        (blanks around a number, ``1.0`` for a whole number, any text when
        errors are not fatal), Polars fails, and the engine runs the subjob
        again with every column read as text. Text is read from the start
        when the engine cannot do that, and when the reject output is
        wired: a rejected row carries its fields as they stand in the file.

        Returns:
            The columns, and when there are none, why every column is read
            as text.
        """
        if self._by_line():
            return {}, (
                "v2 splits the rows itself (a field count, a delimiter of several bytes, a limit, "
                "or empty rows that are kept)"
            )
        if not self.run_context.fast_read:
            return {}, "the engine asked for the tolerant reader in this subjob"
        if "reject" in self.wired:
            return {}, "its reject output is wired, and a rejected row carries its fields as they stand in the file"
        if self.config["footer_rows"] > 0:
            # Polars parses the lines after the last row it is asked for: a footer would fail it every time.
            return {}, "the file has a footer, and Polars would parse its lines as numbers too"
        kinds = {"int": pl.Int64, "float": pl.Float64}
        native = {column.name: kinds[column.type] for column in self.schema if column.type in kinds}
        return native, "" if native else "no column is declared int or float"

    def _fields(self, source: str, names: List[str], native: Dict[str, pl.DataType]) -> pl.LazyFrame:
        """The file's fields as columns, split by Polars: text, except the columns it parses itself."""
        config = self.config
        csv = config["csv_option"]

        def scan(rows: Optional[int], types: Dict[str, pl.DataType]) -> pl.LazyFrame:
            return pl.scan_csv(
                source,
                separator=config["delimiter"][0] if csv else config["delimiter"],
                has_header=False,
                schema={name: types.get(name, pl.String) for name in names},
                quote_char=config["text_enclosure"] if csv else None,
                skip_rows=config["header_rows"],
                n_rows=rows,
                eol_char=_ROW_SEPARATORS[config["csv_row_separator" if csv else "row_separator"]],
                encoding="utf8-lossy",
                empty_string_is_null=False,
                truncate_ragged_lines=True,
                raise_if_empty=False,
                glob=False,
                # Numbered where the file is read: a row keeps its place in the file whatever is dropped after.
                row_index_name=self.row_number,
                row_index_offset=1,
            )

        rows = config["limit"]
        if config["footer_rows"] > 0:
            # The footer is counted in lines from the end, so the file's length is needed first. Where fields
            # may be enclosed, every field is read for it, as the job's pass reads them: Polars' quick row
            # count takes an enclosure that does not pair up for a row that goes on, and the rows after it
            # would be dropped without a word. Read in full, such a file fails here.
            if csv:
                read = scan(None, {}).select(pl.len(), *[pl.col(name).null_count() for name in names])
                total = read.collect(engine="streaming").row(0)[0]
            else:
                total = scan(None, {}).select(pl.len()).collect().item()
            kept = max(total - config["footer_rows"], 0)
            rows = kept if rows is None else min(rows, kept)
        return scan(rows, native)

    def _lines(self, source: str, names: List[str]) -> pl.LazyFrame:
        """The file's fields as text columns, split here: slower, but any delimiter and the field count."""
        config = self.config
        lines = pl.scan_lines(source, name=_LINE, glob=False, row_index_name=self.row_number, row_index_offset=1)
        length: Optional[int] = None
        if config["footer_rows"] > 0:
            total = lines.select(pl.len()).collect().item()
            length = max(total - config["header_rows"] - config["footer_rows"], 0)
        lines = lines.slice(config["header_rows"], length)
        text = pl.col(_LINE).str.strip_prefix("\ufeff")
        delimiter = config["delimiter"]
        # What pandas, which reads the file for v1, takes for a blank line and never for a row.
        if len(delimiter) > 1:
            # It also strips a line before a separator of several characters splits it.
            text = text.str.strip_chars()
            blank = text == ""
        elif len(delimiter.encode()) > 1:
            blank = text.str.strip_chars() == ""
        else:
            blank = text.str.strip_chars(" \t".replace(delimiter, "")) == ""
        lines = lines.filter(~blank)
        if config["limit"] is not None:
            lines = lines.head(config["limit"])
        parts = text.str.split_exact(delimiter, len(names) - 1).struct.rename_fields(names)
        frame = lines.select(
            (text.str.count_matches(delimiter, literal=True) + 1).alias(_FIELDS), parts.alias("__row"),
            # The scan numbered every line of the file; a row's number counts from the first line after the header.
            pl.col(self.row_number) - config["header_rows"],
        ).unnest("__row")
        return frame.with_columns([pl.col(name).fill_null("") for name in names])

    def _trimmed(self) -> List[str]:
        text = [column.name for column in self.schema if column.type == "str"]
        if self.config["trim_all"]:
            return text
        asked = {entry["column"] for entry in self.config["trim_select"] if entry["trim"]}
        return [name for name in text if name in asked]

    # ------------------------------------------------------------------
    # Text to the declared types, and what could not be read
    # ------------------------------------------------------------------

    def _typed(
        self, frame: pl.LazyFrame, names: List[str], native: Dict[str, pl.DataType]
    ) -> Dict[str, pl.LazyFrame]:
        typed = [column for column in self.schema if column.type != "str"]
        counted = self.config["check_fields_num"] and not self.config["csv_option"]
        carried = [self.row_number] + [expr.meta.output_name() for expr in self.key_copies()]
        if not typed and not counted:
            return {"main": frame.select(names + carried), "reject": self._no_rejects(names)}

        # Each field read as text is parsed once: the parsed column gives the value and tells an unreadable field.
        frame = frame.with_columns([
            parse_text(pl.col(column.name), column).alias(_VALUE + column.name)
            for column in typed if column.name not in native
        ])

        def value(column: Column) -> pl.Expr:
            parsed = pl.col(column.name) if column.name in native else pl.col(_VALUE + column.name)
            return finish_value(parsed, pl.col(column.name), column)

        flags = []
        for column in typed:
            if column.name not in native:
                flags.append(unreadable(pl.col(_VALUE + column.name), pl.col(column.name), column))
            if not column.nullable:
                flags.append(value(column).is_null())
        if counted:
            flags.append(pl.col(_FIELDS) != len(names))
        held = {column.name: column for column in typed}
        values = [value(held[name]).alias(name) if name in held else pl.col(name) for name in names]
        if not flags:
            # Polars parsed every typed column and none may not be missing: no row can be rejected here.
            return {"main": frame.select(values + carried), "reject": self._no_rejects(names)}

        flagged = frame.with_columns(pl.any_horizontal(flags).alias(_BAD))
        main = flagged.filter(~pl.col(_BAD)).select(values + carried)
        code, message = self._reasons(typed, counted, len(names), native)
        reason = {"errorCode": code.alias("errorCode"), "errorMessage": message.alias("errorMessage")}
        # A data column with one of the two names gives its place to the reason, as in v1.
        reject = flagged.filter(pl.col(_BAD)).select(
            *[reason.get(name, pl.col(name).cast(pl.String)) for name in names],
            *[expr for name, expr in reason.items() if name not in names],
            *carried,
        )
        if self.config["die_on_error"]:
            self.check(
                reject.select(pl.len().alias("rows"), pl.col("errorMessage").first().alias("why"), *first_of(reject)),
                lambda found: fatal(found, self.where(found)),
            )
        return {"main": main, "reject": reject}

    @staticmethod
    def _no_rejects(names: List[str]) -> pl.LazyFrame:
        return pl.LazyFrame(schema={name: pl.String for name in names + ["errorCode", "errorMessage"]})

    def declared_outputs(self) -> Dict[str, pl.LazyFrame]:
        if not self.schema:
            return {}
        names = [column.name for column in self.schema]
        return {"main": pl.LazyFrame(schema=polars_schema(self.schema)), "reject": self._no_rejects(names)}

    @staticmethod
    def _reasons(
        typed: List[Column], counted: bool, width: int, native: Dict[str, pl.DataType]
    ) -> Tuple[pl.Expr, pl.Expr]:
        """Why a row was rejected: the first thing wrong with it, in v1's words."""
        cases: List[Tuple[pl.Expr, str, pl.Expr]] = []
        if counted:
            cases.append((
                pl.col(_FIELDS) != width,
                "FIELD_COUNT",
                pl.format(f"Field count mismatch: expected {width}, got {{}} - Line: {{}}", pl.col(_FIELDS), pl.col(_LINE)),
            ))
        for column in typed:
            if column.name not in native:
                wrong = unreadable(pl.col(_VALUE + column.name), pl.col(column.name), column)
                cases.append((wrong, "TYPE_CONVERSION", pl.format(unreadable_text(column), pl.col(column.name))))
        for column in typed:
            if not column.nullable:
                parsed = pl.col(column.name) if column.name in native else pl.col(_VALUE + column.name)
                cases.append((
                    finish_value(parsed, pl.col(column.name), column).is_null(),
                    "SCHEMA_VIOLATION",
                    pl.lit(f"Column '{column.name}': non-nullable column has null"),
                ))
        code = pl.coalesce([pl.when(wrong).then(pl.lit(name)) for wrong, name, _ in cases])
        message = pl.coalesce([pl.when(wrong).then(text) for wrong, _, text in cases])
        return code, message


def unreadable_text(column: Column) -> str:
    """The message for text that is not the column's type; ``{}`` stands for the text."""
    name = column.name.replace("{", "{{").replace("}", "}}")
    if column.type in ("int", "float"):
        return f"Column '{name}': could not convert string to float: '{{}}'"
    if column.type == "bool":
        return f"Column '{name}': Cannot convert '{{}}' to bool"
    if column.type == "Decimal":
        return f"Column '{name}': could not convert string to Decimal: '{{}}'"
    pattern = (column.date_pattern or "any known date format").replace("{", "{{").replace("}", "}}")
    return f"Column '{name}': time data '{{}}' does not match format '{pattern}'"


def fatal(found: pl.DataFrame, where: str = "") -> Optional[str]:
    """What a reader fails with when rows could not be read: how many, the first one's fault, and where it is."""
    rows = found["rows"].item()
    return f"Schema/coercion failed for {rows} row(s); first error: {found['why'].item()}{where}" if rows else None
