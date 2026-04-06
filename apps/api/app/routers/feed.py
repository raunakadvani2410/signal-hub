"""
Unified inbox feed.

Returns a time-ordered list of FeedItem objects drawn from all connected sources.
Currently sourced from Gmail messages only. To add a new source (Calendar, Notion):

  1. Query its DB table (or call its service).
  2. Write a mapping function that returns FeedItem (same pattern as
     _message_to_feed_item below).
  3. Merge the lists and re-sort by received_at before slicing to limit.

The FeedItem schema does not change when new sources are added — only the
aggregation logic in get_feed() grows.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from signal_hub_shared.models import FeedItem, ItemSource, ItemType
from app.db.models.message import MessageModel
from app.db.session import get_session

router = APIRouter(prefix="/feed", tags=["feed"])


def _message_to_feed_item(row: MessageModel) -> FeedItem:
    """Map a stored MessageModel row into a FeedItem for display."""
    return FeedItem(
        id=f"{row.source}:{row.external_id}",
        source=ItemSource(row.source),
        item_type=ItemType.MESSAGE,
        title=row.subject or "(no subject)",
        preview=row.body_preview,
        sender=row.sender,
        received_at=row.received_at,
        is_read=row.is_read,
        external_id=row.external_id,
        thread_id=row.thread_id,
    )


@router.get("/", response_model=list[FeedItem])
async def get_feed(
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[FeedItem]:
    """
    Return unified inbox feed, newest first.

    Today: Gmail messages only.
    When Calendar/Notion are added, merge their results here and re-sort.
    """
    result = await session.execute(
        select(MessageModel).order_by(MessageModel.received_at.desc()).limit(limit)
    )
    rows = result.scalars().all()
    return [_message_to_feed_item(row) for row in rows]
