"""Base class of every v2 component."""
from __future__ import annotations

from typing import ClassVar, Dict, Optional, Tuple

from ..job.keys import Key, Kind

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
    """

    names: ClassVar[Tuple[str, ...]] = ()
    keys: ClassVar[Tuple[Key, ...]] = ()
    outputs: ClassVar[Dict[str, Tuple[str, ...]]] = {"main": ("flow", "main")}
    min_inputs: ClassVar[int] = 0
    max_inputs: ClassVar[Optional[int]] = 1

    @classmethod
    def all_keys(cls) -> Tuple[Key, ...]:
        """The declared keys plus the ones every component accepts."""
        declared = {key.name for key in cls.keys}
        return tuple(cls.keys) + tuple(key for key in COMMON_KEYS if key.name not in declared)

    @classmethod
    def port_for(cls, flow_type: str, flow_name: str, config: Dict) -> Optional[str]:
        """The output port a flow of this type leaves by, or None when there is none."""
        for port, flow_types in cls.outputs.items():
            if flow_type in flow_types:
                return port
        return None
