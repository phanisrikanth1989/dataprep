"""Text files in encodings other than UTF-8.

Polars reads and writes UTF-8. A file in another encoding is read through a
UTF-8 copy and written by converting the UTF-8 file Polars wrote. Most
single-byte encodings agree with UTF-8 on plain ASCII, so a file that holds
nothing else is used as it is, which is the common case and costs one fast
look through the file.
"""
from __future__ import annotations

import codecs
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


def as_utf8(path: str, encoding: str, run_context: "RunContext") -> str:
    """A file Polars can read: the file itself, or a UTF-8 copy of it.

    Bytes the encoding cannot decode become U+FFFD, as Talend does.

    Args:
        path: The file to read.
        encoding: Its declared encoding.
        run_context: The run; it owns the scratch copy and removes it when
            the job ends.
    """
    name = codec_name(encoding)
    if name in _UTF8 or (_agrees_on_ascii(name) and _is_ascii(path)):
        return path
    copy = run_context.temp_path(".utf8")
    decoder = codecs.getincrementaldecoder(name)(errors="replace")
    with open(path, "rb") as source, open(copy, "wb") as target:
        while chunk := source.read(_CHUNK):
            target.write(decoder.decode(chunk).encode("utf-8"))
        target.write(decoder.decode(b"", final=True).encode("utf-8"))
    return copy


def put_text_in_place(written: str, path: str, encoding: str, append: bool) -> None:
    """Move a UTF-8 file Polars wrote to where the job wants it, in the job's encoding.

    The written file is gone afterwards, whether this succeeds or not.

    Raises:
        UnicodeEncodeError: When the text holds a character the encoding
            cannot write. ``path`` is then left as it was.
    """
    name = codec_name(encoding)
    try:
        if name not in ("utf-8", "utf_8") and not (_agrees_on_ascii(name) and _is_ascii(written)):
            converted = written + ".enc"
            try:
                _convert(written, converted, name)
            except BaseException:
                _remove(converted)
                raise
            os.replace(converted, written)
        if append and os.path.exists(path):
            with open(written, "rb") as source, open(path, "ab") as target:
                shutil.copyfileobj(source, target, _CHUNK)
        else:
            os.replace(written, path)
    finally:
        _remove(written)


def count_occurrences(path: str, text: bytes) -> int:
    """How many times a run of bytes occurs in a file."""
    found, tail = 0, b""
    with open(path, "rb") as handle:
        while chunk := handle.read(_CHUNK):
            # The end of the last chunk is looked at again, so a match cut in two by a chunk boundary is seen.
            window = tail + chunk
            found += window.count(text)
            keep = len(text) - 1
            tail = window[-keep:] if keep else b""
    return found


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
