import uuid
import asyncio
import time
import urllib.parse
import aiohttp
from celery import shared_task, chord, chain, group
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert

from app.workers.celery_app import celery_app
from app.core.deps import async_session_factory
from app.core.events import publish_event_sync
from app.models.models import Audit, Page, Finding, AuditStatusEnum, FindingStatusEnum, Project

from app.crawler.fetcher import fetch_page
from app.schemas.schemas import PageResponse
from app.agents.base import AuditContext
from app.agents.technical import TechnicalAgent

from app.crawler.discovery import extract_sitemap_urls, normalize_url, is_internal, get_registrable_domain
from app.services.industry_detection import detect_industry as detect_industry_service
from playwright.async_api import async_playwright

# Registry of agents
AGENTS = {
    "technical": TechnicalAgent()
}

def get_db_session() -> AsyncSession:
    return async_session_factory()

async def async_crawl_site(audit_id_str: str, url: str):
    audit_id = uuid.UUID(audit_id_str)
    publish_event_sync(audit_id_str, "crawl.progress", {"url": "Initializing discovery..."})
    
    # 1. Fetch Audit to get page_limit
    async with async_session_factory() as db:
        audit = await db.scalar(select(Audit).where(Audit.id == audit_id))
        if not audit:
            return audit_id_str
        page_limit = audit.page_limit
        root_url = audit.root_url
        
        audit.status = AuditStatusEnum.crawling
        await db.commit()

    budget_seconds = page_limit * 20
    start_time = time.time()
    
    base_domain = get_registrable_domain(root_url)
    
    queue = asyncio.Queue()
    queued_urls = set()
    
    def enqueue(u):
        u_norm = normalize_url(u, root_url)
        if len(queued_urls) < page_limit and u_norm not in queued_urls and is_internal(u_norm, base_domain):
            queued_urls.add(u_norm)
            queue.put_nowait(u_norm)
            
    # Seed with root URL
    enqueue(root_url)
    
    # Extract sitemap
    sitemap_url = urllib.parse.urljoin(root_url, '/sitemap.xml')
    async with aiohttp.ClientSession() as session:
        sitemap_urls = await extract_sitemap_urls(sitemap_url, session)
        for su in sitemap_urls:
            if len(queued_urls) >= page_limit:
                break
            enqueue(su)

    crawled_count = 0
    
    async def worker(browser_context=None):
        nonlocal crawled_count
        while crawled_count < page_limit:
            if time.time() - start_time > budget_seconds:
                break
            try:
                # Short timeout to yield control
                current_url = await asyncio.wait_for(queue.get(), timeout=2.0)
            except asyncio.TimeoutError:
                if queue.empty():
                    # If queue is empty, wait a bit longer just in case other workers are adding
                    await asyncio.sleep(2)
                    if queue.empty():
                        break
                continue
                
            if time.time() - start_time > budget_seconds:
                queue.task_done()
                break

            publish_event_sync(audit_id_str, "crawl.progress", {"url": current_url})
            res = await fetch_page(current_url, audit_id, browser_context=browser_context)
            crawled_count += 1
            
            async with async_session_factory() as db:
                page = Page(
                    id=uuid.uuid4(), audit_id=audit_id, url=res.url, status_code=res.status_code,
                    rendered=res.rendered, title=res.title, meta_description=res.meta_description,
                    h1=res.h1, word_count=res.word_count, snapshot_key=res.snapshot_key,
                    screenshot_key=res.screenshot_key, lab_vitals=res.lab_vitals
                )
                db.add(page)
                await db.commit()
                
            if res.links:
                for l in res.links:
                    if len(queued_urls) >= page_limit:
                        break
                    enqueue(l)
                    
            queue.task_done()

    # Pool Playwright contexts
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Create 4 contexts for 4 workers
        contexts = [await browser.new_context(user_agent="RankerPilot/1.0") for _ in range(4)]
        
        workers = [asyncio.create_task(worker(ctx)) for ctx in contexts]
        await asyncio.gather(*workers)
        
        for ctx in contexts:
            await ctx.close()
        await browser.close()
        
    # Check if partial
    async with async_session_factory() as db:
        audit = await db.scalar(select(Audit).where(Audit.id == audit_id))
        if audit:
            if time.time() - start_time > budget_seconds and crawled_count < page_limit:
                audit.status = AuditStatusEnum.partial
                audit.error = f"Budget exceeded. Crawled {crawled_count}/{page_limit} pages."
            else:
                audit.status = AuditStatusEnum.analyzing
            await db.commit()

    publish_event_sync(audit_id_str, "crawl.completed", {"pages_crawled": crawled_count})
    return audit_id_str

