"""
Unified inbox feed.

Returns a time-ordered list of FeedItem objects drawn from all connected sources.
To add a new source (Notion, etc.):

  1. Query its DB table (or call its service).
  2. Write a mapping function that returns FeedItem (same pattern as
     _message_to_feed_item / _event_to_feed_item below).
  3. Add it to the `items` list in get_feed() — merging and sorting is automatic.

The FeedItem schema does not change when new sources are added — only the
aggregation logic in get_feed() grows.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from signal_hub_shared.models import FeedItem, ItemSource, ItemType
from app.db.models.event import EventModel
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


def _event_to_feed_item(row: EventModel) -> FeedItem:
    """Map a stored EventModel row into a FeedItem for display."""
    return FeedItem(
        id=f"{row.source}:{row.external_id}",
        source=ItemSource(row.source),
        item_type=ItemType.EVENT,
        title=row.title,
        preview=row.description or "",
        sender=None,
        received_at=row.start_at,  # events sort by when they start
        is_read=True,              # events have no unread concept
        external_id=row.external_id,
        thread_id=None,
    )


@router.get("/", response_model=list[FeedItem])
async def get_feed(
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[FeedItem]:
    """Return unified inbox feed, newest first (Gmail + Calendar merged)."""
    msg_result = await session.execute(select(MessageModel))
    evt_result = await session.execute(select(EventModel))

    items: list[FeedItem] = [
        _message_to_feed_item(row) for row in msg_result.scalars().all()
    ] + [
        _event_to_feed_item(row) for row in evt_result.scalars().all()
    ]

    items.sort(key=lambda i: i.received_at, reverse=True)
    return items[:limit]
