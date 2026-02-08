"""ResearchHistory ORM model -- stores past researcher agent results."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class ResearchHistory(Base):
    """Stores the output of each researcher agent run for future reference."""

    __tablename__ = "research_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    pipeline_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    topic: Mapped[str] = mapped_column(String(500), nullable=False)
    target_keywords: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    # The full research report markdown
    research_report: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Structured data from researcher output
    key_statistics: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    sources: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    competitor_insights: Mapped[str | None] = mapped_column(Text, nullable=True)
    market_data: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Entries are auto-deleted after ~1 month
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    def __repr__(self) -> str:
        return f"<ResearchHistory id={self.id} topic={self.topic!r}>"
