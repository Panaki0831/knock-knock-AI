"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import articles, calendar, dashboard, pipeline
from app.config import settings
from app.db.database import engine, Base


def _add_column_if_missing(conn, table: str, column: str, col_type: str) -> None:
    """Add a column to an existing table if it doesn't exist (dev helper)."""
    from sqlalchemy import text

    result = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :col"
        ),
        {"table": table, "col": column},
    )
    if result.fetchone() is None:
        conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {col_type}'))


def _run_migrations(sync_conn) -> None:
    """Add missing columns to existing tables (dev only)."""
    _add_column_if_missing(sync_conn, "pipeline_runs", "calendar_entry_id", "INTEGER")
    _add_column_if_missing(sync_conn, "pipeline_runs", "topic", "VARCHAR(500)")


def _cleanup_stale_runs(sync_conn) -> None:
    """Mark abandoned pending/running pipeline runs as failed on startup."""
    from sqlalchemy import text

    sync_conn.execute(
        text(
            "UPDATE pipeline_runs SET status = 'failed', "
            "error_message = 'Abandoned: server restarted before completion', "
            "current_step = NULL "
            "WHERE status IN ('pending', 'running')"
        )
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # Startup: create tables if they don't exist (dev only)
    if settings.app_env == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # Migrate: add columns that create_all doesn't add to existing tables
            await conn.run_sync(_run_migrations)
            # Clean up abandoned pipeline runs from previous restarts
            await conn.run_sync(_cleanup_stale_runs)
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
