"""
Gmail router tests.

All Google API calls are mocked — these tests never hit Google's servers.
They verify endpoint behavior: correct status codes, response shapes,
and error handling when credentials are missing or tokens are absent.
"""

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient


# ── /api/gmail/auth ───────────────────────────────────────────────────────────


async def test_gmail_auth_returns_503_when_not_configured(client: AsyncClient) -> None:
    # In the test environment GMAIL_CLIENT_ID defaults to "" → 503.
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
