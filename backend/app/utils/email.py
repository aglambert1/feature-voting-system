import logging
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

_template_dir = Path(__file__).resolve().parent.parent / "templates" / "email"
_jinja_env = Environment(loader=FileSystemLoader(str(_template_dir)), autoescape=True)


def _render_template(template_name: str, **context) -> str:
    return _jinja_env.get_template(template_name).render(**context)


class EmailService:

    def __init__(self):
        from app.config import settings

        self._api_key = settings.sendgrid_api_key
        self._from_email = settings.sendgrid_from_email
        self._from_name = settings.sendgrid_from_name
        self._sg_client = None

    @property
    def sg(self):
        if self._sg_client is None and self._api_key:
            from sendgrid import SendGridAPIClient
            self._sg_client = SendGridAPIClient(self._api_key)
        return self._sg_client

    @property
    def is_live(self) -> bool:
        return bool(self._api_key)

    def send_email(self, to_email: str, subject: str, html_content: str, plain_content: str | None = None) -> bool:
        if not self.is_live:
            logger.info(f"[EMAIL-DEV] To: {to_email} | Subject: {subject}")
            print(f"\n{'=' * 60}")
            print(f"EMAIL (console fallback)")
            print(f"{'=' * 60}")
            print(f"To: {to_email}")
            print(f"Subject: {subject}")
            print(f"{'=' * 60}\n")
            return True

        try:
            from sendgrid.helpers.mail import Mail, Email, To

            message = Mail(
                from_email=Email(self._from_email, self._from_name),
                to_emails=To(to_email),
                subject=subject,
                html_content=html_content,
                plain_text_content=plain_content,
            )
            response = self.sg.send(message)
            logger.info(f"Email sent to {to_email}: status={response.status_code}")
            return 200 <= response.status_code < 300
        except Exception:
            logger.exception(f"Failed to send email to {to_email}")
            return False

    def send_password_reset_otp(self, to_email: str, otp: str, username: str) -> bool:
        subject = "Password Reset Code - Feature-IQ"
        html = _render_template("password_reset_otp.html", username=username, otp=otp, expires_minutes=15)
        plain = (
            f"Hello {username},\n\n"
            f"Your password reset code is: {otp}\n\n"
            f"This code expires in 15 minutes.\n\n"
            f"If you didn't request this, ignore this email."
        )

        if not self.is_live:
            print(f"\n{'=' * 60}")
            print(f"PASSWORD RESET OTP")
            print(f"{'=' * 60}")
            print(f"To: {to_email}")
            print(f"OTP Code: {otp}")
            print(f"Expires: 15 minutes")
            print(f"{'=' * 60}\n")

        return self.send_email(to_email, subject, html, plain)

    def send_password_changed_notification(self, to_email: str, username: str) -> bool:
        changed_at = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")
        subject = "Password Changed - Feature-IQ"
        html = _render_template("password_changed.html", username=username, changed_at=changed_at)
        plain = (
            f"Hello {username},\n\n"
            f"Your Feature-IQ password was changed on {changed_at}.\n\n"
            f"If you did not make this change, please reset your password immediately."
        )

        if not self.is_live:
            print(f"\n{'=' * 60}")
            print(f"PASSWORD CHANGED NOTIFICATION")
            print(f"{'=' * 60}")
            print(f"To: {to_email}")
            print(f"Changed at: {changed_at}")
            print(f"{'=' * 60}\n")

        return self.send_email(to_email, subject, html, plain)

    def send_competitor_alert_digest(
        self,
        to_email: str,
        username: str,
        product_name: str,
        alerts: list[dict],
    ) -> bool:
        count = len(alerts)
        noun = "competitor" if count == 1 else "competitors"
        subject = f"{count} new {noun} for {product_name} - Feature-IQ"
        html = _render_template(
            "competitor_alert_digest.html",
            username=username,
            product_name=product_name,
            alerts=alerts,
            count=count,
        )
        lines = "\n".join(f"  - {a['competitor_name']}" for a in alerts)
        plain = (
            f"Hello {username},\n\n"
            f"Feature-IQ discovered {count} new {noun} for {product_name}:\n\n"
            f"{lines}\n\n"
            f"Sign in to review them in the Competitive Intelligence hub."
        )

        if not self.is_live:
            print(f"\n{'=' * 60}")
            print(f"COMPETITOR ALERT DIGEST")
            print(f"{'=' * 60}")
            print(f"To: {to_email}")
            print(f"Product: {product_name}")
            print(f"New {noun} ({count}):")
            for a in alerts:
                print(f"  - {a['competitor_name']}")
            print(f"{'=' * 60}\n")

        return self.send_email(to_email, subject, html, plain)


email_service = EmailService()
