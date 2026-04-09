"""
Notion integration tests.

Tests normalize_task() directly and the sync/feed behaviour:
- Tasks are stored and survive (no window pruning for tasks)
- The feed source filter correctly isolates notion items
- Preview text reflects the due-date relationship to today
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from app.services.notion import normalize_task
from app.routers.feed import _task_preview

_NOW = datetime.now(tz=timezone.utc)


# ── raw page fixtures ─────────────────────────────────────────────────────────

def _make_page(
    page_id: str,
    title: str,
    due_date: str | None = None,
    last_edited: str = "2026-04-09T10:00:00.000Z",
) -> dict:
    """Helper to build a minimal Notion page dict matching the user's schema."""
    date_prop = {"date": {"start": due_date}} if due_date else {"date": None}
    return {
        "id": page_id,
        "last_edited_time": last_edited,
        "properties": {
            "Task": {"type": "title", "title": [{"plain_text": title}]},
            "Status": {"type": "status", "status": {"name": "In progress"}},
            "Date": {"type": "date", **date_prop},
        },
    }


_PAGE_WITH_DUE = _make_page("page-1111", "Buy groceries", due_date=(_NOW + timedelta(days=2)).strftime("%Y-%m-%d"))
_PAGE_NO_DUE = _make_page("page-2222", "Read backlog")
_PAGE_OVERDUE = _make_page("page-3333", "File taxes", due_date=(_NOW - timedelta(days=3)).strftime("%Y-%m-%d"))
_PAGE_DUE_TODAY = _make_page("page-4444", "Call dentist", due_date=_NOW.strftime("%Y-%m-%d"))
_PAGE_NO_TITLE = {
    "id": "page-5555",
    "last_edited_time": "2026-04-09T10:00:00.000Z",
    "properties": {
        "Task": {"type": "title", "title": []},
        "Status": {"type": "status", "status": {"name": "In progress"}},
        "Date": {"type": "date", "date": None},
    },
}


# ── normalize_task unit tests ─────────────────────────────────────────────────


def test_normalize_task_with_due_date() -> None:
    task = normalize_task(_PAGE_WITH_DUE)

    assert task.external_id == "page-1111"
    assert task.source.value == "notion"
    assert task.title == "Buy groceries"
    assert task.is_done is False
    assert task.due_at is not None
    assert task.due_at.tzinfo is not None


def test_normalize_task_no_due_date() -> None:
    task = normalize_task(_PAGE_NO_DUE)
    assert task.title == "Read backlog"
    assert task.due_at is None


def test_normalize_task_no_title_falls_back() -> None:
    task = normalize_task(_PAGE_NO_TITLE)
    assert task.title == "(untitled)"


def test_normalize_task_stores_last_edited_in_raw_json() -> None:
    task = normalize_task(_PAGE_NO_DUE)
    assert task.raw_json is not None
    assert task.raw_json["last_edited_time"] == "2026-04-09T10:00:00.000Z"


# ── _task_preview unit tests ──────────────────────────────────────────────────


def test_preview_no_due_date() -> None:
    assert _task_preview(None) == "No due date"


def test_preview_due_today() -> None:
    assert _task_preview(_NOW) == "Due today"


def test_preview_due_tomorrow() -> None:
    assert _task_preview(_NOW + timedelta(days=1)) == "Due tomorrow"


def test_preview_due_in_n_days() -> None:
    assert _task_preview(_NOW + timedelta(days=5)) == "Due in 5 days"


def test_preview_overdue_by_1_day() -> None:
    assert _task_preview(_NOW - timedelta(days=1)) == "Overdue by 1 day"


def test_preview_overdue_by_n_days() -> None:
    assert _task_preview(_NOW - timedelta(days=4)) == "Overdue by 4 days"


# ── sync endpoint ─────────────────────────────────────────────────────────────


async def test_notion_sync_stores_tasks(client: AsyncClient) -> None:
    with (
        patch("app.routers.notion.settings") as mock_settings,
        patch(
            "app.services.notion.fetch_open_tasks",
            new=AsyncMock(return_value=[_PAGE_WITH_DUE, _PAGE_NO_DUE]),
        ),
    ):
        mock_settings.notion_token = "fake-token"
        mock_settings.notion_todo_database_id = "fake-db-id"
        resp = await client.post("/api/notion/sync")

    assert resp.status_code == 200
    assert resp.json()["synced"] == 2


