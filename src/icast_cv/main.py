"""FastAPI application factory, lifespan, and middleware."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from icast_cv.auth import require_api_key
from icast_cv.config import get_settings
from icast_cv.db import close_db, connect_db
from icast_cv.routers import cameras, capture, health, images, samples


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown lifecycle: connect and disconnect from MongoDB."""
    settings = get_settings()
    try:
        await connect_db(settings)
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "MongoDB not available — running in degraded mode"
        )
    settings.image_storage_path.mkdir(parents=True, exist_ok=True)
    yield
    await close_db()


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    settings = get_settings()

    application = FastAPI(
        title="ICast Computer Vision API",
        description="Lab sample photography service — capture, store, and query images.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Public routes (no auth)
    application.include_router(health.router)

    # Protected routes (API key required when configured)
    api_deps = [Depends(require_api_key)]
    application.include_router(
        samples.router, prefix="/api/v1", dependencies=api_deps
    )
    application.include_router(
        images.router, prefix="/api/v1", dependencies=api_deps
    )
    application.include_router(
        capture.router, prefix="/api/v1", dependencies=api_deps
    )
    application.include_router(
        cameras.router, prefix="/api/v1", dependencies=api_deps
    )

    return application


app = create_app()
