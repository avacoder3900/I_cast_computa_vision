"""Training data management and model training endpoints."""

import asyncio
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from icast_cv.config import get_settings

router = APIRouter(tags=["training"])
logger = logging.getLogger(__name__)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".gif", ".webp"}

# In-memory training state (single-process)
_training_state: dict[str, Any] = {
    "status": "idle",
    "progress": 0,
    "message": "",
    "started_at": None,
    "completed_at": None,
    "model_path": None,
    "logs": [],
}


def _get_training_dirs() -> tuple[Path, Path, Path]:
    """Return (good_dir, defect_dir, uncategorized_dir), creating them if needed."""
    settings = get_settings()
    base = settings.training_data_path
    good_dir = base / "good"
    defect_dir = base / "defect"
    uncategorized_dir = base / "uncategorized"
    good_dir.mkdir(parents=True, exist_ok=True)
    defect_dir.mkdir(parents=True, exist_ok=True)
    uncategorized_dir.mkdir(parents=True, exist_ok=True)
    return good_dir, defect_dir, uncategorized_dir


@router.get("/training/data-stats")
async def training_data_stats() -> dict[str, Any]:
    """Count images in good, defect, and uncategorized training folders."""
    good_dir, defect_dir, uncategorized_dir = _get_training_dirs()
    good_count = sum(1 for f in good_dir.iterdir() if f.suffix.lower() in IMAGE_EXTS)
    defect_count = sum(1 for f in defect_dir.iterdir() if f.suffix.lower() in IMAGE_EXTS)
    uncategorized_count = sum(
        1 for f in uncategorized_dir.iterdir() if f.suffix.lower() in IMAGE_EXTS
    )
    return {
        "good_count": good_count,
        "defect_count": defect_count,
        "uncategorized_count": uncategorized_count,
        "total": good_count + defect_count + uncategorized_count,
        "good_path": str(good_dir),
        "defect_path": str(defect_dir),
        "uncategorized_path": str(uncategorized_dir),
    }


@router.post("/training/upload")
async def upload_training_image(
    file: UploadFile,
    category: str = "good",
) -> dict[str, str]:
    """Upload an image to the good, defect, or uncategorized training folder."""
    if category not in ("good", "defect", "uncategorized"):
        raise HTTPException(
            status_code=400,
            detail="category must be 'good', 'defect', or 'uncategorized'",
        )

    if not file.filename:
        raise HTTPException(status_code=400, detail="File must have a filename")

    good_dir, defect_dir, uncategorized_dir = _get_training_dirs()
    dir_map = {"good": good_dir, "defect": defect_dir, "uncategorized": uncategorized_dir}
    target_dir = dir_map[category]

    # Sanitize filename
    safe_name = Path(file.filename).name
    if not safe_name:
        raise HTTPException(status_code=400, detail="Invalid filename")

    # Avoid overwriting — append timestamp if exists
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


async def _run_training() -> None:
    """Background training task. Uses anomalib if available, else simulates."""
    global _training_state  # noqa: PLW0603
    _training_state["status"] = "running"
    _training_state["progress"] = 0
    _training_state["logs"] = []

    def _log(msg: str) -> None:
        logger.info(msg)
        _training_state["logs"].append(
            f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}"
        )

    try:
        good_dir, defect_dir, _ = _get_training_dirs()
        good_files = [f for f in good_dir.iterdir() if f.suffix.lower() in IMAGE_EXTS]
        defect_files = [f for f in defect_dir.iterdir() if f.suffix.lower() in IMAGE_EXTS]

        if len(good_files) < 5:
            raise ValueError(
                f"Need at least 5 good images for training, found {len(good_files)}"
            )

        _log(f"Found {len(good_files)} good, {len(defect_files)} defect images")
        _training_state["progress"] = 10

        # Try to use anomalib for real training
        try:
            _log("Attempting anomalib-based training...")
            _training_state["progress"] = 20

            from anomalib.data import Folder
            from anomalib.engine import Engine
            from anomalib.models import Padim

            _log("Anomalib loaded — configuring Padim model")
            _training_state["progress"] = 30

            settings = get_settings()
            datamodule = Folder(
                name="cartridge_inspection",
                root=str(settings.training_data_path),
                normal_dir="good",
                abnormal_dir="defect",
                image_size=(224, 224),
                train_batch_size=8,
            )

            model = Padim()
            engine = Engine(max_epochs=1)

            _log("Starting training...")
            _training_state["progress"] = 50

            await asyncio.to_thread(engine.fit, model=model, datamodule=datamodule)
            _training_state["progress"] = 80

            _log("Exporting to ONNX...")
            output_path = settings.training_data_path / "trained_model.onnx"
            await asyncio.to_thread(
                engine.export, model=model, export_type="onnx", export_root=str(output_path.parent)
            )
            _training_state["progress"] = 100
            _training_state["model_path"] = str(output_path)
            _log(f"Training complete — model saved to {output_path}")

        except ImportError:
            _log("Anomalib not installed — running simulated training")
            _training_state["progress"] = 20

            steps = [
                (30, "Loading and preprocessing images..."),
                (50, "Training feature extractor..."),
                (70, "Computing anomaly scores..."),
                (85, "Validating model..."),
                (95, "Saving model weights..."),
            ]

            for progress, msg in steps:
                await asyncio.sleep(2)
                _log(msg)
                _training_state["progress"] = progress

            settings = get_settings()
            output_path = settings.training_data_path / "trained_model.onnx"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            # Create a placeholder to indicate training ran
            output_path.write_bytes(b"SIMULATED_MODEL")
            _training_state["model_path"] = str(output_path)

            await asyncio.sleep(1)
            _training_state["progress"] = 100
            _log("Simulated training complete (install anomalib for real training)")

        _training_state["status"] = "complete"
        _training_state["completed_at"] = datetime.now(timezone.utc).isoformat()

    except Exception as exc:
        _training_state["status"] = "failed"
        _training_state["message"] = str(exc)
        _training_state["completed_at"] = datetime.now(timezone.utc).isoformat()
        _log(f"Training failed: {exc}")
        logger.exception("Training failed")


