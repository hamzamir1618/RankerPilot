import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sse_starlette.sse import EventSourceResponse

from app.core.deps import get_db, get_current_user
from app.models.models import Audit, Project, Finding, Page, AuditStatusEnum, AuditModeEnum
from app.schemas.schemas import AuditResponse, FindingResponse, PageResponse
from app.workers.pipelines import start_audit_pipeline
from app.crawler.validator import validate_target_url, SSRFViolation
from app.core.rate_limit import redis_client

router = APIRouter(prefix="/v1", tags=["audits"])

@router.post("/projects/{project_id}/audits", status_code=202)
async def create_audit(
    project_id: uuid.UUID,
    data: dict, # mode, url, page_limit
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    project = await db.scalar(select(Project).where(Project.id == project_id))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    mode_str = data.get("mode", "single_page")
    url = data.get("url")
    page_limit = data.get("page_limit", 1)
    
    if mode_str not in ("full", "single_page"):
        raise HTTPException(status_code=400, detail="Invalid mode")
        
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    try:
        await validate_target_url(url)
    except SSRFViolation as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    audit = Audit(
        id=uuid.uuid4(),
        project_id=project_id,
        status=AuditStatusEnum.queued,
        mode=AuditModeEnum[mode_str],
        page_limit=page_limit,
        root_url=url,
        created_by=user.id
    )
    db.add(audit)
    await db.commit()
    
    # Enqueue pipeline
    start_audit_pipeline(audit.id, url, mode_str)
    
    return {"audit_id": audit.id}

@router.get("/audits/{audit_id}", response_model=AuditResponse)
async def get_audit(
    audit_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    audit = await db.scalar(select(Audit).where(Audit.id == audit_id))
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    return audit

@router.get("/audits/{audit_id}/findings", response_model=List[FindingResponse])
async def get_findings(
    audit_id: uuid.UUID,
    severity: Optional[str] = None,
    category: Optional[str] = None,
    cursor: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    stmt = select(Finding).where(Finding.audit_id == audit_id)
    if severity:
        stmt = stmt.where(Finding.severity == severity)
    if category:
        stmt = stmt.where(Finding.category == category)
    if cursor:
        stmt = stmt.where(Finding.id > uuid.UUID(cursor))
        
    stmt = stmt.order_by(Finding.id).limit(100)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/audits/{audit_id}/pages", response_model=List[PageResponse])
async def get_pages(
    audit_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    stmt = select(Page).where(Page.audit_id == audit_id)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/audits/{audit_id}/events")
async def sse_events(audit_id: str, request: Request):
    async def event_generator():
        channel = f"audit_events:{audit_id}"
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(channel)
        
        try:
            while True:
                if await request.is_disconnected():
                    break
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    yield {"data": message["data"]}
        finally:
            await pubsub.unsubscribe(channel)
            
    return EventSourceResponse(event_generator())
