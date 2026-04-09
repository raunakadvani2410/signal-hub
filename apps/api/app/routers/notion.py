"""
Notion router.

POST /api/notion/sync  — fetch open tasks from the todo database and upsert.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_session
from app.services.notion import sync_notion

router = APIRouter(prefix="/notion", tags=["notion"])


@router.post("/sync")
async def notion_sync(session: AsyncSession = Depends(get_session)) -> dict:
    """
    Sync open tasks from the Notion todo database.

    Requires NOTION_TOKEN and NOTION_TODO_DATABASE_ID in .env.
    Returns {"synced": N}.
    """
    if not settings.notion_token or not settings.notion_todo_database_id:
        raise HTTPException(
            status_code=503,
            detail="Notion is not configured. Set NOTION_TOKEN and NOTION_TODO_DATABASE_ID in .env.",
        )
    try:
        return await sync_notion(session)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Notion sync failed: {exc}")
