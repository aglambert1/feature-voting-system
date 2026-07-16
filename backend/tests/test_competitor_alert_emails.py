"""Tests for competitor-alert email notifications (Flow E follow-up).

Covers recipient resolution (get_product_members), the AlertNotificationService
dispatch, the email_tasks branch, and discovery-job resilience if email
enqueue fails.
"""

from unittest.mock import patch

import pytest

from app.models.competitor_intelligence import (
    ProductPermission,
    ProductPermissionLevel,
)
from app.models.user import UserRole
from app.services.alert_notification_service import AlertNotificationService
from app.services.permission_service import PermissionService
from conftest import _create_user_with_password


def _grant(db_session, product, user, level):
    perm = ProductPermission(
        product_id=product.id,
        user_id=user.id,
        permission_level=level,
        granted_by_user_id=product.created_by_user_id,
    )
    db_session.add(perm)
    db_session.commit()
    return perm


@pytest.fixture
def editor_user(db_session, test_product):
    """A PRODUCT_OWNER granted EDIT on test_product (not the creator)."""
    user = _create_user_with_password(
        db_session, "editor@example.com", "editor", "Editor@pass1",
        UserRole.PRODUCT_OWNER,
    )
    _grant(db_session, test_product, user, ProductPermissionLevel.EDIT)
    return user


class TestGetProductMembers:
    def test_includes_creator(self, db_session, test_product, po_user):
        members = PermissionService(db_session).get_product_members(
            test_product.id, min_level=ProductPermissionLevel.EDIT
        )
        assert po_user.id in {u.id for u in members}

    def test_includes_edit_grantee(self, db_session, test_product, editor_user):
        members = PermissionService(db_session).get_product_members(
            test_product.id, min_level=ProductPermissionLevel.EDIT
        )
        assert editor_user.id in {u.id for u in members}

    def test_excludes_view_only_member(
        self, db_session, test_product, voter_user, voter_product_access
    ):
        members = PermissionService(db_session).get_product_members(
            test_product.id, min_level=ProductPermissionLevel.EDIT
        )
        assert voter_user.id not in {u.id for u in members}

    def test_view_min_level_includes_view_member(
        self, db_session, test_product, voter_user, voter_product_access
    ):
        members = PermissionService(db_session).get_product_members(
            test_product.id, min_level=ProductPermissionLevel.VIEW
        )
        assert voter_user.id in {u.id for u in members}

    def test_excludes_inactive_creator(self, db_session, test_product, po_user):
        po_user.is_active = False
        db_session.commit()
        members = PermissionService(db_session).get_product_members(
            test_product.id, min_level=ProductPermissionLevel.EDIT
        )
        assert po_user.id not in {u.id for u in members}

    def test_deduplicates(self, db_session, test_product, po_user):
        # Creator also has an explicit grant — should appear once
        _grant(db_session, test_product, po_user, ProductPermissionLevel.OWNER)
        members = PermissionService(db_session).get_product_members(
            test_product.id, min_level=ProductPermissionLevel.EDIT
        )
        ids = [u.id for u in members]
        assert ids.count(po_user.id) == 1


class TestAlertNotificationService:
    @patch("app.queue.email_tasks.send_email_task.delay")
    def test_enqueues_one_email_per_recipient(
        self, mock_delay, db_session, test_product, po_user, editor_user
    ):
        alerts = [{"competitor_name": "Acme", "message": "New competitor discovered: Acme"}]
        sent = AlertNotificationService(db_session).notify_new_competitors(
            test_product.id, alerts
        )
        assert sent == 2  # creator + editor
        assert mock_delay.call_count == 2
        recipients = {c.kwargs["to_email"] for c in mock_delay.call_args_list}
        assert recipients == {po_user.email, editor_user.email}

    @patch("app.queue.email_tasks.send_email_task.delay")
    def test_digest_context_shape(
        self, mock_delay, db_session, test_product, po_user
    ):
        alerts = [
            {"competitor_name": "Acme", "message": "m1"},
            {"competitor_name": "Globex", "message": "m2"},
        ]
        AlertNotificationService(db_session).notify_new_competitors(
            test_product.id, alerts
        )
        ctx = mock_delay.call_args_list[0].kwargs["context"]
        assert ctx["product_name"] == test_product.product_name
        assert [a["competitor_name"] for a in ctx["alerts"]] == ["Acme", "Globex"]
        assert mock_delay.call_args_list[0].kwargs["email_type"] == "competitor_alert_digest"

    @patch("app.queue.email_tasks.send_email_task.delay")
    def test_no_alerts_no_email(self, mock_delay, db_session, test_product):
        sent = AlertNotificationService(db_session).notify_new_competitors(
            test_product.id, []
        )
        assert sent == 0
        mock_delay.assert_not_called()

    @patch("app.queue.email_tasks.send_email_task.delay")
    def test_view_only_recipient_not_emailed(
        self, mock_delay, db_session, test_product, voter_user, voter_product_access
    ):
        # Product creator (po_user) still gets it; the view-only voter does not
        alerts = [{"competitor_name": "Acme", "message": "m"}]
        AlertNotificationService(db_session).notify_new_competitors(
            test_product.id, alerts
        )
        recipients = {c.kwargs["to_email"] for c in mock_delay.call_args_list}
        assert voter_user.email not in recipients

    @patch("app.queue.email_tasks.send_email_task.delay")
    def test_per_recipient_enqueue_failure_is_swallowed(
        self, mock_delay, db_session, test_product, po_user, editor_user
    ):
        # First recipient raises; the service must continue to the second and
        # not propagate (discovery job must not fail on a notification error).
        mock_delay.side_effect = [RuntimeError("broker down"), None]
        alerts = [{"competitor_name": "Acme", "message": "m"}]
        sent = AlertNotificationService(db_session).notify_new_competitors(
            test_product.id, alerts
        )
        assert sent == 1  # one failed, one succeeded
        assert mock_delay.call_count == 2


class TestEmailTaskBranch:
    @patch("app.utils.email.email_service.send_competitor_alert_digest")
    def test_task_dispatches_competitor_digest(self, mock_send):
        from app.queue.email_tasks import send_email_task

        mock_send.return_value = True
        result = send_email_task(
            email_type="competitor_alert_digest",
            to_email="po@example.com",
            context={
                "username": "po",
                "product_name": "Widget",
                "alerts": [{"competitor_name": "Acme", "message": "m"}],
            },
        )
        assert result["status"] == "sent"
        mock_send.assert_called_once()
