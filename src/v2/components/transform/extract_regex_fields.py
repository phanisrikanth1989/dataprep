"""Extract regex fields: a pattern is looked for in one column's text and what its groups hold becomes columns."""
from __future__ import annotations

import re
from typing import List, Tuple

import polars as pl

from ...job.keys import Key
from .extract_delimited_fields import ExtractFields, Fault
from ..registry import REGISTRY


def _pattern(value: str) -> str:
    """A pattern as it is looked for: v1 reads two backslashes as one."""
    value = value.replace("\\\\", "\\")
    if not value:
        raise ValueError("there is no pattern")
    odd = _read_differently(value)
    if odd:
        raise ValueError(f"Python and Polars read {odd} differently; write the pattern without it")
    try:
        re.compile(value)
    except re.error as exc:
        raise ValueError(f"this is no pattern: {exc}") from None
    try:
        pl.select(pl.lit("").str.contains(value))
    except Exception as exc:  # noqa: BLE001 -- Polars decides what a pattern it can look for is
        detail = " ".join(str(exc).split())[:160]
        raise ValueError(f"v2 cannot look for this pattern: {detail}") from None
    return value


def _read_differently(pattern: str) -> str:
    """What in a pattern both Python and Polars take and do not read alike; nothing when there is none.

    Inside ``[...]`` Polars reads a second ``[`` as a set within the set
    and ``&&``, ``--`` and ``~~`` as ways to put sets together, where
    Python reads plain characters; and ``\\<`` and ``\\>`` are the start
    and the end of a word to Polars and those two characters to Python.
    """
    at, inside = 0, False
    while at < len(pattern):
        char, pair = pattern[at], pattern[at:at + 2]
        if char == "\\":
            if not inside and pair in ("\\<", "\\>"):
                return f"`{pair}`"
            at += 2
            continue
        if not inside:
            if char == "[":
                inside = True
                # A `]` that comes first, also after `^`, is a character of the set.
                at += 2 if pattern[at + 1:at + 2] == "^" else 1
                if pattern[at:at + 1] == "]":
                    at += 1
                continue
        elif char == "]":
            inside = False
        elif char == "[":
            return "a `[` inside `[...]`"
        elif pair in ("&&", "--", "~~"):
            return f"`{pair}` inside `[...]`"
        at += 1
    return ""


def _as_python_shows(text: pl.Expr) -> pl.Expr:
    """A text the way Python shows it (`repr`), which is how v1 says the text a pattern was not found in."""
    shown = text.str.replace_all("\\", "\\\\", literal=True)
    for char, written in (("\n", "\\n"), ("\r", "\\r"), ("\t", "\\t")):
        shown = shown.str.replace_all(char, written, literal=True)
    single, double = text.str.contains("'", literal=True), text.str.contains('"', literal=True)
    return (
        pl.when(single & ~double).then(pl.lit('"') + shown + pl.lit('"'))
        .otherwise(pl.lit("'") + shown.str.replace_all("'", "\\'", literal=True) + pl.lit("'"))
    )


@REGISTRY.register
class ExtractRegexFields(ExtractFields):
    """Look for the pattern `regex` in the text of the column `field`, and hand what its groups hold on as columns.

    The pattern is looked for anywhere in the text, and the first place it
    is found counts. The columns the output schema declares and the input
    does not bring take the groups, the first column the first group. A
    group that took no part is missing, and so is a column beyond the last
    group. The other output columns are handed on as they came. What a
    group holds is text; the engine turns it into the type the output
    declares.

    A row whose text the pattern is not found in fails the job, or, with
    `die_on_error` off, leaves by the reject output (`NO_MATCH`). A row
    whose source is missing always leaves by the reject output
    (`NULL_SOURCE`). With `check_fields_num`, a pattern whose groups are
    not as many as the columns to fill turns away every row it is found in
    (`FIELD_COUNT_MISMATCH`).

    The pattern is Python's, as far as Polars can look for it and reads it
    the same way: a pattern Polars does not take (lookaround, a
    backreference), or one of the few things the two read differently,
    refuses the job.
    """

    names = ("extract_regex_fields", "ExtractRegexFields", "tExtractRegexFields")
    skips_missing = False
    keys = (
        Key("field", required=True, doc="The column whose text is looked in."),
        Key("regex", required=True, convert=_pattern, doc="The pattern, with a group for each column to fill."),
        Key("check_fields_num", type=bool, default=False,
            doc="Whether every row is turned away when the pattern's groups are not as many as the columns to fill."),
        Key("die_on_error", type=bool, default=True,
            doc="Whether a text the pattern is not found in (or, under `check_fields_num`, groups that are not as "
                "many as the columns), or a missing value in a column the schema declares not nullable, fails the "
                "job; when off, the row leaves by the reject output."),
    )

    def problems(self) -> List[str]:
        if self.config["regex"] is None:
            return ["regex: there is no pattern"]
        return super().problems()

    def pieces(self, text: pl.Expr, wanted: int) -> Tuple[pl.Expr, List[Fault]]:
        pattern = self.config["regex"]
        read = re.compile(pattern)
        # Polars names a group by its name, or by its number where it has none.
        named = {number: name for name, number in read.groupindex.items()}
        groups = [named.get(number, str(number)) for number in range(1, read.groups + 1)]
        found = text.str.extract_groups(pattern)
        held = [found.struct.field(name) for name in groups]
        pieces = pl.concat_list(held) if held else pl.lit([], dtype=pl.List(pl.String))
        faults = [Fault(~text.str.contains(pattern), "NO_MATCH", pl.lit("Regex did not match: ") + _as_python_shows(text), True)]
        if self.config["check_fields_num"] and read.groups != wanted:
            said = pl.lit(f"Expected {wanted} capture groups, got {read.groups}")
            faults.append(Fault(pl.lit(True), "FIELD_COUNT_MISMATCH", said, True))
        return pieces, faults
