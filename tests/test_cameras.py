"""Tests for camera endpoints."""

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from icast_cv.exceptions import CameraError
from icast_cv.services.camera_service import CameraInfo


@pytest.mark.asyncio
async def test_list_cameras(client: AsyncClient) -> None:
    """GET /api/v1/cameras returns camera list."""
    fake_cameras = [
        CameraInfo(index=0, name="Camera 0", is_open=True, width=1920, height=1080),
    ]
    with patch("icast_cv.routers.cameras.list_cameras", return_value=fake_cameras):
        resp = await client.get("/api/v1/cameras")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["index"] == 0
    assert body[0]["width"] == 1920


@pytest.mark.asyncio
async def test_list_cameras_empty(client: AsyncClient) -> None:
    """GET /api/v1/cameras returns empty list when no cameras."""
    with patch("icast_cv.routers.cameras.list_cameras", return_value=[]):
        resp = await client.get("/api/v1/cameras")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_camera_status(client: AsyncClient) -> None:
    """GET /api/v1/cameras/{index}/status returns camera info."""
    fake_info = CameraInfo(index=0, name="Camera 0", is_open=True, width=1920, height=1080)
    with patch("icast_cv.routers.cameras.get_camera_status", return_value=fake_info):
        resp = await client.get("/api/v1/cameras/0/status")
    assert resp.status_code == 200
    assert resp.json()["index"] == 0


@pytest.mark.asyncio
async def test_get_camera_status_not_found(client: AsyncClient) -> None:
    """GET /api/v1/cameras/{index}/status returns 404 for missing camera."""
    with patch(
        "icast_cv.routers.cameras.get_camera_status",
        side_effect=CameraError("No camera found at index 99"),
    ):
        resp = await client.get("/api/v1/cameras/99/status")
    assert resp.status_code == 404
