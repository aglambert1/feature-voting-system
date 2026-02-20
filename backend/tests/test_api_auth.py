"""
Tests for authentication & security (Category 1A).

Covers registration, login, JWT validation, RBAC, account management,
password reset, and password change flows.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock

from app.models.user import User, UserRole
from app.models.password_reset import PasswordResetToken
from app.utils.security import hash_password, create_access_token, verify_password
from tests.conftest import auth_headers


# ============================================================================
# Security Utilities (utils/security.py)
# ============================================================================


class TestPasswordHashing:

    def test_hash_password_produces_bcrypt_hash(self):
        hashed = hash_password("testpassword")
        assert hashed.startswith("$2b$")
        assert len(hashed) > 50

    def test_verify_password_correct(self):
        hashed = hash_password("mypassword")
        assert verify_password("mypassword", hashed) is True

    def test_verify_password_incorrect(self):
        hashed = hash_password("mypassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_hash_password_unique_per_call(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # bcrypt uses random salt


class TestJWTTokens:

    def test_create_access_token_default_expiry(self):
        token = create_access_token(data={"sub": "user1", "user_id": 1})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_custom_expiry(self):
        token = create_access_token(
            data={"sub": "user1", "user_id": 1},
            expires_delta=timedelta(minutes=5)
        )
        from jose import jwt
        from app.config import settings
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        assert "exp" in payload
        assert payload["sub"] == "user1"

    def test_token_contains_correct_claims(self):
        from jose import jwt
        from app.config import settings
        token = create_access_token(data={"sub": "testuser", "user_id": 42})
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        assert payload["sub"] == "testuser"
        assert payload["user_id"] == 42
        assert "exp" in payload


# ============================================================================
# Registration (POST /auth/register)
# ============================================================================


class TestRegistration:

    def test_register_valid_user(self, client, db_session):
        resp = client.post("/auth/register", json={
            "email": "new@example.com",
            "username": "newuser",
            "password": "securepass123",
            "full_name": "New User"
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert data["username"] == "newuser"
        assert data["role"] == "voter"  # default role
        assert data["is_active"] is True
        assert "hashed_password" not in data

    def test_register_duplicate_email(self, client, voter_user):
        resp = client.post("/auth/register", json={
            "email": voter_user.email,
            "username": "different",
            "password": "securepass123"
        })
        assert resp.status_code == 400
        assert "Email already registered" in resp.json()["detail"]

    def test_register_duplicate_username(self, client, voter_user):
        resp = client.post("/auth/register", json={
            "email": "unique@example.com",
            "username": voter_user.username,
            "password": "securepass123"
        })
        assert resp.status_code == 400
        assert "Username already taken" in resp.json()["detail"]

    def test_register_missing_required_fields(self, client):
        resp = client.post("/auth/register", json={
            "email": "test@example.com"
        })
        assert resp.status_code == 422

    def test_register_short_password(self, client):
        resp = client.post("/auth/register", json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "short"
        })
        assert resp.status_code == 422

    def test_register_short_username(self, client):
        resp = client.post("/auth/register", json={
            "email": "test@example.com",
            "username": "ab",
            "password": "securepass123"
        })
        assert resp.status_code == 422

    def test_register_invalid_email(self, client):
        resp = client.post("/auth/register", json={
            "email": "not-an-email",
            "username": "testuser",
            "password": "securepass123"
        })
        assert resp.status_code == 422

    def test_register_default_role_is_voter(self, client, db_session):
        resp = client.post("/auth/register", json={
            "email": "roletest@example.com",
            "username": "roletest",
            "password": "securepass123"
        })
        assert resp.status_code == 201
        assert resp.json()["role"] == "voter"


# ============================================================================
# Login (POST /auth/login)
# ============================================================================


class TestLogin:

    def test_login_with_username(self, client, voter_user):
        resp = client.post("/auth/login", data={
            "username": "voter",
            "password": "password123"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_with_email(self, client, voter_user):
        resp = client.post("/auth/login", data={
            "username": "voter@example.com",
            "password": "password123"
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_login_wrong_password(self, client, voter_user):
        resp = client.post("/auth/login", data={
            "username": "voter",
            "password": "wrongpassword"
        })
        assert resp.status_code == 401
        assert "Incorrect username or password" in resp.json()["detail"]

    def test_login_nonexistent_user(self, client):
        resp = client.post("/auth/login", data={
            "username": "nobody",
            "password": "password123"
        })
        assert resp.status_code == 401

    def test_login_inactive_user(self, client, db_session, voter_user):
        voter_user.is_active = False
        db_session.commit()
        resp = client.post("/auth/login", data={
            "username": "voter",
            "password": "password123"
        })
        assert resp.status_code == 403
        assert "disabled" in resp.json()["detail"].lower()

    def test_login_token_contains_correct_claims(self, client, voter_user):
        resp = client.post("/auth/login", data={
            "username": "voter",
            "password": "password123"
        })
        from jose import jwt
        from app.config import settings
        token = resp.json()["access_token"]
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        assert payload["sub"] == "voter"
        assert payload["user_id"] == voter_user.id


# ============================================================================
# Token & Session (GET /auth/me, JWT validation)
# ============================================================================


class TestTokenValidation:

    def test_valid_token_returns_user_data(self, client, voter_user):
        resp = client.get("/auth/me", headers=auth_headers(voter_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "voter"
        assert data["email"] == "voter@example.com"

    def test_expired_token_rejected(self, client, voter_user):
        token = create_access_token(
            data={"sub": voter_user.username, "user_id": voter_user.id},
            expires_delta=timedelta(seconds=-1)
        )
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    def test_malformed_token_rejected(self, client):
        resp = client.get("/auth/me", headers={"Authorization": "Bearer not.a.valid.token"})
        assert resp.status_code == 401

    def test_missing_token_rejected(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_token_for_deleted_user_rejected(self, client, db_session, voter_user):
        headers = auth_headers(voter_user)
        db_session.delete(voter_user)
        db_session.commit()
        resp = client.get("/auth/me", headers=headers)
        assert resp.status_code == 401

    def test_token_for_deactivated_user_rejected(self, client, db_session, voter_user):
        headers = auth_headers(voter_user)
        voter_user.is_active = False
        db_session.commit()
        resp = client.get("/auth/me", headers=headers)
        assert resp.status_code == 403


# ============================================================================
# Role-Based Access Control
# ============================================================================


class TestRBAC:

    def test_admin_endpoint_with_voter_returns_403(self, client, voter_user):
        resp = client.get("/auth/users", headers=auth_headers(voter_user))
        assert resp.status_code == 403

    def test_admin_endpoint_with_admin_returns_200(self, client, admin_user):
        resp = client.get("/auth/users", headers=auth_headers(admin_user))
        assert resp.status_code == 200

    def test_list_users_returns_all_users(self, client, admin_user, voter_user):
        resp = client.get("/auth/users", headers=auth_headers(admin_user))
        assert resp.status_code == 200
        usernames = [u["username"] for u in resp.json()]
        assert "apiadmin" in usernames
        assert "voter" in usernames

    def test_update_role_requires_admin(self, client, voter_user, db_session):
        other = User(
            email="other@example.com", username="other",
            hashed_password=hash_password("pass12345678"),
            role=UserRole.VOTER
        )
        db_session.add(other)
        db_session.commit()
        db_session.refresh(other)

        resp = client.patch(
            f"/auth/users/{other.id}/role",
            json={"role": "admin"},
            headers=auth_headers(voter_user)
        )
        assert resp.status_code == 403

    def test_update_role_as_admin(self, client, admin_user, voter_user):
        resp = client.patch(
            f"/auth/users/{voter_user.id}/role",
            json={"role": "product_owner"},
            headers=auth_headers(admin_user)
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "product_owner"

    def test_admin_cannot_change_own_role(self, client, admin_user):
        resp = client.patch(
            f"/auth/users/{admin_user.id}/role",
            json={"role": "voter"},
            headers=auth_headers(admin_user)
        )
        assert resp.status_code == 400
        assert "cannot change your own role" in resp.json()["detail"].lower()

    def test_update_role_nonexistent_user(self, client, admin_user):
        resp = client.patch(
            "/auth/users/99999/role",
            json={"role": "voter"},
            headers=auth_headers(admin_user)
        )
        assert resp.status_code == 404


# ============================================================================
# Account Management (admin endpoints)
# ============================================================================


class TestAccountManagement:

    def test_deactivate_user(self, client, admin_user, voter_user):
        resp = client.patch(
            f"/auth/users/{voter_user.id}/deactivate",
            headers=auth_headers(admin_user)
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_deactivated_user_cannot_login(self, client, admin_user, voter_user):
        # Deactivate first
        client.patch(
            f"/auth/users/{voter_user.id}/deactivate",
            headers=auth_headers(admin_user)
        )
        # Try to login
        resp = client.post("/auth/login", data={
            "username": "voter", "password": "password123"
        })
        assert resp.status_code == 403

    def test_reactivate_user(self, client, admin_user, voter_user, db_session):
        voter_user.is_active = False
        db_session.commit()
        resp = client.patch(
            f"/auth/users/{voter_user.id}/activate",
            headers=auth_headers(admin_user)
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is True

    def test_admin_cannot_deactivate_self(self, client, admin_user):
        resp = client.patch(
            f"/auth/users/{admin_user.id}/deactivate",
            headers=auth_headers(admin_user)
        )
        assert resp.status_code == 400
        assert "cannot deactivate your own" in resp.json()["detail"].lower()

    def test_deactivate_nonexistent_user(self, client, admin_user):
        resp = client.patch(
            "/auth/users/99999/deactivate",
            headers=auth_headers(admin_user)
        )
        assert resp.status_code == 404

    def test_deactivate_requires_admin(self, client, voter_user, db_session):
        other = User(
            email="other2@example.com", username="other2",
            hashed_password=hash_password("pass12345678"),
            role=UserRole.VOTER
        )
        db_session.add(other)
        db_session.commit()
        db_session.refresh(other)

        resp = client.patch(
            f"/auth/users/{other.id}/deactivate",
            headers=auth_headers(voter_user)
        )
        assert resp.status_code == 403


# ============================================================================
# Password Reset (POST /auth/password/reset-request, /reset-confirm)
# ============================================================================


class TestPasswordReset:

    @patch("app.utils.email.email_service")
    def test_reset_request_valid_email(self, mock_email_svc, client, voter_user, db_session):
        mock_email_svc.send_password_reset_otp = AsyncMock(return_value=True)
        resp = client.post("/auth/password/reset-request", json={
            "email": voter_user.email
        })
        assert resp.status_code == 200
        # OTP should be stored in DB
        token = db_session.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == voter_user.id
        ).first()
        assert token is not None
        assert token.is_used is False

    def test_reset_request_unknown_email_returns_200(self, client):
        resp = client.post("/auth/password/reset-request", json={
            "email": "nobody@example.com"
        })
        # Same 200 response to prevent email enumeration
        assert resp.status_code == 200

    @patch("app.utils.email.email_service")
    def test_reset_confirm_valid_otp(self, mock_email_svc, client, voter_user, db_session):
        mock_email_svc.send_password_reset_otp = AsyncMock(return_value=True)
        mock_email_svc.send_password_changed_notification = AsyncMock(return_value=True)

        # Create OTP token directly
        from app.utils.otp import generate_otp, get_otp_expiration
        otp = generate_otp()
        token = PasswordResetToken(
            user_id=voter_user.id,
            token=otp,
            expires_at=get_otp_expiration(minutes=15),
        )
        db_session.add(token)
        db_session.commit()

        resp = client.post("/auth/password/reset-confirm", json={
            "email": voter_user.email,
            "otp": otp,
            "new_password": "newpassword123"
        })
        assert resp.status_code == 200

        # Verify password was changed
        db_session.refresh(voter_user)
        assert verify_password("newpassword123", voter_user.hashed_password)

    @patch("app.utils.email.email_service")
    def test_reset_confirm_expired_otp(self, mock_email_svc, client, voter_user, db_session):
        token = PasswordResetToken(
            user_id=voter_user.id,
            token="123456",
            expires_at=datetime.utcnow() - timedelta(minutes=1),  # expired
        )
        db_session.add(token)
        db_session.commit()

        resp = client.post("/auth/password/reset-confirm", json={
            "email": voter_user.email,
            "otp": "123456",
            "new_password": "newpassword123"
        })
        assert resp.status_code == 400
        assert "expired" in resp.json()["detail"].lower()

    def test_reset_confirm_used_otp(self, client, voter_user, db_session):
        token = PasswordResetToken(
            user_id=voter_user.id,
            token="654321",
            expires_at=datetime.utcnow() + timedelta(minutes=15),
            is_used=True,
        )
        db_session.add(token)
        db_session.commit()

        resp = client.post("/auth/password/reset-confirm", json={
            "email": voter_user.email,
            "otp": "654321",
            "new_password": "newpassword123"
        })
        assert resp.status_code == 400

    def test_reset_confirm_wrong_otp(self, client, voter_user, db_session):
        token = PasswordResetToken(
            user_id=voter_user.id,
            token="111111",
            expires_at=datetime.utcnow() + timedelta(minutes=15),
        )
        db_session.add(token)
        db_session.commit()

        resp = client.post("/auth/password/reset-confirm", json={
            "email": voter_user.email,
            "otp": "999999",
            "new_password": "newpassword123"
        })
        assert resp.status_code == 400

    @patch("app.utils.email.email_service")
    def test_previous_otps_invalidated(self, mock_email_svc, client, voter_user, db_session):
        mock_email_svc.send_password_reset_otp = AsyncMock(return_value=True)
        # Create an existing unused OTP
        old_token = PasswordResetToken(
            user_id=voter_user.id,
            token="111111",
            expires_at=datetime.utcnow() + timedelta(minutes=15),
        )
        db_session.add(old_token)
        db_session.commit()

        # Request a new reset
        client.post("/auth/password/reset-request", json={
            "email": voter_user.email
        })

        # Old token should be marked as used
        db_session.refresh(old_token)
        assert old_token.is_used is True

    def test_reset_confirm_nonexistent_email(self, client):
        resp = client.post("/auth/password/reset-confirm", json={
            "email": "nobody@example.com",
            "otp": "123456",
            "new_password": "newpassword123"
        })
        assert resp.status_code == 404


# ============================================================================
# Password Change (POST /auth/password/change)
# ============================================================================


class TestPasswordChange:

    @patch("app.utils.email.email_service")
    def test_change_password_success(self, mock_email_svc, client, voter_user):
        mock_email_svc.send_password_changed_notification = AsyncMock(return_value=True)
        resp = client.post("/auth/password/change", json={
            "current_password": "password123",
            "new_password": "newpassword456"
        }, headers=auth_headers(voter_user))
        assert resp.status_code == 200
        assert "successfully changed" in resp.json()["message"].lower()

    def test_change_password_wrong_current(self, client, voter_user):
        resp = client.post("/auth/password/change", json={
            "current_password": "wrongpassword",
            "new_password": "newpassword456"
        }, headers=auth_headers(voter_user))
        assert resp.status_code == 400
        assert "incorrect" in resp.json()["detail"].lower()

    def test_change_password_same_as_current(self, client, voter_user):
        resp = client.post("/auth/password/change", json={
            "current_password": "password123",
            "new_password": "password123"
        }, headers=auth_headers(voter_user))
        assert resp.status_code == 400
        assert "different" in resp.json()["detail"].lower()

    def test_change_password_requires_auth(self, client):
        resp = client.post("/auth/password/change", json={
            "current_password": "password123",
            "new_password": "newpassword456"
        })
        assert resp.status_code == 401
