"""Tests for cartridge photo tagging."""

from datetime import datetime, timezone
from typing import Any

import pytest
from httpx import AsyncClient


async def _seed_image(client: AsyncClient, mock_db: Any) -> tuple[str, str]:
    """Helper: create a sample and insert a fake image document."""
    create_resp = await client.post("/api/v1/samples", json={"name": "TagSample"})
    sample_id = create_resp.json()["id"]

    doc = {
        "sample_id": sample_id,
        "filename": "tag_test.jpg",
        "file_path": f"{sample_id}/tag_test.jpg",
        "thumbnail_path": f"{sample_id}/thumbs/tag_test.jpg",
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
async def test_tag_image(client: AsyncClient, mock_db: Any) -> None:
    """POST /api/v1/images/{id}/tags sets cartridge tag on image."""
    _, image_id = await _seed_image(client, mock_db)

    resp = await client.post(
        f"/api/v1/images/{image_id}/tags",
        json={
            "cartridge_record_id": "cart-001",
            "phase": "wax_filled",
            "labels": ["wax_fill", "top_view"],
            "notes": "Slight overflow on left edge",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["cartridge_tag"] is not None
    assert body["cartridge_tag"]["cartridge_record_id"] == "cart-001"
    assert body["cartridge_tag"]["phase"] == "wax_filled"
    assert body["cartridge_tag"]["labels"] == ["wax_fill", "top_view"]
    assert body["cartridge_tag"]["notes"] == "Slight overflow on left edge"


@pytest.mark.asyncio
async def test_tag_image_replaces_existing(client: AsyncClient, mock_db: Any) -> None:
    """POST /api/v1/images/{id}/tags replaces an existing tag."""
    _, image_id = await _seed_image(client, mock_db)

    await client.post(
        f"/api/v1/images/{image_id}/tags",
        json={
            "cartridge_record_id": "cart-001",
            "phase": "backing",
            "labels": ["initial"],
        },
    )
    resp = await client.post(
        f"/api/v1/images/{image_id}/tags",
        json={
            "cartridge_record_id": "cart-001",
            "phase": "inspected",
            "labels": ["defect_crack"],
            "notes": "Crack found after inspection",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["cartridge_tag"]["phase"] == "inspected"
    assert resp.json()["cartridge_tag"]["labels"] == ["defect_crack"]


@pytest.mark.asyncio
async def test_tag_image_not_found(client: AsyncClient) -> None:
    """POST /api/v1/images/{id}/tags returns 404 for missing image."""
    resp = await client.post(
        "/api/v1/images/000000000000000000000000/tags",
        json={
            "cartridge_record_id": "cart-001",
            "phase": "backing",
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_images_by_cartridge_id(
    client: AsyncClient, mock_db: Any
) -> None:
    """GET /api/v1/images?cartridge_id=X returns images for that cartridge."""
    _, image_id = await _seed_image(client, mock_db)

    # Tag the image with a cartridge
    await client.post(
        f"/api/v1/images/{image_id}/tags",
        json={
            "cartridge_record_id": "cart-123",
            "phase": "sealed",
            "labels": ["final_check"],
        },
    )

    # Query by cartridge_id
    resp = await client.get("/api/v1/images?cartridge_id=cart-123")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == image_id
    assert body[0]["cartridge_tag"]["cartridge_record_id"] == "cart-123"


@pytest.mark.asyncio
async def test_list_images_by_cartridge_id_empty(client: AsyncClient) -> None:
    """GET /api/v1/images?cartridge_id=X returns empty when no matches."""
    resp = await client.get("/api/v1/images?cartridge_id=nonexistent")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_untagged_image_has_null_cartridge_tag(
    client: AsyncClient, mock_db: Any
) -> None:
    """Images without a cartridge tag return cartridge_tag: null."""
    _, image_id = await _seed_image(client, mock_db)
    resp = await client.get("/api/v1/images")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) >= 1
    img = [i for i in body if i["id"] == image_id][0]
    assert img["cartridge_tag"] is None


@pytest.mark.asyncio
async def test_inspection_with_cartridge_fields(
    client: AsyncClient, mock_db: Any
) -> None:
    """Inspections can carry cartridge_record_id and phase."""
    sample_id, image_id = await _seed_image(client, mock_db)

    resp = await client.post(
        "/api/inspections",
        json={
            "sample_id": sample_id,
            "image_id": image_id,
            "inspection_type": "anomaly_detection",
            "cartridge_record_id": "cart-456",
            "phase": "reagent_filled",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["cartridge_record_id"] == "cart-456"
    assert body["phase"] == "reagent_filled"

    # Verify the fields survive a GET
    inspection_id = body["id"]
    get_resp = await client.get(f"/api/inspections/{inspection_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["cartridge_record_id"] == "cart-456"
    assert get_resp.json()["phase"] == "reagent_filled"
