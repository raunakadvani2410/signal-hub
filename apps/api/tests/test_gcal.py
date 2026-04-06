"""
Google Calendar tests.

Tests normalize_event() directly and the feed merging behaviour
(Calendar events appear alongside Gmail messages in GET /api/feed/).
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.services.gcal import normalize_event

# ── raw event fixtures ────────────────────────────────────────────────────────

_TIMED_EVENT = {
    "id": "evt_timed",
    "summary": "Team standup",
    "description": "Daily sync",
    "start": {"dateTime": "2026-04-06T09:00:00Z"},
    "end": {"dateTime": "2026-04-06T09:30:00Z"},
    "location": "Google Meet",
    "hangoutLink": "https://meet.google.com/abc-defg-hij",
    "organizer": {"displayName": "Alice", "email": "alice@example.com"},
    "attendees": [
        {"email": "alice@example.com"},
        {"email": "bob@example.com"},
    ],
}

_ALL_DAY_EVENT = {
    "id": "evt_allday",
    "summary": "Company holiday",
    "start": {"date": "2026-04-07"},
    "end": {"date": "2026-04-08"},
}

_NO_TITLE_EVENT = {
    "id": "evt_notitle",
    "start": {"dateTime": "2026-04-08T14:00:00Z"},
    "end": {"dateTime": "2026-04-08T15:00:00Z"},
}


# ── normalize_event unit tests ────────────────────────────────────────────────


def test_normalize_timed_event() -> None:
    evt = normalize_event(_TIMED_EVENT)

    assert evt.external_id == "evt_timed"
    assert evt.source.value == "google_calendar"
    assert evt.title == "Team standup"
    assert evt.description == "Daily sync"
    assert evt.start_at == datetime(2026, 4, 6, 9, 0, 0, tzinfo=timezone.utc)
    assert evt.end_at == datetime(2026, 4, 6, 9, 30, 0, tzinfo=timezone.utc)
    assert evt.location == "Google Meet"
    assert evt.meeting_url == "https://meet.google.com/abc-defg-hij"
    assert "alice@example.com" in evt.attendees
    assert "bob@example.com" in evt.attendees


def test_normalize_all_day_event() -> None:
    evt = normalize_event(_ALL_DAY_EVENT)

    assert evt.title == "Company holiday"
    assert evt.start_at.tzinfo is not None
    assert evt.start_at.date().isoformat() == "2026-04-07"


def test_normalize_event_no_title_falls_back() -> None:
    evt = normalize_event(_NO_TITLE_EVENT)
    assert evt.title == "(no title)"


def test_normalize_event_no_attendees() -> None:
    evt = normalize_event(_ALL_DAY_EVENT)
    assert evt.attendees == []


# ── sync endpoint ─────────────────────────────────────────────────────────────


async def test_gcal_sync_stores_events(client: AsyncClient) -> None:
    with (
        patch("app.routers.gcal.load_tokens", return_value={"access_token": "fake"}),
        patch(
            "app.services.gcal.fetch_calendar_events",
            new=AsyncMock(return_value=[_TIMED_EVENT, _ALL_DAY_EVENT]),
        ),
    ):
        resp = await client.post("/api/gcal/sync")

    assert resp.status_code == 200
    assert resp.json()["synced"] == 2


async def test_gcal_sync_is_idempotent(client: AsyncClient) -> None:
    with (
        patch("app.routers.gcal.load_tokens", return_value={"access_token": "fake"}),
        patch(
            "app.services.gcal.fetch_calendar_events",
            new=AsyncMock(return_value=[_TIMED_EVENT]),
        ),
    ):
        await client.post("/api/gcal/sync")
        resp = await client.post("/api/gcal/sync")

    assert resp.status_code == 200
    assert resp.json()["synced"] == 1


async def test_gcal_sync_requires_auth(client: AsyncClient) -> None:
    with patch("app.routers.gcal.load_tokens", return_value=None):
        resp = await client.post("/api/gcal/sync")
    assert resp.status_code == 401


# ── feed merging ──────────────────────────────────────────────────────────────


async def _sync_gmail(client: AsyncClient, messages: list[dict]) -> None:
    with (
        patch("app.routers.gmail.load_tokens", return_value={"access_token": "fake"}),
        patch(
            "app.services.gmail.fetch_inbox_messages",
            new=AsyncMock(return_value=messages),
        ),
    ):
        resp = await client.post("/api/gmail/sync")
    assert resp.status_code == 200


_GMAIL_MSG = {
    "id": "msg_1",
    "threadId": "thread_1",
    "labelIds": ["INBOX", "UNREAD"],
    "snippet": "Email body",
    "internalDate": "1743900000000",  # 2026-04-06T10:40:00Z
    "historyId": "9000",
    "payload": {
        "headers": [
            {"name": "From", "value": "Alice <alice@example.com>"},
            {"name": "Subject", "value": "Hello"},
        ]
    },
}


async def test_feed_merges_gmail_and_calendar(client: AsyncClient) -> None:
    await _sync_gmail(client, [_GMAIL_MSG])

    with (
        patch("app.routers.gcal.load_tokens", return_value={"access_token": "fake"}),
        patch(
            "app.services.gcal.fetch_calendar_events",
            new=AsyncMock(return_value=[_TIMED_EVENT]),
        ),
    ):
        await client.post("/api/gcal/sync")

    resp = await client.get("/api/feed/")
    assert resp.status_code == 200
    items = resp.json()

    sources = {i["source"] for i in items}
    assert "gmail" in sources
    assert "google_calendar" in sources

    item_types = {i["item_type"] for i in items}
    assert "message" in item_types
    assert "event" in item_types


async def test_feed_events_are_read_and_have_no_sender(client: AsyncClient) -> None:
    with (
        patch("app.routers.gcal.load_tokens", return_value={"access_token": "fake"}),
        patch(
            "app.services.gcal.fetch_calendar_events",
            new=AsyncMock(return_value=[_TIMED_EVENT]),
        ),
    ):
        await client.post("/api/gcal/sync")

    items = (await client.get("/api/feed/")).json()
    evt = next(i for i in items if i["source"] == "google_calendar")
    assert evt["is_read"] is True
    assert evt["sender"] is None
    assert evt["item_type"] == "event"


async def test_feed_sorted_newest_first_across_sources(client: AsyncClient) -> None:
    """Feed items from different sources are interleaved in start/received_at order."""
    await _sync_gmail(client, [_GMAIL_MSG])

    with (
        patch("app.routers.gcal.load_tokens", return_value={"access_token": "fake"}),
        patch(
            "app.services.gcal.fetch_calendar_events",
            new=AsyncMock(return_value=[_TIMED_EVENT]),
        ),
    ):
        await client.post("/api/gcal/sync")

    items = (await client.get("/api/feed/")).json()
    times = [i["received_at"] for i in items]
    assert times == sorted(times, reverse=True)
