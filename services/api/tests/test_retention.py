import pytest
import uuid
import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient

from app.workers.beat_schedule import get_jitter_hour
from app.services.drift import check_drift
from app.models.models import SharedReportToken, Audit, AuditStatusEnum, AuditModeEnum, Organization, Project
from app.core.db_partitions import create_future_partitions

def test_beat_jitter_distribution():
    """
    Test that the jitter hour logic evenly distributes across the 168 hours of the week.
    """
    counts = {i: 0 for i in range(168)}
    
    # Generate 10,000 project IDs
    for _ in range(10000):
        pid = uuid.uuid4()
        hour = get_jitter_hour(pid, "weekly")
        counts[hour] += 1
        
    # Verify even distribution (mean ~59, standard deviation shouldn't be crazy)
    # Just basic bounds check
    for h, count in counts.items():
        assert count > 10, f"Hour {h} had very low distribution: {count}"

def test_drift_rules_concrete():
    """
    Test some concrete drift rules (like Title changed, Word count dropped, etc.)
    """
    baseline = {
        "title": "Old Title",
        "word_count": 1000,
        "status_code": 200,
        "internal_pagerank": 0.5
    }
    
    current = {
        "title": "New Title",
        "word_count": 500, # 50% drop
        "status_code": 404,
        "internal_pagerank": 0.1 # Drop
    }
    
    pid = uuid.uuid4()
    events = check_drift(baseline, current, pid, "https://test.com")
    
    rules = [e.rule for e in events]
    assert "1. Title Changed" in rules
    assert "9. Word Count Dropped (>20%)" in rules
    assert "8. Status Code Changed (non-200)" in rules
    assert "17. Internal Pagerank Dropped" in rules

@pytest.mark.asyncio
async def test_shared_token(client: AsyncClient, db: AsyncSession):
    # Setup some dummy data without going through endpoints to save fixture complexity
    # Assumes db is transactional fixture
    org_id = uuid.uuid4()
    org = Organization(id=org_id, name="Shared Org")
    db.add(org)
    
    proj_id = uuid.uuid4()
    proj = Project(id=proj_id, org_id=org_id, domain="shared.com", name="Shared Proj")
    db.add(proj)
    await db.flush()
    
    audit_id = uuid.uuid4()
    audit = Audit(
        id=audit_id,
        project_id=proj_id,
        status=AuditStatusEnum.done,
        mode=AuditModeEnum.full,
        page_limit=1,
        root_url="https://shared.com",
        created_by=None,
        score=100.0,
        category_scores={}
    )
    db.add(audit)
    
    token = SharedReportToken(
        token=uuid.uuid4(),
        audit_id=audit_id,
        expires_at=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) + datetime.timedelta(days=1),
        revoked=False
    )
    db.add(token)
    await db.commit()
    
    # Test GET
    res = await client.get(f"/v1/shared/{str(token.token)}")
    assert res.status_code == 200
    data = res.json()
    assert data["target_url"] == "https://shared.com"
    
    # Test Revoke directly (no auth needed for this simple test DB mutation)
    token.revoked = True
    await db.commit()
    
    res2 = await client.get(f"/v1/shared/{str(token.token)}")
    assert res2.status_code == 403
    assert res2.json()["detail"] == "Token revoked"

@pytest.mark.asyncio
async def test_partition_helper_compiles(db: AsyncSession):
    """
    Since we can't reliably test partition creation in sqlite (or without raw PSQL perms sometimes),
    we just ensure the helper runs or we skip it if not PSQL.
    If the DB is Postgres, this should create partitions for rank_snapshots safely if they don't exist.
    """
    try:
        await create_future_partitions(db, "rank_snapshots", 1)
    except Exception as e:
        # If it fails due to SQLite syntax (like 'SELECT to_regclass'), we gracefully ignore in local testing
        if "to_regclass" in str(e):
            pytest.skip("Skipping postgres-specific partition test in non-postgres env")
        else:
            raise e
