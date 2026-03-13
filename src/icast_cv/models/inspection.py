"""Inspection collection Pydantic models."""

from datetime import datetime

from pydantic import BaseModel, Field


class Defect(BaseModel):
    """A single defect found during inspection."""

    type: str
    location: str
    severity: str


class InspectionCreate(BaseModel):
    """Request body for creating an inspection."""

    sample_id: str
    image_id: str
    inspection_type: str = Field(..., min_length=1)


class InspectionResult(BaseModel):
    """Request body for posting inspection results (from CV worker)."""

    result: str = Field(..., pattern="^(pass|fail)$")
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    defects: list[Defect] = Field(default_factory=list)
    model_version: str = ""
    processing_time_ms: int | None = None


class InspectionInDB(BaseModel):
    """Internal representation of an inspection document from MongoDB."""

    id: str
    sample_id: str
    image_id: str
    inspection_type: str
    status: str
    result: str | None = None
    confidence_score: float | None = None
    defects: list[Defect] = Field(default_factory=list)
    model_version: str = ""
    processing_time_ms: int | None = None
    created_at: datetime
    completed_at: datetime | None = None


class InspectionResponse(BaseModel):
    """API response for an inspection."""

    id: str
    sample_id: str
    image_id: str
    inspection_type: str
    status: str
    result: str | None = None
    confidence_score: float | None = None
    defects: list[Defect] = Field(default_factory=list)
    model_version: str = ""
    processing_time_ms: int | None = None
    created_at: datetime
    completed_at: datetime | None = None
