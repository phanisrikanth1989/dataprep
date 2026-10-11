"""Pivot to columns delimited: the values of one column become the columns of a delimited file."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import polars as pl

from ...column_types import plain_text, to_text
from ...errors import ConfigurationError
from ...files import put_in_place
from ...job.keys import Key, Kind
from ...job.model import Column
from ..base import Sink, Write
from ..registry import REGISTRY
from .file_input_delimited import encoding, unescape

logger = logging.getLogger(__name__)

_PLACE, _VALUE, _HEAD = "__pivot_place", "__pivot_value", "__pivot_head"
_FUNCTIONS = ("sum", "count", "min", "max", "first", "last")


def _separator(value: str) -> str:
    value = unescape(value)
    if len(value) != 1:
        raise ValueError(f"must be one character, and {value!r} is {len(value)}")
    return value


def _columns(value: List[Any]) -> List[str]:
    if not value:
        raise ValueError("names no column to group the rows by")
    return [str(name) for name in value]


def _field(text: Optional[str], separator: str) -> str:
    """A field as pandas writes it: enclosed in quotes only where it holds the separator, a quote or a line break."""
    if text is None:
        return ""
    if separator in text or '"' in text or "\n" in text or "\r" in text:
        return '"' + text.replace('"', '""') + '"'
    return text


@REGISTRY.register
class PivotToColumnsDelimited(Sink):
    """Write one row for each group, with a column for every value of the pivot column.

    The rows are grouped by `groupbys`. Each value the pivot column holds
    becomes a column of the file, in the order the values first appear,
    and a cell holds the `aggregation_function` of the `aggregation_column`
    over the rows of its group and its pivot value. A cell no row stands
    behind is empty. Rows whose pivot value is missing take no part.

    The file's columns depend on the data, so the component cannot plan
    them: the rows are grouped in the subjob's one pass, and that table of
    groups, which is small, is held in memory and turned into columns when
    the pass is done, before the file is put in place.

    As in v1: a column of floats that are all whole is written as whole
    numbers; a sum or a count over nothing but missing values is 0, while
    the other functions leave the cell empty, and a column that would be
    empty in every row is left out; no rows in write no file at all.
    Rows that miss a group value are a group of their own, as in Talend.
    """

    names = ("pivot_to_columns_delimited", "PivotToColumnsDelimited", "tPivotToColumnsDelimited")
    keys = (
        Key("pivot_column", required=True, doc="The column whose values become columns of the file."),
        Key("aggregation_column", required=True, doc="The column whose values fill the cells."),
        Key("aggregation_function", default="sum", choices=_FUNCTIONS, doc="What a cell holds of the values behind it."),
        Key("groupbys", type=list, required=True, convert=_columns, doc="The columns to group by: a row of the file for each group."),
        Key("path", required=True, aliases=("filename",), doc="The file to write."),
        Key("create", type=bool, default=True, doc="Whether the file is written; folders that are missing are made."),
        Key("rowseparator", default="\n", convert=unescape, doc="What ends a row."),
        Key("fieldseparator", default=";", convert=_separator, doc="What separates the fields: one character."),
        Key("encoding", default="ISO-8859-15", convert=encoding, doc="The file's character encoding."),
        Key("delete_emptyfile", type=bool, default=False, doc="Whether no file is left when there is no group to write."),
        Key("advanced_separator", kind=Kind.IGNORED, type=object, doc="Not acted on by v1."),
        Key("thousands_separator", kind=Kind.IGNORED, type=object, doc="Not acted on by v1."),
        Key("decimal_separator", kind=Kind.IGNORED, type=object, doc="Not acted on by v1."),
        Key("csv_option", kind=Kind.IGNORED, type=object, doc="Not acted on by v1."),
        Key("escape_char", kind=Kind.IGNORED, type=object, doc="Not acted on by v1."),
        Key("text_enclosure", kind=Kind.IGNORED, type=object, doc="Not acted on by v1."),
    )

    def problems(self) -> List[str]:
        """What the config and the declared input columns show to be wrong before any row is read."""
        if not self.config["path"]:
            return ["path: the file to write has no name"]
        if not self.input_schema:
            return []
        kinds = {column.name: column.type in ("int", "float", "Decimal") for column in self.input_schema}
        return self._wrong(kinds)

    def _wrong(self, numeric: Dict[str, bool]) -> List[str]:
        """What is wrong with the columns the config names, given the columns there are and which hold numbers."""
        config = self.config
        named = (("pivot_column", [config["pivot_column"]]), ("aggregation_column", [config["aggregation_column"]]),
                 ("groupbys", config["groupbys"]))
        found = [f"{key}: there is no column '{name}'" for key, names in named for name in names if name not in numeric]
        value = config["aggregation_column"]
        if not found and config["aggregation_function"] == "sum" and not numeric[value]:
            found.append(f"aggregation_function: sum needs a column of numbers, and '{value}' is not one")
        return found

    def write(self, frame: pl.LazyFrame) -> Write:
        config = self.config
        pivot, value, groups = config["pivot_column"], config["aggregation_column"], config["groupbys"]
        function, path = config["aggregation_function"], config["path"]
        types = frame.collect_schema()
        wrong = self._wrong({name: types[name].is_numeric() for name in types.names()})
        if wrong:
            raise ConfigurationError("; ".join(wrong))
        if config["create"]:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

        held = pl.col(value)
        cell = {"sum": held.sum(), "count": held.count(), "min": held.min(), "max": held.max(),
                "first": held.drop_nulls().first(), "last": held.drop_nulls().last()}[function]
        numbered = frame.with_row_index(_PLACE).filter(pl.col(pivot).is_not_null())
        grouped = numbered.group_by(groups + [pivot], maintain_order=True).agg(
            cell.alias(_VALUE), pl.col(_PLACE).min().alias(_PLACE))
        written = {"rows": 0}

        def sink(target: str) -> pl.LazyFrame:
            return grouped.sink_ipc(target, lazy=True)

        def ready(temp: str, rows: int) -> None:
            table = pl.read_ipc(temp, memory_map=False)
            lines = self._lines(table, types)
            written["rows"] = max(len(lines) - 1, 0)
            with open(temp, "wb") as handle:
                handle.write("".join(line + config["rowseparator"] for line in lines).encode(config["encoding"]))

        def place(temp: str, rows: int) -> None:
            # As in v1: no rows in write no file, and neither does `create` off.
            if not rows or not config["create"] or (config["delete_emptyfile"] and not written["rows"]):
                os.remove(temp)
                return
            put_in_place(temp, path)

        def finish(rows: int) -> None:
            self.global_map[f"{self.id}_NB_LINE_OUT"] = written["rows"]

        return Write(path=path, sink=sink, ready=ready, place=place, finish=finish, empty_leaves_none=True)

    def _lines(self, table: pl.DataFrame, types: pl.Schema) -> List[str]:
        """The lines of the file, the header first, from the table of groups and pivot values."""
        config = self.config
        pivot, groups, separator = config["pivot_column"], config["groupbys"], config["fieldseparator"]
        declared = {column.name: column for column in self.input_schema}
        table = table.with_columns(plain_text(pl.col(pivot), types[pivot], declared.get(pivot)).alias(_HEAD))
        # Columns and rows come in the order they first appear among the rows that arrived.
        heads = table.group_by(_HEAD, maintain_order=True).agg(pl.col(_PLACE).min()).sort(_PLACE)[_HEAD].to_list()
        wide = table.pivot(on=_HEAD, index=groups, values=_VALUE, aggregate_function="first", maintain_order=True)
        first = table.group_by(groups, maintain_order=True).agg(pl.col(_PLACE).min())
        wide = wide.join(first, on=groups, how="left", nulls_equal=True, maintain_order="left").sort(_PLACE).drop(_PLACE)
        heads = [head for head in heads if wide[head].null_count() < wide.height]

        columns = [self._group_text(wide[name], declared.get(name)) for name in groups]
        columns += [self._cell_text(wide[head], declared.get(config["aggregation_column"])) for head in heads]
        lines = [separator.join(_field(name, separator) for name in groups + heads)]
        lines += [separator.join(_field(text, separator) for text in row) for row in zip(*columns)] if columns else []
        return lines if wide.height else lines[:1]

    @staticmethod
    def _group_text(values: pl.Series, declared: Optional[Column]) -> List[Optional[str]]:
        return values.to_frame("v").select(to_text(pl.col("v"), values.dtype, declared)).to_series().to_list()

    @staticmethod
    def _cell_text(values: pl.Series, declared: Optional[Column]) -> List[Optional[str]]:
        """A column of cells as text; floats that are all whole as whole numbers, as v1 writes them."""
        dtype = values.dtype
        if dtype.is_float():
            held = values.drop_nulls().drop_nans()
            if held.len() and (held == held.floor()).all():
                return values.cast(pl.Int64, strict=False).cast(pl.String).to_list()
        if dtype.is_temporal():
            # A date by its column's pattern, as in Talend; with none, its day alone when it has no time of day.
            return values.to_frame("v").select(plain_text(pl.col("v"), dtype, declared)).to_series().to_list()
        return values.to_frame("v").select(to_text(pl.col("v"), dtype)).to_series().to_list()
