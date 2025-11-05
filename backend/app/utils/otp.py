"""
OTP (One-Time Password) generation utilities.
"""

import secrets
import string
from datetime import datetime, timedelta


def generate_otp(length: int = 6) -> str:
    """
    Generate a random numeric OTP code.

    Args:
        length: Length of OTP (default 6 digits)

    Returns:
        String of random digits
    """
    digits = string.digits
    otp = ''.join(secrets.choice(digits) for _ in range(length))
    return otp


def get_otp_expiration(minutes: int = 15) -> datetime:
    """
    Get expiration time for OTP.

    Args:
        minutes: Minutes until expiration (default 15)

    Returns:
        Datetime when OTP expires
    """
    return datetime.utcnow() + timedelta(minutes=minutes)
