"""Project CRUD endpoints + project-scoped training, images, inspections."""

import asyncio
import logging
import random
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from icast_cv.config import get_settings
from icast_cv.crud.image_crud import create_image, label_image, list_images
from icast_cv.crud.inspection_crud import (
    create_inspection,
    list_all_inspections,
    update_inspection_result,
)
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
from icast_cv.models.image import ImageCreate
from icast_cv.models.inspection import InspectionCreate, InspectionResult
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

# Per-project training state (in-memory, single process)
_project_training_state: dict[str, dict[str, Any]] = {}


def _get_project_training_state(project_id: str) -> dict[str, Any]:
    """Get or create training state for a project."""
    if project_id not in _project_training_state:
        _project_training_state[project_id] = {
            "status": "idle",
            "progress": 0,
            "message": "",
            "started_at": None,
            "completed_at": None,
            "model_path": None,
            "logs": [],
        }
    return _project_training_state[project_id]


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
        {"_id": ObjectId(project_id)},
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


class ReviewRequest(BaseModel):
    """Request body for reviewing (approving/rejecting) an inspection."""
    result: str


@router.patch("/projects/{project_id}/inspections/{inspection_id}/review")
async def review_project_inspection(
    project_id: str,
    inspection_id: str,
    data: ReviewRequest,
    db: DB,
) -> dict[str, Any]:
    """Approve or reject an inspection result (human review override)."""
    if data.result not in ("pass", "fail"):
        raise HTTPException(status_code=400, detail="result must be 'pass' or 'fail'")
    result_data = InspectionResult(
        result=data.result,
        confidence_score=1.0,
        model_version="human-review",
    )
    try:
        inspection = await update_inspection_result(db, inspection_id, result_data)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return inspection.model_dump()


# ---------------------------------------------------------------------------
# Project-scoped training start / status
# ---------------------------------------------------------------------------

async def _run_project_training(project_id: str, db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
    """Background training task for a project."""
    state = _get_project_training_state(project_id)
    state["status"] = "running"
    state["progress"] = 0
    state["logs"] = []

    def _log(msg: str) -> None:
        logger.info(msg)
        state["logs"].append(
            f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}"
        )

    try:
        good_dir, defect_dir, _ = _get_project_training_dirs(project_id)
        good_files = [f for f in good_dir.iterdir() if f.suffix.lower() in IMAGE_EXTS]
        defect_files = [f for f in defect_dir.iterdir() if f.suffix.lower() in IMAGE_EXTS]

        if len(good_files) < 2:
            raise ValueError(
                f"Need at least 2 approved images for training, found {len(good_files)}"
            )

        _log(f"Found {len(good_files)} approved, {len(defect_files)} rejected images")
        state["progress"] = 10

        # Simulated training steps
        steps = [
            (20, "Loading and preprocessing images..."),
            (40, "Training feature extractor..."),
            (60, "Computing anomaly scores..."),
            (80, "Validating model..."),
            (95, "Saving model weights..."),
        ]

        for progress, msg in steps:
            await asyncio.sleep(2)
            _log(msg)
            state["progress"] = progress

        model_path = _get_project_model_path(project_id)
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model_path.write_bytes(b"SIMULATED_MODEL")
        state["model_path"] = str(model_path)

        await asyncio.sleep(1)
        state["progress"] = 100
        _log("Training complete (simulated — install anomalib for real training)")
        state["status"] = "complete"
        state["completed_at"] = datetime.now(timezone.utc).isoformat()

        # Update project model status
        version = f"v{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
        await db.projects.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {
                "model_status": "trained",
                "model_version": version,
                "updated_at": datetime.now(timezone.utc),
            }},
        )
        _log(f"Model version: {version}")

    except Exception as exc:
        state["status"] = "failed"
        state["message"] = str(exc)
        state["completed_at"] = datetime.now(timezone.utc).isoformat()
        _log(f"Training failed: {exc}")
        logger.exception("Project training failed for %s", project_id)

        await db.projects.update_one(
            {"_id": ObjectId(project_id)},
            {"$set": {
                "model_status": "failed",
                "updated_at": datetime.now(timezone.utc),
            }},
        )


@router.post("/projects/{project_id}/training/start")
async def start_project_training(
    project_id: str,
    db: DB,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """Kick off training for a specific project."""
    try:
        await get_project(db, project_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    state = _get_project_training_state(project_id)
    if state["status"] == "running":
        raise HTTPException(status_code=409, detail="Training is already running")

    state["status"] = "starting"
    state["progress"] = 0
    state["message"] = ""
    state["started_at"] = datetime.now(timezone.utc).isoformat()
    state["completed_at"] = None
    state["model_path"] = None
    state["logs"] = []

    # Update project status to training
    await db.projects.update_one(
        {"_id": ObjectId(project_id)},
        {"$set": {"model_status": "training", "updated_at": datetime.now(timezone.utc)}},
    )

    background_tasks.add_task(_run_project_training, project_id, db)
    return {"status": "started"}


@router.get("/projects/{project_id}/training/status")
async def project_training_status_endpoint(project_id: str) -> dict[str, Any]:
    """Get training status for a specific project."""
    return dict(_get_project_training_state(project_id))


# ---------------------------------------------------------------------------
# Project-scoped test / invoke
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/test/invoke")
async def invoke_project_test(
    project_id: str,
    file: UploadFile,
    db: DB,
) -> dict[str, Any]:
    """Upload a test image, run inference (simulated), return pass/fail + confidence."""
    try:
        project = await get_project(db, project_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not file.filename:
        raise HTTPException(status_code=400, detail="File must have a filename")

    # Save test image under image_storage_path so /images/{id}/file can serve it
    settings = get_settings()
    test_dir = settings.image_storage_path / "test" / project_id
    test_dir.mkdir(parents=True, exist_ok=True)

    safe_name = Path(file.filename).name
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    target_name = f"{Path(safe_name).stem}_{ts}{Path(safe_name).suffix}"
    target_path = test_dir / target_name

    content = await file.read()
    target_path.write_bytes(content)

    # Create image record (file_path relative to image_storage_path)
    relative_path = f"test/{project_id}/{target_name}"
    image_data = ImageCreate(
        sample_id="test",
        project_id=project_id,
        filename=target_name,
        file_path=relative_path,
        thumbnail_path=relative_path,
        width=0,
        height=0,
        file_size_bytes=len(content),
        camera_index=-1,
        captured_at=datetime.now(timezone.utc),
    )
    image = await create_image(db, image_data)

    # Simulate inference
    confidence = round(random.uniform(0.55, 0.99), 3)
    result = "pass" if confidence > 0.70 else "fail"

    # Create and complete inspection record
    insp_data = InspectionCreate(
        sample_id="test",
        image_id=image.id,
        project_id=project_id,
        inspection_type="binary_classification",
    )
    inspection = await create_inspection(db, insp_data)

    insp_result = InspectionResult(
        result=result,
        confidence_score=confidence,
        model_version=project.model_version or "simulated-v1",
        processing_time_ms=random.randint(50, 500),
    )
    inspection = await update_inspection_result(db, inspection.id, insp_result)

    return {
        "inspection_id": inspection.id,
        "image_id": image.id,
        "result": result,
        "confidence_score": confidence,
        "model_version": project.model_version or "simulated-v1",
        "processing_time_ms": inspection.processing_time_ms,
        "image_url": f"/api/v1/images/{image.id}/file",
    }
