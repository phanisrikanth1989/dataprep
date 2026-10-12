"""File properties: one row that says what a file is."""
from __future__ import annotations

import hashlib
import os
import stat
import time
from typing import Any, Dict, List

import polars as pl

from ...column_types import held_frame, polars_schema
from ...errors import ConfigurationError
from ...job.keys import Key
from ...job.model import Column
from ...rows import hidden, visible
from ..base import Source
from ..registry import REGISTRY

_CHUNK = 1 << 22
# What can be asked of a file, and the type each is when the job declares no other.
_KNOWN = {
    "abs_path": "str", "dirname": "str", "basename": "str", "mode_string": "str", "size": "int", "mtime": "int",
    "mtime_string": "str", "md5": "str", "sha256": "str", "exists": "bool", "type": "str",
}
_TALEND = ("abs_path", "dirname", "basename", "mode_string", "size", "mtime", "mtime_string")
_CHECK_SUMS = ("md5", "sha256")


@REGISTRY.register
class FileProperties(Source):
    """Hand on one row that says what the file `filename` is, by the columns the output schema declares.

    A column is one of: `abs_path` (the path in full), `dirname` (the
    folder it is in, in full), `basename` (its name), `mode_string` (its
    permissions as `ls -l` shows them, `-rw-r--r--`), `size` (bytes),
    `mtime` (when it was last changed, in milliseconds since 1970),
    `mtime_string` (the same in local time, `2026-10-12 14:03:05`), `md5`
    and `sha256` (check sums of what it holds), `type` (`file` or
    `folder`) and `exists`. A job that declares no columns gets the seven
    Talend's component has, and `md5` as an eighth when `md5` is on.

    A file that is not there fails the job, unless `exists` is among the
    columns: the row then says false there and holds nothing but the
    names. A link has the properties of what it leads to, and a folder has
    no check sum. A check sum is worked out only when its column is asked
    for, piece by piece: the file is never held in memory.
    """

    names = ("file_properties", "FileProperties", "tFileProperties")
    keys = (
        Key("filename", required=True, aliases=("FILENAME",), doc="The file, or the folder, to say the properties of."),
        Key("md5", type=bool, default=False, aliases=("MD5",),
            doc="Whether `md5` is a column when the job declares none. A column that is declared is always filled."),
    )

    def problems(self) -> List[str]:
        found = [] if self.config["filename"].strip() else ["filename: there is no file named"]
        unknown = [column.name for column in self.schema if column.name not in _KNOWN]
        if unknown:
            named = " or ".join(f"'{name}'" for name in unknown)
            found.append(f"schema: there is no property {named}: a column is one of {', '.join(_KNOWN)}")
        return found

    def declared_outputs(self) -> Dict[str, pl.LazyFrame]:
        # The columns are known also when the job declares none, so what follows can be checked at load.
        return {"main": pl.LazyFrame(schema=polars_schema(self._columns()))}

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def read(self) -> Dict[str, pl.LazyFrame]:
        made = self.run_context.made
        if self.id not in made:
            # Once in a run, however often the engine reads the source: a check sum of a large file takes long.
            made[self.id] = self._row()
        frame = held_frame(self._columns(), [made[self.id]])
        # One row: a run for picked rows has it or fails before it comes here, so there is nothing to pick among.
        frame = frame.with_columns(pl.Series(self.row_number, [1], dtype=pl.UInt32)).with_columns(self.key_copies())
        return {"main": frame.select(visible(frame.columns) + hidden(frame.columns)).lazy()}

    def locate(self, number: int) -> str:
        return f"the properties of {self.config['filename']}"

    @property
    def place_kind(self) -> str:
        return "rows"

    @property
    def place_why(self) -> str:
        return "hands on one row, the properties of its file"

    def _columns(self) -> List[Column]:
        """The columns handed on: the declared ones, or Talend's when the job declares none."""
        if self.schema:
            return self.schema
        names = _TALEND + (("md5",) if self.config["md5"] else ())
        return [Column(name, _KNOWN[name]) for name in names]

    def _row(self) -> Dict[str, Any]:
        """The file's properties, each under its name; only the check sums asked for are among them."""
        path = self.config["filename"]
        asked = [column.name for column in self._columns()]
        full = os.path.abspath(path)
        row: Dict[str, Any] = {
            "abs_path": full, "dirname": os.path.dirname(full), "basename": os.path.basename(full), "exists": True,
        }
        try:
            found = os.stat(path)
        except FileNotFoundError:
            if "exists" not in asked:
                raise ConfigurationError(f"File not found: '{path}'") from None
            row["exists"] = False
            return row
        except OSError as exc:
            raise ConfigurationError(f"'{path}' cannot be looked at: {_said(exc)}") from None
        folder = stat.S_ISDIR(found.st_mode)
        row.update({
            "mode_string": stat.filemode(found.st_mode), "size": found.st_size,
            "mtime": found.st_mtime_ns // 1_000_000,
            "mtime_string": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(found.st_mtime)),
            "type": "folder" if folder else "file",
        })
        wanted = [name for name in _CHECK_SUMS if name in asked]
        if wanted and not folder:
            row.update(self._check_sums(path, wanted))
        return row

    @staticmethod
    def _check_sums(path: str, wanted: List[str]) -> Dict[str, str]:
        """The check sums asked for, from one reading of the file."""
        # Not for security: a server that allows only approved algorithms still works out an md5 then.
        sums = {name: hashlib.new(name, usedforsecurity=False) for name in wanted}
        try:
            with open(path, "rb") as handle:
                while chunk := handle.read(_CHUNK):
                    for held in sums.values():
                        held.update(chunk)
        except OSError as exc:
            raise ConfigurationError(f"'{path}' cannot be read for its check sum: {_said(exc)}") from None
        return {name: held.hexdigest() for name, held in sums.items()}


def _said(error: OSError) -> str:
    return (error.strerror or type(error).__name__).lower()
