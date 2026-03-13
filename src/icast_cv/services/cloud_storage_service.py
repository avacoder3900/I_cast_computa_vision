"""S3-compatible cloud storage service for Cloudflare R2."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from icast_cv.config import Settings


def _get_s3_client(settings: Settings) -> Any:
    """Create a boto3 S3 client configured for Cloudflare R2."""
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
    )


def _upload_sync(local_path: Path, key: str, settings: Settings) -> str:
    """Upload a file to R2 and return the public URL."""
    client = _get_s3_client(settings)
    client.upload_file(
        str(local_path),
        settings.r2_bucket_name,
        key,
        ExtraArgs={"ContentType": "image/jpeg"},
    )
    public_url: str = settings.r2_public_url.rstrip("/")
    return f"{public_url}/{key}"


def _download_sync(key: str, dest_path: Path, settings: Settings) -> Path:
    """Download a file from R2 to a local path."""
    client = _get_s3_client(settings)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    client.download_file(settings.r2_bucket_name, key, str(dest_path))
    return dest_path


async def upload_file(local_path: Path, key: str, settings: Settings) -> str:
    """Upload a file to R2 (async). Returns the public URL."""
    return await asyncio.to_thread(_upload_sync, local_path, key, settings)


async def download_file(key: str, dest_path: Path, settings: Settings) -> Path:
    """Download a file from R2 (async). Returns the local path."""
    return await asyncio.to_thread(_download_sync, key, dest_path, settings)
