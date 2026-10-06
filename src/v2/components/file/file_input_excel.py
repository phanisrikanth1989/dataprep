"""Excel file input: read the sheets of a workbook as rows.

A workbook cannot be read lazily, so the sheets are read when the component
runs. v1 turns a cell into its column's declared type by what the cell
itself is: a number, text, a date, a boolean. fastexcel reads a whole column
as one type, so each sheet is read under several views (every cell as text,
as a number, as a date) and the views of a cell together say what it is.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from ...errors import ConfigurationError
from ...job.keys import Key, Kind
from ...job.model import Column
from ...types import from_text, polars_type, to_text
from ..base import Source
from ..registry import REGISTRY

logger = logging.getLogger(__name__)

# The views a sheet is read under, by the type fastexcel is asked for, and
# what each one holds:
#   text    every cell that is not empty, as text
#   number  number cells, text that is a number, and boolean cells (1.0 / 0.0)
#   strict  number and boolean cells only: text is never taken for a number
#   moment  date and time cells; number cells too, taken as a count of days
_TEXT, _NUMBER, _STRICT, _MOMENT = "string", "float", "boolean", "datetime"
_VIEW_TYPES = {_TEXT: pl.String, _NUMBER: pl.Float64, _STRICT: pl.Boolean, _MOMENT: pl.Datetime("ms")}
_VIEWS_NEEDED = {
    "str": (_TEXT, _NUMBER, _STRICT, _MOMENT),
    "int": (_TEXT, _NUMBER),
    "float": (_TEXT, _NUMBER),
    "bool": (_TEXT,),
    "datetime": (_TEXT, _NUMBER, _MOMENT),
    "date": (_TEXT, _NUMBER, _MOMENT),
    "Decimal": (_TEXT, _NUMBER, _STRICT),
}
_ROW = "__row"
_TRUE = ("true", "1", "yes", "on")
# A cell that holds a time of day and no date is read as a moment of the day before this one.
_FIRST_DAY = pl.datetime(1900, 1, 1)

_SHEET = (
    Key("sheetname", default="", doc="The sheet's name, or a regular expression when `use_regex` is on."),
    Key("use_regex", type=bool, default=False,
        doc="Whether `sheetname` is a regular expression, looked for anywhere in a sheet's name."),
)


def _sheet_entry(item: Any) -> Any:
    return {"sheetname": item} if isinstance(item, str) else item


def _count(value: Any) -> int:
    """A count written as a number or as text; v1 also takes true for 1."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    raise ValueError(f"{value!r} is not a whole number, zero or more")


def _first_column(value: Any) -> int:
    return max(_count(value), 1)


def _last_column(value: Any) -> Optional[int]:
    """A column given by its number or its letters, counted from 1; None when there is none."""
    text = str(value).strip()
    if not text:
        return None
    if isinstance(value, bool) or not re.fullmatch(r"\d+|[A-Za-z]+", text):
        raise ValueError(f"{value!r} is neither a column number nor column letters")
    if text.isdigit():
        return int(text) or None
    number = 0
    for letter in text.upper():
        number = number * 26 + ord(letter) - ord("A") + 1
    return number


def _limit(value: Any) -> Optional[int]:
    """v1's reading of a limit: nothing or the number 0 for every row, the text "0" for none."""
    if not value:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return _count(value)


