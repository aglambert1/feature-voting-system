"""
Celery application configuration for background task processing.

This module sets up the Celery app with Redis as the message broker
and result backend. Tasks are auto-discovered from the tasks module.

NOTE: On macOS, Celery must be started with --pool=solo or --pool=threads
to avoid SIGABRT crashes. The default 'fork' pool can cause issues on macOS.

Example:
    celery -A app.queue worker --loglevel=info --pool=solo
"""

import sys
from celery import Celery
from app.config import settings

# Configure broker and result backend URLs
broker_url = settings.celery_broker_url or settings.redis_url
result_backend = settings.celery_result_backend or settings.redis_url

# Create Celery application
celery_app = Celery(
    'feature_voting',
    broker=broker_url,
    backend=result_backend,
    include=['app.queue.tasks']
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,

    # Task execution settings
    task_acks_late=True,  # Acknowledge tasks after completion (for reliability)
    task_reject_on_worker_lost=True,  # Requeue tasks if worker dies
    task_track_started=True,  # Track when tasks start executing

    # Result settings
    result_expires=3600,  # Results expire after 1 hour
    result_extended=True,  # Store task name and args in result

    # Broker connection settings
    broker_connection_retry_on_startup=True,  # Retry connection on startup
    broker_connection_max_retries=10,  # Max retries for broker connection
    broker_pool_limit=None,  # Disable connection pooling (each connection is new)
    broker_connection_retry=True,  # Retry failed connections
    broker_connection_timeout=10,  # Connection timeout in seconds

    # Task timeout settings
    task_soft_time_limit=900,   # Default: 15 min soft limit (raises SoftTimeLimitExceeded)
    task_time_limit=1500,       # Default: 25 min hard kill (backstop if soft limit fails)

    # Worker settings
    worker_prefetch_multiplier=1,  # One task at a time per worker for fairness
    worker_concurrency=1 if sys.platform == 'darwin' else 4,  # Solo on macOS

    # Task routing (for future use with dedicated queues)
    task_default_queue='default',
    task_queues={
        'default': {},
        'product_analysis': {},
        'competitor_research': {},
        'feature_extraction': {},
        'idea_generation': {},
    },

    # Beat schedule
    beat_schedule={
        # Legacy scheduled monitoring (Phase 4)
        'scheduled-monitoring-daily': {
            'task': 'app.queue.tasks.scheduled_monitoring_task',
            'schedule': 86400.0,  # Run once per day (24 * 60 * 60 seconds)
            # Note: The task checks each product's individual schedule
            # (daily, weekly, biweekly, monthly) and only runs monitoring
            # for products that are due based on their configuration.
        },
        # Agent-centric scheduling - runs hourly to check what's due
        'check-scheduled-agent-tasks': {
            'task': 'app.queue.tasks.check_scheduled_tasks',
            'schedule': 3600.0,  # Run every hour
            # Checks CompetitiveAgentConfig for each product and queues work if due:
            # - Product analysis (if scheduled mode and next_run <= now)
            # - Competitor discovery (if scheduled mode and next_run <= now)
            # - Deep analysis (if scheduled mode and next_run <= now)
        },
    },
)


def get_celery_app() -> Celery:
    """Return the configured Celery app instance."""
    return celery_app
