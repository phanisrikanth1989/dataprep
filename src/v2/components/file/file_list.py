"""File list: a loop over the files of a folder."""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from ...errors import ConfigurationError
from ...job.keys import Key, Kind, has_context_reference
from ..base import DIE_ON_ERROR, FAULTS, MAX_ITEMS, Action, one_line
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# The name of a file v2 itself is still writing beside its place (``files.temp_beside``).
_OWN_UNFINISHED = re.compile(r"\.v2tmp\d+$")
_ORDERS = ("order_by_filename", "order_by_filesize", "order_by_modifieddate")
_ORDER_BY = {"": None, "ORDER_BY_NOTHING": None, "ORDER_BY_FILENAME": "order_by_filename",
             "ORDER_BY_FILESIZE": "order_by_filesize", "ORDER_BY_MODIFIEDDATE": "order_by_modifieddate"}

# What is found: its path as the folder was named, its name, whether it is a folder, its size and when it changed.
Found = Tuple[str, str, bool, int, float]


def pattern_of(mask: str, glob: bool, apart: bool) -> "re.Pattern[str]":
    """A mask as the regular expression a whole name is held against.

    Args:
        mask: The mask.
        glob: Whether it is a pattern in Talend's form (Jakarta ORO's):
            ``*`` any run of characters, ``?`` any one, ``[abc]`` one of a
            set, which ``!`` or ``^`` at its start turns round, and a
            backslash takes the character after it as itself. Otherwise it
            is a regular expression already.
        apart: Whether capitals and small letters are told apart.

    Raises:
        ValueError: When Python cannot read it as a regular expression.
    """
    try:
        if glob:
            # `*` and `?` stand for any character, a line end in a name among them.
            return re.compile(_from_glob(mask), re.DOTALL if apart else re.DOTALL | re.IGNORECASE)
        return re.compile(mask, 0 if apart else re.IGNORECASE)
    except re.error as exc:
        raise ValueError(f"{mask!r} is no regular expression Python reads: {exc}") from None


def _from_glob(mask: str) -> str:
    """A pattern in Talend's form as a regular expression that is held against a name in one go.

    What stands between two stars is looked for where it comes first, and
    that place is not gone back on: a later place fits whenever the first
    one does. A star written as `.*` would have Python try every way of
    sharing a name out among the stars, which for a name made for it is
    minutes.
    """
    # What stands between the stars, each as a regular expression of a fixed length.
    between: List[List[str]] = [[]]
    at = 0
    while at < len(mask):
        char = mask[at]
        if char == "\\" and at + 1 < len(mask):
            between[-1].append(re.escape(mask[at + 1]))
            at += 2
            continue
        if char == "[":
            start = at + 1
            turned_round = mask[start:start + 1] in ("!", "^")
            start += turned_round
            # A closing bracket right at the start of a set is one of the set.
            end = mask.find("]", start + 1)
            if end != -1:
                held = "".join("\\" + one if one in "\\[]^" else one for one in mask[start:end])
                between[-1].append(f"[{'^' if turned_round else ''}{held}]")
                at = end + 1
                continue
        if char == "*":
            between.append([])
        else:
            between[-1].append("." if char == "?" else re.escape(char))
        at += 1
    first, *later = ["".join(part) for part in between]
    if not later:
        return first
    # Between two stars: the first place that fits, kept. After the last star: whatever is left, up to the end.
    return first + "".join(f"(?>.*?{part})" for part in later[:-1] if part) + ".*" + later[-1]


def _named(value: str) -> str:
    if not value.strip():
        raise ValueError("there is no folder named")
    return value


def _apart(value: Any) -> bool:
    """Talend's "case sensitive", written YES or NO, as whether capitals and small letters are told apart."""
    if isinstance(value, bool):
        return value
    written = str(value).strip().lower()
    if written in ("yes", "true"):
        return True
    if written in ("no", "false"):
        return False
    raise ValueError(f"{value!r} is neither YES nor NO")


def _age(value: float) -> float:
    if value < 0:
        raise ValueError(f"{value} seconds is no age; give 0 or more")
    return value


