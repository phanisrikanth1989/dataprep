"""File output Excel: the rows of a flow written to a sheet of a workbook."""
from __future__ import annotations

import logging
import math
import os
from typing import Any, Dict, List, Optional

import openpyxl
import polars as pl
from openpyxl.utils import get_column_letter

from ...column_types import to_text
from ...errors import ConfigurationError
from ...files import put_in_place
from ...job.keys import Key, Kind
from ...job.model import Column
from ..base import Sink, Write
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# What a sheet's name may not hold, and how long it may be: Excel's own limits.
_NOT_IN_A_NAME = "\\/*?:[]"
_NAME_LENGTH = 31
# The characters no cell of a workbook can hold: the control characters but tab, line feed and carriage return.
_NOT_IN_A_CELL = "[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f]"
_LAST_ROW = 1048576
_LAST_COLUMN = 16384
_UNREAD = (
    "version_2007", "streamname", "first_cell_y_absolute", "keep_cell_formating", "font", "password", "flushonrow",
    "flushonrow_num", "advanced_separator", "thousands_separator", "decimal_separator",
    "truncate_exceeding_characters", "encoding", "streaming_append", "use_shared_strings_table",
)


def _sheet(value: str) -> str:
    """A sheet's name, without the quotes v1 takes off it."""
    if value and value[0] == value[-1] and value[0] in "'\"":
        # As in v1, a lone quote too; what is left of it is no name, and the sheet is openpyxl's `Sheet`.
        value = value[1:-1] or "Sheet"
    for char in _NOT_IN_A_NAME:
        if char in value:
            raise ValueError(f"'{value}' is no name for a sheet: it holds '{char}'")
    if len(value) > _NAME_LENGTH:
        raise ValueError(f"a sheet's name has {_NAME_LENGTH} characters at most, and this has {len(value)}")
    return value


def _offset(what: str, most: int):
    def convert(value: Any) -> int:
        # As in v1: nothing given, or what is no number, is the first.
        try:
            offset = int(value or 0)
        except (TypeError, ValueError):
            return 0
        if offset < 0:
            raise ValueError(f"{offset} is before the first {what}")
        if offset >= most:
            raise ValueError(f"a sheet has {most} {what}s, and {offset} is beyond them")
        return offset
    return convert


def _last_row(sheet: Any) -> int:
    """The last row of a sheet that holds anything, 0 when none does."""
    for at in range(sheet.max_row or 0, 0, -1):
        if any(cell.value is not None for cell in sheet[at]):
            return at
    return 0


