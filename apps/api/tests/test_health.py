import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_list_integrations() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/integrations/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 6
    keys = {item["integration_key"] for item in data}
    assert keys == {"gmail", "google_calendar", "notion", "whatsapp", "linkedin", "imessage"}
