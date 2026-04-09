"""
Google Calendar integration service.

Reuses the OAuth credentials managed by the Gmail service (same Google app,
same token file). calendar.readonly scope must be included in SCOPES there.

Fetches events from the authenticated user's primary calendar, normalises
them to the shared Event model, and upserts into the events table.

Rolling window
--------------
Only events whose start time falls within [now, now + 7 days] are fetched and
kept in the DB. Each sync prunes any stored google_calendar events that have
drifted outside that window (past events, or events beyond 7 days that were
stored during an earlier sync when the window was different).
"""

from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from signal_hub_shared.models import Event, ItemSource
from app.db.models.event import EventModel
from app.services.gmail import _get_valid_credentials

_GCAL_API_BASE = "https://www.googleapis.com/calendar/v3"
_WINDOW_DAYS = 7


# ── normalisation ─────────────────────────────────────────────────────────────


def _parse_dt(dt_obj: dict) -> datetime:
    """
    Parse a Google Calendar dateTime or date object into a timezone-aware datetime.

    Google returns either {"dateTime": "2026-04-05T10:00:00Z"} for timed events
    or {"date": "2026-04-05"} for all-day events.
    """
    if "dateTime" in dt_obj:
        dt = datetime.fromisoformat(dt_obj["dateTime"])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    # All-day event: treat as midnight UTC on that date.
    return datetime.fromisoformat(dt_obj["date"]).replace(tzinfo=timezone.utc)


def normalize_event(raw: dict) -> Event:
    """
    Normalize a raw Google Calendar event resource into a shared Event.

    raw is the JSON object returned by the Calendar events.list API.
    """
    organizer = raw.get("organizer", {})
    organizer_name = organizer.get("displayName") or organizer.get("email") or None  # noqa: F841

    attendees = [
        a.get("email", "")
        for a in raw.get("attendees", [])
        if a.get("email")
    ]

    meeting_url = raw.get("hangoutLink") or raw.get("conferenceData", {}).get(
        "entryPoints", [{}]
    )[0].get("uri")

    return Event(
        external_id=raw["id"],
        source=ItemSource.GOOGLE_CALENDAR,
        title=raw.get("summary") or "(no title)",
        description=raw.get("description"),
        start_at=_parse_dt(raw["start"]),
        end_at=_parse_dt(raw["end"]),
        location=raw.get("location"),
        attendees=attendees,
        meeting_url=meeting_url,
        raw_json=None,
    )


# ── API fetch ─────────────────────────────────────────────────────────────────


async def fetch_calendar_events(max_results: int = 50) -> list[dict]:
    """
    Fetch events from the primary calendar within the next 7 days.

    timeMin = now (inclusive), timeMax = now + 7 days (exclusive).
    singleEvents=true expands recurring events into individual instances.
    Events are ordered by start time.
    """
    creds = await _get_valid_credentials()
    auth_header = {"Authorization": f"Bearer {creds.token}"}
    now = datetime.now(tz=timezone.utc)
    window_end = now + timedelta(days=_WINDOW_DAYS)

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_GCAL_API_BASE}/calendars/primary/events",
            headers=auth_header,
            params={
                "timeMin": now.isoformat(),
                "timeMax": window_end.isoformat(),
                "maxResults": max_results,
                "singleEvents": "true",
                "orderBy": "startTime",
            },
        )
        resp.raise_for_status()
        return resp.json().get("items", [])


# ── DB upsert ─────────────────────────────────────────────────────────────────


async def _upsert_events(session: AsyncSession, raw_events: list[dict]) -> int:
    """
    Normalize and upsert a list of raw Calendar event dicts.

    Inserts new events; updates title/times on existing ones.
    Does NOT commit — caller owns the transaction.
    Returns the number of events processed.
    """
    for raw in raw_events:
        evt = normalize_event(raw)
        result = await session.execute(
            select(EventModel).where(EventModel.external_id == evt.external_id)
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            session.add(
                EventModel(
                    external_id=evt.external_id,
                    source=evt.source.value,
                    title=evt.title,
                    description=evt.description,
                    start_at=evt.start_at,
                    end_at=evt.end_at,
                    location=evt.location,
                    meeting_url=evt.meeting_url,
                    raw_json=evt.raw_json,
                )
            )
        else:
            existing.title = evt.title
            existing.description = evt.description
            existing.start_at = evt.start_at
            existing.end_at = evt.end_at
            existing.location = evt.location
            existing.meeting_url = evt.meeting_url
    return len(raw_events)


async def _prune_outside_window(
    session: AsyncSession, now: datetime, window_end: datetime
) -> None:
    """
    Delete stored google_calendar events that fall outside [now, window_end].

    Runs after every sync so the DB never accumulates stale events from
    previous syncs whose window has since rolled past.
    Does NOT commit — caller owns the transaction.
    """
    await session.execute(
        delete(EventModel).where(
            EventModel.source == ItemSource.GOOGLE_CALENDAR.value,
            or_(
                EventModel.start_at < now,
                EventModel.start_at > window_end,
            ),
        )
    )


# ── public sync entry point ───────────────────────────────────────────────────


async def sync_calendar(session: AsyncSession, max_results: int = 50) -> dict:
    """
    Fetch upcoming calendar events (next 7 days) and upsert them.

    After upserting, prunes any google_calendar rows outside the current
    7-day window so past or far-future events from prior syncs are removed.
    Returns {"synced": N} where N is the number of events fetched from the API.
    """
    now = datetime.now(tz=timezone.utc)
    window_end = now + timedelta(days=_WINDOW_DAYS)

    raw_events = await fetch_calendar_events(max_results)
    count = await _upsert_events(session, raw_events)
    await _prune_outside_window(session, now, window_end)
    await session.commit()
    return {"synced": count}
