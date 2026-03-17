"""Inspection collection CRUD operations."""

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from icast_cv.exceptions import NotFoundError
from icast_cv.models.inspection import (
    InspectionCreate,
    InspectionInDB,
    InspectionResult,
)


def _doc_to_inspection(doc: dict[str, Any]) -> InspectionInDB:
    """Convert a raw MongoDB document to an InspectionInDB model."""
    return InspectionInDB(
        id=str(doc["_id"]),
        sample_id=doc["sample_id"],
        image_id=doc["image_id"],
        project_id=doc.get("project_id", ""),
        inspection_type=doc["inspection_type"],
        status=doc["status"],
        result=doc.get("result"),
        confidence_score=doc.get("confidence_score"),
        defects=doc.get("defects", []),
        model_version=doc.get("model_version", ""),
        processing_time_ms=doc.get("processing_time_ms"),
        created_at=doc["created_at"],
        completed_at=doc.get("completed_at"),
        cartridge_record_id=doc.get("cartridge_record_id"),
        phase=doc.get("phase"),
    )


async def create_inspection(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    data: InspectionCreate,
) -> InspectionInDB:
    """Insert a new inspection document with status=pending."""
    now = datetime.now(timezone.utc)
    doc: dict[str, Any] = {
        "sample_id": data.sample_id,
        "image_id": data.image_id,
        "project_id": data.project_id,
        "inspection_type": data.inspection_type,
        "status": "pending",
        "result": None,
        "confidence_score": None,
        "defects": [],
        "model_version": "",
        "processing_time_ms": None,
        "created_at": now,
        "completed_at": None,
        "cartridge_record_id": data.cartridge_record_id,
        "phase": data.phase,
    }
    result = await db.inspections.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_inspection(doc)


async def get_inspection(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    inspection_id: str,
) -> InspectionInDB:
    """Get an inspection by ID. Raises NotFoundError if not found."""
    if not ObjectId.is_valid(inspection_id):
        raise NotFoundError(f"Inspection {inspection_id} not found")
    doc = await db.inspections.find_one({"_id": ObjectId(inspection_id)})
    if doc is None:
        raise NotFoundError(f"Inspection {inspection_id} not found")
    return _doc_to_inspection(doc)


async def list_all_inspections(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    sample_id: str | None = None,
    cartridge_id: str | None = None,
    phase: str | None = None,
    result: str | None = None,
    project_id: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[InspectionInDB]:
    """List inspections with optional filters and pagination."""
    query: dict[str, Any] = {}
    if sample_id is not None:
        query["sample_id"] = sample_id
    if cartridge_id is not None:
        query["cartridge_record_id"] = cartridge_id
    if phase is not None:
        query["phase"] = phase
    if result is not None:
        query["result"] = result
    if project_id is not None:
        query["project_id"] = project_id
    cursor = (
        db.inspections.find(query)
        .skip(skip)
        .limit(limit)
        .sort("created_at", -1)
    )
    docs: list[dict[str, Any]] = await cursor.to_list(length=limit)
    return [_doc_to_inspection(d) for d in docs]


async def get_inspection_stats(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> dict[str, Any]:
    """Get aggregate inspection statistics."""
    total = await db.inspections.count_documents({})
    pass_count = await db.inspections.count_documents({"result": "pass"})
    fail_count = await db.inspections.count_documents({"result": "fail"})
    pending = await db.inspections.count_documents({"status": "pending"})
    processing = await db.inspections.count_documents({"status": "processing"})
    total_images = await db.images.count_documents({})
    cursor = db.inspections.find().sort("created_at", -1).limit(10)
    recent_docs: list[dict[str, Any]] = await cursor.to_list(length=10)
    recent = [_doc_to_inspection(d) for d in recent_docs]
    return {
        "total_inspections": total,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "pending_count": pending,
        "processing_count": processing,
        "total_images": total_images,
        "pass_rate": round(pass_count / total * 100, 1) if total > 0 else 0,
        "recent_inspections": [r.model_dump() for r in recent],
    }


async def list_inspections_by_sample(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    sample_id: str,
    skip: int = 0,
    limit: int = 50,
) -> list[InspectionInDB]:
    """List inspections for a sample with pagination."""
    cursor = (
        db.inspections.find({"sample_id": sample_id})
        .skip(skip)
        .limit(limit)
        .sort("created_at", -1)
    )
    docs: list[dict[str, Any]] = await cursor.to_list(length=limit)
    return [_doc_to_inspection(d) for d in docs]


async def update_inspection_result(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    inspection_id: str,
    data: InspectionResult,
) -> InspectionInDB:
    """Update an inspection with CV worker results."""
    if not ObjectId.is_valid(inspection_id):
        raise NotFoundError(f"Inspection {inspection_id} not found")
    now = datetime.now(timezone.utc)
    updates: dict[str, Any] = {
        "status": "complete",
        "result": data.result,
        "confidence_score": data.confidence_score,
        "defects": [d.model_dump() for d in data.defects],
        "model_version": data.model_version,
        "processing_time_ms": data.processing_time_ms,
        "completed_at": now,
    }
    doc = await db.inspections.find_one_and_update(
        {"_id": ObjectId(inspection_id)},
        {"$set": updates},
        return_document=True,
    )
    if doc is None:
        raise NotFoundError(f"Inspection {inspection_id} not found")
    return _doc_to_inspection(doc)
