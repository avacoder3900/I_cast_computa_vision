"""Tests for cloud storage service."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from icast_cv.config import Settings


def _r2_settings() -> Settings:
    """Return settings with R2 configured."""
    return Settings(
        r2_account_id="test-account",
        r2_access_key_id="test-key-id",
        r2_secret_access_key="test-secret",
        r2_bucket_name="test-bucket",
        r2_public_url="https://pub-test.r2.dev",
    )


def test_r2_configured_flag() -> None:
    """Settings.r2_configured is True when R2 credentials are set."""
    s = _r2_settings()
    assert s.r2_configured is True


def test_r2_not_configured_by_default() -> None:
    """Settings.r2_configured is False with defaults."""
    s = Settings()
    assert s.r2_configured is False


@pytest.mark.asyncio
async def test_upload_file(tmp_path: Path) -> None:
    """upload_file calls boto3 and returns a public URL."""
    from icast_cv.services.cloud_storage_service import upload_file

    local_file = tmp_path / "img.jpg"
    local_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 50)

    mock_client = MagicMock()

    with patch("boto3.client", return_value=mock_client):
        url = await upload_file(local_file, "sample1/img.jpg", _r2_settings())

    assert url == "https://pub-test.r2.dev/sample1/img.jpg"
    mock_client.upload_file.assert_called_once()


@pytest.mark.asyncio
async def test_download_file(tmp_path: Path) -> None:
    """download_file calls boto3 and returns the dest path."""
    from icast_cv.services.cloud_storage_service import download_file

    mock_client = MagicMock()
    dest = tmp_path / "downloaded.jpg"

    with patch("boto3.client", return_value=mock_client):
        result = await download_file("sample1/img.jpg", dest, _r2_settings())

    assert result == dest
    mock_client.download_file.assert_called_once()
