import asyncio
import uuid
import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings
from app.models.models import Organization, User, Membership, Project, Audit, Page, RoleEnum, AuditStatusEnum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

engine = create_async_engine(str(settings.DATABASE_URL), echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def seed_data():
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
            
            # 2. Create a demo organization
            org_id = uuid.uuid4()
            org = Organization(
                id=org_id,
                name="Demo Corp"
            )
            db.add(org)
            
            # 3. Create membership
            membership = Membership(
                user_id=user_id,
                org_id=org_id,
                role=RoleEnum.owner
            )
            db.add(membership)
            
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
            
            # 5. Create an initial audit placeholder
            audit_id = uuid.uuid4()
            audit = Audit(
                id=audit_id,
                project_id=project_id,
                status=AuditStatusEnum.queued,
                mode="single_page",
                page_limit=1,
                root_url="https://example.com",
                created_by=user_id
            )
            db.add(audit)
            
            await db.commit()
            
            logger.info(f"Successfully seeded database!")
            logger.info(f"User ID: {user_id}")
            logger.info(f"Org ID: {org_id}")
            logger.info(f"Project ID: {project_id}")
            logger.info(f"Audit ID: {audit_id}")
            logger.info(f"Run the following to start the audit pipeline:")
            logger.info(f"  from app.workers.pipelines import start_audit_pipeline")
            logger.info(f"  start_audit_pipeline(uuid.UUID('{audit_id}'), 'https://example.com', 'single_page')")
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to seed data: {e}")

if __name__ == "__main__":
    asyncio.run(seed_data())
