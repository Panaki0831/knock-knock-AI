"""Pipeline execution API routes."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session, async_session_factory
from app.models.pipeline_run import PipelineRun, PipelineStatus
from app.services import trigger_pipeline

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────


class PipelineTriggerIn(BaseModel):
    calendar_entry_id: int


class PipelineTriggerOut(BaseModel):
    run_id: int
    status: str
    message: str


class PipelineRunOut(BaseModel):
    id: int
    article_id: int | None = None
    calendar_entry_id: int | None = None
    topic: str | None = None
    status: str
    current_step: str | None = None
    steps_log: list[dict[str, Any]] | None = None
    error_message: str | None = None
    retry_count: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_tokens_used: int | None = None
    total_cost_usd: float | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PipelineListOut(BaseModel):
    items: list[PipelineRunOut]
    total: int


# ── Background task helper ───────────────────────────────────────────────────


async def _run_pipeline_background(calendar_entry_id: int, run_id: int) -> None:
    """Run the pipeline in a background task with its own DB session."""
    async with async_session_factory() as session:
        try:
            await trigger_pipeline(calendar_entry_id, session, pipeline_run_id=run_id)
        except Exception as exc:
            # Log but don't propagate -- background tasks should not raise.
            import structlog

            structlog.get_logger(__name__).error(
                "background_pipeline_failed",
                calendar_entry_id=calendar_entry_id,
                run_id=run_id,
                error=str(exc),
            )


# ── Routes ───────────────────────────────────────────────────────────────────


@router.post("/trigger", response_model=PipelineTriggerOut, status_code=202)
async def trigger_pipeline_route(
    body: PipelineTriggerIn,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """Trigger the content-generation pipeline for a calendar entry.

    The pipeline runs asynchronously in the background. Use the returned
    ``run_id`` to poll for status via ``GET /api/v1/pipeline/runs/{run_id}``.
    """
    from app.models.content_calendar import ContentCalendar

    entry = await session.get(ContentCalendar, body.calendar_entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Calendar entry not found")

    # Create a placeholder pipeline run immediately
    run = PipelineRun(
        status=PipelineStatus.PENDING,
        current_step="queued",
        calendar_entry_id=body.calendar_entry_id,
        topic=entry.article_theme,
    )
    session.add(run)
    await session.flush()
    run_id = run.id
    await session.commit()

    background_tasks.add_task(_run_pipeline_background, body.calendar_entry_id, run_id)

    return PipelineTriggerOut(
        run_id=run_id,
        status="pending",
        message=f"Pipeline queued for calendar entry {body.calendar_entry_id}",
    )


@router.get("/runs", response_model=PipelineListOut)
async def list_pipeline_runs(
    status: str | None = None,
    limit: int = 20,
    session: AsyncSession = Depends(get_session),
):
    """List pipeline runs with optional status filter."""
    query = select(PipelineRun)
    if status:
        query = query.where(PipelineRun.status == status)

    query = query.order_by(PipelineRun.created_at.desc()).limit(limit)
    result = await session.execute(query)
    runs = result.scalars().all()

    return PipelineListOut(
        items=[PipelineRunOut.model_validate(r) for r in runs],
        total=len(runs),
    )


@router.get("/runs/{run_id}", response_model=PipelineRunOut)
async def get_pipeline_run(
    run_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get details of a specific pipeline run."""
    run = await session.get(PipelineRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return PipelineRunOut.model_validate(run)


@router.delete("/runs/failed", status_code=200)
async def delete_failed_runs(
    session: AsyncSession = Depends(get_session),
):
    """Delete all failed pipeline runs to clean up the list."""
    from sqlalchemy import delete

    result = await session.execute(
        delete(PipelineRun).where(PipelineRun.status == PipelineStatus.FAILED)
    )
    await session.commit()
    return {"deleted": result.rowcount}


@router.delete("/runs/{run_id}", status_code=200)
async def delete_pipeline_run(
    run_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Delete a single pipeline run by ID."""
    run = await session.get(PipelineRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    await session.delete(run)
    await session.commit()
    return {"deleted": run_id}
