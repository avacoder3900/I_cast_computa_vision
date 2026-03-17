"""Image collection CRUD operations."""

from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from icast_cv.exceptions import NotFoundError
from icast_cv.models.image import CartridgeTag, ImageCreate, ImageInDB


def _doc_to_image(doc: dict[str, Any]) -> ImageInDB:
    """Convert a raw MongoDB document to an ImageInDB model."""
    raw_tag = doc.get("cartridge_tag")
    tag = CartridgeTag(**raw_tag) if isinstance(raw_tag, dict) else None
    return ImageInDB(
        id=str(doc["_id"]),
        sample_id=doc["sample_id"],
        project_id=doc.get("project_id", ""),
        filename=doc["filename"],
        file_path=doc["file_path"],
        thumbnail_path=doc["thumbnail_path"],
        width=doc["width"],
        height=doc["height"],
        file_size_bytes=doc["file_size_bytes"],
        camera_index=doc["camera_index"],
        metadata=doc.get("metadata", {}),
        captured_at=doc["captured_at"],
        image_url=doc.get("image_url", ""),
        cartridge_tag=tag,
        label=doc.get("label"),
    )


async def create_image(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    data: ImageCreate,
) -> ImageInDB:
    """Insert a new image document and return it."""
    doc: dict[str, Any] = data.model_dump()
    result = await db.images.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_image(doc)


async def get_image(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    image_id: str,
) -> ImageInDB:
    """Get an image by ID. Raises NotFoundError if not found."""
    if not ObjectId.is_valid(image_id):
        raise NotFoundError(f"Image {image_id} not found")
    doc = await db.images.find_one({"_id": ObjectId(image_id)})
    if doc is None:
        raise NotFoundError(f"Image {image_id} not found")
    return _doc_to_image(doc)


async def list_images(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    sample_id: str | None = None,
    cartridge_id: str | None = None,
    project_id: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[ImageInDB]:
    """List images with optional sample_id/cartridge_id/project_id filter and pagination."""
    query: dict[str, Any] = {}
    if sample_id is not None:
        query["sample_id"] = sample_id
    if cartridge_id is not None:
        query["cartridge_tag.cartridge_record_id"] = cartridge_id
    if project_id is not None:
        query["project_id"] = project_id
    cursor = db.images.find(query).skip(skip).limit(limit).sort("captured_at", -1)
    docs: list[dict[str, Any]] = await cursor.to_list(length=limit)
    return [_doc_to_image(d) for d in docs]


async def tag_image(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    image_id: str,
    tag: CartridgeTag,
) -> ImageInDB:
    """Set or replace the cartridge tag on an image. Raises NotFoundError."""
    if not ObjectId.is_valid(image_id):
        raise NotFoundError(f"Image {image_id} not found")
    doc = await db.images.find_one_and_update(
        {"_id": ObjectId(image_id)},
        {"$set": {"cartridge_tag": tag.model_dump()}},
        return_document=True,
    )
    if doc is None:
        raise NotFoundError(f"Image {image_id} not found")
    return _doc_to_image(doc)


async def label_image(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    image_id: str,
    label: str,
) -> ImageInDB:
    """Set the binary label (approved/rejected) on an image."""
    if label not in ("approved", "rejected"):
        raise ValueError("label must be 'approved' or 'rejected'")
    if not ObjectId.is_valid(image_id):
        raise NotFoundError(f"Image {image_id} not found")
    doc = await db.images.find_one_and_update(
        {"_id": ObjectId(image_id)},
        {"$set": {"label": label}},
        return_document=True,
    )
    if doc is None:
        raise NotFoundError(f"Image {image_id} not found")
    return _doc_to_image(doc)


async def delete_images_for_sample(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    sample_id: str,
) -> int:
    """Delete all images for a sample. Returns count of deleted documents."""
    result = await db.images.delete_many({"sample_id": sample_id})
    return result.deleted_count