@REGISTRY.register
class FileInputExcel(Source):
    """Read one or more sheets of an .xlsx or .xls workbook.

    Columns are taken by position, from ``first_column`` on, one per declared
    column; a declared column the sheet or the range does not reach is
    missing. A cell that cannot be read as its column's type is missing, as
    in v1: an Excel input never rejects a row for what a cell holds. Rows
    leave by the reject output only for a missing value where the schema
    allows none.
    """

    names = ("file_input_excel", "FileInputExcel", "tFileInputExcel")
    outputs = {"main": ("flow", "main"), "reject": ("reject",)}
    keys = (
        Key("path", required=True, aliases=("filepath",),
            doc="The workbook to read. Quotes and blanks around it are dropped."),
        Key("all_sheets", type=bool, default=False,
            doc="Whether every sheet is read, or every sheet `sheetlist` matches when it is given."),
        Key("sheetlist", type=list, default=[], items=_SHEET, item_convert=_sheet_entry,
            doc="Sheets to read. Without `all_sheets` only the first entry counts, and the first sheet is read "
                "when it names none; with it, a name may also be a part of a sheet's name, whatever the case."),
        Key("header", type=object, default=0, convert=_count, doc="Rows to skip at the top of each sheet."),
        Key("footer", type=object, default=0, convert=_count, doc="Rows to skip at the end of each sheet."),
        Key("limit", type=object, default=None, convert=_limit,
            doc="The most rows to read from each sheet. Empty, or the number 0, reads them all; "
                "the text 0 reads none, as in v1."),
        Key("first_column", type=object, default=1, convert=_first_column,
            doc="The sheet column the first declared column is read from, counted from 1."),
        Key("last_column", type=object, default=None, convert=_last_column,
            doc="The last sheet column to read, as a number or as letters; empty for no bound."),
        Key("die_on_error", type=bool, default=False,
            doc="Whether a workbook that cannot be read, no sheet to read, or a missing value where the schema "
                "allows none fails the job. When off, the first two read as no rows and the third is rejected."),
        Key("stopread_on_emptyrow", kind=Kind.IGNORED, type=object, doc="Never acted on by v1: empty rows are rows."),
        Key("trimall", kind=Kind.IGNORED, type=object, doc="Never acted on by v1: text is read as it is."),
        Key("trim_select", kind=Kind.IGNORED, type=object, doc="Never acted on by v1."),
        Key("advanced_separator", kind=Kind.IGNORED, type=object, doc="Never acted on by v1."),
        Key("thousands_separator", kind=Kind.IGNORED, type=object, doc="Never acted on by v1."),
        Key("decimal_separator", kind=Kind.IGNORED, type=object, doc="Never acted on by v1."),
        Key("convertdatetostring", kind=Kind.IGNORED, type=object,
            doc="Never acted on by v1: a date cell in a text column is always written day-month-year."),
        Key("date_select", kind=Kind.IGNORED, type=object, doc="Never acted on by v1."),
        Key("password", kind=Kind.IGNORED, type=object,
            doc="Ignored by v1 as well: the workbook is opened without it."),
        Key("version_2007", kind=Kind.IGNORED, type=object, doc="The file itself says which format it is."),
        Key("affect_each_sheet", kind=Kind.IGNORED, type=object,
            doc="Ignored by v1 as well: header, footer and limit always apply sheet by sheet."),
        Key("suppress_warn", kind=Kind.IGNORED, type=object, doc="Logging only."),
        Key("novalidate_on_cell", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well."),
        Key("encoding", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well: a workbook says its own."),
        Key("read_real_value", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well."),
        Key("generation_mode", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well."),
        Key("include_phoneticruns", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well."),
        Key("configure_inflation_ratio", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well."),
        Key("inflation_ratio", kind=Kind.IGNORED, type=object, doc="Ignored by v1 as well."),
    )

    def problems(self) -> List[str]:
        config, found = self.config, []
        if not self.schema:
            found.append("schema: an Excel file input needs its columns declared")
        if config["last_column"] is not None and config["last_column"] < config["first_column"]:
            found.append("last_column: comes before first_column")
        for entry in config["sheetlist"] if config["all_sheets"] else config["sheetlist"][:1]:
            if entry["use_regex"] and _pattern(entry["sheetname"]) is None:
                found.append(f"sheetlist: '{entry['sheetname']}' is not a regular expression")
        return found

    def declared_outputs(self) -> Dict[str, pl.LazyFrame]:
        outputs = super().declared_outputs()
        if "main" in outputs:
            outputs["reject"] = _no_rejects(outputs["main"])
        return outputs

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def read(self) -> Dict[str, pl.LazyFrame]:
        path = self.config["path"].strip()
        if len(path) > 1 and path[0] == path[-1] and path[0] in "'\"":
            path = path[1:-1]
        if not os.path.isfile(path):
            return self._nothing(f"Excel file not found: {path}")
        try:
            # Imported here: a job without Excel input runs on a machine without the library.
            import fastexcel
        except ImportError:
            raise ConfigurationError(
                "reading Excel files needs the fastexcel package (pip install 'dataprep[v2]')"
            ) from None
        try:
            book = fastexcel.read_excel(path)
            sheets = self._sheets(book.sheet_names)
            if not sheets:
                return self._nothing("No sheets found to read")
            frames = [self._rows(book, sheet, legacy=path.lower().endswith(".xls")) for sheet in sheets]
        except fastexcel.FastExcelError as exc:
            return self._nothing(f"Error reading Excel file {path}: {str(exc).splitlines()[0]}")
        self.global_map[f"{self.id}_CURRENT_SHEET"] = sheets[-1]
        rows = pl.concat(frames).lazy()
        return {"main": rows, "reject": _no_rejects(rows)}

    def _nothing(self, why: str) -> Dict[str, pl.LazyFrame]:
        """No rows at all, or a failed component when errors are fatal."""
        if self.config["die_on_error"]:
            raise ConfigurationError(why)
        logger.warning(f"[{self.id}] {why}; no rows are read")
        return self.declared_outputs()

    def _sheets(self, available: List[str]) -> List[str]:
        """The sheets to read, in the order the workbook holds them."""
        entries = self.config["sheetlist"]
        if self.config["all_sheets"]:
            if not entries:
                return available
            chosen = {name for entry in entries for name in _matching(entry, available, loosely=True)}
            return [name for name in available if name in chosen]
        if entries:
            entry = entries[0]
            if entry["use_regex"] and entry["sheetname"]:
                return _matching(entry, available)[:1]
            if entry["sheetname"] in available:
                return [entry["sheetname"]]
            logger.warning(f"[{self.id}] there is no sheet '{entry['sheetname']}'; the first sheet is read, as in v1")
        return available[:1]

    def _rows(self, book: "fastexcel.ExcelReader", sheet: str, legacy: bool) -> pl.DataFrame:
        """The rows of one sheet as the declared columns.

        Args:
            book: The open workbook.
            sheet: The name of the sheet.
            legacy: Whether the workbook is an .xls one.
        """
        header, limit = self.config["header"], self.config["limit"]
        # Under a limit pandas, which reads a sheet for v1, looks at the rows down to the limit only (and at
        # one more when no header is skipped) and, in an .xlsx sheet, takes the empty rows they end on for none.
        to_last_filled = limit is not None and not legacy
        cells, height = self._cells(book, sheet, None if limit is None else limit + max(header, 1), to_last_filled)
        end = height - self.config["footer"]
        if limit is not None:
            end = min(end, header + limit)
        if to_last_filled:
            end = min(end, _rows_filled(cells))
        return cells.slice(header, max(end - header, 0)).select([
            _as_declared(column, *[pl.col(_view_column(view, index)) for view in _VIEW_TYPES]).alias(column.name)
            for index, column in enumerate(self.schema)
        ])

    def _cells(
        self, book: "fastexcel.ExcelReader", sheet: str, rows: Optional[int], whole_width: bool
    ) -> Tuple[pl.DataFrame, int]:
        """The cells of one sheet under every view, and how many rows the sheet has.

        Each declared column has one column per view, named by ``_view_column``.
        A column the sheet does not reach, and a view the column's type has no
        use for, is a column of missing values.

        Args:
            book: The open workbook.
            sheet: The name of the sheet.
            rows: How many rows to read from the top; None for all of them.
            whole_width: Whether the text view takes in every column of the
                sheet, so that a row can be told to be empty.
        """
        cells, height = pl.DataFrame(), 0
        for view, columns in self._columns_by_view().items():
            everything = whole_width and view == _TEXT
            loaded = book.load_sheet(
                sheet, header_row=None, skip_rows=0, n_rows=rows, dtypes=view,
                use_columns=None if everything else (lambda column, columns=columns: column.absolute_index in columns),
            )
            if view == _TEXT:
                height = loaded.total_height
                cells = pl.select(pl.int_range(loaded.height).alias(_ROW))
            if loaded.selected_columns:
                read = loaded.to_polars()
                read.columns = [
                    columns.get(column.absolute_index, f"{_TEXT}:+{column.absolute_index}")
                    for column in loaded.selected_columns
                ]
                cells = cells.hstack(read)
        absent = [
            pl.lit(None, dtype=dtype).alias(_view_column(view, index))
            for index in range(len(self.schema)) for view, dtype in _VIEW_TYPES.items()
            if _view_column(view, index) not in cells.columns
        ]
        return cells.with_columns(absent), height

    def _columns_by_view(self) -> Dict[str, Dict[int, str]]:
        """Per view, the sheet columns to read (counted from 0) and what each is called once read.

        The text view comes first and is always there: it also says how
        many rows the sheet has.
        """
        first, last = self.config["first_column"] - 1, self.config["last_column"]
        wanted: Dict[str, Dict[int, str]] = {_TEXT: {}}
        for index, column in enumerate(self.schema):
            if last is not None and first + index >= last:
                break
            for view in _VIEWS_NEEDED[column.type]:
                wanted.setdefault(view, {})[first + index] = _view_column(view, index)
        return wanted


# ------------------------------------------------------------------
# A cell as its column's declared type
# ------------------------------------------------------------------

def _as_declared(column: Column, text: pl.Expr, number: pl.Expr, strict: pl.Expr, moment: pl.Expr) -> pl.Expr:
    """What v1's converter of the column's type makes of each cell.

    Args:
        column: The declared column.
        text: The column under the text view.
        number: Under the number view.
        strict: Under the strict view.
        moment: Under the moment view. A view the type has no use for holds
            missing values and is not looked at.
    """
    # A boolean cell is the only one read as the text true or false and as a number too.
    boolean = number.is_not_null() & text.is_in(("true", "false")).fill_null(False)
    if column.type == "bool":
        said = pl.when(text.is_not_null() & (text != "")).then(text.str.strip_chars().str.to_lowercase().is_in(_TRUE))
        return said.fill_null(False) if column.nullable else said
    if column.type in ("int", "float"):
        value = pl.when(~boolean).then(pl.coalesce(number, text.str.strip_chars().cast(pl.Float64, strict=False)))
        if column.type == "float":
            return value.fill_nan(None)
        return pl.when(value.is_finite()).then(value).cast(pl.Int64, strict=False)

    # A date or time cell is the only one read as a moment and not as a number.
    dated = moment.is_not_null() & number.is_null()
    time_only = dated & (moment < _FIRST_DAY)
    if column.type in ("datetime", "date"):
        written = pl.when(text == text.str.strip_chars()).then(from_text(text.fill_null(""), column)[0])
        return pl.when(dated).then(pl.when(~time_only).then(moment.cast(polars_type(column)))).otherwise(written)

    # A number cell that is not whole is read as text by its shortest exact digits, as Python writes a float.
    fraction = strict.is_not_null() & ~boolean & (number != number.floor())
    if column.type == "Decimal":
        return from_text(pl.when(fraction).then(number.cast(pl.String)).otherwise(text).fill_null(""), column)[0]
    return (
        pl.when(boolean).then(pl.when(text == "true").then(pl.lit("1")).otherwise(pl.lit("0")))
        .when(time_only).then(_time_of_day(moment))
        .when(dated).then(moment.dt.strftime("%d-%m-%Y"))
        .when(fraction).then(to_text(number, pl.Float64))
        .otherwise(text)
        .fill_null("")
    )


def _time_of_day(moment: pl.Expr) -> pl.Expr:
    whole = moment.dt.strftime("%H:%M:%S")
    return pl.when(moment.dt.microsecond() == 0).then(whole).otherwise(moment.dt.strftime("%H:%M:%S%.6f"))


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _view_column(view: str, index: int) -> str:
    return f"{view}:{index}"


def _rows_filled(cells: pl.DataFrame) -> int:
    """How many rows there are down to the last one that holds anything, going by the text view."""
    filled = [pl.col(name).fill_null("") != "" for name in cells.columns if name.startswith(_TEXT)]
    last = cells.select(pl.any_horizontal(filled).arg_true().max()).item() if filled else None
    return 0 if last is None else last + 1


def _pattern(text: str) -> Optional["re.Pattern[str]"]:
    try:
        return re.compile(text)
    except re.error:
        return None


def _matching(entry: Dict[str, Any], available: List[str], loosely: bool = False) -> List[str]:
    """The sheets one ``sheetlist`` entry names.

    Args:
        entry: The entry.
        available: The workbook's sheet names.
        loosely: Whether a name that is no sheet's name may be part of one,
            whatever the case.
    """
    name = entry["sheetname"]
    if not name:
        return []
    if entry["use_regex"]:
        pattern = _pattern(name)
        return [sheet for sheet in available if pattern is not None and pattern.search(sheet)]
    if name in available:
        return [name]
    return [sheet for sheet in available if loosely and name.lower() in sheet.lower()]


def _no_rejects(main: pl.LazyFrame) -> pl.LazyFrame:
    """The reject output of rows read without trouble: the columns of main and v1's two, no rows."""
    return main.clear().with_columns(
        pl.lit(None, dtype=pl.String).alias("errorCode"), pl.lit(None, dtype=pl.String).alias("errorMessage")
    )
