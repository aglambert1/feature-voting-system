"""
Tests for authentication & security (Category 1A).

Covers registration, login, JWT validation, RBAC, account management,
password reset, and password change flows.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, Mock

from app.models.user import User, UserRole
from app.models.password_reset import PasswordResetToken
from app.utils.security import hash_password, create_access_token, verify_password
from conftest import auth_headers


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

    def test_register_valid_user_via_admin(self, client, admin_user):
        """Admin can create users without invite codes."""
        resp = client.post("/auth/register", json={
            "email": "new@example.com",
            "username": "newuser",
            "password": "Secure@pass1",
            "full_name": "New User"
        }, headers=auth_headers(admin_user))
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert data["username"] == "newuser"
        assert data["role"] == "voter"  # default role
        assert data["is_active"] is True
        assert "hashed_password" not in data

    def test_register_requires_invite_code(self, client, db_session):
        """Self-registration without invite code is rejected."""
        resp = client.post("/auth/register", json={
            "email": "new@example.com",
            "username": "newuser",
            "password": "Secure@pass1",
            "full_name": "New User"
        })
        assert resp.status_code == 400
        assert "invite code" in resp.json()["detail"].lower()

    def test_register_duplicate_email(self, client, voter_user, admin_user):
        resp = client.post("/auth/register", json={
            "email": voter_user.email,
            "username": "different",
            "password": "Secure@pass1"
        }, headers=auth_headers(admin_user))
        assert resp.status_code == 400
        assert "Email already registered" in resp.json()["detail"]

    def test_register_duplicate_username(self, client, voter_user, admin_user):
        resp = client.post("/auth/register", json={
            "email": "unique@example.com",
            "username": voter_user.username,
            "password": "Secure@pass1"
        }, headers=auth_headers(admin_user))
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

    def test_register_weak_password_rejected(self, client):
        resp = client.post("/auth/register", json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "alllowercase1"
        })
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        messages = [e.get("msg", "") for e in detail] if isinstance(detail, list) else [str(detail)]
        assert any("uppercase" in m.lower() for m in messages)

    def test_register_short_username(self, client):
        resp = client.post("/auth/register", json={
            "email": "test@example.com",
            "username": "ab",
            "password": "Secure@pass1"
        })
        assert resp.status_code == 422

    def test_register_invalid_email(self, client):
        resp = client.post("/auth/register", json={
            "email": "not-an-email",
            "username": "testuser",
            "password": "Secure@pass1"
        })
        assert resp.status_code == 422

    def test_register_default_role_is_voter(self, client, admin_user):
        resp = client.post("/auth/register", json={
            "email": "roletest@example.com",
            "username": "roletest",
            "password": "Secure@pass1"
        }, headers=auth_headers(admin_user))
        assert resp.status_code == 201
        assert resp.json()["role"] == "voter"

    def test_self_registration_ignores_requested_admin_role(
        self, client, db_session, test_invite_code
    ):
        """Self-registrants cannot escalate to ADMIN via the role field."""
        resp = client.post("/auth/register", json={
            "email": "escalate@example.com",
            "username": "escalate",
            "password": "Secure@pass1",
            "invite_code": test_invite_code.code,
            "role": "admin",
        })
        assert resp.status_code == 201
        assert resp.json()["role"] == "voter"

    def test_self_registration_ignores_requested_po_role(
        self, client, db_session, test_invite_code
    ):
        """Self-registrants cannot escalate to PRODUCT_OWNER either."""
        resp = client.post("/auth/register", json={
            "email": "escalate2@example.com",
            "username": "escalate2",
            "password": "Secure@pass1",
            "invite_code": test_invite_code.code,
            "role": "product_owner",
        })
        assert resp.status_code == 201
        assert resp.json()["role"] == "voter"

    def test_admin_can_still_set_role(self, client, admin_user):
        """The admin-created path still honors an explicit role."""
        resp = client.post("/auth/register", json={
            "email": "realpo@example.com",
            "username": "realpo",
            "password": "Secure@pass1",
            "role": "product_owner",
        }, headers=auth_headers(admin_user))
        assert resp.status_code == 201
        assert resp.json()["role"] == "product_owner"


# ============================================================================
# Login (POST /auth/login)
# ============================================================================


class TestLogin:

    def test_login_with_username(self, client, voter_user):
        resp = client.post("/auth/login", data={
            "username": "voter",
            "password": "Voter@pass1"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_with_email(self, client, voter_user):
        resp = client.post("/auth/login", data={
            "username": "voter@example.com",
            "password": "Voter@pass1"
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
            "password": "Voter@pass1"
        })
        assert resp.status_code == 401

    def test_login_inactive_user(self, client, db_session, voter_user):
        voter_user.is_active = False
        db_session.commit()
        resp = client.post("/auth/login", data={
            "username": "voter",
            "password": "Voter@pass1"
        })
        assert resp.status_code == 403
        assert "disabled" in resp.json()["detail"].lower()

    def test_login_token_contains_correct_claims(self, client, voter_user):
        resp = client.post("/auth/login", data={
            "username": "voter",
            "password": "Voter@pass1"
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
# Welcome Flag (POST /auth/me/mark-welcomed)
# ============================================================================


class TestMarkWelcomed:

    def test_new_user_defaults_to_unwelcomed(self, client, voter_user):
        resp = client.get("/auth/me", headers=auth_headers(voter_user))
        assert resp.status_code == 200
        assert resp.json()["has_seen_welcome"] is False

    def test_mark_welcomed_flips_flag(self, client, db_session, voter_user):
        resp = client.post("/auth/me/mark-welcomed", headers=auth_headers(voter_user))
        assert resp.status_code == 200
        assert resp.json()["has_seen_welcome"] is True

        db_session.refresh(voter_user)
        assert voter_user.has_seen_welcome is True

    def test_mark_welcomed_is_idempotent(self, client, voter_user):
        first = client.post("/auth/me/mark-welcomed", headers=auth_headers(voter_user))
        second = client.post("/auth/me/mark-welcomed", headers=auth_headers(voter_user))
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["has_seen_welcome"] is True

    def test_mark_welcomed_requires_auth(self, client):
        resp = client.post("/auth/me/mark-welcomed")
        assert resp.status_code == 401

    def test_welcome_flag_is_per_user(self, client, db_session, voter_user, admin_user):
        # Admin flips the flag on their own account...
        client.post("/auth/me/mark-welcomed", headers=auth_headers(admin_user))

        # ...voter's flag stays false. This is the regression the bug fix exists for.
        resp = client.get("/auth/me", headers=auth_headers(voter_user))
        assert resp.json()["has_seen_welcome"] is False


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
            "username": "voter", "password": "Voter@pass1"
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
        mock_email_svc.is_live = False
        mock_email_svc.send_password_reset_otp = Mock(return_value=True)
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
        mock_email_svc.is_live = False
        mock_email_svc.send_password_reset_otp = Mock(return_value=True)
        mock_email_svc.send_password_changed_notification = Mock(return_value=True)

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
            "new_password": "NewPass@456"
        })
        assert resp.status_code == 200

        # Verify password was changed
        db_session.refresh(voter_user)
        assert verify_password("NewPass@456", voter_user.hashed_password)

    @patch("app.utils.email.email_service")
    def test_reset_confirm_expired_otp(self, mock_email_svc, client, voter_user, db_session):
        mock_email_svc.is_live = False
        token = PasswordResetToken(
            user_id=voter_user.id,
            token="123456",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),  # expired
        )
        db_session.add(token)
        db_session.commit()

        resp = client.post("/auth/password/reset-confirm", json={
            "email": voter_user.email,
            "otp": "123456",
            "new_password": "NewPass@456"
        })
        assert resp.status_code == 400
        assert "expired" in resp.json()["detail"].lower()

    def test_reset_confirm_used_otp(self, client, voter_user, db_session):
        token = PasswordResetToken(
            user_id=voter_user.id,
            token="654321",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            is_used=True,
        )
        db_session.add(token)
        db_session.commit()

        resp = client.post("/auth/password/reset-confirm", json={
            "email": voter_user.email,
            "otp": "654321",
            "new_password": "NewPass@456"
        })
        assert resp.status_code == 400

    def test_reset_confirm_wrong_otp(self, client, voter_user, db_session):
        token = PasswordResetToken(
            user_id=voter_user.id,
            token="111111",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        )
        db_session.add(token)
        db_session.commit()

        resp = client.post("/auth/password/reset-confirm", json={
            "email": voter_user.email,
            "otp": "999999",
            "new_password": "NewPass@456"
        })
        assert resp.status_code == 400

    @patch("app.utils.email.email_service")
    def test_previous_otps_invalidated(self, mock_email_svc, client, voter_user, db_session):
        mock_email_svc.is_live = False
        mock_email_svc.send_password_reset_otp = Mock(return_value=True)
        # Create an existing unused OTP
        old_token = PasswordResetToken(
            user_id=voter_user.id,
            token="111111",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
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
            "new_password": "NewPass@456"
        })
        assert resp.status_code == 404


# ============================================================================
# Password Change (POST /auth/password/change)
# ============================================================================


class TestPasswordChange:

    @patch("app.utils.email.email_service")
    def test_change_password_success(self, mock_email_svc, client, voter_user):
        mock_email_svc.is_live = False
        mock_email_svc.send_password_changed_notification = Mock(return_value=True)
        resp = client.post("/auth/password/change", json={
            "current_password": "Voter@pass1",
            "new_password": "Changed@789"
        }, headers=auth_headers(voter_user))
        assert resp.status_code == 200
        assert "successfully changed" in resp.json()["message"].lower()

    def test_change_password_wrong_current(self, client, voter_user):
        resp = client.post("/auth/password/change", json={
            "current_password": "wrongpassword",
            "new_password": "Changed@789"
        }, headers=auth_headers(voter_user))
        assert resp.status_code == 400
        assert "incorrect" in resp.json()["detail"].lower()

    def test_change_password_same_as_current(self, client, voter_user):
        resp = client.post("/auth/password/change", json={
            "current_password": "Voter@pass1",
            "new_password": "Voter@pass1"
        }, headers=auth_headers(voter_user))
        assert resp.status_code == 400
        assert "different" in resp.json()["detail"].lower()

    def test_change_password_requires_auth(self, client):
        resp = client.post("/auth/password/change", json={
            "current_password": "Voter@pass1",
            "new_password": "Changed@789"
        })
        assert resp.status_code == 401


# ============================================================================
# Admin Password Reset (POST /auth/users/{id}/reset-password)
# ============================================================================


class TestAdminPasswordReset:

    def test_admin_resets_user_password(self, client, admin_user, voter_user, db_session):
        resp = client.post(
            f"/auth/users/{voter_user.id}/reset-password",
            headers=auth_headers(admin_user)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "temporary_password" in data
        assert data["username"] == voter_user.username
        assert len(data["temporary_password"]) >= 8

        # Verify must_change_password is set
        db_session.refresh(voter_user)
        assert voter_user.must_change_password is True

        # Verify the temp password works for login
        login_resp = client.post("/auth/login", data={
            "username": voter_user.username,
            "password": data["temporary_password"],
        })
        assert login_resp.status_code == 200
        assert login_resp.json()["must_change_password"] is True

    def test_admin_cannot_reset_own_password(self, client, admin_user):
        resp = client.post(
            f"/auth/users/{admin_user.id}/reset-password",
            headers=auth_headers(admin_user)
        )
        assert resp.status_code == 400
        assert "own password" in resp.json()["detail"].lower()

    def test_non_admin_gets_403(self, client, voter_user, admin_user):
        resp = client.post(
            f"/auth/users/{admin_user.id}/reset-password",
            headers=auth_headers(voter_user)
        )
        assert resp.status_code == 403

    def test_reset_nonexistent_user(self, client, admin_user):
        resp = client.post(
            "/auth/users/99999/reset-password",
            headers=auth_headers(admin_user)
        )
        assert resp.status_code == 404

    @patch("app.utils.email.email_service")
    def test_password_change_clears_must_change_flag(self, mock_email_svc, client, admin_user, voter_user, db_session):
        mock_email_svc.is_live = False
        mock_email_svc.send_password_changed_notification = Mock(return_value=True)

        # Admin resets the password
        reset_resp = client.post(
            f"/auth/users/{voter_user.id}/reset-password",
            headers=auth_headers(admin_user)
        )
        temp_password = reset_resp.json()["temporary_password"]

        # Login with temp password to get a valid token
        login_resp = client.post("/auth/login", data={
            "username": voter_user.username,
            "password": temp_password,
        })
        new_token = login_resp.json()["access_token"]
        new_headers = {"Authorization": f"Bearer {new_token}"}

        # Change password
        change_resp = client.post("/auth/password/change", json={
            "current_password": temp_password,
            "new_password": "Permanent@123",
        }, headers=new_headers)
        assert change_resp.status_code == 200

        # Flag should be cleared
        db_session.refresh(voter_user)
        assert voter_user.must_change_password is False


# ============================================================================
# Session Invalidation (tokens_valid_after)
# ============================================================================


class TestSessionInvalidation:

    def test_old_token_rejected_after_password_reset(self, client, admin_user, voter_user, db_session):
        # Get a token before the reset
        old_headers = auth_headers(voter_user)

        # Admin resets the password
        client.post(
            f"/auth/users/{voter_user.id}/reset-password",
            headers=auth_headers(admin_user)
        )

        # Old token should be rejected
        resp = client.get("/auth/me", headers=old_headers)
        assert resp.status_code == 401

    def test_old_token_rejected_after_deactivation(self, client, admin_user, voter_user, db_session):
        old_headers = auth_headers(voter_user)

        client.patch(
            f"/auth/users/{voter_user.id}/deactivate",
            headers=auth_headers(admin_user)
        )

        resp = client.get("/auth/me", headers=old_headers)
        assert resp.status_code in (401, 403)

    def test_new_token_works_after_password_reset(self, client, admin_user, voter_user, db_session):
        reset_resp = client.post(
            f"/auth/users/{voter_user.id}/reset-password",
            headers=auth_headers(admin_user)
        )
        temp_password = reset_resp.json()["temporary_password"]

        login_resp = client.post("/auth/login", data={
            "username": voter_user.username,
            "password": temp_password,
        })
        assert login_resp.status_code == 200

        new_token = login_resp.json()["access_token"]
        me_resp = client.get("/auth/me", headers={"Authorization": f"Bearer {new_token}"})
        assert me_resp.status_code == 200
        assert me_resp.json()["username"] == voter_user.username


# ============================================================================
# Login Tracking & Account Lockout
# ============================================================================


class TestLoginTracking:

    def test_successful_login_updates_last_login_at(self, client, voter_user, db_session):
        resp = client.post("/auth/login", data={
            "username": "voter", "password": "Voter@pass1"
        })
        assert resp.status_code == 200
        db_session.refresh(voter_user)
        assert voter_user.last_login_at is not None

    def test_successful_login_creates_login_event(self, client, voter_user, db_session):
        from app.models.login_event import LoginEvent
        client.post("/auth/login", data={
            "username": "voter", "password": "Voter@pass1"
        })
        events = db_session.query(LoginEvent).filter(
            LoginEvent.user_id == voter_user.id
        ).all()
        assert len(events) == 1
        assert events[0].ip_address is not None

    def test_failed_login_increments_counter(self, client, voter_user, db_session):
        client.post("/auth/login", data={
            "username": "voter", "password": "WrongPass@1"
        })
        db_session.refresh(voter_user)
        assert voter_user.failed_login_attempts == 1

    def test_successful_login_resets_counter(self, client, voter_user, db_session):
        voter_user.failed_login_attempts = 3
        db_session.commit()
        client.post("/auth/login", data={
            "username": "voter", "password": "Voter@pass1"
        })
        db_session.refresh(voter_user)
        assert voter_user.failed_login_attempts == 0


class TestAccountLockout:

    def test_account_locks_after_5_failures(self, client, voter_user, db_session):
        for _ in range(5):
            client.post("/auth/login", data={
                "username": "voter", "password": "WrongPass@1"
            })
        db_session.refresh(voter_user)
        assert voter_user.locked_until is not None
        assert voter_user.failed_login_attempts == 5

    def test_locked_account_returns_403(self, client, voter_user, db_session):
        voter_user.failed_login_attempts = 5
        voter_user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
        db_session.commit()
        resp = client.post("/auth/login", data={
            "username": "voter", "password": "Voter@pass1"
        })
        assert resp.status_code == 403
        assert "temporarily locked" in resp.json()["detail"].lower()

    def test_lockout_expires(self, client, voter_user, db_session):
        voter_user.failed_login_attempts = 5
        voter_user.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)
        db_session.commit()
        resp = client.post("/auth/login", data={
            "username": "voter", "password": "Voter@pass1"
        })
        assert resp.status_code == 200
        db_session.refresh(voter_user)
        assert voter_user.failed_login_attempts == 0
        assert voter_user.locked_until is None

    def test_admin_unlock_resets_lockout(self, client, admin_user, voter_user, db_session):
        voter_user.failed_login_attempts = 5
        voter_user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
        db_session.commit()
        resp = client.post(
            f"/auth/users/{voter_user.id}/unlock",
            headers=auth_headers(admin_user)
        )
        assert resp.status_code == 200
        db_session.refresh(voter_user)
        assert voter_user.failed_login_attempts == 0
        assert voter_user.locked_until is None

    def test_unlock_requires_admin(self, client, voter_user):
        resp = client.post(
            f"/auth/users/{voter_user.id}/unlock",
            headers=auth_headers(voter_user)
        )
        assert resp.status_code == 403


class TestLoginHistory:

    def test_admin_can_view_login_history(self, client, admin_user, voter_user, db_session):
        # Create a login event
        client.post("/auth/login", data={
            "username": "voter", "password": "Voter@pass1"
        })
        resp = client.get(
            f"/auth/users/{voter_user.id}/login-history",
            headers=auth_headers(admin_user)
        )
        assert resp.status_code == 200
        events = resp.json()
        assert len(events) >= 1
        assert "logged_in_at" in events[0]
        assert "ip_address" in events[0]

    def test_login_history_requires_admin(self, client, voter_user):
        resp = client.get(
            f"/auth/users/{voter_user.id}/login-history",
            headers=auth_headers(voter_user)
        )
        assert resp.status_code == 403

    def test_login_history_nonexistent_user(self, client, admin_user):
        resp = client.get(
            "/auth/users/99999/login-history",
            headers=auth_headers(admin_user)
        )
        assert resp.status_code == 404


class TestProfileUpdate:

    def test_update_full_name(self, client, voter_user):
        resp = client.patch("/auth/me", json={
            "full_name": "Updated Name"
        }, headers=auth_headers(voter_user))
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Updated Name"

    def test_update_email(self, client, voter_user):
        resp = client.patch("/auth/me", json={
            "email": "newemail@example.com"
        }, headers=auth_headers(voter_user))
        assert resp.status_code == 200
        assert resp.json()["email"] == "newemail@example.com"

    def test_update_email_duplicate(self, client, voter_user, admin_user):
        resp = client.patch("/auth/me", json={
            "email": admin_user.email
        }, headers=auth_headers(voter_user))
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"].lower()

    def test_update_email_same_as_current(self, client, voter_user):
        resp = client.patch("/auth/me", json={
            "email": voter_user.email
        }, headers=auth_headers(voter_user))
        assert resp.status_code == 200

    def test_update_requires_auth(self, client):
        resp = client.patch("/auth/me", json={"full_name": "No Auth"})
        assert resp.status_code == 401
