"""Tests for capture endpoint."""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from icast_cv.exceptions import CameraError
from icast_cv.services.storage_service import StoredImage


@pytest.mark.asyncio
async def test_capture_success(client: AsyncClient, mock_db: Any, tmp_storage: Path) -> None:
    """POST /api/v1/capture creates an image for an existing sample."""
    create_resp = await client.post("/api/v1/samples", json={"name": "Capture Sample"})
    sample_id = create_resp.json()["id"]

    # Create fake files on disk so the response is verifiable
    sample_dir = tmp_storage / sample_id
    sample_dir.mkdir(parents=True, exist_ok=True)
    thumb_dir = sample_dir / "thumbs"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    (sample_dir / "test_capture.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
    (thumb_dir / "test_capture.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 50)

    fake_frame = object()  # Opaque fake — we mock everything that touches it
    fake_stored = StoredImage(
        filename="test_capture.jpg",
        file_path=f"{sample_id}/test_capture.jpg",
        thumbnail_path=f"{sample_id}/thumbs/test_capture.jpg",
        width=640,
        height=480,
        file_size_bytes=104,
    )

    with (
        patch("icast_cv.routers.capture.capture_frame", new_callable=AsyncMock, return_value=fake_frame),
        patch("icast_cv.routers.capture.save_image", new_callable=AsyncMock, return_value=fake_stored),
    ):
        resp = await client.post(
            "/api/v1/capture",
            json={"sample_id": sample_id, "camera_index": 0},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["sample_id"] == sample_id
    assert body["width"] == 640
    assert body["height"] == 480
    assert body["camera_index"] == 0
    assert "id" in body
    assert body["filename"] == "test_capture.jpg"


@pytest.mark.asyncio
async def test_capture_sample_not_found(client: AsyncClient) -> None:
    """POST /api/v1/capture returns 404 if sample doesn't exist."""
    resp = await client.post(
        "/api/v1/capture",
        json={"sample_id": "000000000000000000000000", "camera_index": 0},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_capture_camera_error(client: AsyncClient, mock_db: Any) -> None:
    """POST /api/v1/capture returns 502 if camera fails."""
    create_resp = await client.post("/api/v1/samples", json={"name": "Cam Fail"})
    sample_id = create_resp.json()["id"]

    with patch(
        "icast_cv.routers.capture.capture_frame",
        new_callable=AsyncMock,
        side_effect=CameraError("no camera"),
    ):
        resp = await client.post(
            "/api/v1/capture",
            json={"sample_id": sample_id, "camera_index": 0},
        )
    assert resp.status_code == 502
