"""File touch: a file is made, or the time it was changed is set to now."""
from __future__ import annotations

import logging
import os
from typing import List

from ...errors import ConfigurationError
from ...job.keys import Key
from ..base import DIE_ON_ERROR, FAULTS, Action, one_line
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register
class FileTouch(Action):
    """Make the file `filename` empty when it is not there, and set the time it was changed to now when it is.

    What a file holds is never touched. A folder that is there has its
    time set as well. The folder the file is to stand in has to be there,
    unless `createdir` is on. The path is left in globalMap as
    `<id>_FILENAME`, and it counts one row. No flow comes to it or leaves
    it. What cannot be done fails the job.
    """

    names = ("file_touch", "FileTouch", "tFileTouch")
    keys = (
        Key("filename", required=True, aliases=("FILENAME",), doc="The file to make, or whose time is set to now."),
        Key("createdir", type=bool, default=False, aliases=("create_directory",),
            doc="Whether the folder the file is to stand in is made when it is not there."),
        DIE_ON_ERROR,
    )

    def problems(self) -> List[str]:
        return [] if self.config["filename"].strip() else ["filename: there is no file named"]

    def act(self) -> None:
        try:
            self._touch()
        except FAULTS as exc:
            self.fail_or_go_on(exc)
            self.global_map.update({f"{self.id}_NB_LINE": 1, f"{self.id}_NB_LINE_OK": 0, f"{self.id}_NB_LINE_REJECT": 1})

    def _touch(self) -> None:
        path = self.config["filename"]
        folder = os.path.dirname(path)
        made_folder = False
        try:
            if folder and not os.path.exists(folder):
                if not self.config["createdir"]:
                    raise ConfigurationError(f"the folder '{folder}' is not there, and is not to be made")
                os.makedirs(folder, exist_ok=True)
                made_folder = True
            try:
                # Made only if nothing is there, in one step: what another job made meanwhile keeps what it
                # holds, and nothing is made through a link.
                with open(path, "xb"):
                    made = True
            except (FileExistsError, IsADirectoryError):
                made = False
            os.utime(path, None)
        except OSError as exc:
            said = (exc.strerror or str(exc)).lower()
            raise ConfigurationError(f"'{path}' cannot be touched: {said}") from None
        if made:
            done = f"made '{path}', an empty file"
        elif made_folder:
            done = f"made the folder '{path}'"
        else:
            done = f"'{path}' was there; its time is set to now"
        logger.info(one_line(f"[{self.id}] {done}"))
        self.global_map.update({
            f"{self.id}_FILENAME": path,
            f"{self.id}_NB_LINE": 1, f"{self.id}_NB_LINE_OK": 1, f"{self.id}_NB_LINE_REJECT": 0,
        })
