"""File copy: a file or a folder is copied, or moved."""
from __future__ import annotations

import logging
import os
import shutil
from typing import List

from ...errors import ConfigurationError
from ...job.keys import Key, Kind
from ..base import Action, one_line
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


@REGISTRY.register
class FileCopy(Action):
    """Copy the file `filename` into the folder `destination`, or a folder with everything in it.

    The file keeps its name, or takes `destination_rename` with `rename`
    on. With `enable_copy_directory` the folder `source_derectory`
    (Talend's spelling) is copied to `destination`. `create_directory`
    makes the folders that are missing. A file that is there is written
    over unless `replace_file` is off: then nothing is copied, and that is
    no fault. With `remove_file` the source is taken away once it has been
    copied. The time the file was changed is kept only with
    `preserve_last_modified_time`.

    A copy that fails leaves why in `<id>_ERROR_MESSAGE` and lets the job
    go on, unless `failon` (or `die_on_error`) is on. After a copy the
    path and name of the copy are in `<id>_DESTINATION_FILEPATH` and
    `<id>_DESTINATION_FILENAME`, the folders in `<id>_SOURCE_DIRECTORY`
    and `<id>_DESTINATION_DIRECTORY`, as Talend leaves them.
    """

    names = ("file_copy", "FileCopy", "tFileCopy")
    keys = (
        Key("filename", default="", aliases=("source",), doc="The file to copy."),
        Key("enable_copy_directory", type=bool, default=False, doc="Whether a folder is copied, not a file."),
        Key("source_derectory", default="", aliases=("source_directory",), doc="The folder to copy (Talend's spelling)."),
        Key("destination", required=True, doc="The folder the file goes into; for a folder, where its copy goes."),
        Key("rename", type=bool, default=False, doc="Whether the copy of a file takes another name."),
        Key("destination_rename", default="", aliases=("new_name",), doc="That name."),
        Key("remove_file", type=bool, default=False, doc="Whether the source is taken away once copied: a move."),
        Key("replace_file", type=bool, default=True, doc="Whether a file that is there is written over."),
        Key("create_directory", type=bool, default=True, doc="Whether folders that are missing are made."),
        Key("failon", type=bool, default=False, aliases=("fail_on_error",), doc="Whether a copy that fails fails the job."),
        Key("die_on_error", type=bool, default=False, doc="As `failon`."),
        Key("preserve_last_modified_time", type=bool, default=False, aliases=("preserve_last_modified",),
            doc="Whether the copy keeps the time the file was changed."),
        Key("force_copy_delete", kind=Kind.IGNORED, type=object,
            doc="Talend's other way of moving a file; the result is the same."),
    )

    def problems(self) -> List[str]:
        config, found = self.config, []
        source = "source_derectory" if config["enable_copy_directory"] else "filename"
        if not config[source]:
            found.append(f"{source}: there is nothing named to copy")
        if not config["destination"]:
            found.append("destination: there is nowhere named to copy to")
        if config["rename"] and not config["enable_copy_directory"] and not config["destination_rename"]:
            found.append("destination_rename: the copy is to take another name, and none is given")
        return found

    def act(self) -> None:
        held = self.global_map
        try:
            self._folder() if self.config["enable_copy_directory"] else self._file()
        except (ConfigurationError, OSError) as exc:
            why = str(exc) if isinstance(exc, ConfigurationError) else f"the copy failed: {exc.strerror or exc}"
            held.update({f"{self.id}_ERROR_MESSAGE": why, f"{self.id}_NB_LINE": 1, f"{self.id}_NB_LINE_OK": 0,
                         f"{self.id}_NB_LINE_REJECT": 1})
            if self.config["failon"] or self.config["die_on_error"]:
                raise ConfigurationError(why) from None
            logger.warning(one_line(f"[{self.id}] {why}; the job goes on"))
            return
        held.update({f"{self.id}_NB_LINE": 1, f"{self.id}_NB_LINE_OK": 1, f"{self.id}_NB_LINE_REJECT": 0})

    def _file(self) -> None:
        config = self.config
        source, folder = config["filename"], config["destination"]
        if not os.path.isfile(source):
            raise ConfigurationError(f"'{source}' is not there, or is no file")
        self._made(folder)
        name = config["destination_rename"] if config["rename"] else os.path.basename(source)
        target = os.path.join(folder, name)
        self.global_map.update({
            f"{self.id}_DESTINATION_FILEPATH": target, f"{self.id}_DESTINATION_FILENAME": name,
            f"{self.id}_SOURCE_DIRECTORY": os.path.dirname(source), f"{self.id}_DESTINATION_DIRECTORY": folder,
        })
        same = os.path.exists(target) and os.path.samefile(source, target)
        if same or (os.path.exists(target) and not config["replace_file"]):
            # As in Talend: nothing is copied, and that is no fault. The source stays, having no copy.
            logger.info(one_line(f"[{self.id}] '{target}' is there and is not written over; nothing is copied"))
            return
        (shutil.copy2 if config["preserve_last_modified_time"] else shutil.copy)(source, target)
        if config["remove_file"]:
            os.remove(source)

    def _folder(self) -> None:
        config = self.config
        source, target = config["source_derectory"], config["destination"]
        if not os.path.isdir(source):
            raise ConfigurationError(f"'{source}' is not there, or is no folder")
        self._made(os.path.dirname(target.rstrip("/" + os.sep)))
        self.global_map.update({f"{self.id}_SOURCE_DIRECTORY": source, f"{self.id}_DESTINATION_DIRECTORY": target})
        copier = shutil.copy2 if config["preserve_last_modified_time"] else shutil.copy
        shutil.copytree(source, target, dirs_exist_ok=config["replace_file"], copy_function=copier)
        if config["remove_file"]:
            shutil.rmtree(source)

    def _made(self, folder: str) -> None:
        """Make a folder that is missing, or fail when it is not to be made."""
        if not folder or os.path.isdir(folder):
            return
        if not self.config["create_directory"]:
            raise ConfigurationError(f"the folder '{folder}' is not there, and is not to be made")
        os.makedirs(folder, exist_ok=True)
