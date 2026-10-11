"""File input properties: the entries of a properties or an ini file as rows."""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from ...column_types import held_frame
from ...errors import ConfigurationError
from ...files import codec_name
from ...job.keys import Key
from ...rows import hidden, visible
from ..base import Source
from ..registry import REGISTRY
from .file_input_delimited import encoding

# The columns Talend's component has, which a job cannot change.
_TALEND = ("key", "value", "section")
_BLANK = " \t\f"
_ESCAPES = {"t": "\t", "n": "\n", "r": "\r", "f": "\f"}
_LINE_END = re.compile("\r\n|\r|\n")

# One property: the line it starts on, its section (None in a properties file), its key and its value.
Entry = Tuple[int, Optional[str], str, Optional[str]]


def _odd_backslashes(line: str) -> bool:
    """Whether a line ends on a backslash that is not itself escaped: it goes on in the next line."""
    return (len(line) - len(line.rstrip("\\"))) % 2 == 1


def _unescaped(text: str) -> str:
    """Java's escapes in a key or a value as the characters they mean."""
    out, at = [], 0
    while at < len(text):
        char = text[at]
        if char != "\\" or at + 1 == len(text):
            out.append(char)
            at += 1
            continue
        following = text[at + 1]
        if following == "u" and re.fullmatch("[0-9a-fA-F]{4}", text[at + 2:at + 6]):
            out.append(chr(int(text[at + 2:at + 6], 16)))
            at += 6
            continue
        out.append(_ESCAPES.get(following, following))
        at += 2
    return "".join(out)


def properties(text: str) -> List[Entry]:
    """The entries of a properties file, read as `java.util.Properties.load` reads one.

    A line that starts with `#` or `!` is a comment. A key ends at the
    first `=`, `:` or blank that is not escaped; blanks around the
    separator are no part of either side, blanks the value ends on are. A
    line that ends on an odd number of backslashes goes on in the next,
    whose leading blanks are dropped.
    """
    found: List[Entry] = []
    lines = _LINE_END.split(text)
    at = 0
    while at < len(lines):
        start, line = at + 1, lines[at].lstrip(_BLANK)
        at += 1
        if not line or line[0] in "#!":
            continue
        while _odd_backslashes(line) and at < len(lines):
            line = line[:-1] + lines[at].lstrip(_BLANK)
            at += 1
        if _odd_backslashes(line):
            line = line[:-1]
        end = 0
        while end < len(line) and line[end] not in "=:" + _BLANK:
            end += 2 if line[end] == "\\" else 1
        key, rest = line[:end], line[end:].lstrip(_BLANK)
        if rest[:1] in ("=", ":"):
            rest = rest[1:].lstrip(_BLANK)
        found.append((start, None, _unescaped(key), _unescaped(rest)))
    return found


def ini(text: str) -> List[Entry]:
    """The entries of an ini file: `[section]` lines, and `key = value` or `key: value` under them.

    A line that starts with `;` or `#` is a comment. Blanks around a name,
    a key and a value are no part of them. A section with no entry gives
    one entry with no key.
    """
    found: List[Entry] = []
    section: Optional[str] = None
    for at, line in enumerate(_LINE_END.split(text), start=1):
        line = line.strip()
        if not line or line[0] in ";#":
            continue
        if line[0] == "[" and line[-1] == "]":
            section = line[1:-1].strip()
            found.append((at, section, "", None))
            continue
        if section is None:
            continue
        cut = min((place for place in (line.find("="), line.find(":")) if place >= 0), default=len(line))
        found.append((at, section, line[:cut].strip(), line[cut + 1:].strip()))
    return found


