"""Fixed flow input: rows written in the job config itself."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from ...column_types import held_frame, to_text
from ...job.keys import Key, Looked
from ...job.model import Column
from ...rows import hidden, visible
from ..base import Source
from ..registry import REGISTRY

# The escapes v1 reads in a separator, in v1's order.
_ESCAPES = (("\\n", "\n"), ("\\t", "\t"), ("\\r", "\r"), ("\\|", "|"))
_WHOLE = re.compile(r"-?\d+")
_FRACTION = re.compile(r"-?\d*\.\d+")
_GLOBAL = re.compile(r'globalMap\.get\("([^"]+)"\)')


def _separator(value: str) -> str:
    for written, meant in _ESCAPES:
        value = value.replace(written, meant)
    if value == "":
        raise ValueError("a separator of nothing cannot split the content")
    return value


def _count(value: int) -> int:
    if value < 0:
        raise ValueError(f"{value} rows cannot be made; give 0 or more")
    return value


def _number(value: Any) -> Any:
    """Text that is a plain number as that number, as v1 has it; anything else as it is."""
    if isinstance(value, str):
        stripped = value.strip()
        if _WHOLE.fullmatch(stripped):
            return int(stripped)
        if _FRACTION.fullmatch(stripped):
            return float(stripped)
    return value


_VALUE = (
    Key("schema_column", required=True, doc="The column."),
    Key("value", type=object, default=None, nullable=True, takes_looked=True, doc="What it holds in every row."),
)
_ENTRY = (
    Key("element_ref", default="", doc="The column."),
    Key("value", type=object, default=None, nullable=True, takes_looked=True, doc="What it holds in this row."),
)


@REGISTRY.register
class FixedFlowInput(Source):
    """Hand on rows that are written in the job config.

    Three ways to write them, the first that is switched on in this order:
    `use_inlinecontent` (text, a row a line and a column a field; a blank
    line is no row), `use_intable` (a list of entries, a row for every run
    of as many entries as there are columns), and one row of `values_config`
    repeated `nb_rows` times, which is also what happens when none is on.

    As in v1, text that is a plain number is that number before the
    column's type is looked at (`007` is 7, in a text column too), and a
    value written `globalMap.get("KEY")` is that entry of globalMap. What
    an entry holds is handed on as it is: `00123` looked up stays `00123`.

    The rows are held in memory: they are as many as the config writes.
    A failure names a row as `line 3 of the inline content of <id>` or
    `row 3 of <id>`.
    """

    names = ("fixed_flow_input", "FixedFlowInputComponent", "FixedFlowInput", "tFixedFlowInput")
    keys = (
        Key("nb_rows", type=int, default=1, convert=_count, doc="How many times the single row is made."),
        Key("use_singlemode", type=bool, default=True, doc="Whether the rows are one row of `values_config`, repeated."),
        Key("use_intable", type=bool, default=False, doc="Whether the rows are those of `intable`."),
        Key("use_inlinecontent", type=bool, default=False, doc="Whether the rows are the lines of `inline_content`."),
        Key("values_config", type=list, default=[], items=_VALUE, doc="The single row: each column with its value."),
        Key("intable", type=list, default=[], items=_ENTRY, doc="The table, entry after entry, row after row."),
        Key("inline_content", default="", takes_looked=True, doc="The rows as text."),
        Key("row_separator", default="\n", convert=_separator,
            doc="What ends a row of `inline_content`; `\\n`, `\\t`, `\\r` and `\\|` may be written as escapes."),
        Key("field_separator", default=";", convert=_separator, doc="What separates its fields; the same escapes."),
        Key("die_on_error", type=bool, default=True,
            doc="Whether a missing value in a column the schema declares not nullable fails the job; "
                "when off, the row is dropped."),
    )

    def problems(self) -> List[str]:
        return [] if self.schema else ["schema: a fixed flow input needs its columns declared"]

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def read(self) -> Dict[str, pl.LazyFrame]:
        names = [column.name for column in self.schema]
        rows, places = self._rows(names)
        frame = held_frame(self.schema, rows)
        frame = frame.with_columns(pl.Series(self.row_number, places, dtype=pl.UInt32))
        frame = self.picked(frame).with_columns(self.key_copies())
        return {"main": frame.select(visible(frame.columns) + hidden(frame.columns)).lazy()}

    def as_read(self, column: Column, text: pl.Expr) -> pl.Expr:
        """Text as this source holds it: a plain number written as text is the number (007 is 7)."""
        stripped = text.str.strip_chars()
        whole = stripped.str.contains(r"^-?\d+$") & (stripped.str.len_chars() <= 18)
        fraction = stripped.str.contains(r"^-?\d*\.\d+$")
        return (
            pl.when(whole).then(stripped.cast(pl.Int64, strict=False).cast(pl.String))
            .when(fraction).then(to_text(stripped.cast(pl.Float64, strict=False), pl.Float64()))
            .otherwise(text)
        )

    def locate(self, number: int) -> str:
        if self.config["use_inlinecontent"]:
            return f"line {number} of the inline content of {self.id}"
        return f"row {number} of {self.id}"

    @property
    def place_kind(self) -> str:
        return "lines" if self.config["use_inlinecontent"] else "rows"

    @property
    def place_why(self) -> str:
        return "holds its rows as lines of text" if self.config["use_inlinecontent"] else "holds its rows in its config"

    def _rows(self, names: List[str]) -> Tuple[List[Dict[str, Any]], List[int]]:
        """The rows, each as column to value, and the place of each as ``locate`` names it."""
        config = self.config
        if config["use_inlinecontent"]:
            content = config["inline_content"]
            if isinstance(content, Looked):
                # All of it was looked up: one value, whatever it holds, and no text to take apart.
                return [{name: self._held(content if at == 0 else None) for at, name in enumerate(names)}], [1]
            rows, places = [], []
            for place, line in enumerate(content.split(config["row_separator"]), start=1):
                if not line.strip():
                    continue
                fields = line.split(config["field_separator"])
                rows.append({name: self._held(fields[at] if at < len(fields) else None) for at, name in enumerate(names)})
                places.append(place)
            return rows, places
        if config["use_intable"]:
            entries, width = config["intable"], len(names)
            rows = []
            for start in range(0, len(entries), width):
                # An entry for what is no column is held and never read.
                rows.append({entry["element_ref"]: self._held(entry["value"]) for entry in entries[start:start + width]})
            return rows, list(range(1, len(rows) + 1))
        given = {entry["schema_column"]: entry["value"] for entry in config["values_config"]}
        row = {name: self._held(given.get(name)) for name in names}
        return [dict(row) for _ in range(config["nb_rows"])], list(range(1, config["nb_rows"] + 1))

    def _held(self, value: Any) -> Any:
        """A value as written, as what the row holds."""
        if isinstance(value, Looked):
            # Looked up while the job runs: data, handed on as it is. `00123` is no number written as text.
            return value.value
        if isinstance(value, str):
            entry: Optional["re.Match[str]"] = _GLOBAL.search(value)
            if entry and self.global_map.get(entry.group(1)) is not None:
                return self.global_map[entry.group(1)]
        return _number(value)
