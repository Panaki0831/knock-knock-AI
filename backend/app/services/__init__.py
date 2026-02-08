"""Pipeline service -- high-level entry point for triggering article generation."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import OrchestratorAgent
from app.models.article import Article, ArticleStatus
from app.models.content_calendar import CalendarStatus, ContentCalendar
from app.models.pipeline_run import PipelineRun, PipelineStatus

logger = structlog.get_logger(__name__)


async def trigger_pipeline(
    calendar_entry_id: int,
    session: AsyncSession,
    *,
    pipeline_run_id: int | None = None,
) -> PipelineRun:
    """Kick off the full content pipeline for a single calendar entry.

    If ``pipeline_run_id`` is given, reuse the existing :class:`PipelineRun`
    record (created by the API route as a placeholder).  Otherwise create a
    new one.
    """
    # 1. Load calendar entry
    calendar_entry = await session.get(ContentCalendar, calendar_entry_id)
    if calendar_entry is None:
        raise ValueError(f"Calendar entry {calendar_entry_id} not found")

    log = logger.bind(calendar_entry_id=calendar_entry_id)
    log.info("pipeline_trigger", theme=calendar_entry.article_theme)

    # 2. Reuse existing pipeline run or create a new one
    if pipeline_run_id is not None:
        pipeline_run = await session.get(PipelineRun, pipeline_run_id)
        if pipeline_run is None:
            raise ValueError(f"PipelineRun {pipeline_run_id} not found")
        pipeline_run.status = PipelineStatus.RUNNING
        pipeline_run.current_step = "research"
        pipeline_run.started_at = datetime.now(timezone.utc)
    else:
        pipeline_run = PipelineRun(
            status=PipelineStatus.RUNNING,
            current_step="research",
            started_at=datetime.now(timezone.utc),
            calendar_entry_id=calendar_entry_id,
            topic=calendar_entry.article_theme,
        )
        session.add(pipeline_run)
    await session.flush()

    # 3. Update calendar entry status
    calendar_entry.status = CalendarStatus.IN_PROGRESS
    await session.flush()

    # 4. Build the orchestrator input
    orchestrator_input: dict[str, Any] = {
        "calendar_entry": {
            "topic": calendar_entry.article_theme,
            "target_keywords": calendar_entry.target_keywords or [],
            "target_locales": [],
            "target_platforms": [calendar_entry.target_platform or "note"],
            "language": calendar_entry.language,
            "category": calendar_entry.category or "",
            "funnel_stage": calendar_entry.funnel_stage.value if calendar_entry.funnel_stage else "TOFU",
            "persona": calendar_entry.assigned_persona or "不動産業界関係者",
            "notes": calendar_entry.notes or "",
        }
    }

    # 5. Execute pipeline
    orchestrator = OrchestratorAgent()
    try:
        from app.agents.base import AgentContext

        context = AgentContext(
            task_id=uuid.uuid4().hex,
            article_id=str(pipeline_run.id),
            input_data=orchestrator_input,
        )
        result = await orchestrator.execute(context)

        pipeline_run.steps_log = result.output_data.get("steps", [])
        pipeline_run.total_tokens_used = result.tokens_used
        pipeline_run.total_cost_usd = result.cost_usd

        if result.success:
            # Create the article record
            final_output = result.output_data.get("final_output", {})
            article_markdown = (
                final_output.get("formatted_content")
                or final_output.get("edited_markdown")
                or final_output.get("article_markdown", "")
            )
            title = _extract_title(article_markdown) or calendar_entry.article_theme
            slug = _slugify(title, pipeline_run.id)

            article = Article(
                title=title,
                slug=slug,
                content_markdown=article_markdown,
                status=ArticleStatus.REVIEWING,
                language=calendar_entry.language,
                category=calendar_entry.category,
                funnel_stage=calendar_entry.funnel_stage,
                target_keywords=calendar_entry.target_keywords,
                platform=calendar_entry.target_platform,
            )
            session.add(article)
            await session.flush()

            pipeline_run.article_id = article.id
            pipeline_run.status = PipelineStatus.COMPLETED
            pipeline_run.current_step = None
            calendar_entry.status = CalendarStatus.COMPLETED
            calendar_entry.article_id = article.id
        else:
            pipeline_run.status = PipelineStatus.FAILED
            pipeline_run.error_message = result.error_message
            calendar_entry.status = CalendarStatus.SCHEDULED

    except Exception as exc:
        log.error("pipeline_execution_error", error=str(exc))
        pipeline_run.status = PipelineStatus.FAILED
        pipeline_run.error_message = str(exc)
        calendar_entry.status = CalendarStatus.SCHEDULED

    pipeline_run.completed_at = datetime.now(timezone.utc)
    await session.commit()

    log.info(
        "pipeline_complete",
        run_id=pipeline_run.id,
        status=pipeline_run.status.value,
    )
    return pipeline_run


def _extract_title(markdown: str) -> str:
    """Extract the first H1 heading from markdown content."""
    for line in markdown.split("\n"):
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            return stripped.lstrip("# ").strip()
    return ""


def _slugify(text: str, fallback_id: int) -> str:
    """Create a URL-friendly slug from text."""
    import re
    import unicodedata

    text = unicodedata.normalize("NFKD", text)
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[-\s]+", "-", slug).strip("-")
    if not slug:
        slug = f"article-{fallback_id}"
    return slug[:200]
