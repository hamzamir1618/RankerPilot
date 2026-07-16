import pytest
import uuid
import respx
from httpx import Response
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import User, Organization, Project, Membership, OAuthToken, OAuthProviderEnum, RoleEnum
from app.integrations.gsc import get_quick_wins, refresh_gsc_token, get_fernet

@pytest.fixture
async def gsc_setup_data(db: AsyncSession):
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    proj_id = uuid.uuid4()
    
    db.add(User(id=user_id, email=f"gsc_{user_id.hex}@test.com"))
    db.add(Organization(id=org_id, name="GSC Org"))
    await db.flush()
    db.add(Membership(user_id=user_id, org_id=org_id, role=RoleEnum.owner))
    
    project = Project(id=proj_id, org_id=org_id, domain="gsc.com", name="GSC Proj", gsc_connected=True)
    db.add(project)
    
    fernet = get_fernet()
    enc_refresh = fernet.encrypt(b"valid_refresh_token")
    
    token = OAuthToken(
        id=uuid.uuid4(),
        user_id=user_id,
        provider=OAuthProviderEnum.gsc,
        encrypted_refresh_token=enc_refresh,
        scopes=["https://www.googleapis.com/auth/webmasters.readonly"]
    )
    db.add(token)
    await db.flush()
    await db.commit()
    
    return {"project_id": str(proj_id), "token_id": str(token.id)}

@pytest.mark.asyncio
@respx.mock
async def test_gsc_token_refresh_happy(db: AsyncSession, gsc_setup_data):
    respx.post("https://oauth2.googleapis.com/token").mock(
        return_value=Response(200, json={"access_token": "new_access_token", "expires_in": 3600})
    )
    
    project = await db.get(Project, gsc_setup_data["project_id"])
    token = await db.get(OAuthToken, gsc_setup_data["token_id"])
    
    access_token = await refresh_gsc_token(db, token, project)
    assert access_token == "new_access_token"
    assert project.gsc_connected is True

@pytest.mark.asyncio
@respx.mock
async def test_gsc_token_refresh_revoked(db: AsyncSession, gsc_setup_data):
    respx.post("https://oauth2.googleapis.com/token").mock(
        return_value=Response(400, json={"error": "invalid_grant", "error_description": "Token has been expired or revoked."})
    )
    
    project = await db.get(Project, gsc_setup_data["project_id"])
    token = await db.get(OAuthToken, gsc_setup_data["token_id"])
    
    access_token = await refresh_gsc_token(db, token, project)
    
    # Should silently return None and disconnect the project
    assert access_token is None
    assert project.gsc_connected is False

@pytest.mark.asyncio
@respx.mock
async def test_get_quick_wins_boundaries(db: AsyncSession, gsc_setup_data):
    # Mock token refresh
    respx.post("https://oauth2.googleapis.com/token").mock(
        return_value=Response(200, json={"access_token": "valid_token"})
    )
    
    # Mock Search Analytics endpoint
    respx.post("https://searchconsole.googleapis.com/webmasters/v3/sites/sc-domain:gsc.com/searchAnalytics/query").mock(
        return_value=Response(200, json={
            "rows": [
                {"keys": ["query1"], "position": 7.9, "impressions": 100}, # Out (too high)
                {"keys": ["query2"], "position": 8.0, "impressions": 100}, # In (boundary)
                {"keys": ["query3"], "position": 15.0, "impressions": 50}, # Out (low impressions)
                {"keys": ["query4"], "position": 20.9, "impressions": 500}, # In (boundary)
                {"keys": ["query5"], "position": 21.0, "impressions": 500}, # Out (too low)
            ]
        })
    )
    
    wins = await get_quick_wins(db, gsc_setup_data["project_id"])
    
    assert len(wins) == 2
    assert wins[0]["keys"][0] == "query4" # Because sorted by impressions desc
    assert wins[1]["keys"][0] == "query2"
