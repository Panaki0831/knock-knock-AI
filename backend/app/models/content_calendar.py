"""ContentCalendar ORM model."""

from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.article import FunnelStage


class CalendarPriority(str, enum.Enum):
    """Priority level for a calendar entry."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class CalendarStatus(str, enum.Enum):
    """Lifecycle status of a calendar entry."""

    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ContentCalendar(Base):
    """Represents a planned content slot on the editorial calendar."""

    __tablename__ = "content_calendar"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    article_theme: Mapped[str] = mapped_column(String(500), nullable=False)
    target_keywords: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    category: Mapped[str | None] = mapped_column(String(200), nullable=True)
    funnel_stage: Mapped[FunnelStage | None] = mapped_column(
        Enum(FunnelStage, name="funnel_stage", create_constraint=False, values_callable=lambda e: [m.value for m in e]),
        nullable=True,
    )
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="ja")
    target_platform: Mapped[str | None] = mapped_column(String(100), nullable=True)
    assigned_persona: Mapped[str | None] = mapped_column(String(200), nullable=True)

    priority: Mapped[CalendarPriority] = mapped_column(
        Enum(CalendarPriority, name="calendar_priority", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=CalendarPriority.MEDIUM,
        server_default="medium",
    )
    status: Mapped[CalendarStatus] = mapped_column(
        Enum(CalendarStatus, name="calendar_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=CalendarStatus.SCHEDULED,
        server_default="scheduled",
    )

    article_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("articles.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    article = relationship("Article", backref="calendar_entries", lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<ContentCalendar id={self.id} date={self.scheduled_date} "
            f"theme={self.article_theme!r} status={self.status.value!r}>"
        )
