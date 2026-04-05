"""
Gmail integration service — OAuth scaffolding only.

Handles:
  - building the Google OAuth consent URL
  - exchanging an authorization code for access + refresh tokens
  - fetching the authenticated user's Gmail profile
  - refreshing an expired access token

Does NOT implement inbox sync. That is Phase 3.

Token storage
-------------
Access and refresh tokens are stored at {settings.token_dir}/gmail.json.
The directory is gitignored via .tokens/.
OAuth CSRF state is stored at {settings.token_dir}/.gmail_oauth_state.

Threading note
--------------
google-auth-oauthlib uses the synchronous `requests` library internally.
Functions that call it (build_auth_url, exchange_code, and token refresh) are
synchronous and must be called via starlette's run_in_threadpool from async
router handlers.
"""

import json
from pathlib import Path

import httpx
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from starlette.concurrency import run_in_threadpool

from app.config import settings

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

_GMAIL_PROFILE_URL = "https://www.googleapis.com/gmail/v1/users/me/profile"


# ── helpers ───────────────────────────────────────────────────────────────────


def _token_dir() -> Path:
    path = Path(settings.token_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _token_path() -> Path:
    return _token_dir() / "gmail.json"


def _state_path() -> Path:
    return _token_dir() / ".gmail_oauth_state"


def _client_config() -> dict:
    return {
        "web": {
            "client_id": settings.gmail_client_id,
            "client_secret": settings.gmail_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.gmail_redirect_uri],
        }
    }


# ── token persistence ─────────────────────────────────────────────────────────


def load_tokens() -> dict | None:
    path = _token_path()
    return json.loads(path.read_text()) if path.exists() else None


def save_tokens(tokens: dict) -> None:
    _token_path().write_text(json.dumps(tokens, indent=2))


def _save_oauth_state(state: str) -> None:
    _state_path().write_text(state)


def _load_oauth_state() -> str | None:
    path = _state_path()
    return path.read_text().strip() if path.exists() else None


# ── OAuth flow (synchronous — wrap with run_in_threadpool) ────────────────────


def build_auth_url() -> str:
    """
    Build the Google OAuth consent URL and persist CSRF state to disk.
    Returns the URL string to redirect the user's browser to.
    """
    flow = Flow.from_client_config(
        _client_config(),
        scopes=SCOPES,
        redirect_uri=settings.gmail_redirect_uri,
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",          # forces refresh_token to be returned
        include_granted_scopes="true",
    )
    _save_oauth_state(state)
    return auth_url


def exchange_code(code: str, state: str) -> dict:
    """
    Exchange an OAuth authorization code for access and refresh tokens.
    Verifies the CSRF state, then persists the token set to disk.
    Returns the raw token dict.
    """
    saved_state = _load_oauth_state()
    if saved_state and saved_state != state:
        raise ValueError("OAuth state mismatch — possible CSRF attempt.")

    flow = Flow.from_client_config(
        _client_config(),
        scopes=SCOPES,
        redirect_uri=settings.gmail_redirect_uri,
        state=state,
    )
    flow.fetch_token(code=code)
    creds = flow.credentials

    tokens = {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes or SCOPES),
    }
    save_tokens(tokens)
    return tokens


# ── profile fetch (async) ─────────────────────────────────────────────────────


async def fetch_profile() -> dict:
    """
    Fetch the authenticated user's Gmail profile.
    Refreshes the access token automatically if it has expired.

    Returns a dict with keys: emailAddress, messagesTotal, threadsTotal, historyId.
    Raises RuntimeError if no tokens are stored.
    Raises httpx.HTTPStatusError on Gmail API errors.
    """
    tokens = load_tokens()
    if not tokens:
        raise RuntimeError("No Gmail tokens found. Complete the OAuth flow first.")

    creds = Credentials(
        token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
        token_uri=tokens["token_uri"],
        client_id=tokens["client_id"],
        client_secret=tokens["client_secret"],
        scopes=tokens.get("scopes"),
    )

    # Token refresh is synchronous (uses requests internally).
    if not creds.valid and creds.refresh_token:
        await run_in_threadpool(creds.refresh, GoogleRequest())
        tokens["access_token"] = creds.token
        save_tokens(tokens)

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            _GMAIL_PROFILE_URL,
            headers={"Authorization": f"Bearer {creds.token}"},
        )
        resp.raise_for_status()
        return resp.json()
