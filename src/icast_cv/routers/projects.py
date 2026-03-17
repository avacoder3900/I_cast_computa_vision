"""Project CRUD endpoints + project-scoped training, images, inspections."""

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from icast_cv.config import get_settings
from icast_cv.crud.image_crud import label_image, list_images
from icast_cv.crud.inspection_crud import list_all_inspections
from icast_cv.crud.project_crud import (
    create_project,
    delete_project,
    duplicate_project,
    get_project,
    list_projects,
    update_project,
)
from icast_cv.db import get_database
from icast_cv.exceptions import NotFoundError
from icast_cv.models.project import (
    BIMS_PHASE_LABELS,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)

router = APIRouter(tags=["projects"])
logger = logging.getLogger(__name__)

DB = Annotated[AsyncIOMotorDatabase, Depends(get_database)]  # type: ignore[type-arg]

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".gif", ".webp"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_project_training_dirs(project_id: str) -> tuple[Path, Path, Path]:
    """Return (good_dir, defect_dir, uncategorized_dir) for a project, creating them."""
    settings = get_settings()
    base = settings.training_data_path / project_id
    good_dir = base / "good"
    defect_dir = base / "defect"
    uncategorized_dir = base / "uncategorized"
    good_dir.mkdir(parents=True, exist_ok=True)
    defect_dir.mkdir(parents=True, exist_ok=True)
    uncategorized_dir.mkdir(parents=True, exist_ok=True)
    return good_dir, defect_dir, uncategorized_dir


def _get_project_model_path(project_id: str) -> Path:
    """Return model path for a project."""
    settings = get_settings()
    return settings.training_data_path / "models" / project_id / "model.onnx"


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------

@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project_endpoint(
    data: ProjectCreate,
    db: DB,
) -> dict[str, Any]:
    """Create a new project."""
    project = await create_project(db, data)
    # Pre-create training directories
    _get_project_training_dirs(project.id)
    return project.model_dump()


