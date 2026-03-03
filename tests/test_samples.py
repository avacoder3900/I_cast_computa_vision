"""Tests for sample CRUD endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_sample(client: AsyncClient) -> None:
    """POST /api/v1/samples creates a sample."""
    resp = await client.post(
        "/api/v1/samples",
        json={"name": "Test Sample", "description": "A test", "project": "Proj-1", "tags": ["t1"]},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Test Sample"
    assert body["description"] == "A test"
    assert body["project"] == "Proj-1"
    assert body["tags"] == ["t1"]
    assert "id" in body
    assert "created_at" in body


@pytest.mark.asyncio
async def test_list_samples(client: AsyncClient) -> None:
    """GET /api/v1/samples returns a list."""
    await client.post("/api/v1/samples", json={"name": "S1"})
    await client.post("/api/v1/samples", json={"name": "S2"})
    resp = await client.get("/api/v1/samples")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2


@pytest.mark.asyncio
async def test_get_sample(client: AsyncClient) -> None:
    """GET /api/v1/samples/{id} returns the sample."""
    create_resp = await client.post("/api/v1/samples", json={"name": "GetMe"})
    sample_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/samples/{sample_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "GetMe"


@pytest.mark.asyncio
async def test_get_sample_not_found(client: AsyncClient) -> None:
    """GET /api/v1/samples/{id} returns 404 for missing sample."""
    resp = await client.get("/api/v1/samples/000000000000000000000000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_sample(client: AsyncClient) -> None:
    """PATCH /api/v1/samples/{id} updates fields."""
    create_resp = await client.post("/api/v1/samples", json={"name": "Old Name"})
    sample_id = create_resp.json()["id"]
    resp = await client.patch(
        f"/api/v1/samples/{sample_id}",
        json={"name": "New Name"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_delete_sample(client: AsyncClient) -> None:
    """DELETE /api/v1/samples/{id} removes the sample."""
    create_resp = await client.post("/api/v1/samples", json={"name": "Delete Me"})
    sample_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/v1/samples/{sample_id}")
    assert resp.status_code == 204
    # Confirm gone
    resp2 = await client.get(f"/api/v1/samples/{sample_id}")
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_delete_sample_not_found(client: AsyncClient) -> None:
    """DELETE /api/v1/samples/{id} returns 404 for missing sample."""
    resp = await client.delete("/api/v1/samples/000000000000000000000000")
    assert resp.status_code == 404
