"""Sample collection Pydantic models."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class SampleCreate(BaseModel):
    """Request body for creating a sample."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")
    project: str = Field(default="")
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


class SampleUpdate(BaseModel):
    """Request body for updating a sample. All fields optional."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    project: str | None = None
    tags: list[str] | None = None
    metadata: dict[str, object] | None = None


class SampleInDB(BaseModel):
    """Internal representation of a sample document from MongoDB."""

    id: str
    name: str
    description: str
    project: str
    tags: list[str]
    metadata: dict[str, object]
    created_at: datetime
    updated_at: datetime


class SampleResponse(BaseModel):
    """API response for a sample."""

    id: str
    name: str
    description: str
    project: str
    tags: list[str]
    metadata: dict[str, object]
    created_at: datetime
    updated_at: datetime


def sample_create_to_doc(data: SampleCreate) -> dict[str, object]:
    """Convert a SampleCreate to a MongoDB-insertable dict."""
    now = datetime.now(timezone.utc)
    return {
        "name": data.name,
        "description": data.description,
        "project": data.project,
        "tags": data.tags,
        "metadata": data.metadata,
        "created_at": now,
        "updated_at": now,
    }
