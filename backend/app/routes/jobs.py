"""
Job management API routes
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List
import logging
from app.models import JobSchema, JobNode, JobEdge
from app.services.job_service import JobService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jobs", tags=["jobs"])

# Initialize job service
job_service = JobService("jobs")


@router.get("")
async def list_jobs():
    """List all jobs"""
    try:
        jobs = job_service.list_jobs()
        return [
            {
                "id": job.id,
                "name": job.name,
                "description": job.description,
                "node_count": len(job.nodes),
                "edge_count": len(job.edges),
                "created_at": job.created_at,
                "updated_at": job.updated_at,
            }
            for job in jobs
        ]
    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}")
async def get_job(job_id: str):
    """Get job details"""
    try:
        job = job_service.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_job(job_data: JobSchema):
    """Create new job"""
    try:
        created_job = job_service.create_job(job_data)
        return created_job
    except Exception as e:
        logger.error(f"Error creating job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{job_id}")
async def update_job(job_id: str, job_data: JobSchema):
    """Update job"""
    try:
        updated_job = job_service.update_job(job_id, job_data)
        if not updated_job:
            raise HTTPException(status_code=404, detail="Job not found")
        return updated_job
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{job_id}")
async def delete_job(job_id: str):
    """Delete job"""
    try:
        success = job_service.delete_job(job_id)
        if not success:
            raise HTTPException(status_code=404, detail="Job not found")
        return {"message": "Job deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}/export")
async def export_job_config(job_id: str):
    """Export job as ETL engine config (JSON)"""
    try:
        config = job_service.export_job_config(job_id)
        if not config:
            raise HTTPException(status_code=404, detail="Job not found")
        return config
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
