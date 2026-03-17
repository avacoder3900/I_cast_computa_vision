"""Project collection CRUD operations."""

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from icast_cv.exceptions import NotFoundError
from icast_cv.models.project import (
    ProjectCreate,
    ProjectInDB,
    ProjectUpdate,
    project_create_to_doc,
)


def _doc_to_project(doc: dict[str, Any]) -> ProjectInDB:
    """Convert a raw MongoDB document to a ProjectInDB model."""
    return ProjectInDB(
        id=str(doc["_id"]),
        name=doc["name"],
        description=doc.get("description", ""),
        project_type=doc.get("project_type", "classification"),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
        image_count=doc.get("image_count", 0),
        annotated_count=doc.get("annotated_count", 0),
        model_status=doc.get("model_status", "untrained"),
        model_version=doc.get("model_version"),
        tags=doc.get("tags", []),
        phases=doc.get("phases", []),
        labels=doc.get("labels", []),
    )


async def create_project(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    data: ProjectCreate,
) -> ProjectInDB:
    """Insert a new project and return it."""
    doc = project_create_to_doc(data)
    result = await db.projects.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_project(doc)


async def get_project(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    project_id: str,
) -> ProjectInDB:
    """Get a project by ID. Raises NotFoundError if not found."""
    if not ObjectId.is_valid(project_id):
        raise NotFoundError(f"Project {project_id} not found")
    doc = await db.projects.find_one({"_id": ObjectId(project_id)})
    if doc is None:
        raise NotFoundError(f"Project {project_id} not found")
    return _doc_to_project(doc)


async def list_projects(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    skip: int = 0,
    limit: int = 50,
    sort_by: str = "created_at",
    sort_order: int = -1,
    search: str | None = None,
) -> tuple[list[ProjectInDB], int]:
    """List projects with pagination, sorting, and optional search. Returns (projects, total)."""
    query: dict[str, Any] = {}
    if search:
        query["name"] = {"$regex": search, "$options": "i"}

    total = await db.projects.count_documents(query)
    cursor = db.projects.find(query).skip(skip).limit(limit).sort(sort_by, sort_order)
    docs: list[dict[str, Any]] = await cursor.to_list(length=limit)
    return [_doc_to_project(d) for d in docs], total


async def update_project(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    project_id: str,
    data: ProjectUpdate,
) -> ProjectInDB:
    """Update a project. Raises NotFoundError if not found."""
    if not ObjectId.is_valid(project_id):
        raise NotFoundError(f"Project {project_id} not found")
    updates: dict[str, Any] = data.model_dump(exclude_none=True)
    # Serialize label objects to dicts for MongoDB
    if "labels" in updates:
        updates["labels"] = [
            l.model_dump() if hasattr(l, "model_dump") else l for l in updates["labels"]
        ]
    if not updates:
        return await get_project(db, project_id)
    updates["updated_at"] = datetime.now(timezone.utc)
    result = await db.projects.find_one_and_update(
        {"_id": ObjectId(project_id)},
        {"$set": updates},
        return_document=True,
    )
    if result is None:
        raise NotFoundError(f"Project {project_id} not found")
    return _doc_to_project(result)


async def delete_project(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    project_id: str,
) -> bool:
    """Delete a project by ID. Returns True if deleted."""
    if not ObjectId.is_valid(project_id):
        raise NotFoundError(f"Project {project_id} not found")
    result = await db.projects.delete_one({"_id": ObjectId(project_id)})
    if result.deleted_count == 0:
        raise NotFoundError(f"Project {project_id} not found")
    return True


async def duplicate_project(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    project_id: str,
) -> ProjectInDB:
    """Duplicate a project (copies metadata, resets counts)."""
    source = await get_project(db, project_id)
    create_data = ProjectCreate(
        name=f"{source.name} (copy)",
        description=source.description,
        project_type=source.project_type,
        tags=source.tags,
        phases=source.phases,
        labels=source.labels,
    )
    return await create_project(db, create_data)
