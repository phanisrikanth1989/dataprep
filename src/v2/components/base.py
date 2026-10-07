"""Base classes of every v2 component.

A component is one of four kinds, and the kind says who does the work:

- ``Source``: makes lazy frames out of nothing (a file). No input.
- ``Transform``: turns lazy frames into lazy frames. It only builds the plan.
- ``Sink``: describes a file to write. The engine runs the write.
- ``Eager``: needs the rows in hand (user Python, printing rows). The engine
  collects its inputs for it. This is the one kind that holds rows in memory.

Components never collect. The engine does, once per subjob wherever it can.
A component that needs something out of the data (a few rows to print, a
count to verify) asks for it with ``tap`` or ``check`` and is handed the
answer when the engine has run the subjob.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Dict, List, Mapping, Optional, Set, Tuple

import polars as pl

from ..expressions.translate import Scope
from ..job.keys import Key, Kind
from ..rows import REASON, described, first_of, key_column, row_column, shown, visible

if TYPE_CHECKING:
    from ..engine.context import RunContext
    from ..job.model import Column, ComponentSpec

# Keys v1 job configs carry on any component and that never affect the data.
COMMON_KEYS: Tuple[Key, ...] = (
    Key("label", kind=Kind.IGNORED, type=object, doc="Display label."),
    Key("tstatcatcher_stats", kind=Kind.IGNORED, type=object, doc="Talend statistics flag."),
    Key("execution_mode", kind=Kind.IGNORED, type=object, doc="v1 batch/streaming switch; v2 decides itself."),
    Key("chunk_size", kind=Kind.IGNORED, type=object, doc="v1 streaming chunk size."),
    Key("component_type", kind=Kind.IGNORED, type=object, doc="v1's name for the component type; a label."),
)


# In the frame asked for about dropped rows: how many there are, and what is wrong with the first.
_DROPPED = "__dropped_rows"
_WRONG = "__dropped_why"
# In the frame a check of conversions computes, for each conversion: how many rows it failed on, and what
# it was handed on the first failing row.
_FAILED = "__failed_rows_"
_CONVERTED = "__converted_"


def is_on(value: Any) -> bool:
    """Whether a switch in a config as written is on: true, or the text "true"."""
    return value is True or (isinstance(value, str) and value.strip().lower() == "true")


def ascii_only(text: str) -> str:
    """A text as plain ASCII, for the log: any other character is written as its escape."""
    return text.encode("ascii", "backslashreplace").decode("ascii")


# A line break and every other control character, each as the escape it is written with.
_CONTROL = {code: f"\\x{code:02x}" for code in (*range(32), 127)}
_CONTROL.update({9: "\\t", 10: "\\n", 13: "\\r"})


def one_line(text: str) -> str:
    """A text as one line of plain ASCII, for a log line that shows values from the data.

    A line break, any other control character and whatever is beyond ASCII
    are written as escapes, so that a value can neither start a line of its
    own nor act on the terminal the log is read in.
    """
    return ascii_only(text).translate(_CONTROL)


class Component:
    """One step of a job.

    Class attributes a component declares:

    Attributes:
        names: Type names a job config may use: v2's first, then v1's.
        keys: The config keys the component knows.
        outputs: Each output port, mapped to the v1 flow types that leave by
            it. A flow with no explicit port is matched on its type.
        min_inputs: The fewest input flows the component can work with.
        max_inputs: The most input flows it takes; None for any number.
        conforms: Whether the engine makes the ``main`` and ``reject``
            outputs match the declared schemas (column order, missing
            columns, types, values that may not be missing), as v1 does
            after every component. A component that already produces
            exactly its schema turns this off.
        may_need_rows: Whether ``needs_rows()`` can ever be true for the
            class. A subjob holding such a component is never run a second
            time (see ``RunContext.fast_read``), because what the component
            did with the rows cannot be undone.
        sees_hidden_columns: Whether the component is handed the hidden
            columns that say where a row came from (``src/v2/rows.py``). A
            component that hands its rows to code the engine cannot see
            into, or that reads its columns by their place, turns this off;
            what it hands on has then lost them.

    An instance exists for one run of one subjob. It holds:

    Attributes:
        id: The component's id in the job.
        config: Its config under v2 names, context references resolved.
        schema: Its declared output columns.
        input_schema: Its declared input columns.
        run_context: The run it belongs to (context, globalMap, routines).
    """

    names: ClassVar[Tuple[str, ...]] = ()
    keys: ClassVar[Tuple[Key, ...]] = ()
    outputs: ClassVar[Dict[str, Tuple[str, ...]]] = {"main": ("flow", "main")}
    min_inputs: ClassVar[int] = 0
    max_inputs: ClassVar[Optional[int]] = 1
    conforms: ClassVar[bool] = True
    may_need_rows: ClassVar[bool] = False
    sees_hidden_columns: ClassVar[bool] = True

    def __init__(self, spec: "ComponentSpec", config: Dict[str, Any], run_context: "RunContext") -> None:
        self.spec = spec
        self.id = spec.id
        self.config = config
        self.schema: List["Column"] = spec.schema
        self.input_schema: List["Column"] = spec.input_schema
        self.run_context = run_context
        self.taps: List[Tap] = []
        self.noticed: List[Noticed] = []
        # Every scope handed out: each has to be checked for conversions before the component is done building.
        self.scopes: List[Scope] = []
        # The output ports a flow leaves by. The engine fills it in; a component may do less for a port nobody reads.
        self.wired: Set[str] = set()

    def needs_rows(self) -> bool:
        """Whether this component must be handed real rows instead of a lazy frame."""
        return False

    def lookup_inputs(self, names: List[str]) -> List[str]:
        """Which of the flows that arrive are looked things up in, and are not where its rows come from.

        The engine asks when it traces picked rows: a component's rows come
        from the picked rows when every input that is not a lookup does.
        """
        return []

    def line_counts(
        self, inputs: Dict[str, pl.LazyFrame], outputs: Dict[str, pl.LazyFrame]
    ) -> Dict[str, List[pl.LazyFrame]]:
        """The frames whose rows add up to each of the component's row counts.

        The counts are ``NB_LINE``, ``NB_LINE_OK`` and ``NB_LINE_REJECT``
        (``<id>_NB_LINE``... in globalMap). v1's rule is the default:
        NB_LINE is the rows of every input, or of the main and reject
        outputs for a component with no input; OK is the main output and
        REJECT the reject output. A component whose v1 counterpart counts
        differently says so here. Counting happens only when something in
        the job reads the count, or when the run asks for the counts of
        every component.
        """
        accepted = [outputs[port] for port in ("main",) if port in outputs]
        rejected = [outputs[port] for port in ("reject",) if port in outputs]
        return {
            "NB_LINE": list(inputs.values()) or accepted + rejected,
            "NB_LINE_OK": accepted,
            "NB_LINE_REJECT": rejected,
        }

    def problems(self) -> List[str]:
        """What is wrong with this component's config that no data is needed to see.

        Called when the job is checked at load and again before the component
        runs. Say here what the key declarations cannot: keys that do not go
        together, a schema that is needed. Each entry reads
        ``"<key>: <what is wrong>"``.
        """
        return []

    def declared_outputs(self) -> Dict[str, pl.LazyFrame]:
        """Empty frames shaped like this component's outputs, from its declared schema.

        Used when a job is checked at load, where a source is not read and a
        component that needs rows is not run. Returns nothing when no schema
        is declared, and what follows the component is then left unchecked.
        """
        from ..types import polars_schema  # late: types reads the job model only

        if not self.schema:
            return {}
        outputs = {"main": pl.LazyFrame(schema=polars_schema(self.schema))}
        for port in type(self).outputs:
            if port != "main":
                text = {column.name: pl.String for column in self.schema}
                text.update({"errorCode": pl.String, "errorMessage": pl.String})
                outputs[port] = pl.LazyFrame(schema=text)
        return outputs

    def row_scope(self, types: Mapping[str, pl.DataType], *names: str, **more: Any) -> Scope:
        """What an expression over one input may refer to.

        Its columns may be written bare (``price``) or after any of the given
        row names (``row1.price``, ``input_row.price``), and it may read
        ``context``, ``globalMap`` and the run's routines.

        Args:
            types: The input's columns and their Polars types.
            *names: Names the row goes by; the flow's name, usually.
            **more: Further ``Scope`` fields, such as ``variables``.
        """
        # The hidden columns are not a job's to name.
        types = {column: types[column] for column in visible(types)}
        same = {column: column for column in types}
        rows = {name: dict(same) for name in names or ("row",)}
        scope = Scope(
            columns=dict(types),
            rows=rows,
            bare=next(iter(rows)),
            context=self.context,
            global_map=self.global_map,
            routines=self.run_context.routines,
            **more,
        )
        self.scopes.append(scope)
        return scope

    def check_conversions(self, frame: pl.LazyFrame, scope: Scope, where: Optional[str] = None) -> None:
        """Fail the component when a conversion in a translated expression fails on a row.

        An expression's ``int()``, ``float()`` or ``strptime()`` gives
        nothing where it cannot convert, and the translation notes those
        rows in its scope. This asks, in the pass the subjob runs in, how
        many rows of the frame are among them and which is the first, and
        fails the component with the conversion that failed on that row,
        the value it was handed, the row, and how many rows that one
        conversion failed on.

        Call it for every frame expressions were translated to run on, once
        they are translated. The conversions it checks are taken out of the
        scope, so the next call checks only what was translated since.

        Args:
            frame: The rows the expressions are worked out on.
            scope: The scope they were translated with.
            where: The config key that holds them, when they were not given
                one each.
        """
        failures, scope.failures[:] = list(scope.failures), []
        if not failures:
            return
        bad = frame.filter(pl.any_horizontal([failure.failed for failure in failures]))
        asked: List[pl.Expr] = []
        for index, failure in enumerate(failures):
            # What the conversion was handed on the first failing row, when it is one that failed there;
            # and on how many rows it failed.
            handed = pl.when(failure.failed).then(failure.value.cast(pl.String))
            asked += [handed.first().alias(f"{_CONVERTED}{index}"), failure.failed.sum().alias(f"{_FAILED}{index}")]

        def problem(found: pl.DataFrame) -> Optional[str]:
            for index, failure in enumerate(failures):
                value = found[f"{_CONVERTED}{index}"].item()
                if value is not None:
                    rows = found[f"{_FAILED}{index}"].item()
                    count = "1 row" if rows == 1 else f"{rows} rows"
                    return (
                        f"{where or failure.where}: {failure.what} could not read '{shown(value)}' "
                        f"(in: {failure.source}); {count} failed{self.where(found)}"
                    )
            return None

        self.check(bad.select(*asked, *first_of(bad)), problem)

    def unchecked(self) -> List[str]:
        """The expressions whose conversions were translated and never checked: a fault in the component."""
        return sorted({failure.source for scope in self.scopes for failure in scope.failures})

    def tap(self, frame: pl.LazyFrame, receive: Callable[[pl.DataFrame], None]) -> None:
        """Ask for a frame to be computed in the same pass as the subjob.

        Keep it small: a few rows, or an aggregate. It is held in memory.

        Args:
            frame: What to compute.
            receive: Called with the result once the pass has run and before
                any file of the subjob is put in place. If it raises, the
                component has failed.
        """
        self.taps.append(Tap(frame, receive))

    def check(self, frame: pl.LazyFrame, problem: Callable[[pl.DataFrame], Optional[str]]) -> None:
        """Verify something about the data once the subjob has run.

        Args:
            frame: What to compute, as for ``tap``.
            problem: Given the result, returns what is wrong, or None. A
                problem fails the component, and no file of the subjob is
                put in place.
        """

        def receive(result: pl.DataFrame) -> None:
            found = problem(result)
            if found:
                raise CheckFailed(found)

        self.tap(frame, receive)

    def tell_dropped(self, frame: pl.LazyFrame, turned_away: pl.Expr, wrong: pl.Expr) -> pl.LazyFrame:
        """Have the log say that rows of a frame are dropped for a fault. Returns the frame to go on with.

        For the rows a component turns away because something is wrong with
        them (a value that cannot be read, a missing value where none is
        allowed) and then goes on without. Not for the rows the job itself
        turns away, such as a filter's. Nothing is said when a flow takes
        the component's reject output: the rows are then the job's to deal
        with. Nothing is said either when the subjob fails: nothing was
        written, so nothing was dropped.

        Such rows are noticed as they pass, which costs next to nothing.
        Only a subjob that had some is asked, once it has finished, how many
        they were and which was the first: that is a second reading.

        Args:
            frame: The rows, the turned-away ones among them, with the
                hidden columns they came with.
            turned_away: True for a row that is turned away.
            wrong: What is wrong with such a row, as text.

        Returns:
            The frame to take the rows that go on from, in place of
            ``frame``: it is what notices the rows.
        """
        if "reject" in self.wired:
            return frame
        untaken = " (no flow takes this component's rejects)" if "reject" in type(self).outputs else ""

        def said(found: Optional[pl.DataFrame], why_not: str = "") -> Optional[str]:
            if found is None:
                return f"rows were dropped{untaken}; how many and which could not be found: {why_not}"
            rows = found[_DROPPED].item()
            if not rows:
                return None
            start = f"1 row was dropped{untaken}: " if rows == 1 else f"{rows} rows were dropped{untaken}; the first: "
            return f"{start}{shown(found[_WRONG].item(), REASON)}{self.where(found)}"

        rows = frame.filter(turned_away)
        # Counted as a sum: Polars 1.44 miscounts a plain row count of some frames (see the component guide).
        asked = rows.select(
            turned_away.sum().alias(_DROPPED), wrong.first().str.slice(0, REASON + 1).alias(_WRONG), *first_of(rows)
        )
        noting, any_passed = self.run_context.noticing(frame, turned_away)
        self.noticed.append(Noticed(asked, any_passed, said))
        return noting

    def where(self, found: pl.DataFrame) -> str:
        """The words that name the row a check found, to end its message with.

        Args:
            found: The check's one-row result, holding the hidden columns of
                the first failing row (``rows.first_of`` asks for them).

        Returns:
            ``"; the row is line 7 of in.csv (id=42)"``; nothing when the row
            carries no number.
        """
        return described(found.row(0, named=True), self.run_context.sources) if found.height else ""

    @property
    def context(self) -> Dict[str, Any]:
        """The run's context values. Changes are seen by components built later."""
        return self.run_context.context

    @property
    def global_map(self) -> Dict[str, Any]:
        """The run's globalMap entries."""
        return self.run_context.global_map

    @classmethod
    def all_keys(cls) -> Tuple[Key, ...]:
        """The declared keys plus the ones every component accepts."""
        declared = {key.name for key in cls.keys}
        return tuple(cls.keys) + tuple(key for key in COMMON_KEYS if key.name not in declared)

    @classmethod
    def port_for(cls, flow_type: str, flow_name: str, config: Dict[str, Any]) -> Optional[str]:
        """The output port a flow of this type leaves by, or None when there is none."""
        for port, flow_types in cls.outputs.items():
            if flow_type in flow_types:
                return port
        return None

    @classmethod
    def unread_paths(cls, raw_config: Dict[str, Any]) -> List[str]:
        """Paths of config values the component does not read with the config as written.

        A filter that is switched off, for example. The converter leaves
        Talend's Java there; a Java expression under one of these paths does
        not refuse the job. Paths are written as the refusal report writes
        them: ``advanced_cond``, ``outputs[0].filter``.
        """
        return []

    @classmethod
    def no_port_reason(cls, flow_type: str, flow_name: str, config: Dict[str, Any]) -> str:
        """What to say of a flow no output port takes: the words after "a <type> "."""
        return f"has no '{flow_type}' output"


