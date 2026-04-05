"""
Test fixtures.

Uses an in-memory SQLite database (via aiosqlite) so tests never need a running
Postgres. The test app is built without the startup lifespan event — the lifespan
would try to connect to Postgres and fail in CI / local runs without a DB.
"""

from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.db.models  # noqa: F401 — registers all ORM models with Base.metadata
from app.db.base import Base
from app.db.seed import seed_integrations
from app.db.session import get_session
from app.routers import health
from app.routers import integrations as integration_router

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


def _make_test_app() -> FastAPI:
    """Minimal app without the startup lifespan — safe to use without Postgres."""
    test_app = FastAPI()
    test_app.include_router(health.router)
    test_app.include_router(integration_router.router, prefix="/api")
    return test_app


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    engine = create_async_engine(TEST_DB_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Seed once before any requests hit the app.
    async with session_factory() as session:
        await seed_integrations(session)

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    test_app = _make_test_app()
    test_app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as c:
        yield c

    test_app.dependency_overrides.clear()
    await engine.dispose()
