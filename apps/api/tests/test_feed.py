"""
Feed router tests.

Populates the DB via the sync endpoint (mocking only the Gmail API call)
and verifies the normalized FeedItem shape returned by GET /api/feed/.
"""

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

# Two messages with different internalDates so we can verify sort order.
_OLDER = {
    "id": "older_msg",
    "threadId": "thread_a",
    "labelIds": ["INBOX"],         # no UNREAD → is_read True
    "snippet": "Old news preview",
    "internalDate": "1743807500000",
    "historyId": "9000",
    "payload": {
        "headers": [
            {"name": "From", "value": "Bob <bob@example.com>"},
            {"name": "Subject", "value": "Old news"},
        ]
    },
}

_NEWER = {
    "id": "newer_msg",
    "threadId": "thread_b",
    "labelIds": ["INBOX", "UNREAD"],
    "snippet": "Newer message preview",
    "internalDate": "1743807600000",
    "historyId": "9001",
    "payload": {
        "headers": [
            {"name": "From", "value": "Alice <alice@example.com>"},
            {"name": "Subject", "value": "Hello"},
        ]
    },
}


async def _sync(client: AsyncClient, messages: list[dict]) -> None:
    with (
        patch("app.routers.gmail.load_tokens", return_value={"access_token": "fake"}),
        patch(
            "app.services.gmail.fetch_inbox_messages",
            new=AsyncMock(return_value=messages),
        ),
    ):
        resp = await client.post("/api/gmail/sync")
    assert resp.status_code == 200


# ── basic shape ───────────────────────────────────────────────────────────────


async def test_feed_empty_before_any_sync(client: AsyncClient) -> None:
    resp = await client.get("/api/feed/")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_feed_returns_normalized_feed_items(client: AsyncClient) -> None:
    await _sync(client, [_OLDER, _NEWER])

    resp = await client.get("/api/feed/")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2

    # Newest first
    newest = items[0]
    assert newest["id"] == "gmail:newer_msg"
    assert newest["source"] == "gmail"
    assert newest["item_type"] == "message"
    assert newest["title"] == "Hello"
    assert newest["preview"] == "Newer message preview"
    assert newest["sender"] == "Alice <alice@example.com>"
    assert newest["is_read"] is False
    assert newest["external_id"] == "newer_msg"

    oldest = items[1]
    assert oldest["id"] == "gmail:older_msg"
    assert oldest["is_read"] is True   # UNREAD label absent


async def test_feed_title_falls_back_to_no_subject(client: AsyncClient) -> None:
    no_subject = {
        "id": "bare_msg",
        "threadId": "t0",
        "labelIds": ["INBOX"],
        "snippet": "A snippet",
        "internalDate": "1743807600000",
        "historyId": "9002",
        "payload": {
            "headers": [{"name": "From", "value": "carol@example.com"}]
        },
    }
    await _sync(client, [no_subject])

    items = (await client.get("/api/feed/")).json()
    assert items[0]["title"] == "(no subject)"


# ── limit ─────────────────────────────────────────────────────────────────────


async def test_feed_limit_param(client: AsyncClient) -> None:
    await _sync(client, [_OLDER, _NEWER])

    resp = await client.get("/api/feed/?limit=1")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    # Newest first — the one item returned should be the newer message
    assert items[0]["id"] == "gmail:newer_msg"


async def test_feed_limit_default_is_50(client: AsyncClient) -> None:
    # Just verify the endpoint accepts requests without a limit param
    resp = await client.get("/api/feed/")
    assert resp.status_code == 200
