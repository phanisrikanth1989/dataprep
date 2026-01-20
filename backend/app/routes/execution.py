"""
Job execution API routes
"""
from fastapi import APIRouter, HTTPException, WebSocket
import logging
import uuid
from typing import Optional
from app.models import ExecutionRequest, ExecutionUpdate
from app.services.execution_service import execution_manager
from app.services.job_service import JobService
import json
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/execution", tags=["execution"])

job_service = JobService("jobs")


@router.post("/start")
async def start_execution(request: ExecutionRequest):
    """Start job execution"""
    try:
        # Validate job exists
        job = job_service.get_job(request.job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Generate task ID
        task_id = f"task_{uuid.uuid4().hex[:8]}"

        # Create execution tracking
        execution_manager.create_execution(request.job_id, task_id)

        # Export job config
        job_config = job_service.export_job_config(request.job_id)

        # Start execution in background
        asyncio.create_task(
            execution_manager.execute_job(
                task_id, job_config, request.context_overrides
            )
        )

        return {
            "task_id": task_id,
            "job_id": request.job_id,
            "status": "started",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting execution: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{task_id}")
async def get_execution_status(task_id: str):
    """Get execution status"""
    try:
        execution = execution_manager.get_execution(task_id)
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")
        return execution
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting execution {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{task_id}/stop")
async def stop_execution(task_id: str):
    """Stop job execution"""
    try:
        execution = execution_manager.get_execution(task_id)
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")

        if execution.status in ["success", "error"]:
            raise HTTPException(status_code=400, detail="Execution already completed")

        # TODO: Implement actual job stopping mechanism
        execution_manager.update_execution(
            task_id,
            status="error",
            error_message="Execution stopped by user",
        )

        return {"message": "Execution stopped"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping execution {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Active WebSocket connections
active_connections: dict = {}


@router.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for real-time execution updates"""
    await websocket.accept()
    active_connections[task_id] = websocket

    try:
        # Send initial status
        execution = execution_manager.get_execution(task_id)
        if execution:
            await websocket.send_json(
                {
                    "type": "status",
                    "data": execution.model_dump(),
                    "timestamp": execution.started_at or "",
                }
            )

        # Send periodic updates
        while task_id in active_connections:
            execution = execution_manager.get_execution(task_id)
            if execution:
                await websocket.send_json(
                    {
                        "type": "update",
                        "data": execution.model_dump(),
                    }
                )

                # If execution completed, close after final update
                if execution.status in ["success", "error"]:
                    await websocket.send_json(
                        {
                            "type": "complete",
                            "data": execution.model_dump(),
                        }
                    )
                    break

            await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"WebSocket error for {task_id}: {e}")
    finally:
        if task_id in active_connections:
            del active_connections[task_id]
        try:
            await websocket.close()
        except:
            pass
