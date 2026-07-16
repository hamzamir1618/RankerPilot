from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
import datetime

from app.core.deps import get_db, get_current_user
from app.models.models import Project, KeywordSet, Keyword, KeywordIntentEnum, User
from app.integrations.dataforseo import keyword_ideas, domain_intersection, serp_advanced, CostMeter
from app.core.config import settings

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
    
    meter = CostMeter(cap=settings.DFS_AUDIT_BUDGET_USD)
    
    # Ideally, if URL is provided, we use a different DFS endpoint, but let's assume we use keyword_ideas with seed
    seed = req.seed or req.url
    dfs_data = await keyword_ideas([str(seed)], location_code, req.language, meter=meter)
    
    if dfs_data and dfs_data.get("error") == "budget_exceeded":
        return {"status": "partial", "message": "keyword data truncated: budget cap reached"}
        
    if not dfs_data or not dfs_data.get("tasks"):
        raise HTTPException(status_code=500, detail="DFS integration failed")
        
    # Extract keywords
    items = dfs_data["tasks"][0].get("result", [])
    if not items:
        return {"keywords": []}
        
    keyword_list = items[0].get("items", [])[:50] # Take top 50
    
    # Save to KeywordSet
    kw_set_name = req.keyword_set_name or f"Discovery for {seed}"
    kw_set = KeywordSet(id=uuid.uuid4(), project_id=project_id, name=kw_set_name)
    db.add(kw_set)
    await db.flush()
    
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
        
    meter = CostMeter(cap=settings.DFS_AUDIT_BUDGET_USD)
    
    # Compare project.domain with competitor 1
    # For full multi-domain intersection, DFS expects target1 and target2. 
    # We will just intersect our domain with the first competitor for simplicity here.
    comp1 = req.competitors[0]
    
    dfs_data = await domain_intersection(project.domain, comp1, meter=meter)
    
    if dfs_data and dfs_data.get("error") == "budget_exceeded":
        return {"status": "partial", "message": "keyword data truncated: budget cap reached"}
        
    if not dfs_data or not dfs_data.get("tasks"):
        raise HTTPException(status_code=500, detail="DFS integration failed")
        
    items = dfs_data["tasks"][0].get("result", [])
    if not items:
        return {"keywords": []}
        
    keyword_list = items[0].get("items", [])[:50]
    
    kw_set_name = req.keyword_set_name or f"Gap vs {comp1}"
    kw_set = KeywordSet(id=uuid.uuid4(), project_id=project_id, name=kw_set_name)
    db.add(kw_set)
    await db.flush()
    
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
        
    meter = CostMeter(cap=settings.DFS_AUDIT_BUDGET_USD)
    dfs_data = await serp_advanced(keyword.term, meter=meter)
    
    if dfs_data and dfs_data.get("error") == "budget_exceeded":
        return {"status": "partial", "message": "keyword data truncated: budget cap reached"}
        
    if not dfs_data or not dfs_data.get("tasks"):
        raise HTTPException(status_code=500, detail="DFS integration failed")
        
    items = dfs_data["tasks"][0].get("result", [])
    if not items:
        return {"status": "no_results"}
        
    keyword.serp_snapshot = items[0]
    keyword.refreshed_at = datetime.datetime.now(datetime.timezone.utc)
    
    await db.commit()
    return {"status": "success", "keyword_id": keyword.id}
