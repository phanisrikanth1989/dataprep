"""Delimited file output: write rows to a delimited text file."""
from __future__ import annotations

import logging
import os
from typing import List, Optional

import polars as pl

from ...errors import ConfigurationError
from ...files import encoded, put_in_place, to_encoding
from ...job.keys import Key, Kind
from ...job.model import Column
from ...types import to_text
from ..base import Sink, Write
from ..registry import REGISTRY
from .file_input_delimited import encoding, unescape

logger = logging.getLogger(__name__)

_WHOLE_ESCAPES = {"\\n": "\n", "\\r": "\r", "\\t": "\t", "\\r\\n": "\r\n"}
_CSV_ROW_SEPARATORS = {"LF": "\n", "CR": "\r", "CRLF": "\r\n"}


def _row_separator(value: str) -> str:
    """v1 translates an escape only when it is the whole value."""
    return _WHOLE_ESCAPES.get(value, value)


def _csv_row_separator(value: str) -> str:
    return _CSV_ROW_SEPARATORS.get(value, _row_separator(value))


@REGISTRY.register
class FileOutputDelimited(Sink):
    """Write rows to a delimited text file.

    Columns are written in the order they arrive. The component's declared
    input columns decide how a value is written: a date by its pattern, a
    Decimal to its declared places.
    """

    names = ("file_output_delimited", "FileOutputDelimited", "tFileOutputDelimited")
    keys = (
        Key("path", required=True, aliases=("filepath",), doc="The file to write."),
        Key("delimiter", default=";", aliases=("fieldseparator",), convert=unescape,
            doc="What separates fields. With `csv_option` only its first character is used."),
        Key("row_separator", default="\n", convert=_row_separator,
            doc="What ends a row when `csv_option` and `os_line_separator` are off."),
        Key("csv_row_separator", default="\n", aliases=("csvrowseparator",), convert=_csv_row_separator,
            doc="What ends a row when `csv_option` is on and `os_line_separator` off: LF, CR, CRLF or the text itself."),
        Key("os_line_separator", type=bool, default=True,
            doc="Whether rows end the way the operating system ends lines, whatever the separator keys say."),
        Key("encoding", default="ISO-8859-15", convert=encoding, doc="The file's character encoding."),
        Key("include_header", type=bool, default=False,
            doc="Whether the column names are written first. When appending, only into a new or empty file."),
        Key("append", type=bool, default=False, doc="Whether rows are added to an existing file."),
        Key("create_directory", type=bool, default=True, doc="Whether a missing folder is created."),
        Key("csv_option", type=bool, default=False, doc="Whether every field is enclosed."),
        Key("text_enclosure", default='"', doc="The character that encloses a field when `csv_option` is on."),
        Key("escape_char", default='"',
            doc="Must equal `text_enclosure`: an enclosure inside a field is written twice."),
        Key("file_exist_exception", type=bool, default=True,
            doc="Whether an existing file fails the job (unless `append` is on)."),
        Key("delete_empty_file", type=bool, default=False,
            doc="Whether no file is left, and an existing one removed, when there are no rows."),
        Key("split", kind=Kind.REFUSED, type=bool, reason="writing one flow to several files is not built yet",
            doc="Split the output into files of `split_every` rows."),
        Key("split_every", kind=Kind.IGNORED, type=object, doc="Only read by `split`."),
        Key("die_on_error", kind=Kind.IGNORED, type=object, doc="A file that cannot be written always fails the job."),
        Key("compress", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well."),
        Key("usestream", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well."),
        Key("streamname", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well."),
        Key("advanced_separator", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well."),
        Key("thousands_separator", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well."),
        Key("decimal_separator", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well."),
        Key("flushonrow", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well."),
        Key("flush_row_count", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well."),
        Key("row_mode", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well."),
    )

    def problems(self) -> List[str]:
        config, found = self.config, []
        if config["csv_option"]:
            if len(config["text_enclosure"]) != 1:
                found.append("text_enclosure: must be one character")
            elif config["escape_char"] not in (config["text_enclosure"], ""):
                found.append("escape_char: v2 writes an enclosure inside a field by writing it twice, nothing else")
            if len(config["delimiter"][:1].encode()) != 1:
                found.append("delimiter: with csv_option, v2 writes a separator of one byte only")
        return found

    def write(self, frame: pl.LazyFrame) -> Write:
        config = self.config
        path = config["path"]
        folder = os.path.dirname(path)
        if folder and config["create_directory"]:
            os.makedirs(folder, exist_ok=True)
        if folder and not os.path.isdir(folder):
            raise ConfigurationError(f"Failed to write file '{path}': folder '{folder}' does not exist")
        exists = os.path.exists(path)
        refuses_existing = None
        if config["file_exist_exception"] and not config["append"]:
            refuses_existing = (
                f"File already exists: '{path}'. Set file_exist_exception=false or append=true to allow writing."
            )
            if exists:
                raise ConfigurationError(refuses_existing)
        # When appending, a header goes into a new or empty file only. The plan writes it when the file is one
        # now; an earlier output of the same subjob may still write the file first, so it is settled for good
        # when the file is put in place.
        header = config["include_header"] and not (config["append"] and exists and os.path.getsize(path) > 0)
        csv = config["csv_option"]
        delimiter = config["delimiter"][:1] if csv else config["delimiter"]
        if config["os_line_separator"]:
            terminator = os.linesep
        else:
            terminator = config["csv_row_separator"] if csv else config["row_separator"]

        declared = {column.name: column for column in self.input_schema}
        types = frame.collect_schema()
        columns = [_as_written(name, types[name], declared.get(name)) for name in types.names()]
        if not columns:
            # A flow with no columns has nothing to write, not even a header: the file is left empty.
            header, out = False, pl.LazyFrame(schema={"nothing": pl.String})
        elif len(delimiter.encode()) == 1:
            out = frame.select(columns)
        else:
            # Polars separates fields with one byte; any other separator is put in by hand.
            texts = [column.cast(pl.String).fill_null("") for column in columns]
            out = frame.select(pl.concat_str(texts, separator=delimiter).alias(delimiter.join(types.names())))
            delimiter = "\x1f"

        style = {
            "separator": delimiter,
            "line_terminator": terminator,
            "quote_char": config["text_enclosure"] if csv else '"',
            "quote_style": "always" if csv else "never",
        }

        def sink(target: str) -> pl.LazyFrame:
            return out.sink_csv(target, include_header=header, lazy=True, **style)

        keeps_nothing = config["append"] or config["delete_empty_file"]
        # What is settled once the file is written: its byte order mark, and its header line as bytes.
        settled = {"mark": b"", "header": b""}

        def ready(written: str, rows: int) -> None:
            if not rows and keeps_nothing:
                return
            if config["append"] and config["include_header"] and columns:
                line = pl.DataFrame(schema=out.collect_schema()).write_csv(include_header=True, **style)
                settled["header"] = encoded(line, config["encoding"])
            settled["mark"] = to_encoding(written, config["encoding"])

        def place(written: str, rows: int) -> None:
            if not rows and keeps_nothing:
                os.remove(written)
                if not config["append"] and os.path.exists(path):
                    os.remove(path)
                return
            held = header and bool(settled["header"])
            put_in_place(written, path, config["append"], settled["mark"], settled["header"], held)

        return Write(
            path=path, sink=sink, append=config["append"], ready=ready, place=place,
            refuses_existing=refuses_existing, empty_leaves_none=keeps_nothing,
        )


def _as_written(name: str, dtype: pl.DataType, declared: Optional[Column]) -> pl.Expr:
    """A column as it goes to the file. Text and whole numbers are left for Polars to write."""
    column = pl.col(name)
    if dtype == pl.String or dtype.is_integer():
        return column
    if dtype == pl.Boolean and declared is not None and declared.type == "bool":
        return column
    return to_text(column, dtype, declared).alias(name)
