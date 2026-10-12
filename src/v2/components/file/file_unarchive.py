"""File unarchive: an archive unpacked into a folder, all of it or none."""
from __future__ import annotations

import bz2
import gzip
import logging
import lzma
import os
import shutil
import stat
import sys
import tarfile
import time
import zipfile
import zlib
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from ...errors import ConfigurationError
from ...files import cleared, not_a_file, temp_beside
from ...job.keys import Key, Kind
from ..base import DIE_ON_ERROR, FAULTS, MAX_ITEMS, Action, one_line
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
# The endings that say tar. A tar with no entry is zero bytes and nothing else, and so is a file of zero bytes:
# of those two, only the name tells which one it is.
_TAR_NAMES = (".tar", ".tgz", ".tbz", ".tbz2", ".txz", ".tzst") + _TWO_PART
# A tar is written in blocks of this many bytes: the header of an entry is one, and so is the mark of its end.
_BLOCK = 512
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


def _damaged(archive: str, fault: BaseException) -> ConfigurationError:
    short = isinstance(fault, EOFError) or "nexpected end" in str(fault) or "truncated" in str(fault).lower()
    return ConfigurationError(
        f"'{archive}' is damaged: {'it ends before its end' if short else _said(fault)}; nothing is unpacked")


def _packing(archive: str) -> Optional[Tuple[str, Callable[..., Any], str]]:
    """How an archive's bytes are compressed, told from the first of them: what the way is called, what opens
    it and the ending a name has for it. None when they are not compressed."""
    with open(archive, "rb") as handle:
        start = handle.read(8)
    for magic, name, opener, ending in _PACKED:
        if start.startswith(magic):
            if opener is None:
                raise ConfigurationError(
                    f"'{archive}' is compressed with {name}, which Python reads from 3.14 on, and this is Python "
                    f"{sys.version_info.major}.{sys.version_info.minor}")
            return name, opener, ending
    return None


def _is_entry(block: bytes) -> bool:
    """Whether a block of a file is the header of an entry of a tar: it carries a check sum of itself."""
    try:
        tarfile.TarInfo.frombuf(block, tarfile.ENCODING, "surrogateescape")
    except tarfile.HeaderError:
        return False
    return True


def _beyond(stream: Any) -> bool:
    """Read a stream to its end; returns whether any byte on the way is not zero.

    Reading to the end is also what makes a compressed stream say that it
    is not whole: its check sum stands after its last byte.
    """
    more = False
    while True:
        piece = stream.read(_CHUNK)
        if not piece:
            return more
        more = more or piece.count(0) != len(piece)


