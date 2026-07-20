from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import datetime
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
import io
import csv
from fastapi.responses import StreamingResponse

from app.core.deps import get_db, get_current_user
from app.models.models import Project, KeywordSet, Keyword, KeywordIntentEnum, User, RankSnapshot, ProjectSchedule, Organization
from app.integrations.dataforseo import keyword_ideas, domain_intersection, serp_advanced, CostMeter
from app.core.config import settings
from app.core.billing import COST_TABLE
from app.services.credits import get_balance, debit

router = APIRouter(prefix="/v1", tags=["Keywords"])

class DiscoverRequest(BaseModel):
    seed: Optional[str] = None
    url: Optional[str] = None
    country: str = "US"
    language: str = "en"
    keyword_set_name: Optional[str] = None

class GapRequest(BaseModel):
    competitors: List[str] = Field(..., max_length=3, min_length=1, description="Max 3 competitors")
    country: str = "US"
    language: str = "en"
    keyword_set_name: Optional[str] = None

@router.post("/projects/{project_id}/keywords/discover")
async def discover_keywords(
    project_id: uuid.UUID,
    req: DiscoverRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not req.seed and not req.url:
        raise HTTPException(status_code=400, detail="Must provide seed or url")
        
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    # Mocking location_code and language_code mapping for simplicity
    location_code = 2840 # US
    
    required_cost = COST_TABLE.get("keyword_discover", 5)
    
    try:
        await db.execute(
            select(Organization)
            .where(Organization.id == project.org_id)
            .with_for_update()
        )
        
        current_balance = await get_balance(db, project.org_id)
        if current_balance < required_cost:
            raise HTTPException(
                status_code=402, 
                detail={
                    "error": "Payment Required",
                    "current_balance": current_balance, 
                    "required": required_cost, 
                    "shortfall": required_cost - current_balance
                }
            )
            
        meter = CostMeter(cap=settings.DFS_AUDIT_BUDGET_USD)
        
        # Ideally, if URL is provided, we use a different DFS endpoint, but let's assume we use keyword_ideas with seed
        seed = req.seed or req.url
        dfs_data = await keyword_ideas([str(seed)], location_code, req.language, meter=meter)
        
        if dfs_data and dfs_data.get("error") == "budget_exceeded":
            await db.rollback()
            return {"status": "partial", "message": "keyword data truncated: budget cap reached"}
            
        if not dfs_data or not dfs_data.get("tasks"):
            await db.rollback()
            raise HTTPException(status_code=500, detail="DFS integration failed")
            
        # Extract keywords
        items = dfs_data["tasks"][0].get("result", [])
        if not items:
            await db.rollback()
            return {"keywords": []}
            
        keyword_list = items[0].get("items", [])[:50] # Take top 50
        
        # Save to KeywordSet
        kw_set_name = req.keyword_set_name or f"Discovery for {seed}"
        kw_set = KeywordSet(id=uuid.uuid4(), project_id=project_id, name=kw_set_name)
        db.add(kw_set)
        
        # Debit
        debit(db, project.org_id, required_cost, "Keyword Discovery", ref_type="keyword_set", ref_id=kw_set.id)
        await db.flush()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise e
    
    saved_keywords = []
    for item in keyword_list:
        vol = item.get("search_volume")
        diff = item.get("keyword_info", {}).get("competition_level")
        cpc = item.get("keyword_info", {}).get("cpc")
        # intent is complex in DFS, simplifying:
        intent = KeywordIntentEnum.informational
        
        kw = Keyword(
            id=uuid.uuid4(),
            set_id=kw_set.id,
            term=item["keyword"],
            country=req.country,
            language=req.language,
            volume=vol,
            difficulty=diff,
            cpc=cpc,
            intent=intent
        )
        db.add(kw)
        saved_keywords.append(kw)
        
    await db.commit()
    return {"keyword_set_id": kw_set.id, "count": len(saved_keywords)}

@router.post("/projects/{project_id}/keywords/gap")
async def keyword_gap_analysis(
    project_id: uuid.UUID,
    req: GapRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    required_cost = COST_TABLE.get("keyword_gap", 10)
    
    try:
        await db.execute(
            select(Organization)
            .where(Organization.id == project.org_id)
            .with_for_update()
        )
        
        current_balance = await get_balance(db, project.org_id)
        if current_balance < required_cost:
            raise HTTPException(
                status_code=402, 
                detail={
                    "error": "Payment Required",
                    "current_balance": current_balance, 
                    "required": required_cost, 
                    "shortfall": required_cost - current_balance
                }
            )
            
        meter = CostMeter(cap=settings.DFS_AUDIT_BUDGET_USD)
        
        comp1 = req.competitors[0]
        dfs_data = await domain_intersection(project.domain, comp1, meter=meter)
        
        if dfs_data and dfs_data.get("error") == "budget_exceeded":
            await db.rollback()
            return {"status": "partial", "message": "keyword data truncated: budget cap reached"}
            
        if not dfs_data or not dfs_data.get("tasks"):
            await db.rollback()
            raise HTTPException(status_code=500, detail="DFS integration failed")
            
        items = dfs_data["tasks"][0].get("result", [])
        if not items:
            await db.rollback()
            return {"keywords": []}
            
        keyword_list = items[0].get("items", [])[:50]
        
        kw_set_name = req.keyword_set_name or f"Gap vs {comp1}"
        kw_set = KeywordSet(id=uuid.uuid4(), project_id=project_id, name=kw_set_name)
        db.add(kw_set)
        
        debit(db, project.org_id, required_cost, "Keyword Gap", ref_type="keyword_set", ref_id=kw_set.id)
        await db.flush()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise e
    
    for item in keyword_list:
        kw_data = item.get("keyword_data", {})
        kw = Keyword(
            id=uuid.uuid4(),
            set_id=kw_set.id,
            term=kw_data.get("keyword", "unknown"),
            country=req.country,
            language=req.language,
            volume=kw_data.get("keyword_info", {}).get("search_volume"),
            difficulty=kw_data.get("keyword_info", {}).get("competition_level"),
            cpc=kw_data.get("keyword_info", {}).get("cpc"),
            intent=KeywordIntentEnum.informational
        )
        db.add(kw)
        
    await db.commit()
    return {"keyword_set_id": kw_set.id, "competitors": req.competitors}

@router.get("/keyword-sets/{set_id}")
async def get_keyword_set(
    set_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    kset = await db.get(KeywordSet, set_id)
    if not kset:
        raise HTTPException(status_code=404, detail="Keyword Set not found")
        
    result = await db.execute(select(Keyword).where(Keyword.set_id == set_id))
    keywords = result.scalars().all()
    
    return {
        "id": kset.id,
        "name": kset.name,
        "keywords": [
            {
                "id": k.id,
                "term": k.term,
                "volume": k.volume,
                "difficulty": k.difficulty,
                "opportunity_score": k.opportunity_score,
                "has_serp": bool(k.serp_snapshot)
            } for k in keywords
        ]
    }

@router.post("/keywords/{keyword_id}/serp")
async def fetch_keyword_serp(
    keyword_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    keyword = await db.get(Keyword, keyword_id)
    if not keyword:
        raise HTTPException(status_code=404, detail="Keyword not found")
    kw_set = await db.get(KeywordSet, keyword.set_id)
    if not kw_set:
        raise HTTPException(status_code=404, detail="KeywordSet not found")
        
    project = await db.get(Project, kw_set.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    required_cost = COST_TABLE.get("keyword_serp", 2)
    
    try:
        await db.execute(
            select(Organization)
            .where(Organization.id == project.org_id)
            .with_for_update()
        )
        
        current_balance = await get_balance(db, project.org_id)
        if current_balance < required_cost:
            raise HTTPException(
                status_code=402, 
                detail={
                    "error": "Payment Required",
                    "current_balance": current_balance, 
                    "required": required_cost, 
                    "shortfall": required_cost - current_balance
                }
            )
            
        meter = CostMeter(cap=settings.DFS_AUDIT_BUDGET_USD)
        dfs_data = await serp_advanced(keyword.term, meter=meter)
        
        if dfs_data and dfs_data.get("error") == "budget_exceeded":
            await db.rollback()
            return {"status": "partial", "message": "keyword data truncated: budget cap reached"}
            
        if not dfs_data or not dfs_data.get("tasks"):
            await db.rollback()
            raise HTTPException(status_code=500, detail="DFS integration failed")
            
        items = dfs_data["tasks"][0].get("result", [])
        if not items:
            await db.rollback()
            return {"status": "no_results"}
            
        keyword.serp_snapshot = items[0]
        keyword.refreshed_at = datetime.datetime.now(datetime.timezone.utc)
        
        debit(db, project.org_id, required_cost, "Keyword SERP", ref_type="keyword", ref_id=keyword.id)
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
        
    return {"status": "success", "keyword_id": keyword_id}

class RankTrackingRequest(BaseModel):
    keyword_ids: List[uuid.UUID]
    schedule: str

@router.post("/projects/{project_id}/tracking")
async def register_tracking(
    project_id: uuid.UUID,
    req: RankTrackingRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    # Mark keywords as tracked
    subq = select(KeywordSet.id).where(KeywordSet.project_id == project_id)
    await db.execute(
        update(Keyword).where(
            Keyword.id.in_(req.keyword_ids),
            Keyword.set_id.in_(subq)
        ).values(is_tracked=True)
    )

    # Set schedule in ProjectSchedule
    sched = await db.get(ProjectSchedule, project_id)
    if not sched:
        sched = ProjectSchedule(project_id=project_id, rank_cadence=req.schedule)
        db.add(sched)
    else:
        sched.rank_cadence = req.schedule

    await db.commit()
    return {"status": "success"}

@router.get("/projects/{project_id}/tracking/trends")
async def get_tracking_trends(
    project_id: uuid.UUID,
    from_date: datetime.datetime,
    to_date: datetime.datetime,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    stmt = select(RankSnapshot, Keyword).join(
        Keyword, RankSnapshot.keyword_id == Keyword.id
    ).join(
        KeywordSet, Keyword.set_id == KeywordSet.id
    ).where(
        KeywordSet.project_id == project_id,
        RankSnapshot.captured_at >= from_date,
        RankSnapshot.captured_at <= to_date
    ).order_by(RankSnapshot.captured_at.asc())
    
    result = await db.execute(stmt)
    rows = result.all()
    
    response = []
    for snapshot, keyword in rows:
        response.append({
            "keyword_id": keyword.id,
            "term": keyword.term,
            "position": snapshot.position,
            "url": snapshot.url,
            "captured_at": snapshot.captured_at
        })
    return response

@router.get("/projects/{project_id}/keywords/export.csv")
async def export_keywords_csv(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    async def iter_csv():
        yield "ID,Set_Name,Term,Country,Language,Volume,Difficulty,CPC,Intent,Tracked\n"
        
        stmt = select(Keyword, KeywordSet).join(
            KeywordSet, Keyword.set_id == KeywordSet.id
        ).where(
            KeywordSet.project_id == project_id
        ).order_by(Keyword.id)
        
        result = await db.stream(stmt)
        async for kw, kset in result:
            out = io.StringIO()
            writer = csv.writer(out)
            writer.writerow([
                str(kw.id),
                kset.name,
                kw.term,
                kw.country,
                kw.language,
                str(kw.volume) if kw.volume is not None else "",
                str(kw.difficulty) if kw.difficulty is not None else "",
                str(kw.cpc) if kw.cpc is not None else "",
                kw.intent.value if hasattr(kw.intent, 'value') else str(kw.intent),
                str(kw.is_tracked)
            ])
            yield out.getvalue()

    return StreamingResponse(iter_csv(), media_type="text/csv", headers={
        "Content-Disposition": f"attachment; filename=project_{project_id}_keywords.csv"
    })

