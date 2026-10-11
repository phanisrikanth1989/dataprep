"""Extract delimited fields: one column's text is split at a separator and its pieces become columns."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

import polars as pl

from ...column_types import BLANKS, plain_text
from ...errors import ConfigurationError
from ...job.keys import Key, Kind
from ...rows import first_of, hidden, shown, visible
from ..base import Transform
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

_PIECES, _CODE, _WHY, _DIES = "__extract_pieces", "__extract_code", "__extract_why", "__extract_dies"


class Fault(NamedTuple):
    """Something that turns a row away: where, v1's code for it, what is said, and whether it can fail the job."""

    wrong: pl.Expr
    code: str
    why: pl.Expr
    dies: bool


def _separator(value: Optional[str]) -> str:
    # As in v1: quotes around it are no part of it, and nothing given is a semicolon.
    return (value or "").strip('"').strip("'") or ";"


class ExtractFields(Transform):
    """What the components that make columns out of one column's text have in common.

    The columns the output schema declares and the input does not bring
    are the extracted ones: the first takes the first piece, and so on. A
    piece that is not there is missing, and pieces beyond the last column
    are dropped. The other output columns are handed on as they came; an
    input column the output does not declare is dropped.

    A subclass says how a text falls into pieces (``pieces``).
    """

    outputs = {"main": ("flow", "main"), "reject": ("reject",)}
    # Whether a row with no source is left out without a word unless the job says otherwise.
    skips_missing = True

    def problems(self) -> List[str]:
        names = [column.name for column in self.input_schema]
        field = self.config["field"]
        return [f"field: there is no column '{field}' ({', '.join(names)})"] if names and field not in names else []

    def pieces(self, text: pl.Expr, wanted: int) -> Tuple[pl.Expr, List[Fault]]:
        """The pieces of a text, as a list of texts, and what turns a row away for them.

        Args:
            text: The source column as text; never missing where it is read.
            wanted: How many columns there are to fill.
        """
        raise NotImplementedError

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        (frame,) = inputs.values()
        config, field = self.config, self.config["field"]
        types = frame.collect_schema()
        names = visible(types.names())
        if field not in names:
            raise ConfigurationError(f"field: there is no column '{field}' ({', '.join(names)})")
        declared = [column.name for column in self.schema] or names
        new = [name for name in declared if name not in names]

        source = pl.col(field)
        text = source if types[field] == pl.String else plain_text(source, types[field], self.declared(field))
        faults: List[Fault] = []
        if config.get("ignore_source_null", self.skips_missing):
            frame = frame.filter(source.is_not_null())
        else:
            faults.append(Fault(source.is_null(), "NULL_SOURCE", pl.lit(f"Source column {field!r} is null"), False))
        pieces, more = self.pieces(text, len(new))
        # A fault is looked for only in a row no earlier one has turned away: a missing source has no pieces.
        faults += more
        code = pl.coalesce([pl.when(fault.wrong).then(pl.lit(fault.code)) for fault in faults]) if faults else pl.lit(None, dtype=pl.String)
        why = pl.coalesce([pl.when(fault.wrong).then(fault.why) for fault in faults]) if faults else pl.lit(None, dtype=pl.String)
        dies = pl.coalesce([pl.when(fault.wrong).then(pl.lit(fault.dies)) for fault in faults]) if faults else pl.lit(False)
        flagged = frame.with_columns(pieces.alias(_PIECES)).with_columns(
            code.alias(_CODE), why.alias(_WHY), dies.fill_null(False).alias(_DIES))
        bad = pl.col(_CODE).is_not_null()

        if config["die_on_error"] and any(fault.dies for fault in faults):
            fatal = flagged.filter(pl.col(_DIES))
            self.check(
                fatal.select(pl.len().alias("rows"), pl.col(_WHY).first().alias("why"), *first_of(fatal)),
                lambda found: self._fatal(found) if found["rows"].item() else None,
            )
        if faults:
            flagged = self.tell_dropped(flagged, bad, pl.col(_WHY))
        carried = hidden(types.names())
        filled = [pl.col(_PIECES).list.get(at, null_on_oob=True).alias(name) for at, name in enumerate(new)]
        main = flagged.filter(~bad).with_columns(filled).select(declared + carried)
        reject = flagged.filter(bad).select(
            *names, pl.col(_CODE).alias("errorCode"), pl.col(_WHY).alias("errorMessage"), *carried)
        return {"main": main, "reject": reject}

    def _fatal(self, found: pl.DataFrame) -> str:
        rows = found["rows"].item()
        more = "" if rows == 1 else f" (the first of {rows} such rows)"
        return f"{shown(found['why'].item())}{more}{self.where(found)}"


@REGISTRY.register
class ExtractDelimitedFields(ExtractFields):
    """Split the text of the column `field` at `fieldseparator`, and hand its pieces on as columns.

    The columns the output schema declares and the input does not bring
    take the pieces, the first column the first piece. A piece that is not
    there is missing; pieces beyond the last column are dropped. The other
    output columns are handed on as they came. The pieces are text; the
    engine turns them into the types the output declares.

    The separator is taken as it is written, no pattern. A source that is
    not text is split as the text it is written as. An empty text is one
    empty piece.

    A row whose source is missing is left out without a word, or, with
    `ignore_source_null` off, leaves by the reject output (`NULL_SOURCE`).
    With `check_fields_num`, a row whose pieces are not as many as the
    columns to fill leaves by the reject output (`FIELD_COUNT_MISMATCH`),
    or fails the job under `die_on_error`. With no flow on the reject
    output the rows are dropped, and the log says how many and the first.
    """

    names = ("extract_delimited_fields", "ExtractDelimitedFields", "tExtractDelimitedFields")
    keys = (
        Key("field", required=True, doc="The column whose text is split."),
        Key("fieldseparator", default=";", nullable=True, convert=_separator,
            doc="What separates the pieces, taken as it is written; quotes around it are no part of it."),
        Key("ignore_source_null", type=bool, default=True,
            doc="Whether a row whose source is missing is left out; when off, it leaves by the reject output."),
        Key("trim", type=bool, default=False, doc="Whether blanks around each piece are dropped."),
        Key("check_fields_num", type=bool, default=False,
            doc="Whether a row is turned away when its pieces are not as many as the columns to fill."),
        Key("die_on_error", type=bool, default=False,
            doc="Whether a wrong number of pieces (under `check_fields_num`), or a missing value in a column the "
                "schema declares not nullable, fails the job; when off, the row leaves by the reject output."),
        Key("advanced_separator", kind=Kind.IGNORED, type=object, doc="Never acted on by v1."),
        Key("thousands_separator", kind=Kind.IGNORED, type=object, doc="Never acted on by v1."),
        Key("decimal_separator", kind=Kind.IGNORED, type=object, doc="Never acted on by v1."),
        Key("check_date", kind=Kind.IGNORED, type=object, doc="Never acted on by v1."),
    )

    def pieces(self, text: pl.Expr, wanted: int) -> Tuple[pl.Expr, List[Fault]]:
        pieces = text.str.split(self.config["fieldseparator"])
        if self.config["trim"]:
            pieces = pieces.list.eval(pl.element().str.strip_chars(BLANKS))
        if not self.config["check_fields_num"]:
            return pieces, []
        count = pl.col(_PIECES).list.len()
        said = pl.format(f"Expected {wanted} tokens, got {{}}", count)
        return pieces, [Fault(count != wanted, "FIELD_COUNT_MISMATCH", said, True)]
