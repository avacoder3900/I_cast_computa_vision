"""Tests for image query endpoints."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient


async def _seed_image(client: AsyncClient, mock_db: Any, tmp_storage: Path) -> tuple[str, str]:
    """Helper: create a sample and insert a fake image document."""
    create_resp = await client.post("/api/v1/samples", json={"name": "ImgSample"})
    sample_id = create_resp.json()["id"]

    # Create a fake image file on disk
    sample_dir = tmp_storage / sample_id
    sample_dir.mkdir(parents=True, exist_ok=True)
    thumb_dir = sample_dir / "thumbs"
    thumb_dir.mkdir(parents=True, exist_ok=True)

    filename = "test_image.jpg"
    # Write a minimal JPEG (just enough bytes for test)
    (sample_dir / filename).write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
    (thumb_dir / filename).write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 50)

    doc = {
        "sample_id": sample_id,
        "filename": filename,
        "file_path": f"{sample_id}/{filename}",
        "thumbnail_path": f"{sample_id}/thumbs/{filename}",
        "width": 640,
        "height": 480,
        "file_size_bytes": 104,
        "camera_index": 0,
        "metadata": {},
        "captured_at": datetime.now(timezone.utc),
    }
    result = await mock_db.images.insert_one(doc)
    image_id = str(result.inserted_id)
    return sample_id, image_id


@pytest.mark.asyncio
async def test_list_images(client: AsyncClient, mock_db: Any, tmp_storage: Path) -> None:
    """GET /api/v1/images returns images."""
    await _seed_image(client, mock_db, tmp_storage)
    resp = await client.get("/api/v1/images")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_list_images_by_sample(client: AsyncClient, mock_db: Any, tmp_storage: Path) -> None:
    """GET /api/v1/images?sample_id=... filters by sample."""
    sample_id, _ = await _seed_image(client, mock_db, tmp_storage)
    resp = await client.get(f"/api/v1/images?sample_id={sample_id}")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
    assert all(img["sample_id"] == sample_id for img in resp.json())


@pytest.mark.asyncio
async def test_sample_images_endpoint(client: AsyncClient, mock_db: Any, tmp_storage: Path) -> None:
    """GET /api/v1/samples/{id}/images returns images for sample."""
    sample_id, _ = await _seed_image(client, mock_db, tmp_storage)
    resp = await client.get(f"/api/v1/samples/{sample_id}/images")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_get_image_file(client: AsyncClient, mock_db: Any, tmp_storage: Path) -> None:
    """GET /api/v1/images/{id}/file streams the image."""
    _, image_id = await _seed_image(client, mock_db, tmp_storage)
    resp = await client.get(f"/api/v1/images/{image_id}/file")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_image_thumbnail(client: AsyncClient, mock_db: Any, tmp_storage: Path) -> None:
    """GET /api/v1/images/{id}/thumbnail streams the thumbnail."""
    _, image_id = await _seed_image(client, mock_db, tmp_storage)
    resp = await client.get(f"/api/v1/images/{image_id}/thumbnail")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_image_file_not_found(client: AsyncClient) -> None:
    """GET /api/v1/images/{id}/file returns 404 for missing image."""
    resp = await client.get("/api/v1/images/000000000000000000000000/file")
    assert resp.status_code == 404
