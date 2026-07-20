import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

import uuid
from app.models.models import Organization, User, Membership, RoleEnum

@pytest.fixture
async def webhook_setup_data(db: AsyncSession):
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    
    org = Organization(id=org_id, name="Webhook Org")
    db.add(org)
    
    user = User(id=user_id, email=f"webhook_{user_id.hex}@test.com")
    db.add(user)
    
    await db.flush()
    
    db.add(Membership(user_id=user_id, org_id=org_id, role=RoleEnum.owner))
    await db.commit()
    
    return {
        "org_id": str(org_id),
        "user_id": str(user_id)
    }

@pytest.mark.asyncio
async def test_webhook_crud(client: AsyncClient, db: AsyncSession, webhook_setup_data):
    from app.services.auth_service import create_access_token
    
    org_id = webhook_setup_data["org_id"]
    user_id = webhook_setup_data["user_id"]
    
    user_token = create_access_token(uuid.UUID(user_id))
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
async def test_ssrf_protection(client: AsyncClient, webhook_setup_data):
    from app.services.auth_service import create_access_token

    org_id = webhook_setup_data["org_id"]
    user_id = webhook_setup_data["user_id"]
    
    user_token = create_access_token(uuid.UUID(user_id))
    user_headers = {"Authorization": f"Bearer {user_token}"}

    create_res = await client.post(
        f"/v1/organizations/{org_id}/webhooks",
        json={"url": "http://127.0.0.1/admin", "events": ["*"]},
        headers=user_headers
    )
    assert create_res.status_code == 400
    assert "Invalid webhook URL" in create_res.text
