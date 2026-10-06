"""Python dataframe: run the user's Python once over a whole flow.

The code is handed the flow as ``df`` and leaves its result in ``df``. By
default ``df`` is a pandas frame, as in v1, which takes every row into
memory. Asked for Polars, the code is handed a lazy frame and only adds to
the plan, so the component stays lazy.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional

import polars as pl

from ...errors import ConfigurationError
from ...job.keys import CODE, Key
from ...job.model import Column
from ...types import polars_schema
from ..base import Transform
from ..registry import REGISTRY

if TYPE_CHECKING:
    import pandas as pd

logger = logging.getLogger(__name__)

# The file name the user's code is compiled under; it finds the code's own lines in a traceback.
_SOURCE = "<python_code>"
_DECIMAL_DIGITS = 38


def _not_empty(value: str) -> str:
    if not value:
        raise ValueError("must not be empty")
    return value


def _column_names(value: List[Any]) -> List[str]:
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{item!r} is not a column name")
        if value.count(item) > 1:
            raise ValueError(f"{item!r} is listed more than once")
    return value


@REGISTRY.register
class PythonDataFrame(Transform):
    """Run the user's Python once over the whole flow, never row by row.

    The code may use ``df``, ``context`` (a copy: changing it changes
    nothing outside the code), ``globalMap`` (``get``, ``put``, ``contains``,
    ``remove``, ``get_all``), ``routines`` and each routine by its name.

    With ``dataframe: pandas`` it may also use ``pd`` and ``np``; ``df`` is
    the pandas frame v1 hands over and must still be one when the code ends.
    The code is not run on a flow with no rows.

    With ``dataframe: polars`` it may use ``pl``; ``df`` is a lazy frame and
    must be left a lazy frame or a DataFrame. The code then runs when the
    job is checked at load as well, on an empty frame: it builds a plan and
    must not depend on the rows.
    """

    names = ("python_dataframe", "PythonDataFrameComponent", "tPythonDataFrame")
    may_need_rows = True
    keys = (
        Key("python_code", type=CODE, required=True, convert=_not_empty,
            doc="The Python to run. It is handed the flow as `df` and leaves its result in `df`."),
        Key("dataframe", default="pandas", choices=("pandas", "polars"),
            doc="What `df` is: a pandas frame, as in v1, or a Polars lazy frame, which keeps the component lazy."),
        Key("output_columns", type=list, default=[], convert=_column_names,
            doc="The columns of the result to keep, in this order. Names the result lacks are skipped; "
                "when it has none of them, every column is kept."),
        Key("die_on_error", type=bool, default=True,
            doc="Whether a missing value in a column declared not nullable fails the component instead of "
                "dropping the row. Code that raises always fails it."),
    )

    def needs_rows(self) -> bool:
        return self.config["dataframe"] == "pandas"

    def problems(self) -> List[str]:
        try:
            compile(self.config["python_code"], _SOURCE, "exec")
        except SyntaxError as exc:
            return [f"python_code: line {exc.lineno}: {exc.msg}"]
        return []

    # ------------------------------------------------------------------
    # The two ways to run
    # ------------------------------------------------------------------

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        (frame,) = inputs.values()
        result = self._execute({"df": frame, "pl": pl})
        if isinstance(result, pl.DataFrame):
            result = result.lazy()
        if not isinstance(result, pl.LazyFrame):
            raise ConfigurationError(f"python_code must leave a Polars frame in 'df', found {_kind(result)}")
        columns = result.collect_schema().names()
        if not columns:
            return {"main": self._no_rows().lazy()}
        kept = self._kept(columns)
        return {"main": result.select(kept) if kept else result}

    def run(self, inputs: Dict[str, pl.DataFrame]) -> Dict[str, pl.DataFrame]:
        import numpy as np
        import pandas as pd

        (frame,) = inputs.values()
        if frame.height == 0:
            logger.info(f"[{self.id}] no rows: python_code was not run")
            return {"main": self._no_rows()}
        declared = {column.name: column for column in self.input_schema}
        result = self._execute({"df": _to_pandas(frame, declared), "pd": pd, "np": np})
        if not isinstance(result, pd.DataFrame):
            raise ConfigurationError(f"python_code must leave a pandas DataFrame in 'df', found {_kind(result)}")
        if not len(result.columns):
            return {"main": self._no_rows()}
        kept = self._kept(list(result.columns))
        return {"main": _from_pandas(result[kept] if kept else result, frame.schema)}

    def _no_rows(self) -> pl.DataFrame:
        """The declared columns with no rows: what a flow with no rows, or a result with no columns, gives."""
        return pl.DataFrame(schema=polars_schema(self.schema))

    def _execute(self, handed: Dict[str, Any]) -> Any:
        """Run the code with ``handed`` beside the names every run gets; returns what it left in ``df``."""
        routines = _Names({name: _Names(functions) for name, functions in self.run_context.routines.items()})
        names = {
            **routines,
            "context": dict(self.context),
            "globalMap": _GlobalMap(self.global_map),
            "routines": routines,
            **handed,
        }
        code = compile(self.config["python_code"], _SOURCE, "exec")
        try:
            exec(code, names)
        except Exception as exc:  # noqa: BLE001 -- whatever the user's code raises fails the component
            raise ConfigurationError(f"python_code line {_line(exc)}: {type(exc).__name__}: {exc}") from exc
        return names.get("df", _NOTHING)

    def _kept(self, columns: List[Any]) -> List[str]:
        """The listed output columns the result has; none when every column is to be kept."""
        wanted = self.config["output_columns"]
        kept = [name for name in wanted if name in columns]
        if wanted and not kept:
            logger.warning(f"[{self.id}] the result has none of the output_columns; every column is kept")
        return kept


# ------------------------------------------------------------------
# What the code is handed beside the frame
# ------------------------------------------------------------------

class _GlobalMap:
    """The run's globalMap behind the methods v1 gives user code.

    A number pandas or numpy hands out (``df["n"].sum()``) is stored as the
    plain Python value it stands for: trigger conditions and expressions
    read globalMap entries as Python.
    """

    def __init__(self, entries: Dict[str, Any]) -> None:
        self._entries = entries

    def get(self, key: str, default: Any = None) -> Any:
        return self._entries.get(key, default)

    def put(self, key: str, value: Any) -> None:
        if type(value).__module__ == "numpy":
            import numpy as np

            if isinstance(value, np.generic):
                value = value.item()
        self._entries[key] = value

    def contains(self, key: str) -> bool:
        return key in self._entries

    def remove(self, key: str) -> None:
        self._entries.pop(key, None)

    def get_all(self) -> Dict[str, Any]:
        return dict(self._entries)


class _Names(dict):
    """A mapping whose entries can also be read as attributes: ``routines.Tax.vat`` or ``routines["Tax"]``."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"there is no '{name}' here; known: {', '.join(sorted(self)) or 'nothing'}") from None