async def test_notion_sync_is_idempotent(client: AsyncClient) -> None:
    with (
        patch("app.routers.notion.settings") as mock_settings,
        patch(
            "app.services.notion.fetch_open_tasks",
            new=AsyncMock(return_value=[_PAGE_WITH_DUE]),
        ),
    ):
        mock_settings.notion_token = "fake-token"
        mock_settings.notion_todo_database_id = "fake-db-id"
        await client.post("/api/notion/sync")
        resp = await client.post("/api/notion/sync")

    assert resp.status_code == 200
    assert resp.json()["synced"] == 1


async def test_notion_sync_requires_config(client: AsyncClient) -> None:
    with patch("app.routers.notion.settings") as mock_settings:
        mock_settings.notion_token = ""
        mock_settings.notion_todo_database_id = ""
        resp = await client.post("/api/notion/sync")
    assert resp.status_code == 503


# ── feed source filter ────────────────────────────────────────────────────────


async def _sync_notion(client: AsyncClient, pages: list[dict]) -> None:
    with (
        patch("app.routers.notion.settings") as mock_settings,
        patch(
            "app.services.notion.fetch_open_tasks",
            new=AsyncMock(return_value=pages),
        ),
    ):
        mock_settings.notion_token = "fake-token"
        mock_settings.notion_todo_database_id = "fake-db-id"
        resp = await client.post("/api/notion/sync")
    assert resp.status_code == 200


async def test_feed_source_filter_notion(client: AsyncClient) -> None:
    await _sync_notion(client, [_PAGE_WITH_DUE, _PAGE_NO_DUE])

    resp = await client.get("/api/feed/?source=notion")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    assert all(i["source"] == "notion" for i in items)
    assert all(i["item_type"] == "task" for i in items)


async def test_feed_source_filter_excludes_other_sources(client: AsyncClient) -> None:
    await _sync_notion(client, [_PAGE_WITH_DUE])

    resp = await client.get("/api/feed/?source=gmail")
    assert resp.status_code == 200
    assert resp.json() == []  # no gmail items synced


async def test_feed_consolidated_includes_notion_tasks(client: AsyncClient) -> None:
    await _sync_notion(client, [_PAGE_WITH_DUE])

    resp = await client.get("/api/feed/")
    assert resp.status_code == 200
    items = resp.json()
    notion_items = [i for i in items if i["source"] == "notion"]
    assert len(notion_items) == 1
    assert notion_items[0]["item_type"] == "task"
    assert notion_items[0]["is_read"] is False


# ── feed task content ─────────────────────────────────────────────────────────


async def test_feed_task_preview_overdue(client: AsyncClient) -> None:
    await _sync_notion(client, [_PAGE_OVERDUE])

    items = (await client.get("/api/feed/?source=notion")).json()
    assert "Overdue" in items[0]["preview"]


async def test_feed_task_preview_due_today(client: AsyncClient) -> None:
    await _sync_notion(client, [_PAGE_DUE_TODAY])

    items = (await client.get("/api/feed/?source=notion")).json()
    assert items[0]["preview"] == "Due today"


async def test_feed_task_preview_no_due_date(client: AsyncClient) -> None:
    await _sync_notion(client, [_PAGE_NO_DUE])

    items = (await client.get("/api/feed/?source=notion")).json()
    assert items[0]["preview"] == "No due date"


async def test_feed_task_sorted_by_due_date(client: AsyncClient) -> None:
    """Task with earlier due_at (overdue) sorts below task with later due_at."""
    await _sync_notion(client, [_PAGE_OVERDUE, _PAGE_WITH_DUE])

    items = (await client.get("/api/feed/?source=notion")).json()
    times = [i["received_at"] for i in items]
    assert times == sorted(times, reverse=True)
    # _PAGE_WITH_DUE is in the future → sorts above _PAGE_OVERDUE (past)
    assert items[0]["title"] == "Buy groceries"
    assert items[1]["title"] == "File taxes"
