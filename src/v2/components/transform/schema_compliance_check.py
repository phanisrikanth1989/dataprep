"""Schema compliance check: rows that do not fit a schema leave by the reject output."""
from __future__ import annotations

import codecs
import logging
import re
import time
from typing import Any, Dict, List, Optional

import polars as pl

from ...column_types import chrono_format, plain_text
from ...job.keys import Key, Kind
from ..base import Transform
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

_BAD, _WHY = "__check_bad", "__check_why"
_CODE = 8
_NUMBERS = ("int", "float", "Decimal")
_BLANKS = " \t\n\r\x0b\x0c"
_TRUE_OR_FALSE = ("true", "false", "1", "0", "yes", "no", "")
# Java's date letters, which v1 reads in a pattern wherever they stand, as the strftime codes it makes of them.
_JAVA = (("yyyy", "%Y"), ("yy", "%y"), ("MM", "%m"), ("dd", "%d"), ("HH", "%H"), ("hh", "%I"), ("mm", "%M"),
         ("SSS", "%f"), ("ss", "%S"), ("a", "%p"))
# Encodings in which every character is one byte: a length in bytes is the length in characters.
_ONE_BYTE = ("ascii", "latin-1", "iso8859-1", "iso8859-15", "cp1252")


# ------------------------------------------------------------------
# Whether a date fits its pattern, as v1 has it
# ------------------------------------------------------------------
#
# v1 asks pandas to read the text by the pattern. pandas has two readers: one of its own for a pattern that is
# ISO 8601 (year, month, day, then the time, in that order), and Python's for any other. Each is written out
# here as the text it takes, part by part; the calendar is asked afterwards whether the day exists.

_ISO_PATTERN = re.compile(r"^%Y(?:([-/ \\.]?)%m(?:\1%d(?:[ T]%H(?::%M(?::%S(?:%z|\.%f(?:%z)?)?)?)?)?)?)?$")
_MONTH, _HOUR12 = "1[0-2]|0[1-9]|[1-9]", "1[0-2]|0[1-9]|[1-9]"
_HOUR, _MINUTE, _SECOND = "2[0-3]|[01][0-9]|[0-9]", "[0-5][0-9]|[0-9]", "6[01]|[0-5][0-9]|[0-9]"
_PYTHON_PARTS = {
    "Y": "(?P<Y>[0-9]{4})", "y": "(?P<y>[0-9]{2})", "m": f"(?P<m>{_MONTH})",
    "d": "(?P<d>3[01]|[12][0-9]|0[1-9]|[1-9]| [1-9])", "H": f"(?:{_HOUR})", "I": f"(?:{_HOUR12})",
    "M": f"(?:{_MINUTE})", "S": f"(?:{_SECOND})", "f": "[0-9]{1,9}", "p": "(?:am|pm)",
    "z": "(?:[+-][0-9]{2}:?[0-5][0-9](?::?[0-5][0-9](?:\\.[0-9]{1,6})?)?|(?-i:Z))", "%": "%",
}
_ISO_PARTS = dict(
    _PYTHON_PARTS, Y="(?P<Y>-?[0-9]{4})", H=f"(?:{_HOUR}| [0-9])", f="[0-9]*",
    z="(?:(?-i:Z)|[+-][0-9]{2}(?::?[0-9]{2}(?::?[0-9]{2})?)?)",
)


def _strftime(pattern: str) -> str:
    """A pattern with Java's date letters as the strftime codes v1 makes of them, wherever they stand."""
    for java, python in _JAVA:
        pattern = pattern.replace(java, python)
    return pattern


def _is_iso(pattern: str) -> bool:
    """Whether pandas reads a pattern with its own reader: year, month, day and time in ISO 8601's order."""
    return _ISO_PATTERN.match(pattern) is not None and pattern != "%Y%m"


def _date_regex(pattern: str) -> Optional[str]:
    """The text a pattern takes, as a regular expression; None for a pattern with a part not written out here."""
    iso = _is_iso(pattern)
    parts = _ISO_PARTS if iso else _PYTHON_PARTS
    made, at = "", 0
    while at < len(pattern):
        char = pattern[at]
        if char == "%":
            part = parts.get(pattern[at + 1:at + 2])
            if part is None:
                return None
            made, at = made + part, at + 2
        elif char.isspace():
            while at < len(pattern) and pattern[at].isspace():
                at += 1
            made += "\\s+"
        else:
            made, at = made + re.escape(char), at + 1
    return f"(?i)^(?:{made})$"


