"""
Job service for CRUD operations
"""
import json
import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from app.models import JobSchema

logger = logging.getLogger(__name__)


class JobService:
    """Service for managing job configurations"""

    def __init__(self, jobs_dir: str = "jobs"):
        self.jobs_dir = Path(jobs_dir)
        self.jobs_dir.mkdir(exist_ok=True)

    def _get_job_path(self, job_id: str) -> Path:
        """Get file path for a job"""
        return self.jobs_dir / f"{job_id}.json"

    def create_job(self, job: JobSchema) -> JobSchema:
        """Create a new job"""
        job.created_at = datetime.utcnow().isoformat()
        job.updated_at = job.created_at

        job_path = self._get_job_path(job.id)
        with open(job_path, "w") as f:
            f.write(job.model_dump_json(indent=2))

        logger.info(f"Created job: {job.id}")
        return job

    def get_job(self, job_id: str) -> Optional[JobSchema]:
        """Get a job by ID"""
        job_path = self._get_job_path(job_id)

        if not job_path.exists():
            logger.warning(f"Job not found: {job_id}")
            return None

        with open(job_path) as f:
            data = json.load(f)
        return JobSchema(**data)

    def list_jobs(self) -> List[JobSchema]:
        """List all jobs"""
        jobs = []
        for job_file in self.jobs_dir.glob("*.json"):
            try:
                with open(job_file) as f:
                    data = json.load(f)
                jobs.append(JobSchema(**data))
            except Exception as e:
                logger.error(f"Error loading job {job_file}: {e}")
        return jobs

    def update_job(self, job_id: str, job: JobSchema) -> Optional[JobSchema]:
        """Update an existing job"""
        existing = self.get_job(job_id)
        if not existing:
            logger.warning(f"Job not found for update: {job_id}")
            return None

        job.id = job_id
        job.created_at = existing.created_at
        job.updated_at = datetime.utcnow().isoformat()

        job_path = self._get_job_path(job_id)
        with open(job_path, "w") as f:
            f.write(job.model_dump_json(indent=2))

        logger.info(f"Updated job: {job_id}")
        return job

    def delete_job(self, job_id: str) -> bool:
        """Delete a job"""
        job_path = self._get_job_path(job_id)

        if not job_path.exists():
            logger.warning(f"Job not found for deletion: {job_id}")
            return False

        job_path.unlink()
        logger.info(f"Deleted job: {job_id}")
        return True

    def export_job_config(self, job_id: str) -> Optional[dict]:
        """Export job as ETL engine config"""
        job = self.get_job(job_id)
        if not job:
            return None

        # Convert UI format to ETL engine format
        components = []
        for node in job.nodes:
            comp = {
                "id": node.id,
                "type": node.type,
                "subjob_id": node.subjob_id or "subjob_0",
                "is_subjob_start": node.is_subjob_start,
                "config": node.config,
            }
            components.append(comp)

        flows = []
        for edge in job.edges:
            if edge.edge_type == "flow":
                flow = {
                    "from": edge.source,
                    "to": edge.target,
                    "type": "flow",
                    "name": edge.name or f"{edge.source}_to_{edge.target}",
                }
                flows.append(flow)

        triggers = []
        for edge in job.edges:
            if edge.edge_type == "trigger":
                trigger = {
                    "type": edge.trigger_type or "OnComponentOK",
                    "from_component": edge.source,
                    "to_component": edge.target,
                    "condition": edge.condition,
                }
                triggers.append(trigger)

        # Build ETL config
        config = {
            "job_name": job.name,
            "description": job.description,
            "default_context": "Default",
            "context": {
                "Default": {
                    k: {"value": v, "type": "id_String"}
                    for k, v in (job.context or {}).items()
                }
            },
            "java_config": job.java_config,
            "python_config": job.python_config,
            "components": components,
            "flows": flows,
            "triggers": triggers,
        }

        return config
