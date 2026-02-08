"""ImageAsset ORM model -- stores generated and uploaded images."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class ImageAsset(Base):
    """An image asset - either AI-generated or uploaded to knowledge base."""

    __tablename__ = "image_assets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # File info
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Source: "generated" (DALL-E), "uploaded" (knowledge base), "reused" (from gallery)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="uploaded")

    # Tags for search/selection (JSON array of strings)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    # Description of the image content
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Generation metadata (prompt, model, etc.)
    generation_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    generation_model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Link to article (if generated for a specific article)
    article_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_heading: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Whether this is a knowledge base image available for reuse
    is_knowledge_base: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<ImageAsset id={self.id} filename={self.filename!r} source={self.source!r}>"
