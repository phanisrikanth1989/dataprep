"""
Job Configuration Models for v2 Engine.

Defines the structure of ETL job configurations using Pydantic for validation.
"""
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


class ContextVariableType(str, Enum):
    """Supported context variable types."""
    STRING = "str"
    INTEGER = "int"
    FLOAT = "float"
    BOOLEAN = "bool"
    DATE = "date"
    DATETIME = "datetime"


class ContextVariable(BaseModel):
    """A context variable definition."""
    value: Any
    type: ContextVariableType = ContextVariableType.STRING
    format: Optional[str] = None
    description: Optional[str] = None

    def get_typed_value(self) -> Any:
        """Return the value cast to the appropriate Python type."""
        if self.value is None:
            return None

        type_map = {
            ContextVariableType.STRING: str,
            ContextVariableType.INTEGER: int,
            ContextVariableType.FLOAT: float,
            ContextVariableType.BOOLEAN: bool,
        }

        if self.type in type_map:
            return type_map[self.type](self.value)

        if self.type == ContextVariableType.DATE:
            if isinstance(self.value, date):
                return self.value
            s = str(self.value)
            if self.format:
                return datetime.strptime(s, self.format).date()
            return date.fromisoformat(s)

        if self.type == ContextVariableType.DATETIME:
            if isinstance(self.value, datetime):
                return self.value
            s = str(self.value)
            if self.format:
                return datetime.strptime(s, self.format)
            return datetime.fromisoformat(s)

        return self.value


class FlowConnection(BaseModel):
    """A connection between components."""
    source: str = Field(..., description="Source component ID")
    output: str = Field(default="main", description="Output port name from source")
    target: str = Field(..., description="Target component ID")
    input: str = Field(default="main", description="Input port name on target")


class TriggerType(str, Enum):
    """Types of trigger connections between stages."""
    ON_SUCCESS = "on_success"
    ON_FAILURE = "on_failure"
    CONDITIONAL = "conditional"


class TriggerConnection(BaseModel):
    """A trigger (control-flow) connection between stages.

    Triggers connect stages and determine execution order and conditions.
    The source/target fields reference component IDs — the engine maps
    these to stages automatically.
    """
    source: str = Field(..., description="Source component ID (identifies source stage)")
    target: str = Field(..., description="Target component ID (identifies target stage)")
    type: TriggerType = Field(..., description="Trigger type")
    condition: Optional[str] = Field(
        default=None,
        description="Boolean expression for conditional triggers",
    )

    @model_validator(mode='after')
    def validate_condition(self) -> 'TriggerConnection':
        if self.type == TriggerType.CONDITIONAL and not self.condition:
            raise ValueError(
                "TriggerConnection with type='conditional' requires a non-empty 'condition'"
            )
        return self


class ComponentConfig(BaseModel):
    """Base configuration for a component."""
    id: str = Field(..., description="Unique component identifier")
    type: str = Field(..., description="Component type (e.g., 'file_input', 'map')")
    config: Dict[str, Any] = Field(default_factory=dict, description="Component-specific configuration")


class JobConfig(BaseModel):
    """
    Complete job configuration.

    Example:
        {
            "name": "customer_orders_etl",
            "version": "2.0",
            "context": {
                "input_dir": {"value": "/data/input", "type": "str"},
                "tax_rate": {"value": 0.08, "type": "float"}
            },
            "components": [...],
            "flows": [...],
        }
    """
    name: str = Field(..., description="Job name")
    version: str = Field(default="2.0", description="Config version")
    description: Optional[str] = None

    # Context variables
    context: Dict[str, Union[ContextVariable, Dict[str, Any]]] = Field(
        default_factory=dict,
        description="Context variables available to all components"
    )

    # Components and flows
    components: List[ComponentConfig] = Field(
        default_factory=list,
        description="List of component configurations"
    )
    flows: List[FlowConnection] = Field(
        default_factory=list,
        description="Data flow connections between components"
    )

    # Execution settings
    streaming: bool = Field(
        default=False,
        description="Use Polars streaming engine for .collect() at barrier points"
    )

    # Trigger connections (orchestration)
    triggers: List[TriggerConnection] = Field(
        default_factory=list,
        description="Trigger connections between stages for orchestration"
    )

    @field_validator('context', mode='before')
    @classmethod
    def normalize_context(cls, v):
        """Convert simple dicts to ContextVariable objects."""
        if not isinstance(v, dict):
            return v

        result = {}
        for key, value in v.items():
            if isinstance(value, ContextVariable):
                result[key] = value
            elif isinstance(value, dict) and 'value' in value:
                result[key] = ContextVariable(**value)
            else:
                # Simple value - wrap it with auto-detected type
                inferred_type = ContextVariableType.STRING
                if isinstance(value, bool):
                    inferred_type = ContextVariableType.BOOLEAN
                elif isinstance(value, int):
                    inferred_type = ContextVariableType.INTEGER
                elif isinstance(value, float):
                    inferred_type = ContextVariableType.FLOAT
                result[key] = ContextVariable(value=value, type=inferred_type)
        return result

    def get_context_values(self) -> Dict[str, Any]:
        """Get all context variables as a simple dict of typed values."""
        return {
            key: var.get_typed_value() if isinstance(var, ContextVariable) else var
            for key, var in self.context.items()
        }

    def get_component(self, component_id: str) -> Optional[ComponentConfig]:
        """Get a component by ID."""
        for comp in self.components:
            if comp.id == component_id:
                return comp
        return None

    def get_source_components(self) -> List[ComponentConfig]:
        """Get components that have no incoming flows (sources)."""
        targets = {flow.target for flow in self.flows}
        return [c for c in self.components if c.id not in targets]

    def get_downstream_components(self, component_id: str) -> List[str]:
        """Get component IDs that receive data from the given component."""
        return [
            flow.target for flow in self.flows
            if flow.source == component_id
        ]

    def get_upstream_components(self, component_id: str) -> List[str]:
        """Get component IDs that send data to the given component."""
        return [
            flow.source for flow in self.flows
            if flow.target == component_id
        ]
