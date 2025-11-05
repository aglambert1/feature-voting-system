"""
Email service utilities.

For MVP: This is a mock email service that logs to console.
In production: Replace with actual SMTP service (SendGrid, AWS SES, etc.)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class EmailService:
    """
    Email service for sending emails.

    MVP Implementation: Logs emails to console instead of sending them.
    This allows testing without setting up an SMTP server.

    Production TODO:
    - Add SMTP configuration
    - Use SendGrid/AWS SES/Postmark
    - Add email templates
    - Add retry logic
    - Add email queue
    """

    def __init__(self):
        """Initialize email service."""
        self.enabled = True  # Set to False to disable all emails

    async def send_password_reset_otp(
        self,
        to_email: str,
        otp: str,
        username: str
    ) -> bool:
        """
        Send password reset OTP to user's email.

        Args:
            to_email: Recipient email address
            otp: 6-digit OTP code
            username: User's username

        Returns:
            True if email was "sent" successfully
        """
        if not self.enabled:
            logger.info(f"Emails disabled - would have sent OTP to {to_email}")
            return False

        # MVP: Log to console (in production, send actual email)
        subject = "Password Reset Request - Feature Voting System"
        body = f"""
Hello {username},

You requested to reset your password for Feature Voting System.

Your One-Time Password (OTP) is: {otp}

This code will expire in 15 minutes.

If you didn't request this, please ignore this email.

Best regards,
Feature Voting System Team
        """

        # Log the email (MVP implementation)
        logger.info("=" * 60)
        logger.info("📧 EMAIL (MVP - Console Only)")
        logger.info("=" * 60)
        logger.info(f"To: {to_email}")
        logger.info(f"Subject: {subject}")
        logger.info(f"Body:\n{body}")
        logger.info("=" * 60)

        print("\n" + "=" * 60)
        print("📧 PASSWORD RESET EMAIL")
        print("=" * 60)
        print(f"To: {to_email}")
        print(f"OTP Code: {otp}")
        print(f"Expires: 15 minutes")
        print("=" * 60 + "\n")

        return True

    async def send_password_changed_notification(
        self,
        to_email: str,
        username: str
    ) -> bool:
        """
        Send notification that password was changed.

        Args:
            to_email: Recipient email address
            username: User's username

        Returns:
            True if email was "sent" successfully
        """
        if not self.enabled:
            logger.info(f"Emails disabled - would have sent notification to {to_email}")
            return False

        subject = "Password Changed - Feature Voting System"
        body = f"""
Hello {username},

Your password for Feature Voting System was successfully changed.

If you didn't make this change, please contact support immediately.

Best regards,
Feature Voting System Team
        """

        logger.info("=" * 60)
        logger.info("📧 EMAIL (MVP - Console Only)")
        logger.info("=" * 60)
        logger.info(f"To: {to_email}")
        logger.info(f"Subject: {subject}")
        logger.info(f"Body:\n{body}")
        logger.info("=" * 60)

        print("\n" + "=" * 60)
        print("📧 PASSWORD CHANGED NOTIFICATION")
        print("=" * 60)
        print(f"To: {to_email}")
        print("Password was successfully changed")
        print("=" * 60 + "\n")

        return True


# Global email service instance
email_service = EmailService()
