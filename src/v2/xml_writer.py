"""Writing XML: the text of a document made by Polars expressions, with no Python in the pass.

Nothing here builds a tree. A row becomes one line of text, and the lines
are sunk as they come. What a library would see to is seen to here:
escaping, the characters XML cannot hold, the names an element or an
attribute may have, and a last reading of the finished file before it is
put in place.
"""
from __future__ import annotations

import re
from typing import List
from xml.parsers import expat

import polars as pl

from . import xml_reader

# The characters XML 1.0 cannot hold, as a pattern Polars reads: the control characters but tab and the two
# line ends, and the two that are no characters at all.
NOT_IN_XML = "[\\x00-\\x08\\x0B\\x0C\\x0E-\\x1F\\x{FFFE}\\x{FFFF}]"
# What an element says to be marked as holding nothing, and what the document has to declare for it.
NIL = ' xsi:nil="true"'
NIL_NAMESPACE = ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
_NAME = re.compile(r"[A-Za-z_][\w.\-]*")
# A line end inside a value is written by its number: every row stays one line, and a carriage return is read
# back as one (a parser turns a bare one into a line feed).
_IN_TEXT = (["&", "<", ">", "\r", "\n"], ["&amp;", "&lt;", "&gt;", "&#13;", "&#10;"])
# In an attribute a parser turns every white space but a blank into a blank, unless it is written by its number.
_IN_ATTRIBUTE = (_IN_TEXT[0] + ['"', "\t"], _IN_TEXT[1] + ["&quot;", "&#9;"])


def is_name(name: str) -> bool:
    """Whether a text is a name an element or an attribute may have. A prefix (`a:b`) is none: it needs a namespace."""
    return _NAME.fullmatch(name) is not None


def text(value: pl.Expr) -> pl.Expr:
    """A text as it stands inside an element."""
    return value.str.replace_many(*_IN_TEXT)


def attribute(value: pl.Expr) -> pl.Expr:
    """A text as it stands inside the quotes of an attribute."""
    return value.str.replace_many(*_IN_ATTRIBUTE)


def declaration(encoding: str) -> str:
    """The line a document starts with."""
    return f'<?xml version="1.0" encoding="{encoding}"?>'


def lines(parts: List[pl.LazyFrame]) -> pl.LazyFrame:
    """Frames of one text column each, one after another, as the lines of one file."""
    return pl.concat([part.select(pl.all().alias("line")) for part in parts], how="vertical")


def read_back(path: str, shown: str) -> None:
    """Read a finished document once, as any reader would, before it is put in place.

    It is read by expat, which is in Python itself and keeps nothing of
    what it reads. An encoding expat does not know (it knows UTF-8, UTF-16
    and the encodings of one byte a character) is read by lxml.

    Raises:
        xml_reader.Fault: The file is no well-formed XML. That is a fault of
            whoever wrote it, found before anyone else reads the file.
    """
    try:
        with open(path, "rb") as source:
            expat.ParserCreate().ParseFile(source)
        return
    except expat.ExpatError as fault:
        if fault.code != expat.errors.codes[expat.errors.XML_ERROR_UNKNOWN_ENCODING]:
            raise xml_reader.Fault(f"what was written to '{shown}' is not well-formed XML: {fault}") from None
    except (ValueError, LookupError):
        # How Python's expat says it does not know an encoding of more than one byte a character.
        pass
    xml_reader.needs_lxml()
    etree = xml_reader.etree
    try:
        with open(path, "rb") as source:
            for _, element in etree.iterparse(source, events=("end",), **xml_reader.settings(large_values=True)):
                if element.getparent() is not None and element.getparent().getparent() is None:
                    # A child of the root: let go of it, and of what stood before it.
                    xml_reader._free(element)
    except etree.XMLSyntaxError as fault:
        raise xml_reader.Fault(f"what was written to '{shown}' is not well-formed XML: {fault.msg}") from None
