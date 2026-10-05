"""Delimited file output: write rows to a delimited text file."""
from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

import polars as pl

from ...errors import ConfigurationError
from ...files import count_occurrences, put_text_in_place
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
        if exists and config["file_exist_exception"] and not config["append"]:
            raise ConfigurationError(
                f"File already exists: '{path}'. Set file_exist_exception=false or append=true to allow writing."
            )
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
        if len(delimiter.encode()) == 1:
            out = frame.select(columns)
        else:
            # Polars separates fields with one byte; any other separator is put in by hand.
            texts = [column.cast(pl.String).fill_null("") for column in columns]
            out = frame.select(pl.concat_str(texts, separator=delimiter).alias(delimiter.join(types.names())))
            delimiter = "\x1f"

        def sink(target: str) -> pl.LazyFrame:
            return out.sink_csv(
                target,
                separator=delimiter,
                include_header=header,
                line_terminator=terminator,
                quote_char=config["text_enclosure"] if csv else '"',
                quote_style="always" if csv else "never",
                lazy=True,
            )

        def count(written: str) -> int:
            """Rows in the written file, not counting the header line."""
            if csv and terminator in ("\n", "\r\n", "\r"):
                # Fields may hold line breaks inside their enclosures: let Polars tell rows apart.
                lines = pl.scan_csv(
                    written, separator=delimiter, has_header=False, quote_char=config["text_enclosure"],
                    eol_char="\r" if terminator == "\r" else "\n", infer_schema=False, raise_if_empty=False,
                ).select(pl.len()).collect().item()
            else:
                lines = count_occurrences(written, terminator.encode("utf-8")) if terminator else 0
            return max(lines - (1 if header else 0), 0)

        def place(written: str, rows: Optional[int]) -> None:
            if not rows and (config["append"] or config["delete_empty_file"]):
                os.remove(written)
                if not config["append"] and os.path.exists(path):
                    os.remove(path)
                return
            put_text_in_place(written, path, config["encoding"], config["append"])

        return Write(path=path, sink=sink, count=count, append=config["append"], place=place)


def _as_written(name: str, dtype: pl.DataType, declared: Optional[Column]) -> pl.Expr:
    """A column as it goes to the file. Text and numbers are left for Polars to write."""
    column = pl.col(name)
    if dtype == pl.String or dtype.is_integer():
        return column
    if dtype.is_float():
        return column.fill_nan(None)
    if dtype == pl.Boolean and declared is not None and declared.type == "bool":
        return column
    return to_text(column, dtype, declared).alias(name)
