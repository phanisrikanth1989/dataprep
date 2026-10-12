"""Oracle stored procedure: a procedure or a function called once, or once for each row of a flow."""
from __future__ import annotations

import decimal
import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import polars as pl

from ... import oracle
from ...column_types import DEFAULT_DECIMAL_SCALE, polars_schema, polars_type
from ...errors import DatabaseError
from ...job.keys import Key, Kind
from ...rows import HIDDEN, visible
from ...sessions import CallFailed
from ..base import Action, Transform, is_on, one_line
from ..registry import REGISTRY

if TYPE_CHECKING:
    from ...job.model import Column

logger = logging.getLogger(__name__)

IN, OUT, INOUT = "IN", "OUT", "INOUT"
# A procedure's name: one name, or names with dots between (a package, a schema).
_NAME = re.compile(r"[A-Za-z][\w$#]*(?:\.[A-Za-z][\w$#]*)*")
_LANGUAGE = re.compile(r"[A-Za-z][A-Za-z_ ]*")
# What a value comes out as, by the type Talend names for it; AUTOMAPPING goes by the declared column.
_KINDS = {"DECIMAL": "number", "NUMERIC": "number", "DATE": "date", "TIMESTAMP": "datetime", "CLOB": "large text"}
_BY_COLUMN = {"str": "text", "int": "number", "float": "number", "Decimal": "number", "bool": "number",
              "datetime": "datetime", "date": "date"}
_NOT_READ = ("BLOB", "XMLTYPE", "TIMESTAMP_WITH_TIMEZONE")
# Calls a round trip.
_BATCH = 10_000

_ARGUMENT = (
    Key("column", required=True, doc="The column the value comes from, or goes to."),
    Key("type", default=IN, doc="`IN`, `OUT` or `INOUT`."),
    Key("dbtype", default="AUTOMAPPING",
        doc="What a value that comes out is: `AUTOMAPPING` (as its column is declared), `DECIMAL`, `NUMERIC`, `DATE`, "
            "`TIMESTAMP` or `CLOB`."),
    Key("is_custom", type=object, default=False, doc="Talend's switch for a STRUCT or an ARRAY, which are not read."),
    Key("custom_type", kind=Kind.IGNORED, type=object, doc="See `is_custom`."),
    Key("custom_name", kind=Kind.IGNORED, type=object, doc="See `is_custom`."),
)


