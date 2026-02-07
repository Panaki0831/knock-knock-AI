"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import articles, calendar, dashboard, pipeline
from app.config import settings
from app.db.database import engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # Startup: create tables if they don't exist (dev only)
    if settings.app_env == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown: dispose of engine
    await engine.dispose()


app = FastAPI(
    title="knock knock AI - Content Marketing Automation",
    description="AIエージェント駆動型コンテンツマーケティング自動生成システム",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(articles.router, prefix="/api/v1/articles", tags=["articles"])
app.include_router(calendar.router, prefix="/api/v1/calendar", tags=["calendar"])
app.include_router(pipeline.router, prefix="/api/v1/pipeline", tags=["pipeline"])


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "knock-knock-ai"}
