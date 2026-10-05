"""Delimited file input: read a delimited text file as rows."""
from __future__ import annotations

from typing import Dict

import polars as pl

from ...errors import ConfigurationError
from ...job.keys import Key
from ...types import polars_schema
from ..base import Source
from ..registry import REGISTRY

_UTF8 = ("utf-8", "utf8")


def unescape(value: str) -> str:
    """Turn the two characters backslash-n (and -t, -r) into the one they mean."""
    return value.replace("\\r", "\r").replace("\\n", "\n").replace("\\t", "\t")


@REGISTRY.register
class FileInputDelimited(Source):
    """Read a delimited text file."""

    names = ("file_input_delimited", "FileInputDelimited", "tFileInputDelimited")
    outputs = {"main": ("flow", "main"), "reject": ("reject",)}
    keys = (
        Key("path", required=True, aliases=("filepath",), doc="The file to read."),
        Key("delimiter", default=";", aliases=("fieldseparator",), convert=unescape, doc="Field separator."),
        Key("row_separator", default="\\n", convert=unescape, doc="Row separator."),
        Key("header_rows", type=int, default=0, doc="Lines to skip at the top of the file."),
        Key("footer_rows", type=int, default=0, doc="Lines to skip at the end of the file."),
        Key("limit", type=int, doc="The most rows to read."),
        Key("encoding", default="ISO-8859-15", doc="The file's character encoding."),
        Key("csv_option", type=bool, default=False, doc="Whether fields may be quoted."),
        Key("remove_empty_row", type=bool, default=True, doc="Whether blank lines are dropped."),
        Key("die_on_error", type=bool, default=False, doc="Whether a bad row stops the job."),
    )

    def read(self) -> Dict[str, pl.LazyFrame]:
        config = self.config
        if config["encoding"].lower() not in _UTF8:
            raise ConfigurationError(f"encoding: '{config['encoding']}' is not built yet")
        frame = pl.scan_csv(
            config["path"],
            separator=config["delimiter"],
            has_header=False,
            skip_rows=config["header_rows"],
            schema=polars_schema(self.schema),
            quote_char=None,
            n_rows=config["limit"],
        )
        return {"main": frame}
