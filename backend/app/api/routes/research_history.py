"""Research History API routes -- view and manage past research results."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.models.research_history import ResearchHistory

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────


class ResearchHistoryOut(BaseModel):
    id: int
    pipeline_run_id: int | None = None
    topic: str
    target_keywords: list[str] | None = None
    research_report: str | None = None
    key_statistics: list[dict[str, Any]] | None = None
    sources: list[str] | None = None
    competitor_insights: str | None = None
    market_data: str | None = None
    created_at: datetime
    expires_at: datetime

    model_config = {"from_attributes": True}


class ResearchHistorySummaryOut(BaseModel):
    id: int
    pipeline_run_id: int | None = None
    topic: str
    target_keywords: list[str] | None = None
    source_count: int
    stat_count: int
    created_at: datetime
    expires_at: datetime


class ResearchHistoryListOut(BaseModel):
    items: list[ResearchHistorySummaryOut]
    total: int


# ── Routes ───────────────────────────────────────────────────────────────────


@router.get("", response_model=ResearchHistoryListOut)
async def list_research_history(
    session: AsyncSession = Depends(get_session),
):
    """List all research history entries (summaries only)."""
    count_q = select(func.count()).select_from(ResearchHistory)
    total = (await session.execute(count_q)).scalar() or 0

    query = select(ResearchHistory).order_by(ResearchHistory.created_at.desc())
    result = await session.execute(query)
    entries = result.scalars().all()

    items = []
    for e in entries:
        items.append(
            ResearchHistorySummaryOut(
                id=e.id,
                pipeline_run_id=e.pipeline_run_id,
                topic=e.topic,
                target_keywords=e.target_keywords,
                source_count=len(e.sources) if e.sources else 0,
                stat_count=len(e.key_statistics) if e.key_statistics else 0,
                created_at=e.created_at,
                expires_at=e.expires_at,
            )
        )

    return ResearchHistoryListOut(items=items, total=total)


@router.get("/{entry_id}", response_model=ResearchHistoryOut)
async def get_research_history(
    entry_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get the full details of a research history entry."""
    entry = await session.get(ResearchHistory, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Research history entry not found")
    return ResearchHistoryOut.model_validate(entry)


@router.delete("/{entry_id}", status_code=200)
async def delete_research_history(
    entry_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Delete a research history entry."""
    entry = await session.get(ResearchHistory, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Research history entry not found")
    await session.delete(entry)
    await session.commit()
    return {"deleted": entry_id}
