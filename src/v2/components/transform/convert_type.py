"""Convert type: read the values of columns as the type the output declares."""
from __future__ import annotations

import logging
from typing import Dict, List, Tuple

import polars as pl

from ...column_types import from_text, to_text
from ...job.keys import Key
from ...rows import first_of, hidden, shown, visible
from ..base import Transform
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

_BAD, _WHY = "__convert_bad", "__convert_why"

_PAIR = (
    Key("input_column", required=True, doc="The column to read."),
    Key("output_column", default="", doc="The column to hand the value on in; the same one when empty."),
)


@REGISTRY.register
class ConvertType(Transform):
    """Read the columns of `manualtable` as the type the output schema declares for them.

    A value is read as text, by the rules every reader of v2 has for the
    type. Text that cannot be read as the type turns its row away: to the
    reject output, with `error_code` CONVERSION_ERROR and an `error_message`,
    or it fails the job under `dieonerror`. Nothing in a value is a missing
    value, never a fault. A pair with another output column adds that
    column and keeps the one it read.

    `autocast` asks for nothing more in v2: the engine reads every value as
    the type its output column declares, as after any component.

    v1 on today's pandas turns away every row a pair converts in place, so
    this is held against v1 only where a pair names another output column.
    """

    names = ("convert_type", "ConvertType", "tConvertType")
    outputs = {"main": ("flow", "main"), "reject": ("reject",)}
    keys = (
        Key("manualtable", type=list, default=[], items=_PAIR, doc="The columns to convert, each with its output column."),
        Key("emptytonull", type=bool, default=False, aliases=("empty_to_null",),
            doc="Whether text with nothing in it becomes a missing value, in every text column."),
        Key("dieonerror", type=bool, default=False, aliases=("die_on_error",),
            doc="Whether a value that cannot be read fails the job; off, its row goes to the reject output."),
        Key("autocast", type=bool, default=False, doc="Accepted: the engine reads values as their declared types anyway."),
    )

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        (frame,) = inputs.values()
        types = frame.collect_schema()
        names = visible(types.names())
        if self.config["emptytonull"]:
            text = [name for name in names if types[name] == pl.String]
            frame = frame.with_columns([pl.when(pl.col(name) != "").then(pl.col(name)).alias(name) for name in text])

        declared = {column.name: column for column in self.schema}
        values: List[pl.Expr] = []
        cases: List[Tuple[pl.Expr, pl.Expr]] = []
        for pair in self.config["manualtable"]:
            source = pair["input_column"].strip()
            target = pair["output_column"].strip() or source
            if source not in types:
                logger.warning(f"[{self.id}] manualtable: there is no column '{source}'; it is passed over")
                continue
            column = declared.get(target) or declared.get(source)
            if column is None or column.type == "str":
                if target != source:
                    values.append(to_text(pl.col(source), types[source]).alias(target))
                continue
            text = to_text(pl.col(source), types[source]).fill_null("")
            value, wrong = from_text(text, column)
            values.append(value.alias(f"__converted_{len(values)}:{target}"))
            cases.append((wrong, pl.format(f"Column '{source}' -> '{target}' ({column.type}): cannot read '{{}}'", text)))
        if not cases:
            plain = frame.with_columns(values) if values else frame
            return {"main": plain, "reject": _rejects(frame.clear(), names)}

        why = pl.coalesce([pl.when(wrong).then(reason) for wrong, reason in cases])
        flagged = frame.with_columns(pl.any_horizontal([wrong for wrong, _ in cases]).alias(_BAD), why.alias(_WHY))
        bad = flagged.filter(pl.col(_BAD))
        if self.config["dieonerror"]:
            self.check(
                bad.select(pl.len().alias("rows"), pl.col(_WHY).first().alias("why"), *first_of(bad)),
                lambda found: (f"Type conversion failed for {found['rows'].item()} row(s); the first: "
                               f"{shown(found['why'].item())}{self.where(found)}") if found["rows"].item() else None,
            )
        else:
            flagged = self.tell_dropped(flagged, pl.col(_BAD), pl.col(_WHY))
        renamed = [value.alias(value.meta.output_name().split(":", 1)[1]) if value.meta.output_name().startswith("__converted_")
                   else value for value in values]
        main = flagged.filter(~pl.col(_BAD)).drop(_BAD, _WHY).with_columns(renamed)
        return {"main": main, "reject": _rejects(bad.rename({_WHY: "error_message"}).drop(_BAD), names)}


def _rejects(frame: pl.LazyFrame, names: List[str]) -> pl.LazyFrame:
    """The rows turned away as they arrived, with v1's two columns."""
    held = frame.collect_schema().names()
    message = pl.col("error_message") if "error_message" in held and "error_message" not in names else pl.lit(None, dtype=pl.String)
    return frame.select(
        [pl.col(name) for name in names if name not in ("error_code", "error_message")]
        + [pl.lit("CONVERSION_ERROR").alias("error_code"), message.alias("error_message")] + hidden(held)
    )