@router.get("/projects", response_model=dict[str, Any])
async def list_projects_endpoint(
    db: DB,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    sort_by: str = "created_at",
    sort_order: int = -1,
    search: str | None = None,
) -> dict[str, Any]:
    """List projects with pagination, sorting, and search."""
    projects, total = await list_projects(
        db, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order, search=search
    )
    return {
        "projects": [p.model_dump() for p in projects],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/projects/labels/global")
async def get_global_labels() -> dict[str, Any]:
    """Return the global BIMS manufacturing phase labels."""
    return {"labels": BIMS_PHASE_LABELS}


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project_endpoint(
    project_id: str,
    db: DB,
) -> dict[str, Any]:
    """Get a project by ID."""
    try:
        project = await get_project(db, project_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return project.model_dump()


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project_endpoint(
    project_id: str,
    data: ProjectUpdate,
    db: DB,
) -> dict[str, Any]:
    """Update a project."""
    try:
        project = await update_project(db, project_id, data)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return project.model_dump()


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project_endpoint(
    project_id: str,
    db: DB,
) -> None:
    """Delete a project by ID."""
    try:
        await delete_project(db, project_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/projects/{project_id}/duplicate", response_model=ProjectResponse, status_code=201)
async def duplicate_project_endpoint(
    project_id: str,
    db: DB,
) -> dict[str, Any]:
    """Duplicate a project."""
    try:
        project = await duplicate_project(db, project_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return project.model_dump()


# ---------------------------------------------------------------------------
# Project-scoped stats
# ---------------------------------------------------------------------------

@router.get("/projects/{project_id}/stats")
async def project_stats(
    project_id: str,
    db: DB,
) -> dict[str, Any]:
    """Get stats for a specific project."""
    try:
        project = await get_project(db, project_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    total_images = await db.images.count_documents({"project_id": project_id})
    approved = await db.images.count_documents({"project_id": project_id, "label": "approved"})
    rejected = await db.images.count_documents({"project_id": project_id, "label": "rejected"})
    annotated = approved + rejected

    total_inspections = await db.inspections.count_documents({"project_id": project_id})
    pass_count = await db.inspections.count_documents({"project_id": project_id, "result": "pass"})
    fail_count = await db.inspections.count_documents({"project_id": project_id, "result": "fail"})

    # Training data stats from filesystem
    good_dir, defect_dir, uncat_dir = _get_project_training_dirs(project_id)
    training_good = sum(1 for f in good_dir.iterdir() if f.suffix.lower() in IMAGE_EXTS)
    training_defect = sum(1 for f in defect_dir.iterdir() if f.suffix.lower() in IMAGE_EXTS)
    training_uncat = sum(1 for f in uncat_dir.iterdir() if f.suffix.lower() in IMAGE_EXTS)

    return {
        "project_id": project_id,
        "image_count": total_images,
        "annotated_count": annotated,
        "approved_count": approved,
        "rejected_count": rejected,
        "total_inspections": total_inspections,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "accuracy": round(pass_count / total_inspections * 100, 1) if total_inspections > 0 else 0,
        "training_good": training_good,
        "training_defect": training_defect,
        "training_uncategorized": training_uncat,
        "model_status": project.model_status,
        "model_version": project.model_version,
    }


# ---------------------------------------------------------------------------
# Project-scoped images
# ---------------------------------------------------------------------------

@router.get("/projects/{project_id}/images")
async def list_project_images(
    project_id: str,
    db: DB,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    label: str | None = None,
) -> dict[str, Any]:
    """List images for a specific project."""
    query: dict[str, Any] = {"project_id": project_id}
    if label:
        query["label"] = label
    total = await db.images.count_documents(query)
    cursor = db.images.find(query).skip(skip).limit(limit).sort("captured_at", -1)
    from icast_cv.crud.image_crud import _doc_to_image
    docs = await cursor.to_list(length=limit)
    images = [_doc_to_image(d).model_dump() for d in docs]
    return {"total": total, "images": images}


class LabelRequest(BaseModel):
    """Request body for labeling an image."""
    label: str


@router.patch("/projects/{project_id}/images/{image_id}/label")
async def label_project_image(
    project_id: str,
    image_id: str,
    data: LabelRequest,
    db: DB,
) -> dict[str, Any]:
    """Label an image as approved or rejected within a project."""
    if data.label not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="label must be 'approved' or 'rejected'")
    try:
        image = await label_image(db, image_id, data.label)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Update project counts
    approved = await db.images.count_documents({"project_id": project_id, "label": "approved"})
    rejected = await db.images.count_documents({"project_id": project_id, "label": "rejected"})
    total = await db.images.count_documents({"project_id": project_id})
    await db.projects.update_one(
        {"_id": __import__("bson").ObjectId(project_id)},
        {"$set": {
            "annotated_count": approved + rejected,
            "image_count": total,
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    return image.model_dump()


# ---------------------------------------------------------------------------
# Project-scoped training data (filesystem)
# ---------------------------------------------------------------------------

@router.get("/projects/{project_id}/training/data-stats")
async def project_training_stats(project_id: str) -> dict[str, Any]:
    """Count images in project-specific training folders."""
    good_dir, defect_dir, uncat_dir = _get_project_training_dirs(project_id)
    good = sum(1 for f in good_dir.iterdir() if f.suffix.lower() in IMAGE_EXTS)
    defect = sum(1 for f in defect_dir.iterdir() if f.suffix.lower() in IMAGE_EXTS)
    uncat = sum(1 for f in uncat_dir.iterdir() if f.suffix.lower() in IMAGE_EXTS)
    return {
        "good_count": good,
        "defect_count": defect,
        "uncategorized_count": uncat,
        "total": good + defect + uncat,
    }


@router.post("/projects/{project_id}/training/upload")
async def upload_project_training_image(
    project_id: str,
    file: UploadFile,
    category: str = "good",
) -> dict[str, str]:
    """Upload an image to a project's training folder."""
    if category not in ("good", "defect", "uncategorized"):
        raise HTTPException(status_code=400, detail="category must be 'good', 'defect', or 'uncategorized'")
    if not file.filename:
        raise HTTPException(status_code=400, detail="File must have a filename")

    good_dir, defect_dir, uncat_dir = _get_project_training_dirs(project_id)
    dir_map = {"good": good_dir, "defect": defect_dir, "uncategorized": uncat_dir}
    target_dir = dir_map[category]

    safe_name = Path(file.filename).name
    if not safe_name:
        raise HTTPException(status_code=400, detail="Invalid filename")

    target_path = target_dir / safe_name
    if target_path.exists():
        stem = target_path.stem
        suffix = target_path.suffix
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        target_path = target_dir / f"{stem}_{ts}{suffix}"

    content = await file.read()
    target_path.write_bytes(content)

    return {
        "filename": target_path.name,
        "category": category,
        "path": str(target_path),
        "size_bytes": str(len(content)),
    }


@router.get("/projects/{project_id}/training/images")
async def list_project_training_images(
    project_id: str,
    category: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    """List training images for a specific project."""
    good_dir, defect_dir, uncat_dir = _get_project_training_dirs(project_id)
    dirs: dict[str, Path] = {"good": good_dir, "defect": defect_dir, "uncategorized": uncat_dir}

    if category and category in dirs:
        dirs = {category: dirs[category]}

    results: list[dict[str, Any]] = []
    for cat, directory in dirs.items():
        for f in directory.iterdir():
            if f.suffix.lower() not in IMAGE_EXTS:
                continue
            stat = f.stat()
            results.append({
                "filename": f.name,
                "category": cat,
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "file_url": f"/api/v1/projects/{project_id}/training/images/{cat}/{f.name}/file",
            })
    results.sort(key=lambda x: x["modified_at"], reverse=True)
    return {"total": len(results), "images": results[skip: skip + limit]}


@router.get("/projects/{project_id}/training/images/{category}/{filename}/file")
async def serve_project_training_image(
    project_id: str,
    category: str,
    filename: str,
) -> FileResponse:
    """Serve a training image file from a project."""
    if category not in ("good", "defect", "uncategorized"):
        raise HTTPException(status_code=400, detail="Invalid category")

    good_dir, defect_dir, uncat_dir = _get_project_training_dirs(project_id)
    dirs = {"good": good_dir, "defect": defect_dir, "uncategorized": uncat_dir}

    safe_name = Path(filename).name
    file_path = dirs[category] / safe_name
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")

    suffix = file_path.suffix.lower()
    media_types = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".bmp": "image/bmp", ".tiff": "image/tiff", ".gif": "image/gif",
        ".webp": "image/webp",
    }
    return FileResponse(str(file_path), media_type=media_types.get(suffix, "image/jpeg"))


class RecategorizeRequest(BaseModel):
    new_category: str


@router.patch("/projects/{project_id}/training/images/{filename}")
async def recategorize_project_training_image(
    project_id: str,
    filename: str,
    data: RecategorizeRequest,
) -> dict[str, str]:
    """Move a training image between categories within a project."""
    if data.new_category not in ("good", "defect", "uncategorized"):
        raise HTTPException(status_code=400, detail="new_category must be 'good', 'defect', or 'uncategorized'")

    good_dir, defect_dir, uncat_dir = _get_project_training_dirs(project_id)
    dirs = {"good": good_dir, "defect": defect_dir, "uncategorized": uncat_dir}

    source_path: Path | None = None
    old_category: str | None = None
    safe_name = Path(filename).name
    for cat, directory in dirs.items():
        candidate = directory / safe_name
        if candidate.is_file():
            source_path = candidate
            old_category = cat
            break

    if source_path is None or old_category is None:
        raise HTTPException(status_code=404, detail=f"Image '{filename}' not found")

    if old_category == data.new_category:
        return {"filename": safe_name, "old_category": old_category, "new_category": data.new_category, "status": "unchanged"}

    target_dir = dirs[data.new_category]
    target_path = target_dir / safe_name
    if target_path.exists():
        stem = target_path.stem
        suffix = target_path.suffix
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        target_path = target_dir / f"{stem}_{ts}{suffix}"

    shutil.move(str(source_path), str(target_path))
    return {"filename": target_path.name, "old_category": old_category, "new_category": data.new_category, "status": "moved"}


# ---------------------------------------------------------------------------
# Project-scoped inspections
# ---------------------------------------------------------------------------

@router.get("/projects/{project_id}/inspections")
async def list_project_inspections(
    project_id: str,
    db: DB,
    result: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    """List inspections for a specific project."""
    inspections = await list_all_inspections(
        db, project_id=project_id, result=result, skip=skip, limit=limit
    )
    return {
        "total": len(inspections),
        "inspections": [i.model_dump() for i in inspections],
    }