@REGISTRY.register
class FileOutputExcel(Sink):
    """Write the rows to a sheet of a workbook (`.xlsx`).

    The columns are written in the order the component's input schema
    declares them (as they arrive when it declares none), from the cell
    `first_cell_x` columns right and `first_cell_y` rows down of A1. With
    `includeheader` the column names come first, in a sheet that holds
    nothing yet. Every row is written, one with nothing in it as an empty
    row, as in Talend.

    With `append_file` a workbook that is there is kept: the rows go under
    the last row of the sheet, or into a new sheet. Without it the workbook
    is replaced.

    A whole number, a float and true/false are cells of that kind; a
    Decimal is a number shown to its declared places, and so is a float
    that declares some. A date whose column declares a pattern is text
    written by it, as in v1; one with no pattern is a date of Excel's.

    The rows are held in memory while the workbook is made, as in v1. The
    workbook is made when the whole subjob has succeeded and the file's
    turn comes to be put in place: an output before it in the same subjob
    may have written the workbook this one adds to. What the rows of a new
    workbook can fail on is found before that, so a subjob that fails
    leaves the file as it was. A workbook that is added to can still fail
    then (it cannot be read, its sheet is a chart or has no room left), and
    files the subjob wrote before it are in place by that time.
    """

    names = ("file_output_excel", "FileOutputExcel", "tFileOutputExcel")
    keys = (
        Key("path", required=True, aliases=("filename",), doc="The workbook to write."),
        Key("sheetname", default="Sheet1", convert=_sheet, doc="The sheet; quotes around the name are no part of it."),
        Key("includeheader", type=bool, default=False, doc="Whether the column names are written first."),
        Key("append_file", type=bool, default=False, doc="Whether a workbook that is there is added to."),
        Key("append_sheet", kind=Kind.IGNORED, type=object,
            doc="With `append_file` the rows go under those of the sheet either way; alone it does nothing, as in v1."),
        Key("create", type=bool, default=True, doc="Whether folders that are missing are made."),
        Key("first_cell_x", type=object, default=0, convert=_offset("column", _LAST_COLUMN),
            doc="How many columns right of A the first column is written."),
        Key("first_cell_y", type=object, default=0, convert=_offset("row", _LAST_ROW),
            doc="How many rows down of 1 the first row is written."),
        Key("is_all_auto_szie", type=bool, default=False, doc="Whether every column is made as wide as its longest value."),
        Key("auto_szie_setting", type=list, default=[], doc="The columns to make so wide, when not every one is."),
        Key("recalculate_formula", type=bool, default=False, doc="Whether Excel is told to work out formulas when it opens the workbook."),
        Key("delete_empty_file", type=bool, default=False, doc="Whether no workbook is left when there is no row to write."),
        Key("die_on_error", kind=Kind.IGNORED, type=object, doc="A workbook that cannot be written always fails the job."),
        Key("protect_file", kind=Kind.REFUSED, type=object,
            reason="v2 does not protect a workbook with a password (v1 leaves it unprotected without a word)"),
        Key("usestream", kind=Kind.REFUSED, type=object, reason="v2 writes to a file, not to a stream"),
    ) + tuple(Key(name, kind=Kind.IGNORED, type=object, doc="Never read by v1.") for name in _UNREAD)

    def problems(self) -> List[str]:
        return [] if self.config["path"] else ["path: the workbook to write has no name"]

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def write(self, frame: pl.LazyFrame) -> Write:
        config = self.config
        path = config["path"]
        folder = os.path.dirname(path)
        if folder and config["create"]:
            os.makedirs(folder, exist_ok=True)
        if folder and not os.path.isdir(folder):
            raise ConfigurationError(f"Failed to write file '{path}': folder '{folder}' does not exist")

        types = frame.collect_schema()
        declared = {column.name: column for column in self.input_schema}
        names = list(declared) or types.names()
        if config["first_cell_x"] + len(names) > _LAST_COLUMN:
            raise ConfigurationError(
                f"a sheet has {_LAST_COLUMN} columns, and the {len(names)} to write from column "
                f"{config['first_cell_x'] + 1} do not fit"
            )
        cells = frame.select([self._cell(name, types.get(name), declared.get(name)) for name in names])
        text = [name for name in names if types.get(name) == pl.String]

        def sink(target: str) -> pl.LazyFrame:
            return cells.sink_ipc(target, lazy=True)

        def ready(written: str, rows: int) -> None:
            # What the rows can fail on is found here, before any file of the subjob is put in place.
            if rows + config["first_cell_y"] + config["includeheader"] > _LAST_ROW:
                raise ConfigurationError(f"a sheet holds {_LAST_ROW} rows at most, and there are {rows} to write")
            if not text:
                return
            table = pl.read_ipc(written, memory_map=False, columns=text).with_row_index("__row", offset=1)
            for name in text:
                bad = table.filter(pl.col(name).str.contains(_NOT_IN_A_CELL)).head(1)
                if bad.height:
                    raise ConfigurationError(
                        f"column '{name}' of row {bad['__row'].item()} holds a character a workbook cannot hold: "
                        f"{bad[name].item()!r}"
                    )

        def place(written: str, rows: int) -> None:
            if not rows and config["delete_empty_file"]:
                os.remove(written)
                # As in Talend: a workbook nothing was added to is kept; one this run would have replaced is not.
                if not config["append_file"] and os.path.exists(path):
                    os.remove(path)
                return
            table = pl.read_ipc(written, memory_map=False)
            self._workbook(table, names, declared).save(written)
            put_in_place(written, path)

        def as_text(rows: pl.DataFrame) -> pl.DataFrame:
            kinds = rows.schema
            return rows.select([
                self._cell(name, kinds[name], declared.get(name)).cast(pl.String).alias(name) for name in rows.columns
            ])

        return Write(path=path, sink=sink, ready=ready, place=place, empty_leaves_none=config["delete_empty_file"],
                     as_text=as_text)

    @staticmethod
    def _cell(name: str, dtype: Optional[pl.DataType], declared: Optional[Column]) -> pl.Expr:
        """A column as its cells hold it."""
        column = pl.col(name)
        if dtype is None:
            # Declared and not among the columns that arrive: empty cells, as in v1. Nothing, once for every
            # row: a plain literal would make one row of however many arrive.
            return pl.repeat(None, pl.len(), dtype=pl.String).alias(name)
        if dtype.is_temporal() and dtype != pl.Time:
            if declared is not None and declared.type in ("date", "datetime") and declared.date_pattern:
                return to_text(column, dtype, declared).alias(name)
            if dtype == pl.Date:
                # A day alone is text, as v1 holds it.
                return column.dt.strftime("%Y-%m-%d").alias(name)
            return column.alias(name)
        if dtype.is_decimal():
            # Through the digits: the float nearest to the Decimal.
            return column.cast(pl.String).cast(pl.Float64).alias(name)
        return column

    def _workbook(self, table: pl.DataFrame, names: List[str], declared: Dict[str, Column]) -> Any:
        """The workbook to leave at the path: the one that is there with the rows added, or a new one."""
        config = self.config
        path, title = config["path"], config["sheetname"]
        if config["append_file"] and os.path.exists(path):
            try:
                workbook = openpyxl.load_workbook(path)
            except Exception as exc:  # noqa: BLE001 -- openpyxl and zipfile raise what they like
                raise ConfigurationError(f"'{path}' is there and is no workbook that can be read: {exc}") from exc
        else:
            workbook = openpyxl.Workbook()
            if title != "Sheet":
                workbook.remove(workbook["Sheet"])
        sheet = workbook[title] if title in workbook.sheetnames else workbook.create_sheet(title)

        last = _last_row(sheet)
        if last + table.height > _LAST_ROW:
            raise ConfigurationError(
                f"sheet '{title}' of '{path}' holds {last} rows, and a sheet has room for {_LAST_ROW}: "
                f"the {table.height} to add do not fit"
            )
        first_column, row = config["first_cell_x"] + 1, config["first_cell_y"] + 1
        if last:
            # A workbook that is added to: under what the sheet holds, or at the first cell when that is lower.
            row = max(row, last + 1)
        if config["includeheader"] and names and not last:
            for at, name in enumerate(names):
                sheet.cell(row=row, column=first_column + at).value = name
            row += 1

        formats = {at: "0." + "0" * column.precision if column.precision else "0"
                   for at, column in enumerate(declared.get(name) for name in names)
                   if column is not None and column.type in ("Decimal", "float") and column.precision is not None}
        widest = [0] * len(names)
        for values in table.iter_rows():
            for at, value in enumerate(values):
                if isinstance(value, float) and not math.isfinite(value):
                    # No number: a workbook has no cell for it.
                    value = None
                cell = sheet.cell(row=row, column=first_column + at)
                cell.value = value
                if at in formats:
                    cell.number_format = formats[at]
                widest[at] = max(widest[at], self._width(value, declared.get(names[at])))
            row += 1

        sized = names if config["is_all_auto_szie"] else [str(name) for name in config["auto_szie_setting"]]
        for at, name in enumerate(names):
            if name in sized:
                titled = len(name) if config["includeheader"] and config["is_all_auto_szie"] else 0
                sheet.column_dimensions[get_column_letter(first_column + at)].width = max(widest[at], titled) + 2
        if config["recalculate_formula"]:
            workbook.calculation.calcMode = "auto"
        return workbook

    @staticmethod
    def _width(value: Any, declared: Optional[Column]) -> int:
        """How many characters a value takes, as v1 counts them: nothing for what is missing, zero or false."""
        if not value:
            return 0
        places = declared.precision if declared is not None and declared.type == "Decimal" else None
        if isinstance(value, float) and places is not None:
            return len(f"{value:.{places}f}")
        return len(str(value))
