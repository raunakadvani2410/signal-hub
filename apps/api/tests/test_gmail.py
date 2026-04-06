"""
Gmail router tests.

All Google API calls are mocked — these tests never hit Google's servers.
They verify endpoint behavior: correct status codes, response shapes,
and error handling when credentials are missing or tokens are absent.
"""

from unittest.mock import AsyncMock, patch

from app.services.gmail import HistoryExpiredError, normalize_message

from httpx import AsyncClient


# ── /api/gmail/auth ───────────────────────────────────────────────────────────


async def test_gmail_auth_returns_503_when_not_configured(client: AsyncClient) -> None:
    # Explicitly zero out credentials — the test must not rely on .env being empty.
    with patch("app.routers.gmail.settings") as mock_settings:
        mock_settings.gmail_client_id = ""
        mock_settings.gmail_client_secret = ""
        response = await client.get("/api/gmail/auth", follow_redirects=False)
    assert response.status_code == 503
    assert "GMAIL_CLIENT_ID" in response.json()["detail"]


async def test_gmail_auth_redirects_to_google_when_configured(client: AsyncClient) -> None:
    fake_url = "https://accounts.google.com/o/oauth2/auth?client_id=fake"
    with (
        patch("app.routers.gmail.settings") as mock_settings,
        patch("app.routers.gmail.build_auth_url", return_value=fake_url),
    ):
        mock_settings.gmail_client_id = "fake-client-id"
        mock_settings.gmail_client_secret = "fake-client-secret"
        response = await client.get("/api/gmail/auth", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == fake_url


# ── /api/gmail/callback ───────────────────────────────────────────────────────


async def test_gmail_callback_missing_code_returns_400(client: AsyncClient) -> None:
    response = await client.get("/api/gmail/callback")
    assert response.status_code == 400
    assert "code" in response.json()["detail"].lower()


async def test_gmail_callback_state_mismatch_returns_400(client: AsyncClient) -> None:
    def _raise_state_error(code: str, state: str) -> None:
        raise ValueError("OAuth state mismatch — possible CSRF attempt.")

    with patch("app.routers.gmail.exchange_code", side_effect=_raise_state_error):
        response = await client.get("/api/gmail/callback?code=abc&state=wrong")

    assert response.status_code == 400
    assert "mismatch" in response.json()["detail"].lower()


async def test_gmail_callback_success_returns_connected(client: AsyncClient) -> None:
    fake_tokens = {
        "access_token": "ya29.fake",
        "refresh_token": "1//fake",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "fake-client-id",
        "client_secret": "fake-secret",
        "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
    }
    fake_profile = {
        "emailAddress": "user@gmail.com",
        "messagesTotal": 100,
        "threadsTotal": 50,
        "historyId": "12345",
    }

    with (
        patch("app.routers.gmail.exchange_code", return_value=fake_tokens),
        patch("app.routers.gmail.fetch_profile", new=AsyncMock(return_value=fake_profile)),
    ):
        response = await client.get("/api/gmail/callback?code=valid_code&state=valid_state")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "connected"
    assert data["email"] == "user@gmail.com"


# ── /api/gmail/profile ────────────────────────────────────────────────────────


async def test_gmail_profile_returns_401_when_not_connected(client: AsyncClient) -> None:
    with patch("app.routers.gmail.load_tokens", return_value=None):
        response = await client.get("/api/gmail/profile")
    assert response.status_code == 401
    assert "not connected" in response.json()["detail"].lower()


async def test_gmail_profile_returns_profile_when_connected(client: AsyncClient) -> None:
    fake_profile = {
        "emailAddress": "user@gmail.com",
        "messagesTotal": 1234,
        "threadsTotal": 567,
        "historyId": "99999",
    }
    with (
        patch("app.routers.gmail.load_tokens", return_value={"access_token": "fake-token"}),
        patch("app.routers.gmail.fetch_profile", new=AsyncMock(return_value=fake_profile)),
    ):
        response = await client.get("/api/gmail/profile")

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "user@gmail.com"
    assert data["messages_total"] == 1234
    assert data["threads_total"] == 567


async def test_gmail_profile_returns_502_on_api_error(client: AsyncClient) -> None:
    with (
        patch("app.routers.gmail.load_tokens", return_value={"access_token": "fake-token"}),
        patch(
            "app.routers.gmail.fetch_profile",
            new=AsyncMock(side_effect=Exception("Gmail API unavailable")),
        ),
    ):
        response = await client.get("/api/gmail/profile")

    assert response.status_code == 502


# ── /api/gmail/status ─────────────────────────────────────────────────────────


async def test_gmail_status_not_connected_when_no_token_file(
    client: AsyncClient,
) -> None:
    with patch("app.routers.gmail.load_tokens", return_value=None):
        resp = await client.get("/api/gmail/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is False
    assert data["has_refresh_token"] is False


async def test_gmail_status_not_connected_without_refresh_token(
    client: AsyncClient,
) -> None:
    # Token file exists but has only an access token (no refresh_token).
    # connected must be False — the token cannot self-heal after expiry.
    with patch(
        "app.routers.gmail.load_tokens",
        return_value={"access_token": "tok"},
    ):
        resp = await client.get("/api/gmail/status")
    data = resp.json()
    assert data["connected"] is False
    assert data["has_refresh_token"] is False


async def test_gmail_status_connected_with_refresh_token(client: AsyncClient) -> None:
    with patch(
        "app.routers.gmail.load_tokens",
        return_value={"access_token": "tok", "refresh_token": "rtok"},
    ):
        resp = await client.get("/api/gmail/status")
    data = resp.json()
    assert data["connected"] is True
    assert data["has_refresh_token"] is True
    assert "last_synced_at" in data
    assert "history_id" in data


# ── _get_valid_credentials (unit) ────────────────────────────────────────────


async def test_credentials_refresh_when_no_expiry_stored() -> None:
    """
    Regression: tokens written without 'expiry' must trigger a proactive refresh.
    Without the fix, Credentials(expiry=None).valid is True and refresh is skipped,
    sending an expired access token to the API.
    """
    from unittest.mock import MagicMock
    from app.services.gmail import _get_valid_credentials

    stored_tokens = {
        "access_token": "stale_token",
        "refresh_token": "valid_refresh",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "fake",
        "client_secret": "fake",
        "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
        # deliberately no "expiry" key — simulates tokens stored before this fix
    }

    refreshed_tokens = {**stored_tokens, "access_token": "fresh_token", "expiry": "2099-01-01T00:00:00"}

    def fake_refresh(request):
        # Simulate what google-auth does when refresh succeeds
        pass

    new_creds = MagicMock()
    new_creds.token = "fresh_token"
    new_creds.expiry = None

    with (
        patch("app.services.gmail.load_tokens", return_value=stored_tokens),
        patch("app.services.gmail.save_tokens") as mock_save,
        patch("app.services.gmail.run_in_threadpool", new=AsyncMock()) as mock_refresh,
    ):
        mock_refresh.return_value = None
        # Patch the Credentials class so we can inspect what expiry was passed in
        from google.oauth2.credentials import Credentials as RealCreds
        original_init = RealCreds.__init__

        expiry_passed = {}

        def capturing_init(self, *args, **kwargs):
            expiry_passed["value"] = kwargs.get("expiry")
            original_init(self, *args, **kwargs)

        with patch.object(RealCreds, "__init__", capturing_init):
            await _get_valid_credentials()

        # expiry should have been None (no 'expiry' in stored_tokens)
        assert expiry_passed["value"] is None
        # refresh must have been called despite creds.valid appearing True
        mock_refresh.assert_called_once()


# ── normalize_message (unit) ──────────────────────────────────────────────────

_FAKE_RAW = {
    "id": "msg001",
    "threadId": "thread001",
    "labelIds": ["INBOX", "UNREAD"],
    "snippet": "Hey, just checking in.",
    "internalDate": "1743807600000",  # 2025-04-05 in ms
    "historyId": "9000",
    "payload": {
        "headers": [
            {"name": "From", "value": "Alice <alice@example.com>"},
            {"name": "Subject", "value": "Quick question"},
        ]
    },
}


def test_normalize_message_extracts_all_fields() -> None:
    msg = normalize_message(_FAKE_RAW)
    assert msg.external_id == "msg001"
    assert msg.thread_id == "thread001"
    assert msg.source.value == "gmail"
    assert msg.sender == "Alice <alice@example.com>"
    assert msg.subject == "Quick question"
    assert msg.body_preview == "Hey, just checking in."
    assert msg.is_read is False  # UNREAD in labelIds


def test_normalize_message_marks_read_when_unread_label_absent() -> None:
    raw = {**_FAKE_RAW, "labelIds": ["INBOX"]}
    assert normalize_message(raw).is_read is True


def test_normalize_message_subject_is_none_when_missing() -> None:
    raw = {**_FAKE_RAW, "payload": {"headers": [{"name": "From", "value": "x@y.com"}]}}
    assert normalize_message(raw).subject is None


# ── /api/gmail/sync ───────────────────────────────────────────────────────────


async def test_gmail_sync_returns_401_when_not_connected(client: AsyncClient) -> None:
    with patch("app.routers.gmail.load_tokens", return_value=None):
        response = await client.post("/api/gmail/sync")
    assert response.status_code == 401
    assert "not connected" in response.json()["detail"].lower()


async def test_gmail_sync_first_run_does_full_sync(client: AsyncClient) -> None:
    """No history_id stored → full fetch; response includes mode and history_id."""
    with (
        patch("app.routers.gmail.load_tokens", return_value={"access_token": "fake"}),
        patch(
            "app.services.gmail.fetch_inbox_messages",
            new=AsyncMock(return_value=[_FAKE_RAW]),
        ),
    ):
        resp = await client.post("/api/gmail/sync")

    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "full"
    assert data["synced"] == 1
    assert data["history_id"] == "9000"

    msgs = await client.get("/api/messages/")
    assert len(msgs.json()) == 1
    assert msgs.json()[0]["external_id"] == "msg001"


async def test_gmail_sync_subsequent_run_uses_incremental(client: AsyncClient) -> None:
    """After a full sync stores a history_id, the next call uses the incremental path."""
    # Seed the integration with a history_id via a full sync.
    with (
        patch("app.routers.gmail.load_tokens", return_value={"access_token": "fake"}),
        patch(
            "app.services.gmail.fetch_inbox_messages",
            new=AsyncMock(return_value=[_FAKE_RAW]),
        ),
    ):
        await client.post("/api/gmail/sync")

    # Second sync hits the incremental path (mocked directly).
    with (
        patch("app.routers.gmail.load_tokens", return_value={"access_token": "fake"}),
        patch(
            "app.services.gmail._incremental_sync",
            new=AsyncMock(return_value=(2, "9001")),
        ),
    ):
        resp = await client.post("/api/gmail/sync")

    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "incremental"
    assert data["synced"] == 2
    assert data["history_id"] == "9001"


async def test_gmail_sync_falls_back_to_full_on_expired_history(
    client: AsyncClient,
) -> None:
    """If incremental raises HistoryExpiredError, sync falls back to a full fetch."""
    # Seed history_id via an initial full sync.
    with (
        patch("app.routers.gmail.load_tokens", return_value={"access_token": "fake"}),
        patch(
            "app.services.gmail.fetch_inbox_messages",
            new=AsyncMock(return_value=[_FAKE_RAW]),
        ),
    ):
        await client.post("/api/gmail/sync")

    # Incremental path raises; should fall back to full.
    with (
        patch("app.routers.gmail.load_tokens", return_value={"access_token": "fake"}),
        patch(
            "app.services.gmail._incremental_sync",
            new=AsyncMock(side_effect=HistoryExpiredError()),
        ),
        patch(
            "app.services.gmail.fetch_inbox_messages",
            new=AsyncMock(return_value=[_FAKE_RAW]),
        ),
    ):
        resp = await client.post("/api/gmail/sync")

    assert resp.status_code == 200
    assert resp.json()["mode"] == "full"

    # Idempotency: the same message is not duplicated.
    msgs = await client.get("/api/messages/")
    assert len(msgs.json()) == 1
