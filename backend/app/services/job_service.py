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

    def _transform_map_config(self, config: dict, component_id: str, flows: list) -> dict:
        """Transform frontend Map config to backend expected format.
        
        Frontend sends:
        {
            "mappings": [{"sourceColumn": "col1", "targetColumn": "out1", "expression": "", "dataType": "string"}, ...],
            "output_schema": [{"name": "out1", "type": "string"}, ...]
        }
        
        Backend expects:
        {
            "inputs": {"main": {"name": "main"}, "lookups": []},
            "outputs": [{"name": "out", "columns": [{"name": "out1", "expression": "main.col1"}, ...]}],
            "variables": []
        }
        """
        mappings = config.get("mappings", [])
        
        # Find the input flow name for this component
        main_input_name = "main"
        for flow in flows:
            if flow.get("to") == component_id:
                # Use the flow name or source component as the table name
                main_input_name = flow.get("name", flow.get("from", "main"))
                break
        
        # Build output columns from mappings
        output_columns = []
        for mapping in mappings:
            source = mapping.get("sourceColumn", "")
            target = mapping.get("targetColumn", "")
            expression = mapping.get("expression", "")
            data_type = mapping.get("dataType", "string")
            
            if not target:
                continue
                
            # Build expression: if custom expression provided use it, otherwise use source column reference
            if expression:
                # Use custom expression as-is
                col_expr = expression
            elif source:
                # Simple column copy: reference source column from main input
                col_expr = f"{main_input_name}.{source}"
            else:
                col_expr = ""
            
            output_columns.append({
                "name": target,
                "expression": col_expr,
                "type": data_type,
            })
        
        return {
            "inputs": {
                "main": {"name": main_input_name},
                "lookups": []
            },
            "outputs": [
                {
                    "name": "out",
                    "columns": output_columns
                }
            ],
            "variables": []
        }

    def export_job_config(self, job_id: str) -> Optional[dict]:
        """Export job as ETL engine config"""
        job = self.get_job(job_id)
        if not job:
            return None

        # Build flows first (needed for Map config transformation)
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

        # Convert UI format to ETL engine format
        components = []
        for node in job.nodes:
            node_config = node.config or {}
            
            # Transform Map component config from frontend format to backend format
            if node.type == "Map" and "mappings" in node_config:
                node_config = self._transform_map_config(node_config, node.id, flows)
            
            comp = {
                "id": node.id,
                "type": node.type,
                "subjob_id": node.subjob_id or "subjob_0",
                "is_subjob_start": node.is_subjob_start,
                "config": node_config,
            }
            components.append(comp)

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
