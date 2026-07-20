import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.deps import get_db, get_current_user
from app.models.models import Project, DriftEvent, User, Baseline
from app.crawler.fetcher import fetch_page

router = APIRouter(prefix="/v1", tags=["drift"])

class BaselinesRequest(BaseModel):
    urls: List[str]

@router.post("/projects/{project_id}/baselines", status_code=202)
async def create_baselines(
    project_id: uuid.UUID,
    req: BaselinesRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
        
    # Schedule background task to fetch and save baselines
    background_tasks.add_task(fetch_and_save_baselines, project_id, req.urls)
    
    return {"status": "accepted", "message": "Baseline fetching started"}

async def fetch_and_save_baselines(project_id: uuid.UUID, urls: List[str]):
    from app.core.deps import async_session_factory
    
    async with async_session_factory() as db:
        for url in urls:
            try:
                res = await fetch_page(url, uuid.uuid4())
                
                snapshot = {
                    "title": res.title,
                    "meta_description": res.meta_description,
                    "h1": res.h1,
                    "word_count": res.word_count,
                    "status_code": res.status_code,
                    "json_ld": res.json_ld,
                    "lab_vitals": res.lab_vitals,
                    "images": res.images,
                    "links": res.links,
                }
                
                baseline = Baseline(
                    id=uuid.uuid4(),
                    project_id=project_id,
                    page_url=url,
                    snapshot=snapshot
                )
                db.add(baseline)
            except Exception as e:
                print(f"Failed to fetch baseline for {url}: {e}")
                
        await db.commit()

@router.get("/projects/{project_id}/drift")
async def get_drift_events(
    project_id: uuid.UUID,
    acknowledged: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    stmt = select(DriftEvent).where(
        DriftEvent.project_id == project_id,
        DriftEvent.acknowledged == acknowledged
    ).order_by(DriftEvent.detected_at.desc())
    
    result = await db.execute(stmt)
    events = result.scalars().all()
    
    return [
        {
            "id": e.id,
            "page_url": e.page_url,
            "rule": e.rule,
            "before": e.before,
            "after": e.after,
            "detected_at": e.detected_at,
            "acknowledged": e.acknowledged
        } for e in events
    ]

@router.post("/projects/{project_id}/drift/{event_id}/acknowledge")
async def acknowledge_drift_event(
    project_id: uuid.UUID,
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    event = await db.scalar(select(DriftEvent).where(DriftEvent.id == event_id, DriftEvent.project_id == project_id))
    if not event:
        raise HTTPException(404, "Drift event not found")
        
    event.acknowledged = True
    await db.commit()
    return {"status": "success"}
