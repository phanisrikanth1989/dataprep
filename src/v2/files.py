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
# The character a file may start with to say how it is written; no part of its text.
_BYTE_ORDER_MARK = chr(0xFEFF)
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
            the subjob that reads it has ended.
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
    # A subjob that is read a second time reads the copy made the first time.
    known = (os.path.abspath(path), name)
    if known in run_context.utf8_copies:
        return run_context.utf8_copies[known]
    copy = run_context.temp_path(".utf8")
    decoder = codecs.getincrementaldecoder(name)(errors="replace")
    with open(path, "rb") as source, open(copy, "wb") as target:
        while chunk := source.read(_CHUNK):
            target.write(decoder.decode(chunk).encode("utf-8"))
        target.write(decoder.decode(b"", final=True).encode("utf-8"))
    run_context.utf8_copies[known] = copy
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


def transcode(source: str, target: str, read_as: str, write_as: str) -> int:
    """Write a file's text to another file in another encoding, piece by piece.

    The text is written as it is: line ends are not touched. A byte order
    mark at the start of the source is not carried over; the target starts
    with one where its encoding writes one (UTF-16, UTF-32, utf-8-sig).

    Args:
        source: The file to read, as the job names it.
        target: The file to write.
        read_as: The source's encoding.
        write_as: The target's encoding.

    Returns:
        How many bytes were written.

    Raises:
        ConfigurationError: When a byte of the source is no character in
            its encoding, or one of its characters cannot be written in the
            target's. The message names the place by its line.
    """
    decoder = codecs.getincrementaldecoder(codec_name(read_as))()
    encoder = codecs.getincrementalencoder(codec_name(write_as))()
    fed = lines = written = 0
    at_start = True
    with open(source, "rb") as reading, open(target, "wb") as writing:
        while True:
            chunk = reading.read(_CHUNK)
            # What the decoder still holds of the piece before: the start of a character that goes on in this one.
            held = len(decoder.getstate()[0])
            try:
                text = decoder.decode(chunk, final=not chunk)
            except UnicodeDecodeError as fault:
                line = lines + chunk[:max(fault.start - held, 0)].count(b"\n") + 1
                raise ConfigurationError(
                    f"'{source}' is not written in {read_as}: byte {fed - held + fault.start + 1} of it, on line {line}, "
                    "is no character there"
                ) from None
            if at_start and text:
                text, at_start = text.removeprefix(_BYTE_ORDER_MARK), False
            try:
                written += writing.write(encoder.encode(text, final=not chunk))
            except UnicodeEncodeError as fault:
                line = lines + text.count("\n", 0, fault.start) + 1
                raise ConfigurationError(
                    f"'{source}' holds {ascii(text[fault.start])} on line {line}, which {write_as} cannot write"
                ) from None
            fed += len(chunk)
            lines += text.count("\n")
            if not chunk:
                return written


def temp_beside(path: str, component_id: str) -> str:
    """Where a component's file is written before it is put in place: beside its target.

    The component's id is part of the name, so two components writing to one
    file in the same subjob do not write over each other.
    """
    folder, name = os.path.split(path)
    safe = "".join(char if char.isalnum() or char in "-_" else "_" for char in component_id)
    return os.path.join(folder, f".{name}.{safe}.v2tmp{os.getpid()}")


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
