"""Content calendar API routes."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.models.article import FunnelStage
from app.models.content_calendar import (
    CalendarPriority,
    CalendarStatus,
    ContentCalendar,
)

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────


class CalendarEntryIn(BaseModel):
    scheduled_date: date
    article_theme: str = Field(..., min_length=1, max_length=500)
    target_keywords: list[str] | None = None
    category: str | None = None
    funnel_stage: str | None = None
    language: str = "ja"
    target_platform: str | None = "note"
    assigned_persona: str | None = None
    priority: str = "medium"
    notes: str | None = None


class CalendarEntryOut(BaseModel):
    id: int
    scheduled_date: date
    article_theme: str
    target_keywords: list[str] | None = None
    category: str | None = None
    funnel_stage: str | None = None
    language: str
    target_platform: str | None = None
    assigned_persona: str | None = None
    priority: str
    status: str
    article_id: int | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CalendarListOut(BaseModel):
    items: list[CalendarEntryOut]
    total: int


class CalendarEntryUpdateIn(BaseModel):
    scheduled_date: date | None = None
    article_theme: str | None = None
    target_keywords: list[str] | None = None
    category: str | None = None
    funnel_stage: str | None = None
    language: str | None = None
    target_platform: str | None = None
    assigned_persona: str | None = None
    priority: str | None = None
    notes: str | None = None


# ── Routes ───────────────────────────────────────────────────────────────────


@router.get("", response_model=CalendarListOut)
async def list_calendar_entries(
    start_date: date | None = None,
    end_date: date | None = None,
    status: str | None = None,
    language: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    """List calendar entries with optional date range and filters."""
    query = select(ContentCalendar)

    if start_date:
        query = query.where(ContentCalendar.scheduled_date >= start_date)
    if end_date:
        query = query.where(ContentCalendar.scheduled_date <= end_date)
    if status:
        query = query.where(ContentCalendar.status == status)
    if language:
        query = query.where(ContentCalendar.language == language)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_q)).scalar() or 0

    query = query.order_by(ContentCalendar.scheduled_date.asc())
    result = await session.execute(query)
    entries = result.scalars().all()

    return CalendarListOut(
        items=[CalendarEntryOut.model_validate(e) for e in entries],
        total=total,
    )


@router.post("", response_model=CalendarEntryOut, status_code=201)
async def create_calendar_entry(
    body: CalendarEntryIn,
    session: AsyncSession = Depends(get_session),
):
    """Create a new content calendar entry."""
    entry = ContentCalendar(
        scheduled_date=body.scheduled_date,
        article_theme=body.article_theme,
        target_keywords=body.target_keywords,
        category=body.category,
        funnel_stage=FunnelStage(body.funnel_stage) if body.funnel_stage else None,
        language=body.language,
        target_platform=body.target_platform,
        assigned_persona=body.assigned_persona,
        priority=CalendarPriority(body.priority),
        notes=body.notes,
    )
    session.add(entry)
    await session.flush()
    return CalendarEntryOut.model_validate(entry)


@router.get("/{entry_id}", response_model=CalendarEntryOut)
async def get_calendar_entry(
    entry_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get a single calendar entry."""
    entry = await session.get(ContentCalendar, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Calendar entry not found")
    return CalendarEntryOut.model_validate(entry)


@router.patch("/{entry_id}", response_model=CalendarEntryOut)
async def update_calendar_entry(
    entry_id: int,
    body: CalendarEntryUpdateIn,
    session: AsyncSession = Depends(get_session),
):
    """Update a calendar entry."""
    entry = await session.get(ContentCalendar, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Calendar entry not found")

    if body.scheduled_date is not None:
        entry.scheduled_date = body.scheduled_date
    if body.article_theme is not None:
        entry.article_theme = body.article_theme
    if body.target_keywords is not None:
        entry.target_keywords = body.target_keywords
    if body.category is not None:
        entry.category = body.category
    if body.funnel_stage is not None:
        entry.funnel_stage = FunnelStage(body.funnel_stage)
    if body.language is not None:
        entry.language = body.language
    if body.target_platform is not None:
        entry.target_platform = body.target_platform
    if body.assigned_persona is not None:
        entry.assigned_persona = body.assigned_persona
    if body.priority is not None:
        entry.priority = CalendarPriority(body.priority)
    if body.notes is not None:
        entry.notes = body.notes

    entry.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return CalendarEntryOut.model_validate(entry)


@router.delete("/{entry_id}", status_code=204)
async def delete_calendar_entry(
    entry_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Delete a calendar entry."""
    entry = await session.get(ContentCalendar, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Calendar entry not found")
    await session.delete(entry)
    await session.flush()
