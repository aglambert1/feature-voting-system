"""Alert notification service.

Dispatches email notifications to the members of a product when something
happens that they should know about (currently: new competitors discovered by
a scheduled discovery run). Built to extend to other alert types — add a new
alert_type + template and call notify_product_members with it.
"""

import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.competitor_intelligence import CIProduct, ProductPermissionLevel
from app.services.permission_service import PermissionService

logger = logging.getLogger(__name__)


class AlertNotificationService:
    """Resolves recipients for product alerts and enqueues emails."""

    def __init__(self, db: Session):
        self.db = db
        self.permission_service = PermissionService(db)

    def notify_new_competitors(
        self,
        product_id: int,
        alerts: List[dict],
        min_level: ProductPermissionLevel = ProductPermissionLevel.EDIT,
    ) -> int:
        """Email a digest of newly discovered competitors to product members.

        Args:
            product_id: Product the alerts belong to.
            alerts: List of alert dicts (each with at least 'competitor_name'
                and 'message'). Typically CompetitorAlert.to_dict() output.
            min_level: Minimum permission level a member needs to be notified.
                Defaults to EDIT — voters/view-only members don't manage CI.

        Returns:
            Number of recipients an email was enqueued for. Never raises for a
            per-recipient failure; logs and continues so a notification problem
            can't fail the calling job.
        """
        if not alerts:
            return 0

        product = self.db.query(CIProduct).filter(
            CIProduct.id == product_id
        ).first()
        if not product:
            logger.warning(
                "notify_new_competitors: product %s not found", product_id
            )
            return 0

        recipients = self.permission_service.get_product_members(
            product_id, min_level=min_level
        )
        if not recipients:
            return 0

        context_alerts = [
            {
                "competitor_name": a.get("competitor_name"),
                "message": a.get("message"),
            }
            for a in alerts
        ]

        sent = 0
        for user in recipients:
            if not user.email:
                continue
            try:
                self._enqueue(
                    email_type="competitor_alert_digest",
                    to_email=user.email,
                    context={
                        "username": user.username,
                        "product_name": product.product_name,
                        "alerts": context_alerts,
                    },
                )
                sent += 1
            except Exception:
                logger.exception(
                    "Failed to enqueue competitor alert email for user %s",
                    user.id,
                )
        return sent

    def _enqueue(self, email_type: str, to_email: str, context: dict) -> None:
        """Enqueue an email via the Celery email task (imported lazily)."""
        from app.queue.email_tasks import send_email_task

        send_email_task.delay(
            email_type=email_type,
            to_email=to_email,
            context=context,
        )
