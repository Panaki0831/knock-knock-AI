"""Knowledge Base API routes -- upload and manage documents."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.models.knowledge_document import KnowledgeDocument
from app.services.document_parser import parse_document

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".pptx", ".docx"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


# ── Schemas ──────────────────────────────────────────────────────────────────


class KnowledgeDocumentOut(BaseModel):
    id: int
    filename: str
    file_type: str
    file_size: int
    description: str | None = None
    category: str | None = None
    page_count: int
    content_preview: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeDocumentContentOut(BaseModel):
    id: int
    filename: str
    content_text: str | None = None

    model_config = {"from_attributes": True}


class KnowledgeDocumentListOut(BaseModel):
    items: list[KnowledgeDocumentOut]
    total: int


# ── Routes ───────────────────────────────────────────────────────────────────


@router.post("", response_model=KnowledgeDocumentOut, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    description: str | None = None,
    category: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Upload a document (pdf, pptx, docx) to the knowledge base."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Validate extension
    ext = ""
    for e in ALLOWED_EXTENSIONS:
        if file.filename.lower().endswith(e):
            ext = e
            break
    if not ext:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read file content
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 50 MB)")

    # Parse the document
    try:
        result = parse_document(file_bytes, file.filename)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse document: {exc}")

    # Store in DB
    doc = KnowledgeDocument(
        filename=file.filename,
        file_type=ext.lstrip("."),
        file_size=len(file_bytes),
        content_text=result.text,
        description=description,
        category=category,
        page_count=result.page_count,
    )
    session.add(doc)
    await session.flush()

    return _to_out(doc)


@router.get("", response_model=KnowledgeDocumentListOut)
async def list_documents(
    session: AsyncSession = Depends(get_session),
):
    """List all knowledge base documents."""
    count_q = select(func.count()).select_from(KnowledgeDocument)
    total = (await session.execute(count_q)).scalar() or 0

    query = select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc())
    result = await session.execute(query)
    docs = result.scalars().all()

    return KnowledgeDocumentListOut(
        items=[_to_out(d) for d in docs],
        total=total,
    )


@router.get("/{doc_id}", response_model=KnowledgeDocumentContentOut)
async def get_document_content(
    doc_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get the full extracted text of a knowledge document."""
    doc = await session.get(KnowledgeDocument, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return KnowledgeDocumentContentOut.model_validate(doc)


@router.delete("/{doc_id}", status_code=200)
async def delete_document(
    doc_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Delete a knowledge document."""
    doc = await session.get(KnowledgeDocument, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    await session.delete(doc)
    await session.commit()
    return {"deleted": doc_id}


def _to_out(doc: KnowledgeDocument) -> KnowledgeDocumentOut:
    """Convert a KnowledgeDocument to the output schema with a content preview."""
    preview = None
    if doc.content_text:
        preview = doc.content_text[:200] + ("..." if len(doc.content_text) > 200 else "")
    return KnowledgeDocumentOut(
        id=doc.id,
        filename=doc.filename,
        file_type=doc.file_type,
        file_size=doc.file_size,
        description=doc.description,
        category=doc.category,
        page_count=doc.page_count,
        content_preview=preview,
        created_at=doc.created_at,
    )
