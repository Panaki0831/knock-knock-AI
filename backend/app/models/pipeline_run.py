"""PipelineRun ORM model."""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class PipelineStatus(str, enum.Enum):
    """Execution status of a pipeline run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineRun(Base):
    """Tracks a single article-generation pipeline execution."""

    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    article_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("articles.id", ondelete="SET NULL"), nullable=True
    )
    calendar_entry_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("content_calendar.id", ondelete="SET NULL"), nullable=True
    )
    topic: Mapped[str | None] = mapped_column(String(500), nullable=True)

    status: Mapped[PipelineStatus] = mapped_column(
        Enum(PipelineStatus, name="pipeline_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=PipelineStatus.PENDING,
        server_default="pending",
    )
    current_step: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Ordered JSON array – each element records one step's result
    steps_log: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment="JSON array of step results: [{step, status, started_at, completed_at, detail}, ...]",
    )

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    total_tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=10, scale=6), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    article = relationship("Article", backref="pipeline_runs", lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<PipelineRun id={self.id} article_id={self.article_id} "
            f"status={self.status.value!r} step={self.current_step!r}>"
        )
