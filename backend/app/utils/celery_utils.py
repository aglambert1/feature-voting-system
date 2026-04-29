"""
Thread-safe Celery task dispatch utilities.

This module provides a thread-safe way to dispatch Celery tasks from FastAPI endpoints.

BACKGROUND:
FastAPI runs synchronous endpoint functions in a thread pool (using anyio).
When a @shared_task decorated function is imported and called via .delay() in such
a thread, Celery may bind the task to a default unconfigured app (with broker=None)
instead of our properly configured celery_app.

This happens because @shared_task uses "current app" semantics, and in a new thread
that hasn't properly initialized the Celery context, it falls back to a default app.

SOLUTION:
Use celery_app.send_task() instead of task.delay(). This explicitly uses our
configured Celery app instance regardless of thread context.
"""

from app.queue import celery_app


# After the tasks.py split (PR: split-tasks-py), tasks live across multiple
# `app.queue.<group>_tasks` modules. Callers still pass an unqualified short
# name; this map resolves that to the full registered Celery task name. Keep
# this in sync with the @shared_task(name=...) declarations in each module.
_TASK_NAME_MAP = {
    # product_tasks
    "analyze_product_task": "app.queue.product_tasks.analyze_product_task",
    "health_check": "app.queue.product_tasks.health_check",
    # competitor_tasks
    "discover_competitors_task": "app.queue.competitor_tasks.discover_competitors_task",
    "functional_audit_task": "app.queue.competitor_tasks.functional_audit_task",
    "aggregate_functional_audits_v2": "app.queue.competitor_tasks.aggregate_functional_audits_v2",
    "run_competitive_analysis_v2": "app.queue.competitor_tasks.run_competitive_analysis_v2",
    # triage_tasks
    "triage_idea_task": "app.queue.triage_tasks.triage_idea_task",
    "submit_and_triage_idea_task": "app.queue.triage_tasks.submit_and_triage_idea_task",
    # scheduled_tasks
    "check_scheduled_tasks": "app.queue.scheduled_tasks.check_scheduled_tasks",
    # internal_tasks
    "internal_discovery_task": "app.queue.internal_tasks.internal_discovery_task",
    "activity_insight_task": "app.queue.internal_tasks.activity_insight_task",
    # jtbd_tasks
    "extract_job_map_task": "app.queue.jtbd_tasks.extract_job_map_task",
    # synthesis_tasks
    "unified_synthesis_task": "app.queue.synthesis_tasks.unified_synthesis_task",
    "resume_unified_synthesis_task": "app.queue.synthesis_tasks.resume_unified_synthesis_task",
}

# Module-path prefixes that callers must NOT prepend themselves. Prior incident:
# an endpoint passed the full-prefixed name, the wrapper concatenated another
# prefix, and Celery couldn't resolve "app.queue.tasks.app.queue.tasks.X" —
# messages were silently discarded. Reject any prefixed input up-front.
_FORBIDDEN_PREFIXES = ("app.queue.tasks.", "app.queue.")


def send_celery_task(task_name: str, *args, **kwargs):
    """
    Thread-safe wrapper to send a Celery task.

    Uses celery_app.send_task() instead of task.delay() to ensure the task
    is dispatched using the properly configured Celery app, even when called
    from FastAPI's thread pool (which runs sync endpoints).

    Args:
        task_name: The unqualified short task name (e.g. ``'analyze_product_task'``).
            The wrapper resolves this to the registered Celery task path.
        *args: Positional arguments to pass to the task
        **kwargs: Keyword arguments to pass to the task

    Returns:
        AsyncResult object representing the queued task
    """
    # Guard against double-prefixing — see _FORBIDDEN_PREFIXES note above.
    for prefix in _FORBIDDEN_PREFIXES:
        if task_name.startswith(prefix):
            raise ValueError(
                f"task_name must not include the {prefix!r} prefix; "
                f"got {task_name!r}"
            )

    full_name = _TASK_NAME_MAP.get(task_name)
    if full_name is None:
        raise ValueError(
            f"Unknown Celery task name {task_name!r}. "
            f"Add it to _TASK_NAME_MAP in celery_utils.py."
        )

    return celery_app.send_task(
        full_name,
        args=args,
        kwargs=kwargs if kwargs else None
    )
