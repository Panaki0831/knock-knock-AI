"""KnowledgeDocument ORM model -- stores uploaded knowledge base documents."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class KnowledgeDocument(Base):
    """A document uploaded to the knowledge base (pptx, pdf, docx)."""

    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)  # pdf, pptx, docx
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Extracted text content from the document
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Optional metadata
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    category: Mapped[str | None] = mapped_column(String(200), nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Number of pages/slides extracted
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<KnowledgeDocument id={self.id} filename={self.filename!r}>"
