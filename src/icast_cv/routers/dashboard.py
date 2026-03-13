"""Dashboard statistics endpoint."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from icast_cv.crud.inspection_crud import get_inspection_stats
from icast_cv.db import get_database

router = APIRouter(tags=["dashboard"])

DB = Annotated[AsyncIOMotorDatabase, Depends(get_database)]


@router.get("/dashboard/stats")
async def dashboard_stats(db: DB) -> dict[str, Any]:
    """Aggregate stats for the dashboard."""
    return await get_inspection_stats(db)
