"""Motor async MongoDB client lifecycle."""

from typing import AsyncIterator

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from icast_cv.config import Settings

_client: AsyncIOMotorClient | None = None  # type: ignore[type-arg]
_database: AsyncIOMotorDatabase | None = None  # type: ignore[type-arg]


async def connect_db(settings: Settings) -> None:
    """Open the Motor client and select the database."""
    global _client, _database  # noqa: PLW0603
    _client = AsyncIOMotorClient(settings.mongodb_uri)
    _database = _client[settings.mongodb_database]


async def close_db() -> None:
    """Close the Motor client."""
    global _client, _database  # noqa: PLW0603
    if _client is not None:
        _client.close()
    _client = None
    _database = None


async def get_database() -> AsyncIterator[AsyncIOMotorDatabase]:  # type: ignore[type-arg]
    """FastAPI dependency that yields the database handle."""
    if _database is None:
        raise RuntimeError("Database not connected. Call connect_db() first.")
    yield _database


def get_database_sync() -> AsyncIOMotorDatabase:  # type: ignore[type-arg]
    """Non-generator accessor for use outside of FastAPI dependencies."""
    if _database is None:
        raise RuntimeError("Database not connected. Call connect_db() first.")
    return _database