def _upper(value: str) -> str:
    return value.strip().upper()


@REGISTRY.register
class FileList(Action):
    """Start a loop over the files of the folder `directory`: what its iterate link leads to runs once for each.

    Which names: every name, or those that fit one of the masks in `files`
    whole (`*` any run of characters, `?` any one, `[abc]` one of a set;
    with `glob_expressions` off a mask is a regular expression). Names that
    fit one of the masks in `exclude_filemask`, a list with commas between,
    are left out when `exclude_file` is on. `case_sensitive` NO takes
    capitals and small letters for the same. `list_mode` says whether
    files, folders or both are listed, and `include_subdirs` whether
    folders inside the folder are gone into.

    The list is made once, before the first pass, and is sorted by path,
    or by name, size or the time of the last change when one of the
    `order_by_...` keys is on, upwards unless `order_action_desc` is on.

    In a pass the file is in globalMap as `<id>_CURRENT_FILE` (its name),
    `<id>_CURRENT_FILEPATH` (its path in full), `<id>_CURRENT_FILEDIRECTORY`
    and `<id>_CURRENT_FILEEXTENSION`, with `<id>_NB_FILE` the number of
    files so far.

    Left out always: a name that starts with a dot, unless a mask that
    starts with one fits it; a file v2 itself is still writing; a link
    that leads out of the folder, and what is neither a file nor a folder
    (these are named in a warning). A folder that starts with a dot or is
    reached through a link is not gone into. A folder that is not there,
    or cannot be looked into, fails the job.
    """

    names = ("file_list", "FileList", "tFileList")
    loops = True
    keys = (
        Key("directory", required=True, convert=_named, aliases=("DIRECTORY",), doc="The folder whose files are listed."),
        Key("files", type=list, default=[], aliases=("FILES",), doc="The masks: a name is listed when one fits it whole.",
            items=(Key("filemask", required=True, aliases=("FILEMASK",), doc="A mask."),)),
        Key("glob_expressions", type=bool, default=True, aliases=("GLOBEXPRESSIONS", "USE_GLOB"),
            doc="Whether a mask is a pattern (`*`, `?`, `[abc]`); off, it is a regular expression."),
        Key("case_sensitive", type=object, default=True, convert=_apart, aliases=("CASE_SENSITIVE",),
            doc="Whether capitals and small letters are told apart: `YES` or `NO`."),
        Key("exclude_file", type=bool, default=False, aliases=("IFEXCLUDE",),
            doc="Whether names that fit `exclude_filemask` are left out."),
        Key("exclude_filemask", default="", aliases=("EXCLUDEFILEMASK",), doc="Masks of names to leave out, with commas between."),
        Key("list_mode", default="FILES", convert=_upper, choices=("FILES", "DIRECTORIES", "BOTH"), aliases=("LIST_MODE",),
            doc="What is listed: files, folders, or both."),
        Key("include_subdirs", type=bool, default=False, aliases=("INCLUDSUBDIR",),
            doc="Whether the folders inside the folder are gone into, at every depth."),
        Key("order_by_filename", type=bool, default=False, aliases=("ORDER_BY_FILENAME",), doc="Whether the list is by name."),
        Key("order_by_filesize", type=bool, default=False, aliases=("ORDER_BY_FILESIZE",), doc="Whether the list is by size."),
        Key("order_by_modifieddate", type=bool, default=False, aliases=("ORDER_BY_MODIFIEDDATE",),
            doc="Whether the list is by the time of the last change."),
        Key("order_action_desc", type=bool, default=False, aliases=("ORDER_ACTION_DESC",),
            doc="Whether the list goes downwards. Not for the order by path."),
        Key("order_by", default="", convert=_upper, choices=tuple(_ORDER_BY), aliases=("ORDER_BY",),
            doc="v1's way to name the order: `ORDER_BY_FILENAME`, `ORDER_BY_FILESIZE`, `ORDER_BY_MODIFIEDDATE`."),
        Key("order_action", default="", convert=_upper, choices=("", "ORDER_ACTION_ASC", "ORDER_ACTION_DESC"),
            aliases=("ORDER_ACTION",), doc="v1's way to say upwards or downwards."),
        Key("error", type=bool, default=False, aliases=("ERROR",), doc="Whether finding no file fails the job."),
        Key("min_age_seconds", type=float, default=0.0, convert=_age,
            doc="A file changed less than this long ago is left out, for a later run: it may still be arriving."),
        MAX_ITEMS,
        DIE_ON_ERROR,
        Key("order_by_nothing", kind=Kind.IGNORED, type=object, doc="The order by path: what is left when no other is on."),
        Key("order_action_asc", kind=Kind.IGNORED, type=object, doc="Upwards: what is left when downwards is not on."),
        Key("format_filepath_to_slash", kind=Kind.IGNORED, type=object, aliases=("FORMAT_FILEPATH_TO_SLASH",),
            doc="Talend's turning of backslashes into slashes; a path has none here."),
    )

    def problems(self) -> List[str]:
        config, found = self.config, []
        if not config["glob_expressions"]:
            for at, entry in enumerate(config["files"]):
                mask = entry["filemask"]
                if not has_context_reference(mask):
                    try:
                        pattern_of(mask, glob=False, apart=True)
                    except ValueError as exc:
                        found.append(f"files[{at}].filemask: {exc}")
        on = [name for name in _ORDERS if config[name]]
        if len(on) > 1:
            found.append(f"{on[1]}: files are listed in one order, and `{on[0]}` is on as well")
        return found

    # ------------------------------------------------------------------
    # Doing it
    # ------------------------------------------------------------------

    def act(self) -> None:
        held = self.global_map
        try:
            found = self._found()
        except FAULTS as exc:
            self.fail_or_go_on(exc)
            held.update({f"{self.id}_NB_LINE": 1, f"{self.id}_NB_LINE_OK": 0, f"{self.id}_NB_LINE_REJECT": 1})
            return
        root = self.config["directory"]
        items = []
        for number, (path, name, is_folder, _, _) in enumerate(found, start=1):
            full = os.path.abspath(path)
            items.append((os.path.relpath(path, root), {
                f"{self.id}_CURRENT_FILE": name,
                f"{self.id}_CURRENT_FILEPATH": full,
                f"{self.id}_CURRENT_FILEDIRECTORY": os.path.dirname(full),
                # As in Talend: what follows the last dot of a file's name; nothing for a folder.
                f"{self.id}_CURRENT_FILEEXTENSION": name.rpartition(".")[2] if "." in name and not is_folder else "",
                f"{self.id}_NB_FILE": number,
            }))
        self.loop_over(items)
        held.update({
            f"{self.id}_NB_FILE": len(found),
            f"{self.id}_NB_LINE": len(found), f"{self.id}_NB_LINE_OK": len(found), f"{self.id}_NB_LINE_REJECT": 0,
        })

    def _found(self) -> List[Found]:
        """What the folder holds that is to be listed, in the order of the passes."""
        config = self.config
        root = config["directory"]
        if not os.path.lexists(root):
            raise ConfigurationError(f"the folder '{root}' is not there")
        if not os.path.isdir(root):
            raise ConfigurationError(f"'{root}' is no folder")
        found, left_out, too_new = self._walked(root)
        if left_out:
            logger.warning(one_line(
                f"[{self.id}] {len(left_out)} names in '{root}' are left out, being links out of the folder or no "
                f"files; the first: '{sorted(left_out)[0]}'"
            ))
        if too_new:
            files, are = ("file", "is") if too_new == 1 else ("files", "are")
            logger.info(one_line(
                f"[{self.id}] {too_new} {files} in '{root}' changed less than {config['min_age_seconds']:g} seconds ago "
                f"and {are} left for a later run"
            ))
        if not found and config["error"]:
            raise ConfigurationError(f"No file found in directory {root}")
        return self._ordered(found)

    def _walked(self, root: str) -> Tuple[List[Found], List[str], int]:
        """Go through the folder; returns what is listed, the paths left out for what they are, and how many
        files changed too lately."""
        config = self.config
        files_wanted, folders_wanted = config["list_mode"] != "DIRECTORIES", config["list_mode"] != "FILES"
        fits = self._fitting()
        inside, newest = os.path.realpath(root), time.time() - config["min_age_seconds"]
        # A file's size and time cost a call to the system each, which a folder of very many files feels:
        # asked for only when the order or the age needs them.
        measured = bool(config["min_age_seconds"]) or self._order() is not None
        found: List[Found] = []
        left_out: List[str] = []
        too_new = 0
        waiting = [root]
        while waiting:
            folder = waiting.pop()
            try:
                with os.scandir(folder) as scanned:
                    entries = list(scanned)
            except OSError as exc:
                # Not passed over: a folder that cannot be looked into would look like one with nothing in it.
                said = (exc.strerror or type(exc).__name__).lower()
                raise ConfigurationError(f"'{folder}' cannot be looked into: {said}") from None
            for entry in entries:
                name, link = entry.name, entry.is_symlink()
                if _OWN_UNFINISHED.search(name):
                    continue
                try:
                    is_folder, is_file = entry.is_dir(), entry.is_file()
                except OSError:
                    is_folder = is_file = False
                if is_folder and not link and config["include_subdirs"] and not name.startswith("."):
                    # Not through a link, where the walk could go round for ever or leave the folder.
                    waiting.append(entry.path)
                if not (folders_wanted if is_folder else files_wanted) or not fits(name):
                    continue
                reached = os.path.realpath(entry.path) if link else inside
                if not (is_folder or is_file) or (reached != inside and not reached.startswith(inside + os.sep)):
                    left_out.append(entry.path)
                    continue
                size, changed = 0, 0.0
                if measured:
                    try:
                        said = entry.stat()
                    except OSError:
                        # Gone since the folder was read: not there to be listed.
                        continue
                    size, changed = said.st_size, said.st_mtime
                if is_file and config["min_age_seconds"] and changed > newest:
                    too_new += 1
                else:
                    found.append((entry.path, name, is_folder, size, changed))
        return found, left_out, too_new

    def _fitting(self) -> Any:
        """The question whether a name is one to list: by the masks, the exclude masks and the rule for dot names."""
        config = self.config
        glob, apart = config["glob_expressions"], config["case_sensitive"]
        try:
            masks = [(entry["filemask"], pattern_of(entry["filemask"], glob, apart)) for entry in config["files"]]
            excluded = [pattern_of(mask.strip(), glob, apart)
                        for mask in config["exclude_filemask"].split(",") if mask.strip()] if config["exclude_file"] else []
        except ValueError as exc:
            raise ConfigurationError(str(exc)) from None
        dot = "." if glob else "\\."

        def fits(name: str) -> bool:
            if name.startswith("."):
                # As a shell has it: a name that starts with a dot is listed only by a mask that starts with one.
                taken = any(mask.startswith(dot) and pattern.fullmatch(name) for mask, pattern in masks)
            else:
                taken = not masks or any(pattern.fullmatch(name) for _, pattern in masks)
            return bool(taken) and not any(pattern.fullmatch(name) for pattern in excluded)

        return fits

    def _order(self) -> Optional[str]:
        """The key that says the order, or None for the order by path."""
        config = self.config
        return next((name for name in _ORDERS if config[name]), None) or _ORDER_BY[config["order_by"]]

    def _ordered(self, found: List[Found]) -> List[Found]:
        config = self.config
        by = self._order()
        by_path = sorted(found)
        if by is None:
            # Talend's "by default", which is by path, and which "downwards" does not turn round.
            return by_path
        key: Dict[str, Any] = {
            # Folders before files, as in Talend; then the name, and the path where two have one name.
            "order_by_filename": lambda one: (not one[2], one[1], one[0]),
            "order_by_filesize": lambda one: (one[3], one[1], one[0]),
            "order_by_modifieddate": lambda one: (one[4], one[1], one[0]),
        }
        down = config["order_action_desc"] or config["order_action"] == "ORDER_ACTION_DESC"
        return sorted(by_path, key=key[by], reverse=down)
