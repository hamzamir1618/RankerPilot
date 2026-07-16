import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import Audit, Page, Finding, Project, User, Organization, Membership

@pytest.fixture
async def diff_data(db: AsyncSession):
    # Setup base data
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    proj_id = uuid.uuid4()
    
    db.add(User(id=user_id, email=f"diff_{user_id.hex}@test.com"))
    db.add(Organization(id=org_id, name="Diff Org"))
    await db.flush()
    db.add(Membership(user_id=user_id, org_id=org_id, role="owner"))
    db.add(Project(id=proj_id, org_id=org_id, domain="diff.com", name="Diff Proj"))
    await db.flush()
    
    # Older audit
    old_audit_id = uuid.uuid4()
    old_audit = Audit(
        id=old_audit_id, project_id=proj_id, status="done", mode="full",
        page_limit=10, root_url="https://diff.com", created_by=user_id, score=60.0
    )
    db.add(old_audit)
    
    # Newer audit
    new_audit_id = uuid.uuid4()
    new_audit = Audit(
        id=new_audit_id, project_id=proj_id, status="done", mode="full",
        page_limit=10, root_url="https://diff.com", created_by=user_id, score=85.5
    )
    db.add(new_audit)
    await db.flush()
    
    # Pages
    old_page = Page(id=uuid.uuid4(), audit_id=old_audit_id, url="https://diff.com/about", status_code=200, rendered=False)
    new_page = Page(id=uuid.uuid4(), audit_id=new_audit_id, url="https://diff.com/about", status_code=200, rendered=False)
    db.add_all([old_page, new_page])
    await db.flush()
    
    # Findings
    # 1. Resolved (fail in old, pass in new)
    f_resolved_old = Finding(
        id=uuid.uuid4(), audit_id=old_audit_id, page_id=old_page.id,
        agent="test", check_id="missing_h1", status="fail", severity="high", category="onpage", title="Missing H1"
    )
    f_resolved_new = Finding(
        id=uuid.uuid4(), audit_id=new_audit_id, page_id=new_page.id,
        agent="test", check_id="missing_h1", status="pass", category="onpage", title="Missing H1"
    )
    
    # 2. Unchanged (fail in both)
    f_unchanged_old = Finding(
        id=uuid.uuid4(), audit_id=old_audit_id, page_id=old_page.id,
        agent="test", check_id="slow_lcp", status="fail", severity="medium", category="performance", title="Slow LCP"
    )
    f_unchanged_new = Finding(
        id=uuid.uuid4(), audit_id=new_audit_id, page_id=new_page.id,
        agent="test", check_id="slow_lcp", status="fail", severity="medium", category="performance", title="Slow LCP"
    )
    
    # 3. New (pass/missing in old, fail in new)
    f_new_new = Finding(
        id=uuid.uuid4(), audit_id=new_audit_id, page_id=new_page.id,
        agent="test", check_id="broken_link", status="fail", severity="high", category="technical", title="Broken Link"
    )
    
    db.add_all([f_resolved_old, f_resolved_new, f_unchanged_old, f_unchanged_new, f_new_new])
    await db.flush()
    await db.commit()
    
    return {
        "user_id": user_id,
        "old_audit_id": str(old_audit_id),
        "new_audit_id": str(new_audit_id)
    }

@pytest.mark.asyncio
async def test_audit_diff_endpoint(client: AsyncClient, diff_data, db):
    # Authenticate
    email = f"diff_{diff_data['user_id'].hex}@test.com"
    await client.post("/v1/auth/register", json={
        "email": f"new_{email}", # need a new one since diff_data inserts directly without hash
        "password": "strongpassword123"
    })
    
    # Actually just use login since we bypassed the password hash in setup? No, better to register a fresh one and link it.
    # The fixture inserts `diff_...` user but without valid password hash. Let's just mock the current user or rely on the fact that endpoint requires auth.
    # Wait, the endpoint uses Depends(get_current_user). We must have a valid token.
    token_res = await client.post("/v1/auth/register", json={"email": "diff_test_auth@example.com", "password": "pass"})
    token = token_res.json()["access_token"]
    
    res = await client.get(
        f"/v1/audits/{diff_data['new_audit_id']}/diff/{diff_data['old_audit_id']}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert res.status_code == 200
    data = res.json()
    
    # 85.5 - 60.0 = 25.5
    assert data["score_delta"] == 25.5
    
    # 1 resolved finding (missing_h1)
    assert len(data["resolved"]) == 1
    assert data["resolved"][0]["check_id"] == "missing_h1"
    
    # 1 new finding (broken_link)
    assert len(data["new"]) == 1
    assert data["new"][0]["check_id"] == "broken_link"
    
    # 1 unchanged finding (slow_lcp)
    assert len(data["unchanged"]) == 1
    assert data["unchanged"][0]["check_id"] == "slow_lcp"
