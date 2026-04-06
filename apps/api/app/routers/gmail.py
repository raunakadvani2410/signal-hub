from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.db.models.integration import IntegrationModel
from app.db.session import get_session
from app.schemas.gmail import GmailProfileResponse
from app.services.gmail import (
    build_auth_url,
    exchange_code,
    fetch_profile,
    load_tokens,
    sync_gmail,
)

router = APIRouter(prefix="/gmail", tags=["gmail"])


@router.get("/auth")
async def gmail_auth():
    """
    Redirect the user's browser to Google's OAuth consent screen.

    Open this URL directly in a browser — it initiates the full OAuth redirect chain.
    Returns 503 if GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET are not set in .env.
    """
    if not settings.gmail_client_id or not settings.gmail_client_secret:
        raise HTTPException(
            status_code=503,
            detail=(
                "Gmail credentials are not configured. "
                "Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in apps/api/.env. "
                "See docs/google-oauth-setup.md for instructions."
            ),
        )
    auth_url = await run_in_threadpool(build_auth_url)
    return RedirectResponse(auth_url)


@router.get("/callback")
async def gmail_callback(code: str = "", state: str = ""):
    """
    Google redirects here after the user grants permissions.
    Exchanges the authorization code for tokens and confirms the connection.

    This endpoint is called by Google's redirect — do not call it directly.
    """
    if not code:
        raise HTTPException(status_code=400, detail="Missing OAuth code parameter.")

    try:
        await run_in_threadpool(exchange_code, code, state)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Token exchange failed: {exc}")

    try:
        profile = await fetch_profile()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gmail API error after auth: {exc}")

    return {
        "status": "connected",
        "email": profile.get("emailAddress"),
        "messages_total": profile.get("messagesTotal"),
        "threads_total": profile.get("threadsTotal"),
    }


@router.get("/profile", response_model=GmailProfileResponse)
async def gmail_profile():
    """
    Return the connected Gmail account's profile.
    Returns 401 if OAuth has not been completed yet.
    Returns 502 if the Gmail API call fails.
    """
    if load_tokens() is None:
        raise HTTPException(
            status_code=401,
            detail="Gmail not connected. Complete OAuth at /api/gmail/auth.",
        )

    try:
        profile = await fetch_profile()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gmail API error: {exc}")

    return GmailProfileResponse(
        email=profile.get("emailAddress", ""),
        messages_total=profile.get("messagesTotal", 0),
        threads_total=profile.get("threadsTotal", 0),
    )


@router.post("/sync")
async def gmail_sync(session: AsyncSession = Depends(get_session)):
    """
    Synchronize Gmail inbox into the DB.

    First run: full fetch of recent messages.
    Subsequent runs: incremental via Gmail History API (only new messages).
    Automatic fallback to full fetch if the stored historyId has expired.

    Returns 401 if OAuth has not been completed yet.
    Returns {"mode", "synced", "history_id"}.
    """
    if load_tokens() is None:
        raise HTTPException(
            status_code=401,
            detail="Gmail not connected. Complete OAuth at /api/gmail/auth.",
        )
    try:
        result = await sync_gmail(session)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gmail sync failed: {exc}")
    return result


@router.get("/status")
async def gmail_status(session: AsyncSession = Depends(get_session)):
    """
    Return Gmail connection and sync state.

    connected         — true only when a refresh_token is present on disk.
                        A token file without a refresh_token cannot self-heal
                        after the access token expires; re-auth is required.
    has_refresh_token — explicit flag; use this to prompt re-auth in the UI.
    last_synced_at    — ISO timestamp of the last successful sync, or null.
    history_id        — incremental sync cursor, or null (= never synced).
    """
    from sqlalchemy import select as sa_select

    result = await session.execute(
        sa_select(IntegrationModel).where(IntegrationModel.integration_key == "gmail")
    )
    integration = result.scalar_one()

    tokens = load_tokens()
    has_refresh_token = bool(tokens and tokens.get("refresh_token"))

    return {
        "connected": has_refresh_token,
        "has_refresh_token": has_refresh_token,
        "last_synced_at": integration.last_synced_at,
        "history_id": integration.history_id,
    }
