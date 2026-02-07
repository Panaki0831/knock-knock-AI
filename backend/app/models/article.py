"""Article ORM model."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class ArticleStatus(str, enum.Enum):
    """Lifecycle status of an article."""

    DRAFTING = "drafting"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"


class FunnelStage(str, enum.Enum):
    """Marketing funnel stage."""

    TOFU = "TOFU"
    MOFU = "MOFU"
    BOFU = "BOFU"


class Article(Base):
    """Represents a single content article produced by the pipeline."""

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    slug: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    content_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_html: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[ArticleStatus] = mapped_column(
        Enum(ArticleStatus, name="article_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=ArticleStatus.DRAFTING,
        server_default="drafting",
    )
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="ja")
    category: Mapped[str | None] = mapped_column(String(200), nullable=True)
    funnel_stage: Mapped[FunnelStage | None] = mapped_column(
        Enum(FunnelStage, name="funnel_stage", values_callable=lambda e: [m.value for m in e]),
        nullable=True,
    )
    target_keywords: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    meta_description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Quality scores stored as a single JSON object
    quality_scores: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment=(
            "JSON with keys: readability_score, seo_score, ai_detection_score, "
            "factual_accuracy_score, brand_consistency_score"
        ),
    )

    platform: Mapped[str | None] = mapped_column(String(100), nullable=True)
    published_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    author_persona: Mapped[str | None] = mapped_column(String(200), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Article id={self.id} slug={self.slug!r} status={self.status.value!r}>"
