from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.schemas.gmail import GmailProfileResponse
from app.services.gmail import (
    build_auth_url,
    exchange_code,
    fetch_profile,
    load_tokens,
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
