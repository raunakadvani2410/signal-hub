"""
Normalized data models shared between api and web.

These are the canonical shapes for all items ingested from external sources.
When a new field is added here, update packages/shared/typescript/src/models.ts too.
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
