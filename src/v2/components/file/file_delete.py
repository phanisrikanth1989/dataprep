"""File delete: a file or a folder is deleted."""
from __future__ import annotations

import logging
import os
import shutil
from typing import List, Tuple

from ...errors import ConfigurationError
from ...job.keys import Key, Kind
from ..base import Action, one_line
from ..registry import REGISTRY
from .file_copy import why

logger = logging.getLogger(__name__)


@REGISTRY.register
class FileDelete(Action):
    """Delete a file (`filename`), a folder (`folder` on, `directory`), or whichever the path is (`folder_file` on, `path`).

    A folder goes with everything in it, unless `recursive` is off: then
    only an empty one goes. What happened is left in globalMap as
    `<id>_CURRENT_STATUS`, in Talend's words (`File deleted.`, `Path
    deleted.`, `No file deleted.`, `No path deleted.`, `File does not
    exist or is invalid.`, `Path does not exist or is invalid.`, `File or
    path does not exist or is invalid.`), and the path as
    `<id>_DELETE_PATH`.

    When there is nothing to delete, or it cannot be deleted, the job
    fails, as in Talend; with `failon` off it goes on, with why in
    `<id>_ERROR_MESSAGE` and a warning in the log.

    Two things are never deleted, whatever v1 or Talend would do: what a
    link leads to (the link itself is taken away, also when the path ends
    in a slash), and the folder the job runs in or one it lies in.
    """

    names = ("file_delete", "FileDelete", "tFileDelete")
    keys = (
        Key("filename", default="", aliases=("FILENAME",), doc="The file to delete."),
        Key("directory", default="", aliases=("DIRECTORY",), doc="The folder to delete, with `folder` on."),
        Key("path", default="", aliases=("PATH",), doc="The file or folder to delete, with `folder_file` on."),
        Key("folder", type=bool, default=False, aliases=("is_directory",), doc="Whether a folder is deleted."),
        Key("folder_file", type=bool, default=False, aliases=("is_folder_file",),
            doc="Whether the path is deleted whichever it is, a file or a folder."),
        Key("recursive", type=bool, default=True, doc="Whether a folder goes with everything in it."),
        Key("failon", type=bool, default=True, aliases=("fail_on_error",),
            doc="Whether nothing to delete, or a delete that fails, fails the job."),
        Key("die_on_error", kind=Kind.IGNORED, type=object, doc="`failon` says it; v1 reads this on every component."),
    )

    def _named(self) -> Tuple[str, str]:
        """The config key the path is read from, and the path. As v1: `path` stands in for the other two."""
        config = self.config
        if config["folder_file"]:
            return "path", config["path"]
        key = "directory" if config["folder"] else "filename"
        return key, config[key] or config["path"]

    def problems(self) -> List[str]:
        key, path = self._named()
        return [] if path else [f"{key}: there is nothing named to delete"]

    def act(self) -> None:
        config, held = self.config, self.global_map
        _, path = self._named()
        status, fault = self._deleted(path)
        held.update({f"{self.id}_DELETE_PATH": path, f"{self.id}_CURRENT_STATUS": status, f"{self.id}_NB_LINE": 1,
                     f"{self.id}_NB_LINE_OK": int(not fault), f"{self.id}_NB_LINE_REJECT": int(bool(fault))})
        if not fault:
            return
        held[f"{self.id}_ERROR_MESSAGE"] = fault
        if config["failon"]:
            raise ConfigurationError(fault)
        logger.warning(one_line(f"[{self.id}] {fault}; the job goes on"))

    def _deleted(self, path: str) -> Tuple[str, str]:
        """Delete it. Returns Talend's word for what happened, and what is wrong when something is."""
        config = self.config
        link = path.rstrip("/" + os.sep) or path
        if os.path.islink(link):
            # A link is taken away itself; what it leads to is never touched.
            if config["folder"] and not config["folder_file"] and not os.path.isdir(link):
                return ("Path does not exist or is invalid.",
                        f"Directory '{path}' does not exist or is invalid or is not a directory.")
            as_file = not config["folder_file"] and not config["folder"] or not os.path.isdir(link)
            return self._file(link) if as_file else self._unlinked(link, path)
        if config["folder_file"]:
            if os.path.isfile(path):
                return self._file(path)
            if os.path.isdir(path):
                return self._folder(path)
            said = "File or path does not exist or is invalid."
            return said, said
        if config["folder"]:
            if os.path.isdir(path):
                return self._folder(path)
            return ("Path does not exist or is invalid.",
                    f"Directory '{path}' does not exist or is invalid or is not a directory.")
        if os.path.isfile(path):
            return self._file(path)
        return "File does not exist or is invalid.", f"File '{path}' does not exist or is invalid or is not a file."

    @staticmethod
    def _file(path: str) -> Tuple[str, str]:
        try:
            os.remove(path)
        except OSError as exc:
            return "No file deleted.", f"File '{path}' can not be deleted: {(exc.strerror or str(exc)).lower()}"
        return "File deleted.", ""

    @staticmethod
    def _unlinked(link: str, path: str) -> Tuple[str, str]:
        try:
            os.unlink(link)
        except OSError as exc:
            return "No path deleted.", f"Directory '{path}' can not be deleted: {why(exc)}"
        return "Path deleted.", ""

    def _folder(self, path: str) -> Tuple[str, str]:
        here, gone = os.path.realpath(os.getcwd()), os.path.realpath(path)
        if here == gone or here.startswith(gone.rstrip(os.sep) + os.sep):
            return "No path deleted.", f"Directory '{path}' is the folder the job runs in, or one it lies in: it is not deleted"
        if not self.config["recursive"] and os.listdir(path):
            return "No path deleted.", f"Directory '{path}' can not be deleted: it is not empty"
        held = sum(len(folders) + len(files) for _, folders, files in os.walk(path))
        try:
            shutil.rmtree(path)
        except OSError as exc:
            left = sum(len(folders) + len(files) for _, folders, files in os.walk(path))
            partly = "; some of what it held is gone" if left < held else ""
            said = why(exc) if exc.filename and exc.filename != path else (exc.strerror or str(exc)).lower()
            return "No path deleted.", f"Directory '{path}' can not be deleted: {said}{partly}"
        return "Path deleted.", ""
