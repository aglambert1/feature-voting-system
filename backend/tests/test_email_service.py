import os
import pytest
from unittest.mock import patch, MagicMock

os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only-32chars!")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")


class TestEmailServiceConsoleFallback:

    def test_is_live_false_without_api_key(self):
        with patch("app.config.settings") as mock_settings:
            mock_settings.sendgrid_api_key = ""
            mock_settings.sendgrid_from_email = ""
            mock_settings.sendgrid_from_name = "Feature-IQ"
            from app.utils.email import EmailService
            svc = EmailService()
        assert svc.is_live is False

    def test_is_live_true_with_api_key(self):
        with patch("app.config.settings") as mock_settings:
            mock_settings.sendgrid_api_key = "SG.test-key"
            mock_settings.sendgrid_from_email = "test@example.com"
            mock_settings.sendgrid_from_name = "Feature-IQ"
            from app.utils.email import EmailService
            svc = EmailService()
        assert svc.is_live is True

    def test_send_password_reset_otp_console(self):
        with patch("app.config.settings") as mock_settings:
            mock_settings.sendgrid_api_key = ""
            mock_settings.sendgrid_from_email = ""
            mock_settings.sendgrid_from_name = "Feature-IQ"
            from app.utils.email import EmailService
            svc = EmailService()
        result = svc.send_password_reset_otp("user@example.com", "123456", "testuser")
        assert result is True

    def test_send_password_changed_notification_console(self):
        with patch("app.config.settings") as mock_settings:
            mock_settings.sendgrid_api_key = ""
            mock_settings.sendgrid_from_email = ""
            mock_settings.sendgrid_from_name = "Feature-IQ"
            from app.utils.email import EmailService
            svc = EmailService()
        result = svc.send_password_changed_notification("user@example.com", "testuser")
        assert result is True


class TestEmailServiceSendGrid:

    def _make_live_service(self):
        with patch("app.config.settings") as mock_settings:
            mock_settings.sendgrid_api_key = "SG.test-key"
            mock_settings.sendgrid_from_email = "noreply@example.com"
            mock_settings.sendgrid_from_name = "Feature-IQ"
            from app.utils.email import EmailService
            svc = EmailService()
        return svc

    @patch("sendgrid.SendGridAPIClient")
    def test_send_email_success(self, mock_sg_class):
        svc = self._make_live_service()
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_sg_class.return_value.send.return_value = mock_response

        result = svc.send_email("user@example.com", "Test Subject", "<p>Hello</p>")
        assert result is True
        mock_sg_class.return_value.send.assert_called_once()

    @patch("sendgrid.SendGridAPIClient")
    def test_send_email_failure_returns_false(self, mock_sg_class):
        svc = self._make_live_service()
        mock_sg_class.return_value.send.side_effect = Exception("API error")

        result = svc.send_email("user@example.com", "Test Subject", "<p>Hello</p>")
        assert result is False

    @patch("sendgrid.SendGridAPIClient")
    def test_send_password_reset_otp_live(self, mock_sg_class):
        svc = self._make_live_service()
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_sg_class.return_value.send.return_value = mock_response

        result = svc.send_password_reset_otp("user@example.com", "654321", "testuser")
        assert result is True

        call_args = mock_sg_class.return_value.send.call_args
        mail_obj = call_args[0][0]
        assert "Password Reset Code" in mail_obj.subject.get()

    @patch("sendgrid.SendGridAPIClient")
    def test_send_password_changed_live(self, mock_sg_class):
        svc = self._make_live_service()
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_sg_class.return_value.send.return_value = mock_response

        result = svc.send_password_changed_notification("user@example.com", "testuser")
        assert result is True

        call_args = mock_sg_class.return_value.send.call_args
        mail_obj = call_args[0][0]
        assert "Password Changed" in mail_obj.subject.get()


class TestEmailTemplates:

    def test_otp_template_renders(self):
        from app.utils.email import _render_template
        html = _render_template("password_reset_otp.html", username="Alice", otp="987654", expires_minutes=15)
        assert "987654" in html
        assert "Alice" in html
        assert "15 minutes" in html

    def test_password_changed_template_renders(self):
        from app.utils.email import _render_template
        html = _render_template("password_changed.html", username="Bob", changed_at="June 24, 2026 at 12:00 UTC")
        assert "Bob" in html
        assert "June 24, 2026" in html


class TestEmailTask:

    @patch("app.utils.email.email_service")
    def test_send_email_task_password_reset(self, mock_svc):
        mock_svc.send_password_reset_otp.return_value = True
        from app.queue.email_tasks import send_email_task
        result = send_email_task(
            email_type="password_reset_otp",
            to_email="user@example.com",
            context={"otp": "123456", "username": "testuser"},
        )
        assert result["status"] == "sent"
        mock_svc.send_password_reset_otp.assert_called_once_with(
            to_email="user@example.com", otp="123456", username="testuser"
        )

    @patch("app.utils.email.email_service")
    def test_send_email_task_password_changed(self, mock_svc):
        mock_svc.send_password_changed_notification.return_value = True
        from app.queue.email_tasks import send_email_task
        result = send_email_task(
            email_type="password_changed",
            to_email="user@example.com",
            context={"username": "testuser"},
        )
        assert result["status"] == "sent"
        mock_svc.send_password_changed_notification.assert_called_once_with(
            to_email="user@example.com", username="testuser"
        )

    @patch("app.utils.email.email_service")
    def test_send_email_task_unknown_type(self, mock_svc):
        from app.queue.email_tasks import send_email_task
        result = send_email_task(
            email_type="unknown_type",
            to_email="user@example.com",
            context={},
        )
        assert result["status"] == "error"
