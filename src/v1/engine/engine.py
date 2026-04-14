"""Main ETL Engine -- thin orchestrator delegating to Executor, ExecutionPlan, OutputRouter.

Backward-compatible API: ETLEngine, run_job(), CLI entry point preserved.
"""
import json
import logging
import time
from typing import Dict, Any
import argparse

from .global_map import GlobalMap
from .context_manager import ContextManager
from .trigger_manager import TriggerManager
from .base_component import BaseComponent
from .exceptions import ETLError
from .java_bridge_manager import JavaBridgeManager
from .python_routine_manager import PythonRoutineManager
from .component_registry import REGISTRY
from .execution_plan import ExecutionPlan
from .output_router import OutputRouter
from .executor import Executor

logger = logging.getLogger(__name__)


class ETLEngine:
    """Main ETL execution engine -- thin orchestrator delegating to Executor,
    ExecutionPlan, OutputRouter, and REGISTRY.
    """

    def __init__(self, job_config: Dict[str, Any]):
        """Initialize ETL engine with job configuration."""
        # Load configuration
        if isinstance(job_config, str):
            with open(job_config, 'r') as f:
                self.job_config = json.load(f)
        else:
            self.job_config = job_config

        # Java bridge
        self.java_bridge_manager = None
        java_config = self.job_config.get('java_config', {})
        if java_config.get('enabled', False):
            routines = java_config.get('routines', [])
            libraries = java_config.get('libraries', [])
            self.java_bridge_manager = JavaBridgeManager(enable=True, routines=routines, libraries=libraries)
            self.java_bridge_manager.start()
            logger.info(f"Java bridge initialized with {len(routines)} routines and {len(libraries)} libraries")

        # Python routine manager
        self.python_routine_manager = None
        python_config = self.job_config.get('python_config', {})
        if python_config.get('enabled', False):
            routines_dir = python_config.get('routines_dir', 'src/python_routines')
            self.python_routine_manager = PythonRoutineManager(routines_dir)
            logger.info(f"Python routine manager initialized from {routines_dir}")

        # Core services
        self.job_name = self.job_config.get('job_name', 'unnamed_job')
        self.global_map = GlobalMap()
        self.context_manager = ContextManager(
            initial_context=self.job_config.get('context', {}),
            default_context=self.job_config.get('default_context', 'Default'),
            java_bridge_manager=self.java_bridge_manager
        )
        self.trigger_manager = TriggerManager(self.global_map)

        self.components: Dict[str, BaseComponent] = {}
        self._initialize_components()
        self._initialize_triggers()

        # Build execution plan, output router, executor
        components_config = self.job_config.get('components', [])
        flows_config = self.job_config.get('flows', [])
        triggers_config = self.job_config.get('triggers', [])
        subjobs_dict = self._build_subjobs_dict()
        self.execution_plan = ExecutionPlan(
            components_config, flows_config, triggers_config, subjobs_dict or None
        )
        self.execution_plan.validate()
        for subjob_id in self.execution_plan.all_subjob_ids:
            plan = self.execution_plan.get_subjob_plan(subjob_id)
            self.trigger_manager.register_subjob(subjob_id, list(plan.component_ids))
        self.output_router = OutputRouter(flows_config, components_config)
        self.executor = Executor(
            self.components, self.execution_plan, self.output_router,
            self.trigger_manager, self.global_map,
        )

    def _initialize_components(self) -> None:
        """Initialize all components from configuration using REGISTRY."""
        for comp_config in self.job_config.get('components', []):
            comp_id = comp_config['id']
            comp_type = comp_config['type']
            comp_class = REGISTRY.get(comp_type)

            if not comp_class:
                logger.warning(f"Unknown component type: {comp_type}")
                continue
            component = comp_class(
                comp_id,
                comp_config.get('config', {}),
                self.global_map,
                self.context_manager
            )
            component.subjob_id = comp_config.get('subjob_id')
            component.is_subjob_start = comp_config.get('is_subjob_start', False)
            component.inputs = comp_config.get('inputs', [])
            component.outputs = comp_config.get('outputs', [])
            component.input_schema = comp_config.get('schema', {}).get('input', [])
            component.output_schema = comp_config.get('schema', {}).get('output', [])
            if self.java_bridge_manager:
                component.java_bridge = self.java_bridge_manager.bridge
            if self.python_routine_manager:
                component.python_routine_manager = self.python_routine_manager

            self.components[comp_id] = component

        logger.info(f"Initialized {len(self.components)} components for job '{self.job_name}'")

    def _initialize_triggers(self) -> None:
        """Initialize triggers from configuration."""
        for trigger in self.job_config.get('triggers', []):
            self.trigger_manager.add_trigger(
                trigger['type'],
                trigger.get('from_component') or trigger.get('from'),
                trigger.get('to_component') or trigger.get('to'),
                trigger.get('condition')
            )

        for comp_config in self.job_config.get('components', []):
            comp_id = comp_config['id']
            for trigger in comp_config.get('triggers', []):
                self.trigger_manager.add_trigger(
                    trigger['type'],
                    comp_id,
                    trigger.get('target_component') or trigger.get('to'),
                    trigger.get('condition')
                )

        logger.info(f"Initialized {len(self.trigger_manager.triggers)} triggers")

    def _build_subjobs_dict(self) -> dict:
        """Build subjobs dict from component configs."""
        subjobs: dict[str, list[str]] = {}
        for comp_config in self.job_config.get('components', []):
            subjob_id = comp_config.get('subjob_id')
            if subjob_id:
                if subjob_id not in subjobs:
                    subjobs[subjob_id] = []
                subjobs[subjob_id].append(comp_config['id'])
        return subjobs

    def execute(self) -> Dict[str, Any]:
        """Execute the ETL job. Delegates to Executor.execute_job()."""
        logger.info(f"Starting execution of job: {self.job_name}")

        try:
            stats = self.executor.execute_job()

            stats['job_name'] = self.job_name
            stats['global_map'] = self.global_map.get_all_stats()

            logger.info(f"Job completed in {stats.get('execution_time', 0):.2f} seconds")
            self._cleanup()

            return stats

        except Exception as e:
            logger.error(f"Job execution failed: {e}", exc_info=True)
            self._cleanup()

            return {
                'job_name': self.job_name,
                'status': 'error',
                'error': str(e),
                'execution_time': 0,
                'components_executed': len(self.executor.executed_components),
                'components_failed': len(self.executor.failed_components),
                'component_stats': self.executor.execution_stats,
            }

    def set_context_variable(self, name: str, value: Any) -> None:
        """Set or update a context variable."""
        self.context_manager.set(name, value)

        # Update all components
        for component in self.components.values():
            component.context_manager = self.context_manager

    def get_execution_stats(self) -> Dict[str, Any]:
        """Get detailed execution statistics."""
        return {
            'job_name': self.job_name,
            'components_executed': list(self.executor.executed_components),
            'components_failed': list(self.executor.failed_components),
            'component_stats': self.executor.execution_stats,
            'global_map': self.global_map.get_all(),
            'context': self.context_manager.get_all()
        }

    def _cleanup(self) -> None:
        """Cleanup resources including Java bridge."""
        if self.java_bridge_manager:
            logger.info("Shutting down Java bridge...")
            self.java_bridge_manager.stop()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self._cleanup()
        return False


