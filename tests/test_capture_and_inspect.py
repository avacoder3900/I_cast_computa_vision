"""Integration tests for the capture-and-inspect flow."""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from icast_cv.services.storage_service import StoredImage


@pytest.mark.asyncio
async def test_capture_and_inspect_creates_both(
    client: AsyncClient, mock_db: Any, tmp_storage: Path
) -> None:
    """POST /api/v1/samples/{id}/capture-and-inspect creates image + inspection."""
    create_resp = await client.post("/api/v1/samples", json={"name": "E2E Sample"})
    sample_id = create_resp.json()["id"]

    # Set up fake files
    sample_dir = tmp_storage / sample_id
    sample_dir.mkdir(parents=True, exist_ok=True)
    thumb_dir = sample_dir / "thumbs"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    (sample_dir / "cap.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
    (thumb_dir / "cap.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 50)

    fake_frame = object()
    fake_stored = StoredImage(
        filename="cap.jpg",
        file_path=f"{sample_id}/cap.jpg",
        thumbnail_path=f"{sample_id}/thumbs/cap.jpg",
        width=640,
        height=480,
        file_size_bytes=104,
    )

    with (
        patch(
            "icast_cv.routers.capture.capture_frame",
            new_callable=AsyncMock,
            return_value=fake_frame,
        ),
        patch(
            "icast_cv.routers.capture.save_image",
            new_callable=AsyncMock,
            return_value=fake_stored,
        ),
    ):
        resp = await client.post(
            f"/api/v1/samples/{sample_id}/capture-and-inspect",
            json={"camera_index": 0, "inspection_type": "anomaly_detection"},
        )

    assert resp.status_code == 201
    body = resp.json()

    # Image created
    assert body["image"]["sample_id"] == sample_id
    assert body["image"]["filename"] == "cap.jpg"
    assert "id" in body["image"]

    # Inspection created with pending status
    assert body["inspection"]["sample_id"] == sample_id
    assert body["inspection"]["image_id"] == body["image"]["id"]
    assert body["inspection"]["status"] == "pending"
    assert body["inspection"]["inspection_type"] == "anomaly_detection"


@pytest.mark.asyncio
async def test_capture_and_inspect_sample_not_found(client: AsyncClient) -> None:
    """POST /api/v1/samples/{id}/capture-and-inspect returns 404 for missing sample."""
    resp = await client.post(
        "/api/v1/samples/000000000000000000000000/capture-and-inspect",
        json={"camera_index": 0},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_poll_inspection(client: AsyncClient, mock_db: Any) -> None:
    """GET /api/inspections/{id}/poll returns current inspection state."""
    # Create sample + image
    sample_resp = await client.post("/api/v1/samples", json={"name": "PollSample"})
    sample_id = sample_resp.json()["id"]

    from datetime import datetime, timezone

    img_doc = {
        "sample_id": sample_id,
        "filename": "poll.jpg",
        "file_path": f"{sample_id}/poll.jpg",
        "thumbnail_path": f"{sample_id}/thumbs/poll.jpg",
        "width": 640,
        "height": 480,
        "file_size_bytes": 100,
        "camera_index": 0,
        "metadata": {},
        "captured_at": datetime.now(timezone.utc),
    }
    img_result = await mock_db.images.insert_one(img_doc)
    image_id = str(img_result.inserted_id)

    # Create inspection
    create_resp = await client.post(
        "/api/inspections",
        json={
            "sample_id": sample_id,
            "image_id": image_id,
            "inspection_type": "visual",
        },
    )
    inspection_id = create_resp.json()["id"]

    # Poll
    poll_resp = await client.get(f"/api/inspections/{inspection_id}/poll")
    assert poll_resp.status_code == 200
    assert poll_resp.json()["status"] == "pending"

    # Post result
    await client.post(
        f"/api/inspections/{inspection_id}/result",
        json={"result": "pass", "confidence_score": 0.92},
    )

    # Poll again — should be complete
    poll_resp2 = await client.get(f"/api/inspections/{inspection_id}/poll")
    assert poll_resp2.status_code == 200
    assert poll_resp2.json()["status"] == "complete"
    assert poll_resp2.json()["result"] == "pass"
