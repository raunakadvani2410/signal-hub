"""
Normalized data models shared between api and web.

These are the canonical shapes for all items ingested from external sources.
When a field is added or changed here, update packages/shared/typescript/src/models.ts too.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel


class ItemSource(str, Enum):
    GMAIL = "gmail"
    GOOGLE_CALENDAR = "google_calendar"
    NOTION = "notion"
    WHATSAPP = "whatsapp"
    LINKEDIN = "linkedin"
    IMESSAGE = "imessage"


class ItemType(str, Enum):
    MESSAGE = "message"  # email or chat message
    EVENT = "event"      # calendar event
    TASK = "task"        # todo / task


class Message(BaseModel):
    external_id: str
    source: ItemSource
    sender: str
    subject: Optional[str] = None
    body_preview: str
    is_read: bool = False
    received_at: datetime
    thread_id: Optional[str] = None
    raw_json: Optional[dict[str, Any]] = None


class Event(BaseModel):
    external_id: str
    source: ItemSource
    title: str
    description: Optional[str] = None
    start_at: datetime
    end_at: datetime
    location: Optional[str] = None
    attendees: list[str] = []
    meeting_url: Optional[str] = None
    raw_json: Optional[dict[str, Any]] = None


class Task(BaseModel):
    external_id: str
    source: ItemSource
    title: str
    description: Optional[str] = None
    is_done: bool = False
    due_at: Optional[datetime] = None
    priority: Optional[str] = None
    raw_json: Optional[dict[str, Any]] = None


class Notification(BaseModel):
    external_id: str
    source: ItemSource
    title: str
    body: Optional[str] = None
    is_read: bool = False
    received_at: datetime
    raw_json: Optional[dict[str, Any]] = None


class FeedItem(BaseModel):
    """
    Normalized display shape for the unified inbox feed.

    Abstracts source-specific field names (Gmail subject, Calendar title, Notion
    page heading) behind a common interface so the UI never branches on source.

    id          Stable composite key: "{source}:{external_id}". Unique across all
                sources; safe to use as a React key or cursor.
    source      Origin system. Determines the badge shown in the UI.
    item_type   message | event | task — shapes how the item is rendered.
    title       Primary line: email subject, event title, task name, etc.
                "(no subject)" when a message has no subject.
    preview     Short plaintext snippet: email body preview, event description,
                task description, etc.
    sender      Human-readable "From" string (email) or organiser (event).
                None for tasks and items with no clear author.
    received_at When the item arrived or was created. Used for sorting.
    is_read     False = show unread indicator in the UI.
    external_id The source system's own ID (Gmail message ID, etc.).
    thread_id   Optional grouping key. Used by Gmail threading; None for events.

    To add a new source: write a mapping function in its service/router that
    returns FeedItem. This model itself does not need to change.
    """

    id: str
    source: ItemSource
    item_type: ItemType
    title: str
    preview: str
    sender: Optional[str] = None
    received_at: datetime
    is_read: bool = False
    external_id: str
    thread_id: Optional[str] = None
