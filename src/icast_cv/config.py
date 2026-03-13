"""Application configuration via environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "icast_cv"

    image_storage_path: Path = Path("data/images")

    default_camera_index: int = 0

    host: str = "0.0.0.0"
    port: int = 8000

    # CORS — comma-separated origins, or "*" for development
    cors_origins: str = "http://localhost:3000"

    # API key — set to empty string to disable auth (dev only)
    api_key: str = ""

    # Cloudflare R2 (S3-compatible) — leave empty to use local storage only
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""
    r2_public_url: str = ""

    # Training data
    training_data_path: Path = Path("data/training")

    # CV inference worker
    model_path: str = "model.onnx"
    model_input_size: int = 224
    confidence_threshold: float = 0.5

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def r2_configured(self) -> bool:
        """Return True if R2 credentials are fully configured."""
        return bool(self.r2_bucket_name and self.r2_access_key_id)

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated origins into a list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


def get_settings() -> Settings:
    """Return application settings singleton."""
    return Settings()
