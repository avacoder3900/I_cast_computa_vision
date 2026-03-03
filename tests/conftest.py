"""Shared test fixtures."""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient
from motor.motor_asyncio import AsyncIOMotorDatabase

from icast_cv.auth import require_api_key
from icast_cv.config import Settings
from icast_cv.db import get_database
from icast_cv.main import create_app


@pytest.fixture
def mock_db() -> Any:
    """Return a mongomock-motor database for testing."""
    client = AsyncMongoMockClient()
    return client["test_icast_cv"]


@pytest.fixture
def tmp_storage(tmp_path: Path) -> Path:
    """Return a temp directory for image storage."""
    storage = tmp_path / "images"
    storage.mkdir()
    return storage


@pytest.fixture
def test_settings(tmp_storage: Path) -> Settings:
    """Settings pointing at temp storage, auth disabled."""
    return Settings(
        mongodb_uri="mongodb://localhost:27017",
        mongodb_database="test_icast_cv",
        image_storage_path=tmp_storage,
        api_key="",
    )


@pytest.fixture
async def client(
    mock_db: Any, tmp_storage: Path, test_settings: Settings
) -> AsyncIterator[AsyncClient]:
    """Async test client with mocked DB, storage, and auth disabled."""
    with patch("icast_cv.main.get_settings", return_value=test_settings):
        app = create_app()

    # Override DB dependency
    async def override_get_database() -> AsyncIterator[AsyncIOMotorDatabase]:  # type: ignore[type-arg]
        yield mock_db

    # Override auth to always pass (no key needed in tests)
    async def override_auth() -> str | None:
        return None

    app.dependency_overrides[get_database] = override_get_database
    app.dependency_overrides[require_api_key] = override_auth

    with (
        patch("icast_cv.routers.health.get_database_sync", return_value=mock_db),
        patch("icast_cv.routers.capture.get_settings", return_value=test_settings),
        patch("icast_cv.routers.images.get_settings", return_value=test_settings),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def authed_app(
    mock_db: Any, tmp_storage: Path
) -> AsyncIterator[tuple[AsyncClient, str]]:
    """Test client with API key auth ENABLED. Returns (client, api_key)."""
    api_key = "test-secret-key-123"
    settings = Settings(
        mongodb_uri="mongodb://localhost:27017",
        mongodb_database="test_icast_cv",
        image_storage_path=tmp_storage,
        api_key=api_key,
    )

    with patch("icast_cv.main.get_settings", return_value=settings):
        app = create_app()

    async def override_get_database() -> AsyncIterator[AsyncIOMotorDatabase]:  # type: ignore[type-arg]
        yield mock_db

    app.dependency_overrides[get_database] = override_get_database

    # Patch auth module's get_settings so it sees the key
    with (
        patch("icast_cv.auth.get_settings", return_value=settings),
        patch("icast_cv.routers.health.get_database_sync", return_value=mock_db),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac, api_key

    app.dependency_overrides.clear()
