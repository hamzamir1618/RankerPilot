import logging
from typing import List

from app.agents.base import BaseAgent, AuditContext
from app.models.models import FindingCategoryEnum

logger = logging.getLogger(__name__)

class ImagesAgent(BaseAgent):
    id = "images"
    category = FindingCategoryEnum.images
    requires_llm = False

    async def run(self, ctx: AuditContext) -> List[dict]:
        findings = []
        
        for page in ctx.pages:
            if page.status_code != 200 or not page.images:
                continue
                
            total_images = len(page.images)
            missing_alt = []
            legacy_formats = []
            missing_dimensions = []
            missing_lazy = []
            
            for i, img in enumerate(page.images):
                src = img.get('src', '')
                alt = img.get('alt')
                width = img.get('width')
                height = img.get('height')
                loading = img.get('loading')
                
                # We skip tiny tracking pixels or base64 usually, but here we check data: URLs
                if src.startswith("data:"):
                    continue
                    
                # 1. Alt text
                if alt is None or alt.strip() == "":
                    missing_alt.append(src)
                    
                # 2. Next-gen format
                if src.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    legacy_formats.append(src)
                    
                # 3. Explicit dimensions
                if not width or not height:
                    missing_dimensions.append(src)
                    
                # 4. Lazy loading (below fold heuristic: assume images after first 3 should be lazy)
                if i > 2 and loading != "lazy":
                    missing_lazy.append(src)
                    
            if missing_alt:
                coverage = int((total_images - len(missing_alt)) / total_images * 100)
                findings.append({
                    "check_id": "missing_alt_text",
                    "status": "fail",
                    "severity": "medium",
                    "category": self.category.value,
                    "title": f"Missing Alt Text ({coverage}% coverage)",
                    "evidence": {"missing_alt_urls": missing_alt[:5]},
                    "fix": "Add descriptive alt text to all non-decorative images.",
                    "page_id": str(page.id)
                })
            else:
                findings.append({
                    "check_id": "missing_alt_text",
                    "status": "pass",
                    "category": self.category.value,
                    "title": "All images have alt text",
                    "page_id": str(page.id)
                })

            if legacy_formats:
                findings.append({
                    "check_id": "legacy_image_formats",
                    "status": "warn",
                    "severity": "low",
                    "category": self.category.value,
                    "title": f"Using legacy image formats ({len(legacy_formats)} images)",
                    "evidence": {"legacy_format_urls": legacy_formats[:5]},
                    "fix": "Serve images in next-gen formats like WebP or AVIF.",
                    "page_id": str(page.id)
                })

            if missing_dimensions:
                findings.append({
                    "check_id": "missing_image_dimensions",
                    "status": "fail",
                    "severity": "medium",
                    "category": self.category.value,
                    "title": f"Missing width/height attributes ({len(missing_dimensions)} images)",
                    "evidence": {"urls": missing_dimensions[:5]},
                    "fix": "Add explicit width and height attributes to prevent CLS.",
                    "page_id": str(page.id)
                })

            if missing_lazy:
                findings.append({
                    "check_id": "missing_lazy_loading",
                    "status": "warn",
                    "severity": "low",
                    "category": self.category.value,
                    "title": f"Missing lazy loading on below-fold images ({len(missing_lazy)} images)",
                    "evidence": {"urls": missing_lazy[:5]},
                    "fix": "Add loading=\"lazy\" to images below the fold.",
                    "page_id": str(page.id)
                })

        return findings
