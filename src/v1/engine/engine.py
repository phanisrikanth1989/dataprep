"""Main ETL Engine -- thin orchestrator delegating to Executor, ExecutionPlan, OutputRouter.

Backward-compatible API: ETLEngine, run_job(), CLI entry point preserved.
"""
import json
import logging
from typing import Dict, Any
import argparse

from .global_map import GlobalMap
from .context_manager import ContextManager
from .trigger_manager import TriggerManager
from .base_component import BaseComponent
from .exceptions import ETLError
from .java_bridge_manager import JavaBridgeManager
from .python_routine_manager import PythonRoutineManager
from .oracle_connection_manager import OracleConnectionManager
from .mssql_connection_manager import MSSqlConnectionManager
from .component_registry import REGISTRY
from . import components as _components  # noqa: F401 -- triggers decorator registration
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
            routine_jars = java_config.get('routine_jars', [])
            self.java_bridge_manager = JavaBridgeManager(
                enable=True, routines=routines, libraries=libraries, routine_jars=routine_jars
            )
            try:
                self.java_bridge_manager.start()
            except Exception:
                self.java_bridge_manager.stop()
                raise
            logger.info("Java bridge initialized with %d routines, %d libraries, %d routine JARs",
                        len(routines), len(libraries), len(routine_jars))

        # Python routine manager
        self.python_routine_manager = None
        python_config = self.job_config.get('python_config', {})
        if python_config.get('enabled', False):
            routines_dir = python_config.get('routines_dir', 'src/python_routines')
            required_routines = python_config.get('routines', [])
            self.python_routine_manager = PythonRoutineManager(
                routines_dir, required_routines=required_routines or None
            )
            logger.info("Python routine manager initialized from %s", routines_dir)

        # Oracle connection manager (D-A1, D-A2, D-A4b)
        self.oracle_manager = None
        oracle_config = self.job_config.get('oracle_config', {})
        # Auto-detect Oracle components in the job config
        oracle_component_types = {
            "OracleConnection", "tOracleConnection", "tDBConnection",
            "OracleRow", "tOracleRow",
            "OracleOutput", "tOracleOutput",
            "OracleInput", "tOracleInput",
            "OracleSP", "tOracleSP",
            "OracleBulkExec", "tOracleBulkExec",
            "OracleCommit", "tOracleCommit",
            "OracleRollback", "tOracleRollback",
            "OracleClose", "tOracleClose",
        }
        has_oracle_components = any(
            c.get('type') in oracle_component_types
            for c in self.job_config.get('components', [])
        )
        if has_oracle_components or oracle_config.get('enabled', False):
            thick_mode = bool(oracle_config.get('thick_mode', False))
            self.oracle_manager = OracleConnectionManager(thick_mode=thick_mode)
            try:
                self.oracle_manager.start()
            except Exception:
                self.oracle_manager.stop()
                raise
            logger.info("Oracle connection manager initialized (thick_mode=%s)", thick_mode)

        # MSSql connection manager (parallel to Oracle; pyodbc driver)
        self.mssql_manager = None
        mssql_config = self.job_config.get('mssql_config', {})
        mssql_component_types = {
            "MSSqlConnection", "tMSSqlConnection",
            "MSSqlInput", "tMSSqlInput",
        }
        has_mssql_components = any(
            c.get('type') in mssql_component_types
            for c in self.job_config.get('components', [])
        )
        if has_mssql_components or mssql_config.get('enabled', False):
            self.mssql_manager = MSSqlConnectionManager()
            try:
                self.mssql_manager.start()
            except Exception:
                self.mssql_manager.stop()
                raise
            logger.info("MSSql connection manager initialized")

        # Core services
        self.job_name = self.job_config.get('job_name', 'unnamed_job')
        self.global_map = GlobalMap()
        self.context_manager = ContextManager(
            initial_context=self.job_config.get('context', {}),
            default_context=self.job_config.get('default_context', 'Default'),
            java_bridge_manager=self.java_bridge_manager
        )
        # Pass context_manager to TriggerManager for evaluating trigger conditions so that 
        #Run If triggers can access context variables.
        #Converter phase 7.1: context_manager is now passed to TriggerManager for evaluating trigger conditions.
        #placeholders are resolved using context_manager.get() instead of global_map.get(), allowing for dynamic context variable evaluation.
        self.trigger_manager = TriggerManager(self.global_map, self.context_manager)

        self.components: Dict[str, BaseComponent] = {}
        self._initialize_components()
        self._initialize_triggers()

        # Build execution plan, output router, executor
        components_config = self.job_config.get('components', [])
        flows_config = self.job_config.get('flows', [])
        triggers_config = self.job_config.get('triggers', [])
        subjobs_dict = self._build_subjobs_dict()
        # Empty dict (no components have subjob_id) -> None triggers auto-detection
        self.execution_plan = ExecutionPlan(
            components_config, flows_config, triggers_config, subjobs_dict or None
        )
        self.execution_plan.validate()
        for subjob_id in self.execution_plan.all_subjob_ids:
            plan = self.execution_plan.get_subjob_plan(subjob_id)
            self.trigger_manager.register_subjob(subjob_id, list(plan.component_ids))
        self.output_router = OutputRouter(flows_config, components_config)
        # D-H6: read iterate log threshold from job_config["engine_config"]["iterate"]
        from .iterate_logging import DEFAULT_LOG_PER_ITER_THRESHOLD
        engine_cfg = self.job_config.get("engine_config", {})
        iterate_log_threshold = (
            engine_cfg.get("iterate", {}).get(
                "log_per_iter_threshold", DEFAULT_LOG_PER_ITER_THRESHOLD
            )
        )
        self.executor = Executor(
            self.components, self.execution_plan, self.output_router,
            self.trigger_manager, self.global_map,
            iterate_log_threshold=iterate_log_threshold,
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
            component.reject_schema = comp_config.get('schema', {}).get('reject', [])
            # ENG-CR-04 CONSUMER: per-flow schema map for multi-input components (tMap, etc.)
            # Populated by converter _propagate_input_schemas (Phase 7.1 producer fix).
            # Multi-input components read component.schema_inputs_map[flow_name] for
            # the per-connector schema; falls back gracefully if not present (old configs).
            component.schema_inputs_map = comp_config.get('schema', {}).get('inputs', {})
            if self.java_bridge_manager:
                component.java_bridge = self.java_bridge_manager.bridge
            if self.python_routine_manager:
                component.python_routine_manager = self.python_routine_manager
            if self.oracle_manager:
                component.oracle_manager = self.oracle_manager
            if self.mssql_manager:
                component.mssql_manager = self.mssql_manager

            self.components[comp_id] = component

        logger.info(f"Initialized {len(self.components)} components for job '{self.job_name}'")

    def _initialize_triggers(self) -> None:
        """Initialize triggers from configuration."""
        for trigger in self.job_config.get('triggers', []):
            self.trigger_manager.add_trigger(
                trigger['type'],
                trigger.get('from_component') or trigger.get('from'),
                trigger.get('to_component') or trigger.get('to'),
                trigger.get('condition'),
                output_id=int(trigger.get('output_id', 0) or 0),
            )

        for comp_config in self.job_config.get('components', []):
            comp_id = comp_config['id']
            for trigger in comp_config.get('triggers', []):
                self.trigger_manager.add_trigger(
                    trigger['type'],
                    comp_id,
                    trigger.get('target_component') or trigger.get('to'),
                    trigger.get('condition'),
                    output_id=int(trigger.get('output_id', 0) or 0),
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
        """Cleanup resources including Java bridge and database connections."""
        if self.java_bridge_manager:
            logger.info("Shutting down Java bridge...")
            self.java_bridge_manager.stop()
        if self.oracle_manager:
            logger.info("Closing Oracle connections...")
            self.oracle_manager.stop()
        if self.mssql_manager:
            logger.info("Closing MSSql connections...")
            self.mssql_manager.stop()

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
