from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from signal_hub_shared.integrations import (
    ConnectorType,
    IntegrationConfig,
    IntegrationStatus,
    RiskLevel,
)
from app.db.models.integration import IntegrationModel
from app.db.session import get_session

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/", response_model=list[IntegrationConfig])
async def list_integrations(
    session: AsyncSession = Depends(get_session),
) -> list[IntegrationConfig]:
    """Return all integrations from the database, ordered by insertion order."""
    result = await session.execute(
        select(IntegrationModel).order_by(IntegrationModel.id)
    )
    rows = result.scalars().all()
    return [
        IntegrationConfig(
            integration_key=row.integration_key,
            display_name=row.display_name,
            status=IntegrationStatus(row.status),
            connector_type=ConnectorType(row.connector_type),
            risk_level=RiskLevel(row.risk_level),
            official_api_available=row.official_api_available,
            notes=row.notes,
        )
        for row in rows
    ]
