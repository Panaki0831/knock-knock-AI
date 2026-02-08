"""Article management API routes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.models.article import Article, ArticleStatus

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────


class ArticleOut(BaseModel):
    id: int
    title: str
    slug: str
    status: str
    language: str
    category: str | None = None
    funnel_stage: str | None = None
    target_keywords: list[str] | None = None
    meta_description: str | None = None
    quality_scores: dict[str, Any] | None = None
    platform: str | None = None
    published_url: str | None = None
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None = None

    model_config = {"from_attributes": True}


class ArticleListOut(BaseModel):
    items: list[ArticleOut]
    total: int
    page: int
    page_size: int


class ArticleUpdateIn(BaseModel):
    title: str | None = None
    status: str | None = None
    content_markdown: str | None = None
    meta_description: str | None = None
    target_keywords: list[str] | None = None


class ArticleContentOut(BaseModel):
    id: int
    title: str
    content_markdown: str | None = None
    content_html: str | None = None

    model_config = {"from_attributes": True}


# ── Routes ───────────────────────────────────────────────────────────────────


@router.get("", response_model=ArticleListOut)
async def list_articles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    language: str | None = None,
    category: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    """List articles with optional filters and pagination."""
    query = select(Article)

    if status:
        query = query.where(Article.status == status)
    if language:
        query = query.where(Article.language == language)
    if category:
        query = query.where(Article.category == category)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar() or 0

    # Paginate
    query = query.order_by(Article.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(query)
    articles = result.scalars().all()

    return ArticleListOut(
        items=[ArticleOut.model_validate(a) for a in articles],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{article_id}", response_model=ArticleOut)
async def get_article(
    article_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get a single article by ID."""
    article = await session.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return ArticleOut.model_validate(article)


@router.get("/{article_id}/content", response_model=ArticleContentOut)
async def get_article_content(
    article_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get the full content of an article."""
    article = await session.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return ArticleContentOut.model_validate(article)


@router.patch("/{article_id}", response_model=ArticleOut)
async def update_article(
    article_id: int,
    body: ArticleUpdateIn,
    session: AsyncSession = Depends(get_session),
):
    """Update article fields."""
    article = await session.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    if body.title is not None:
        article.title = body.title
    if body.status is not None:
        article.status = ArticleStatus(body.status)
    if body.content_markdown is not None:
        article.content_markdown = body.content_markdown
    if body.meta_description is not None:
        article.meta_description = body.meta_description
    if body.target_keywords is not None:
        article.target_keywords = body.target_keywords

    article.updated_at = datetime.now(timezone.utc)
    await session.flush()

    return ArticleOut.model_validate(article)


@router.post("/{article_id}/approve", response_model=ArticleOut)
async def approve_article(
    article_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Approve an article for publishing."""
    article = await session.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    if article.status != ArticleStatus.REVIEWING:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve article in status '{article.status.value}'",
        )
    article.status = ArticleStatus.APPROVED
    article.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return ArticleOut.model_validate(article)


@router.post("/{article_id}/reject", response_model=ArticleOut)
async def reject_article(
    article_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Reject an article, sending it back for revision."""
    article = await session.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    article.status = ArticleStatus.REJECTED
    article.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return ArticleOut.model_validate(article)


@router.delete("/{article_id}", status_code=200)
async def delete_article(
    article_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Delete an article by ID."""
    article = await session.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    await session.delete(article)
    await session.commit()
    return {"deleted": article_id}
