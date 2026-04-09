import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.seed import seed_integrations
from app.db.session import async_session_factory
from app.routers import feed, gcal, gmail, health, integrations, messages, notion
from app.services.gcal import sync_calendar
from app.services.gmail import load_tokens, sync_gmail
from app.services.notion import sync_notion

logger = logging.getLogger(__name__)


# ── background sync ───────────────────────────────────────────────────────────


async def _sync_all_sources() -> None:
    """
    Sync every connected source once.

    Each source is attempted independently — a failure in one does not
    prevent the others from running. Sources with missing credentials are
    silently skipped.
    """
    if load_tokens():
        async with async_session_factory() as session:
            try:
                result = await sync_gmail(session)
                logger.info("Gmail sync complete: %s", result)
            except Exception as exc:
                logger.warning("Gmail sync failed: %s", exc)

        async with async_session_factory() as session:
            try:
                result = await sync_calendar(session)
                logger.info("Calendar sync complete: %s", result)
            except Exception as exc:
                logger.warning("Calendar sync failed: %s", exc)
    else:
        logger.debug("Gmail not connected — skipping Gmail and Calendar sync")

    if settings.notion_token and settings.notion_todo_database_id:
        async with async_session_factory() as session:
            try:
                result = await sync_notion(session)
                logger.info("Notion sync complete: %s", result)
            except Exception as exc:
                logger.warning("Notion sync failed: %s", exc)
    else:
        logger.debug("Notion not configured — skipping Notion sync")


async def _background_sync_loop() -> None:
    """
    Periodically sync all connected sources.

    Runs every settings.sync_interval_seconds (default 300 / 5 minutes).
    If sync_interval_seconds is 0, this loop exits immediately (startup-only
    sync mode).
    """
    if settings.sync_interval_seconds <= 0:
        logger.info("Background sync polling disabled (sync_interval_seconds=0)")
        return

    logger.info(
        "Background sync loop started — interval %ds", settings.sync_interval_seconds
    )
    while True:
        await asyncio.sleep(settings.sync_interval_seconds)
        logger.info("Background sync firing")
        await _sync_all_sources()


# ── application lifespan ──────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Seed the integrations table (idempotent).
    async with async_session_factory() as session:
        await seed_integrations(session)

    # Run an immediate sync on startup so the feed is fresh the moment the
    # server comes up. Errors are logged but do not abort startup.
    logger.info("Running startup sync")
    await _sync_all_sources()

    # Start background polling.
    loop_task = asyncio.create_task(_background_sync_loop())

    yield

    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        pass


# ── app ───────────────────────────────────────────────────────────────────────


app = FastAPI(
    title="Personal Command Center API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(integrations.router, prefix="/api")
app.include_router(gmail.router, prefix="/api")
app.include_router(messages.router, prefix="/api")
app.include_router(gcal.router, prefix="/api")
app.include_router(notion.router, prefix="/api")
app.include_router(feed.router, prefix="/api")
