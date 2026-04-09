"""
Notion integration service.

Fetches open tasks from a single Notion database (the user's todo database)
and upserts them into the tasks table. Only database pages are synced;
standalone notes, reading entries, and sub-pages are intentionally excluded.

Authentication
--------------
Uses a static Internal Integration Token stored in NOTION_TOKEN (.env).
No OAuth flow required. The token must be shared with the target database
inside Notion (database "..." menu → Add connections → select integration).

Schema assumptions (user's actual database)
-------------------------------------------
  Task    — title property (the page name)
  Status  — status property (Notion built-in status type)
  Date    — date property (due date; optional)

Filter
------
Queries for tasks where Status != "Done". Tasks with no Status set are
included (they are not done). Pagination is not implemented — the first
100 open tasks are synced, which is sufficient for a personal database.
"""

from datetime import datetime, timezone

import httpx

from signal_hub_shared.models import ItemSource, Task
from app.config import settings
from app.db.models.task import TaskModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_NOTION_API_BASE = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"


# ── helpers ───────────────────────────────────────────────────────────────────


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.notion_token}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _parse_notion_dt(value: str) -> datetime:
    """
    Parse a Notion date/datetime string into a timezone-aware UTC datetime.

    Notion returns either:
      "2026-04-11"                         (date-only)
      "2026-04-11T09:00:00.000+05:30"      (datetime with offset)
    """
    if "T" in value:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    # Date-only: treat as midnight UTC.
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def _get_title(page: dict) -> str:
    """Extract plain text from the Task title property."""
    items = page.get("properties", {}).get("Task", {}).get("title", [])
    if items:
        return items[0].get("plain_text", "").strip() or "(untitled)"
    return "(untitled)"


def _get_due_at(page: dict) -> datetime | None:
    """Extract the Date property as a timezone-aware datetime, or None if unset."""
    date_prop = page.get("properties", {}).get("Date", {}).get("date")
    if not date_prop or not date_prop.get("start"):
        return None
    return _parse_notion_dt(date_prop["start"])


# ── normalisation ─────────────────────────────────────────────────────────────


def normalize_task(page: dict) -> Task:
    """
    Normalize a raw Notion page resource into a shared Task.

    The page must come from the todo database. The external_id is the Notion
    page ID with hyphens preserved (format: 32-char hex with 4 dashes).
    last_edited_time is stored in raw_json for use as a sort fallback when
    no due date is set.
    """
    return Task(
        external_id=page["id"],
        source=ItemSource.NOTION,
        title=_get_title(page),
        description=None,
        is_done=False,  # filter guarantees only open tasks are returned
        due_at=_get_due_at(page),
        raw_json={"last_edited_time": page.get("last_edited_time")},
    )


# ── API fetch ─────────────────────────────────────────────────────────────────


async def fetch_open_tasks() -> list[dict]:
    """
    Query the todo database for non-done tasks.

    Returns raw Notion page dicts. Only the first 100 results are fetched
    (sufficient for a personal database; no pagination for v1).
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_NOTION_API_BASE}/databases/{settings.notion_todo_database_id}/query",
            headers=_headers(),
            json={
                "filter": {
                    "property": "Status",
                    "status": {"does_not_equal": "Done"},
                },
                "page_size": 100,
            },
        )
        resp.raise_for_status()
        return resp.json().get("results", [])


# ── DB upsert ─────────────────────────────────────────────────────────────────


async def _upsert_tasks(session: AsyncSession, pages: list[dict]) -> int:
    """
    Normalize and upsert a list of raw Notion page dicts.

    Inserts new tasks; updates title, due_at, and raw_json on existing ones.
    Does NOT commit — caller owns the transaction.
    Returns the number of pages processed.
    """
    for page in pages:
        task = normalize_task(page)
        result = await session.execute(
            select(TaskModel).where(TaskModel.external_id == task.external_id)
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            session.add(
                TaskModel(
                    external_id=task.external_id,
                    source=task.source.value,
                    title=task.title,
                    description=task.description,
                    is_done=task.is_done,
                    due_at=task.due_at,
                    priority=task.priority,
                    raw_json=task.raw_json,
                )
            )
        else:
            existing.title = task.title
            existing.due_at = task.due_at
            existing.raw_json = task.raw_json
    return len(pages)


# ── public sync entry point ───────────────────────────────────────────────────


async def sync_notion(session: AsyncSession) -> dict:
    """
    Fetch open tasks from the Notion todo database and upsert them.

    Returns {"synced": N}.
    """
    pages = await fetch_open_tasks()
    count = await _upsert_tasks(session, pages)
    await session.commit()
    return {"synced": count}
