"""
Component metadata API routes
"""
from fastapi import APIRouter, HTTPException
import logging
from app.schemas import list_components, get_component_metadata

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/components", tags=["components"])


@router.get("")
async def list_all_components():
    """List all available components grouped by category"""
    try:
        return list_components()
    except Exception as e:
        logger.error(f"Error listing components: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{component_type}")
async def get_component(component_type: str):
    """Get metadata for a specific component type"""
    try:
        metadata = get_component_metadata(component_type)
        return metadata
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting component {component_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