def date_fits(text: pl.Expr, pattern: str) -> pl.Expr:
    """Whether a text is a date written by a strftime pattern, as v1 judges it."""
    regex = _date_regex(pattern)
    if regex is None:
        # A part of a date that is not written out here (a month by name): by Polars' own reading.
        return text.str.strptime(pl.Datetime("us"), chrono_format(pattern, parsing=True), strict=False).is_not_null()
    found = text.str.extract_groups(regex)
    names = re.findall(r"\(\?P<(\w)>", regex)

    def part(name: str, otherwise: int) -> pl.Expr:
        if name not in names:
            return pl.lit(otherwise, dtype=pl.Int32)
        return found.struct.field(name).str.strip_chars(" -").cast(pl.Int32, strict=False)

    year = part("Y", 1900)
    if "y" in names and "Y" not in names:
        # Only whether February has 29 days is asked of the year, and 19yy and 20yy agree on that.
        year = part("y", 0) + 2000
    month, day = part("m", 1), part("d", 1)
    leap = (year % 4 == 0) & ((year % 100 != 0) | (year % 400 == 0))
    last = pl.when(month == 2).then(pl.when(leap).then(29).otherwise(28)).when(month.is_in([4, 6, 9, 11])).then(30).otherwise(31)
    fits = text.str.contains(regex) & (day <= last)
    # Python has no year 0; pandas' own reader has.
    return (fits if _is_iso(pattern) else fits & (year >= 1)).fill_null(False)


def _charset(value: Optional[str]) -> str:
    name = (value or "").strip() or "utf-8"
    try:
        known = codecs.lookup(name).name
    except LookupError:
        raise ValueError(f"'{name}' is no character set Python knows") from None
    if known != "utf-8" and known not in _ONE_BYTE:
        raise ValueError(f"v2 counts bytes in UTF-8 and in one-byte character sets only; '{name}' is neither")
    return known


_COLUMN = (
    Key("name", required=True, doc="The column."),
    Key("type", required=True, doc="What its values have to be readable as: int, float, Decimal, bool, datetime; any other is not checked."),
    Key("nullable", type=bool, default=True, doc="Whether it may be missing."),
    Key("length", type=int, default=-1, nullable=True, doc="The most characters its text may have; none when not above 0."),
    Key("date_pattern", default="", nullable=True, doc="The pattern a date is held to under `strict_date_check`."),
    Key("pattern", kind=Kind.IGNORED, type=object, doc="Not read: v1 reads `date_pattern` alone."),
    Key("key", kind=Kind.IGNORED, type=object, doc="Not read."),
    Key("precision", kind=Kind.IGNORED, type=object, doc="Not read."),
    Key("default", kind=Kind.IGNORED, type=object, doc="Not read."),
    Key("comment", kind=Kind.IGNORED, type=object, doc="Not read."),
    Key("original_type", kind=Kind.IGNORED, type=object, doc="Not read."),
)
_LISTED = (
    Key("column", required=True, doc="A column to check."),
    Key("nullable", type=bool, default=None, nullable=True, doc="Whether it may be missing; the schema's word when left out."),
    Key("selected_type", kind=Kind.IGNORED, type=object, doc="Never read by v1."),
    Key("date_pattern", kind=Kind.IGNORED, type=object, doc="Never read by v1."),
    Key("max_length", kind=Kind.IGNORED, type=object, doc="Never read by v1."),
)
_EMPTY = (
    Key("column", required=True, doc="The column."),
    Key("empty_is_null", type=bool, required=True, doc="Whether text with nothing in it counts as missing there."),
)


