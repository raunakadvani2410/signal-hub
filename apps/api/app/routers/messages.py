from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from signal_hub_shared.models import ItemSource, Message
from app.db.models.message import MessageModel
from app.db.session import get_session

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("/", response_model=list[Message])
async def list_messages(
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[Message]:
    """Return stored messages, newest first."""
    result = await session.execute(
        select(MessageModel).order_by(MessageModel.received_at.desc()).limit(limit)
    )
    rows = result.scalars().all()
    return [
        Message(
            external_id=row.external_id,
            source=ItemSource(row.source),
            sender=row.sender,
            subject=row.subject,
            body_preview=row.body_preview,
            is_read=row.is_read,
            received_at=row.received_at,
            thread_id=row.thread_id,
            raw_json=row.raw_json,
        )
        for row in rows
    ]
