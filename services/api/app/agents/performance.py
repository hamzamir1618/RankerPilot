import logging
from typing import List

from app.agents.base import BaseAgent, AuditContext
from app.models.models import FindingCategoryEnum
from app.integrations.google_psi import fetch_psi_data
from app.integrations.google_crux import fetch_crux_data
from app.utils.clustering import jaccard_similarity

logger = logging.getLogger(__name__)

class PerformanceAgent(BaseAgent):
    id = "performance"
    category = FindingCategoryEnum.performance
    requires_llm = False

    async def run(self, ctx: AuditContext) -> List[dict]:
        findings = []
        
        # 1. Select representative templates
        pages_to_test = []
        root_url = ctx.audit.root_url
        root_page = next((p for p in ctx.pages if p.url == root_url), None)
        if root_page and root_page.status_code == 200:
            pages_to_test.append(root_page)
            
        other_pages = [p for p in ctx.pages if p.status_code == 200 and p.url != root_url and p.content_text]
        clusters = []
        for p in other_pages:
            found_cluster = False
            for cluster in clusters:
                if jaccard_similarity(p.content_text, cluster[0].content_text) > 0.8:
                    cluster.append(p)
                    found_cluster = True
                    break
            if not found_cluster:
                clusters.append([p])
                
        clusters.sort(key=len, reverse=True)
        # Add up to 2 representative templates
        for cluster in clusters[:2]:
            if cluster[0] not in pages_to_test:
                pages_to_test.append(cluster[0])
        
        for page in pages_to_test:
            # Lab Vitals from Crawler
            lab = page.lab_vitals or {}
            js_heap = lab.get("JSHeapUsedSize", 0)
            if js_heap > 50 * 1024 * 1024:  # 50MB
                findings.append({
                    "check_id": "high_js_heap",
                    "status": "fail",
                    "severity": "medium",
                    "category": self.category.value,
                    "title": "High JS Heap Usage",
                    "evidence": {"lab_metrics": {"js_heap_bytes": js_heap}},
                    "page_id": str(page.id)
                })

            task_duration = lab.get("TaskDuration", 0)
            if task_duration > 1.0:
                findings.append({
                    "check_id": "long_main_thread_tasks",
                    "status": "fail",
                    "severity": "high",
                    "category": self.category.value,
                    "title": "Main thread blocked for too long",
                    "evidence": {"lab_metrics": {"task_duration_seconds": task_duration}},
                    "fix": "Minimize main thread work by deferring JS or splitting long tasks.",
                    "page_id": str(page.id)
                })

            # Fetch PSI Lab Data
            psi = await fetch_psi_data(page.url, "mobile")
            if psi:
                lh = psi.get("lighthouseResult", {})
                audits = lh.get("audits", {})
                
                rb = audits.get("render-blocking-resources", {})
                if rb.get("score", 1) < 0.9:
                    findings.append({
                        "check_id": "render_blocking_resources_psi",
                        "status": "fail",
                        "severity": "high",
                        "category": self.category.value,
                        "title": "Render-Blocking Resources",
                        "evidence": {"lab_metrics": {"wastedMs": rb.get("numericValue")}},
                        "page_id": str(page.id)
                    })
                
                lcp = audits.get("largest-contentful-paint", {})
                if lcp.get("score", 1) < 0.9:
                    findings.append({
                        "check_id": "psi_poor_lcp",
                        "status": "fail",
                        "severity": "high",
                        "category": self.category.value,
                        "title": "Poor LCP (Lab Data)",
                        "evidence": {"lab_metrics": {"lcp_ms": lcp.get("numericValue")}},
                        "page_id": str(page.id)
                    })

            # Fetch CrUX Field Data
            crux = await fetch_crux_data(url=page.url)
            if crux and "record" in crux:
                metrics = crux["record"].get("metrics", {})
                
                cls = metrics.get("cumulative_layout_shift", {})
                cls_p75 = cls.get("percentiles", {}).get("p75")
                if cls_p75 and float(cls_p75) > 0.1:
                    findings.append({
                        "check_id": "crux_cls_issue",
                        "status": "fail",
                        "severity": "medium",
                        "category": self.category.value,
                        "title": "Poor CLS (Field Data)",
                        "evidence": {"field_metrics": {"p75_cls": cls_p75}},
                        "page_id": str(page.id)
                    })
                    
                lcp_field = metrics.get("largest_contentful_paint", {})
                lcp_p75 = lcp_field.get("percentiles", {}).get("p75")
                if lcp_p75 and float(lcp_p75) > 2500:
                    findings.append({
                        "check_id": "crux_lcp_issue",
                        "status": "fail",
                        "severity": "high",
                        "category": self.category.value,
                        "title": "Poor LCP (Field Data)",
                        "evidence": {"field_metrics": {"p75_lcp_ms": lcp_p75}},
                        "page_id": str(page.id)
                    })

        return findings
