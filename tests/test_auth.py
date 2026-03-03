"""Tests for API key authentication."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_is_public(authed_app: tuple[AsyncClient, str]) -> None:
    """GET /health works without API key even when auth is enabled."""
    client, _ = authed_app
    resp = await client.get("/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_protected_route_rejects_no_key(authed_app: tuple[AsyncClient, str]) -> None:
    """Protected routes return 401 without API key."""
    client, _ = authed_app
    resp = await client.get("/api/v1/samples")
    assert resp.status_code == 401
    assert "API key" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_protected_route_rejects_wrong_key(authed_app: tuple[AsyncClient, str]) -> None:
    """Protected routes return 401 with wrong API key."""
    client, _ = authed_app
    resp = await client.get(
        "/api/v1/samples",
        headers={"X-API-Key": "wrong-key"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_accepts_correct_key(authed_app: tuple[AsyncClient, str]) -> None:
    """Protected routes work with correct API key."""
    client, api_key = authed_app
    resp = await client.get(
        "/api/v1/samples",
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 200
