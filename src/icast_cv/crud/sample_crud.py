"""Sample collection CRUD operations."""

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from icast_cv.exceptions import NotFoundError
from icast_cv.models.sample import (
    SampleCreate,
    SampleInDB,
    SampleUpdate,
    sample_create_to_doc,
)


def _doc_to_sample(doc: dict[str, Any]) -> SampleInDB:
    """Convert a raw MongoDB document to a SampleInDB model."""
    return SampleInDB(
        id=str(doc["_id"]),
        name=doc["name"],
        description=doc.get("description", ""),
        project=doc.get("project", ""),
        tags=doc.get("tags", []),
        metadata=doc.get("metadata", {}),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


async def create_sample(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    data: SampleCreate,
) -> SampleInDB:
    """Insert a new sample and return it."""
    doc = sample_create_to_doc(data)
    result = await db.samples.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_sample(doc)


async def get_sample(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    sample_id: str,
) -> SampleInDB:
    """Get a sample by ID. Raises NotFoundError if not found."""
    if not ObjectId.is_valid(sample_id):
        raise NotFoundError(f"Sample {sample_id} not found")
    doc = await db.samples.find_one({"_id": ObjectId(sample_id)})
    if doc is None:
        raise NotFoundError(f"Sample {sample_id} not found")
    return _doc_to_sample(doc)


async def list_samples(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    skip: int = 0,
    limit: int = 50,
) -> list[SampleInDB]:
    """List samples with pagination."""
    cursor = db.samples.find().skip(skip).limit(limit).sort("created_at", -1)
    docs: list[dict[str, Any]] = await cursor.to_list(length=limit)
    return [_doc_to_sample(d) for d in docs]


async def update_sample(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    sample_id: str,
    data: SampleUpdate,
) -> SampleInDB:
    """Update a sample. Raises NotFoundError if not found."""
    if not ObjectId.is_valid(sample_id):
        raise NotFoundError(f"Sample {sample_id} not found")
    updates: dict[str, Any] = data.model_dump(exclude_none=True)
    if not updates:
        return await get_sample(db, sample_id)
    updates["updated_at"] = datetime.now(timezone.utc)
    result = await db.samples.find_one_and_update(
        {"_id": ObjectId(sample_id)},
        {"$set": updates},
        return_document=True,
    )
    if result is None:
        raise NotFoundError(f"Sample {sample_id} not found")
    return _doc_to_sample(result)


async def delete_sample(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    sample_id: str,
) -> bool:
    """Delete a sample by ID. Returns True if deleted."""
    if not ObjectId.is_valid(sample_id):
        raise NotFoundError(f"Sample {sample_id} not found")
    result = await db.samples.delete_one({"_id": ObjectId(sample_id)})
    if result.deleted_count == 0:
        raise NotFoundError(f"Sample {sample_id} not found")
    return True
