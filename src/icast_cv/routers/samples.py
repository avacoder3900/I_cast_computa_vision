"""Sample CRUD endpoints."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from icast_cv.crud.sample_crud import (
    create_sample,
    delete_sample,
    get_sample,
    list_samples,
    update_sample,
)
from icast_cv.db import get_database
from icast_cv.exceptions import NotFoundError
from icast_cv.models.sample import SampleCreate, SampleResponse, SampleUpdate

router = APIRouter(tags=["samples"])

DB = Annotated[AsyncIOMotorDatabase, Depends(get_database)]  # type: ignore[type-arg]


@router.post("/samples", response_model=SampleResponse, status_code=201)
async def create_sample_endpoint(
    data: SampleCreate,
    db: DB,
) -> dict[str, Any]:
    """Create a new sample."""
    sample = await create_sample(db, data)
    return sample.model_dump()


@router.get("/samples", response_model=list[SampleResponse])
async def list_samples_endpoint(
    db: DB,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict[str, Any]]:
    """List samples with pagination."""
    samples = await list_samples(db, skip=skip, limit=limit)
    return [s.model_dump() for s in samples]


@router.get("/samples/{sample_id}", response_model=SampleResponse)
async def get_sample_endpoint(
    sample_id: str,
    db: DB,
) -> dict[str, Any]:
    """Get a sample by ID."""
    try:
        sample = await get_sample(db, sample_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return sample.model_dump()


@router.patch("/samples/{sample_id}", response_model=SampleResponse)
async def update_sample_endpoint(
    sample_id: str,
    data: SampleUpdate,
    db: DB,
) -> dict[str, Any]:
    """Update a sample."""
    try:
        sample = await update_sample(db, sample_id, data)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return sample.model_dump()


@router.delete("/samples/{sample_id}", status_code=204)
async def delete_sample_endpoint(
    sample_id: str,
    db: DB,
) -> None:
    """Delete a sample by ID."""
    try:
        await delete_sample(db, sample_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
