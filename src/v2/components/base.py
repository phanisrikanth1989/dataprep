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
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Dict, List, Mapping, Optional, Tuple

import polars as pl

from ..expressions.translate import Scope
from ..job.keys import Key, Kind

if TYPE_CHECKING:
    from ..engine.context import RunContext
    from ..job.model import Column, ComponentSpec

# Keys v1 job configs carry on any component and that never affect the data.
COMMON_KEYS: Tuple[Key, ...] = (
    Key("label", kind=Kind.IGNORED, type=object, doc="Display label."),
    Key("tstatcatcher_stats", kind=Kind.IGNORED, type=object, doc="Talend statistics flag."),
    Key("execution_mode", kind=Kind.IGNORED, type=object, doc="v1 batch/streaming switch; v2 decides itself."),
    Key("chunk_size", kind=Kind.IGNORED, type=object, doc="v1 streaming chunk size."),
)


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

    def __init__(self, spec: "ComponentSpec", config: Dict[str, Any], run_context: "RunContext") -> None:
        self.spec = spec
        self.id = spec.id
        self.config = config
        self.schema: List["Column"] = spec.schema
        self.input_schema: List["Column"] = spec.input_schema
        self.run_context = run_context
        self.taps: List[Tap] = []

    def needs_rows(self) -> bool:
        """Whether this component must be handed real rows instead of a lazy frame."""
        return False

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
        same = {column: column for column in types}
        rows = {name: dict(same) for name in names or ("row",)}
        return Scope(
            columns=dict(types),
            rows=rows,
            bare=next(iter(rows)),
            context=self.context,
            global_map=self.global_map,
            routines=self.run_context.routines,
            **more,
        )

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


@dataclass
class Tap:
    """A frame a component wants computed alongside its subjob."""

    frame: pl.LazyFrame
    receive: Callable[[pl.DataFrame], None]


class CheckFailed(Exception):
    """A component's check found a problem in the data."""


class Source(Component):
    """A component that produces rows and takes no input."""

    max_inputs: ClassVar[Optional[int]] = 0

    def read(self) -> Dict[str, pl.LazyFrame]:
        """Return the lazy frame of each output port."""
        raise NotImplementedError


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
    into a temporary file beside the target, and moves it into place only
    when the subjob has succeeded.

    Attributes:
        path: The file the job writes.
        sink: Given a path, returns the lazy sink that writes there.
        rows: A lazy frame whose one value is the number of rows written.
        count: Given the written temporary file, returns the number of rows
            in it. Used instead of ``rows`` when given: counting from the
            file costs nothing in the pass, while a second frame over the
            same rows can make Polars read the source twice.
        append: Whether to add to an existing file instead of replacing it.
        place: Puts the written temporary file in place, given its path and
            the row count; it must leave no temporary file behind. Without
            it the file is moved to ``path``, or added to it on ``append``.
        finish: Called after the file is in place, with the row count.
    """

    path: str
    sink: Callable[[str], pl.LazyFrame]
    rows: Optional[pl.LazyFrame] = None
    count: Optional[Callable[[str], int]] = None
    append: bool = False
    place: Optional[Callable[[str, Optional[int]], None]] = None
    finish: Optional[Callable[[Optional[int]], None]] = None


class Sink(Component):
    """A component that writes its one input to a file."""

    outputs: ClassVar[Dict[str, Tuple[str, ...]]] = {}
    min_inputs: ClassVar[int] = 1

    def write(self, frame: pl.LazyFrame) -> Write:
        """Describe the file to write from the input frame."""
        raise NotImplementedError


class Eager(Component):
    """A component that needs its input rows in hand."""

    def needs_rows(self) -> bool:
        return True

    def run(self, inputs: Dict[str, pl.DataFrame]) -> Dict[str, pl.DataFrame]:
        """Return the frame of each output port.

        Args:
            inputs: The collected input frames by flow name.
        """
        raise NotImplementedError
