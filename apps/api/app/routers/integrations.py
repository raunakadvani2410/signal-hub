from fastapi import APIRouter

from signal_hub_shared.integrations import INTEGRATION_REGISTRY, IntegrationConfig

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/", response_model=list[IntegrationConfig])
async def list_integrations() -> list[IntegrationConfig]:
    """Return the full integration registry with status and metadata."""
    return INTEGRATION_REGISTRY
