"""Tests for project CRUD endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient) -> None:
    """POST /api/v1/projects creates a project."""
    resp = await client.post(
        "/api/v1/projects",
        json={
            "name": "Wax Filling",
            "description": "Inspect wax filling quality",
            "project_type": "classification",
            "tags": ["production"],
            "phases": ["wax_filled", "wax_qc"],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Wax Filling"
    assert body["project_type"] == "classification"
    assert body["image_count"] == 0
    assert body["annotated_count"] == 0
    assert body["model_status"] == "untrained"
    assert "id" in body
    assert "created_at" in body


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient) -> None:
    """GET /api/v1/projects returns paginated list."""
    await client.post("/api/v1/projects", json={"name": "P1"})
    await client.post("/api/v1/projects", json={"name": "P2"})
    resp = await client.get("/api/v1/projects")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["projects"]) == 2


@pytest.mark.asyncio
async def test_list_projects_search(client: AsyncClient) -> None:
    """GET /api/v1/projects?search= filters by name."""
    await client.post("/api/v1/projects", json={"name": "Wax Filling"})
    await client.post("/api/v1/projects", json={"name": "Reagent Fill"})

    resp = await client.get("/api/v1/projects", params={"search": "Wax"})
    body = resp.json()
    assert body["total"] == 1
    assert body["projects"][0]["name"] == "Wax Filling"


@pytest.mark.asyncio
async def test_get_project(client: AsyncClient) -> None:
    """GET /api/v1/projects/{id} returns the project."""
    create_resp = await client.post("/api/v1/projects", json={"name": "GetMe"})
    pid = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/projects/{pid}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "GetMe"


@pytest.mark.asyncio
async def test_get_project_not_found(client: AsyncClient) -> None:
    """GET /api/v1/projects/{id} returns 404 for missing."""
    resp = await client.get("/api/v1/projects/000000000000000000000000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_project(client: AsyncClient) -> None:
    """PATCH /api/v1/projects/{id} updates fields."""
    create_resp = await client.post("/api/v1/projects", json={"name": "Old"})
    pid = create_resp.json()["id"]
    resp = await client.patch(
        f"/api/v1/projects/{pid}",
        json={"name": "New", "model_status": "trained"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New"
    assert resp.json()["model_status"] == "trained"


@pytest.mark.asyncio
async def test_delete_project(client: AsyncClient) -> None:
    """DELETE /api/v1/projects/{id} removes the project."""
    create_resp = await client.post("/api/v1/projects", json={"name": "Bye"})
    pid = create_resp.json()["id"]
    resp = await client.delete(f"/api/v1/projects/{pid}")
    assert resp.status_code == 204
    resp2 = await client.get(f"/api/v1/projects/{pid}")
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_project(client: AsyncClient) -> None:
    """POST /api/v1/projects/{id}/duplicate creates a copy."""
    create_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Original", "tags": ["a"], "phases": ["backing"]},
    )
    pid = create_resp.json()["id"]
    resp = await client.post(f"/api/v1/projects/{pid}/duplicate")
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Original (copy)"
    assert body["tags"] == ["a"]
    assert body["phases"] == ["backing"]
    assert body["image_count"] == 0


@pytest.mark.asyncio
async def test_project_stats(client: AsyncClient) -> None:
    """GET /api/v1/projects/{id}/stats returns project statistics."""
    create_resp = await client.post("/api/v1/projects", json={"name": "Stats Test"})
    pid = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/projects/{pid}/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["project_id"] == pid
    assert body["image_count"] == 0
    assert body["annotated_count"] == 0


@pytest.mark.asyncio
async def test_global_labels(client: AsyncClient) -> None:
    """GET /api/v1/projects/labels/global returns BIMS labels."""
    resp = await client.get("/api/v1/projects/labels/global")
    assert resp.status_code == 200
    labels = resp.json()["labels"]
    assert "backing" in labels
    assert "wax_filled" in labels
    assert len(labels) == 15


@pytest.mark.asyncio
async def test_project_with_labels(client: AsyncClient) -> None:
    """Projects can store custom label definitions."""
    resp = await client.post(
        "/api/v1/projects",
        json={
            "name": "With Labels",
            "labels": [
                {"name": "crack", "color": "#ff0000"},
                {"name": "bubble", "color": "#0000ff"},
            ],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["labels"]) == 2
    assert body["labels"][0]["name"] == "crack"
