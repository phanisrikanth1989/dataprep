"""
Component library for v2 engine.

Component categories:
- file: FileInput, FileOutput
- transform: Map, Filter, Select, Sort, Unite, UniqRow
- aggregate: Aggregate
- python: PythonCode, PythonDataFrame, PythonRow
- iterate: FileList, FlowToIterate
- utility: ContextLoad
"""
from .base import (
    Component,
    SourceComponent,
    SinkComponent,
    TransformComponent,
    PythonComponent,
    UtilityComponent,
)
from .capabilities import Support, FeatureSupport, get_supported_features
from .registry import ComponentRegistry, REGISTRY

__all__ = [
    'Component',
    'SourceComponent',
    'SinkComponent',
    'TransformComponent',
    'PythonComponent',
    'UtilityComponent',
    'Support',
    'FeatureSupport',
    'get_supported_features',
    'ComponentRegistry',
    'REGISTRY',
]
