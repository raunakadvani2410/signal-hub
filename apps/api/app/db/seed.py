"""
Seed the integrations table from the in-code INTEGRATION_REGISTRY.

Called on app startup via the lifespan event in main.py. Safe to run repeatedly —
it upserts, so re-running after a code change updates notes/status in the DB to
match the registry.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from signal_hub_shared.integrations import INTEGRATION_REGISTRY
from app.db.models.integration import IntegrationModel


async def seed_integrations(session: AsyncSession) -> None:
    for config in INTEGRATION_REGISTRY:
        result = await session.execute(
            select(IntegrationModel).where(
                IntegrationModel.integration_key == config.integration_key
            )
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            session.add(
                IntegrationModel(
                    integration_key=config.integration_key,
                    display_name=config.display_name,
                    status=config.status.value,
                    connector_type=config.connector_type.value,
                    risk_level=config.risk_level.value,
                    official_api_available=config.official_api_available,
                    notes=config.notes,
                )
            )
        else:
            # Keep DB in sync if the registry values change in code.
            existing.display_name = config.display_name
            existing.status = config.status.value
            existing.connector_type = config.connector_type.value
            existing.risk_level = config.risk_level.value
            existing.official_api_available = config.official_api_available
            existing.notes = config.notes

    await session.commit()