@REGISTRY.register
class OracleSP(Action, Transform):
    """Call a procedure or a function of an Oracle database.

    Set off by a trigger, it calls `sp_name` once. With a flow leading to
    it, it calls it once for each row, a batch of calls in one round
    trip. `sp_args` names the procedure's arguments in their order: an
    `IN` takes the value of its column, an `OUT` puts what comes out
    into its column, an `INOUT` does both. With `is_function` what the
    function returns goes into `return_column`. The rows go on with what
    came out in them; with no flow to it, it hands on one row.

    A number comes out with every digit it has. The rows are held in
    memory while the calls are made.

    What the procedure changes waits on the session of its connection
    for a commit component, or is stored when its subjob is done where it
    has a session of its own. A procedure that commits by itself stores
    what waited on the session too, and a warning then says so.

    A call that fails fails the job and names the row.
    """

    names = ("oracle_sp", "OracleSP", "tOracleSP")
    uses_session = "Oracle"
    min_inputs = 0
    max_inputs = 1
    outputs = {"main": ("flow", "main")}
    may_need_rows = True
    keys = (
        Key("sp_name", default="", doc="The procedure or function: its name, with its package or schema before a dot."),
        Key("is_function", type=bool, default=False, doc="Whether it is a function, whose value goes to `return_column`."),
        Key("return_column", default="", doc="The column that takes what a function returns."),
        Key("return_bdtype", default="AUTOMAPPING", doc="What a function returns; as `dbtype` of an argument."),
        Key("sp_args", type=list, default=[], items=_ARGUMENT, doc="The arguments, in the procedure's order."),
        Key("nls_language", default="NONE", doc="The language the session is set to before the call; `NONE` leaves it."),
        Key("nls_territory", default="NONE", doc="The territory the session is set to before the call; `NONE` leaves it."),
    ) + oracle.WORKING_KEYS + oracle.CONNECTION_KEYS

    def needs_rows(self) -> bool:
        return bool(self.fed)

    def problems(self) -> List[str]:
        config = self.config
        found = oracle.working_problems(config)
        if not _NAME.fullmatch(config["sp_name"].strip()):
            found.append("sp_name: is no name of a procedure: a name, or names with a dot between")
        names = [column.name for column in self.schema]
        for at, argument in enumerate(config["sp_args"]):
            where = f"sp_args[{at}]"
            if argument["type"] == "RECORDSET":
                found.append(f"{where}.type: a cursor a procedure hands out is not read; read its rows with an input")
            elif argument["type"] not in (IN, OUT, INOUT):
                found.append(f"{where}.type: '{argument['type']}' is none of IN, OUT, INOUT")
            if is_on(argument["is_custom"]):
                found.append(f"{where}.is_custom: a STRUCT or an ARRAY is not handed to a procedure")
            if names and argument["column"] not in names:
                found.append(f"{where}.column: '{argument['column']}' is no column of the schema ({', '.join(names)})")
            found += [f"{where}.dbtype: {said}" for said in _kind_problems(argument["dbtype"], argument["type"] != IN)]
        if config["is_function"]:
            if names and config["return_column"] not in names:
                found.append(f"return_column: '{config['return_column']}' is no column of the schema ({', '.join(names)})")
            found += [f"return_bdtype: {said}" for said in _kind_problems(config["return_bdtype"], True)]
        if not names:
            found.append("schema: a stored procedure needs its columns declared")
        for key in ("nls_language", "nls_territory"):
            if not _LANGUAGE.fullmatch(config[key].strip()):
                found.append(f"{key}: is no name of a language or a territory")
        return found

    def declared_outputs(self) -> Dict[str, pl.LazyFrame]:
        return {"main": pl.LazyFrame(schema=polars_schema(self.schema))}

    # ------------------------------------------------------------------

    def act(self) -> Optional[Dict[str, pl.LazyFrame]]:
        # One call with nothing handed in: a row with nothing in it stands for it.
        nothing = pl.DataFrame({HIDDEN + "made:" + self.id: [True]})
        called = self._called(nothing)
        return {"main": called.lazy()} if "main" in self.wired else None

    def run(self, inputs: Dict[str, pl.DataFrame]) -> Dict[str, pl.DataFrame]:
        (frame,) = inputs.values()
        return {"main": self._called(frame)}

    def _called(self, frame: pl.DataFrame) -> pl.DataFrame:
        """Call the procedure for each row. Returns the rows with what came out in their columns."""
        config, sessions = self.config, self.run_context.sessions
        places, outs, block = self._block()
        have = visible(frame.columns)
        declared = {column.name: column for column in self.schema}
        # What goes in at each place: the row's column, where it has one; nothing where a value only comes out.
        taken = [name if way != OUT and name in have else None for name, way in places]
        handed_in = frame.select([
            (pl.col(name) if name is not None else pl.lit(None)).alias(f"v{at}") for at, name in enumerate(taken)
        ]) if places else None
        session, own = oracle.session_of(self)
        if own:
            sessions.own(session)
        waited = sessions.waiting(session)
        sessions.working(session, self.id)
        for key, setting in (("nls_language", "nls_language"), ("nls_territory", "nls_territory")):
            if config[key].strip().upper() != "NONE":
                session.run(f"alter session set {setting} = '{config[key].strip()}'")
        # A moment that only goes in is said to be one: by itself a driver may take it for a date.
        ins = {at: "datetime" for at, name in enumerate(taken)
               if name is not None and at not in outs and declared[name].type == "datetime"}
        came_out: Dict[int, List[Any]] = {place: [] for place in outs}
        for start in range(0, frame.height, _BATCH):
            rows = [tuple(_plain(value) for value in row) for row in handed_in.slice(start, _BATCH).iter_rows()] \
                if handed_in is not None else [()] * min(_BATCH, frame.height - start)
            try:
                got = session.call(block, rows, outs, ins)
            except CallFailed as fault:
                raise DatabaseError(f"the call failed: {fault}{self.where(frame.slice(start + fault.at, 1))}") from None
            for place in outs:
                came_out[place] += got[place]
        if waited and not session.in_transaction():
            logger.warning(one_line(
                f"[{self.id}] the procedure stored what waited on the session by itself: the work of "
                f"{', '.join(waited)} is stored now, with no commit of the job's"))
        logger.info(one_line(f"[{self.id}] called {config['sp_name'].strip()} {frame.height} time(s): {block}"))
        if not outs:
            return frame
        columns = {place: declared[places[place][0]] for place in outs}
        values = [pl.Series(column.name, [_as_declared(value, column) for value in came_out[place]],
                            dtype=polars_type(column)) for place, column in columns.items()]
        return frame.drop([series.name for series in values if series.name in frame.columns]).hstack(values)

    def _block(self) -> Tuple[List[Tuple[str, str]], Dict[int, str], str]:
        """The places of the call, each as its column and the way its value goes; the places that hand a value
        out, with the kind of value; and the block that makes the call."""
        config = self.config
        declared = {column.name: column for column in self.schema}
        places = [(argument["column"], argument["type"]) for argument in config["sp_args"]]
        kinds = [argument["dbtype"] for argument in config["sp_args"]]
        if config["is_function"]:
            places.insert(0, (config["return_column"], OUT))
            kinds.insert(0, config["return_bdtype"])
        outs = {at: _KINDS.get(kinds[at]) or _BY_COLUMN[declared[name].type]
                for at, (name, way) in enumerate(places) if way != IN}
        first = 2 if config["is_function"] else 1
        values = ", ".join(f":{at}" for at in range(first, len(places) + 1))
        called = f"{config['sp_name'].strip()}({values})" if values else config["sp_name"].strip()
        return places, outs, f"begin {':1 := ' if config['is_function'] else ''}{called}; end;"


