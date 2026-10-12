"""File archive: files packed into one archive."""
from __future__ import annotations

import fnmatch
import gzip
import logging
import os
import shutil
import stat
import sys
import tarfile
import zipfile
from typing import Any, List, Optional, Tuple

from ...errors import ConfigurationError
from ...files import put_in_place, temp_beside
from ...job.keys import Key, Kind
from ..base import DIE_ON_ERROR, Action, one_line
from ..registry import REGISTRY
from .file_row_count import unreadable

try:
    from compression import zstd
except ImportError:  # Zstandard is in the standard library from Python 3.14.
    zstd = None

logger = logging.getLogger(__name__)

_CHUNK = 1 << 22
# The kinds of archive, each under the names a job config may give it. Talend's are zip, gzip and tgz.
_KINDS = {
    "zip": "zip", "gzip": "gzip", "gz": "gzip", "tgz": "tgz", "tar_gzip": "tgz", "tar.gz": "tgz", "tar": "tar",
    "tar.zst": "tar.zst", "tzst": "tar.zst", "zst": "zst",
}
# The kinds that hold one file, compressed, and no names.
_ONE_FILE = ("gzip", "zst")
_ZSTANDARD = ("tar.zst", "zst")


def _kind(value: str) -> str:
    kind = _KINDS.get(value.strip().lower())
    if kind is None:
        raise ValueError(f"'{value}' is no kind of archive v2 writes; use one of zip, gzip, tgz, tar, tar.zst, zst")
    if kind in _ZSTANDARD and zstd is None:
        running = ".".join(str(part) for part in sys.version_info[:2])
        raise ValueError(f"{kind} needs Zstandard, which Python has from 3.14; this is Python {running}")
    return kind


def _level(value: Any) -> int:
    try:
        return int(str(value).strip())
    except ValueError:
        raise ValueError(f"{value!r} is no whole number") from None


def _masks(value: Any) -> List[str]:
    # v1's engine reads one mask as text; the converter writes a list of them.
    given = [value] if isinstance(value, str) else list(value or [])
    return [str(mask) for mask in given if str(mask).strip()]


def _unowned(member: tarfile.TarInfo) -> tarfile.TarInfo:
    """A tar entry that says nothing of who owns the file, with its time in whole seconds.

    The same files then give the same archive on every server, and no
    user's name leaves with it.
    """
    member.uid = member.gid = 0
    member.uname = member.gname = ""
    member.mtime = int(member.mtime)
    return member


def _not_passed_over(fault: OSError) -> None:
    raise ConfigurationError(f"'{fault.filename}' cannot be read: {(fault.strerror or type(fault).__name__).lower()}")


