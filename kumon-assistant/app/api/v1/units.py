"""
Units API endpoints for managing Kumon centers/units
"""
from fastapi import APIRouter, HTTPException, Path, Query
from typing import List

from app.models.unit import CreateUnitRequest, UpdateUnitRequest, UnitResponse
from app.services.unit_manager import unit_manager
from app.core.logger import app_logger

router = APIRouter()


@router.post("/units", response_model=UnitResponse)
async def create_unit(request: CreateUnitRequest):
    """Create a new Kumon unit"""
    try:
        unit = unit_manager.create_unit(request)
        app_logger.info(f"Created unit: {unit.user_id} - {unit.username}")
        return unit
    except Exception as e:
        app_logger.error(f"Error creating unit: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create unit")


@router.get("/units", response_model=List[UnitResponse])
async def list_units(active_only: bool = Query(True, description="Only return active units")):
    """List all Kumon units"""
    return unit_manager.list_units(active_only=active_only)


@router.get("/units/{user_id}", response_model=UnitResponse)
async def get_unit(user_id: str = Path(..., description="User ID")):
    """Get a specific unit by ID"""
    unit = unit_manager.get_unit(user_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    
    return UnitResponse(
        user_id=unit.config.user_id,
        username=unit.config.username,
        address=unit.config.address,
        phone=unit.config.phone,
        is_active=unit.config.is_active,
        created_at=unit.config.created_at,
        updated_at=unit.config.updated_at
    )


@router.put("/units/{user_id}", response_model=UnitResponse)
async def update_unit(
    request: UpdateUnitRequest,
    user_id: str = Path(..., description="User ID")
):
    """Update a specific unit"""
    result = unit_manager.update_unit(user_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Unit not found")
    return result


@router.delete("/units/{user_id}")
async def delete_unit(user_id: str = Path(..., description="User ID")):
    """Delete (deactivate) a specific unit"""
    if not unit_manager.delete_unit(user_id):
        raise HTTPException(status_code=404, detail="Unit not found")
    return {"message": "Unit deactivated successfully"}


@router.get("/units/{user_id}/context")
async def get_unit_context(user_id: str = Path(..., description="User ID")):
    """Get unit context for AI responses"""
    unit = unit_manager.get_unit(user_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    
    return unit_manager.get_unit_context(user_id) 