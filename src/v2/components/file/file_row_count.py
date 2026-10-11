"""File row count: the rows of a file are counted, and the count is left in globalMap."""
from __future__ import annotations

import logging
import os
from typing import List, Tuple

from ...errors import ConfigurationError
from ...files import codec_name
from ...job.keys import Key
from ..base import Action
from ..registry import REGISTRY
from .file_input_delimited import encoding, unescape

logger = logging.getLogger(__name__)

_LINE_ENDS = ("\n", "\r\n", "\r")


def _separator(value: str) -> str:
    value = unescape(value)
    if not value:
        raise ValueError("a separator of nothing ends no row")
    return value


@REGISTRY.register
class FileRowCount(Action):
    """Count the rows of a file and leave the count in globalMap as `<id>_COUNT`.

    With a row separator that is a line end (`\\n`, `\\r\\n`, `\\r`), every
    kind of line end ends a row, a last row needs none, and an empty file
    has no row. Any other separator splits the whole text, and what
    follows the last separator is a row unless it is empty. With
    `ignore_empty_row` a row of nothing but blanks is not counted.

    Beside `<id>_COUNT` it leaves `<id>_NB_LINE` (the rows found),
    `<id>_NB_LINE_OK` (those counted) and `<id>_NB_LINE_REJECT` (those not
    counted), as in v1. No flow comes to it or leaves it.
    """

    names = ("file_row_count", "FileRowCount", "tFileRowCount")
    keys = (
        Key("path", required=True, aliases=("filename",), doc="The file whose rows are counted."),
        Key("row_separator", default="\n", convert=_separator, doc="What ends a row."),
        Key("ignore_empty_row", type=bool, default=False, doc="Whether a row of nothing but blanks is not counted."),
        Key("encoding", default="ISO-8859-15", convert=encoding, doc="The file's character encoding."),
    )

    def problems(self) -> List[str]:
        return [] if self.config["path"] else ["path: the file to count has no name"]

    def act(self) -> None:
        config = self.config
        path = config["path"]
        if not os.path.exists(path):
            raise ConfigurationError(f"File not found: '{path}'")
        try:
            found, counted = self._counted(path)
        except UnicodeDecodeError:
            raise ConfigurationError(f"'{path}' is not written in {config['encoding']}: a byte in it is no character there") from None
        logger.info(f"[{self.id}] counted {counted} row(s) of {found} in {path}")
        entries = {"COUNT": counted, "NB_LINE": found, "NB_LINE_OK": counted, "NB_LINE_REJECT": found - counted}
        for name, value in entries.items():
            self.global_map[f"{self.id}_{name}"] = value

    def _counted(self, path: str) -> Tuple[int, int]:
        """How many rows the file has, and how many of them count."""
        config = self.config
        name, separator = codec_name(config["encoding"]), config["row_separator"]
        found = counted = 0
        if separator in _LINE_ENDS:
            # Line by line, every kind of line end ending one: the file is never held whole.
            with open(path, "r", encoding=name) as handle:
                for line in handle:
                    found += 1
                    counted += not (config["ignore_empty_row"] and not line.strip())
            return found, counted
        with open(path, "r", encoding=name, newline="") as handle:
            rows = handle.read().split(separator)
        if rows and rows[-1] == "":
            rows.pop()
        for row in rows:
            found += 1
            counted += not (config["ignore_empty_row"] and not row.strip())
        return found, counted
