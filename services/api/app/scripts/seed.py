import asyncio
import uuid
import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings
from datetime import datetime, timezone
from app.models.models import Organization, User, Membership, Project, Audit, Page, Finding, RoleEnum, AuditStatusEnum, FindingStatusEnum
from app.models.base import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

engine = create_async_engine(str(settings.DATABASE_URL), echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def seed_data():
    if settings.ENV != "dev":
        raise RuntimeError("Seed script can only be run in the 'dev' environment to prevent accidental data overwriting in production.")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        try:
            logger.info("Seeding demo organization, user, and project...")
            
            # 1. Create a demo user
            user_id = uuid.uuid4()
            user = User(
                id=user_id,
                email="demo@rankerpilot.com",
                google_sub="demo_sub_123"
            )
            db.add(user)
            await db.flush()
            
            # 2. Create a demo organization
            org_id = uuid.uuid4()
            org = Organization(
                id=org_id,
                name="Demo Corp"
            )
            db.add(org)
            await db.flush()
            
            # 3. Create membership
            membership = Membership(
                user_id=user_id,
                org_id=org_id,
                role=RoleEnum.owner
            )
            db.add(membership)
            await db.flush()
            
            # 4. Create a project
            project_id = uuid.uuid4()
            project = Project(
                id=project_id,
                org_id=org_id,
                domain="example.com",
                name="Example.com Marketing Site",
                industry="saas"
            )
            db.add(project)
            await db.flush()
            
            # 5. Create a completed audit
            audit_id = uuid.uuid4()
            audit = Audit(
                id=audit_id,
                project_id=project_id,
                status=AuditStatusEnum.done,
                mode="single_page",
                page_limit=1,
                root_url="https://example.com",
                score=85.0,
                category_scores={"technical": 85.0},
                started_at=datetime.now(timezone.utc).replace(tzinfo=None),
                finished_at=datetime.now(timezone.utc).replace(tzinfo=None),
                created_by=user_id
            )
            db.add(audit)
            await db.flush()
            
            # 6. Create a page for the findings
            page_id = uuid.uuid4()
            page = Page(
                id=page_id,
                audit_id=audit_id,
                url="https://example.com/pricing",
                status_code=200,
                rendered=False,
                title="Pricing | Example",
                word_count=450
            )
            db.add(page)
            await db.flush()
            
            # 7. Create dummy findings from technical agent
            findings_data = [
                {
                    "check_id": "canonical_tag",
                    "status": FindingStatusEnum.pass_,
                    "severity": None,
                    "category": "technical",
                    "title": "Canonical Tag is Present and Valid",
                    "evidence": {"found": "https://example.com/pricing"},
                    "fix": None,
                    "fix_code": None,
                    "effort": None
                },
                {
                    "check_id": "redirect_chain",
                    "status": FindingStatusEnum.pass_,
                    "severity": None,
                    "category": "technical",
                    "title": "No Redirect Chains Detected",
                    "evidence": {"chain_length": 0},
                    "fix": None,
                    "fix_code": None,
                    "effort": None
                },
                {
                    "check_id": "mixed_content",
                    "status": FindingStatusEnum.fail,
                    "severity": "high",
                    "category": "technical",
                    "title": "Mixed Content: HTTP resource on HTTPS page",
                    "evidence": {"insecure_urls": ["http://example.com/assets/logo.png"]},
                    "fix": "Update the resource URL to use HTTPS.",
                    "fix_code": '<img src="https://example.com/assets/logo.png" />',
                    "effort": "low"
                },
                {
                    "check_id": "mobile_viewport",
                    "status": FindingStatusEnum.fail,
                    "severity": "high",
                    "category": "technical",
                    "title": "Missing Mobile Viewport Meta Tag",
                    "evidence": {},
                    "fix": "Add the viewport meta tag to the <head> of your document.",
                    "fix_code": '<meta name="viewport" content="width=device-width, initial-scale=1">',
                    "effort": "low"
                },
                {
                    "check_id": "noindex_conflict",
                    "status": FindingStatusEnum.warn,
                    "severity": "medium",
                    "category": "technical",
                    "title": "Noindex tag found but page is listed in sitemap",
                    "evidence": {"sitemap": "https://example.com/sitemap.xml", "robots": "noindex"},
                    "fix": "Remove the page from the sitemap or remove the noindex tag if the page should be indexed.",
                    "fix_code": None,
                    "effort": "medium"
                }
            ]
            
            for f in findings_data:
                db.add(Finding(
                    id=uuid.uuid4(),
                    audit_id=audit_id,
                    page_id=page_id,
                    agent="technical",
                    check_id=f["check_id"],
                    status=f["status"],
                    severity=f["severity"],
                    category=f["category"],
                    title=f["title"],
                    evidence=f["evidence"],
                    fix=f["fix"],
                    fix_code=f["fix_code"],
                    effort=f["effort"]
                ))
            
            await db.commit()
            
            logger.info("Successfully seeded database!")
            logger.info(f"User ID: {user_id}")
            logger.info(f"Org ID: {org_id}")
            logger.info(f"Project ID: {project_id}")
            logger.info(f"Audit ID: {audit_id}")
            logger.info("Run the following to start the audit pipeline:")
            logger.info("  from app.workers.pipelines import start_audit_pipeline")
            logger.info(f"  start_audit_pipeline(uuid.UUID('{audit_id}'), 'https://example.com', 'single_page')")
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to seed data: {e}")

if __name__ == "__main__":
    asyncio.run(seed_data())
