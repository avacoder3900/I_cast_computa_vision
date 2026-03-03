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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated origins into a list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


def get_settings() -> Settings:
    """Return application settings singleton."""
    return Settings()
