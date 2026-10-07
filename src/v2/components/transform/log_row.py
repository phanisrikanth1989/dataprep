"""Log row: print the first rows of a flow and pass every row on."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

import polars as pl

from ...job.keys import Key, Kind
from ...rows import visible
from ...types import to_text
from ..base import Transform
from ..registry import REGISTRY

logger = logging.getLogger(__name__)


def _not_negative(value: int) -> int:
    if value < 0:
        raise ValueError("must not be negative")
    return value


def _widths(value: List[Any]) -> List[int]:
    for item in value:
        number = isinstance(item, (int, float)) and not isinstance(item, bool)
        if not number or item < 0 or (isinstance(item, float) and not item.is_integer()):
            raise ValueError(f"{item!r} is not a column width")
    return [int(item) for item in value]


@REGISTRY.register
class LogRow(Transform):
    """Print the first rows of a flow through the logger and pass every row on.

    A row is printed on one line unless ``table_print`` or ``vertical`` asks
    for another layout. Only the rows to print are computed and held; a flow
    with no rows prints nothing.
    """

    names = ("log_row", "LogRow", "tLogRow")
    keys = (
        Key("max_rows", type=int, default=100, convert=_not_negative,
            doc="The most rows printed. Every row is passed on, whatever this says."),
        Key("table_print", type=bool, default=False, doc="Whether the rows are printed as a bordered table."),
        Key("vertical", type=bool, default=False,
            doc="Whether each row is printed as a block of `column: value` lines. Wins over `table_print`."),
        Key("delimiter", default="|", aliases=("fieldseparator",),
            doc="What separates the values of a row printed on one line, used as written."),
        Key("print_header", type=bool, default=False,
            doc="Whether the column names are printed first, when rows are printed one per line."),
        Key("print_colnames", type=bool, default=False,
            doc="Whether each value is printed as `column=value`, when rows are printed one per line."),
        Key("print_unique_name", type=bool, default=False,
            doc="Whether `[id]` starts each line, or stands above the table."),
        Key("use_fixed_length", type=bool, default=False,
            doc="Whether values are cut and padded to `lengths`. A table is only padded."),
        Key("lengths", type=list, default=[], convert=_widths,
            doc="Column widths, by position, for `use_fixed_length`. Columns beyond the list are left alone."),
        Key("print_label", type=bool, default=False,
            doc="Whether a vertical block is titled with `label` instead of `[id]`."),
        Key("print_unique_label", type=bool, default=False,
            doc="Whether a vertical block is titled `[id] label`. Wins over `print_label`."),
        Key("label", default="", doc="The label the vertical titles use."),
        Key("basic_mode", kind=Kind.IGNORED, type=object,
            doc="One line per row is what v1 prints whenever neither `table_print` nor `vertical` is set."),
        Key("print_unique", kind=Kind.IGNORED, type=object,
            doc="`[id]` is the vertical title whenever neither label key is set."),
        Key("print_content_with_log4j", kind=Kind.IGNORED, type=object,
            doc="Rows are printed through the logger whatever this says, as in v1."),
    )

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        (frame,) = inputs.values()
        types = frame.collect_schema()
        # One row is asked for even when none is to be printed: a header line is printed only for a flow with rows.
        shown = frame.head(max(self.config["max_rows"], 1))
        self.tap(shown.select([_printed(name, types[name]) for name in visible(types)]), self._print)
        return {"main": frame}

    # ------------------------------------------------------------------
    # Printing
    # ------------------------------------------------------------------

    def _print(self, rows: pl.DataFrame) -> None:
        if rows.height == 0:
            return
        names = rows.columns
        cells = [[_cell(value) for value in row] for row in rows.head(self.config["max_rows"]).iter_rows()]
        if self.config["vertical"]:
            lines = self._vertical(names, cells)
        elif self.config["table_print"]:
            lines = self._table(names, cells)
        else:
            lines = self._one_per_line(names, cells)
        for line in lines:
            logger.info(line)

    def _one_per_line(self, names: List[str], cells: List[List[str]]) -> List[str]:
        config = self.config
        prefix = f"[{self.id}] " if config["print_unique_name"] else ""
        separator = config["delimiter"]
        lines = [prefix + separator.join(names)] if config["print_header"] else []
        for row in cells:
            values = self._fitted(row)
            if config["print_colnames"]:
                values = [f"{name}={value}" for name, value in zip(names, values)]
            lines.append(prefix + separator.join(values))
        return lines

    def _table(self, names: List[str], cells: List[List[str]]) -> List[str]:
        if not cells:
            return []
        config = self.config
        declared = config["lengths"] if config["use_fixed_length"] else []
        widths = []
        for index, name in enumerate(names):
            if declared:
                widths.append(declared[index] if index < len(declared) else max(len(name), 1))
            else:
                widths.append(max([len(name), 1] + [len(row[index]) for row in cells]))

        def line(values: List[str]) -> str:
            return "|" + "|".join(value.ljust(width) for value, width in zip(values, widths)) + "|"

        border = "+" + "+".join("-" * width for width in widths) + "+"
        title = [f"[{self.id}]"] if config["print_unique_name"] else []
        return title + [border, line(names), border] + [line(row) for row in cells] + [border]

    def _vertical(self, names: List[str], cells: List[List[str]]) -> List[str]:
        config = self.config
        label, own = config["label"], f"[{self.id}]"
        if config["print_unique_label"]:
            title = f"{own} {label}".strip() if label else own
        elif config["print_label"]:
            title = label or own
        else:
            title = own
        lines = []
        for number, row in enumerate(cells, start=1):
            lines.append(f"--- {title} row {number} ---")
            lines += [f"  {name}: {value}" for name, value in zip(names, self._fitted(row))]
        return lines

    def _fitted(self, row: List[str]) -> List[str]:
        """Cut and pad each value to its width, where widths are asked for and one is given."""
        if not self.config["use_fixed_length"]:
            return row
        widths = self.config["lengths"]
        return [value[:width].ljust(width) for value, width in zip(row, widths)] + row[len(widths):]


def _printed(name: str, dtype: pl.DataType) -> pl.Expr:
    """A column as the text v1 prints for its values.

    A column of a kind no v2 schema declares (a duration, a list, a date
    with a time zone...) is left as it is and printed with Python's ``str``.
    """
    column = pl.col(name)
    if isinstance(dtype, pl.Datetime):
        declarable = dtype.time_zone is None
    else:
        declarable = dtype in (pl.String, pl.Boolean, pl.Date) or dtype.is_numeric()
    if not declarable:
        return column
    return to_text(column, dtype)


def _cell(value: Any) -> str:
    """What is printed for one value; nothing for a missing one."""
    if value is None:
        return ""
    return value if isinstance(value, str) else str(value)
