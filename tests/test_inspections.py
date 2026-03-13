"""Tests for inspection endpoints."""

from datetime import datetime, timezone
from typing import Any

import pytest
from httpx import AsyncClient


async def _seed_sample_and_image(client: AsyncClient, mock_db: Any) -> tuple[str, str]:
    """Helper: create a sample and insert a fake image document."""
    create_resp = await client.post("/api/v1/samples", json={"name": "InspSample"})
    sample_id = create_resp.json()["id"]

    doc = {
        "sample_id": sample_id,
        "filename": "test.jpg",
        "file_path": f"{sample_id}/test.jpg",
        "thumbnail_path": f"{sample_id}/thumbs/test.jpg",
        "width": 640,
        "height": 480,
        "file_size_bytes": 100,
        "camera_index": 0,
        "metadata": {},
        "captured_at": datetime.now(timezone.utc),
    }
    result = await mock_db.images.insert_one(doc)
    image_id = str(result.inserted_id)
    return sample_id, image_id


@pytest.mark.asyncio
async def test_create_inspection(client: AsyncClient, mock_db: Any) -> None:
    """POST /api/inspections creates an inspection with status=pending."""
    sample_id, image_id = await _seed_sample_and_image(client, mock_db)
    resp = await client.post(
        "/api/inspections",
        json={
            "sample_id": sample_id,
            "image_id": image_id,
            "inspection_type": "anomaly_detection",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "pending"
    assert body["sample_id"] == sample_id
    assert body["image_id"] == image_id
    assert body["inspection_type"] == "anomaly_detection"
    assert body["result"] is None
    assert "id" in body


@pytest.mark.asyncio
async def test_get_inspection(client: AsyncClient, mock_db: Any) -> None:
    """GET /api/inspections/{id} returns the inspection."""
    sample_id, image_id = await _seed_sample_and_image(client, mock_db)
    create_resp = await client.post(
        "/api/inspections",
        json={
            "sample_id": sample_id,
            "image_id": image_id,
            "inspection_type": "visual",
        },
    )
    inspection_id = create_resp.json()["id"]
    resp = await client.get(f"/api/inspections/{inspection_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == inspection_id


@pytest.mark.asyncio
async def test_get_inspection_not_found(client: AsyncClient) -> None:
    """GET /api/inspections/{id} returns 404 for missing inspection."""
    resp = await client.get("/api/inspections/000000000000000000000000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_inspections_by_sample(client: AsyncClient, mock_db: Any) -> None:
    """GET /api/inspections?sample_id=X returns inspections for sample."""
    sample_id, image_id = await _seed_sample_and_image(client, mock_db)
    await client.post(
        "/api/inspections",
        json={
            "sample_id": sample_id,
            "image_id": image_id,
            "inspection_type": "anomaly_detection",
        },
    )
    resp = await client.get(f"/api/inspections?sample_id={sample_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["sample_id"] == sample_id


@pytest.mark.asyncio
async def test_list_inspections_requires_sample_id(client: AsyncClient) -> None:
    """GET /api/inspections without sample_id returns 400."""
    resp = await client.get("/api/inspections")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_post_inspection_result(client: AsyncClient, mock_db: Any) -> None:
    """POST /api/inspections/{id}/result updates with CV results."""
    sample_id, image_id = await _seed_sample_and_image(client, mock_db)
    create_resp = await client.post(
        "/api/inspections",
        json={
            "sample_id": sample_id,
            "image_id": image_id,
            "inspection_type": "anomaly_detection",
        },
    )
    inspection_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/inspections/{inspection_id}/result",
        json={
            "result": "pass",
            "confidence_score": 0.95,
            "defects": [],
            "model_version": "patchcore-v1",
            "processing_time_ms": 320,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "complete"
    assert body["result"] == "pass"
    assert body["confidence_score"] == 0.95
    assert body["model_version"] == "patchcore-v1"
    assert body["completed_at"] is not None


@pytest.mark.asyncio
async def test_post_inspection_result_with_defects(
    client: AsyncClient, mock_db: Any
) -> None:
    """POST /api/inspections/{id}/result stores defect details."""
    sample_id, image_id = await _seed_sample_and_image(client, mock_db)
    create_resp = await client.post(
        "/api/inspections",
        json={
            "sample_id": sample_id,
            "image_id": image_id,
            "inspection_type": "anomaly_detection",
        },
    )
    inspection_id = create_resp.json()["id"]

    resp = await client.post(
        f"/api/inspections/{inspection_id}/result",
        json={
            "result": "fail",
            "confidence_score": 0.87,
            "defects": [
                {"type": "scratch", "location": "top-left", "severity": "medium"},
            ],
            "model_version": "patchcore-v1",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"] == "fail"
    assert len(body["defects"]) == 1
    assert body["defects"][0]["type"] == "scratch"


@pytest.mark.asyncio
async def test_post_result_not_found(client: AsyncClient) -> None:
    """POST /api/inspections/{id}/result returns 404 for missing inspection."""
    resp = await client.post(
        "/api/inspections/000000000000000000000000/result",
        json={"result": "pass", "confidence_score": 0.9},
    )
    assert resp.status_code == 404
