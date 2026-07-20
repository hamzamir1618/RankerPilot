from celery import Celery
from app.core.config import settings
from celery.schedules import crontab

celery_app = Celery(
    "rankerpilot",
    broker=str(settings.REDIS_URL),
    backend=str(settings.REDIS_URL),
    include=[
        "app.workers.pipelines", 
        "app.workers.reports",
        "app.workers.beat_schedule",
        "app.workers.rank_tracking"
    ]
)

celery_app.conf.beat_schedule = {
    'dispatch-audits-hourly': {
        'task': 'app.workers.beat_schedule.dispatch_audits',
        'schedule': crontab(minute='0'), # Run at top of every hour
    },
    'dispatch-rank-tracking-hourly': {
        'task': 'app.workers.beat_schedule.dispatch_rank_tracking',
        'schedule': crontab(minute='5'), # Run at 5 past the hour
    },
    'maintain-partitions-monthly': {
        'task': 'app.workers.beat_schedule.maintain_partitions',
        'schedule': crontab(day_of_month='1', hour='0', minute='0'), 
    },
}

celery_app.conf.update(
    task_routes={
        "app.workers.pipelines.crawl_site": {"queue": "crawl"},
        "app.workers.pipelines.run_agent": {"queue": "agents"},
        "app.workers.pipelines.detect_industry": {"queue": "agents"},
        "app.workers.pipelines.run_agents_chord": {"queue": "agents"},
        "app.workers.pipelines.aggregate_findings": {"queue": "reports"},
        "app.workers.pipelines.compute_score": {"queue": "reports"},
        "app.workers.pipelines.finalize_audit": {"queue": "reports"},
        "app.workers.reports.generate_report_task": {"queue": "reports"},
        "app.workers.beat_schedule.dispatch_audits": {"queue": "beat"},
        "app.workers.beat_schedule.dispatch_rank_tracking": {"queue": "beat"},
        "app.workers.beat_schedule.maintain_partitions": {"queue": "beat"},
        "app.workers.rank_tracking.run_rank_tracking_for_project": {"queue": "crawl"},
    },
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
)
