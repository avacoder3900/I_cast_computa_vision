"""Main worker loop — polls for pending inspections and runs inference."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from icast_cv.config import Settings
from icast_cv.worker.model_loader import load_model, run_inference
from icast_cv.worker.preprocessor import preprocess

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 2


async def _download_image(
    image_doc: dict[str, Any],
    settings: Settings,
) -> Path:
    """Return a local path for the image, downloading from R2 if needed."""
    local_path = Path(settings.image_storage_path) / image_doc["file_path"]
    if local_path.is_file():
        return local_path

    if settings.r2_configured:
        from icast_cv.services.cloud_storage_service import download_file

        key = image_doc["file_path"].replace("\\", "/")
        return await download_file(key, local_path, settings)

    raise FileNotFoundError(
        f"Image file not found locally and R2 not configured: {local_path}"
    )


async def _process_one(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    inspection_doc: dict[str, Any],
    session: Any,
    settings: Settings,
) -> None:
    """Process a single pending inspection."""
    from bson import ObjectId
    from PIL import Image

    inspection_id = inspection_doc["_id"]
    image_id = inspection_doc["image_id"]

    # Mark as processing
    await db.inspections.update_one(
        {"_id": inspection_id},
        {"$set": {"status": "processing"}},
    )

    try:
        # Fetch image document
        if not ObjectId.is_valid(image_id):
            raise ValueError(f"Invalid image_id: {image_id}")
        image_doc = await db.images.find_one({"_id": ObjectId(image_id)})
        if image_doc is None:
            raise FileNotFoundError(f"Image document {image_id} not found")

        # Download image
        image_path = await _download_image(image_doc, settings)

        # Preprocess
        input_size = (settings.model_input_size, settings.model_input_size)
        pil_image = Image.open(image_path).convert("RGB")
        tensor = preprocess(pil_image, input_size=input_size)

        # Run inference
        start = time.monotonic()
        score, is_anomaly = await asyncio.to_thread(run_inference, session, tensor)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        is_fail = score >= settings.confidence_threshold
        result_str = "fail" if is_fail else "pass"

        from datetime import datetime, timezone

        await db.inspections.update_one(
            {"_id": inspection_id},
            {
                "$set": {
                    "status": "complete",
                    "result": result_str,
                    "confidence_score": round(score, 4),
                    "defects": (
                        [{"type": "anomaly", "location": "global", "severity": "auto"}]
                        if is_fail
                        else []
                    ),
                    "model_version": str(Path(settings.model_path).name),
                    "processing_time_ms": elapsed_ms,
                    "completed_at": datetime.now(timezone.utc),
                }
            },
        )
        logger.info(
            "Inspection %s complete: %s (score=%.4f, %dms)",
            inspection_id,
            result_str,
            score,
            elapsed_ms,
        )

    except Exception:
        logger.exception("Inspection %s failed", inspection_id)
        from datetime import datetime, timezone

        await db.inspections.update_one(
            {"_id": inspection_id},
            {
                "$set": {
                    "status": "failed",
                    "completed_at": datetime.now(timezone.utc),
                }
            },
        )


async def run_worker(settings: Settings | None = None) -> None:
    """Main worker loop — connect to MongoDB, load model, poll for work."""
    from icast_cv.db import close_db, connect_db, get_database_sync

    if settings is None:
        settings = Settings()

    await connect_db(settings)
    db = get_database_sync()

    logger.info("Loading model from %s", settings.model_path)
    session = load_model(settings.model_path)
    logger.info("Worker ready — polling for pending inspections")

    try:
        while True:
            doc = await db.inspections.find_one({"status": "pending"})
            if doc is not None:
                await _process_one(db, doc, session, settings)
            else:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Worker shutting down")
    finally:
        await close_db()
