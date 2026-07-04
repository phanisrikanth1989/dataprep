"""Job management routes -- upload, run, status, list."""
import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from src.v1.engine.engine import ETLEngine

logger = logging.getLogger(__name__)

router = APIRouter()

# Storage paths
JOBS_DIR = Path("data/jobs")
JOBS_DIR.mkdir(parents=True, exist_ok=True)

# In-memory run tracker  {run_id: {status, stats, error, ...}}
_runs: Dict[str, Dict[str, Any]] = {}
_runs_lock = threading.Lock()


# ── Request / Response models ────────────────────────────────────────────

class RunRequest(BaseModel):
    context_overrides: Dict[str, str] | None = None


class RunInlineRequest(BaseModel):
    job_config: Dict[str, Any]
    context_overrides: Dict[str, str] | None = None


# ── Upload ───────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_job(file: UploadFile = File(...)):
    """Upload a JSON job config file. Returns a job_id for later use."""
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json files are accepted")

    content = await file.read()
    try:
        job_config = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}")

    job_id = str(uuid.uuid4())
    job_path = JOBS_DIR / f"{job_id}.json"
    job_path.write_text(json.dumps(job_config, indent=2), encoding="utf-8")

    return {
        "job_id": job_id,
        "job_name": job_config.get("job_name", "unknown"),
        "filename": file.filename,
        "components_count": len(job_config.get("components", [])),
    }


# ── Run ──────────────────────────────────────────────────────────────────

def _execute_in_background(run_id: str, job_config: dict, context_overrides: dict | None):
    """Run ETL job in a background thread and update the run tracker."""
    with _runs_lock:
        _runs[run_id]["status"] = "running"
        _runs[run_id]["started_at"] = time.time()

    try:
        with ETLEngine(job_config) as engine:
            if context_overrides:
                for name, value in context_overrides.items():
                    engine.set_context_variable(name, value)
            stats = engine.execute()

        with _runs_lock:
            _runs[run_id]["status"] = stats.get("status", "success")
            _runs[run_id]["stats"] = _make_serializable(stats)
            _runs[run_id]["finished_at"] = time.time()

    except Exception as exc:
        logger.error("Run %s failed: %s", run_id, exc, exc_info=True)
        with _runs_lock:
            _runs[run_id]["status"] = "error"
            _runs[run_id]["error"] = str(exc)
            _runs[run_id]["finished_at"] = time.time()


@router.post("/{job_id}/run")
def run_job(job_id: str, body: RunRequest | None = None):
    """Run a previously uploaded job. Returns a run_id to poll for status."""
    job_path = JOBS_DIR / f"{job_id}.json"
    if not job_path.exists():
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    job_config = json.loads(job_path.read_text(encoding="utf-8"))
    context_overrides = body.context_overrides if body else None

    run_id = str(uuid.uuid4())
    with _runs_lock:
        _runs[run_id] = {
            "run_id": run_id,
            "job_id": job_id,
            "job_name": job_config.get("job_name", "unknown"),
            "status": "queued",
            "stats": None,
            "error": None,
            "started_at": None,
            "finished_at": None,
        }

    thread = threading.Thread(
        target=_execute_in_background,
        args=(run_id, job_config, context_overrides),
        daemon=True,
    )
    thread.start()

    return {"run_id": run_id, "job_id": job_id, "status": "queued"}


@router.post("/run-inline")
def run_inline(body: RunInlineRequest):
    """Run a job directly from a JSON payload (no upload needed)."""
    job_config = body.job_config
    context_overrides = body.context_overrides

    run_id = str(uuid.uuid4())
    with _runs_lock:
        _runs[run_id] = {
            "run_id": run_id,
            "job_id": None,
            "job_name": job_config.get("job_name", "unknown"),
            "status": "queued",
            "stats": None,
            "error": None,
            "started_at": None,
            "finished_at": None,
        }

    thread = threading.Thread(
        target=_execute_in_background,
        args=(run_id, job_config, context_overrides),
        daemon=True,
    )
    thread.start()

    return {"run_id": run_id, "status": "queued"}


# ── Status ───────────────────────────────────────────────────────────────

@router.get("/runs/{run_id}")
def get_run_status(run_id: str):
    """Poll the status/result of a job run."""
    with _runs_lock:
        run = _runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run


@router.get("/runs")
def list_runs():
    """List all runs (most recent first)."""
    with _runs_lock:
        all_runs = list(_runs.values())
    all_runs.sort(key=lambda r: r.get("started_at") or 0, reverse=True)
    return all_runs


# ── Job management ───────────────────────────────────────────────────────

@router.get("/")
def list_jobs():
    """List all uploaded job configs."""
    jobs = []
    for path in sorted(JOBS_DIR.glob("*.json")):
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
            jobs.append({
                "job_id": path.stem,
                "job_name": config.get("job_name", "unknown"),
                "components_count": len(config.get("components", [])),
            })
        except Exception:
            continue
    return jobs


@router.get("/{job_id}")
def get_job(job_id: str):
    """Get the full JSON config of an uploaded job."""
    job_path = JOBS_DIR / f"{job_id}.json"
    if not job_path.exists():
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return json.loads(job_path.read_text(encoding="utf-8"))


@router.delete("/{job_id}")
def delete_job(job_id: str):
    """Delete an uploaded job config."""
    job_path = JOBS_DIR / f"{job_id}.json"
    if not job_path.exists():
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    job_path.unlink()
    return {"deleted": job_id}


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_serializable(obj: Any) -> Any:
    """Convert non-serializable types (sets, etc.) for JSON response."""
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(v) for v in obj]
    if isinstance(obj, set):
        return list(obj)
    if isinstance(obj, float) and (obj != obj):  # NaN check
        return None
    return obj
