"""Camera status endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException

from icast_cv.exceptions import CameraError
from icast_cv.services.camera_service import get_camera_status, list_cameras

router = APIRouter(tags=["cameras"])


@router.get("/cameras")
async def list_cameras_endpoint() -> list[dict[str, Any]]:
    """List all available cameras."""
    cameras = await list_cameras()
    return [
        {
            "index": cam.index,
            "name": cam.name,
            "is_open": cam.is_open,
            "width": cam.width,
            "height": cam.height,
        }
        for cam in cameras
    ]


@router.get("/cameras/{index}/status")
async def get_camera_status_endpoint(index: int) -> dict[str, Any]:
    """Get status for a specific camera."""
    try:
        cam = await get_camera_status(index)
    except CameraError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "index": cam.index,
        "name": cam.name,
        "is_open": cam.is_open,
        "width": cam.width,
        "height": cam.height,
    }
