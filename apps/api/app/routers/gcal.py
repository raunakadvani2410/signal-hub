"""
Google Calendar router.

POST /api/gcal/sync  — fetch upcoming events and upsert into the events table.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.gcal import sync_calendar
from app.services.gmail import load_tokens

router = APIRouter(prefix="/gcal", tags=["gcal"])


@router.post("/sync")
async def gcal_sync(session: AsyncSession = Depends(get_session)) -> dict:
    """
    Sync upcoming Google Calendar events into the local events table.

    Requires a valid OAuth token with calendar.readonly scope.
    Returns {"synced": N}.
    """
    if load_tokens() is None:
        raise HTTPException(
            status_code=401,
            detail="Google account not connected. Complete the OAuth flow at /api/gmail/auth.",
        )
    try:
        return await sync_calendar(session)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Calendar sync failed: {exc}")
