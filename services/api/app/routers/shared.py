import uuid
import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.deps import get_db, get_current_org
from app.models.models import User, Audit, SharedReportToken, Page, Finding, Project, Organization

router = APIRouter(prefix="/v1", tags=["shared"])

class ShareRequest(BaseModel):
    expires_in_days: int | None = None

@router.post("/audits/{audit_id}/share")
async def generate_share_token(
    audit_id: uuid.UUID,
    req: ShareRequest,
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(get_current_org)
):
    audit = await db.get(Audit, audit_id)
    if not audit:
        raise HTTPException(404, "Audit not found")
        
    expires_at = None
    if req.expires_in_days:
        expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=req.expires_in_days)
        
    token = SharedReportToken(
        token=uuid.uuid4(),
        audit_id=audit_id,
        expires_at=expires_at,
        revoked=False
    )
    db.add(token)
    await db.commit()
    
    return {"status": "success", "token": token.token, "expires_at": expires_at}

@router.post("/audits/{audit_id}/share/{token_id}/revoke")
async def revoke_share_token(
    audit_id: uuid.UUID,
    token_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(get_current_org)
):
    token = await db.scalar(select(SharedReportToken).where(SharedReportToken.token == token_id, SharedReportToken.audit_id == audit_id))
    if not token:
        raise HTTPException(404, "Token not found")
        
    token.revoked = True
    await db.commit()
    return {"status": "success"}

@router.get("/shared/{token}")
async def get_shared_report(
    token: uuid.UUID,
    db: AsyncSession = Depends(get_db)
    # NO auth dependency here! Public endpoint.
):
    # Verify token
    shared_token = await db.get(SharedReportToken, token)
    if not shared_token:
        raise HTTPException(404, "Not found")
        
    if shared_token.revoked:
        raise HTTPException(403, "Token revoked")
        
    if shared_token.expires_at and shared_token.expires_at < datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None):
        raise HTTPException(403, "Token expired")
        
    # Fetch Audit safely
    audit = await db.get(Audit, shared_token.audit_id)
    if not audit:
        raise HTTPException(404, "Audit not found")
        
    project = await db.get(Project, audit.project_id)
    org = await db.get(Organization, project.org_id) if project else None
        
    # Fetch Pages (stripped)
    pages_res = await db.execute(select(Page).where(Page.audit_id == audit.id))
    pages = pages_res.scalars().all()
    
    # Fetch Findings
    findings_res = await db.execute(select(Finding).where(Finding.audit_id == audit.id))
    findings = findings_res.scalars().all()
    
    # Construct a sanitized response that doesn't leak internal IDs (except page_id to link findings)
    # No org_id or user_ids exposed
    return {
        "report_date": audit.finished_at or audit.started_at,
        "score": audit.score,
        "category_scores": audit.category_scores,
        "target_url": audit.root_url,
        "domain": project.domain if project else None,
        "theme": {
            "logo_url": org.theme_logo_url if org else None,
            "primary_color": org.theme_primary_color if org else None,
            "accent_color": org.theme_accent_color if org else None,
            "agency_name": org.theme_agency_name if org else None
        },
        "pages": [
            {
                "id": str(p.id),
                "url": p.url,
                "status_code": p.status_code,
                "title": p.title,
                "word_count": p.word_count
            } for p in pages
        ],
        "findings": [
            {
                "page_id": str(f.page_id) if f.page_id else None,
                "category": str(f.category.value if hasattr(f.category, 'value') else f.category),
                "severity": str(f.severity.value if f.severity and hasattr(f.severity, 'value') else f.severity),
                "title": f.title,
                "evidence": f.evidence,
                "fix": f.fix
            } for f in findings
        ]
    }
