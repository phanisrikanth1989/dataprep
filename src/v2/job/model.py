"""The job as v2 holds it once a job config has been loaded."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type

if TYPE_CHECKING:
    from ..components.base import Component

# Every type name a schema column may carry, mapped to v2's name for it.
# v1 job configs write the first spelling of each group.
TYPE_NAMES: Dict[str, str] = {}
for _canonical, _spellings in {
    "str": ("str", "string", "id_String"),
    "int": ("int", "integer", "long", "short", "byte", "id_Integer", "id_Long", "id_Short", "id_Byte"),
    "float": ("float", "double", "id_Float", "id_Double"),
    "bool": ("bool", "boolean", "id_Boolean"),
    "datetime": ("datetime", "timestamp", "id_Date"),
    "date": ("date",),
    "Decimal": ("Decimal", "decimal", "big_decimal", "bigdecimal", "id_BigDecimal"),
}.items():
    for _spelling in _spellings:
        TYPE_NAMES[_spelling] = _canonical


@dataclass(frozen=True)
class Column:
    """One column of a declared schema.

    Attributes:
        name: The column name.
        type: ``str``, ``int``, ``float``, ``bool``, ``datetime``, ``date``
            or ``Decimal``.
        nullable: Whether the column may hold missing values.
        key: Whether the column is part of the key.
        length: Declared length, when there is one.
        precision: Declared number of decimal places, when there is one.
        date_pattern: The strftime pattern dates are read and written with.
    """

    name: str
    type: str = "str"
    nullable: bool = True
    key: bool = False
    length: Optional[int] = None
    precision: Optional[int] = None
    date_pattern: Optional[str] = None


@dataclass(frozen=True)
class Flow:
    """Rows going from one component to another.

    Attributes:
        name: The flow's name, unique in the job. Components that take
            several inputs tell them apart by it.
        source: Id of the component the rows come from.
        target: Id of the component they go to.
        kind: The flow type as written (``flow``, ``reject``, ``filter``...).
        port: The output port of the source the flow leaves by.
    """

    name: str
    source: str
    target: str
    kind: str
    port: str


@dataclass(frozen=True)
class Trigger:
    """A link that starts one subjob after another.

    Attributes:
        kind: ``OnSubjobOk``, ``OnComponentOk``, ``OnSubjobError``,
            ``OnComponentError`` or ``RunIf``.
        source: Id of the component the trigger leaves from.
        target: Id of the component it starts.
        condition: The expression a ``RunIf`` trigger fires on.
        order: Where the trigger comes among those of its subjob; lower
            first, job-config order among equals. v1's ``output_id``.
    """

    kind: str
    source: str
    target: str
    condition: Optional[str] = None
    order: int = 0


@dataclass
class ComponentSpec:
    """One component of a loaded job.

    Attributes:
        id: The component's id in the job.
        type: Its type name as written in the job config.
        cls: The class that runs it.
        raw_config: Its config exactly as written.
        config: Its config under v2 names with defaults filled in. Values
            that name context variables are still unresolved here.
        schema: Its declared output columns.
        input_schema: Its declared input columns.
        reject_schema: The declared columns of its reject output.
        input_schemas: Declared input columns per incoming flow name, for
            components that take several inputs.
        input_order: The component's own list of incoming flow names. Its
            order is the order inputs reach the component in, as in v1.
    """

    id: str
    type: str
    cls: Type["Component"]
    raw_config: Dict[str, Any]
    config: Dict[str, Any]
    schema: List[Column] = field(default_factory=list)
    input_schema: List[Column] = field(default_factory=list)
    reject_schema: List[Column] = field(default_factory=list)
    input_schemas: Dict[str, List[Column]] = field(default_factory=dict)
    input_order: List[str] = field(default_factory=list)

    @property
    def where(self) -> str:
        """How refusals and errors name this component."""
        return f"component {self.id} ({self.type})"


@dataclass
class Job:
    """A loaded job: what the engine runs.

    Attributes:
        name: The job's name.
        context: Context variables and their values.
        components: The components by id, in job-config order.
        flows: The flows, in job-config order.
        triggers: The triggers, in job-config order.
        routines: Where routine modules are loaded from: v1's
            ``python_config`` block, or None.
    """

    name: str
    context: Dict[str, Any] = field(default_factory=dict)
    routines: Optional[Dict[str, Any]] = None
    components: Dict[str, ComponentSpec] = field(default_factory=dict)
    flows: List[Flow] = field(default_factory=list)
    triggers: List[Trigger] = field(default_factory=list)

    def incoming(self, component_id: str) -> List[Flow]:
        """The flows arriving at a component, in the order it takes its inputs.

        That is the order of the component's own ``inputs`` list where it
        names them, and job-config order for the rest.
        """
        arriving = [flow for flow in self.flows if flow.target == component_id]
        spec = self.components.get(component_id)
        listed = spec.input_order if spec is not None else []
        if not listed:
            return arriving
        place = {name: index for index, name in enumerate(listed)}
        return sorted(arriving, key=lambda flow: place.get(flow.name, len(place)))

    def outgoing(self, component_id: str) -> List[Flow]:
        """The flows leaving a component, in job-config order."""
        return [flow for flow in self.flows if flow.source == component_id]
