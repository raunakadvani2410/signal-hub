from httpx import AsyncClient


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_list_integrations_returns_all_six(client: AsyncClient) -> None:
    response = await client.get("/api/integrations/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 6
    keys = {item["integration_key"] for item in data}
    assert keys == {"gmail", "google_calendar", "notion", "whatsapp", "linkedin", "imessage"}


async def test_list_integrations_shape(client: AsyncClient) -> None:
    response = await client.get("/api/integrations/")
    item = response.json()[0]
    assert "integration_key" in item
    assert "display_name" in item
    assert "status" in item
    assert "connector_type" in item
    assert "risk_level" in item
    assert "official_api_available" in item
    assert "notes" in item


async def test_list_integrations_known_statuses(client: AsyncClient) -> None:
    response = await client.get("/api/integrations/")
    statuses = {item["status"] for item in response.json()}
    valid = {"official", "official_constrained", "third_party_experimental", "local_only_experimental"}
    assert statuses <= valid
