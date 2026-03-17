"""Project collection Pydantic models."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


# Global BIMS manufacturing phase labels available across all projects.
BIMS_PHASE_LABELS: list[str] = [
    "backing",
    "wax_filled",
    "wax_qc",
    "wax_stored",
    "reagent_filled",
    "inspected",
    "sealed",
    "cured",
    "stored",
    "released",
    "shipped",
    "assay_loaded",
    "testing",
    "completed",
    "voided",
]


class LabelDefinition(BaseModel):
    """A label/tag definition for a project."""

    name: str = Field(..., min_length=1, max_length=100)
    color: str = Field(default="#6366f1", pattern="^#[0-9a-fA-F]{6}$")


class ProjectCreate(BaseModel):
    """Request body for creating a project."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="")
    project_type: str = Field(
        default="classification",
        pattern="^(classification|anomaly_detection|object_detection)$",
    )
    tags: list[str] = Field(default_factory=list)
    phases: list[str] = Field(default_factory=list)
    labels: list[LabelDefinition] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    """Request body for updating a project. All fields optional."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    project_type: str | None = Field(
        default=None,
        pattern="^(classification|anomaly_detection|object_detection)$",
    )
    tags: list[str] | None = None
    phases: list[str] | None = None
    labels: list[LabelDefinition] | None = None
    model_status: str | None = Field(
        default=None,
        pattern="^(untrained|training|trained|failed)$",
    )
    model_version: str | None = None


class ProjectInDB(BaseModel):
    """Internal representation of a project document from MongoDB."""

    id: str
    name: str
    description: str
    project_type: str
    created_at: datetime
    updated_at: datetime
    image_count: int
    annotated_count: int
    model_status: str
    model_version: str | None = None
    tags: list[str]
    phases: list[str]
    labels: list[LabelDefinition] = Field(default_factory=list)


class ProjectResponse(BaseModel):
    """API response for a project."""

    id: str
    name: str
    description: str
    project_type: str
    created_at: datetime
    updated_at: datetime
    image_count: int
    annotated_count: int
    model_status: str
    model_version: str | None = None
    tags: list[str]
    phases: list[str]
    labels: list[LabelDefinition] = Field(default_factory=list)


def project_create_to_doc(data: ProjectCreate) -> dict[str, object]:
    """Convert a ProjectCreate to a MongoDB-insertable dict."""
    now = datetime.now(timezone.utc)
    return {
        "name": data.name,
        "description": data.description,
        "project_type": data.project_type,
        "created_at": now,
        "updated_at": now,
        "image_count": 0,
        "annotated_count": 0,
        "model_status": "untrained",
        "model_version": None,
        "tags": data.tags,
        "phases": data.phases,
        "labels": [l.model_dump() for l in data.labels],
    }
