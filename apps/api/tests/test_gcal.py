"""
Google Calendar tests.

Tests normalize_event() directly, the 7-day window pruning behaviour,
and feed merging (Calendar events alongside Gmail messages in GET /api/feed/).

Fixture strategy
----------------
- normalize_event unit tests use static dates — the function is pure and
  date values don't affect DB state or window logic.
- Sync / feed integration tests use dates computed relative to now so they
  always fall inside the rolling 7-day window and are not immediately pruned.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from app.services.gcal import normalize_event

# ── module-level "now" for dynamic fixtures ───────────────────────────────────

_NOW = datetime.now(tz=timezone.utc)

# ── static fixtures for normalize_event unit tests ────────────────────────────

_STATIC_TIMED = {
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

_STATIC_ALL_DAY = {
    "id": "evt_allday",
    "summary": "Company holiday",
    "start": {"date": "2026-04-07"},
    "end": {"date": "2026-04-08"},
}

_STATIC_NO_TITLE = {
    "id": "evt_notitle",
    "start": {"dateTime": "2026-04-08T14:00:00Z"},
    "end": {"dateTime": "2026-04-08T15:00:00Z"},
}

# ── dynamic fixtures for sync / feed integration tests ────────────────────────
# These must start within the next 7 days so they survive the pruning step.

_T1 = _NOW + timedelta(days=1)
_T2 = _NOW + timedelta(days=2)
_T3 = _NOW + timedelta(days=3)

_FUTURE_EVENT = {
    "id": "evt_future",
    "summary": "Team standup",
    "description": "Daily sync",
    "start": {"dateTime": _T1.isoformat()},
    "end": {"dateTime": (_T1 + timedelta(hours=1)).isoformat()},
    "location": "Google Meet",
    "hangoutLink": "https://meet.google.com/abc-defg-hij",
    "attendees": [{"email": "alice@example.com"}],
}

_FUTURE_ALL_DAY = {
    "id": "evt_allday_future",
    "summary": "Company holiday",
    "start": {"date": _T2.strftime("%Y-%m-%d")},
    "end": {"date": _T3.strftime("%Y-%m-%d")},
}

# An event in the past — should be pruned immediately after sync.
_PAST_EVENT = {
    "id": "evt_past",
    "summary": "Yesterday's meeting",
    "start": {"dateTime": (_NOW - timedelta(days=1)).isoformat()},
    "end": {"dateTime": (_NOW - timedelta(hours=23)).isoformat()},
}

# An event beyond 7 days — should be pruned immediately after sync.
_FAR_FUTURE_EVENT = {
    "id": "evt_far_future",
    "summary": "Far future meeting",
    "start": {"dateTime": (_NOW + timedelta(days=8)).isoformat()},
    "end": {"dateTime": (_NOW + timedelta(days=8, hours=1)).isoformat()},
}


# ── normalize_event unit tests ────────────────────────────────────────────────


def test_normalize_timed_event() -> None:
    evt = normalize_event(_STATIC_TIMED)

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
    evt = normalize_event(_STATIC_ALL_DAY)

    assert evt.title == "Company holiday"
    assert evt.start_at.tzinfo is not None
    assert evt.start_at.date().isoformat() == "2026-04-07"


def test_normalize_event_no_title_falls_back() -> None:
    evt = normalize_event(_STATIC_NO_TITLE)
    assert evt.title == "(no title)"


def test_normalize_event_no_attendees() -> None:
    evt = normalize_event(_STATIC_ALL_DAY)
    assert evt.attendees == []


# ── sync endpoint ─────────────────────────────────────────────────────────────


async def test_gcal_sync_stores_events(client: AsyncClient) -> None:
    with (
        patch("app.routers.gcal.load_tokens", return_value={"access_token": "fake"}),
        patch(
            "app.services.gcal.fetch_calendar_events",
            new=AsyncMock(return_value=[_FUTURE_EVENT, _FUTURE_ALL_DAY]),
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
            new=AsyncMock(return_value=[_FUTURE_EVENT]),
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


# ── 7-day window pruning ──────────────────────────────────────────────────────


async def test_gcal_sync_prunes_past_events(client: AsyncClient) -> None:
    """Events with start_at before now are removed from the DB after sync."""
    with (
        patch("app.routers.gcal.load_tokens", return_value={"access_token": "fake"}),
        patch(
            "app.services.gcal.fetch_calendar_events",
            new=AsyncMock(return_value=[_PAST_EVENT]),
        ),
    ):
        resp = await client.post("/api/gcal/sync")

    assert resp.status_code == 200
    # API returned 1 event (count reflects what was fetched, not what survived)
    assert resp.json()["synced"] == 1

    # Feed must not contain the past event — it was pruned.
    items = (await client.get("/api/feed/")).json()
    gcal_items = [i for i in items if i["source"] == "google_calendar"]
    assert gcal_items == []


async def test_gcal_sync_prunes_events_beyond_7_days(client: AsyncClient) -> None:
    """Events starting more than 7 days away are removed from the DB after sync."""
    with (
        patch("app.routers.gcal.load_tokens", return_value={"access_token": "fake"}),
        patch(
            "app.services.gcal.fetch_calendar_events",
            new=AsyncMock(return_value=[_FAR_FUTURE_EVENT]),
        ),
    ):
        await client.post("/api/gcal/sync")

    items = (await client.get("/api/feed/")).json()
    gcal_items = [i for i in items if i["source"] == "google_calendar"]
    assert gcal_items == []


async def test_gcal_sync_keeps_events_within_window(client: AsyncClient) -> None:
    """Events within the 7-day window survive the pruning step."""
    with (
        patch("app.routers.gcal.load_tokens", return_value={"access_token": "fake"}),
        patch(
            "app.services.gcal.fetch_calendar_events",
            new=AsyncMock(return_value=[_FUTURE_EVENT]),
        ),
    ):
        await client.post("/api/gcal/sync")

    items = (await client.get("/api/feed/")).json()
    gcal_items = [i for i in items if i["source"] == "google_calendar"]
    assert len(gcal_items) == 1
    assert gcal_items[0]["title"] == "Team standup"


async def test_gcal_sync_prunes_stale_event_on_subsequent_sync(
    client: AsyncClient,
) -> None:
    """
    An event stored in a previous sync that is now past gets cleaned up
    on the next sync even if the API no longer returns it.
    """
    # First sync: store a future event (within window — survives).
    with (
        patch("app.routers.gcal.load_tokens", return_value={"access_token": "fake"}),
        patch(
            "app.services.gcal.fetch_calendar_events",
            new=AsyncMock(return_value=[_FUTURE_EVENT]),
        ),
    ):
        await client.post("/api/gcal/sync")

    # Verify it's in the feed.
    items = (await client.get("/api/feed/")).json()
    assert any(i["source"] == "google_calendar" for i in items)

    # Second sync: API returns a different future event and a past event.
    # The past one should be pruned; the original future event (no longer
    # returned by API) remains because it's still within the window.
    with (
        patch("app.routers.gcal.load_tokens", return_value={"access_token": "fake"}),
        patch(
            "app.services.gcal.fetch_calendar_events",
            new=AsyncMock(return_value=[_FUTURE_ALL_DAY, _PAST_EVENT]),
        ),
    ):
        await client.post("/api/gcal/sync")

    items = (await client.get("/api/feed/")).json()
    gcal_items = [i for i in items if i["source"] == "google_calendar"]
    titles = {i["title"] for i in gcal_items}

    # Future event from first sync + future all-day from second sync survive.
    assert "Team standup" in titles
    assert "Company holiday" in titles
    # Past event was pruned.
    assert "Yesterday's meeting" not in titles


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
    "internalDate": "1743900000000",  # 2026-04-06T10:40:00Z (past — messages aren't pruned)
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
            new=AsyncMock(return_value=[_FUTURE_EVENT]),
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
            new=AsyncMock(return_value=[_FUTURE_EVENT]),
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
            new=AsyncMock(return_value=[_FUTURE_EVENT]),
        ),
    ):
        await client.post("/api/gcal/sync")

    items = (await client.get("/api/feed/")).json()
    times = [i["received_at"] for i in items]
    assert times == sorted(times, reverse=True)
