"""
Unified inbox feed.

Returns a time-ordered list of FeedItem objects drawn from all connected sources.
To add a new source: write a _X_to_feed_item() mapper and include its table query
in get_feed(). The FeedItem schema itself does not need to change.

Source filter
-------------
Pass ?source=gmail (or google_calendar, notion) to get items from a single
source. Omit the param for the consolidated feed (all sources merged).
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from signal_hub_shared.models import FeedItem, ItemSource, ItemType
from app.db.models.event import EventModel
from app.db.models.message import MessageModel
from app.db.models.task import TaskModel
from app.db.session import get_session

router = APIRouter(prefix="/feed", tags=["feed"])


# ── helpers ───────────────────────────────────────────────────────────────────


def _as_utc(dt: datetime) -> datetime:
    """Return dt with UTC tzinfo. SQLite stores datetimes as naive; Postgres stores tz-aware."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ── per-source mappers ────────────────────────────────────────────────────────


def _message_to_feed_item(row: MessageModel) -> FeedItem:
    """Map a stored MessageModel row into a FeedItem for display."""
    return FeedItem(
        id=f"{row.source}:{row.external_id}",
        source=ItemSource(row.source),
        item_type=ItemType.MESSAGE,
        title=row.subject or "(no subject)",
        preview=row.body_preview,
        sender=row.sender,
        received_at=_as_utc(row.received_at),
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
        received_at=_as_utc(row.start_at),  # events sort by when they start
        is_read=True,               # events have no unread concept
        external_id=row.external_id,
        thread_id=None,
    )


def _task_preview(due_at: datetime | None) -> str:
    """Compute a human-readable due-date string for display as the preview line."""
    if due_at is None:
        return "No due date"
    today = datetime.now(tz=timezone.utc).date()
    due_date = due_at.date() if due_at.tzinfo else due_at.replace(tzinfo=timezone.utc).date()
    delta = (due_date - today).days
    if delta < 0:
        n = abs(delta)
        return f"Overdue by {n} day{'s' if n != 1 else ''}"
    if delta == 0:
        return "Due today"
    if delta == 1:
        return "Due tomorrow"
    return f"Due in {delta} days"


def _task_received_at(row: TaskModel) -> datetime:
    """
    Sort signal for a task.

    Priority order:
      1. due_at — the explicit due date the user set in Notion
      2. last_edited_time from raw_json — when they last touched the task
      3. created_at — when Signal Hub first synced it
    """
    if row.due_at:
        return _as_utc(row.due_at)
    if row.raw_json and row.raw_json.get("last_edited_time"):
        raw = row.raw_json["last_edited_time"]
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass
    return _as_utc(row.created_at)


def _task_to_feed_item(row: TaskModel) -> FeedItem:
    """Map a stored TaskModel row into a FeedItem for display."""
    return FeedItem(
        id=f"{row.source}:{row.external_id}",
        source=ItemSource(row.source),
        item_type=ItemType.TASK,
        title=row.title,
        preview=_task_preview(row.due_at),
        sender=None,
        received_at=_task_received_at(row),
        is_read=False,  # open task is always "unread"
        external_id=row.external_id,
        thread_id=None,
    )


# ── feed endpoint ─────────────────────────────────────────────────────────────


@router.get("/", response_model=list[FeedItem])
async def get_feed(
    limit: int = Query(default=50, le=200),
    source: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[FeedItem]:
    """
    Return unified inbox feed, newest first.

    ?source=gmail|google_calendar|notion   returns items from one source only.
    Omit ?source for the consolidated Signal Hub feed (all sources merged).
    """
    msg_result = await session.execute(select(MessageModel))
    evt_result = await session.execute(select(EventModel))
    task_result = await session.execute(select(TaskModel))

    items: list[FeedItem] = (
        [_message_to_feed_item(r) for r in msg_result.scalars().all()]
        + [_event_to_feed_item(r) for r in evt_result.scalars().all()]
        + [_task_to_feed_item(r) for r in task_result.scalars().all()]
    )

    if source is not None:
        items = [i for i in items if i.source.value == source]

    items.sort(key=lambda i: i.received_at, reverse=True)
    return items[:limit]
