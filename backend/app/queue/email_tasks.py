import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="app.queue.email_tasks.send_email_task",
    max_retries=3,
    default_retry_delay=30,
    soft_time_limit=30,
)
def send_email_task(self, email_type: str, to_email: str, context: dict):
    from app.utils.email import email_service

    try:
        if email_type == "password_reset_otp":
            success = email_service.send_password_reset_otp(
                to_email=to_email,
                otp=context["otp"],
                username=context["username"],
            )
        elif email_type == "password_changed":
            success = email_service.send_password_changed_notification(
                to_email=to_email,
                username=context["username"],
            )
        else:
            logger.error(f"Unknown email type: {email_type}")
            return {"status": "error", "reason": f"Unknown email type: {email_type}"}

        if not success:
            raise RuntimeError(f"EmailService returned failure for {email_type}")

        return {"status": "sent", "email_type": email_type, "to": to_email}

    except Exception as exc:
        logger.error(f"Email send failed: {exc}")
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))
