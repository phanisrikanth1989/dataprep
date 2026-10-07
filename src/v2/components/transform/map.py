"""Map: join lookups to a main input and compute any number of named outputs.

The main rows keep their order through every join. Every output is a filter
and a projection of the one joined frame, so the inputs are read once however
many outputs there are. The joins are in ``map_joins``, the outputs in
``map_outputs``.
"""
from __future__ import annotations

import ast
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from ...errors import ConfigurationError
from ...expressions import Scope
from ...job.keys import EXPRESSION, Key, Kind
from ...job.model import TYPE_NAMES
from ...rows import visible, without
from ..base import Transform, is_on
from ..registry import REGISTRY
from .map_joins import MISSED, joined_with
from .map_outputs import condition, projected, routed, translated, type_of

# Working columns that hold the variables, one per entry of `variables`.
_VARIABLE_COLUMN = "__map_var_"
_MATCHING_MODES = ("UNIQUE_MATCH", "FIRST_MATCH", "LAST_MATCH", "ALL_MATCHES", "ALL_ROWS")


def _not_empty(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be empty")
    return value


def _listed(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _load_once(value: str) -> str:
    if value != "LOAD_ONCE":
        raise ValueError(
            f"{value!r} is not supported: a lookup is loaded once ('LOAD_ONCE'); "
            "loading it again for each main row needs a loop over the rows"
        )
    return value


_EDITOR = (
    Key("size_state", kind=Kind.IGNORED, type=object, doc="Talend editor state."),
    Key("persistent", kind=Kind.IGNORED, type=object, doc="Talend's store-on-disk switch."),
    Key("activate_condensed_tool", kind=Kind.IGNORED, type=object, doc="Talend editor state."),
    Key("activate_global_map", kind=Kind.IGNORED, type=object, doc="Talend editor state."),
)

_MAIN = (
    Key("name", required=True, convert=_not_empty, doc="The flow that brings the main rows."),
    Key("filter", type=EXPRESSION, default="",
        doc="A condition on the main input's own columns; a row that fails it is not mapped at all."),
    Key("activate_filter", type=bool, default=False, doc="Whether `filter` applies."),
    Key("matching_mode", kind=Kind.IGNORED, type=object, doc="Read on lookups only, as in v1."),
    Key("lookup_mode", kind=Kind.IGNORED, type=object, doc="Read on lookups only, as in v1."),
) + _EDITOR

_JOIN_KEY = (
    Key("lookup_column", required=True, convert=_not_empty, doc="The lookup's column the key is compared with."),
    Key("expression", type=EXPRESSION, required=True, convert=_not_empty,
        doc="The value on the main side: a column of the main row or of an earlier lookup, a constant, "
            "or any expression over them."),
    Key("operator", kind=Kind.REFUSED, off=("=",), reason="join keys are compared for equality only",
        doc="Talend's comparison operator; v1 compares for equality whatever it says."),
    Key("type", kind=Kind.IGNORED, type=object, doc="The lookup column's own type decides."),
    Key("nullable", kind=Kind.IGNORED, type=object, doc="A missing key never matches."),
)

_LOOKUP = (
    Key("name", required=True, convert=_not_empty, doc="The flow that brings the lookup's rows."),
    Key("join_keys", type=list, default=[], items=_JOIN_KEY,
        doc="What a lookup row is matched on. Without keys every lookup row goes with every main row."),
    Key("join_mode", default="LEFT_OUTER_JOIN", choices=("LEFT_OUTER_JOIN", "INNER_JOIN"),
        doc="Whether a main row without a match is kept, its lookup columns missing, or leaves the outputs."),
    Key("matching_mode", default="UNIQUE_MATCH", choices=_MATCHING_MODES,
        doc="Which lookup rows a main row gets when several match: the last (UNIQUE_MATCH, LAST_MATCH), "
            "the first (FIRST_MATCH) or all of them (ALL_MATCHES). ALL_ROWS is for a lookup without keys."),
    Key("lookup_mode", default="LOAD_ONCE", convert=_load_once, doc="When the lookup is loaded: once."),
    Key("filter", type=EXPRESSION, default="",
        doc="A condition on the lookup's own columns, applied before the join."),
    Key("activate_filter", type=bool, default=False, doc="Whether `filter` applies."),
) + _EDITOR

_VARIABLE = (
    Key("name", required=True, doc="The name it is read by: `Var.name` or `Var['name']`."),
    Key("expression", type=EXPRESSION, default="",
        doc="Its value. It may read the rows and the variables defined before it."),
    Key("type", kind=Kind.IGNORED, type=object, doc="A variable has the type of its expression, as in v1."),
    Key("nullable", kind=Kind.IGNORED, type=object, doc="Not checked, as in v1."),
)

_COLUMN = (
    Key("name", required=True, convert=_not_empty, doc="The output column."),
    Key("expression", type=EXPRESSION, default="", doc="Its value; empty for a missing value."),
    Key("type", default="str", choices=tuple(TYPE_NAMES),
        doc="The column's type. A value of another kind is turned into it; `str` leaves the value as it is."),
    Key("nullable", kind=Kind.IGNORED, type=object, doc="Not checked on a map's outputs, as in v1."),
    Key("length", kind=Kind.IGNORED, type=object, doc="Never applied, as in v1."),
    Key("precision", kind=Kind.IGNORED, type=object,
        doc="Values are not rounded here, as in v1; the writer's schema decides the places."),
    Key("date_pattern", kind=Kind.IGNORED, type=object, doc="Never read by v1; format dates in the expression."),
    Key("pattern", kind=Kind.IGNORED, type=object, doc="The converter's spelling of `date_pattern`."),
    Key("operator", kind=Kind.IGNORED, type=object, doc="Talend editor state."),
)

_OUTPUT = (
    Key("name", required=True, convert=_not_empty,
        doc="The output's name; the flow that carries it has the same name."),
    Key("columns", type=list, required=True, items=_COLUMN, doc="The output's columns."),
    Key("filter", type=EXPRESSION, default="", doc="A condition a row must meet to leave by this output."),
    Key("activate_filter", type=bool, default=False, doc="Whether `filter` applies."),
    Key("is_reject", type=bool, default=False,
        doc="Whether this output takes the rows no other output took. Its own filter is not read, as in v1."),
    Key("inner_join_reject", type=bool, default=False,
        doc="Whether this output takes the main rows an inner join found no match for."),
    Key("catch_output_reject", type=bool, default=False,
        doc="Written by the converter beside `is_reject`, where it adds nothing. On its own it asks for the "
            "rows whose expressions failed, which v2 does not have."),
) + _EDITOR


@REGISTRY.register
class Map(Transform):
    """Join lookups to a main input and compute named outputs from the joined rows.

    Expressions read a column as ``row1.price`` or ``row1['price']``, a
    variable as ``Var.name``, and ``context`` and ``globalMap`` as elsewhere.
    An operation on a missing value gives a missing value: no expression
    fails on one row, except a conversion written in it (``int(...)``), which
    fails the component.
    """

    names = ("map", "Map", "tMap", "PyMap")
    outputs = {}
    max_inputs = None
    conforms = False
    keys = (
        Key("inputs", type=dict, required=True, doc="The main input and the lookups joined to it.",
            fields=(Key("main", type=dict, required=True, fields=_MAIN, doc="The main input."),
                    Key("lookups", type=list, default=[], items=_LOOKUP, doc="The lookups, joined in this order."))),
        Key("variables", type=list, default=[], items=_VARIABLE, doc="Named values computed once per joined row."),
        Key("outputs", type=list, required=True, items=_OUTPUT, doc="The outputs."),
        Key("die_on_error", type=bool, default=True,
            doc="Whether text that cannot be read as its column's type fails the job instead of going missing."),
        Key("enable_auto_convert_type", type=bool, default=False,
            doc="Whether a join key that is text on one side and a number on the other is compared as numbers."),
        Key("rows_buffer_size", kind=Kind.IGNORED, type=object, doc="Talend's lookup buffer size."),
        Key("output_chunk_size", kind=Kind.IGNORED, type=object, doc="v1 chunk size; never read."),
        Key("change_hash_and_equals_for_bigdecimal", kind=Kind.IGNORED, type=object,
            doc="Decimal keys are always compared by value."),
        Key("component_type", kind=Kind.IGNORED, type=object, doc="v1's display name for the component."),
    )

    @classmethod
    def port_for(cls, flow_type: str, flow_name: str, config: Dict[str, Any]) -> Optional[str]:
        """A flow leaves by the output it is named after."""
        declared = config.get("outputs")
        names = [output.get("name") for output in declared if isinstance(output, dict)] if declared else []
        return flow_name if flow_name in names else None

    @classmethod
    def unread_paths(cls, raw_config: Dict[str, Any]) -> List[str]:
        """A filter is not read while its ``activate_filter`` is off."""
        inputs = raw_config.get("inputs") if isinstance(raw_config.get("inputs"), dict) else {}
        places = [("inputs.main", inputs.get("main"))]
        places += [(f"inputs.lookups[{index}]", lookup) for index, lookup in enumerate(_listed(inputs.get("lookups")))]
        places += [(f"outputs[{index}]", output) for index, output in enumerate(_listed(raw_config.get("outputs")))]
        return [
            f"{where}.filter" for where, holder in places
            if isinstance(holder, dict) and not is_on(holder.get("activate_filter"))
        ]

    @classmethod
    def no_port_reason(cls, flow_type: str, flow_name: str, config: Dict[str, Any]) -> str:
        declared = config.get("outputs") or []
        names = [str(output.get("name")) for output in declared if isinstance(output, dict)]
        return f"has no output named '{flow_name}'; its outputs are: {', '.join(names) or 'none'}"

    def problems(self) -> List[str]:
        config, found = self.config, []
        names = [config["inputs"]["main"]["name"]]
        for index, lookup in enumerate(config["inputs"]["lookups"]):
            where = f"inputs.lookups[{index}]"
            if lookup["name"] in names:
                found.append(f"{where}.name: '{lookup['name']}' is named twice among the inputs")
            names.append(lookup["name"])
            if lookup["matching_mode"] == "ALL_ROWS" and lookup["join_keys"]:
                found.append(
                    f"{where}.matching_mode: ALL_ROWS is for a lookup without join keys; "
                    "with keys, ALL_MATCHES gives every match"
                )
        if not config["outputs"]:
            found.append("outputs: a map needs at least one output")
        outputs: List[str] = []
        for index, output in enumerate(config["outputs"]):
            where = f"outputs[{index}]"
            if output["name"] in outputs:
                found.append(f"{where}.name: '{output['name']}' is the name of more than one output")
            outputs.append(output["name"])
            if not output["columns"]:
                found.append(f"{where}.columns: an output needs at least one column")
            columns: List[str] = []
            for position, column in enumerate(output["columns"]):
                if column["name"] in columns:
                    found.append(
                        f"{where}.columns[{position}].name: '{column['name']}' is the name of more than one column"
                    )
                columns.append(column["name"])
            if output["catch_output_reject"] and not output["is_reject"]:
                found.append(
                    f"{where}.catch_output_reject: v2 has no rows whose expressions failed to send here; "
                    "set is_reject to catch the rows the other outputs turned away"
                )
        return found

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        main = self.config["inputs"]["main"]
        joined = self._filtered(self._input(inputs, main["name"], "inputs.main.name"), main, "inputs.main")
        rows = {main["name"]: _own(joined)}
        missed = False
        for index, lookup in enumerate(self.config["inputs"]["lookups"]):
            where = f"inputs.lookups[{index}]"
            # A lookup's own row numbers are left behind: the row that goes on is the main input's.
            frame = without(self._filtered(self._input(inputs, lookup["name"], f"{where}.name"), lookup, where))
            keys = self._keys(lookup, rows, where, joined, missed)
            joined = joined_with(joined, frame, lookup, keys, missed, self.config["enable_auto_convert_type"], where)
            missed = missed or lookup["join_mode"] == "INNER_JOIN"
            rows[lookup["name"]] = _own(frame)
        scope = self._scope(rows)
        outputs = self.config["outputs"]
        # As in v1, a row an inner join turned away has left before the variables are worked out. v1 gives
        # the output that takes such rows no variables to read; here it may read them, and then they are
        # worked out for every row.
        everywhere = not missed or any(_reads_variables(output) for output in outputs if output["inner_join_reject"])
        joined = self._with_variables(joined, scope, None if everywhere else ~pl.col(MISSED))
        taken = routed(joined, outputs, scope, missed)
        # The variables and the outputs' filters are worked out on the joined rows.
        self.check_conversions(joined, scope)
        check = self.check if self.config["die_on_error"] else None
        return {
            output["name"]: projected(
                taken[index], output, scope, f"outputs[{index}]", check, self.where, self.check_conversions
            )
            for index, output in enumerate(outputs)
        }

    def line_counts(
        self, inputs: Dict[str, pl.LazyFrame], outputs: Dict[str, pl.LazyFrame]
    ) -> Dict[str, List[pl.LazyFrame]]:
        """v1's map counts the rows that leave: by any output, by the ordinary ones, by the reject ones."""
        rejecting = {
            output["name"] for output in self.config["outputs"] if output["is_reject"] or output["inner_join_reject"]
        }
        return {
            "NB_LINE": list(outputs.values()),
            "NB_LINE_OK": [frame for name, frame in outputs.items() if name not in rejecting],
            "NB_LINE_REJECT": [frame for name, frame in outputs.items() if name in rejecting],
        }

    def _input(self, inputs: Dict[str, pl.LazyFrame], name: str, key: str) -> pl.LazyFrame:
        if name not in inputs:
            arriving = ", ".join(inputs) or "none"
            raise ConfigurationError(f"{key}: no flow named '{name}' arrives at the map; arriving: {arriving}")
        return inputs[name]

    def _filtered(self, frame: pl.LazyFrame, source: Dict[str, Any], where: str) -> pl.LazyFrame:
        """An input with its own filter applied; the filter reads that input's columns only."""
        text = source["filter"].strip()
        if not source["activate_filter"] or not text:
            return frame
        scope = self.row_scope(frame.collect_schema(), source["name"])
        kept = condition(text, scope, f"{where}.filter")
        self.check_conversions(frame, scope)
        return frame.filter(kept)

    def _keys(
        self, lookup: Dict[str, Any], rows: Dict[str, Dict[str, pl.DataType]], where: str, joined: pl.LazyFrame,
        missed: bool,
    ) -> List[Tuple[pl.Expr, pl.DataType]]:
        """A lookup's key values on the main side, which may read the lookups joined before it.

        Args:
            lookup: The lookup's config.
            rows: The rows joined so far, by name, with their columns.
            where: The lookup's place in the config, for messages.
            joined: The rows joined so far, which the key expressions are worked out on.
            missed: Whether a lookup joined before this one is an inner join.
        """
        scope = self._scope(rows)
        # A row an earlier inner join turned away is looked up no more, so its key is never worked out.
        looked_up = ~pl.col(MISSED) if missed else None
        keys = []
        for index, key in enumerate(lookup["join_keys"]):
            value = translated(key["expression"], scope, f"{where}.join_keys[{index}].expression", looked_up)
            keys.append((value, type_of(value, scope)))
        self.check_conversions(joined, scope)
        return keys

    def _with_variables(self, joined: pl.LazyFrame, scope: Scope, worked_out: Optional[pl.Expr]) -> pl.LazyFrame:
        """Compute each variable once, as a working column that later expressions read.

        Args:
            joined: The joined rows.
            scope: What a variable may refer to; each variable is added to it.
            worked_out: True for the rows a variable is worked out for; None for every row.
        """
        for index, variable in enumerate(self.config["variables"]):
            text = variable["expression"].strip()
            value = translated(text, scope, f"variables[{index}].expression", worked_out) if text else pl.lit(None)
            column = f"{_VARIABLE_COLUMN}{index}"
            dtype = type_of(value, scope)
            joined = joined.with_columns(value.alias(column))
            scope.columns[column] = dtype
            scope.variables[variable["name"]] = pl.col(column)
        return joined

    def _scope(self, rows: Dict[str, Dict[str, pl.DataType]]) -> Scope:
        """What an expression over the joined rows may refer to: the main row and the lookups joined so far."""
        scope = Scope.for_rows(
            rows, context=self.context, global_map=self.global_map, routines=self.run_context.routines
        )
        self.scopes.append(scope)
        return scope


def _reads_variables(output: Dict[str, Any]) -> bool:
    """Whether an output's columns or its filter read a variable."""
    texts = [column["expression"] for column in output["columns"]]
    if output["activate_filter"]:
        texts.append(output["filter"])
    return any(_names(text.strip(), "Var") for text in texts)


def _names(text: str, name: str) -> bool:
    """Whether an expression holds a name; one that cannot be read holds none, and is refused where it is translated."""
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError:
        return False
    return any(isinstance(node, ast.Name) and node.id == name for node in ast.walk(tree))


def _own(frame: pl.LazyFrame) -> Dict[str, pl.DataType]:
    """A frame's own columns with their types: what an expression may name of it."""
    types = frame.collect_schema()
    return {name: types[name] for name in visible(types)}
