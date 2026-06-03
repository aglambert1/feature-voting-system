"""Celery beat-driven scheduler tasks.

Houses ``check_scheduled_tasks`` (the master scheduler that fires daily via
Celery Beat) and the ``_calculate_next_run`` helper that maps cadence strings
to next-run datetimes.

The scheduler queues product-analysis, competitor-discovery, and V2 competitive
analysis jobs whenever each product's CompetitiveAgentConfig says they're due.
"""

from typing import Dict, Any
from celery import shared_task
from datetime import datetime, timedelta, timezone

from app.models.queue import JobType
from app.services.queue_service import QueueService
from app.queue.helpers import get_db
from app.queue.product_tasks import analyze_product_task
from app.queue.competitor_tasks import (
    discover_competitors_task,
    run_competitive_analysis_v2,
)


# ============================================================================
# Scheduled Execution Tasks (Chunk 7)
# ============================================================================

def _calculate_next_run(schedule: str) -> datetime:
    """
    Calculate the next run time based on schedule frequency.

    Args:
        schedule: One of 'daily', 'weekly', 'biweekly', 'monthly'

    Returns:
        Next run datetime (UTC)
    """
    now = datetime.now(timezone.utc)
    if schedule == 'daily':
        return now + timedelta(days=1)
    elif schedule == 'weekly':
        return now + timedelta(weeks=1)
    elif schedule == 'biweekly':
        return now + timedelta(weeks=2)
    elif schedule == 'monthly':
        return now + timedelta(days=30)
    else:
        # Default to weekly
        return now + timedelta(weeks=1)


@shared_task(bind=True, name='app.queue.scheduled_tasks.check_scheduled_tasks', soft_time_limit=300)
def check_scheduled_tasks(self) -> Dict[str, Any]:
    """
    Master scheduler task - runs daily via Celery Beat.

    Checks CompetitiveAgentConfig for each product and queues work if due:
    - Product analysis (if scheduled mode and next_run <= now)
    - Competitor discovery (if scheduled mode and next_run <= now)
    - V2 competitive analysis (if scheduled mode and next_run <= now)

    Returns:
        Dictionary with queued jobs summary
    """
    from app.models.competitive_agent import CompetitiveAgentConfig, AgentMode

    db = None
    try:
        db = get_db()
        queue_service = QueueService(db)
        now = datetime.now(timezone.utc)

        def _as_utc(dt: datetime) -> datetime:
            """Treat naive datetimes as UTC (SQLite strips tzinfo on read)."""
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

        jobs_queued = {
            'product_analysis': [],
            'competitor_discovery': [],
            'deep_analysis': [],
        }

        # Get all enabled configs
        configs = db.query(CompetitiveAgentConfig).filter(
            CompetitiveAgentConfig.enabled == True
        ).all()

        print(f"[check_scheduled_tasks] Checking {len(configs)} products for scheduled tasks...")

        for config in configs:
            try:
                product_id = config.product_id

                # Check Product Analysis
                if (config.product_analysis_mode == AgentMode.SCHEDULED
                        and config.product_analysis_next_run
                        and _as_utc(config.product_analysis_next_run) <= now):
                    print(f"[check_scheduled_tasks] Product {product_id}: Product analysis due")
                    job = queue_service.create_job(
                        job_type=JobType.PRODUCT_ANALYSIS,
                        input_data={'product_id': product_id, 'scheduled': True},
                        product_id=product_id,
                        user_id=None  # System scheduled
                    )
                    db.commit()

                    # Queue the task
                    analyze_product_task.delay(job.id)

                    # Update next run time
                    config.product_analysis_last_run = now
                    config.product_analysis_next_run = _calculate_next_run(
                        config.product_analysis_schedule or 'weekly'
                    )
                    db.commit()

                    jobs_queued['product_analysis'].append({
                        'product_id': product_id,
                        'job_id': job.id
                    })

                # Check Competitor Discovery
                if (config.competitor_discovery_mode == AgentMode.SCHEDULED
                        and config.competitor_discovery_next_run
                        and _as_utc(config.competitor_discovery_next_run) <= now):
                    print(f"[check_scheduled_tasks] Product {product_id}: Competitor discovery due")
                    job = queue_service.create_job(
                        job_type=JobType.COMPETITOR_DISCOVERY,
                        input_data={'product_id': product_id, 'scheduled': True},
                        product_id=product_id,
                        user_id=None
                    )
                    db.commit()

                    discover_competitors_task.delay(job.id)

                    config.competitor_discovery_last_run = now
                    config.competitor_discovery_next_run = _calculate_next_run(
                        config.competitor_discovery_schedule or 'weekly'
                    )
                    db.commit()

                    jobs_queued['competitor_discovery'].append({
                        'product_id': product_id,
                        'job_id': job.id
                    })

                # Check Competitive Analysis (V2 functional audit + landscape synthesis)
                if (config.deep_analysis_mode == AgentMode.SCHEDULED
                        and config.deep_analysis_next_run
                        and _as_utc(config.deep_analysis_next_run) <= now):
                    print(f"[check_scheduled_tasks] Product {product_id}: V2 competitive analysis due")
                    job = queue_service.create_job(
                        job_type=JobType.SCHEDULED_DEEP_ANALYSIS,
                        input_data={'product_id': product_id, 'scheduled': True},
                        product_id=product_id,
                        user_id=None
                    )
                    db.commit()

                    run_competitive_analysis_v2.delay(job.id)

                    config.deep_analysis_last_run = now
                    config.deep_analysis_next_run = _calculate_next_run(
                        config.deep_analysis_schedule or 'weekly'
                    )
                    db.commit()

                    jobs_queued['deep_analysis'].append({
                        'product_id': product_id,
                        'job_id': job.id
                    })

            except Exception as e:
                print(f"[check_scheduled_tasks] Error processing product {config.product_id}: {e}")
                continue

        total_queued = sum(len(v) for v in jobs_queued.values())
        print(f"[check_scheduled_tasks] Queued {total_queued} jobs across {len(configs)} products")

        return {
            'products_checked': len(configs),
            'jobs_queued': jobs_queued,
            'total_jobs': total_queued,
            'checked_at': now.isoformat()
        }

    except Exception as e:
        error_msg = str(e)
        print(f"[check_scheduled_tasks] Error: {error_msg}")
        raise

    finally:
        if db:
            db.close()
