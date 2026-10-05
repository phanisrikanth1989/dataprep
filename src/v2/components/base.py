"""Base classes of every v2 component.

A component is one of four kinds, and the kind says who does the work:

- ``Source``: makes lazy frames out of nothing (a file). No input.
- ``Transform``: turns lazy frames into lazy frames. It only builds the plan.
- ``Sink``: describes a file to write. The engine runs the write.
- ``Eager``: needs the rows in hand (user Python, printing rows). The engine
  collects its inputs for it. This is the one kind that holds rows in memory.

Components never collect. The engine does, once per subjob wherever it can.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Dict, List, Optional, Tuple

import polars as pl

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

    def __init__(self, spec: "ComponentSpec", config: Dict[str, Any], run_context: "RunContext") -> None:
        self.spec = spec
        self.id = spec.id
        self.config = config
        self.schema: List["Column"] = spec.schema
        self.input_schema: List["Column"] = spec.input_schema
        self.run_context = run_context

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
        append: Whether to add to an existing file instead of replacing it.
        finish: Called after the file is in place, with the row count.
    """

    path: str
    sink: Callable[[str], pl.LazyFrame]
    rows: Optional[pl.LazyFrame] = None
    append: bool = False
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

    def run(self, inputs: Dict[str, pl.DataFrame]) -> Dict[str, pl.DataFrame]:
        """Return the frame of each output port.

        Args:
            inputs: The collected input frames by flow name.
        """
        raise NotImplementedError