@REGISTRY.register
class FileInputProperties(Source):
    """Read a properties file, or an ini file, and hand on a row for every property.

    As Talend's component has it, the rows have the columns `key` and
    `value`, and `section` for an ini file read whole; the output schema
    says which of them are handed on, and in what order. A properties
    file is read as Java reads one (`file_format` PROPERTIES_FORMAT): its
    escapes, a key that ends at `=`, `:` or a blank, lines that go on, and
    always as ISO-8859-1. An ini file (INI_FORMAT) is read in `encoding`,
    by `retrive_mode`: one section (RETRIVE_BY_SECTION, the one
    `section_name` names), every section (RETRIVE_ALL), or the names of
    the sections alone (RETRIVE_SECTIONS). A key given twice has its last
    value, at the place of the first.

    A job written for v1 declares other columns: it then gets v1's one
    row, with each column filled from the property of its name (a row for
    each section of an ini file read whole, its name in `__section__`).

    The rows are held in memory: they are as many as the file's entries.
    A failure names a row by the line its property is on.
    """

    names = ("file_input_properties", "FileInputProperties", "tFileInputProperties")
    keys = (
        Key("path", required=True, aliases=("filename",), doc="The file to read."),
        Key("file_format", default="PROPERTIES_FORMAT", choices=("PROPERTIES_FORMAT", "INI_FORMAT"),
            doc="What the file is: a Java properties file, or an ini file."),
        Key("retrive_mode", default="RETRIVE_BY_SECTION", choices=("RETRIVE_BY_SECTION", "RETRIVE_ALL", "RETRIVE_SECTIONS"),
            doc="What of an ini file is read: one section, every section, or the names of the sections."),
        Key("section_name", default="section", doc="The section to read, for RETRIVE_BY_SECTION."),
        Key("encoding", default="ISO-8859-15", convert=encoding,
            doc="An ini file's character encoding. A properties file is always ISO-8859-1, as in Java."),
    )

    def problems(self) -> List[str]:
        found = [] if self.config["path"].strip() else ["path: the file to read has no name"]
        if not self.schema:
            found.append("schema: a properties reader needs its columns declared: key and value, as Talend has them")
        return found

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def read(self) -> Dict[str, pl.LazyFrame]:
        rows, lines = self._rows()
        frame = held_frame(self.schema, rows).with_columns(pl.Series(self.row_number, lines, dtype=pl.UInt32))
        frame = self.picked(frame).with_columns(self.key_copies())
        return {"main": frame.select(visible(frame.columns) + hidden(frame.columns)).lazy()}

    def locate(self, number: int) -> str:
        return f"line {number} of {self.config['path']}"

    def _rows(self) -> Tuple[List[Dict[str, Any]], List[int]]:
        """The rows, each as column to value, and the line each is named by."""
        config = self.config
        path = config["path"].strip()
        if not os.path.exists(path):
            raise ConfigurationError(f"File not found: '{path}'")
        plain = config["file_format"] == "PROPERTIES_FORMAT"
        name = "iso8859-1" if plain else codec_name(config["encoding"])
        try:
            with open(path, "r", encoding=name, newline="") as handle:
                text = handle.read()
        except UnicodeDecodeError:
            raise ConfigurationError(f"'{path}' is not written in {config['encoding']}: a byte in it is no character there") from None
        entries = properties(text) if plain else ini(text.lstrip("\ufeff"))
        mode = config["retrive_mode"]
        if not plain and mode == "RETRIVE_BY_SECTION":
            entries = [entry for entry in entries if entry[1] == config["section_name"]]
        if all(column.name in _TALEND for column in self.schema):
            return self._pairs(entries, names_only=not plain and mode == "RETRIVE_SECTIONS")
        return self._wide(entries, plain, mode)

    @staticmethod
    def _pairs(entries: List[Entry], names_only: bool) -> Tuple[List[Dict[str, Any]], List[int]]:
        """Talend's rows: one for each property, or one for each section when only their names are read."""
        if names_only:
            heads = [entry for entry in entries if entry[3] is None]
            return [{"section": section} for _, section, _, _ in heads], [line for line, _, _, _ in heads]
        placed: Dict[Tuple[Optional[str], str], int] = {}
        rows: List[Dict[str, Any]] = []
        lines: List[int] = []
        for line, section, key, value in entries:
            if value is None:
                continue
            at = placed.setdefault((section, key), len(rows))
            if at == len(rows):
                rows.append({"key": key, "value": value, "section": section})
                lines.append(line)
            else:
                rows[at]["value"] = value
        return rows, lines

    @staticmethod
    def _wide(entries: List[Entry], plain: bool, mode: str) -> Tuple[List[Dict[str, Any]], List[int]]:
        """v1's rows: one for the file, or one for each section of an ini file read whole."""
        if not plain and mode != "RETRIVE_BY_SECTION":
            rows: List[Dict[str, Any]] = []
            lines: List[int] = []
            for line, section, key, value in entries:
                if value is None:
                    rows.append({"__section__": section})
                    lines.append(line)
                else:
                    rows[-1][key] = value
            return rows, lines
        return [{key: value for _, _, key, value in entries if value is not None}], [1]
