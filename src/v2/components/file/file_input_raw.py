"""Raw file input: a whole file as one value."""
from __future__ import annotations

import os
from typing import Dict, List, Optional

import polars as pl

from ...column_types import held_frame, polars_schema
from ...errors import ConfigurationError
from ...files import codec_name
from ...job.keys import Key, Kind
from ...job.model import Column
from ...rows import hidden, visible
from ..base import DIE_ON_ERROR, Source
from ..registry import REGISTRY
from .file_input_delimited import encoding
from .file_row_count import unreadable

_MB = 1024 * 1024
_INSTEAD = "read the file as text, or hand its path to the component that needs it"


def _limit(value: int) -> int:
    if value < 1:
        raise ValueError(f"{value} megabytes is no size to hold a file to; give 1 or more")
    return value


@REGISTRY.register
class FileInputRaw(Source):
    """Hand on one row whose one column holds the whole text of the file `filename`.

    The text is as the file has it: its line ends are kept, and a byte
    order mark at its start is no part of it. It is read in `encoding`,
    and a byte that is no character there fails the job, with the byte's
    place. The column has the name the job declares, and `content` when it
    declares none.

    The whole file is held in memory as one value, and about three times
    over while it is read. That is what the component is for, and why it
    reads no file larger than `size_limit_mb`. A file to be gone through
    row by row is a reader's.

    A file that cannot be read fails the job. When the job config says
    `die_on_error` is off, the job goes on with no row and a warning, and
    why is in `<id>_ERROR_MESSAGE`. The path of a file that was read is
    left in `<id>_FILENAME_PATH`.
    """

    names = ("file_input_raw", "FileInputRaw", "tFileInputRaw")
    keys = (
        Key("filename", required=True, doc="The file to read."),
        Key("encoding", default="ISO-8859-15", convert=encoding, doc="The file's character encoding."),
        Key("size_limit_mb", type=int, default=1024, convert=_limit,
            doc="The largest file that is read, in megabytes; a larger one is not read at all."),
        DIE_ON_ERROR,
        Key("as_string", kind=Kind.IGNORED, type=object, doc="The file is always handed on as text."),
        Key("as_bytearray", kind=Kind.REFUSED, type=bool, reason=f"v2 has no column type that holds bytes: {_INSTEAD}"),
        Key("as_inputstream", kind=Kind.REFUSED, type=bool,
            reason=f"v2 hands on values and not open files: {_INSTEAD}"),
    )

    def problems(self) -> List[str]:
        found = [] if self.config["filename"].strip() else ["filename: there is no file named"]
        if len(self.schema) > 1:
            found.append(f"schema: a raw file input hands on one column, the file's text; {len(self.schema)} are declared")
        return found

    def declared_outputs(self) -> Dict[str, pl.LazyFrame]:
        # The column is known also when the job declares none, so what follows can be checked at load.
        return {"main": pl.LazyFrame(schema=polars_schema([self._column()]))}

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def read(self) -> Dict[str, pl.LazyFrame]:
        made = self.run_context.made
        if self.id not in made:
            # Once in a run, however often the engine reads the source.
            made[self.id] = (self._held(),)
        text = made[self.id][0]
        column = self._column()
        rows = [] if text is None else [{column.name: text}]
        # One row at most: a run for picked rows has it or fails before it comes here, so there is nothing to
        # pick among.
        frame = held_frame([column], rows).with_columns(pl.Series(self.row_number, [1] * len(rows), dtype=pl.UInt32))
        frame = frame.with_columns(self.key_copies())
        return {"main": frame.select(visible(frame.columns) + hidden(frame.columns)).lazy()}

    def locate(self, number: int) -> str:
        return f"the content of {self.config['filename']}"

    @property
    def place_kind(self) -> str:
        return "rows"

    @property
    def place_why(self) -> str:
        return "hands on one row, the content of its file"

    def _column(self) -> Column:
        return self.schema[0] if self.schema else Column("content", "str")

    def _held(self) -> Optional[str]:
        """The file's text; None when it cannot be read and the job is to go on."""
        try:
            text = self._text()
        except ConfigurationError as exc:
            if not self.goes_on_after(str(exc), " with no row"):
                raise
            return None
        self.global_map[f"{self.id}_FILENAME_PATH"] = self.config["filename"]
        return text

    def _text(self) -> str:
        config = self.config
        path, limit = config["filename"], config["size_limit_mb"]
        if not os.path.exists(path):
            raise ConfigurationError(f"File not found: '{path}'")
        try:
            with open(path, "rb") as handle:
                size = os.fstat(handle.fileno()).st_size
                if size > limit * _MB:
                    raise ConfigurationError(
                        f"'{path}' holds {size} bytes, more than the {limit} MB a raw file input reads by "
                        "`size_limit_mb`: the whole file would be held in memory as one value"
                    )
                data = handle.read()
        except OSError as exc:
            raise ConfigurationError(f"'{path}' cannot be read: {unreadable(path, exc)}") from None
        try:
            text = data.decode(codec_name(config["encoding"]))
        except UnicodeDecodeError as exc:
            line = data.count(b"\n", 0, exc.start) + 1
            raise ConfigurationError(
                f"'{path}' is not written in {config['encoding']}: byte {exc.start + 1} of it, on line {line}, "
                "is no character there"
            ) from None
        # A byte order mark says how the file is written; it is no part of what is written.
        return text.removeprefix("\ufeff")
