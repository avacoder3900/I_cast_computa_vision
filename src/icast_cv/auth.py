"""API key authentication dependency."""

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from icast_cv.config import get_settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(
    api_key: str | None = Security(_api_key_header),
) -> str | None:
    """Validate the X-API-Key header. Skips if API_KEY is not configured."""
    settings = get_settings()
    if not settings.api_key:
        # Auth disabled — no key configured
        return None
    if api_key is None or api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key
