"""Dashboard API routes -- aggregated metrics and status overview."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.models.article import Article, ArticleStatus
from app.models.content_calendar import ContentCalendar, CalendarStatus
from app.models.pipeline_run import PipelineRun, PipelineStatus

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────


class DashboardStats(BaseModel):
    total_articles: int = 0
    articles_by_status: dict[str, int] = {}
    articles_this_month: int = 0
    pipeline_runs_today: int = 0
    pipeline_success_rate: float = 0.0
    avg_quality_scores: dict[str, float] = {}
    upcoming_calendar_entries: int = 0
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0


class AgentStatusOut(BaseModel):
    agent_name: str
    status: str  # "idle" | "running" | "error"
    last_run_at: datetime | None = None
    total_runs: int = 0
    avg_execution_time_seconds: float = 0.0


class DashboardOverview(BaseModel):
    stats: DashboardStats
    agents: list[AgentStatusOut]
    recent_articles: list[dict[str, Any]]


# ── Routes ───────────────────────────────────────────────────────────────────


@router.get("/overview", response_model=DashboardOverview)
async def get_dashboard_overview(
    session: AsyncSession = Depends(get_session),
):
    """Get the aggregated dashboard overview with key metrics."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # --- Article stats ---
    total_articles = (
        await session.execute(select(func.count(Article.id)))
    ).scalar() or 0

    status_counts = (
        await session.execute(
            select(Article.status, func.count(Article.id)).group_by(Article.status)
        )
    ).all()
    articles_by_status = {str(row[0].value) if hasattr(row[0], 'value') else str(row[0]): row[1] for row in status_counts}

    articles_this_month = (
        await session.execute(
            select(func.count(Article.id)).where(Article.created_at >= month_start)
        )
    ).scalar() or 0

    # --- Pipeline stats ---
    pipeline_runs_today = (
        await session.execute(
            select(func.count(PipelineRun.id)).where(
                PipelineRun.created_at >= today_start
            )
        )
    ).scalar() or 0

    total_runs = (
        await session.execute(
            select(func.count(PipelineRun.id)).where(
                PipelineRun.status.in_([PipelineStatus.COMPLETED.value, PipelineStatus.FAILED.value])
            )
        )
    ).scalar() or 0

    successful_runs = (
        await session.execute(
            select(func.count(PipelineRun.id)).where(
                PipelineRun.status == PipelineStatus.COMPLETED.value
            )
        )
    ).scalar() or 0

    success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0.0

    # --- Cost tracking ---
    cost_result = (
        await session.execute(
            select(
                func.coalesce(func.sum(PipelineRun.total_tokens_used), 0),
                func.coalesce(func.sum(PipelineRun.total_cost_usd), 0),
            )
        )
    ).one()
    total_tokens = int(cost_result[0])
    total_cost = float(cost_result[1])

    # --- Calendar stats ---
    upcoming_entries = (
        await session.execute(
            select(func.count(ContentCalendar.id)).where(
                ContentCalendar.status == CalendarStatus.SCHEDULED.value,
                ContentCalendar.scheduled_date >= now.date(),
            )
        )
    ).scalar() or 0

    # --- Recent articles ---
    recent_result = await session.execute(
        select(Article)
        .order_by(Article.created_at.desc())
        .limit(5)
    )
    recent_articles = [
        {
            "id": a.id,
            "title": a.title,
            "status": a.status.value if hasattr(a.status, 'value') else str(a.status),
            "language": a.language,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "quality_scores": a.quality_scores,
        }
        for a in recent_result.scalars().all()
    ]

    # --- Aggregate quality scores ---
    avg_quality = {}
    articles_with_scores = (
        await session.execute(
            select(Article.quality_scores).where(Article.quality_scores.isnot(None))
        )
    ).scalars().all()

    if articles_with_scores:
        score_keys = [
            "readability_score", "seo_score", "ai_detection_score",
            "factual_accuracy_score", "brand_consistency_score",
        ]
        for key in score_keys:
            values = [s.get(key, 0) for s in articles_with_scores if isinstance(s, dict)]
            if values:
                avg_quality[key] = round(sum(values) / len(values), 1)

    # --- Agent status (derived from pipeline step logs) ---
    agents = _build_agent_status()

    stats = DashboardStats(
        total_articles=total_articles,
        articles_by_status=articles_by_status,
        articles_this_month=articles_this_month,
        pipeline_runs_today=pipeline_runs_today,
        pipeline_success_rate=round(success_rate, 1),
        avg_quality_scores=avg_quality,
        upcoming_calendar_entries=upcoming_entries,
        total_tokens_used=total_tokens,
        total_cost_usd=round(total_cost, 4),
    )

    return DashboardOverview(
        stats=stats,
        agents=agents,
        recent_articles=recent_articles,
    )


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    session: AsyncSession = Depends(get_session),
):
    """Get just the dashboard statistics (lightweight)."""
    overview = await get_dashboard_overview(session=session)
    return overview.stats


def _build_agent_status() -> list[AgentStatusOut]:
    """Build a static list of agent statuses.

    In a production system this would query a Redis-backed agent registry.
    For now we return a template of all agents with idle status.
    """
    agent_names = [
        "orchestrator", "researcher", "planner",
        "writer", "editor", "localizer", "publisher",
    ]
    return [
        AgentStatusOut(
            agent_name=name,
            status="idle",
            total_runs=0,
            avg_execution_time_seconds=0.0,
        )
        for name in agent_names
    ]
