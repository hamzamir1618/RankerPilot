import uuid
import datetime
import asyncio
import hashlib
from celery import shared_task
from sqlalchemy import select

from app.core.deps import async_session_factory
from app.models.models import ProjectSchedule, AuditModeEnum, Project, Audit, AuditStatusEnum
from app.workers.pipelines import start_audit_pipeline
from app.workers.rank_tracking import run_rank_tracking_for_project

def get_jitter_hour(project_id: uuid.UUID, cadence: str) -> int:
    """
    Deterministically jitter start times per project based on ID to spread out
    API quota usage across the whole week/month.
    """
    modulus = 168 if cadence == 'weekly' else 720
    # Use deterministic hash (Python's built-in hash() is randomized per run)
    h = int(hashlib.md5(project_id.bytes).hexdigest()[:8], 16)
    return h % modulus

async def async_dispatch_audits():
    now = datetime.datetime.now(datetime.timezone.utc)
    current_hour_of_week = now.weekday() * 24 + now.hour
    # Approximation for monthly: just map day 1-30 to hours 0-719
    current_hour_of_month = (min(now.day, 30) - 1) * 24 + now.hour
    
    async with async_session_factory() as db:
        result = await db.execute(select(ProjectSchedule))
        schedules = result.scalars().all()
        
        for sched in schedules:
            if not sched.audit_cadence:
                continue
                
            expected_hour = get_jitter_hour(sched.project_id, sched.audit_cadence)
            
            is_due = False
            if sched.audit_cadence == 'weekly' and current_hour_of_week == expected_hour:
                is_due = True
            elif sched.audit_cadence == 'monthly' and current_hour_of_month == expected_hour:
                is_due = True
                
            if is_due:
                project = await db.scalar(select(Project).where(Project.id == sched.project_id))
                if project:
                    audit = Audit(
                        id=uuid.uuid4(),
                        project_id=project.id,
                        status=AuditStatusEnum.queued,
                        mode=AuditModeEnum.full,
                        page_limit=50, # Arbitrary default for scheduled
                        root_url=f"https://{project.domain}",
                        created_by=None # Scheduled system audit
                    )
                    db.add(audit)
                    await db.commit()
                    
                    start_audit_pipeline(audit.id, audit.root_url, "full")

@shared_task(bind=True, name="app.workers.beat_schedule.dispatch_audits")
def dispatch_audits(self):
    asyncio.run(async_dispatch_audits())


async def async_dispatch_rank_tracking():
    now = datetime.datetime.now(datetime.timezone.utc)
    current_hour_of_week = now.weekday() * 24 + now.hour
    current_hour_of_month = (min(now.day, 30) - 1) * 24 + now.hour
    
    async with async_session_factory() as db:
        result = await db.execute(select(ProjectSchedule))
        schedules = result.scalars().all()
        
        for sched in schedules:
            if not sched.rank_cadence:
                continue
                
            expected_hour = get_jitter_hour(sched.project_id, sched.rank_cadence)
            
            is_due = False
            if sched.rank_cadence == 'weekly' and current_hour_of_week == expected_hour:
                is_due = True
            elif sched.rank_cadence == 'monthly' and current_hour_of_month == expected_hour:
                is_due = True
                
            if is_due:
                # Dispatch the rank tracking workflow for this project
                # (to be implemented in rank_tracking.py)
                run_rank_tracking_for_project.delay(str(sched.project_id))

@shared_task(bind=True, name="app.workers.beat_schedule.dispatch_rank_tracking")
def dispatch_rank_tracking(self):
    asyncio.run(async_dispatch_rank_tracking())

@shared_task(bind=True, name="app.workers.beat_schedule.maintain_partitions")
def maintain_partitions(self):
    from app.core.db_partitions import create_future_partitions
    async def async_maintain_partitions():
        async with async_session_factory() as db:
            await create_future_partitions(db, "rank_snapshots", 3)
    asyncio.run(async_maintain_partitions())
