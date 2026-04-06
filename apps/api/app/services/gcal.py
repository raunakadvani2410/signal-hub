"""
Google Calendar integration service.

Reuses the OAuth credentials managed by the Gmail service (same Google app,
same token file). calendar.readonly scope must be included in SCOPES there.

Fetches events from the authenticated user's primary calendar, normalises
them to the shared Event model, and upserts into the events table.
"""

from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from signal_hub_shared.models import Event, ItemSource
from app.db.models.event import EventModel
from app.services.gmail import _get_valid_credentials

_GCAL_API_BASE = "https://www.googleapis.com/calendar/v3"


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
    organizer_name = organizer.get("displayName") or organizer.get("email") or None

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
    Fetch upcoming events from the primary calendar.

    Returns a list of raw event resource dicts. Events are ordered by start time,
    starting from now, so only future (and in-progress) events are returned.
    """
    creds = await _get_valid_credentials()
    auth_header = {"Authorization": f"Bearer {creds.token}"}
    now_iso = datetime.now(tz=timezone.utc).isoformat()

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_GCAL_API_BASE}/calendars/primary/events",
            headers=auth_header,
            params={
                "timeMin": now_iso,
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


# ── public sync entry point ───────────────────────────────────────────────────


async def sync_calendar(session: AsyncSession, max_results: int = 50) -> dict:
    """
    Fetch upcoming calendar events and upsert them into the events table.

    Returns {"synced": N}.
    """
    raw_events = await fetch_calendar_events(max_results)
    count = await _upsert_events(session, raw_events)
    await session.commit()
    return {"synced": count}
