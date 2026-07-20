import uuid
import datetime
import asyncio
from celery import shared_task
from sqlalchemy import select

from app.core.deps import async_session_factory
from app.models.models import Project, Keyword, KeywordSet, RankSnapshot, Organization
from app.integrations.dataforseo import serp_advanced
from app.services.credits import debit
from app.core.billing import COST_TABLE

async def async_run_rank_tracking_for_project(project_id_str: str):
    project_id = uuid.UUID(project_id_str)
    
    async with async_session_factory() as db:
        # Fetch tracked keywords
        stmt = select(Keyword).join(KeywordSet).where(
            KeywordSet.project_id == project_id,
            Keyword.is_tracked.is_(True)
        )
        result = await db.execute(stmt)
        keywords = result.scalars().all()
        
        if not keywords:
            return
            
        project = await db.get(Project, project_id)
        if not project:
            return
            
        cost_per_keyword = COST_TABLE["keyword_serp"]
        
        for kw in keywords:
            try:
                # Atomically debit
                await db.execute(select(Organization).where(Organization.id == project.org_id).with_for_update())
                debit(db, project.org_id, cost_per_keyword, "Scheduled Rank Tracking", ref_type="keyword", ref_id=kw.id)
                await db.commit()
                
                # Fetch SERP
                res = await serp_advanced(
                    keyword=kw.term,
                    language_code=kw.language,
                    location_code=int(kw.country) if kw.country else 2840,
                    meter=None
                )
                
                if not res:
                    continue
                
                tasks = res.get("tasks", [])
                if not tasks or not tasks[0].get("result"):
                    continue
                    
                items = tasks[0]["result"][0].get("items", [])
                
                # Extract position
                position = None
                url = None
                for item in items:
                    if item.get("type") == "organic" and item.get("domain") == project.domain:
                        position = item.get("rank_group")
                        url = item.get("url")
                        break
                        
                snapshot = RankSnapshot(
                    keyword_id=kw.id,
                    position=position,
                    url=url,
                    serp_features=[i.get("type") for i in items if i.get("type") != "organic"],
                    captured_at=datetime.datetime.now(datetime.timezone.utc)
                )
                db.add(snapshot)
                await db.commit()
                
            except Exception as e:
                await db.rollback()
                print(f"Rank tracking failed for keyword {kw.id}: {e}")

@shared_task(bind=True, name="app.workers.rank_tracking.run_rank_tracking_for_project")
def run_rank_tracking_for_project(self, project_id_str: str):
    asyncio.run(async_run_rank_tracking_for_project(project_id_str))
