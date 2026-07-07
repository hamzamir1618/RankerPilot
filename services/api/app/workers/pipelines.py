import uuid
import asyncio
import time
from celery import shared_task, chord, chain, group
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert

from app.workers.celery_app import celery_app
from app.core.deps import async_session_factory
from app.core.events import publish_event_sync
from app.models.models import Audit, Page, Finding, AuditStatusEnum, FindingStatusEnum

from app.crawler.fetcher import fetch_page
from app.schemas.schemas import PageResponse
from app.agents.base import AuditContext
from app.agents.technical import TechnicalAgent

# Registry of agents
AGENTS = {
    "technical": TechnicalAgent()
}

def get_db_session() -> AsyncSession:
    return async_session_factory()

async def async_crawl_site(audit_id_str: str, url: str):
    audit_id = uuid.UUID(audit_id_str)
    # 1. Fetch single page for now
    publish_event_sync(audit_id_str, "crawl.progress", {"url": url})
    
    res = await fetch_page(url, audit_id)
    
    async with async_session_factory() as db:
        # Save page to DB
        page = Page(
            id=uuid.uuid4(),
            audit_id=audit_id,
            url=res.url,
            status_code=res.status_code,
            rendered=res.rendered,
            title=res.title,
            meta_description=res.meta_description,
            h1=res.h1,
            word_count=res.word_count,
            snapshot_key=res.snapshot_key,
            screenshot_key=res.screenshot_key,
            lab_vitals=res.lab_vitals
        )
        db.add(page)
        
        # Update audit status
        audit = await db.scalar(select(Audit).where(Audit.id == audit_id))
        if audit:
            audit.status = AuditStatusEnum.analyzing
            
        await db.commit()
    
    publish_event_sync(audit_id_str, "crawl.completed", {"pages_crawled": 1})
    return audit_id_str

@shared_task(bind=True, name="app.workers.pipelines.crawl_site", soft_time_limit=1200)
def crawl_site(self, audit_id_str: str, url: str):
    publish_event_sync(audit_id_str, "audit.started", {})
    return asyncio.run(async_crawl_site(audit_id_str, url))

@shared_task(bind=True, name="app.workers.pipelines.detect_industry")
def detect_industry(self, audit_id_str: str):
    # Stub for Prompt 6
    return {"audit_id": audit_id_str, "industry": "saas"}

async def async_run_agent(agent_id: str, ctx_dict: dict):
    start_time = time.time()
    audit_id_str = ctx_dict["audit_id"]
    audit_id = uuid.UUID(audit_id_str)
    
    publish_event_sync(audit_id_str, "agent.started", {"agent": agent_id})
    
    try:
        # Load pages from DB
        async with async_session_factory() as db:
            result = await db.execute(select(Page).where(Page.audit_id == audit_id))
            pages_db = result.scalars().all()
            
            pages_resp = [PageResponse.model_validate(p) for p in pages_db]
            
        ctx = AuditContext(
            audit_id=audit_id_str,
            pages=pages_resp,
            site_graph={},
            robots_txt=None,
            sitemap_urls=[],
            industry=ctx_dict.get("industry", "saas")
        )
        
        agent = AGENTS.get(agent_id)
        if not agent:
            raise ValueError(f"Unknown agent {agent_id}")
            
        findings = await agent.run(ctx)
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        publish_event_sync(audit_id_str, "agent.completed", {
            "agent": agent_id, 
            "findings_count": len(findings), 
            "elapsed_ms": elapsed_ms
        })
        
        return findings
        
    except Exception as e:
        # Don't fail the chord, return empty findings and publish failed event
        elapsed_ms = int((time.time() - start_time) * 1000)
        publish_event_sync(audit_id_str, "agent.failed", {
            "agent": agent_id, 
            "error": str(e),
            "elapsed_ms": elapsed_ms
        })
        return []

@shared_task(bind=True, name="app.workers.pipelines.run_agent", soft_time_limit=300)
def run_agent(self, ctx_dict: dict, agent_id: str):
    return asyncio.run(async_run_agent(agent_id, ctx_dict))

