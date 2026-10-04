"""
Execution infrastructure for v2 engine.

Provides DAG building, execution context, stage detection, and component runner.
"""
from .context import ExecutionContext
from .dag import DAG, DAGBuilder, DAGNode, DAGValidationError
from .stage import Stage, StageDAG, StageDetector, StageExecutor, StageResult, StageStatus
from .trigger import TriggerEvaluator

__all__ = [
    'ExecutionContext',
    'DAG', 'DAGBuilder', 'DAGNode', 'DAGValidationError',
    'Stage', 'StageDAG', 'StageDetector', 'StageExecutor', 'StageResult', 'StageStatus',
    'TriggerEvaluator',
]
