"""File copy: a file or a folder is copied, or moved."""
from __future__ import annotations

import logging
import os
import re
import shutil
from typing import List

from ...errors import ConfigurationError
from ...job.keys import Key, Kind
from ..base import Action, one_line
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

_ERRNO = re.compile(r"^\[Errno \d+\] ")


def why(error: OSError) -> str:
    """What the system said of a path it would not let be read, written or taken away, in plain words."""
    said = (error.strerror or str(error)).lower()
    return f"{said}: '{error.filename}'" if error.filename else said


@REGISTRY.register
class FileCopy(Action):
    """Copy the file `filename` into the folder `destination`, or a folder with everything in it.

    A file keeps its name, or takes `destination_rename` with `rename` on.
    `create_directory` makes the folders that are missing. A file that is
    there is written over unless `replace_file` is off: then nothing is
    copied, and that is no fault; nor is a file copied onto itself. With
    `remove_file` the source file is taken away once it has been copied.

    With `enable_copy_directory` the folder `source_derectory` (Talend's
    spelling) is copied into `destination` under its own name
    (`src` into `out` is `out/src`), as in Talend: what is there is
    written over, what is missing is made, and the source folder is never
    taken away. A folder is not copied into itself.

    The time a file was changed is kept only with
    `preserve_last_modified_time`. A copy that fails leaves why in
    `<id>_ERROR_MESSAGE` and lets the job go on, unless `failon` (or
    `die_on_error`) is on. Where the copy is, or was to be, is left in
    `<id>_DESTINATION_FILEPATH`, `<id>_DESTINATION_FILENAME`,
    `<id>_SOURCE_DIRECTORY` and `<id>_DESTINATION_DIRECTORY`, as Talend
    leaves them.
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
        return found

    def act(self) -> None:
        held = self.global_map
        try:
            self._folder() if self.config["enable_copy_directory"] else self._file()
        except ConfigurationError as exc:
            said = str(exc)
            held.update({f"{self.id}_ERROR_MESSAGE": said, f"{self.id}_NB_LINE": 1, f"{self.id}_NB_LINE_OK": 0,
                         f"{self.id}_NB_LINE_REJECT": 1})
            if self.config["failon"] or self.config["die_on_error"]:
                raise
            logger.warning(one_line(f"[{self.id}] {said}; the job goes on"))
            return
        held.update({f"{self.id}_NB_LINE": 1, f"{self.id}_NB_LINE_OK": 1, f"{self.id}_NB_LINE_REJECT": 0})

    def _file(self) -> None:
        config = self.config
        source, folder = config["filename"], config["destination"]
        name = config["destination_rename"] if config["rename"] else os.path.basename(source)
        if not name.strip():
            # Talend's own name for a copy that is to take another name and is given none.
            name = "NewName.temp"
        target = os.path.join(folder, name)
        self.global_map.update({
            f"{self.id}_DESTINATION_FILEPATH": target, f"{self.id}_DESTINATION_FILENAME": os.path.basename(target),
            f"{self.id}_SOURCE_DIRECTORY": os.path.dirname(source) or None,
            f"{self.id}_DESTINATION_DIRECTORY": os.path.dirname(target),
        })
        if not os.path.isfile(source):
            raise ConfigurationError(f"'{source}' is not there, or is no file")
        if os.path.isfile(folder):
            raise ConfigurationError(f"'{folder}' is a file, not a folder to copy into")
        into = os.path.dirname(target)
        if into and not os.path.isdir(into):
            if not config["create_directory"]:
                raise ConfigurationError(f"the folder '{into}' is not there, and is not to be made")
            os.makedirs(into, exist_ok=True)
        same = os.path.exists(target) and os.path.samefile(source, target)
        if same or (os.path.exists(target) and not config["replace_file"]):
            # As in Talend: nothing is copied, and that is no fault. The source stays, having no copy.
            logger.info(one_line(f"[{self.id}] '{target}' is there and is not written over; nothing is copied"))
            return
        try:
            (shutil.copy2 if config["preserve_last_modified_time"] else shutil.copy)(source, target)
        except OSError as exc:
            raise ConfigurationError(f"the copy failed: {why(exc)}") from None
        if config["remove_file"]:
            try:
                os.remove(source)
            except OSError as exc:
                said = (exc.strerror or str(exc)).lower()
                raise ConfigurationError(
                    f"the file was copied, and the source '{source}' could not be taken away: {said}"
                ) from None

    def _folder(self) -> None:
        config = self.config
        source, into = config["source_derectory"], config["destination"]
        self.global_map.update({f"{self.id}_SOURCE_DIRECTORY": source, f"{self.id}_DESTINATION_DIRECTORY": into})
        if not os.path.isdir(source):
            raise ConfigurationError(f"'{source}' is not there, or is no folder")
        taken, placed = os.path.realpath(source), os.path.realpath(into)
        if placed == taken or placed.startswith(taken + os.sep):
            raise ConfigurationError(
                f"'{into}' is in the folder '{source}' that is to be copied, or is that folder: nothing is copied"
            )
        # As in Talend: under its own name, over what is there, with what is missing made.
        target = os.path.join(into, os.path.basename(taken))
        copier = shutil.copy2 if config["preserve_last_modified_time"] else shutil.copy
        try:
            shutil.copytree(source, target, dirs_exist_ok=True, copy_function=copier)
        except shutil.Error as exc:
            failed = exc.args[0]
            first, _, said = failed[0]
            files = "1 file" if len(failed) == 1 else f"{len(failed)} files"
            raise ConfigurationError(
                f"{files} of '{source}' could not be copied; the first: '{first}': {_ERRNO.sub('', str(said)).lower()}"
            ) from None
        except OSError as exc:
            raise ConfigurationError(f"the copy failed: {why(exc)}") from None
