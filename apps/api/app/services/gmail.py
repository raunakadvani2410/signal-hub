"""
Gmail integration service.

Handles:
  - building the Google OAuth consent URL
  - exchanging an authorization code for access + refresh tokens
  - fetching the authenticated user's Gmail profile
  - refreshing an expired access token
  - syncing a batch of inbox messages into the DB

Token storage
-------------
Access and refresh tokens are stored at {settings.token_dir}/gmail.json.
The directory is gitignored via .tokens/.
OAuth CSRF state is stored at {settings.token_dir}/.gmail_oauth_state.
PKCE code verifier is stored at {settings.token_dir}/.gmail_code_verifier.

Threading note
--------------
google-auth-oauthlib uses the synchronous `requests` library internally.
Functions that call it (build_auth_url, exchange_code, and token refresh) are
synchronous and must be called via starlette's run_in_threadpool from async
router handlers.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from signal_hub_shared.models import ItemSource, Message
from app.config import settings
from app.db.models.integration import IntegrationModel
from app.db.models.message import MessageModel

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

_GMAIL_PROFILE_URL = "https://www.googleapis.com/gmail/v1/users/me/profile"
_GMAIL_API_BASE = "https://www.googleapis.com/gmail/v1/users/me"


# ── helpers ───────────────────────────────────────────────────────────────────


def _token_dir() -> Path:
    path = Path(settings.token_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _token_path() -> Path:
    return _token_dir() / "gmail.json"


def _state_path() -> Path:
    return _token_dir() / ".gmail_oauth_state"


def _verifier_path() -> Path:
    return _token_dir() / ".gmail_code_verifier"


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


def _save_code_verifier(verifier: str) -> None:
    _verifier_path().write_text(verifier)


def _load_code_verifier() -> str | None:
    path = _verifier_path()
    return path.read_text().strip() if path.exists() else None


# ── credential helper ─────────────────────────────────────────────────────────


async def _get_valid_credentials() -> Credentials:
    """
    Load stored tokens and return valid Credentials, refreshing when necessary.

    Refresh is triggered when:
      - The access token is expired (creds.valid is False), OR
      - No expiry was stored (tokens written before expiry tracking was added —
        validity cannot be verified, so a proactive refresh is the safe choice).

    google-auth uses naive UTC datetimes for expiry internally, so we round-trip
    the expiry field as a naive-UTC ISO string to stay compatible.
    """
    tokens = load_tokens()
    if not tokens:
        raise RuntimeError("No Gmail tokens found. Complete the OAuth flow first.")

    expiry_str = tokens.get("expiry")
    expiry = datetime.fromisoformat(expiry_str) if expiry_str else None

    creds = Credentials(
        token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
        token_uri=tokens["token_uri"],
        client_id=tokens["client_id"],
        client_secret=tokens["client_secret"],
        scopes=tokens.get("scopes"),
        expiry=expiry,
    )

    if (not creds.valid or expiry is None) and creds.refresh_token:
        await run_in_threadpool(creds.refresh, GoogleRequest())
        tokens["access_token"] = creds.token
        tokens["expiry"] = creds.expiry.isoformat() if creds.expiry else None
        save_tokens(tokens)

    return creds


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
    if flow.code_verifier:
        _save_code_verifier(flow.code_verifier)
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
    flow.code_verifier = _load_code_verifier()
    flow.fetch_token(code=code)
    creds = flow.credentials

    tokens = {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes or SCOPES),
        # Store expiry so _get_valid_credentials can detect staleness without
        # an extra round-trip to Google. google-auth uses naive UTC datetimes.
        "expiry": creds.expiry.isoformat() if creds.expiry else None,
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
    creds = await _get_valid_credentials()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            _GMAIL_PROFILE_URL,
            headers={"Authorization": f"Bearer {creds.token}"},
        )
        resp.raise_for_status()
        return resp.json()


# ── inbox sync ────────────────────────────────────────────────────────────────


class HistoryExpiredError(Exception):
    """
    Raised when the stored historyId is too old for incremental sync.
    The caller should fall back to a full fetch.

    Gmail returns HTTP 404 with reason "invalidHistoryId" when a historyId
    is more than roughly 7 days old or has been invalidated server-side.
    """


def _header(headers: list[dict], name: str) -> str:
    """Extract a header value by name (case-insensitive). Returns "" if absent."""
    name_lower = name.lower()
    for h in headers:
        if h.get("name", "").lower() == name_lower:
            return h.get("value", "")
    return ""


def normalize_message(raw: dict) -> Message:
    """
    Normalize a raw Gmail API message (format=metadata) into a shared Message.

    raw is the JSON object returned by messages.get with format=metadata.
    internalDate (milliseconds since epoch) is used for received_at.
    """
    headers = raw.get("payload", {}).get("headers", [])
    received_at = datetime.fromtimestamp(
        int(raw.get("internalDate", "0")) / 1000, tz=timezone.utc
    )
    subject = _header(headers, "Subject") or None
    return Message(
        external_id=raw["id"],
        source=ItemSource.GMAIL,
        sender=_header(headers, "From"),
        subject=subject,
        body_preview=raw.get("snippet", ""),
        is_read="UNREAD" not in raw.get("labelIds", []),
        received_at=received_at,
        thread_id=raw.get("threadId"),
        raw_json=None,
    )


async def fetch_inbox_messages(batch_size: int = 20) -> list[dict]:
    """
    Fetch raw metadata-format message dicts from the Gmail inbox.
    Makes one list call then one per-message detail call (sequential).
    Each returned dict includes historyId, labelIds, snippet, internalDate, payload.
    """
    creds = await _get_valid_credentials()
    auth_header = {"Authorization": f"Bearer {creds.token}"}

    async with httpx.AsyncClient() as client:
        list_resp = await client.get(
            f"{_GMAIL_API_BASE}/messages",
            headers=auth_header,
            params={"labelIds": "INBOX", "maxResults": batch_size},
        )
        list_resp.raise_for_status()
        stubs = list_resp.json().get("messages", [])

        raw_messages = []
        for stub in stubs:
            detail_resp = await client.get(
                f"{_GMAIL_API_BASE}/messages/{stub['id']}",
                headers=auth_header,
                params=[
                    ("format", "metadata"),
                    ("metadataHeaders", "From"),
                    ("metadataHeaders", "Subject"),
                ],
            )
            detail_resp.raise_for_status()
            raw_messages.append(detail_resp.json())

        return raw_messages


async def _upsert_messages(session: AsyncSession, raw_messages: list[dict]) -> int:
    """
    Normalize and upsert a list of raw Gmail message dicts.

    Inserts new messages; updates is_read on existing ones.
    Does NOT commit — caller is responsible for the commit.
    Returns the number of messages processed.
    """
    for raw in raw_messages:
        msg = normalize_message(raw)
        result = await session.execute(
            select(MessageModel).where(MessageModel.external_id == msg.external_id)
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            session.add(
                MessageModel(
                    external_id=msg.external_id,
                    source=msg.source.value,
                    sender=msg.sender,
                    subject=msg.subject,
                    body_preview=msg.body_preview,
                    is_read=msg.is_read,
                    received_at=msg.received_at,
                    thread_id=msg.thread_id,
                    raw_json=msg.raw_json,
                )
            )
        else:
            existing.is_read = msg.is_read
    return len(raw_messages)


async def _full_sync(session: AsyncSession, batch_size: int = 20) -> tuple[int, str]:
    """
    Fetch the most recent `batch_size` inbox messages and upsert them.

    Returns (message_count, new_history_id).
    historyId comes from the first (most-recent) message; if the inbox is empty
    it falls back to the profile endpoint.
    """
    raw_messages = await fetch_inbox_messages(batch_size)

    if raw_messages:
        new_history_id = raw_messages[0].get("historyId", "")
    else:
        profile = await fetch_profile()
        new_history_id = profile.get("historyId", "")

    count = await _upsert_messages(session, raw_messages)
    return count, new_history_id


async def _incremental_sync(
    session: AsyncSession, integration: IntegrationModel
) -> tuple[int, str]:
    """
    Fetch only messages added since integration.history_id using the History API.

    Returns (new_message_count, new_history_id).
    Raises HistoryExpiredError when Gmail returns 404 (historyId is too old).
    """
    creds = await _get_valid_credentials()
    auth_header = {"Authorization": f"Bearer {creds.token}"}

    async with httpx.AsyncClient() as client:
        history_resp = await client.get(
            f"{_GMAIL_API_BASE}/history",
            headers=auth_header,
            params={
                "startHistoryId": integration.history_id,
                "historyTypes": "messageAdded",
                "labelId": "INBOX",
            },
        )

        if history_resp.status_code == 404:
            raise HistoryExpiredError(
                f"historyId {integration.history_id!r} is no longer valid"
            )
        history_resp.raise_for_status()

        data = history_resp.json()
        new_history_id = data.get("historyId", integration.history_id)

        # Collect unique message IDs from all history records.
        seen: set[str] = set()
        new_ids: list[str] = []
        for record in data.get("history", []):
            for added in record.get("messagesAdded", []):
                msg_stub = added.get("message", {})
                msg_id = msg_stub.get("id", "")
                if msg_id and msg_id not in seen:
                    seen.add(msg_id)
                    new_ids.append(msg_id)

        # Fetch full metadata for each new message.
        raw_messages = []
        for msg_id in new_ids:
            detail_resp = await client.get(
                f"{_GMAIL_API_BASE}/messages/{msg_id}",
                headers=auth_header,
                params=[
                    ("format", "metadata"),
                    ("metadataHeaders", "From"),
                    ("metadataHeaders", "Subject"),
                ],
            )
            if detail_resp.status_code == 404:
                # Message was deleted before we could fetch it — skip.
                continue
            detail_resp.raise_for_status()
            raw_messages.append(detail_resp.json())

        count = await _upsert_messages(session, raw_messages)
        return count, new_history_id


async def sync_gmail(session: AsyncSession) -> dict:
    """
    Synchronize Gmail inbox into the DB.

    Decision logic:
      - integration.history_id is None  → full fetch (first run or after reset)
      - history_id is set               → incremental via History API
      - incremental returns 404         → historyId expired, fall back to full

    Commits history_id and last_synced_at atomically with the message upserts.
    Returns {"mode", "synced", "history_id"}.
    """
    result = await session.execute(
        select(IntegrationModel).where(IntegrationModel.integration_key == "gmail")
    )
    integration = result.scalar_one()

    if integration.history_id is None:
        count, new_history_id = await _full_sync(session)
        mode = "full"
    else:
        try:
            count, new_history_id = await _incremental_sync(session, integration)
            mode = "incremental"
        except HistoryExpiredError:
            count, new_history_id = await _full_sync(session)
            mode = "full"

    integration.history_id = new_history_id
    integration.last_synced_at = datetime.now(tz=timezone.utc)
    await session.commit()

    return {"mode": mode, "synced": count, "history_id": new_history_id}
