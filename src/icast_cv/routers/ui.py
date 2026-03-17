"""UI page routes — serves Jinja2 templates for the admin dashboard."""

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from motor.motor_asyncio import AsyncIOMotorDatabase

from icast_cv.crud.inspection_crud import get_inspection_stats
from icast_cv.crud.project_crud import get_project
from icast_cv.db import get_database
from icast_cv.exceptions import NotFoundError

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))

router = APIRouter(tags=["ui"], include_in_schema=False)

DB = Annotated[AsyncIOMotorDatabase, Depends(get_database)]


@router.get("/ui/", response_class=HTMLResponse)
async def projects_landing(request: Request, db: DB) -> HTMLResponse:
    """Projects landing page — list all projects."""
    return templates.TemplateResponse("projects.html", {"request": request})


@router.get("/ui/project/{project_id}", response_class=HTMLResponse)
async def project_detail(request: Request, project_id: str, db: DB) -> HTMLResponse:
    """Project detail page with tabs."""
    try:
        project = await get_project(db, project_id)
    except NotFoundError:
        return templates.TemplateResponse(
            "projects.html",
            {"request": request},
            status_code=404,
        )
    return templates.TemplateResponse(
        "project_detail.html",
        {"request": request, "project": project.model_dump(mode="json")},
    )


@router.get("/ui/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: DB) -> HTMLResponse:
    """Legacy dashboard overview page."""
    try:
        stats = await get_inspection_stats(db)
    except Exception:
        stats = {
            "total_inspections": 0,
            "pass_count": 0,
            "fail_count": 0,
            "pending_count": 0,
            "processing_count": 0,
            "total_images": 0,
            "pass_rate": 0,
            "recent_inspections": [],
        }
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "stats": stats},
    )


@router.get("/ui/capture", response_class=HTMLResponse)
async def capture_page(request: Request) -> HTMLResponse:
    """Capture & Inspect page."""
    return templates.TemplateResponse("capture.html", {"request": request})


@router.get("/ui/training", response_class=HTMLResponse)
async def training_page(request: Request) -> HTMLResponse:
    """Training Manager page."""
    return templates.TemplateResponse("training.html", {"request": request})


@router.get("/ui/inspections", response_class=HTMLResponse)
async def inspections_page(request: Request) -> HTMLResponse:
    """Inspection History page."""
    return templates.TemplateResponse("inspections.html", {"request": request})


@router.get("/ui/gallery", response_class=HTMLResponse)
async def gallery_page(request: Request) -> HTMLResponse:
    """Photo Gallery page."""
    return templates.TemplateResponse("gallery.html", {"request": request})


@router.get("/ui/cartridge/{cartridge_id}", response_class=HTMLResponse)
async def cartridge_page(request: Request, cartridge_id: str) -> HTMLResponse:
    """Cartridge detail view page."""
    return templates.TemplateResponse(
        "cartridge.html",
        {"request": request, "cartridge_id": cartridge_id},
    )
