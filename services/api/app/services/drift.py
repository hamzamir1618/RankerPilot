import uuid
import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.models.models import DriftEvent, Baseline, Page

DRIFT_RULES = [
    "1. Title Changed",
    "2. Title Removed",
    "3. Meta Desc Changed",
    "4. Meta Desc Removed",
    "5. Canonical Changed",
    "6. Canonical Removed",
    "7. H1 Changed",
    "8. Status Code Changed (non-200)",
    "9. Word Count Dropped (>20%)",
    "10. Word Count Spiked (>20%)",
    "11. JSON-LD Removed",
    "12. Noindex Added",
    "13. Disallow Added",
    "14. Schema Type Changed",
    "15. Lab Vitals Dropped",
    "16. Alt Tags Removed",
    "17. Internal Pagerank Dropped"
]

def check_drift(baseline: dict, current: dict, project_id: uuid.UUID, page_url: str) -> List[DriftEvent]:
    events = []
    now = datetime.datetime.now(datetime.timezone.utc)
    
    def add_event(rule_idx: int, before: dict, after: dict):
        events.append(DriftEvent(
            id=uuid.uuid4(),
            project_id=project_id,
            page_url=page_url,
            rule=DRIFT_RULES[rule_idx - 1],
            before=before,
            after=after,
            detected_at=now,
            acknowledged=False
        ))

    # 1 & 2: Title
    if baseline.get("title") and not current.get("title"):
        add_event(2, {"title": baseline.get("title")}, {"title": None})
    elif baseline.get("title") != current.get("title"):
        add_event(1, {"title": baseline.get("title")}, {"title": current.get("title")})
        
    # 3 & 4: Meta Desc
    if baseline.get("meta_description") and not current.get("meta_description"):
        add_event(4, {"meta": baseline.get("meta_description")}, {"meta": None})
    elif baseline.get("meta_description") != current.get("meta_description"):
        add_event(3, {"meta": baseline.get("meta_description")}, {"meta": current.get("meta_description")})
        
    # 5 & 6: Canonical
    def get_canonical(page_data):
        links = page_data.get("links", [])
        if not links:
            return None
        for link in links:
            if isinstance(link, dict) and link.get("rel") == "canonical":
                return link.get("href")
        return None
        
    b_canon = get_canonical(baseline)
    c_canon = get_canonical(current)
    if b_canon and not c_canon:
        add_event(6, {"canonical": b_canon}, {"canonical": None})
    elif b_canon != c_canon:
        add_event(5, {"canonical": b_canon}, {"canonical": c_canon})
        
    # 7: H1 Changed
    b_h1 = baseline.get("h1") or []
    c_h1 = current.get("h1") or []
    if set(b_h1) != set(c_h1):
        add_event(7, {"h1": b_h1}, {"h1": c_h1})
        
    # 8: Status code non-200
    b_status = baseline.get("status_code", 200)
    c_status = current.get("status_code", 200)
    if b_status == 200 and c_status != 200:
        add_event(8, {"status": b_status}, {"status": c_status})
        
    # 9 & 10: Word count
    b_words = baseline.get("word_count") or 0
    c_words = current.get("word_count") or 0
    if b_words > 0:
        if c_words < b_words * 0.8:
            add_event(9, {"words": b_words}, {"words": c_words})
        elif c_words > b_words * 1.2:
            add_event(10, {"words": b_words}, {"words": c_words})
            
    # 11: JSON-LD removed
    b_jsonld = baseline.get("json_ld") or []
    c_jsonld = current.get("json_ld") or []
    if b_jsonld and not c_jsonld:
        add_event(11, {"json_ld_count": len(b_jsonld)}, {"json_ld_count": 0})
        
    # 12 & 13: Mock check
    if current.get("_meta_robots_noindex_added"):
        add_event(12, {"noindex": False}, {"noindex": True})
    if current.get("_robots_disallow_added"):
        add_event(13, {"disallow": False}, {"disallow": True})
        
    # 14: Schema type changed
    def get_schema_types(jld):
        types = set()
        for item in (jld or []):
            if isinstance(item, dict) and "@type" in item:
                types.add(item["@type"])
        return types
    b_types = get_schema_types(baseline.get("json_ld"))
    c_types = get_schema_types(current.get("json_ld"))
    if b_types != c_types and b_types:
        add_event(14, {"schema_types": list(b_types)}, {"schema_types": list(c_types)})
        
    # 15: Lab Vitals dropped
    b_vitals = baseline.get("lab_vitals") or {}
    c_vitals = current.get("lab_vitals") or {}
    b_score = b_vitals.get("performance_score", 100)
    c_score = c_vitals.get("performance_score", 100)
    if c_score < b_score * 0.8:
        add_event(15, {"score": b_score}, {"score": c_score})
        
    # 16: Alt tags removed
    def missing_alt_count(images):
        return sum(1 for img in (images or []) if isinstance(img, dict) and not img.get("alt"))
    b_missing = missing_alt_count(baseline.get("images"))
    c_missing = missing_alt_count(current.get("images"))
    if c_missing > b_missing:
        add_event(16, {"missing_alts": b_missing}, {"missing_alts": c_missing})
        
    # 17: Pagerank dropped
    b_pr = float(baseline.get("internal_pagerank") or 0.0)
    c_pr = float(current.get("internal_pagerank") or 0.0)
    if c_pr < b_pr * 0.5 and b_pr > 0.01:
        add_event(17, {"pagerank": b_pr}, {"pagerank": c_pr})
        
    return events

async def detect_and_store_drift(db: AsyncSession, project_id: uuid.UUID, pages: List[Page]):
    if not pages:
        return []
    
    urls = [p.url for p in pages]
    
    stmt = select(Baseline).where(
        Baseline.project_id == project_id,
        Baseline.page_url.in_(urls)
    ).order_by(Baseline.page_url, Baseline.created_at.desc()).distinct(Baseline.page_url)
    
    baselines_result = await db.execute(stmt)
    baselines = {b.page_url: b.snapshot for b in baselines_result.scalars().all()}
    
    all_events = []
    
    for page in pages:
        if page.url in baselines:
            page_dict = {
                "title": page.title,
                "meta_description": page.meta_description,
                "h1": page.h1,
                "word_count": page.word_count,
                "status_code": page.status_code,
                "json_ld": page.json_ld,
                "lab_vitals": page.lab_vitals,
                "images": page.images,
                "links": page.links,
                "internal_pagerank": float(page.internal_pagerank) if page.internal_pagerank else 0.0
            }
            events = check_drift(baselines[page.url], page_dict, project_id, page.url)
            all_events.extend(events)
            
    if all_events:
        db.add_all(all_events)
        await db.commit()
        # Stub email dispatch
        print(f"STUB: Emailing {len(all_events)} drift alerts for project {project_id}")
        
    return all_events
