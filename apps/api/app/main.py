from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.seed import seed_integrations
from app.db.session import async_session_factory
from app.routers import feed, gcal, gmail, health, integrations, messages, notion


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with async_session_factory() as session:
        await seed_integrations(session)
    yield


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