class _Watched:
    """What a tar is read from, which keeps the last piece read.

    Python's reader of tar stops without a word where it finds no entry:
    at the mark of the end, and just the same where the archive is cut
    short or a header is not whole. The piece it read last is what it
    stopped at.
    """

    def __init__(self, stream: Any) -> None:
        self._stream = stream
        self._last: Tuple[int, bytes] = (-1, b"")

    def read(self, size: int = -1) -> bytes:
        at = self._stream.tell()
        data = self._stream.read(size)
        self._last = (at, data)
        return data

    def seek(self, offset: int, whence: int = 0) -> int:
        return self._stream.seek(offset, whence)

    def tell(self) -> int:
        return self._stream.tell()

    def block_at(self, offset: int) -> bytes:
        """The block at an offset, or as much of it as there is: the last piece read, when that is it."""
        at, data = self._last
        if at != offset:
            self._stream.seek(offset)
            data = self._stream.read(_BLOCK)
        return data



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
    or that would not fit, leaves `directory` as it was, and so does a
    file that cannot be moved to its place: what was moved before it is
    put back. A name that would land outside `directory` fails the job. A
    link or a special file in the archive is left out and named in a
    warning, and nothing is written through a link that is already in the
    folder.

    A zip locked with a password is opened with `password` when
    `checkpassword` is on. The password is shown in no log.

    It leaves `<id>_NB_FILE`, the number of files unpacked, and the name
    and the full path of the last of them in `<id>_CURRENT_FILE` and
    `<id>_CURRENT_FILEPATH`, and counts one row. No flow comes to it or
    leaves it.

    It may start a loop: what its iterate link leads to runs once for
    each file it unpacked, in the order of the archive, with that file's
    name and path in the two entries. The loop starts when the whole
    archive is unpacked.
    """

    names = ("file_unarchive", "FileUnarchive", "FileUnarchiveComponent", "tFileUnarchive")
    loops = True
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
        MAX_ITEMS,
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
        except FAULTS as exc:
            self.fail_or_go_on(exc)
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
        # A folder of the archive's own in the folder it is unpacked into: `new` for what is unpacked, `old` for
        # the files that are there and that it takes the place of, until all of it has landed.
        scratch = temp_beside(os.path.join(into, os.path.basename(archive)), self.id)
        staging, aside = os.path.join(scratch, "new"), os.path.join(scratch, "old")
        try:
            try:
                for folder in (cleared(scratch), staging, aside):
                    os.mkdir(folder)
                entries, left_out, noted = self._staged(kind, archive, staging, into)
                placed = self._placed(entries, archive, staging, aside, into, fresh=made is not None)
            except _DAMAGE as fault:
                raise _damaged(archive, fault) from None
            except OSError as fault:
                if fault.errno is None:
                    # No fault of the system: how bzip2 says that the bytes are not what it packed.
                    raise _damaged(archive, fault) from None
                raise ConfigurationError(
                    f"'{archive}' cannot be unpacked into '{into}': {_where(fault, staging)}; nothing is unpacked"
                ) from None
        except BaseException:
            # The folder as it was: what was made for this archive goes, the folder itself too. Only a file that
            # was there before and could not be put back stays where it waits.
            shutil.rmtree(staging, ignore_errors=True)
            if not _waiting(aside):
                shutil.rmtree(scratch, ignore_errors=True)
            if made is not None:
                shutil.rmtree(made, ignore_errors=True)
            raise
        shutil.rmtree(scratch, ignore_errors=True)
        if left_out:
            several = len(left_out) > 1
            logger.warning(one_line(
                f"[{self.id}] {len(left_out)} link{'s' if several else ''} or special file{'s' if several else ''} in "
                f"'{archive}' {'are' if several else 'is'} left out; the first: '{left_out[0]}'"
            ))
        for note in noted:
            logger.warning(one_line(f"[{self.id}] {note}"))
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
        # The items of its loop: every file, named in the log as the archive names it.
        self.loop_over([
            (os.path.relpath(path, into), {
                f"{self.id}_CURRENT_FILE": os.path.basename(path), f"{self.id}_CURRENT_FILEPATH": os.path.abspath(path),
            })
            for path in placed
        ])

    @staticmethod
    def _kind(archive: str) -> str:
        """What an archive is, by what it holds: `tar`, `zip`, or the name of the way its one file is compressed."""
        try:
            packing = _packing(archive)
            with (packing[1] if packing else open)(archive, "rb") as held:
                first = held.read(_BLOCK)
                # A tar first: the header of an entry carries a check sum of itself, so nothing else is taken for
                # one, where the end of a zip may stand in any file that happens to hold a zip.
                if _is_entry(first):
                    return "tar"
                # A tar with no entry is zero bytes to its end, and so is a file of zero bytes: the name decides.
                named_tar = os.path.basename(archive).lower().endswith(_TAR_NAMES)
                if named_tar and first.count(0) == _BLOCK and not _beyond(held):
                    return "tar"
            if packing:
                return packing[0]
            if zipfile.is_zipfile(archive):
                return "zip"
        except _DAMAGE as fault:
            raise _damaged(archive, fault) from None
        except OSError as fault:
            if fault.errno is None:
                raise _damaged(archive, fault) from None
            raise ConfigurationError(f"'{archive}' cannot be read: {_said(fault)}") from None
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

    def _staged(self, kind: str, archive: str, staging: str, into: str) -> Tuple[List[Entry], List[str], List[str]]:
        """Unpack every entry into the staging folder.

        Returns:
            The entries in the archive's order, the names of what was left
            out, and what is to be said in a warning once all of it has
            landed.
        """
        if kind == "zip":
            return (*self._from_zip(archive, staging, into), [])
        if kind == "tar":
            return self._from_tar(archive, staging)
        return self._from_one_file(kind, archive, staging), [], []

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
                    entries.append((_a_file(name, archive), info))
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

    def _from_tar(self, archive: str, staging: str) -> Tuple[List[Entry], List[str], List[str]]:
        entries: List[Entry] = []
        left_out: List[str] = []
        # The files unpacked so far, by name, and the names of what was left out.
        whole: Dict[str, str] = {}
        left: Set[str] = set()
        noted: List[str] = []
        packing = _packing(archive)
        with (packing[1] if packing else open)(archive, "rb") as plain:
            watched = _Watched(plain)
            # Python's reader finds the entries. It makes no file: every file is made here, from the bytes of an
            # entry that is a file, so that nothing an archive holds can make a link, a pipe or a device.
            with tarfile.open(fileobj=watched, mode="r:") as held:
                last = ""
                for member in held:
                    name, last = _inside(member.name, member.name, archive), member.name
                    if member.isdir():
                        entries.append((name, True))
                        continue
                    # A second name for a file of the archive (a hard link) names the file it is for.
                    first = _first_name(member, archive) if member.islnk() else None
                    if not member.isreg() and first not in whole:
                        if first is not None and first not in left:
                            raise ConfigurationError(
                                f"'{archive}' is damaged: '{member.name}' is a second name for a file that is not in "
                                "it; nothing is unpacked")
                        # A link by name, a pipe, a device, or a second name for one of those.
                        left.add(name)
                        left_out.append(name)
                        continue
                    staged = os.path.join(staging, _a_file(name, archive))
                    if first is None:
                        self._one_of_a_tar(held, member, staged)
                    else:
                        # A file of its own, and not the one file under two names: a copy.
                        os.makedirs(os.path.dirname(staged), exist_ok=True)
                        shutil.copy2(whole[first], staged)
                    whole[name] = staged
                    entries.append((name, False))
                stopped_at = watched.block_at(held.offset)
            if len(stopped_at) < _BLOCK:
                raise ConfigurationError(f"'{archive}' is damaged: it ends before its end; nothing is unpacked")
            if stopped_at.count(0) != _BLOCK:
                raise ConfigurationError(
                    f"'{archive}' is damaged: what follows '{last}' in it is no entry; nothing is unpacked")
            # To the last byte: a compressed archive says only there whether all of it is what was packed.
            if _beyond(watched):
                noted.append(f"'{archive}' goes on after its end, and what stands there is not unpacked: it may be "
                             "more than one archive joined")
        return entries, left_out, noted

    @staticmethod
    def _one_of_a_tar(held: tarfile.TarFile, member: tarfile.TarInfo, staged: str) -> None:
        # Of the permissions an entry has, none that lets the file run as its owner or be written by others;
        # and the file is made with them, so that it gets no more than a new file gets here (the umask).
        mode = member.mode & 0o755
        if not mode & 0o100:
            mode &= ~0o111
        os.makedirs(os.path.dirname(staged), exist_ok=True)
        if os.path.lexists(staged):
            # A second entry of one name: the file of the first goes, with its permissions.
            os.remove(staged)
        packed = held.extractfile(member)
        with packed, open(staged, "wb", opener=lambda path, flags: os.open(path, flags, mode | 0o600)) as unpacked:  # type: ignore[union-attr]
            shutil.copyfileobj(packed, unpacked, _CHUNK)  # type: ignore[arg-type]
        try:
            os.utime(staged, (member.mtime, member.mtime))
        except (OverflowError, OSError):
            # A time no clock here shows: the file keeps the time it was unpacked at.
            pass

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

    def _placed(
        self, entries: List[Entry], archive: str, staging: str, aside: str, into: str, fresh: bool
    ) -> List[str]:
        """Move the files from the staging folder to their places; returns the paths of the files, in order.

        All of them or none: a file that is there is moved aside first, and
        when a file cannot be moved to its place every move before it is
        taken back.

        Args:
            entries: The entries of the archive, in its order.
            archive: The archive, for a message.
            staging: Where the files were unpacked to.
            aside: Where a file that is written over waits until all have landed.
            into: The folder to unpack into.
            fresh: Whether `into` was made for this archive: then taking the
                folder away puts everything back, and the caller does that.
        """
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
        # What takes each thing done back again, in the order it was done.
        back: List[Callable[[], None]] = []
        placed: List[str] = []
        try:
            for name in folders:
                _folder(os.path.join(into, name), back)
            for number, (final, name) in enumerate(files.items()):
                target = os.path.join(into, final)
                _folder(os.path.dirname(target), back)
                if os.path.lexists(target):
                    was = os.path.join(aside, str(number))
                    os.replace(target, was)
                    back.append(lambda was=was, target=target: os.replace(was, target))
                os.replace(os.path.join(staging, name), target)
                back.append(lambda target=target: os.remove(target))
                placed.append(target)
        except BaseException as fault:
            stood = _taken_back(back)
            if stood is not None and not fresh and isinstance(fault, OSError):
                kept = f": the files that were there and are not back are kept in '{aside}'" if _waiting(aside) else ""
                raise ConfigurationError(
                    f"'{archive}' cannot be unpacked into '{into}': {_where(fault, staging)}; and '{into}' could not be "
                    f"put back as it was ({_where(stood, staging)}){kept}"
                ) from None
            raise
        return placed


def _folder(path: str, back: List[Callable[[], None]]) -> None:
    """Make a folder, and the folders above it that are not there, noting for each what takes it away again."""
    missing: List[str] = []
    while not os.path.isdir(path):
        missing.append(path)
        if os.path.lexists(path):
            # Something that is no folder stands there: making the folder says so.
            break
        path = os.path.dirname(path)
    for folder in reversed(missing):
        os.mkdir(folder)
        back.append(lambda folder=folder: os.rmdir(folder))


def _waiting(aside: str) -> bool:
    """Whether a file that was there before still waits where it was moved aside to."""
    return os.path.isdir(aside) and bool(os.listdir(aside))


def _taken_back(back: List[Callable[[], None]]) -> Optional[OSError]:
    """Take back what was done, the last thing first; returns what stood in the way, if anything did."""
    stood: Optional[OSError] = None
    for step in reversed(back):
        try:
            step()
        except OSError as fault:
            stood = stood or fault
    return stood


def _where(fault: OSError, staging: str) -> str:
    """What went wrong and with which file, an entry named as the archive names it and not by where it was unpacked to."""
    if not isinstance(fault.filename, str):
        return _said(fault)
    inside = fault.filename.startswith(staging + os.sep)
    return f"{_said(fault)}: '{os.path.relpath(fault.filename, staging) if inside else fault.filename}'"


def _a_file(name: str, archive: str) -> str:
    """The name of an entry that is a file, which has to be one."""
    if not name:
        raise ConfigurationError(f"'{archive}' is damaged: it holds a file without a name; nothing is unpacked")
    return name


def _first_name(member: tarfile.TarInfo, archive: str) -> str:
    """The name of the file a second name (a hard link) is for, as a path below the folder."""
    parts = [part for part in member.linkname.split("/") if part not in ("", ".")]
    if ".." in parts:
        raise ConfigurationError(
            f"'{archive}' holds '{member.name}', which leads out of the folder it is unpacked to: nothing is unpacked")
    return "/".join(parts)


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
