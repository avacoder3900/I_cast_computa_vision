"""Filesystem storage — save images and generate thumbnails."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from PIL import Image

from icast_cv.exceptions import StorageError

if TYPE_CHECKING:
    import numpy as np
    import numpy.typing as npt

THUMBNAIL_MAX_SIZE = 256


@dataclass
class StoredImage:
    """Result of saving an image to the filesystem."""

    filename: str
    file_path: str
    thumbnail_path: str
    width: int
    height: int
    file_size_bytes: int


def _save_sync(
    frame: Any,
    base_path: Path,
    sample_id: str,
) -> StoredImage:
    """Synchronous save + thumbnail generation — called via to_thread."""
    import cv2

    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%dT%H%M%S")
    short_id = uuid4().hex[:6]
    filename = f"{timestamp}_{short_id}.jpg"

    sample_dir = base_path / sample_id
    sample_dir.mkdir(parents=True, exist_ok=True)
    thumb_dir = sample_dir / "thumbs"
    thumb_dir.mkdir(parents=True, exist_ok=True)

    file_path = sample_dir / filename
    thumb_path = thumb_dir / filename

    # Save full image via OpenCV
    success: bool = cv2.imwrite(str(file_path), frame)
    if not success:
        raise StorageError(f"Failed to write image to {file_path}")

    height, width = frame.shape[:2]
    file_size = file_path.stat().st_size

    # Generate thumbnail via Pillow
    pil_image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    pil_image.thumbnail((THUMBNAIL_MAX_SIZE, THUMBNAIL_MAX_SIZE))
    pil_image.save(str(thumb_path), "JPEG")

    # Return paths relative to base_path
    rel_file = str(file_path.relative_to(base_path))
    rel_thumb = str(thumb_path.relative_to(base_path))

    return StoredImage(
        filename=filename,
        file_path=rel_file,
        thumbnail_path=rel_thumb,
        width=width,
        height=height,
        file_size_bytes=file_size,
    )


async def save_image(
    frame: Any,
    base_path: Path,
    sample_id: str,
) -> StoredImage:
    """Save an image frame to disk and generate a thumbnail."""
    return await asyncio.to_thread(_save_sync, frame, base_path, sample_id)
