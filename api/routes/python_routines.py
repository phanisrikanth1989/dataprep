"""Python routine management routes -- list, read, create, update, delete."""
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# Path
_ROUTINES_DIR = Path("src/python_routines")

# Allowed filename pattern -- alphanumeric + underscore, must end with .py
_VALID_FILENAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*\.py$")


# ── Request / Response models ────────────────────────────────────────────

class RoutineCreateRequest(BaseModel):
    filename: str
    content: str


class RoutineUpdateRequest(BaseModel):
    content: str


# ── Helpers ──────────────────────────────────────────────────────────────

def _validate_filename(filename: str) -> None:
    """Raise 400 if filename is not a safe .py name."""
    if not _VALID_FILENAME.match(filename):
        raise HTTPException(
            status_code=400,
            detail="Invalid filename. Must start with a letter, contain only "
                   "alphanumerics/underscores, and end with .py",
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
    """List all Python routine files."""
    if not _ROUTINES_DIR.exists():
        return []
    files = sorted(
        p for p in _ROUTINES_DIR.iterdir()
        if p.is_file() and p.suffix == ".py" and p.name != "__init__.py"
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
    """Create a new Python routine file. Fails if the file already exists."""
    _validate_filename(body.filename)
    path = _routine_path(body.filename)
    if path.exists():
        raise HTTPException(
            status_code=409,
            detail=f"Routine '{body.filename}' already exists. Use PUT to update.",
        )
    _ROUTINES_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(body.content, encoding="utf-8")
    logger.info("Created Python routine %s", body.filename)
    return {"saved": True, **_routine_info(path)}


@router.put("/{filename}")
def update_routine(filename: str, body: RoutineUpdateRequest) -> Dict[str, Any]:
    """Overwrite an existing Python routine file."""
    _validate_filename(filename)
    path = _routine_path(filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Routine '{filename}' not found")
    path.write_text(body.content, encoding="utf-8")
    logger.info("Updated Python routine %s", filename)
    return {"updated": True, **_routine_info(path)}


@router.delete("/{filename}")
def delete_routine(filename: str) -> Dict[str, Any]:
    """Delete a Python routine file."""
    _validate_filename(filename)
    path = _routine_path(filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Routine '{filename}' not found")
    path.unlink()
    logger.info("Deleted Python routine %s", filename)
    return {"deleted": True, "filename": filename}