@REGISTRY.register
class SchemaComplianceCheck(Transform):
    """Hand on the rows that fit the schema written in `schema`, and the others by the reject output.

    For each column of that schema a row is looked at as it arrives: may
    the value be missing; can it be read as a number or as true or false;
    does a date fit its pattern (under `strict_date_check`); is its text
    within `length`. A row with any fault leaves by the reject output as it
    came, with `errorCode` 8 and an `errorMessage` naming every fault,
    `column:what`, joined by `;`.

    With no flow on the reject output the rows are dropped, and the log
    says how many and which was the first.
    """

    names = ("schema_compliance_check", "SchemaComplianceCheck", "tSchemaComplianceCheck")
    outputs = {"main": ("flow", "main"), "reject": ("reject",)}
    keys = (
        Key("schema", type=list, required=True, items=_COLUMN, doc="The columns to check, each with what is asked of it."),
        Key("check_another", type=bool, default=False, doc="Whether only the columns of `checkcols` are checked."),
        Key("checkcols", type=list, default=[], items=_LISTED, doc="The columns to check under `check_another`."),
        Key("all_empty_are_null", type=bool, default=True,
            doc="Whether text with nothing but blanks in it counts as missing, in every column."),
        Key("empty_null_table", type=list, default=[], items=_EMPTY,
            doc="The same, column by column; read only when `all_empty_are_null` is off."),
        Key("strict_date_check", type=bool, default=False, doc="Whether a date has to fit its column's pattern."),
        Key("check_string_by_byte_length", type=bool, default=False, doc="Whether `length` counts bytes, in `charset`."),
        Key("charset", default="utf-8", nullable=True, convert=_charset, doc="The character set bytes are counted in."),
        Key("die_on_error", type=bool, default=True,
            doc="Whether a value that arrives missing in a column the component's own output schema declares not "
                "nullable fails the job; when off, the row leaves by the reject output. (Empty text is not missing "
                "to that schema.)"),
        Key("check_all", kind=Kind.IGNORED, type=object, doc="What v1 does whenever `check_another` is off."),
        Key("customer", kind=Kind.IGNORED, type=object, doc="v1 only warns that it does nothing."),
        Key("sub_string", kind=Kind.IGNORED, type=object, doc="v1 only warns that it does nothing."),
        Key("fast_date_check", kind=Kind.IGNORED, type=object, doc="v1 only warns that it does nothing."),
        Key("ignore_timezone", kind=Kind.IGNORED, type=object, doc="v1 only warns that it does nothing."),
    )

    def problems(self) -> List[str]:
        """A date pattern that is none, where dates are held to their patterns."""
        found = []
        for at, column in enumerate(self.config["schema"] if self.config["strict_date_check"] else []):
            pattern = _strftime(column["date_pattern"] or "")
            if column["type"] != "datetime" or not pattern:
                continue
            try:
                time.strptime("", pattern)
            except ValueError as exc:
                if "bad directive" in str(exc) or "stray %" in str(exc):
                    why = str(exc).split(" in format ")[0]
                    found.append(f"schema[{at}].date_pattern: '{column['date_pattern']}' is no pattern of a date: {why}")
        return found

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        (frame,) = inputs.values()
        config = self.config
        types = frame.collect_schema()
        listed = {entry["column"]: entry for entry in config["checkcols"]} if config["check_another"] else {}
        empties = {} if config["all_empty_are_null"] else {
            entry["column"]: entry["empty_is_null"] for entry in config["empty_null_table"]
        }

        faults: List[pl.Expr] = []
        for column in config["schema"]:
            name = column["name"]
            if (listed and name not in listed) or name not in types:
                continue
            nullable = column["nullable"]
            if listed.get(name, {}).get("nullable") is not None:
                nullable = listed[name]["nullable"]
            faults += self._faults(column, types[name], nullable, empties.get(name, config["all_empty_are_null"]))
        if not faults:
            return {"main": frame, "reject": self._rejects(frame.clear().with_columns(pl.lit(None, dtype=pl.String).alias(_WHY)))}

        # Every fault of a row, in the order of the schema's columns and of the checks.
        why = pl.concat_str([fault.fill_null("") + pl.lit(";") for fault in faults]).str.replace_all(";+", ";")
        why = why.str.strip_chars(";")
        flagged = frame.with_columns(why.alias(_WHY)).with_columns((pl.col(_WHY) != "").alias(_BAD))
        flagged = self.tell_dropped(flagged, pl.col(_BAD), pl.col(_WHY))
        return {
            "main": flagged.filter(~pl.col(_BAD)).drop(_BAD, _WHY),
            "reject": self._rejects(flagged.filter(pl.col(_BAD)).drop(_BAD)),
        }

    def _faults(self, column: Dict[str, Any], dtype: pl.DataType, nullable: bool, empty_is_missing: bool) -> List[pl.Expr]:
        """What can be wrong with one column, each as its message where it is wrong and nothing where it is not."""
        name, kind, value = column["name"], column["type"], pl.col(column["name"])
        # A typed value as the text it is written as: a day alone where it has no time, a Decimal unpadded.
        text = value if dtype == pl.String else plain_text(value, dtype, self.declared(name))
        missing = value.is_null()
        if empty_is_missing and dtype == pl.String:
            missing = missing | (value.str.strip_chars() == "").fill_null(False)
        there = ~missing

        def fault(wrong: pl.Expr, what: str) -> pl.Expr:
            return pl.when(wrong).then(pl.lit(f"{name}:{what}"))

        found = []
        if not nullable:
            found.append(fault(missing, "cannot be null"))
        if kind in _NUMBERS and dtype == pl.String:
            # The blanks of ASCII alone are no part of a number, as v1 has it.
            number = value.str.strip_chars(_BLANKS).cast(pl.Float64, strict=False)
            found.append(fault(there & (number.is_null() | number.is_nan()), "invalid type"))
        elif kind == "bool" and dtype != pl.Boolean:
            found.append(fault(there & ~text.str.to_lowercase().is_in(_TRUE_OR_FALSE), "invalid type"))
        elif kind == "datetime" and self.config["strict_date_check"] and column["date_pattern"] and not dtype.is_temporal():
            found.append(fault(there & ~date_fits(text, _strftime(column["date_pattern"])), "invalid date format"))
        most = column["length"]
        if kind == "str" and most is not None and most > 0:
            in_bytes = self.config["check_string_by_byte_length"] and self.config["charset"] == "utf-8"
            length = text.str.len_bytes() if in_bytes else text.str.len_chars()
            found.append(fault(there & (length > most), "exceed max length"))
        return found

    @staticmethod
    def _rejects(frame: pl.LazyFrame) -> pl.LazyFrame:
        """The rows that do not fit, as they came, with v1's code for them and what is wrong."""
        return frame.with_columns(pl.lit(_CODE, dtype=pl.Int64).alias("errorCode"), pl.col(_WHY).alias("errorMessage")).drop(_WHY)
