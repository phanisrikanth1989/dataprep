"""Delimited file output: write rows to a delimited text file."""
from __future__ import annotations

import os

import polars as pl

from ...job.keys import Key
from ..base import Sink, Write
from ..registry import REGISTRY
from .file_input_delimited import unescape


@REGISTRY.register
class FileOutputDelimited(Sink):
    """Write rows to a delimited text file."""

    names = ("file_output_delimited", "FileOutputDelimited", "tFileOutputDelimited")
    keys = (
        Key("path", required=True, aliases=("filepath",), doc="The file to write."),
        Key("delimiter", default=";", aliases=("fieldseparator",), convert=unescape, doc="Field separator."),
        Key("row_separator", default="\\n", convert=unescape, doc="Row separator."),
        Key("encoding", default="ISO-8859-15", doc="The file's character encoding."),
        Key("include_header", type=bool, default=False, doc="Whether a header line is written."),
        Key("append", type=bool, default=False, doc="Whether rows are added to an existing file."),
        Key("create_directory", type=bool, default=True, doc="Whether a missing folder is created."),
        Key("csv_option", type=bool, default=False, doc="Whether fields are quoted when needed."),
        Key("os_line_separator", type=bool, default=True, doc="Whether the operating system's line ending is used."),
        Key("file_exist_exception", type=bool, default=True, doc="Whether an existing file stops the job."),
    )

    def write(self, frame: pl.LazyFrame) -> Write:
        config = self.config
        path = config["path"]
        folder = os.path.dirname(path)
        if folder and config["create_directory"]:
            os.makedirs(folder, exist_ok=True)
        terminator = os.linesep if config["os_line_separator"] else config["row_separator"]
        header = config["include_header"] and not (config["append"] and os.path.exists(path))

        def sink(target: str) -> pl.LazyFrame:
            return frame.sink_csv(
                target,
                separator=config["delimiter"],
                include_header=header,
                line_terminator=terminator,
                quote_style="never",
                lazy=True,
            )

        return Write(path=path, sink=sink, rows=frame.select(pl.len()), append=config["append"])