@REGISTRY.register
class FileArchive(Action):
    """Pack the files of the folder `source` into the archive `target`.

    The entries are the files by their path below the folder, in the order
    of their names. Only files are entries: a folder is in the archive
    through the files in it. `sub_directroy` off leaves out the files of
    subfolders, and with `all_files` off only the files whose name fits
    one of the patterns in `mask` are taken (`*` any run of characters,
    `?` any one, `[abc]` one of a set). `source` may also be one file.

    `archive_format` is `zip`, `tgz` (a tar compressed with gzip), `tar`,
    or, where Python has Zstandard, `tar.zst`. `gzip` and `zst` hold one
    file, `source_file`, compressed, and no names. `level` says how hard
    it is compressed, 0 (not at all) to 9.

    Each file is read piece by piece and never held in memory. The
    archive is written beside `target` and put there when it is whole, so
    a job that fails leaves the archive that was there. The same files
    give the same bytes. A link or a special file among the files is left
    out and named in a warning: an archive holds files. When no file is
    taken, no archive is written and one that was there is taken away.

    It leaves `<id>_ARCHIVE_FILEPATH`, `<id>_ARCHIVE_FILENAME` and
    `<id>_NB_FILE`, the number of files in the archive, and counts one
    row. No flow comes to it or leaves it.
    """

    names = ("file_archive", "FileArchive", "FileArchiveComponent", "tFileArchive")
    keys = (
        Key("source", default="", doc="The folder whose files are archived, or one file."),
        Key("source_file", default="", doc="The one file a `gzip` or `zst` archive holds."),
        Key("target", required=True, doc="The archive to write."),
        Key("archive_format", default="zip", convert=_kind,
            doc="The kind of archive: `zip`, `gzip`, `tgz`, `tar`, `tar.zst`, `zst`."),
        Key("level", type=object, default=4, convert=_level, aliases=("compression_level",),
            doc="How hard the archive is compressed: 0, not at all, to 9; 1 to 22 for Zstandard."),
        Key("sub_directroy", type=bool, default=True, aliases=("include_subdirectories", "sub_directory"),
            doc="Whether the files of subfolders are taken. (The spelling is Talend's.)"),
        Key("all_files", type=bool, default=True, doc="Whether every file is taken; off, only those `mask` names."),
        Key("mask", type=object, default=[], convert=_masks,
            doc="Patterns of file names, for `all_files` off: a file is taken when its name fits one."),
        Key("mkdir", type=bool, default=False, doc="Whether the folder of the archive is made when it is not there."),
        Key("overwrite", type=bool, default=True,
            doc="Whether an archive that is there is written over; off, the job fails when one is."),
        DIE_ON_ERROR,
        Key("encrypt_files", kind=Kind.REFUSED, type=bool,
            reason="v2 writes no encrypted archive: Python cannot write one. Encrypt the archive with a tool made for "
                   "it after the job has written it"),
        Key("encrypt_method", kind=Kind.IGNORED, type=object, doc="How Talend would encrypt; nothing is encrypted."),
        Key("aes_key_strength", kind=Kind.IGNORED, type=object, doc="How Talend would encrypt; nothing is encrypted."),
        Key("password", kind=Kind.IGNORED, type=object, doc="For Talend's encryption; nothing is encrypted."),
        Key("encoding", kind=Kind.IGNORED, type=object,
            doc="The encoding of the names in a zip: v2 writes them in UTF-8 and marks them so."),
        Key("zip64_mode", kind=Kind.IGNORED, type=object, doc="A zip is written with ZIP64 where it needs it."),
        Key("use_sync_flush", kind=Kind.IGNORED, type=object, doc="Talend's way of flushing a gzip stream."),
    )

    def problems(self) -> List[str]:
        config, found = self.config, []
        kind, level = config["archive_format"], config["level"]
        if not config["target"].strip():
            found.append("target: there is no archive named")
        if kind in _ONE_FILE and not config["source_file"].strip():
            found.append("source_file: there is no file named to compress")
        if kind not in _ONE_FILE:
            if not config["source"].strip():
                found.append("source: there is nothing named to archive")
            if not config["all_files"] and not config["mask"]:
                found.append("mask: `all_files` is off and no mask is given: no file would be taken")
        lowest, highest = (1, 22) if kind in _ZSTANDARD else (0, 9)
        if kind != "tar" and not lowest <= level <= highest:
            found.append(f"level: {level} is no level a {kind} archive is compressed at; give {lowest} to {highest}")
        return found

    # ------------------------------------------------------------------
    # Doing it
    # ------------------------------------------------------------------

    def act(self) -> None:
        try:
            self._pack()
        except ConfigurationError as exc:
            if not self.goes_on_after(str(exc)):
                raise
            self.global_map.update({f"{self.id}_NB_LINE": 1, f"{self.id}_NB_LINE_OK": 0, f"{self.id}_NB_LINE_REJECT": 1})

    def _pack(self) -> None:
        config, held = self.config, self.global_map
        kind, target = config["archive_format"], config["target"]
        source = config["source_file"] if kind in _ONE_FILE else config["source"]
        held.update({f"{self.id}_ARCHIVE_FILEPATH": target, f"{self.id}_ARCHIVE_FILENAME": os.path.basename(target)})
        if not os.path.exists(source):
            raise ConfigurationError(f"'{source}' is not there: there is nothing to archive")
        if not os.path.isdir(source) and not os.path.isfile(source):
            # Never opened: a pipe waits for whoever writes to it, and a device may never end.
            raise ConfigurationError(f"'{source}' is neither a file nor a folder: there is nothing to archive")
        if kind in _ONE_FILE and os.path.isdir(source):
            raise ConfigurationError(f"'{source}' is a folder, and a {kind} archive holds one file: use zip or tgz for a folder")
        there = os.path.lexists(target)
        if there and not config["overwrite"]:
            raise ConfigurationError(f"'{target}' is there, and is not to be written over")
        if os.path.isdir(target):
            raise ConfigurationError(f"'{target}' cannot be written: it is a folder")
        folder = os.path.dirname(target)
        if folder and not os.path.isdir(folder):
            if not config["mkdir"]:
                raise ConfigurationError(f"the folder '{folder}' is not there, and is not to be made")
            os.makedirs(folder, exist_ok=True)
        beside = temp_beside(target, self.id)
        taken, left_out = self._files(source, {os.path.realpath(target), os.path.realpath(beside)})
        if left_out:
            logger.warning(one_line(
                f"[{self.id}] {len(left_out)} links or special files of '{source}' are left out of the archive; "
                f"the first: '{left_out[0]}'"
            ))
        if taken:
            size = self._written(kind, taken, beside, target)
            logger.info(one_line(
                f"[{self.id}] packed {len(taken)} files of '{source}' into '{target}' ({kind}), {size} bytes"
            ))
        else:
            # As in Talend: nothing to pack, no archive, and none of an earlier run left to be taken for this one's.
            if there:
                os.remove(target)
            gone = f", and '{target}', which was there, is taken away" if there else ""
            logger.warning(one_line(f"[{self.id}] no file of '{source}' is taken: no archive is written{gone}"))
        held.update({
            f"{self.id}_NB_FILE": len(taken),
            f"{self.id}_NB_LINE": 1, f"{self.id}_NB_LINE_OK": 1, f"{self.id}_NB_LINE_REJECT": 0,
        })

    def _files(self, source: str, never: set) -> Tuple[List[Tuple[str, str]], List[str]]:
        """The files to pack, each with the name of its entry, in the order of those names; and what is left out.

        Args:
            source: The folder, or the one file.
            never: Paths that are not packed whatever their names: the archive itself.
        """
        config = self.config
        if not os.path.isdir(source):
            return [(source, os.path.basename(source))], []
        masks = [] if config["all_files"] else config["mask"]
        taken: List[Tuple[str, str]] = []
        left_out: List[str] = []
        # A link to a folder is listed and not gone into: nothing is read through a link. A folder that cannot be
        # looked into fails the job: left to itself the walk would pass it over, and its files with it.
        for folder, folders, names in os.walk(source, onerror=_not_passed_over):
            if not config["sub_directroy"]:
                folders.clear()
            for name in sorted(folders):
                if os.path.islink(os.path.join(folder, name)):
                    left_out.append(os.path.join(folder, name))
            for name in sorted(names):
                path = os.path.join(folder, name)
                if masks and not any(fnmatch.fnmatchcase(name, mask) for mask in masks):
                    continue
                if not stat.S_ISREG(os.lstat(path).st_mode):
                    left_out.append(path)
                elif os.path.realpath(path) not in never:
                    taken.append((path, os.path.relpath(path, source).replace(os.sep, "/")))
        return sorted(taken, key=lambda entry: entry[1]), sorted(left_out)

    def _written(self, kind: str, taken: List[Tuple[str, str]], beside: str, target: str) -> int:
        """Write the archive beside its place and put it there; returns its size."""
        level = self.config["level"]
        try:
            if kind == "zip":
                self._zip(taken, beside, level)
            elif kind in _ONE_FILE:
                self._one_file(kind, taken[0][0], beside, level)
            else:
                self._tar(kind, taken, beside, level)
            size = os.path.getsize(beside)
            put_in_place(beside, target)
        except OSError as exc:
            failed: Optional[str] = exc.filename if isinstance(exc.filename, str) else None
            if failed is not None and failed not in (beside, target):
                raise ConfigurationError(f"'{failed}' cannot be read: {unreadable(failed, exc)}") from None
            raise ConfigurationError(f"'{target}' cannot be written: {unreadable(target, exc)}") from None
        finally:
            if os.path.exists(beside):
                os.remove(beside)
        return size

    @staticmethod
    def _zip(taken: List[Tuple[str, str]], beside: str, level: int) -> None:
        method = zipfile.ZIP_DEFLATED if level else zipfile.ZIP_STORED
        # Not strict about times: a file older than 1980, which a zip cannot say, is packed as of 1980.
        with zipfile.ZipFile(beside, "w", compression=method, compresslevel=level or None, strict_timestamps=False) as packed:
            for path, name in taken:
                packed.write(path, name)

    @staticmethod
    def _tar(kind: str, taken: List[Tuple[str, str]], beside: str, level: int) -> None:
        with open(beside, "wb") as raw:
            if kind == "tgz":
                # No name and no time in the gzip header: the same files give the same bytes.
                packer: Any = gzip.GzipFile(filename="", fileobj=raw, mode="wb", compresslevel=level, mtime=0)
            elif kind == "tar.zst":
                packer = zstd.ZstdFile(raw, "wb", level=level)
            else:
                packer = raw
            try:
                with tarfile.open(fileobj=packer, mode="w") as packed:
                    for path, name in taken:
                        packed.add(path, arcname=name, recursive=False, filter=_unowned)
            finally:
                if packer is not raw:
                    packer.close()

    @staticmethod
    def _one_file(kind: str, source: str, beside: str, level: int) -> None:
        with open(source, "rb") as reading, open(beside, "wb") as raw:
            if kind == "gzip":
                # The file's own name and time in the header, as gzip itself writes them.
                changed = int(os.fstat(reading.fileno()).st_mtime)
                packer: Any = gzip.GzipFile(
                    filename=os.path.basename(source), fileobj=raw, mode="wb", compresslevel=level, mtime=changed
                )
            else:
                packer = zstd.ZstdFile(raw, "wb", level=level)
            with packer:
                shutil.copyfileobj(reading, packer, _CHUNK)