def run_job(job_config_path: str, context_overrides: Dict[str, Any] = None) -> Dict[str, Any]:
    """Convenience function to run an ETL job."""
    with ETLEngine(job_config_path) as engine:
        if context_overrides:
            for name, value in context_overrides.items():
                logger.info(f"Setting context variable: {name} = {value}")
                engine.set_context_variable(name, value)

        return engine.execute()


if __name__ == '__main__':
    import sys

    logging.basicConfig(level=logging.INFO)

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Run ETL job with optional context overrides.')
    parser.add_argument('job_config', help='Path to the job configuration JSON file')
    parser.add_argument(
        '--context_param',
        action='append',
        help='Override context variables in the format KEY=VALUE. Can be used multiple times.',
    )
    args = parser.parse_args()

    # Parse context overrides
    context_overrides = {}
    if args.context_param:
        for param in args.context_param:
            if '=' in param:
                key, value = param.split('=', 1)
                context_overrides[key.strip()] = value.strip()
            else:
                logger.error(f"Invalid context_param format: {param}. Expected format is KEY=VALUE.")
                sys.exit(1)

    # Run the job with the provided configuration and context overrides
    stats = run_job(args.job_config, context_overrides)

    # Log execution statistics
    logger.info(json.dumps(stats, indent=2))
