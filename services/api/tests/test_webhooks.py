import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.mark.asyncio
async def test_webhook_crud(client: AsyncClient, db: AsyncSession, admin_token_headers: dict):
    org_res = await client.post("/v1/admin/organizations", json={"name": "Webhook Org"}, headers=admin_token_headers)
    org_id = org_res.json()["id"]

    user_res = await client.post(
        "/v1/auth/register",
        json={"email": "webhook@example.com", "password": "TestPassword123!", "org_id": org_id}
    )
    user_token = user_res.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {user_token}"}

    create_res = await client.post(
        f"/v1/organizations/{org_id}/webhooks",
        json={"url": "https://example.com/hook", "events": ["audit.completed"]},
        headers=user_headers
    )
    assert create_res.status_code == 200
    webhook_id = create_res.json()["id"]
    assert create_res.json()["url"] == "https://example.com/hook/"

    list_res = await client.get(f"/v1/organizations/{org_id}/webhooks", headers=user_headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    del_res = await client.delete(f"/v1/organizations/{org_id}/webhooks/{webhook_id}", headers=user_headers)
    assert del_res.status_code == 204

    list_res2 = await client.get(f"/v1/organizations/{org_id}/webhooks", headers=user_headers)
    assert len(list_res2.json()) == 0

@pytest.mark.asyncio
async def test_ssrf_protection(client: AsyncClient, admin_token_headers: dict):
    org_res = await client.post("/v1/admin/organizations", json={"name": "SSRF Org"}, headers=admin_token_headers)
    org_id = org_res.json()["id"]

    user_res = await client.post(
        "/v1/auth/register",
        json={"email": "ssrf@example.com", "password": "TestPassword123!", "org_id": org_id}
    )
    user_token = user_res.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {user_token}"}

    create_res = await client.post(
        f"/v1/organizations/{org_id}/webhooks",
        json={"url": "http://127.0.0.1/admin", "events": ["*"]},
        headers=user_headers
    )
    assert create_res.status_code == 400
    assert "Invalid webhook URL" in create_res.text
