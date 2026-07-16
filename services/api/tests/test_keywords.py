import pytest
import uuid
from httpx import AsyncClient
from app.scoring.opportunity import compute_opportunity_score

def test_opportunity_score_formula():
    # High volume, low diff, quick win position (8-20)
    score1 = compute_opportunity_score(volume=8000, difficulty=20.0, position=12)
    # Vol score = 80, Diff = 80, Pos = 100
    # (80 * 0.4) + (80 * 0.3) + (100 * 0.3) = 32 + 24 + 30 = 86.0
    assert score1 == 86.0
    
    # Very high volume (capped at 10k), high diff, bad position
    score2 = compute_opportunity_score(volume=50000, difficulty=90.0, position=80)
    # Vol score = 100, Diff = 10, Pos = 30
    # (100 * 0.4) + (10 * 0.3) + (30 * 0.3) = 40 + 3 + 9 = 52.0
    assert score2 == 52.0

@pytest.mark.asyncio
async def test_gap_analysis_validation(client: AsyncClient, db):
    # Register/login to get token
    email = f"gap_{uuid.uuid4().hex}@test.com"
    res = await client.post("/v1/auth/register", json={"email": email, "password": "pass"})
    token = res.json()["access_token"]
    
    # We need a project ID to run this. We can just mock a UUID, it will 404 before 422 if project is checked first,
    # BUT Pydantic validation (422) happens before the route handler logic.
    proj_id = uuid.uuid4()
    
    # Valid input (1-3 competitors)
    res_valid = await client.post(
        f"/v1/projects/{proj_id}/keywords/gap",
        json={"competitors": ["comp1.com", "comp2.com"]},
        headers={"Authorization": f"Bearer {token}"}
    )
    # Will be 404 because project doesn't exist, but it passed validation!
    assert res_valid.status_code == 404
    
    # Invalid input (>3 competitors)
    res_invalid = await client.post(
        f"/v1/projects/{proj_id}/keywords/gap",
        json={"competitors": ["comp1.com", "comp2.com", "comp3.com", "comp4.com"]},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_invalid.status_code == 422
    assert "competitors" in res_invalid.text.lower()