@shared_task(bind=True, name="app.workers.pipelines.crawl_site", soft_time_limit=3600)
def crawl_site(self, audit_id_str: str, url: str):
    publish_event_sync(audit_id_str, "audit.started", {})
    return asyncio.run(async_crawl_site(audit_id_str, url))

async def async_detect_industry(audit_id_str: str):
    audit_id = uuid.UUID(audit_id_str)
    
    async with async_session_factory() as db:
        result = await db.execute(select(Page).where(Page.audit_id == audit_id))
        pages_db = result.scalars().all()
        pages_resp = [PageResponse.model_validate(p) for p in pages_db]
        
        audit = await db.scalar(select(Audit).where(Audit.id == audit_id))
        
    ctx = AuditContext(
        audit_id=audit_id_str,
        pages=pages_resp,
        site_graph={},
        robots_txt=None,
        sitemap_urls=[],
        industry="saas" # unknown initially
    )
    
    res = detect_industry_service(ctx)
    industry = res["industry"]
    
    async with async_session_factory() as db:
        project = await db.scalar(select(Project).where(Project.id == audit.project_id))
        if project:
            project.industry = industry
            await db.commit()
        
    publish_event_sync(audit_id_str, "audit.industry", {"industry": industry})
    return {"audit_id": audit_id_str, "industry": industry}

@shared_task(bind=True, name="app.workers.pipelines.detect_industry")
def detect_industry(self, audit_id_str: str):
    return asyncio.run(async_detect_industry(audit_id_str))

@shared_task(bind=True, name="app.workers.pipelines.run_agents_chord")
def run_agents_chord(self, result: dict):
    audit_id_str = result["audit_id"]
    industry = result["industry"]
    
    # Map industry to roster (for now all map to technical until more agents exist)
    roster_map = {
        "saas": ["technical"],
        "ecommerce": ["technical"],
        "local_service": ["technical"],
        "publisher": ["technical"],
        "agency": ["technical"]
    }
    roster = roster_map.get(industry, ["technical"])
    
    c = chord(
        group(run_agent.s({"audit_id": audit_id_str, "industry": industry}, agent_id) for agent_id in roster),
        aggregate_findings.s(audit_id_str)
    )
    
    pipeline = chain(
        c,
        compute_score.s(),
        finalize_audit.s()
    )
    
    raise self.replace(pipeline)

async def async_run_agent(agent_id: str, ctx_dict: dict):
    start_time = time.time()
    audit_id_str = ctx_dict["audit_id"]
    audit_id = uuid.UUID(audit_id_str)
    
    publish_event_sync(audit_id_str, "agent.started", {"agent": agent_id})
    
    try:
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
    flat_findings = []
    for r in results:
        flat_findings.extend(r)
        
    if not flat_findings:
        return audit_id_str
        
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
    return asyncio.run(async_aggregate_findings(results, audit_id_str))

async def async_compute_score(audit_id_str: str):
    audit_id = uuid.UUID(audit_id_str)
    
    async with async_session_factory() as db:
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
            # Keep partial status if it was set
            if audit.status != AuditStatusEnum.partial:
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
    
    audit_pipeline = chain(
        crawl_site.s(audit_id_str, url),
        detect_industry.s(),
        run_agents_chord.s()
    )
    audit_pipeline.apply_async()

@shared_task(bind=True, name="app.workers.pipelines.cleanup_s3_keys")
def cleanup_s3_keys(self, keys: list[str]):
    if not keys:
        return
    print(f"S3 Cleanup Stub: Would delete {len(keys)} keys from S3")
    return {"deleted_keys_count": len(keys)}
