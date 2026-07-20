import re
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, field_validator

from app.core.deps import get_db, get_current_org
from app.models.models import Organization
from app.core.rate_limit import limit_org

router = APIRouter(prefix="/v1/organizations", tags=["Organizations"], dependencies=[Depends(limit_org)])

class ThemeUpdateRequest(BaseModel):
    theme_primary_color: str | None = None
    theme_accent_color: str | None = None
    theme_agency_name: str | None = None

    @field_validator('theme_primary_color', 'theme_accent_color')
    def validate_hex_color(cls, v):
        if v is not None and not re.match(r'^#(?:[0-9a-fA-F]{3}){1,2}$', v):
            raise ValueError('Must be a valid hex color code (e.g., #FFFFFF)')
        return v

class ThemeResponse(BaseModel):
    theme_logo_url: str | None
    theme_primary_color: str | None
    theme_accent_color: str | None
    theme_agency_name: str | None

@router.put("/{org_id}/theme", response_model=ThemeResponse)
async def update_theme(
    org_id: uuid.UUID,
    data: ThemeUpdateRequest,
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db)
):
    if org_id != org.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Update theme
    if data.theme_primary_color is not None:
        org.theme_primary_color = data.theme_primary_color
    if data.theme_accent_color is not None:
        org.theme_accent_color = data.theme_accent_color
    if data.theme_agency_name is not None:
        org.theme_agency_name = data.theme_agency_name

    await db.commit()
    await db.refresh(org)

    return {
        "theme_logo_url": org.theme_logo_url,
        "theme_primary_color": org.theme_primary_color,
        "theme_accent_color": org.theme_accent_color,
        "theme_agency_name": org.theme_agency_name,
    }

@router.post("/{org_id}/logo", response_model=ThemeResponse)
async def upload_logo(
    org_id: uuid.UUID,
    file: UploadFile = File(...),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db)
):
    if org_id != org.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Validate size and type
    if file.content_type not in ["image/jpeg", "image/png"]:
        raise HTTPException(status_code=400, detail="Invalid image type. Must be JPEG or PNG.")

    content = await file.read()
    if len(content) > 2 * 1024 * 1024:  # 2MB
        raise HTTPException(status_code=400, detail="Image size exceeds 2MB limit.")

    # Stub S3 Upload
    # In a real app, we would use boto3 or aiobotocore
    s3_key = f"orgs/{org_id}/logo_{uuid.uuid4().hex[:8]}.png"
    s3_url = f"https://s3.rankerpilot.com/{s3_key}"

    org.theme_logo_url = s3_url
    await db.commit()
    await db.refresh(org)

    return {
        "theme_logo_url": org.theme_logo_url,
        "theme_primary_color": org.theme_primary_color,
        "theme_accent_color": org.theme_accent_color,
        "theme_agency_name": org.theme_agency_name,
    }
