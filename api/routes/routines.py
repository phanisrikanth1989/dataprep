"""Java routine management routes -- list, read, create, update, delete, build."""
import logging
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# Paths
_ROUTINES_DIR = Path("src/v1/java_bridge/java/src/main/java/routines")
_BRIDGE_DIR = Path("src/v1/java_bridge/java")

# Allowed filename pattern -- alphanumeric + underscore, must end with .java
_VALID_FILENAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*\.java$")


# ── Request / Response models ────────────────────────────────────────────

class RoutineCreateRequest(BaseModel):
    filename: str
    content: str


class RoutineUpdateRequest(BaseModel):
    content: str


# ── Helpers ──────────────────────────────────────────────────────────────

def _validate_filename(filename: str) -> None:
    """Raise 400 if filename is not a safe .java name."""
    if not _VALID_FILENAME.match(filename):
        raise HTTPException(
            status_code=400,
            detail="Invalid filename. Must start with a letter, contain only "
                   "alphanumerics/underscores, and end with .java",
        )


def _routine_path(filename: str) -> Path:
    """Return the absolute path for a routine file."""
    return _ROUTINES_DIR / filename


def _routine_info(path: Path) -> Dict[str, Any]:
    """Return metadata dict for a routine file."""
    stat = path.stat()
    return {
        "filename": path.name,
        "name": path.stem,
        "size_bytes": stat.st_size,
        "last_modified": datetime.utcfromtimestamp(stat.st_mtime).isoformat() + "Z",
    }


# ── Routes ───────────────────────────────────────────────────────────────

@router.get("")
def list_routines() -> List[Dict[str, Any]]:
    """List all Java routine files."""
    if not _ROUTINES_DIR.exists():
        return []
    files = sorted(
        p for p in _ROUTINES_DIR.iterdir()
        if p.is_file() and p.suffix == ".java"
    )
    return [_routine_info(f) for f in files]


@router.get("/{filename}")
def get_routine(filename: str) -> Dict[str, Any]:
    """Return the source content of a single routine file."""
    _validate_filename(filename)
    path = _routine_path(filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Routine '{filename}' not found")
    return {
        **_routine_info(path),
        "content": path.read_text(encoding="utf-8"),
    }


@router.post("")
def create_routine(body: RoutineCreateRequest) -> Dict[str, Any]:
    """Create a new Java routine file. Fails if the file already exists."""
    _validate_filename(body.filename)
    path = _routine_path(body.filename)
    if path.exists():
        raise HTTPException(
            status_code=409,
            detail=f"Routine '{body.filename}' already exists. Use PUT to update.",
        )
    _ROUTINES_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(body.content, encoding="utf-8")
    logger.info("Created routine %s", body.filename)
    return {"saved": True, **_routine_info(path)}


@router.put("/{filename}")
def update_routine(filename: str, body: RoutineUpdateRequest) -> Dict[str, Any]:
    """Overwrite an existing Java routine file."""
    _validate_filename(filename)
    path = _routine_path(filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Routine '{filename}' not found")
    path.write_text(body.content, encoding="utf-8")
    logger.info("Updated routine %s", filename)
    return {"updated": True, **_routine_info(path)}


@router.delete("/{filename}")
def delete_routine(filename: str) -> Dict[str, Any]:
    """Delete a Java routine file."""
    _validate_filename(filename)
    path = _routine_path(filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Routine '{filename}' not found")
    path.unlink()
    logger.info("Deleted routine %s", filename)
    return {"deleted": True, "filename": filename}


@router.post("/build")
def build_routines() -> StreamingResponse:
    """Run mvn package and stream the build output line by line (SSE)."""

    def _stream():
        yield "data: Starting Maven build...\n\n"
        try:
            process = subprocess.Popen(
                ["mvn", "package", "-q", "--no-transfer-progress"],
                cwd=str(_BRIDGE_DIR.resolve()),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env={**os.environ},
            )
            for line in (process.stdout or []):
                yield f"data: {line.rstrip()}\n\n"
            process.wait()
            if process.returncode == 0:
                yield "data: BUILD SUCCESS\n\n"
                yield "data: [done] exit_code=0\n\n"
            else:
                yield f"data: BUILD FAILED (exit code {process.returncode})\n\n"
                yield f"data: [done] exit_code={process.returncode}\n\n"
        except FileNotFoundError:
            yield "data: ERROR: mvn not found on PATH. Install Maven and retry.\n\n"
            yield "data: [done] exit_code=1\n\n"
        except Exception as exc:
            yield f"data: ERROR: {exc}\n\n"
            yield "data: [done] exit_code=1\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
