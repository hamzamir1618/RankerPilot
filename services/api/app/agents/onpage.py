import logging
from typing import List

from app.agents.base import BaseAgent, AuditContext
from app.models.models import FindingCategoryEnum

logger = logging.getLogger(__name__)

class OnPageAgent(BaseAgent):
    id = "onpage"
    category = FindingCategoryEnum.onpage
    requires_llm = False

    async def run(self, ctx: AuditContext) -> List[dict]:
        findings = []
        
        titles = {}
        metas = {}
        
        for page in ctx.pages:
            # Only process successfully fetched HTML pages
            if page.status_code != 200:
                continue
                
            # 1. Title/Meta Length
            if page.title:
                t_len = len(page.title)
                if t_len > 60:
                    findings.append({
                        "check_id": "title_too_long",
                        "status": "warn",
                        "severity": "low",
                        "category": self.category.value,
                        "title": f"Title too long ({t_len} chars)",
                        "evidence": {"title": page.title},
                        "page_id": str(page.id)
                    })
                titles.setdefault(page.title.lower(), []).append(page)
            else:
                findings.append({
                    "check_id": "title_missing",
                    "status": "fail",
                    "severity": "high",
                    "category": self.category.value,
                    "title": "Missing Title",
                    "page_id": str(page.id)
                })

            if page.meta_description:
                m_len = len(page.meta_description)
                if m_len > 160:
                    findings.append({
                        "check_id": "meta_too_long",
                        "status": "warn",
                        "severity": "low",
                        "category": self.category.value,
                        "title": f"Meta Description too long ({m_len} chars)",
                        "evidence": {"meta_description": page.meta_description},
                        "page_id": str(page.id)
                    })
                metas.setdefault(page.meta_description.lower(), []).append(page)
            else:
                findings.append({
                    "check_id": "meta_missing",
                    "status": "fail",
                    "severity": "medium",
                    "category": self.category.value,
                    "title": "Missing Meta Description",
                    "page_id": str(page.id)
                })

            # 2. H1 presence/singularity
            h1s = page.h1 or []
            if len(h1s) == 0:
                findings.append({
                    "check_id": "h1_missing",
                    "status": "fail",
                    "severity": "high",
                    "category": self.category.value,
                    "title": "Missing H1 tag",
                    "page_id": str(page.id)
                })
            elif len(h1s) > 1:
                findings.append({
                    "check_id": "h1_multiple",
                    "status": "fail",
                    "severity": "medium",
                    "category": self.category.value,
                    "title": f"Multiple H1 tags ({len(h1s)})",
                    "evidence": {"h1s": h1s},
                    "page_id": str(page.id)
                })
            else:
                findings.append({
                    "check_id": "h1_valid",
                    "status": "pass",
                    "category": self.category.value,
                    "title": "Valid H1 tag",
                    "page_id": str(page.id)
                })

            # 3. Heading hierarchy validity
            if page.headings:
                last_level = 0
                skipped = []
                for h in page.headings:
                    level = h.get("level", 0)
                    if level and last_level > 0 and level > last_level + 1:
                        skipped.append(f"H{last_level} -> H{level}")
                    last_level = level
                
                if skipped:
                    findings.append({
                        "check_id": "heading_hierarchy_skipped",
                        "status": "fail",
                        "severity": "medium",
                        "category": self.category.value,
                        "title": "Skipped heading levels",
                        "evidence": {"skipped": skipped},
                        "page_id": str(page.id)
                    })
                else:
                    findings.append({
                        "check_id": "heading_hierarchy_valid",
                        "status": "pass",
                        "category": self.category.value,
                        "title": "Valid heading hierarchy",
                        "page_id": str(page.id)
                    })

            # 4. Internal anchor-text quality heuristics
            generic_anchors = ["click here", "read more", "learn more", "here", "more"]
            if page.links:
                bad_anchors = []
                for link in page.links:
                    text = link.get("text", "").strip().lower()
                    if text in generic_anchors:
                        bad_anchors.append({"href": link.get("href"), "text": text})
                
                if bad_anchors:
                    findings.append({
                        "check_id": "generic_anchor_text",
                        "status": "fail",
                        "severity": "low",
                        "category": self.category.value,
                        "title": f"Found {len(bad_anchors)} generic anchor texts",
                        "evidence": {"bad_anchors": bad_anchors[:5]},
                        "fix": "Use descriptive anchor text instead of 'click here' or 'read more'.",
                        "page_id": str(page.id)
                    })

        # 5. Cross-page uniqueness
        for title, pages in titles.items():
            if len(pages) > 1:
                findings.append({
                    "check_id": "duplicate_title",
                    "status": "fail",
                    "severity": "medium",
                    "category": self.category.value,
                    "title": f"Duplicate Title across {len(pages)} pages",
                    "evidence": {"title": title, "urls": [p.url for p in pages[:5]]}
                })

        for meta, pages in metas.items():
            if len(pages) > 1:
                findings.append({
                    "check_id": "duplicate_meta",
                    "status": "fail",
                    "severity": "low",
                    "category": self.category.value,
                    "title": f"Duplicate Meta Description across {len(pages)} pages",
                    "evidence": {"meta_description": meta, "urls": [p.url for p in pages[:5]]}
                })
                
        return findings