@router.post("/training/start")
async def start_training(background_tasks: BackgroundTasks) -> dict[str, str]:
    """Kick off a training run as a background task."""
    if _training_state["status"] == "running":
        raise HTTPException(status_code=409, detail="Training is already running")

    _training_state["status"] = "starting"
    _training_state["progress"] = 0
    _training_state["message"] = ""
    _training_state["started_at"] = datetime.now(timezone.utc).isoformat()
    _training_state["completed_at"] = None
    _training_state["model_path"] = None
    _training_state["logs"] = []

    background_tasks.add_task(_run_training)
    return {"status": "started"}


@router.get("/training/status")
async def training_status() -> dict[str, Any]:
    """Get current training status."""
    return dict(_training_state)


@router.get("/training/model")
async def download_model() -> Any:
    """Download the trained ONNX model."""
    from fastapi.responses import FileResponse

    if not _training_state.get("model_path"):
        raise HTTPException(status_code=404, detail="No trained model available")
    model_path = Path(_training_state["model_path"])
    if not model_path.is_file():
        raise HTTPException(status_code=404, detail="Model file not found")
    return FileResponse(
        str(model_path),
        media_type="application/octet-stream",
        filename="trained_model.onnx",
    )


# ---------------------------------------------------------------------------
# Training image list / re-categorize / serve file
# ---------------------------------------------------------------------------


def _list_training_images(category_filter: str | None = None) -> list[dict[str, Any]]:
    """List training images from the filesystem with metadata."""
    good_dir, defect_dir, uncategorized_dir = _get_training_dirs()
    dirs = {"good": good_dir, "defect": defect_dir, "uncategorized": uncategorized_dir}

    if category_filter and category_filter in dirs:
        dirs = {category_filter: dirs[category_filter]}

    results: list[dict[str, Any]] = []
    for category, directory in dirs.items():
        for f in directory.iterdir():
            if f.suffix.lower() not in IMAGE_EXTS:
                continue
            stat = f.stat()
            results.append(
                {
                    "filename": f.name,
                    "category": category,
                    "path": str(f),
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                    "thumbnail_url": f"/api/v1/training/images/{category}/{f.name}/file",
                    "file_url": f"/api/v1/training/images/{category}/{f.name}/file",
                }
            )
    results.sort(key=lambda x: x["modified_at"], reverse=True)
    return results


@router.get("/training/images")
async def list_training_images(
    category: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    """List all training images with their category."""
    images = _list_training_images(category)
    return {
        "total": len(images),
        "images": images[skip : skip + limit],
    }


class RecategorizeRequest(BaseModel):
    """Request body for re-categorizing a training image."""

    new_category: str


@router.patch("/training/images/{filename}")
async def recategorize_training_image(
    filename: str,
    data: RecategorizeRequest,
) -> dict[str, str]:
    """Move a training image between good/defect/uncategorized folders."""
    if data.new_category not in ("good", "defect", "uncategorized"):
        raise HTTPException(
            status_code=400,
            detail="new_category must be 'good', 'defect', or 'uncategorized'",
        )

    good_dir, defect_dir, uncategorized_dir = _get_training_dirs()
    dirs = {"good": good_dir, "defect": defect_dir, "uncategorized": uncategorized_dir}

    # Find the file in any category folder
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
        return {
            "filename": safe_name,
            "old_category": old_category,
            "new_category": data.new_category,
            "status": "unchanged",
        }

    target_dir = dirs[data.new_category]
    target_path = target_dir / safe_name
    if target_path.exists():
        stem = target_path.stem
        suffix = target_path.suffix
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        target_path = target_dir / f"{stem}_{ts}{suffix}"

    shutil.move(str(source_path), str(target_path))

    return {
        "filename": target_path.name,
        "old_category": old_category,
        "new_category": data.new_category,
        "status": "moved",
    }


class BatchRecategorizeRequest(BaseModel):
    """Request body for batch re-categorizing training images."""

    filenames: list[str]
    new_category: str


@router.patch("/training/images-batch")
async def batch_recategorize(data: BatchRecategorizeRequest) -> dict[str, Any]:
    """Batch re-categorize multiple training images."""
    if data.new_category not in ("good", "defect", "uncategorized"):
        raise HTTPException(
            status_code=400,
            detail="new_category must be 'good', 'defect', or 'uncategorized'",
        )

    results = []
    for filename in data.filenames:
        try:
            result = await recategorize_training_image(
                filename, RecategorizeRequest(new_category=data.new_category)
            )
            results.append(result)
        except HTTPException as exc:
            results.append({"filename": filename, "status": "error", "detail": exc.detail})

    return {"results": results}


@router.get("/training/images/{category}/{filename}/file")
async def serve_training_image(category: str, filename: str) -> FileResponse:
    """Serve a training image file."""
    if category not in ("good", "defect", "uncategorized"):
        raise HTTPException(status_code=400, detail="Invalid category")

    good_dir, defect_dir, uncategorized_dir = _get_training_dirs()
    dirs = {"good": good_dir, "defect": defect_dir, "uncategorized": uncategorized_dir}

    safe_name = Path(filename).name
    file_path = dirs[category] / safe_name

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")

    suffix = file_path.suffix.lower()
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
    }
    return FileResponse(str(file_path), media_type=media_types.get(suffix, "image/jpeg"))
