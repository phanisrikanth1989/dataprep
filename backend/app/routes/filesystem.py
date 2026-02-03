"""
Filesystem browser API routes
"""
from fastapi import APIRouter, HTTPException, Query
import logging
import os
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/filesystem", tags=["filesystem"])


class FileItem(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: Optional[int] = None
    modified: Optional[str] = None


class DirectoryListing(BaseModel):
    path: str
    parent: Optional[str]
    items: List[FileItem]
    drives: Optional[List[str]] = None


@router.get("/drives")
async def list_drives():
    """List available drives (Windows)"""
    try:
        import string
        drives = []
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                drives.append(drive)
        return {"drives": drives}
    except Exception as e:
        logger.error(f"Error listing drives: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/browse")
async def browse_directory(
    path: str = Query(default="C:\\", description="Directory path to browse"),
    show_files: bool = Query(default=True, description="Include files in listing"),
    file_filter: Optional[str] = Query(default=None, description="File extension filter (e.g., .csv,.txt)")
):
    """Browse a directory and list contents"""
    try:
        # Normalize path
        dir_path = Path(path)
        
        if not dir_path.exists():
            raise HTTPException(status_code=404, detail=f"Path not found: {path}")
        
        if not dir_path.is_dir():
            raise HTTPException(status_code=400, detail=f"Not a directory: {path}")

        items = []
        
        # Parse file filter
        extensions = None
        if file_filter:
            extensions = [ext.strip().lower() for ext in file_filter.split(",")]
            # Ensure extensions start with dot
            extensions = [ext if ext.startswith(".") else f".{ext}" for ext in extensions]

        try:
            for entry in sorted(dir_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                try:
                    is_dir = entry.is_dir()
                    
                    # Skip files if show_files is False
                    if not is_dir and not show_files:
                        continue
                    
                    # Apply file filter
                    if not is_dir and extensions:
                        if entry.suffix.lower() not in extensions:
                            continue
                    
                    stat_info = entry.stat()
                    items.append(FileItem(
                        name=entry.name,
                        path=str(entry),
                        is_dir=is_dir,
                        size=stat_info.st_size if not is_dir else None,
                        modified=str(stat_info.st_mtime)
                    ))
                except PermissionError:
                    # Skip files/folders we can't access
                    continue
                except Exception as e:
                    logger.warning(f"Error reading {entry}: {e}")
                    continue
        except PermissionError:
            raise HTTPException(status_code=403, detail=f"Permission denied: {path}")

        # Get parent path
        parent = str(dir_path.parent) if dir_path.parent != dir_path else None

        # Get drives for Windows
        drives = None
        if os.name == 'nt':
            import string
            drives = [f"{letter}:\\" for letter in string.ascii_uppercase if os.path.exists(f"{letter}:\\")]

        return DirectoryListing(
            path=str(dir_path),
            parent=parent,
            items=items,
            drives=drives
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error browsing directory {path}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-directory")
async def create_directory(path: str = Query(..., description="Directory path to create")):
    """Create a new directory"""
    try:
        dir_path = Path(path)
        dir_path.mkdir(parents=True, exist_ok=True)
        return {"success": True, "path": str(dir_path)}
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"Permission denied: {path}")
    except Exception as e:
        logger.error(f"Error creating directory {path}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/exists")
async def check_exists(path: str = Query(..., description="Path to check")):
    """Check if a path exists"""
    try:
        p = Path(path)
        return {
            "exists": p.exists(),
            "is_dir": p.is_dir() if p.exists() else False,
            "is_file": p.is_file() if p.exists() else False,
            "path": str(p)
        }
    except Exception as e:
        logger.error(f"Error checking path {path}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