@dataclass
class Tap:
    """A frame a component wants computed alongside its subjob."""

    frame: pl.LazyFrame
    receive: Callable[[pl.DataFrame], None]


@dataclass
class Noticed:
    """Rows a component turned away for a fault and noticed as they passed (``Component.tell_dropped``).

    Attributes:
        frame: What to ask when any passed: how many they were, what was
            wrong with the first, and where that one came from.
        any: Whether any passed, once the subjob has run.
        said: The words for the log, given the frame's result; or, when the
            frame could not be computed, given None and why not. None when
            there is nothing to say.
    """

    frame: pl.LazyFrame
    any: Callable[[], bool]
    said: Callable[..., Optional[str]]


class CheckFailed(Exception):
    """A component's check found a problem in the data."""


class Source(Component):
    """A component that produces rows and takes no input.

    A source numbers its rows from 1 as it reads them, before it drops any,
    in the column ``row_number``, and hands that column on with every row of
    every output, together with ``key_copies()``. ``locate`` says where a
    number is, in the words a person looking for the row would use, and
    ``number_at`` goes the other way.

    A run may be for a few rows of a source and no others (``run.only``).
    The engine then names them by their numbers in ``only_rows``, and the
    source keeps to them with ``picked``, called where it has numbered its
    rows and before it types or turns away any.
    """

    max_inputs: ClassVar[Optional[int]] = 0
    # The numbers of the rows a run is for, when it is not for every row. Set by the engine before ``read``.
    only_rows: Optional[List[int]] = None

    def read(self) -> Dict[str, pl.LazyFrame]:
        """Return the lazy frame of each output port."""
        raise NotImplementedError

    @property
    def row_number(self) -> str:
        """The name of the hidden column that holds this source's row numbers."""
        return row_column(self.id)

    def key_copies(self) -> List[pl.Expr]:
        """Hidden copies of the columns the schema marks as key, to hand on beside the row number."""
        return [pl.col(column.name).alias(key_column(self.id, column.name)) for column in self.schema if column.key]

    def locate(self, number: int) -> str:
        """Where the row with a number is: ``"line 7 of in.csv"``."""
        raise NotImplementedError

    def picked(self, frame: Any) -> Any:
        """The rows of a frame that a run is for: every row, unless the engine named some by their numbers."""
        if self.only_rows is None:
            return frame
        return frame.filter(pl.col(self.row_number).is_in(self.only_rows))

    @property
    def place_kind(self) -> str:
        """The kind of place this source's rows have, as ``locate`` names them: ``lines``, ``records`` or ``rows``."""
        return "lines"

    @property
    def place_why(self) -> str:
        """Why its rows have that kind of place, to follow the source's id in a message."""
        return "is read line by line"

    def number_at(self, place: int, sheet: Optional[str] = None) -> int:
        """The number of the row at a place: ``locate`` the other way round. Called once the source is read.

        Args:
            place: The line, record or row, as ``locate`` would say it.
            sheet: The sheet it is on, for a source that has sheets.

        Raises:
            ValueError: When no row of this source can be at that place.
                The message says why.
        """
        header = max(self.config.get("header_rows") or 0, 0)
        if place <= header:
            raise ValueError(f"its first {header} line(s) are the header")
        return place - header