async def async_aggregate_findings(results: list, audit_id_str: str):
    # results is a list of findings lists from agents
    flat_findings = []
    for r in results:
        flat_findings.extend(r)
        
    if not flat_findings:
        return audit_id_str
        
    # Idempotent Upsert
    async with async_session_factory() as db:
        stmt = insert(Finding).values([{
            "id": uuid.uuid4(),
            "audit_id": uuid.UUID(f["audit_id"]),
            "page_id": uuid.UUID(f["page_id"]) if f.get("page_id") else None,
            "agent": f["agent"],
            "check_id": f["check_id"],
            "status": f["status"],
            "severity": f.get("severity"),
            "category": f["category"],
            "title": f["title"],
            "evidence": f.get("evidence"),
            "fix": f.get("fix"),
            "fix_code": f.get("fix_code"),
            "effort": f.get("effort")
        } for f in flat_findings])
        
        stmt = stmt.on_conflict_do_update(
            constraint="uq_finding_audit_page_check",
            set_={
                "status": stmt.excluded.status,
                "severity": stmt.excluded.severity,
                "title": stmt.excluded.title,
                "evidence": stmt.excluded.evidence,
                "fix": stmt.excluded.fix,
                "fix_code": stmt.excluded.fix_code,
                "effort": stmt.excluded.effort
            }
        )
        
        await db.execute(stmt)
        await db.commit()
        
    return audit_id_str

@shared_task(bind=True, name="app.workers.pipelines.aggregate_findings")
def aggregate_findings(self, results: list, audit_id_str: str):
    # Due to chord signature, results is the first arg
    return asyncio.run(async_aggregate_findings(results, audit_id_str))

async def async_compute_score(audit_id_str: str):
    audit_id = uuid.UUID(audit_id_str)
    
    async with async_session_factory() as db:
        # Simple ratio of passes
        result = await db.execute(
            select(Finding.status, func.count(Finding.id))
            .where(Finding.audit_id == audit_id)
            .group_by(Finding.status)
        )
        counts = dict(result.all())
        
        total = sum(counts.values())
        passes = counts.get(FindingStatusEnum.pass_, 0)
        
        score = (passes / total * 100) if total > 0 else 0
        
        audit = await db.scalar(select(Audit).where(Audit.id == audit_id))
        if audit:
            audit.score = score
            audit.category_scores = {"technical": score} # stub
            
        await db.commit()
        
    publish_event_sync(audit_id_str, "score.computed", {"score": float(score)})
    return audit_id_str

@shared_task(bind=True, name="app.workers.pipelines.compute_score")
def compute_score(self, audit_id_str: str):
    return asyncio.run(async_compute_score(audit_id_str))

async def async_finalize_audit(audit_id_str: str):
    audit_id = uuid.UUID(audit_id_str)
    
    async with async_session_factory() as db:
        audit = await db.scalar(select(Audit).where(Audit.id == audit_id))
        if audit:
            audit.status = AuditStatusEnum.done
            audit.finished_at = func.now()
            await db.commit()
            
    publish_event_sync(audit_id_str, "audit.done", {})
    return audit_id_str

@shared_task(bind=True, name="app.workers.pipelines.finalize_audit")
def finalize_audit(self, audit_id_str: str):
    return asyncio.run(async_finalize_audit(audit_id_str))

def start_audit_pipeline(audit_id: uuid.UUID, url: str, mode: str):
    audit_id_str = str(audit_id)
    roster = ["technical"]
    
    audit_pipeline = chain(
        crawl_site.s(audit_id_str, url),
        detect_industry.s(),
        chord(
            group(run_agent.s(agent_id) for agent_id in roster),
            aggregate_findings.s(audit_id_str)
        ),
        compute_score.s(),
        finalize_audit.s()
    )
    audit_pipeline.apply_async()

@shared_task(bind=True, name="app.workers.pipelines.cleanup_s3_keys")
def cleanup_s3_keys(self, keys: list[str]):
    """
    Deletes the given keys from S3.
    This is executed when a project is deleted.
    """
    if not keys:
        return
        
    # TODO: Initialize boto3 client and delete objects
    # s3 = boto3.client('s3', region_name=settings.AWS_REGION)
    # objects = [{'Key': key} for key in keys]
    # s3.delete_objects(Bucket=settings.S3_BUCKET, Delete={'Objects': objects})
    print(f"S3 Cleanup Stub: Would delete {len(keys)} keys from S3")
    return {"deleted_keys_count": len(keys)}

