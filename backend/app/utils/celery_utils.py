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

_TASK_PREFIX = "app.queue.tasks."


def send_celery_task(task_name: str, *args, **kwargs):
    """
    Thread-safe wrapper to send a Celery task.

    Uses celery_app.send_task() instead of task.delay() to ensure the task
    is dispatched using the properly configured Celery app, even when called
    from FastAPI's thread pool (which runs sync endpoints).

    Args:
        task_name: The task name (without 'app.queue.tasks.' prefix)
        *args: Positional arguments to pass to the task
        **kwargs: Keyword arguments to pass to the task

    Returns:
        AsyncResult object representing the queued task
    """
    # Guard against double-prefixing. Prior incident: an endpoint passed the
    # full-prefixed name, we concatenated another prefix, and Celery couldn't
    # resolve "app.queue.tasks.app.queue.tasks.X" — messages were silently
    # discarded.
    if task_name.startswith(_TASK_PREFIX):
        raise ValueError(
            f"task_name must not include the {_TASK_PREFIX!r} prefix; "
            f"got {task_name!r}"
        )
    return celery_app.send_task(
        f'{_TASK_PREFIX}{task_name}',
        args=args,
        kwargs=kwargs if kwargs else None
    )
