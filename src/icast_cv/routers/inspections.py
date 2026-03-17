"""Inspection endpoints — create, query, and receive CV results."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from icast_cv.crud.inspection_crud import (
    create_inspection,
    get_inspection,
    list_all_inspections,
    list_inspections_by_sample,
    update_inspection_result,
)
from icast_cv.db import get_database
from icast_cv.exceptions import NotFoundError
from icast_cv.models.inspection import (
    InspectionCreate,
    InspectionResponse,
    InspectionResult,
)

router = APIRouter(tags=["inspections"])

DB = Annotated[AsyncIOMotorDatabase, Depends(get_database)]  # type: ignore[type-arg]


@router.post("/inspections", response_model=InspectionResponse, status_code=201)
async def create_inspection_endpoint(
    data: InspectionCreate,
    db: DB,
) -> dict[str, Any]:
    """Create a new inspection request (status=pending)."""
    inspection = await create_inspection(db, data)
    return inspection.model_dump()


@router.get("/inspections/{inspection_id}", response_model=InspectionResponse)
async def get_inspection_endpoint(
    inspection_id: str,
    db: DB,
) -> dict[str, Any]:
    """Get a single inspection by ID."""
    try:
        inspection = await get_inspection(db, inspection_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return inspection.model_dump()


@router.get("/inspections", response_model=list[InspectionResponse])
async def list_inspections_endpoint(
    db: DB,
    sample_id: str | None = None,
    cartridge_id: str | None = None,
    phase: str | None = None,
    result: str | None = None,
    project_id: str | None = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict[str, Any]]:
    """List inspections with optional filters."""
    inspections = await list_all_inspections(
        db,
        sample_id=sample_id,
        cartridge_id=cartridge_id,
        phase=phase,
        result=result,
        project_id=project_id,
        skip=skip,
        limit=limit,
    )
    return [i.model_dump() for i in inspections]


@router.get("/inspections/{inspection_id}/poll", response_model=InspectionResponse)
async def poll_inspection(
    inspection_id: str,
    db: DB,
) -> dict[str, Any]:
    """Poll for inspection result. Returns current state (check status field)."""
    try:
        inspection = await get_inspection(db, inspection_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return inspection.model_dump()


@router.post(
    "/inspections/{inspection_id}/result",
    response_model=InspectionResponse,
)
async def post_inspection_result(
    inspection_id: str,
    data: InspectionResult,
    db: DB,
) -> dict[str, Any]:
    """Webhook for CV worker to post inspection results."""
    try:
        inspection = await update_inspection_result(db, inspection_id, data)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return inspection.model_dump()
