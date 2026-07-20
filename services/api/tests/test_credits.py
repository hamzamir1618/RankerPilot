import pytest
import uuid
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import User, Organization, Project, Membership, RoleEnum, Audit, AuditStatusEnum
from app.services.credits import credit, get_balance
from app.workers.pipelines import async_crawl_site

@pytest.fixture
async def credits_setup_data(db: AsyncSession):
    owner_id = uuid.uuid4()
    member_id = uuid.uuid4()
    org_id = uuid.uuid4()
    proj_id = uuid.uuid4()
    
    owner = User(id=owner_id, email=f"owner_{owner_id.hex}@test.com")
    member = User(id=member_id, email=f"member_{member_id.hex}@test.com")
    db.add_all([owner, member])
    
    org = Organization(id=org_id, name="Credits Org")
    db.add(org)
    await db.flush()
    
    db.add(Membership(user_id=owner_id, org_id=org_id, role=RoleEnum.owner))
    db.add(Membership(user_id=member_id, org_id=org_id, role=RoleEnum.member))
    
    project = Project(id=proj_id, org_id=org_id, domain="credits.com", name="Credits Proj")
    db.add(project)
    
    await db.commit()
    
    return {
        "owner_id": str(owner_id),
        "member_id": str(member_id),
        "org_id": str(org_id),
        "proj_id": str(proj_id)
    }

@pytest.mark.asyncio
async def test_credit_concurrency_locking(client: AsyncClient, db: AsyncSession, credits_setup_data):
    """
    Test that concurrent requests to create an audit are serialized and only one succeeds
    when the balance is exactly enough for one.
    """
    org_id = uuid.UUID(credits_setup_data["org_id"])
    proj_id = credits_setup_data["proj_id"]
    owner_id = credits_setup_data["owner_id"]
    
    # Pre-fund with exactly 50 credits
    credit(db, org_id, 50, "Initial test fund", ref_type="test")
    await db.commit()
    
    # We need an authenticated client for the owner
    client.headers = {"Authorization": f"Bearer mock_token_for_{owner_id}"}
    
    # Send 3 concurrent requests
    async def create_audit_req():
        return await client.post(f"/v1/projects/{proj_id}/audits", json={
            "mode": "full", # Costs 50
            "url": "https://credits.com",
            "page_limit": 1
        })
        
    responses = await asyncio.gather(
        create_audit_req(),
        create_audit_req(),
        create_audit_req()
    )
    
    status_codes = [r.status_code for r in responses]
    assert status_codes.count(202) == 1
    assert status_codes.count(402) == 2
    
    # Verify balance is 0
    balance = await get_balance(db, org_id)
    assert balance == 0

@pytest.mark.asyncio
async def test_402_shape(client: AsyncClient, db: AsyncSession, credits_setup_data):
    proj_id = credits_setup_data["proj_id"]
    owner_id = credits_setup_data["owner_id"]
    client.headers = {"Authorization": f"Bearer mock_token_for_{owner_id}"}
    
    # Balance is 0
    res = await client.post(f"/v1/projects/{proj_id}/audits", json={
        "mode": "full",
        "url": "https://credits.com",
        "page_limit": 1
    })
    
    assert res.status_code == 402
    data = res.json()["detail"]
    assert "current_balance" in data
    assert "required" in data
    assert "shortfall" in data
    assert data["current_balance"] == 0
    assert data["required"] == 50
    assert data["shortfall"] == 50

@pytest.mark.asyncio
async def test_refund_path(client: AsyncClient, db: AsyncSession, credits_setup_data, monkeypatch):
    """
    If a crawl fails to retrieve any pages, the worker should mark it failed and issue a refund.
    """
    org_id = uuid.UUID(credits_setup_data["org_id"])
    proj_id = credits_setup_data["proj_id"]
    owner_id = credits_setup_data["owner_id"]
    
    # Fund with 100 credits
    credit(db, org_id, 100, "Fund for refund test")
    await db.commit()
    
    client.headers = {"Authorization": f"Bearer mock_token_for_{owner_id}"}
    
    # Create audit (debits 50)
    res = await client.post(f"/v1/projects/{proj_id}/audits", json={
        "mode": "full",
        "url": "https://invalid-domain-that-will-fail-dns.local",
        "page_limit": 1
    })
    assert res.status_code == 202
    audit_id_str = res.json()["audit_id"]
    
    # Balance should be 50 now
    assert await get_balance(db, org_id) == 50
    
    # Force the fetch_page to always raise TimeoutError to simulate immediate failure
    async def mock_fetch_page(*args, **kwargs):
        raise asyncio.TimeoutError("Simulated DNS failure")
        
    monkeypatch.setattr("app.workers.pipelines.fetch_page", mock_fetch_page)
    
    # Run the worker synchronously
    try:
        await async_crawl_site(audit_id_str, "https://invalid-domain-that-will-fail-dns.local")
    except RuntimeError:
        pass # Expected since 0 pages crawled
        
    # Balance should be back to 100
    assert await get_balance(db, org_id) == 100
    
    # Audit should be failed
    audit = await db.get(Audit, uuid.UUID(audit_id_str))
    assert audit is not None
    assert audit.status == AuditStatusEnum.failed

@pytest.mark.asyncio
async def test_admin_top_up_permissions(client: AsyncClient, db: AsyncSession, credits_setup_data):
    org_id = credits_setup_data["org_id"]
    owner_id = credits_setup_data["owner_id"]
    member_id = credits_setup_data["member_id"]
    
    # Member tries to top up
    client.headers = {"Authorization": f"Bearer mock_token_for_{member_id}"}
    res = await client.post(f"/v1/organizations/{org_id}/credits/top-up", json={
        "amount": 500,
        "reason": "Top up"
    })
    assert res.status_code == 403
    
    # Owner tries to top up
    client.headers = {"Authorization": f"Bearer mock_token_for_{owner_id}"}
    res = await client.post(f"/v1/organizations/{org_id}/credits/top-up", json={
        "amount": 500,
        "reason": "Top up"
    })
    assert res.status_code == 200
    assert res.json()["new_balance"] == 500
