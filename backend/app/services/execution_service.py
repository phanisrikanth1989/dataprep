"""
Job execution service
"""
import logging
import asyncio
import time
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from app.models import ExecutionStatus, ExecutionUpdate
import json
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))


class ExecutionManager:
    """Manages job executions"""

    def __init__(self):
        self.executions: Dict[str, Dict[str, Any]] = {}
        self.callbacks: Dict[str, list] = {}  # task_id -> [callback functions]

    def create_execution(self, job_id: str, task_id: str) -> ExecutionStatus:
        """Create new execution tracking"""
        execution = ExecutionStatus(
            task_id=task_id,
            job_id=job_id,
            status="pending",
            started_at=datetime.utcnow().isoformat(),
        )
        self.executions[task_id] = execution.model_dump()
        self.callbacks[task_id] = []
        return execution

    def get_execution(self, task_id: str) -> Optional[ExecutionStatus]:
        """Get execution status"""
        if task_id not in self.executions:
            return None
        return ExecutionStatus(**self.executions[task_id])

    def update_execution(self, task_id: str, **kwargs) -> Optional[ExecutionStatus]:
        """Update execution status"""
        if task_id not in self.executions:
            return None

        self.executions[task_id].update(kwargs)
        execution = ExecutionStatus(**self.executions[task_id])

        # Notify subscribers
        for callback in self.callbacks[task_id]:
            try:
                callback(execution)
            except Exception as e:
                logger.error(f"Error calling execution callback: {e}")

        return execution

    def subscribe(self, task_id: str, callback: Callable):
        """Subscribe to execution updates"""
        if task_id not in self.callbacks:
            self.callbacks[task_id] = []
        self.callbacks[task_id].append(callback)

    async def execute_job(
        self,
        task_id: str,
        job_config: dict,
        context_overrides: Optional[dict] = None,
    ) -> ExecutionStatus:
        """Execute a job (async)"""
        try:
            self.update_execution(task_id, status="running")

            # Import ETL engine
            from v1.engine.engine import ETLEngine

            # Merge context overrides
            if context_overrides:
                if "context" not in job_config:
                    job_config["context"] = {"Default": {}}
                job_config["context"]["Default"].update(context_overrides)

            # Create and execute engine
            with ETLEngine(job_config) as engine:
                # Execute job
                stats = engine.execute()

                # Update execution with stats
                self.update_execution(
                    task_id,
                    status="success",
                    stats=stats,
                    completed_at=datetime.utcnow().isoformat(),
                )

                logger.info(f"Job {task_id} completed successfully")
                return self.get_execution(task_id)

        except Exception as e:
            logger.error(f"Job execution failed: {e}", exc_info=True)
            self.update_execution(
                task_id,
                status="error",
                error_message=str(e),
                completed_at=datetime.utcnow().isoformat(),
            )
            return self.get_execution(task_id)


# Global execution manager
execution_manager = ExecutionManager()