class Transform(Component):
    """A component that turns lazy frames into lazy frames."""

    min_inputs: ClassVar[int] = 1

    def build(self, inputs: Dict[str, pl.LazyFrame]) -> Dict[str, pl.LazyFrame]:
        """Return the lazy frame of each output port.

        Args:
            inputs: The input frames by flow name, in the order the flows are
                written in the job config.
        """
        raise NotImplementedError

    def run(self, inputs: Dict[str, pl.DataFrame]) -> Dict[str, pl.DataFrame]:
        """Return the frame of each output port, given real rows.

        Called instead of ``build`` when ``needs_rows()`` says so.
        """
        raise NotImplementedError


@dataclass
class Write:
    """A file a sink wants written.

    The engine runs the write, together with everything else in the subjob,
    into a temporary file beside the target. When the whole subjob has
    succeeded, every file it wrote is first made ready where it is
    (``ready``), and only then are the files put in place (``place``), in
    the order their components run. ``ready`` is the last place the rows
    can fail the subjob, so a subjob that fails leaves every file as it was.

    The engine counts the rows it hands the sink as they pass, and gives
    that count to ``ready``, ``place`` and ``finish``.

    Attributes:
        path: The file the job writes.
        sink: Given a path, returns the lazy sink that writes there.
        append: Whether to add to an existing file instead of replacing it.
        ready: Makes the written temporary file final in everything but its
            name, given its path and the row count: puts it in the job's
            encoding, say. It may raise.
        place: Puts the ready file in place, given its path and the row
            count; it must leave no temporary file behind, and only the file
            system may fail it. Without it the file is moved to ``path``, or
            added to it on ``append``.
        finish: Called after the file is in place, with the row count.
        refuses_existing: What to fail with when an earlier output of the
            same subjob leaves a file at ``path``; None when the write may
            find one there. A file that is there before the subjob starts is
            the sink's own to refuse, in ``write``.
        empty_leaves_none: Whether no file is left at ``path`` when no row
            was written.
    """

    path: str
    sink: Callable[[str], pl.LazyFrame]
    append: bool = False
    ready: Optional[Callable[[str, int], None]] = None
    place: Optional[Callable[[str, int], None]] = None
    finish: Optional[Callable[[int], None]] = None
    refuses_existing: Optional[str] = None
    empty_leaves_none: bool = False


class Sink(Component):
    """A component that writes its one input to a file."""

    outputs: ClassVar[Dict[str, Tuple[str, ...]]] = {}
    min_inputs: ClassVar[int] = 1

    def write(self, frame: pl.LazyFrame) -> Write:
        """Describe the file to write from the input frame."""
        raise NotImplementedError


class Eager(Component):
    """A component that needs its input rows in hand."""

    may_need_rows: ClassVar[bool] = True

    def needs_rows(self) -> bool:
        return True

    def run(self, inputs: Dict[str, pl.DataFrame]) -> Dict[str, pl.DataFrame]:
        """Return the frame of each output port.

        Args:
            inputs: The collected input frames by flow name.
        """
        raise NotImplementedError
