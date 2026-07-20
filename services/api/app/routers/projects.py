import uuid
import urllib.parse
import httpx
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.deps import get_db, get_current_org, get_current_user
from app.services import project_service
from app.schemas.schemas import ProjectCreate, ProjectResponse
from app.models.models import Organization, OAuthToken, OAuthProviderEnum
from app.core.crypto import encrypt_token
from app.core.config import settings
from app.core.rate_limit import limit_project

router = APIRouter(prefix="/v1/projects", tags=["Projects"], dependencies=[Depends(limit_project)])

@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db)
):
    # Org isolation handles filtering implicitly
    return await project_service.get_projects(db)

@router.post("/", response_model=ProjectResponse)
async def create_project(
    data: ProjectCreate,
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db)
):
    return await project_service.create_project(db, org.id, data)

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db)
):
    return await project_service.get_project(db, project_id)

@router.delete("/{project_id}")
async def delete_project(
    project_id: uuid.UUID,
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db)
):
    return await project_service.delete_project(db, project_id)


# GSC Connect Routes

class GscConnectResponse(BaseModel):
    url: str

class GscCallbackRequest(BaseModel):
    code: str
    state: str
    redirect_uri: str

@router.post("/{project_id}/gsc/connect", response_model=GscConnectResponse)
async def connect_gsc(
    project_id: uuid.UUID,
    org: Organization = Depends(get_current_org),
    user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify project exists
    await project_service.get_project(db, project_id)
    
    # State binds project and user to prevent CSRF
    state = f"{project_id}_{user.id}"
    
    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": "http://localhost:3000/auth/gsc/callback", # Usually a config param
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/webmasters.readonly",
        "access_type": "offline",
        "prompt": "consent",
        "state": state
    }
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    return {"url": url}

@router.post("/gsc/callback")
async def gsc_callback(
    data: GscCallbackRequest,
    user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        project_id_str, user_id_str = data.state.split("_")
        if user_id_str != str(user.id):
            raise HTTPException(status_code=403, detail="State user mismatch")
        project_id = uuid.UUID(project_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid state format")
        
    # verify project
    project = await project_service.get_project(db, project_id)
    
    # Exchange code
    async with httpx.AsyncClient() as client:
        resp = await client.post("https://oauth2.googleapis.com/token", data={
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET.get_secret_value(),
            "code": data.code,
            "redirect_uri": data.redirect_uri,
            "grant_type": "authorization_code"
        })
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange code")
            
        token_data = resp.json()
        refresh_token = token_data.get("refresh_token")
        
        if not refresh_token:
            # Maybe already granted previously, prompt=consent should force it, but if not:
            raise HTTPException(status_code=400, detail="No refresh token returned by Google")
            
    # Store token
    enc_token = encrypt_token(refresh_token)
    oauth_token = OAuthToken(
        id=uuid.uuid4(),
        user_id=user.id,
        provider=OAuthProviderEnum.gsc,
        encrypted_refresh_token=enc_token,
        scopes=["https://www.googleapis.com/auth/webmasters.readonly"]
    )
    db.add(oauth_token)
    
    # Update project
    project.gsc_connected = True
    
    await db.commit()
    return {"status": "connected"}

# GA4 Connect Routes

@router.post("/{project_id}/ga4/connect")
async def connect_ga4(
    project_id: uuid.UUID,
    org: Organization = Depends(get_current_org),
    user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await project_service.get_project(db, project_id)
    state = f"{project_id}_{user.id}"
    
    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": "http://localhost:3000/auth/ga4/callback",
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/analytics.readonly",
        "access_type": "offline",
        "prompt": "consent",
        "state": state
    }
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    return {"url": url}

@router.post("/ga4/callback")
async def ga4_callback(
    data: GscCallbackRequest, # Reusing model
    user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        project_id_str, user_id_str = data.state.split("_")
        if user_id_str != str(user.id):
            raise HTTPException(status_code=403, detail="State user mismatch")
        project_id = uuid.UUID(project_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid state format")
        
    await project_service.get_project(db, project_id)
    
    async with httpx.AsyncClient() as client:
        resp = await client.post("https://oauth2.googleapis.com/token", data={
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET.get_secret_value(),
            "code": data.code,
            "redirect_uri": data.redirect_uri,
            "grant_type": "authorization_code"
        })
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange code")
            
        token_data = resp.json()
        refresh_token = token_data.get("refresh_token")
        if not refresh_token:
            raise HTTPException(status_code=400, detail="No refresh token returned by Google")
            
    enc_token = encrypt_token(refresh_token)
    oauth_token = OAuthToken(
        id=uuid.uuid4(),
        user_id=user.id,
        provider=OAuthProviderEnum.ga4,
        encrypted_refresh_token=enc_token,
        scopes=["https://www.googleapis.com/auth/analytics.readonly"]
    )
    db.add(oauth_token)
    await db.commit()
    return {"status": "connected"}

# GBP Connect Routes

@router.post("/{project_id}/gbp/connect")
async def connect_gbp(
    project_id: uuid.UUID,
    org: Organization = Depends(get_current_org),
    user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await project_service.get_project(db, project_id)
    state = f"{project_id}_{user.id}"
    
    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": "http://localhost:3000/auth/gbp/callback",
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/business.manage",
        "access_type": "offline",
        "prompt": "consent",
        "state": state
    }
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    return {"url": url}

@router.post("/gbp/callback")
async def gbp_callback(
    data: GscCallbackRequest,
    user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        project_id_str, user_id_str = data.state.split("_")
        if user_id_str != str(user.id):
            raise HTTPException(status_code=403, detail="State user mismatch")
        project_id = uuid.UUID(project_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid state format")
        
    await project_service.get_project(db, project_id)
    
    async with httpx.AsyncClient() as client:
        resp = await client.post("https://oauth2.googleapis.com/token", data={
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET.get_secret_value(),
            "code": data.code,
            "redirect_uri": data.redirect_uri,
            "grant_type": "authorization_code"
        })
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange code")
            
        token_data = resp.json()
        refresh_token = token_data.get("refresh_token")
        if not refresh_token:
            raise HTTPException(status_code=400, detail="No refresh token returned by Google")
            
    enc_token = encrypt_token(refresh_token)
    oauth_token = OAuthToken(
        id=uuid.uuid4(),
        user_id=user.id,
        provider=OAuthProviderEnum.gbp,
        encrypted_refresh_token=enc_token,
        scopes=["https://www.googleapis.com/auth/business.manage"]
    )
    db.add(oauth_token)
    await db.commit()
    return {"status": "connected"}
