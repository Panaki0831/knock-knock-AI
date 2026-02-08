"""Image asset API routes -- manage generated and uploaded images."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.models.image_asset import ImageAsset
from app.services.image_generator import save_uploaded_image

router = APIRouter()

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20 MB


# ── Schemas ──────────────────────────────────────────────────────────────────


class ImageAssetOut(BaseModel):
    id: int
    filename: str
    mime_type: str
    file_size: int
    width: int | None = None
    height: int | None = None
    source: str
    tags: list[str] | None = None
    description: str | None = None
    generation_prompt: str | None = None
    generation_model: str | None = None
    article_id: int | None = None
    section_heading: str | None = None
    is_knowledge_base: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ImageAssetListOut(BaseModel):
    items: list[ImageAssetOut]
    total: int


class ImageTagsUpdateIn(BaseModel):
    tags: list[str]
    description: str | None = None


# ── Routes ───────────────────────────────────────────────────────────────────


@router.get("", response_model=ImageAssetListOut)
async def list_images(
    source: str | None = Query(None, description="Filter by source: generated, uploaded"),
    is_knowledge_base: bool | None = Query(None),
    tag: str | None = Query(None, description="Filter by tag"),
    session: AsyncSession = Depends(get_session),
):
    """List all image assets with optional filters."""
    query = select(ImageAsset)
    count_query = select(func.count()).select_from(ImageAsset)

    if source:
        query = query.where(ImageAsset.source == source)
        count_query = count_query.where(ImageAsset.source == source)
    if is_knowledge_base is not None:
        query = query.where(ImageAsset.is_knowledge_base == is_knowledge_base)
        count_query = count_query.where(ImageAsset.is_knowledge_base == is_knowledge_base)

    total = (await session.execute(count_query)).scalar() or 0

    query = query.order_by(ImageAsset.created_at.desc())
    result = await session.execute(query)
    images = result.scalars().all()

    # If tag filter, do it in Python (JSON array filtering in PG is complex)
    if tag:
        tag_lower = tag.lower()
        images = [
            img for img in images
            if img.tags and any(tag_lower in t.lower() for t in img.tags)
        ]
        total = len(images)

    return ImageAssetListOut(
        items=[ImageAssetOut.model_validate(img) for img in images],
        total=total,
    )


@router.get("/{image_id}/file")
async def get_image_file(
    image_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Serve the actual image file."""
    image = await session.get(ImageAsset, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")
    if not os.path.exists(image.file_path):
        raise HTTPException(status_code=404, detail="Image file not found on disk")
    return FileResponse(image.file_path, media_type=image.mime_type)


@router.post("", response_model=ImageAssetOut, status_code=201)
async def upload_image(
    file: UploadFile = File(...),
    tags: str = Form(""),
    description: str = Form(""),
    is_knowledge_base: bool = Form(False),
    session: AsyncSession = Depends(get_session),
):
    """Upload an image to the gallery or knowledge base."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Validate extension
    ext = ""
    for e in ALLOWED_IMAGE_EXTENSIONS:
        if file.filename.lower().endswith(e):
            ext = e
            break
    if not ext:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image type. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}",
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail="Image too large (max 20 MB)")

    # Determine MIME type
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    mime_type = mime_map.get(ext, "image/png")

    # Save file
    file_path, stored_filename = save_uploaded_image(file_bytes, file.filename)

    # Parse tags
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    image = ImageAsset(
        filename=file.filename,
        file_path=file_path,
        mime_type=mime_type,
        file_size=len(file_bytes),
        source="uploaded",
        tags=tag_list if tag_list else None,
        description=description or None,
        is_knowledge_base=is_knowledge_base,
    )
    session.add(image)
    await session.flush()

    return ImageAssetOut.model_validate(image)


@router.patch("/{image_id}/tags", response_model=ImageAssetOut)
async def update_image_tags(
    image_id: int,
    body: ImageTagsUpdateIn,
    session: AsyncSession = Depends(get_session),
):
    """Update tags and description for an image."""
    image = await session.get(ImageAsset, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")
    image.tags = body.tags
    if body.description is not None:
        image.description = body.description
    await session.flush()
    return ImageAssetOut.model_validate(image)


@router.delete("/{image_id}", status_code=200)
async def delete_image(
    image_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Delete an image asset."""
    image = await session.get(ImageAsset, image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")

    # Remove file from disk
    if os.path.exists(image.file_path):
        os.remove(image.file_path)

    await session.delete(image)
    await session.commit()
    return {"deleted": image_id}
