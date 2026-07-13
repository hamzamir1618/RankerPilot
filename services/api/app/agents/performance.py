import logging
from typing import List

from app.agents.base import BaseAgent, AuditContext
from app.models.models import FindingCategoryEnum

logger = logging.getLogger(__name__)

class PerformanceAgent(BaseAgent):
    id = "performance"
    category = FindingCategoryEnum.performance
    requires_llm = False

    def _fetch_crux_data_stub(self, url: str) -> dict:
        """Stub for CrUX API field data."""
        return {
            "lcp": "Good",
            "fid": "Good",
            "cls": "Needs Improvement"
        }

    async def run(self, ctx: AuditContext) -> List[dict]:
        findings = []
        
        for page in ctx.pages:
            if page.status_code != 200:
                continue
                
            lab = page.lab_vitals or {}
            
            # 1. Lab Vitals (from CDP Performance.getMetrics)
            js_heap = lab.get("JSHeapUsedSize", 0)
            if js_heap > 50 * 1024 * 1024:  # 50MB
                findings.append({
                    "check_id": "high_js_heap",
                    "status": "fail",
                    "severity": "medium",
                    "category": self.category.value,
                    "title": "High JS Heap Usage",
                    "evidence": {"js_heap_bytes": js_heap},
                    "page_id": str(page.id)
                })

            task_duration = lab.get("TaskDuration", 0)
            if task_duration > 1.0: # 1 second of total main thread blocking time
                findings.append({
                    "check_id": "long_main_thread_tasks",
                    "status": "fail",
                    "severity": "high",
                    "category": self.category.value,
                    "title": "Main thread blocked for too long",
                    "evidence": {"task_duration_seconds": task_duration},
                    "fix": "Minimize main thread work by deferring JS or splitting long tasks.",
                    "page_id": str(page.id)
                })
            else:
                findings.append({
                    "check_id": "task_duration_valid",
                    "status": "pass",
                    "category": self.category.value,
                    "title": "Main thread task duration acceptable",
                    "page_id": str(page.id)
                })

            # 2. CrUX Field Data (Stubbed)
            crux = self._fetch_crux_data_stub(page.url)
            if crux["cls"] != "Good":
                findings.append({
                    "check_id": "crux_cls_issue",
                    "status": "fail", # We'll mark as fail if it needs improvement
                    "severity": "medium",
                    "category": self.category.value,
                    "title": "CrUX: Poor CLS",
                    "evidence": {"crux_cls": crux["cls"]},
                    "page_id": str(page.id)
                })

            # 3. Render-blocking, oversized images, non-optimized fonts
            # Since we don't have the full DOM/Network waterfall here, we create placeholder checks
            # that would be populated by Lighthouse/PageSpeed Insights.
            findings.append({
                "check_id": "render_blocking_resources_check",
                "status": "info",
                "category": self.category.value,
                "title": "Render-Blocking Resources (Awaiting PSI)",
                "evidence": {"note": "Awaiting PSI integration"},
                "page_id": str(page.id)
            })

        return findings
