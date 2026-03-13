"""Training data management and model training endpoints."""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile

from icast_cv.config import get_settings

router = APIRouter(tags=["training"])
logger = logging.getLogger(__name__)

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


def _get_training_dirs() -> tuple[Path, Path]:
    """Return (good_dir, defect_dir), creating them if needed."""
    settings = get_settings()
    base = settings.training_data_path
    good_dir = base / "good"
    defect_dir = base / "defect"
    good_dir.mkdir(parents=True, exist_ok=True)
    defect_dir.mkdir(parents=True, exist_ok=True)
    return good_dir, defect_dir


@router.get("/training/data-stats")
async def training_data_stats() -> dict[str, Any]:
    """Count images in good and defect training folders."""
    good_dir, defect_dir = _get_training_dirs()
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
    good_count = sum(1 for f in good_dir.iterdir() if f.suffix.lower() in exts)
    defect_count = sum(1 for f in defect_dir.iterdir() if f.suffix.lower() in exts)
    return {
        "good_count": good_count,
        "defect_count": defect_count,
        "total": good_count + defect_count,
        "good_path": str(good_dir),
        "defect_path": str(defect_dir),
    }


@router.post("/training/upload")
async def upload_training_image(
    file: UploadFile,
    category: str = "good",
) -> dict[str, str]:
    """Upload an image to the good or defect training folder."""
    if category not in ("good", "defect"):
        raise HTTPException(status_code=400, detail="category must be 'good' or 'defect'")

    if not file.filename:
        raise HTTPException(status_code=400, detail="File must have a filename")

    good_dir, defect_dir = _get_training_dirs()
    target_dir = good_dir if category == "good" else defect_dir

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
        good_dir, defect_dir = _get_training_dirs()
        exts = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
        good_files = [f for f in good_dir.iterdir() if f.suffix.lower() in exts]
        defect_files = [f for f in defect_dir.iterdir() if f.suffix.lower() in exts]

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
