"""Health check endpoint."""

from typing import Any

from fastapi import APIRouter

from icast_cv.db import get_database_sync

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Return service and database health status."""
    db_ok = False
    try:
        db = get_database_sync()
        result = await db.command("ping")
        db_ok = bool(result.get("ok"))
    except Exception:
        db_ok = False

    status = "healthy" if db_ok else "degraded"
    return {
        "status": status,
        "service": "icast-cv",
        "version": "0.1.0",
        "database": "connected" if db_ok else "disconnected",
    }
