"""Gallery endpoints — combined view of training + inspection images."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from icast_cv.crud.image_crud import list_images
from icast_cv.db import get_database
from icast_cv.routers.training import _list_training_images

router = APIRouter(tags=["gallery"])

DB = Annotated[AsyncIOMotorDatabase, Depends(get_database)]


@router.get("/gallery/all")
async def gallery_all(
    db: DB,
    source: str | None = None,
    project_id: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
) -> dict[str, Any]:
    """Combined view of training images + inspection/captured images."""
    items: list[dict[str, Any]] = []

    # Training images (filesystem-based)
    if source is None or source == "training":
        for img in _list_training_images():
            items.append(
                {
                    "source": "training",
                    "filename": img["filename"],
                    "category": img["category"],
                    "tags": [],
                    "uploaded_at": img["modified_at"],
                    "thumbnail_url": img["thumbnail_url"],
                    "file_url": img["file_url"],
                }
            )

    # Inspection/captured images (MongoDB-based)
    if source is None or source == "inspection":
        try:
            db_images = await list_images(db, skip=0, limit=200, project_id=project_id)
            for img in db_images:
                d = img.model_dump()
                tags = []
                if d.get("cartridge_tag") and d["cartridge_tag"].get("labels"):
                    tags = d["cartridge_tag"]["labels"]
                items.append(
                    {
                        "source": "inspection",
                        "filename": d["filename"],
                        "category": "inspection",
                        "tags": tags,
                        "uploaded_at": d["captured_at"].isoformat()
                        if d.get("captured_at")
                        else "",
                        "thumbnail_url": f"/api/v1/images/{d['id']}/thumbnail",
                        "file_url": f"/api/v1/images/{d['id']}/file",
                    }
                )
        except Exception:
            # MongoDB may not be available
            pass

    # Sort by date descending
    items.sort(key=lambda x: x.get("uploaded_at", ""), reverse=True)

    return {
        "total": len(items),
        "images": items[skip : skip + limit],
    }
