"""File unarchive: an archive unpacked into a folder, all of it or none."""
from __future__ import annotations

import bz2
import gzip
import logging
import lzma
import os
import shutil
import stat
import tarfile
import time
import zipfile
import zlib
from typing import Any, Callable, Dict, List, Optional, Tuple

from ...errors import ConfigurationError
from ...files import not_a_file, temp_beside
from ...job.keys import Key, Kind
from ..base import DIE_ON_ERROR, Action, one_line
from ..registry import REGISTRY
from .file_input_delimited import encoding

try:
    from compression import zstd
except ImportError:  # Zstandard is in the standard library from Python 3.14.
    zstd = None

logger = logging.getLogger(__name__)

_CHUNK = 1 << 22
# One file compressed by itself: the bytes it starts with, what the way is called, what opens it, and the
# ending its name loses when it is unpacked.
_PACKED: Tuple[Tuple[bytes, str, Optional[Callable[..., Any]], str], ...] = (
    (b"\x1f\x8b", "gzip", gzip.open, ".gz"),
    (b"BZh", "bzip2", bz2.open, ".bz2"),
    (b"\xfd7zXZ\x00", "xz", lzma.open, ".xz"),
    (b"\x28\xb5\x2f\xfd", "Zstandard", zstd.open if zstd is not None else None, ".zst"),
)
# Endings of two parts that a folder named after an archive loses whole.
_TWO_PART = (".tar.gz", ".tar.bz2", ".tar.xz", ".tar.zst")
# What Python raises on an archive that is cut short or holds other bytes than it says.
_DAMAGE: Tuple[type, ...] = (zipfile.BadZipFile, tarfile.TarError, zlib.error, lzma.LZMAError, EOFError, gzip.BadGzipFile)
if zstd is not None:
    _DAMAGE += (zstd.ZstdError,)

# An entry: its path below the folder, and whether it is a folder.
Entry = Tuple[str, bool]


def _named(what: str) -> Callable[[str], str]:
    def check(value: str) -> str:
        if not value.strip():
            raise ValueError(f"there is no {what}")
        return value
    return check


def _root_name(archive: str) -> str:
    """The name of the folder an archive is unpacked under when it is to have one of its own."""
    base = os.path.basename(archive)
    for ending in _TWO_PART:
        if base.lower().endswith(ending) and len(base) > len(ending):
            return base[:-len(ending)]
    # As in Talend: the name up to its last dot, and the whole name when it has none.
    return os.path.splitext(base)[0] or base


def _said(fault: BaseException) -> str:
    if isinstance(fault, OSError) and fault.strerror:
        return fault.strerror.lower()
    return " ".join(str(fault).split()) or type(fault).__name__


