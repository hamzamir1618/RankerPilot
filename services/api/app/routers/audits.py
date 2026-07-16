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
from sqlalchemy import case, desc
from app.crawler.discovery import normalize_url
from app.workers.reports import generate_report_task
import io
import csv
from fastapi.responses import StreamingResponse

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
    sort: Optional[str] = "action_plan",
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    stmt = select(Finding).where(Finding.audit_id == audit_id)
    
    if sort == "action_plan":
        stmt = stmt.outerjoin(Page, Finding.page_id == Page.id)
        
        severity_case = case(
            (Finding.severity == "critical", 0),
            (Finding.severity == "high", 1),
            (Finding.severity == "medium", 2),
            (Finding.severity == "low", 3),
            else_=4
        )
        effort_case = case(
            (Finding.effort == "immediate", 0),
            (Finding.effort == "one_week", 1),
            (Finding.effort == "one_month", 2),
            (Finding.effort == "backlog", 3),
            else_=4
        )
        
        stmt = stmt.order_by(
            severity_case,
            desc(Page.internal_pagerank),
            effort_case,
            Finding.id
        )
    else:
        stmt = stmt.order_by(Finding.id)
        
    if severity:
        stmt = stmt.where(Finding.severity == severity)
    if category:
        stmt = stmt.where(Finding.category == category)
    if cursor:
        stmt = stmt.where(Finding.id > uuid.UUID(cursor))
        
    stmt = stmt.limit(100)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/audits/{audit_id}/action-plan")
async def get_action_plan(
    audit_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    # Fetch top findings ordered by action plan criteria
    stmt = select(Finding).outerjoin(Page, Finding.page_id == Page.id).where(
        Finding.audit_id == audit_id,
        Finding.status == "fail"
    )
    
    severity_case = case(
        (Finding.severity == "critical", 0),
        (Finding.severity == "high", 1),
        (Finding.severity == "medium", 2),
        (Finding.severity == "low", 3),
        else_=4
    )
    effort_case = case(
        (Finding.effort == "immediate", 0),
        (Finding.effort == "one_week", 1),
        (Finding.effort == "one_month", 2),
        (Finding.effort == "backlog", 3),
        else_=4
    )
    
    stmt = stmt.order_by(severity_case, desc(Page.internal_pagerank), effort_case, Finding.id).limit(50)
    result = await db.execute(stmt)
    findings = result.scalars().all()
    
    return [FindingResponse.model_validate(f).model_dump() for f in findings]

@router.get("/audits/{audit_id}/diff/{other_id}")
async def get_audit_diff(
    audit_id: uuid.UUID,
    other_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    # audit_id is newer, other_id is older
    newer = await db.scalar(select(Audit).where(Audit.id == audit_id))
    older = await db.scalar(select(Audit).where(Audit.id == other_id))
    
    if not newer or not older:
        raise HTTPException(status_code=404, detail="Audit not found")
        
    score_delta = (newer.score or 0.0) - (older.score or 0.0)
    
    # Load pages to get URLs
    newer_pages = await db.execute(select(Page).where(Page.audit_id == audit_id))
    older_pages = await db.execute(select(Page).where(Page.audit_id == other_id))
    
    newer_url_map = {p.id: normalize_url(p.url, newer.root_url) for p in newer_pages.scalars().all()}
    older_url_map = {p.id: normalize_url(p.url, older.root_url) for p in older_pages.scalars().all()}
    
    # Load findings
    newer_findings = await db.execute(select(Finding).where(Finding.audit_id == audit_id))
    older_findings = await db.execute(select(Finding).where(Finding.audit_id == other_id))
    
    def make_key(f, url_map):
        url = url_map.get(f.page_id, "") if f.page_id else ""
        return (f.check_id, url)
        
    newer_f_map = {make_key(f, newer_url_map): f for f in newer_findings.scalars().all()}
    older_f_map = {make_key(f, older_url_map): f for f in older_findings.scalars().all()}
    
    resolved = []
    new_findings = []
    unchanged = []
    
    # Check what was in older
    for key, old_f in older_f_map.items():
        if old_f.status == "fail":
            new_f = newer_f_map.get(key)
            if not new_f or new_f.status != "fail":
                resolved.append(FindingResponse.model_validate(old_f).model_dump())
            else:
                unchanged.append(FindingResponse.model_validate(new_f).model_dump())
                
    # Check what is in newer but wasn't failing in older
    for key, new_f in newer_f_map.items():
        if new_f.status == "fail":
            old_f = older_f_map.get(key)
            if not old_f or old_f.status != "fail":
                new_findings.append(FindingResponse.model_validate(new_f).model_dump())
                
    return {
        "score_delta": round(score_delta, 1),
        "resolved": resolved,
        "new": new_findings,
        "unchanged": unchanged
    }

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

@router.post("/audits/{audit_id}/report", status_code=202)
async def request_report(audit_id: uuid.UUID, user=Depends(get_current_user)):
    generate_report_task.delay(str(audit_id))
    return {"status": "accepted"}

@router.get("/reports/{audit_id}")
async def get_report(audit_id: uuid.UUID, user=Depends(get_current_user)):
    # Check if the report is ready in Redis
    url = await redis_client.get(f"report_url:{str(audit_id)}")
    if url:
        return {"status": "ready", "url": url}
    return {"status": "pending"}

@router.get("/audits/{audit_id}/export.csv")
async def export_csv(
    audit_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    async def iter_csv():
        yield "ID,Check,Status,Severity,Category,Title,Page_ID\n"
        stmt = select(Finding).where(Finding.audit_id == audit_id).order_by(Finding.id)
        # SQLAlchemy async streaming
        result = await db.stream(stmt)
        async for row in result.scalars():
            out = io.StringIO()
            writer = csv.writer(out)
            writer.writerow([
                str(row.id),
                row.check_id,
                row.status.value if hasattr(row.status, 'value') else str(row.status),
                row.severity.value if row.severity and hasattr(row.severity, 'value') else str(row.severity) if row.severity else "",
                row.category.value if hasattr(row.category, 'value') else str(row.category),
                row.title,
                str(row.page_id) if row.page_id else ""
            ])
            yield out.getvalue()
            
    return StreamingResponse(iter_csv(), media_type="text/csv", headers={
        "Content-Disposition": f"attachment; filename=audit_{audit_id}_findings.csv"
    })
