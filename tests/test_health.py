"""Tests for health endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_status(client: AsyncClient) -> None:
    """Health endpoint returns service info."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "icast-cv"
    assert body["version"] == "0.1.0"
    assert "status" in body
    assert "database" in body