@REGISTRY.register
class FileUnarchive(Action):
    """Unpack the archive `zipfile` into the folder `directory`.

    The archive is a zip, a tar (plain, or compressed with gzip, bzip2, xz
    or Zstandard), or one file compressed by itself in one of those ways.
    Which it is is told from what it holds, not from its name. The files
    land by the paths the archive gives them, with the times it gives
    them; with `extractpath` off they all land in the folder itself. With
    `rootname` they land in a folder of the archive's name inside
    `directory`. The folder is made when it is not there, and a file that
    is there is written over.

    All of it or none: the archive is unpacked into a folder of its own
    inside `directory`, and the files are moved to their places when
    every one of them is whole. An archive that is cut short or damaged,
    or that would not fit, leaves `directory` as it was. A name that
    would land outside `directory` fails the job. A link or a special
    file in the archive is left out and named in a warning, and nothing
    is written through a link that is already in the folder.

    A zip locked with a password is opened with `password` when
    `checkpassword` is on. The password is shown in no log.

    It leaves `<id>_NB_FILE`, the number of files unpacked, and the name
    and the full path of the last of them in `<id>_CURRENT_FILE` and
    `<id>_CURRENT_FILEPATH`, and counts one row. No flow comes to it or
    leaves it.
    """

    names = ("file_unarchive", "FileUnarchive", "FileUnarchiveComponent", "tFileUnarchive")
    keys = (
        Key("zipfile", required=True, convert=_named("archive named"), doc="The archive to unpack."),
        Key("directory", required=True, convert=_named("folder named to unpack into"),
            doc="The folder to unpack into; it is made when it is not there."),
        Key("rootname", type=bool, default=False,
            doc="Whether the files land in a folder of the archive's name inside `directory`."),
        Key("extractpath", type=bool, default=True, aliases=("extract_path",),
            doc="Whether the files keep the folders the archive gives them; off, they all land in the folder itself."),
        Key("checkpassword", type=bool, default=False, aliases=("check_password",),
            doc="Whether a zip is opened with `password`."),
        Key("password", default="", secret=True, doc="The password of a locked zip."),
        Key("decrypt_method", default="ZIP4J_DECRYPT", choices=("ZIP4J_DECRYPT", "JAVA_DECRYPT"),
            doc="How the zip is locked: `ZIP4J_DECRYPT` is the standard way, and the one v2 opens."),
        Key("use_encoding", type=bool, default=False,
            doc="Whether the names in a zip are read in `encording`; off, they are read as UTF-8."),
        Key("encording", default="UTF-8", convert=encoding,
            doc="The encoding of the names in a zip that does not say it itself. (The spelling is Talend's.)"),
        Key("printout", type=bool, default=False, doc="Whether every file unpacked is said in the log at INFO."),
        DIE_ON_ERROR,
        Key("integrity", kind=Kind.IGNORED, type=object,
            doc="Talend's check of the archive before it is unpacked. v2 always unpacks all of it or none."),
    )

    def problems(self) -> List[str]:
        config = self.config
        if config["checkpassword"] and config["decrypt_method"] == "JAVA_DECRYPT":
            return ["decrypt_method: JAVA_DECRYPT is a cipher of Talend's own around the whole file, which only Talend "
                    "reads; v2 opens a zip locked the standard way"]
        return []

    # ------------------------------------------------------------------
    # Doing it
    # ------------------------------------------------------------------

    def act(self) -> None:
        try:
            self._unpack()
        except ConfigurationError as exc:
            if not self.goes_on_after(str(exc)):
                raise
            self.global_map.update({f"{self.id}_NB_LINE": 1, f"{self.id}_NB_LINE_OK": 0, f"{self.id}_NB_LINE_REJECT": 1})

    def _unpack(self) -> None:
        config = self.config
        archive, into = config["zipfile"], config["directory"]
        if not os.path.exists(archive):
            raise ConfigurationError(f"File not found: '{archive}'")
        if not_a_file(archive):
            # Never opened: a pipe waits for whoever writes to it, and a device may never end.
            raise ConfigurationError(f"'{archive}' cannot be unpacked: {not_a_file(archive)}")
        if config["rootname"]:
            into = os.path.join(into, _root_name(archive))
        kind = self._kind(archive)
        made = self._made(into)
        staging = temp_beside(os.path.join(into, os.path.basename(archive)), self.id)
        shutil.rmtree(staging, ignore_errors=True)
        try:
            try:
                os.mkdir(staging)
                entries, left_out = self._staged(kind, archive, staging, into)
                placed = self._placed(entries, archive, staging, into)
            except _DAMAGE as fault:
                short = isinstance(fault, EOFError) or "nexpected end" in str(fault) or "truncated" in str(fault).lower()
                why = "it ends before its end" if short else _said(fault)
                raise ConfigurationError(f"'{archive}' is damaged: {why}; nothing is unpacked") from None
            except OSError as fault:
                where = ""
                if isinstance(fault.filename, str):
                    # An entry is named as the archive names it, not by where it was being unpacked to.
                    inside = fault.filename.startswith(staging + os.sep)
                    where = f": '{os.path.relpath(fault.filename, staging) if inside else fault.filename}'"
                raise ConfigurationError(
                    f"'{archive}' cannot be unpacked into '{into}': {_said(fault)}{where}; nothing is unpacked"
                ) from None
        except BaseException:
            # The folder as it was: what was made for this archive goes, the folder itself too.
            shutil.rmtree(staging, ignore_errors=True)
            if made is not None:
                shutil.rmtree(made, ignore_errors=True)
            raise
        shutil.rmtree(staging, ignore_errors=True)
        if left_out:
            several = len(left_out) > 1
            logger.warning(one_line(
                f"[{self.id}] {len(left_out)} link{'s' if several else ''} or special file{'s' if several else ''} in "
                f"'{archive}' {'are' if several else 'is'} left out; the first: '{left_out[0]}'"
            ))
        say_each = logger.info if config["printout"] else logger.debug
        for path in placed:
            say_each(one_line(f"[{self.id}] unpacked '{path}'"))
        logger.info(one_line(f"[{self.id}] unpacked {len(placed)} files of '{archive}' ({kind}) into '{into}'"))
        held = self.global_map
        held.update({
            f"{self.id}_NB_FILE": len(placed),
            f"{self.id}_NB_LINE": 1, f"{self.id}_NB_LINE_OK": 1, f"{self.id}_NB_LINE_REJECT": 0,
        })
        if placed:
            held[f"{self.id}_CURRENT_FILE"] = os.path.basename(placed[-1])
            held[f"{self.id}_CURRENT_FILEPATH"] = os.path.abspath(placed[-1])

    @staticmethod
    def _kind(archive: str) -> str:
        """What an archive is, by what it holds: `tar`, `zip`, or the name of the way its one file is compressed."""
        try:
            # A tar first: its header carries a check sum of itself, so nothing else is taken for one, where the
            # end of a zip may stand in any file that happens to hold a zip.
            with tarfile.open(archive, "r:*"):
                return "tar"
        except (tarfile.TarError, EOFError, zlib.error, lzma.LZMAError):
            pass
        except OSError as fault:
            if not isinstance(fault, gzip.BadGzipFile):
                raise ConfigurationError(f"'{archive}' cannot be read: {_said(fault)}") from None
        if zipfile.is_zipfile(archive):
            return "zip"
        with open(archive, "rb") as handle:
            start = handle.read(8)
        for magic, name, opener, _ in _PACKED:
            if start.startswith(magic) and opener is not None:
                return name
        raise ConfigurationError(
            f"'{archive}' is no archive v2 can unpack: it is neither a zip nor a tar archive, nor one file compressed "
            "with gzip, bzip2, xz or Zstandard"
        )

    @staticmethod
    def _made(into: str) -> Optional[str]:
        """Make the folder to unpack into; returns the topmost folder that had to be made for it, if any."""
        topmost, path = None, into
        while path and not os.path.lexists(path):
            topmost, path = path, os.path.dirname(path)
        try:
            os.makedirs(into, exist_ok=True)
        except OSError as fault:
            if topmost is not None:
                shutil.rmtree(topmost, ignore_errors=True)
            raise ConfigurationError(f"the folder '{into}' cannot be made: {_said(fault)}") from None
        return topmost

    # ------------------------------------------------------------------
    # Unpacking, into a folder of the archive's own
    # ------------------------------------------------------------------

    def _staged(self, kind: str, archive: str, staging: str, into: str) -> Tuple[List[Entry], List[str]]:
        """Unpack every entry into the staging folder; returns the entries in the archive's order, and what was left out."""
        if kind == "zip":
            return self._from_zip(archive, staging, into)
        if kind == "tar":
            return self._from_tar(archive, staging)
        return self._from_one_file(kind, archive, staging), []

    def _from_zip(self, archive: str, staging: str, into: str) -> Tuple[List[Entry], List[str]]:
        config = self.config
        names_in = config["encording"] if config["use_encoding"] else "UTF-8"
        password = config["password"].encode("utf-8") if config["checkpassword"] else None
        try:
            held = zipfile.ZipFile(archive, metadata_encoding=names_in)
        except UnicodeDecodeError:
            raise ConfigurationError(
                f"the names in '{archive}' are not written in {names_in}: say how they are written with "
                "`use_encoding` and `encording`"
            ) from None
        with held:
            entries: List[Tuple[str, Optional[zipfile.ZipInfo]]] = []
            left_out: List[str] = []
            for info in held.infolist():
                # A zip made on Windows may name its entries with backslashes.
                name = _inside(info.filename.replace("\\", "/"), info.filename, archive)
                # What kind of thing the entry was where the zip was made; nothing, for a zip that does not say.
                kind_of = stat.S_IFMT(info.external_attr >> 16)
                if info.is_dir():
                    entries.append((name, None))
                elif kind_of and kind_of != stat.S_IFREG:
                    left_out.append(name)
                else:
                    entries.append((name, info))
            needed = sum(info.file_size for _, info in entries if info is not None)
            free = shutil.disk_usage(into).free
            if needed > free:
                # A zip says how large its entries are: one that would fill the disk is known before a byte is written.
                raise ConfigurationError(
                    f"'{archive}' unpacks to {needed} bytes, and there are {free} bytes free where '{into}' is: "
                    "nothing is unpacked"
                )
            for name, info in entries:
                if info is None:
                    # A folder: made where it belongs when the files are moved there.
                    continue
                staged = os.path.join(staging, name)
                os.makedirs(os.path.dirname(staged), exist_ok=True)
                self._one_of_a_zip(held, info, staged, password, archive, name)
        return [(name, info is None) for name, info in entries], left_out

    def _one_of_a_zip(
        self, held: zipfile.ZipFile, info: zipfile.ZipInfo, staged: str, password: Optional[bytes], archive: str, name: str
    ) -> None:
        try:
            with held.open(info, pwd=password) as packed, open(staged, "wb") as unpacked:
                shutil.copyfileobj(packed, unpacked, _CHUNK)
        except NotImplementedError:
            raise ConfigurationError(
                f"'{name}' of '{archive}' is packed or locked in a way Python cannot read (AES encryption is one such way)"
            ) from None
        except RuntimeError as fault:
            # How Python says a password is missing or wrong.
            if password is None and "password required" in str(fault):
                raise ConfigurationError(
                    f"'{name}' of '{archive}' is locked with a password: give it with `checkpassword` and `password`"
                ) from None
            raise ConfigurationError(f"the password does not open '{name}' of '{archive}'") from None
        except (zipfile.BadZipFile, zlib.error, EOFError):
            raise ConfigurationError(
                f"'{archive}' is damaged: '{name}' in it cannot be unpacked; nothing is unpacked"
            ) from None
        # A zip gives a time as a clock on the wall would show it, to two seconds.
        changed = time.mktime(tuple(info.date_time) + (0, 0, -1))
        os.utime(staged, (changed, changed))

    @staticmethod
    def _from_tar(archive: str, staging: str) -> Tuple[List[Entry], List[str]]:
        entries: List[Entry] = []
        left_out: List[str] = []
        with tarfile.open(archive, "r:*") as held:
            for member in held:
                name = _inside(member.name, member.name, archive)
                if not (member.isreg() or member.isdir() or member.islnk()):
                    # A link by name, a pipe, a device. A second name for a file of the archive (a hard link) is
                    # a file, and is unpacked.
                    left_out.append(name)
                    continue
                try:
                    # Python's own filter for data: no owner, no setuid, nothing outside the folder.
                    held.extract(member, staging, filter="data")
                except tarfile.FilterError:
                    raise ConfigurationError(
                        f"'{archive}' holds '{member.name}', which leads out of the folder it is unpacked to: "
                        "nothing is unpacked"
                    ) from None
                except KeyError:
                    raise ConfigurationError(
                        f"'{archive}' is damaged: '{member.name}' is a second name for a file that is not in it; "
                        "nothing is unpacked"
                    ) from None
                entries.append((name, member.isdir()))
        return entries, left_out

    @staticmethod
    def _from_one_file(kind: str, archive: str, staging: str) -> List[Entry]:
        opener, ending = next((opener, ending) for _, name, opener, ending in _PACKED if name == kind)
        base = os.path.basename(archive)
        if not base.lower().endswith(ending) or len(base) == len(ending):
            raise ConfigurationError(
                f"'{archive}' is one file compressed with {kind}, and its name does not end in {ending}: there is no "
                "name to unpack it under"
            )
        name = base[:-len(ending)]
        staged = os.path.join(staging, name)
        with opener(archive, "rb") as packed, open(staged, "wb") as unpacked:  # type: ignore[misc]
            shutil.copyfileobj(packed, unpacked, _CHUNK)
        # The time of the archive, as gunzip gives it to the file it unpacks.
        changed = os.stat(archive).st_mtime
        os.utime(staged, (changed, changed))
        return [(name, False)]

    # ------------------------------------------------------------------
    # Moving what was unpacked to its place
    # ------------------------------------------------------------------

    def _placed(self, entries: List[Entry], archive: str, staging: str, into: str) -> List[str]:
        """Move the files from the staging folder to their places; returns the paths of the files, in order."""
        flat = not self.config["extractpath"]
        folders: List[str] = []
        files: Dict[str, str] = {}
        for name, is_folder in entries:
            if is_folder:
                if not flat:
                    folders.append(name)
                continue
            final = os.path.basename(name) if flat else name
            if flat and files.get(final, name) != name:
                raise ConfigurationError(
                    f"'{files[final]}' and '{name}' of '{archive}' would both be '{final}' with their folders dropped: "
                    "nothing is unpacked"
                )
            # The last of two entries of one name stays, at the place of the first.
            files[final] = name
        root = os.path.realpath(into)
        # Every place is looked at before any file is moved: nothing is written through a link out of the folder.
        for final in list(files) + folders:
            above = os.path.dirname(os.path.join(root, final))
            while not os.path.lexists(above):
                above = os.path.dirname(above)
            reached = os.path.realpath(above)
            if reached != root and not reached.startswith(root + os.sep):
                raise ConfigurationError(
                    f"'{final}' of '{archive}' would be written through a link that leads out of '{into}': nothing "
                    "is unpacked"
                )
            target = os.path.join(into, final)
            if final in files and os.path.isdir(target) and not os.path.islink(target):
                raise ConfigurationError(
                    f"'{final}' of '{archive}' is a file, and '{target}' is a folder: nothing is unpacked"
                )
        for name in folders:
            os.makedirs(os.path.join(into, name), exist_ok=True)
        placed: List[str] = []
        for final, name in files.items():
            target = os.path.join(into, final)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            os.replace(os.path.join(staging, name), target)
            placed.append(target)
        return placed


def _inside(name: str, as_named: str, archive: str) -> str:
    """An entry's name as a path below the folder it is unpacked to; empty for an entry that names the folder itself
    (`./`, as tar writes for the folder it packed), which then asks for nothing to be made.

    A name that starts at the root lands in the folder, as tar and unzip
    have it. One that climbs out of the folder fails the job: Python's
    zip reader would put it in the folder under another name without a
    word.
    """
    parts = [part for part in name.split("/") if part not in ("", ".")]
    if ".." in parts:
        raise ConfigurationError(
            f"'{archive}' names '{as_named}', which would land outside the folder it is unpacked to: nothing is unpacked"
        )
    return "/".join(parts)