_NOTHING = object()


def _kind(value: Any) -> str:
    return "nothing" if value is _NOTHING else type(value).__name__


def _line(error: BaseException) -> Optional[int]:
    """The line of the user's code an error came from: the innermost one."""
    line = None
    trace = error.__traceback__
    while trace is not None:
        if trace.tb_frame.f_code.co_filename == _SOURCE:
            line = trace.tb_lineno
        trace = trace.tb_next
    return line


# ------------------------------------------------------------------
# Polars to pandas and back
# ------------------------------------------------------------------

def _to_pandas(frame: pl.DataFrame, declared: Mapping[str, Column]) -> "pd.DataFrame":
    """A frame as v1 hands it to user code.

    Text is pandas text, a date and time is ``datetime64``, a Decimal column
    holds Python Decimals, and a missing value is the one pandas has for the
    column's type. Whole numbers are ``Int64``, which can hold a missing
    value, or plain ``int64`` when the component declares the column not
    nullable, as v1 does by the schema.
    """
    import pandas as pd

    return pd.DataFrame({name: _pandas_column(frame[name], declared.get(name)) for name in frame.columns})


def _pandas_column(column: pl.Series, declared: Optional[Column]) -> "pd.Series":
    import pandas as pd

    dtype = column.dtype
    missing = column.null_count() > 0
    if dtype.is_integer() and (missing or declared is None or declared.nullable):
        values = pd.arrays.IntegerArray(column.fill_null(0).to_numpy(), column.is_null().to_numpy())
        return pd.Series(values, name=column.name)
    if dtype == pl.Boolean and missing:
        values = pd.arrays.BooleanArray(column.fill_null(False).to_numpy(), column.is_null().to_numpy())
        return pd.Series(values, name=column.name)
    if dtype == pl.Date:
        return column.to_pandas(date_as_object=True)
    return column.to_pandas()


def _from_pandas(frame: "pd.DataFrame", before: Mapping[str, pl.DataType]) -> pl.DataFrame:
    """The frame user code left, as a Polars frame. Its index is dropped, as v1's outputs drop it.

    Args:
        frame: What the code left in ``df``.
        before: The columns the code was handed, with their types. A column
            that comes back holding nothing takes its type from here.
    """
    names = [str(name) for name in frame.columns]
    for name in names:
        if names.count(name) > 1:
            raise ConfigurationError(f"python_code left more than one column named '{name}'")
    return pl.DataFrame(
        [_polars_column(name, frame.iloc[:, position], before.get(name)) for position, name in enumerate(names)]
    )


def _polars_column(name: str, values: "pd.Series", before: Optional[pl.DataType]) -> pl.Series:
    """One column the code left, as a Polars column of a kind a v2 flow declares.

    A column of any other kind (durations, periods, categories, lists,
    values of several kinds...) is carried as text, each value as Python
    prints it: that is what v1's outputs write for it.
    """
    import pandas as pd

    def printed(value: Any) -> Optional[str]:
        missing = value is None or value is pd.NA or value is pd.NaT or (isinstance(value, float) and value != value)
        return None if missing else str(value)

    column = None
    # Polars would take a period or an interval for the numbers pandas stores it as.
    if not isinstance(values.dtype, (pd.PeriodDtype, pd.IntervalDtype)):
        try:
            column = pl.from_pandas(values.rename(name), nan_to_null=True)
        except Exception:  # noqa: BLE001 -- Arrow reports values of several kinds in one column in many types
            pass
    if column is None or not _declarable(column.dtype):
        column = pl.Series(name, [printed(value) for value in values], dtype=pl.String)

    if values.dtype == object and column.null_count() == column.len():
        # Nothing in it says what it is: it stays what it was before the code, or is text.
        return column.cast(pl.String if before is None else before)
    if column.dtype.is_decimal():
        return column.cast(pl.Decimal(_DECIMAL_DIGITS, column.dtype.scale))
    return column


def _declarable(dtype: pl.DataType) -> bool:
    """Whether a Polars type is one a v2 schema can declare."""
    if isinstance(dtype, pl.Datetime):
        return dtype.time_zone is None
    return dtype in (pl.String, pl.Boolean, pl.Date) or dtype.is_numeric()
