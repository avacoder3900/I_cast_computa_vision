"""OpenCV camera abstraction — all blocking calls run in asyncio.to_thread."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from icast_cv.exceptions import CameraError

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt

MAX_CAMERA_SCAN = 5


@dataclass
class CameraInfo:
    """Info about a detected camera."""

    index: int
    name: str
    is_open: bool
    width: int
    height: int


def _capture_sync(camera_index: int) -> Any:
    """Synchronous capture — called via to_thread."""
    import cv2

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise CameraError(f"Cannot open camera at index {camera_index}")
    try:
        ret, frame = cap.read()
        if not ret:
            raise CameraError(f"Failed to read frame from camera {camera_index}")
        return frame
    finally:
        cap.release()


def _get_camera_info_sync(camera_index: int) -> CameraInfo | None:
    """Synchronous camera probe — called via to_thread."""
    import cv2

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        return None
    try:
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return CameraInfo(
            index=camera_index,
            name=f"Camera {camera_index}",
            is_open=True,
            width=width,
            height=height,
        )
    finally:
        cap.release()


def _list_cameras_sync() -> list[CameraInfo]:
    """Scan for available cameras synchronously."""
    cameras: list[CameraInfo] = []
    for i in range(MAX_CAMERA_SCAN):
        info = _get_camera_info_sync(i)
        if info is not None:
            cameras.append(info)
    return cameras


async def capture_frame(camera_index: int) -> Any:
    """Capture a single frame from the specified camera."""
    return await asyncio.to_thread(_capture_sync, camera_index)


async def list_cameras() -> list[CameraInfo]:
    """List all available cameras."""
    return await asyncio.to_thread(_list_cameras_sync)


async def get_camera_status(camera_index: int) -> CameraInfo:
    """Get status for a specific camera. Raises CameraError if not found."""
    info = await asyncio.to_thread(_get_camera_info_sync, camera_index)
    if info is None:
        raise CameraError(f"No camera found at index {camera_index}")
    return info
