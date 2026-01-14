"""
Pydantic models for RecDataPrep UI API
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum
import uuid


class ComponentFieldType(str, Enum):
    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    SELECT = "select"
    EXPRESSION = "expression"
    ARRAY = "array"


class ComponentFieldSchema(BaseModel):
    """Schema for a component configuration field"""
    name: str
    type: ComponentFieldType
    label: str
    description: Optional[str] = None
    default: Any = None
    required: bool = False
    options: Optional[List[str]] = None  # For select fields
    placeholder: Optional[str] = None


class ComponentMetadata(BaseModel):
    """Metadata for a component type"""
    type: str
    label: str
    category: str  # "Input", "Transform", "Output"
    icon: str
    description: str
    fields: List[ComponentFieldSchema]
    input_count: int = 1
    output_count: int = 1
    allow_multiple_inputs: bool = False


class JobNode(BaseModel):
    """A component instance in a job"""
    id: str
    type: str
    label: str
    x: float
    y: float
    config: Dict[str, Any] = {}
    subjob_id: Optional[str] = None
    is_subjob_start: bool = False


class JobEdge(BaseModel):
    """A connection between two components"""
    id: str
    source: str
    target: str
    edge_type: str = "flow"  # "flow", "trigger", "iterate"
    name: Optional[str] = None
    trigger_type: Optional[str] = None  # For trigger edges
    condition: Optional[str] = None  # For conditional triggers


class ContextVariable(BaseModel):
    """A context variable definition"""
    name: str
    value: Any
    type: str  # "id_String", "id_Integer", etc.
    description: Optional[str] = None


class JobSchema(BaseModel):
    """Complete job configuration"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    nodes: List[JobNode] = []
    edges: List[JobEdge] = []
    context: Dict[str, Any] = {}
    java_config: Dict[str, Any] = {"enabled": False}
    python_config: Dict[str, Any] = {"enabled": False}
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ExecutionRequest(BaseModel):
    """Request to execute a job"""
    job_id: str
    context_overrides: Optional[Dict[str, Any]] = None


class ExecutionStatus(BaseModel):
    """Execution status response"""
    task_id: str
    job_id: str
    status: str  # "pending", "running", "success", "error"
    progress: float = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    stats: Dict[str, Any] = {}


class ExecutionUpdate(BaseModel):
    """Real-time execution update for WebSocket"""
    type: str  # "progress", "stats", "log", "complete", "error"
    task_id: str
    data: Dict[str, Any] = {}
    message: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: __import__('datetime').datetime.utcnow().isoformat())
