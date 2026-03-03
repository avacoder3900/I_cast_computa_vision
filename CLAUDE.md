# ICast Computer Vision API

## Project Overview
FastAPI REST API for lab/scientific sample photography. Captures images from USB cameras via OpenCV, stores files on local filesystem, metadata in MongoDB.

## Architecture
```
Router (HTTP) -> Service (business logic) -> CRUD (database) -> MongoDB
                                          -> StorageService -> Filesystem
                                          -> CameraService -> OpenCV
```

## Commands
```bash
# Install
pip install -e ".[dev]"

# Run server
uvicorn src.icast_cv.main:app --reload

# Run via Docker
docker compose up

# Tests
pytest tests/ -v

# Type check
mypy --strict src/

# Export OpenAPI spec + TypeScript types
python scripts/export_openapi.py
python scripts/generate_ts_types.py
```

## Code Conventions
- **Async everywhere**: All route handlers, CRUD, and DB operations are async
- **OpenCV in threads**: Camera operations wrapped in `asyncio.to_thread()`
- **ObjectId as string**: MongoDB `_id` converted to `str` at CRUD boundary
- **Pydantic v2 models**: Use `model_config` not `class Config`
- **src layout**: All app code under `src/icast_cv/`
- **API versioning**: Domain routes under `/api/v1/`, health at root
- **No binary in DB**: Images on filesystem, only paths in MongoDB
- **Thumbnails at capture time**: 256px max generated on capture, not on request

## Key Files
- `src/icast_cv/main.py` — App factory, lifespan, CORS, auth middleware
- `src/icast_cv/config.py` — Pydantic Settings from env vars
- `src/icast_cv/auth.py` — API key authentication dependency
- `src/icast_cv/db.py` — Motor async client lifecycle
- `src/icast_cv/services/camera_service.py` — OpenCV wrapper
- `src/icast_cv/services/storage_service.py` — File storage + thumbnails
- `generated/openapi.json` — Exported OpenAPI spec
- `generated/icast-cv-api.ts` — TypeScript types for frontend integration

## Security
- **CORS**: Configured via `CORS_ORIGINS` env var (comma-separated)
- **API Key**: Set `API_KEY` env var to enable X-API-Key header auth
- `/health` and `/docs` are always public; all `/api/v1/*` routes are protected

## Deployment
- `Dockerfile` — Multi-stage Python 3.12 image
- `docker-compose.yml` — API + MongoDB for local dev
- `.github/workflows/ci.yml` — Tests + type check on push/PR
- Designed for Railway, Fly.io, Render, or any Docker host
- Frontend (Vercel) connects via `NEXT_PUBLIC_ICAST_API_URL`

## MongoDB Collections
- `samples` — Lab sample metadata (name, description, project, tags)
- `images` — Image metadata (sample_id, file_path, dimensions, camera_index)
