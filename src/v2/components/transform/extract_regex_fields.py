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
    try:
        re.compile(value)
    except re.error as exc:
        raise ValueError(f"this is no pattern: {exc}") from None
    try:
        pl.select(pl.lit("").str.contains(value))
    except Exception as exc:  # noqa: BLE001 -- Polars decides what a pattern it can look for is
        detail = " ".join(str(exc).split())[:160]
        raise ValueError(f"v2 cannot look for this pattern (no lookaround and no backreferences): {detail}") from None
    return value


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

    The pattern is Python's, as far as Polars can look for it: no
    lookaround and no backreferences.
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
