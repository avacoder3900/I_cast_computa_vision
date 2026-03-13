"""Image collection Pydantic models."""

from datetime import datetime

from pydantic import BaseModel, Field


class CartridgeTag(BaseModel):
    """Links an image to a BIMS cartridge record and manufacturing phase."""

    cartridge_record_id: str
    phase: str = Field(
        ...,
        description=(
            "Manufacturing phase when photo was taken, e.g. "
            "backing, wax_filled, reagent_filled, inspected, sealed"
        ),
    )
    labels: list[str] = Field(default_factory=list)
    notes: str = ""


class ImageCreate(BaseModel):
    """Internal model for creating an image document (not an API request body)."""

    sample_id: str
    filename: str
    file_path: str
    thumbnail_path: str
    width: int
    height: int
    file_size_bytes: int
    camera_index: int
    metadata: dict[str, object] = Field(default_factory=dict)
    captured_at: datetime
    image_url: str = ""
    cartridge_tag: CartridgeTag | None = None


class ImageInDB(BaseModel):
    """Internal representation of an image document from MongoDB."""

    id: str
    sample_id: str
    filename: str
    file_path: str
    thumbnail_path: str
    width: int
    height: int
    file_size_bytes: int
    camera_index: int
    metadata: dict[str, object]
    captured_at: datetime
    image_url: str = ""
    cartridge_tag: CartridgeTag | None = None


class ImageResponse(BaseModel):
    """API response for an image."""

    id: str
    sample_id: str
    filename: str
    file_path: str
    thumbnail_path: str
    width: int
    height: int
    file_size_bytes: int
    camera_index: int
    metadata: dict[str, object]
    captured_at: datetime
    image_url: str = ""
    cartridge_tag: CartridgeTag | None = None