def _kind_problems(kind: str, comes_out: bool) -> List[str]:
    if kind in _NOT_READ and comes_out:
        return [f"a {kind} that comes out of a procedure is not read"]
    if kind != "AUTOMAPPING" and kind not in _KINDS and kind not in _NOT_READ:
        return [f"'{kind}' is no type; the types are AUTOMAPPING, {', '.join(_KINDS)}"]
    return []


def _as_declared(value: Any, column: "Column") -> Any:
    """What a procedure handed out, as the kind its column is declared: Oracle hands out a number with every
    digit, whatever the column is to hold. (A date with a time of day is cut to its day by the column itself.)"""
    if value is None:
        return None
    if column.type == "int" and isinstance(value, decimal.Decimal):
        return int(value)
    if column.type == "float" and isinstance(value, decimal.Decimal):
        return float(value)
    if column.type == "bool" and isinstance(value, decimal.Decimal):
        return value != 0
    if column.type == "str" and not isinstance(value, str):
        return str(value)
    if column.type == "Decimal" and isinstance(value, decimal.Decimal):
        places = DEFAULT_DECIMAL_SCALE if column.precision is None else column.precision
        return value.quantize(decimal.Decimal(1).scaleb(-places), rounding=decimal.ROUND_HALF_UP)
    return value


def _plain(value: Any) -> Any:
    """A value as a procedure takes it: a true/false as 1 or 0, since PL/SQL's own true/false is no number."""
    return int(value) if isinstance(value, bool) else value
