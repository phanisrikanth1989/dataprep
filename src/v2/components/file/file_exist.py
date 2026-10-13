"""File exist: whether a file is there is left in globalMap."""
from __future__ import annotations

import os
from typing import List

from ...job.keys import Key, Kind
from ..base import Action
from ..registry import REGISTRY


@REGISTRY.register
class FileExist(Action):
    """Look whether the path is there, and leave the answer in globalMap as `<id>_EXISTS`.

    A file or a folder counts as there; with `check_directory` only a
    folder does. The path looked at is left as `<id>_FILENAME`. It counts
    one row, as in v1. No flow comes to it or leaves it: a trigger's
    condition reads the answer (`((Boolean)globalMap.get("<id>_EXISTS"))`).
    """

    names = ("file_exist", "FileExistComponent", "FileExist", "tFileExist")
    keys = (
        Key("path", required=True, aliases=("file_name", "file_path", "FILE_NAME"), doc="The file or folder to look for."),
        Key("check_directory", type=bool, default=False, doc="Whether only a folder counts as there."),
        Key("die_on_error", kind=Kind.IGNORED, type=object, doc="Nothing here can fail; v1 reads it on every component."),
    )

    def problems(self) -> List[str]:
        return [] if self.config["path"] else ["path: there is no path to look for"]

    def act(self) -> None:
        path = self.config["path"]
        there = os.path.isdir(path) if self.config["check_directory"] else os.path.exists(path)
        self.global_map.update({
            f"{self.id}_EXISTS": there, f"{self.id}_FILENAME": path,
            f"{self.id}_NB_LINE": 1, f"{self.id}_NB_LINE_OK": 1, f"{self.id}_NB_LINE_REJECT": 0,
        })
