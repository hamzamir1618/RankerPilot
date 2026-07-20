import uuid
import datetime
from sqlalchemy import select, desc, case
from celery import shared_task
import asyncio

from app.core.deps import async_session_factory
from app.models.models import Audit, Finding, Project, Page, Organization
from app.reports.generator import generate_pdf_report
from app.integrations.s3 import upload_file_to_s3
from app.core.events import publish_event_sync
from app.core.rate_limit import redis_client

async def async_generate_report(audit_id_str: str):
    audit_id = uuid.UUID(audit_id_str)
    
    async with async_session_factory() as db:
        audit = await db.scalar(select(Audit).where(Audit.id == audit_id))
        if not audit:
            return
            
        project = await db.scalar(select(Project).where(Project.id == audit.project_id))
        org = await db.scalar(select(Organization).where(Organization.id == project.org_id)) if project else None
        
        # Fetch all findings
        stmt = select(Finding).where(Finding.audit_id == audit_id)
        result = await db.execute(stmt)
        findings = result.scalars().all()
        
        # Fetch action plan (top 10 items)
        action_plan_stmt = select(Finding).outerjoin(Page, Finding.page_id == Page.id).where(
            Finding.audit_id == audit_id,
            Finding.status == "fail"
        )
        
        severity_case = case(
            (Finding.severity == "critical", 0),
            (Finding.severity == "high", 1),
            (Finding.severity == "medium", 2),
            (Finding.severity == "low", 3),
            else_=4
        )
        effort_case = case(
            (Finding.effort == "immediate", 0),
            (Finding.effort == "one_week", 1),
            (Finding.effort == "one_month", 2),
            (Finding.effort == "backlog", 3),
            else_=4
        )
        
        action_plan_stmt = action_plan_stmt.order_by(
            severity_case, desc(Page.internal_pagerank), effort_case, Finding.id
        ).limit(10)
        
        action_plan_result = await db.execute(action_plan_stmt)
        action_plan = action_plan_result.scalars().all()
        
        findings_by_category = {}
        for f in findings:
            cat = f.category.value if f.category and hasattr(f.category, 'value') else str(f.category)
            if cat not in findings_by_category:
                findings_by_category[cat] = []
            findings_by_category[cat].append({
                "title": f.title,
                "severity": f.severity.value if f.severity and hasattr(f.severity, 'value') else str(f.severity) if f.severity else "info",
                "evidence": f.evidence,
                "fix": f.fix
            })
            
        context = {
            "project_name": project.name if project else "Unknown Project",
            "domain": project.domain if project else "unknown.com",
            "score": int(audit.score) if audit.score is not None else "N/A",
            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "action_plan": [{
                "title": f.title,
                "severity": f.severity.value if f.severity and hasattr(f.severity, 'value') else str(f.severity) if f.severity else "info",
                "effort": f.effort.value if f.effort and hasattr(f.effort, 'value') else str(f.effort) if f.effort else "unknown",
                "category": f.category.value if f.category and hasattr(f.category, 'value') else str(f.category),
                "fix": f.fix
            } for f in action_plan],
            "findings_by_category": findings_by_category,
            "theme_primary_color": org.theme_primary_color if org else None,
            "theme_accent_color": org.theme_accent_color if org else None,
            "theme_agency_name": org.theme_agency_name if org else None,
            "theme_logo_url": org.theme_logo_url if org else None
        }

    # Generate PDF
    pdf_bytes = generate_pdf_report(context)
    
    # Upload to S3
    object_name = f"reports/{audit_id_str}.pdf"
    url = await upload_file_to_s3(pdf_bytes, object_name)
    
    # Save the report URL in Redis for polling
    await redis_client.setex(f"report_url:{audit_id_str}", 7 * 24 * 3600, url)
            
    publish_event_sync(audit_id_str, "report.ready", {"url": url})
    return url

@shared_task(bind=True, name="app.workers.reports.generate_report_task", queue="reports")
def generate_report_task(self, audit_id_str: str):
    return asyncio.run(async_generate_report(audit_id_str))
