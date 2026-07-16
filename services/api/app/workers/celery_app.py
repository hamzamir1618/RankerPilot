from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "rankerpilot",
    broker=str(settings.REDIS_URL),
    backend=str(settings.REDIS_URL),
    include=["app.workers.pipelines", "app.workers.reports"]
)

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
    },
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
)
