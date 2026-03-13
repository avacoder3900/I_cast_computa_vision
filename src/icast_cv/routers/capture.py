"""Image capture endpoint — orchestrates camera, storage, and database."""

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from icast_cv.config import get_settings
from icast_cv.crud.image_crud import create_image
from icast_cv.crud.inspection_crud import create_inspection
from icast_cv.crud.sample_crud import get_sample
from icast_cv.db import get_database
from icast_cv.exceptions import CameraError, NotFoundError, StorageError
from icast_cv.models.image import ImageCreate, ImageResponse
from icast_cv.models.inspection import InspectionCreate, InspectionResponse
from icast_cv.services.camera_service import capture_frame
from icast_cv.services.storage_service import save_image

router = APIRouter(tags=["capture"])

DB = Annotated[AsyncIOMotorDatabase, Depends(get_database)]  # type: ignore[type-arg]


class CaptureRequest(BaseModel):
    """Request body for capturing an image."""

    sample_id: str = Field(..., description="ID of the sample to associate the image with")
    camera_index: int = Field(default=0, ge=0, description="Camera device index")
    metadata: dict[str, object] = Field(default_factory=dict)


@router.post("/capture", response_model=ImageResponse, status_code=201)
async def capture_image(
    data: CaptureRequest,
    db: DB,
) -> dict[str, Any]:
    """Capture an image from a camera, save to disk, and store metadata."""
    # Verify sample exists
    try:
        await get_sample(db, data.sample_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Capture frame from camera
    try:
        frame = await capture_frame(data.camera_index)
    except CameraError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # Save to filesystem (and optionally upload to R2)
    settings = get_settings()
    try:
        stored = await save_image(
            frame, settings.image_storage_path, data.sample_id, settings=settings
        )
    except StorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Store metadata in database
    image_data = ImageCreate(
        sample_id=data.sample_id,
        filename=stored.filename,
        file_path=stored.file_path,
        thumbnail_path=stored.thumbnail_path,
        width=stored.width,
        height=stored.height,
        file_size_bytes=stored.file_size_bytes,
        camera_index=data.camera_index,
        metadata=data.metadata,
        captured_at=datetime.now(timezone.utc),
        image_url=stored.image_url,
    )
    image = await create_image(db, image_data)
    return image.model_dump()


class CaptureAndInspectRequest(BaseModel):
    """Request body for capturing an image and creating an inspection."""

    camera_index: int = Field(default=0, ge=0, description="Camera device index")
    inspection_type: str = Field(
        default="anomaly_detection", description="Type of inspection to run"
    )
    metadata: dict[str, object] = Field(default_factory=dict)


class CaptureAndInspectResponse(BaseModel):
    """Response for capture-and-inspect flow."""

    image: ImageResponse
    inspection: InspectionResponse


@router.post(
    "/samples/{sample_id}/capture-and-inspect",
    response_model=CaptureAndInspectResponse,
    status_code=201,
)
async def capture_and_inspect(
    sample_id: str,
    data: CaptureAndInspectRequest,
    db: DB,
) -> dict[str, Any]:
    """Capture an image, save it, and create a pending inspection."""
    # Verify sample exists
    try:
        await get_sample(db, sample_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Capture frame from camera
    try:
        frame = await capture_frame(data.camera_index)
    except CameraError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # Save to filesystem (and optionally upload to R2)
    settings = get_settings()
    try:
        stored = await save_image(
            frame, settings.image_storage_path, sample_id, settings=settings
        )
    except StorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Store image metadata in database
    image_data = ImageCreate(
        sample_id=sample_id,
        filename=stored.filename,
        file_path=stored.file_path,
        thumbnail_path=stored.thumbnail_path,
        width=stored.width,
        height=stored.height,
        file_size_bytes=stored.file_size_bytes,
        camera_index=data.camera_index,
        metadata=data.metadata,
        captured_at=datetime.now(timezone.utc),
        image_url=stored.image_url,
    )
    image = await create_image(db, image_data)

    # Create pending inspection
    inspection_data = InspectionCreate(
        sample_id=sample_id,
        image_id=image.id,
        inspection_type=data.inspection_type,
    )
    inspection = await create_inspection(db, inspection_data)

    return {
        "image": image.model_dump(),
        "inspection": inspection.model_dump(),
    }
