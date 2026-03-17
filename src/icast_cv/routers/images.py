"""Image query, file-serving, and cartridge tagging endpoints."""

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from icast_cv.config import get_settings
from icast_cv.crud.image_crud import get_image, list_images, tag_image
from icast_cv.db import get_database
from icast_cv.exceptions import NotFoundError
from icast_cv.models.image import CartridgeTag, ImageResponse

router = APIRouter(tags=["images"])

DB = Annotated[AsyncIOMotorDatabase, Depends(get_database)]  # type: ignore[type-arg]


@router.get("/images", response_model=list[ImageResponse])
async def list_images_endpoint(
    db: DB,
    sample_id: str | None = None,
    cartridge_id: str | None = None,
    project_id: str | None = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict[str, Any]]:
    """List images with optional sample_id/cartridge_id/project_id filter and pagination."""
    images = await list_images(
        db, sample_id=sample_id, cartridge_id=cartridge_id, project_id=project_id,
        skip=skip, limit=limit,
    )
    return [img.model_dump() for img in images]


@router.get("/samples/{sample_id}/images", response_model=list[ImageResponse])
async def list_sample_images_endpoint(
    sample_id: str,
    db: DB,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict[str, Any]]:
    """List images for a specific sample."""
    images = await list_images(db, sample_id=sample_id, skip=skip, limit=limit)
    return [img.model_dump() for img in images]


@router.post("/images/{image_id}/tags", response_model=ImageResponse)
async def tag_image_endpoint(
    image_id: str,
    data: CartridgeTag,
    db: DB,
) -> dict[str, Any]:
    """Set or replace the cartridge tag on an image."""
    try:
        image = await tag_image(db, image_id, data)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return image.model_dump()


@router.get("/images/{image_id}/file")
async def get_image_file(
    image_id: str,
    db: DB,
) -> FileResponse:
    """Stream the full image file."""
    try:
        image = await get_image(db, image_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    settings = get_settings()
    file_path = Path(settings.image_storage_path) / image.file_path
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Image file not found on disk")
    return FileResponse(str(file_path), media_type="image/jpeg")


@router.get("/images/{image_id}/thumbnail")
async def get_image_thumbnail(
    image_id: str,
    db: DB,
) -> FileResponse:
    """Stream the thumbnail image."""
    try:
        image = await get_image(db, image_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    settings = get_settings()
    thumb_path = Path(settings.image_storage_path) / image.thumbnail_path
    if not thumb_path.is_file():
        raise HTTPException(status_code=404, detail="Thumbnail not found on disk")
    return FileResponse(str(thumb_path), media_type="image/jpeg")
