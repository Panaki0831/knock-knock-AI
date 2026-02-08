"""Pipeline service -- high-level entry point for triggering article generation."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import OrchestratorAgent
from app.models.article import Article, ArticleStatus
from app.models.content_calendar import CalendarStatus, ContentCalendar
from app.models.image_asset import ImageAsset
from app.models.knowledge_document import KnowledgeDocument
from app.models.pipeline_run import PipelineRun, PipelineStatus
from app.models.research_history import ResearchHistory

logger = structlog.get_logger(__name__)


async def _load_knowledge_context(session: AsyncSession) -> str:
    """Load all knowledge base documents and return as context string."""
    result = await session.execute(
        select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc())
    )
    docs = result.scalars().all()
    if not docs:
        return ""

    parts: list[str] = ["=== Knowledge Base ==="]
    for doc in docs:
        if doc.content_text:
            header = f"\n--- {doc.filename}"
            if doc.description:
                header += f" ({doc.description})"
            header += " ---\n"
            # Limit each doc to ~3000 chars to avoid overloading prompts
            text = doc.content_text[:3000]
            parts.append(header + text)

    return "\n".join(parts)


async def _load_knowledge_images(session: AsyncSession) -> list[dict[str, Any]]:
    """Load knowledge base images with their tags for the image generator."""
    result = await session.execute(
        select(ImageAsset).where(ImageAsset.is_knowledge_base == True)  # noqa: E712
    )
    images = result.scalars().all()
    return [
        {
            "id": img.id,
            "filename": img.filename,
            "tags": img.tags or [],
            "description": img.description or "",
        }
        for img in images
    ]


async def _save_generated_images(
    session: AsyncSession,
    article_id: int,
    image_data: list[dict[str, Any]],
) -> list[int]:
    """Save generated image metadata to the database and return image IDs."""
    image_ids: list[int] = []
    for img in image_data:
        asset = ImageAsset(
            filename=img["filename"],
            file_path=img["file_path"],
            mime_type="image/png",
            file_size=img.get("file_size", 0),
            width=img.get("width"),
            height=img.get("height"),
            source="generated",
            tags=img.get("tags"),
            description=img.get("section_heading", ""),
            generation_prompt=img.get("prompt", ""),
            generation_model="dall-e-3",
            article_id=article_id,
            section_heading=img.get("section_heading", ""),
            is_knowledge_base=False,
        )
        session.add(asset)
        await session.flush()
        image_ids.append(asset.id)

        # Replace placeholder in markdown will be handled after article creation
        img["db_id"] = asset.id

    return image_ids


async def _save_research_history(
    session: AsyncSession,
    pipeline_run_id: int,
    topic: str,
    target_keywords: list[str],
    research_data: dict[str, Any],
) -> None:
    """Save researcher output to research_history for future reference."""
    try:
        entry = ResearchHistory(
            pipeline_run_id=pipeline_run_id,
            topic=topic,
            target_keywords=target_keywords,
            research_report=research_data.get("research_report"),
            key_statistics=research_data.get("key_statistics"),
            sources=research_data.get("sources"),
            competitor_insights=research_data.get("competitor_insights"),
            market_data=research_data.get("market_data"),
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        session.add(entry)
        await session.flush()
        logger.info("research_history_saved", topic=topic, entry_id=entry.id)
    except Exception as exc:
        logger.warning("research_history_save_failed", error=str(exc))


def _resolve_image_placeholders(
    markdown: str,
    generated_images: list[dict[str, Any]],
) -> str:
    """Replace {IMAGE_PLACEHOLDER:filename} references with actual API URLs."""
    for img in generated_images:
        filename = img.get("filename", "")
        db_id = img.get("db_id")
        if filename and db_id:
            placeholder = f"{{IMAGE_PLACEHOLDER:{filename}}}"
            real_url = f"/api/v1/images/{db_id}/file"
            markdown = markdown.replace(placeholder, real_url)
    return markdown


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

    # 4. Load knowledge base context and images
    knowledge_context = await _load_knowledge_context(session)
    knowledge_images = await _load_knowledge_images(session)

    # 5. Build the orchestrator input
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

    # Inject knowledge base content and images if available
    if knowledge_context:
        orchestrator_input["knowledge_base"] = knowledge_context
    if knowledge_images:
        orchestrator_input["knowledge_images"] = knowledge_images

    # 6. Execute pipeline
    orchestrator = OrchestratorAgent()
    try:
        from app.agents.base import AgentContext

        async def _on_step_progress(step_name: str) -> None:
            """Update the PipelineRun row with the current step."""
            pipeline_run.current_step = step_name
            pipeline_run.status = PipelineStatus.RUNNING
            await session.commit()

        context = AgentContext(
            task_id=uuid.uuid4().hex,
            article_id=str(pipeline_run.id),
            input_data=orchestrator_input,
        )
        result = await orchestrator.execute(context, progress_callback=_on_step_progress)

        pipeline_run.steps_log = result.output_data.get("steps", [])
        pipeline_run.total_tokens_used = result.tokens_used
        pipeline_run.total_cost_usd = result.cost_usd

        # Save research history from the pipeline's research step output
        research_data = result.output_data.get("research_data", {})
        if research_data:
            await _save_research_history(
                session=session,
                pipeline_run_id=pipeline_run.id,
                topic=calendar_entry.article_theme,
                target_keywords=calendar_entry.target_keywords or [],
                research_data=research_data,
            )

        if result.success:
            # Create the article record
            final_output = result.output_data.get("final_output", {})
            article_markdown = (
                final_output.get("formatted_content")
                or final_output.get("edited_markdown")
                or final_output.get("article_markdown", "")
            )

            # Check for generated images from the image_generate step
            image_gen_data = result.output_data.get("image_generate_data", {})
            generated_images = image_gen_data.get("generated_images", [])

            # If image_generate step ran, use its markdown
            if image_gen_data.get("article_markdown"):
                article_markdown = image_gen_data["article_markdown"]

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

            # Save generated images to DB and resolve placeholders
            if generated_images:
                await _save_generated_images(session, article.id, generated_images)
                article.content_markdown = _resolve_image_placeholders(
                    article_markdown, generated_images
                )
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
    import re as _re
    import unicodedata

    text = unicodedata.normalize("NFKD", text)
    slug = _re.sub(r"[^\w\s-]", "", text.lower())
    slug = _re.sub(r"[-\s]+", "-", slug).strip("-")
    if not slug:
        slug = f"article-{fallback_id}"
    return slug[:200]
