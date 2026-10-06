"""Text files in encodings other than UTF-8.

Polars reads and writes UTF-8. A file in another encoding is read through a
UTF-8 copy and written by converting the UTF-8 file Polars wrote. Most
single-byte encodings agree with UTF-8 on plain ASCII, so a file that holds
nothing else is used as it is, which is the common case and costs one fast
look through the file.
"""
from __future__ import annotations

import codecs
import errno
import os
import shutil
from typing import TYPE_CHECKING

from .errors import ConfigurationError

if TYPE_CHECKING:
    from .engine.context import RunContext

_CHUNK = 1 << 24
_UTF8 = ("utf-8", "utf_8", "utf-8-sig", "utf_8_sig")


def codec_name(encoding: str) -> str:
    """Python's name for an encoding.

    Raises:
        ConfigurationError: When Python does not know the encoding.
    """
    try:
        return codecs.lookup(encoding).name
    except LookupError:
        raise ConfigurationError(f"unknown encoding: {encoding}") from None


def as_utf8(path: str, encoding: str, run_context: "RunContext", exact: bool = False) -> str:
    """A file Polars can read: the file itself, or a UTF-8 copy of it.

    Bytes the encoding cannot decode become U+FFFD, as Talend does.

    Args:
        path: The file to read.
        encoding: Its declared encoding.
        run_context: The run; it owns the scratch copy and removes it when
            the job ends.
        exact: Whether the reader needs every byte to be valid UTF-8. Polars'
            delimited reader repairs a bad byte itself; its line reader
            fails on one, so a file declared UTF-8 is looked through for it
            first and copied with the repair when it holds one.
    """
    name = codec_name(encoding)
    if name in _UTF8:
        if not exact or _is_utf8(path):
            return path
        name = "utf-8"
    elif _agrees_on_ascii(name) and _is_ascii(path):
        return path
    copy = run_context.temp_path(".utf8")
    decoder = codecs.getincrementaldecoder(name)(errors="replace")
    with open(path, "rb") as source, open(copy, "wb") as target:
        while chunk := source.read(_CHUNK):
            target.write(decoder.decode(chunk).encode("utf-8"))
        target.write(decoder.decode(b"", final=True).encode("utf-8"))
    return copy


def to_encoding(written: str, encoding: str) -> bytes:
    """Put a UTF-8 file Polars wrote in the job's encoding, where it is.

    Returns:
        The byte order mark the file now starts with; empty for an encoding
        that writes none.

    Raises:
        UnicodeEncodeError: When the text holds a character the encoding
            cannot write.
    """
    name = codec_name(encoding)
    if name in ("utf-8", "utf_8") or (_agrees_on_ascii(name) and _is_ascii(written)):
        return b""
    converted = written + ".enc"
    try:
        _convert(written, converted, name)
        os.replace(converted, written)
    except BaseException:
        _remove(converted)
        raise
    return codecs.getincrementalencoder(name)().encode("")


def encoded(text: str, encoding: str) -> bytes:
    """Text in an encoding, without the byte order mark the encoding starts a file with."""
    encoder = codecs.getincrementalencoder(codec_name(encoding))()
    encoder.encode("")
    return encoder.encode(text, final=True)


def put_in_place(
    written: str, path: str, append: bool = False, mark: bytes = b"", header: bytes = b"", holds_header: bool = False
) -> None:
    """Put a finished file where the job wants it, or add it to the file that is there.

    Only bytes are moved: nothing here depends on the rows any more, so only
    the file system can fail it. A file that is replaced keeps its
    permissions and a link is followed, as when the file is written into.
    The finished file is gone afterwards, whether this succeeds or not.

    Args:
        written: The finished file, in the job's encoding.
        path: Where the job wants it.
        append: Whether to add to a file that is already there.
        mark: The byte order mark ``written`` starts with. A file has one,
            at its start.
        header: The header line a new file starts with, in the file's
            encoding; empty when it has none. A header is not repeated in a
            file that is added to.
        holds_header: Whether ``written`` holds that header, after the mark.
    """
    try:
        adding = append and os.path.exists(path) and os.path.getsize(path) > 0
        if not adding and holds_header == bool(header):
            _replace(written, path)
            return
        with open(written, "rb") as source, open(path, "ab" if adding else "wb") as target:
            if adding:
                source.seek(len(mark) + (len(header) if holds_header else 0))
            else:
                target.write(mark + header)
                source.seek(len(mark))
            shutil.copyfileobj(source, target, _CHUNK)
    finally:
        _remove(written)


def _replace(written: str, path: str) -> None:
    """Move a file over another, keeping what writing into the other keeps: its permissions, and a link to it."""
    if os.path.islink(path):
        path = os.path.realpath(path)
    if os.path.exists(path):
        shutil.copymode(path, written)
    try:
        os.replace(written, path)
    except OSError as error:
        if error.errno != errno.EXDEV:
            raise
        # The link leads to another file system, where a file cannot be moved to.
        shutil.copyfile(written, path)


def _convert(source_path: str, target_path: str, name: str) -> None:
    decoder = codecs.getincrementaldecoder("utf-8")()
    encoder = codecs.getincrementalencoder(name)()
    with open(source_path, "rb") as source, open(target_path, "wb") as target:
        while chunk := source.read(_CHUNK):
            target.write(encoder.encode(decoder.decode(chunk)))
        target.write(encoder.encode(decoder.decode(b"", final=True), final=True))


def _agrees_on_ascii(name: str) -> bool:
    """Whether the encoding writes ASCII characters as their ASCII bytes."""
    plain = bytes(range(128))
    try:
        return plain.decode(name) == plain.decode("ascii") and plain.decode("ascii").encode(name) == plain
    except (UnicodeError, LookupError):
        return False


def _is_utf8(path: str) -> bool:
    """Whether every byte of a file is valid UTF-8."""
    decoder = codecs.getincrementaldecoder("utf-8")()
    try:
        with open(path, "rb") as handle:
            while chunk := handle.read(_CHUNK):
                if not chunk.isascii():
                    decoder.decode(chunk)
            decoder.decode(b"", final=True)
    except UnicodeDecodeError:
        return False
    return True


def _is_ascii(path: str) -> bool:
    with open(path, "rb") as handle:
        while chunk := handle.read(_CHUNK):
            if not chunk.isascii():
                return False
    return True


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
