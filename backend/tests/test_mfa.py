"""Tests for optional MFA/TOTP functionality."""

import pyotp
import pytest
from unittest.mock import patch

from app.models.user import User, UserRole
from app.utils.security import hash_password, create_access_token
from conftest import auth_headers, _create_user_with_password


class TestMFASetup:

    def test_setup_returns_secret_uri_and_qr(self, client, voter_user):
        resp = client.post("/auth/mfa/setup", headers=auth_headers(voter_user))
        assert resp.status_code == 200
        data = resp.json()
        assert "secret" in data
        assert "provisioning_uri" in data
        assert "otpauth://totp/" in data["provisioning_uri"]
        assert len(data["secret"]) == 32
        assert data["qr_code_data_uri"].startswith("data:image/png;base64,")

    def test_setup_stores_secret_on_user(self, client, voter_user, db_session):
        resp = client.post("/auth/mfa/setup", headers=auth_headers(voter_user))
        assert resp.status_code == 200
        db_session.refresh(voter_user)
        assert voter_user.totp_secret == resp.json()["secret"]
        assert voter_user.totp_enabled is False

    def test_setup_rejected_when_already_enabled(self, client, db_session, voter_user):
        voter_user.totp_secret = pyotp.random_base32()
        voter_user.totp_enabled = True
        db_session.commit()

        resp = client.post("/auth/mfa/setup", headers=auth_headers(voter_user))
        assert resp.status_code == 400
        assert "already enabled" in resp.json()["detail"].lower()

    def test_setup_requires_auth(self, client):
        resp = client.post("/auth/mfa/setup")
        assert resp.status_code == 401


class TestMFAConfirm:

    def _setup_mfa(self, client, user):
        resp = client.post("/auth/mfa/setup", headers=auth_headers(user))
        return resp.json()["secret"]

    def test_confirm_enables_mfa(self, client, voter_user, db_session):
        secret = self._setup_mfa(client, voter_user)
        code = pyotp.TOTP(secret).now()

        resp = client.post(
            "/auth/mfa/confirm",
            json={"code": code},
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 200

        db_session.refresh(voter_user)
        assert voter_user.totp_enabled is True

    def test_confirm_wrong_code(self, client, voter_user):
        self._setup_mfa(client, voter_user)

        resp = client.post(
            "/auth/mfa/confirm",
            json={"code": "000000"},
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 400

    def test_confirm_without_setup(self, client, voter_user):
        resp = client.post(
            "/auth/mfa/confirm",
            json={"code": "123456"},
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 400
        assert "setup first" in resp.json()["detail"].lower()

    def test_confirm_when_already_enabled(self, client, db_session, voter_user):
        voter_user.totp_secret = pyotp.random_base32()
        voter_user.totp_enabled = True
        db_session.commit()

        resp = client.post(
            "/auth/mfa/confirm",
            json={"code": "123456"},
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 400
        assert "already enabled" in resp.json()["detail"].lower()


class TestMFADisable:

    def test_disable_clears_mfa(self, client, db_session, voter_user):
        voter_user.totp_secret = pyotp.random_base32()
        voter_user.totp_enabled = True
        voter_user.hashed_password = hash_password("Voter@pass1")
        db_session.commit()

        resp = client.post(
            "/auth/mfa/disable",
            json={"password": "Voter@pass1"},
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 200

        db_session.refresh(voter_user)
        assert voter_user.totp_enabled is False
        assert voter_user.totp_secret is None

    def test_disable_wrong_password(self, client, db_session, voter_user):
        voter_user.totp_secret = pyotp.random_base32()
        voter_user.totp_enabled = True
        voter_user.hashed_password = hash_password("Voter@pass1")
        db_session.commit()

        resp = client.post(
            "/auth/mfa/disable",
            json={"password": "wrong"},
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 400
        assert "incorrect password" in resp.json()["detail"].lower()

    def test_disable_when_not_enabled(self, client, voter_user):
        resp = client.post(
            "/auth/mfa/disable",
            json={"password": "anything"},
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 400
        assert "not enabled" in resp.json()["detail"].lower()


class TestLoginWithMFA:

    def _enable_mfa(self, db_session, user, password="User@pass1"):
        secret = pyotp.random_base32()
        user.totp_secret = secret
        user.totp_enabled = True
        user.hashed_password = hash_password(password)
        db_session.commit()
        return secret

    def test_login_returns_mfa_required(self, client, db_session):
        user = _create_user_with_password(
            db_session, "mfa@example.com", "mfauser", "Mfa@pass1", UserRole.VOTER
        )
        self._enable_mfa(db_session, user, "Mfa@pass1")

        resp = client.post(
            "/auth/login",
            data={"username": "mfauser", "password": "Mfa@pass1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mfa_required"] is True
        assert data["mfa_token"]
        assert data["access_token"] == ""

    def test_login_without_mfa_unchanged(self, client, voter_user):
        resp = client.post(
            "/auth/login",
            data={"username": "voter", "password": "Voter@pass1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("mfa_required") is not True
        assert data["access_token"]


class TestMFAChallenge:

    def _login_get_mfa_token(self, client, username, password):
        resp = client.post(
            "/auth/login",
            data={"username": username, "password": password},
        )
        return resp.json()["mfa_token"]

    def test_challenge_success(self, client, db_session):
        user = _create_user_with_password(
            db_session, "chal@example.com", "chaluser", "Chal@pass1", UserRole.VOTER
        )
        secret = pyotp.random_base32()
        user.totp_secret = secret
        user.totp_enabled = True
        db_session.commit()

        mfa_token = self._login_get_mfa_token(client, "chaluser", "Chal@pass1")
        code = pyotp.TOTP(secret).now()

        resp = client.post(
            "/auth/mfa/challenge",
            json={"mfa_token": mfa_token, "code": code},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"]
        assert data["token_type"] == "bearer"

    def test_challenge_wrong_code(self, client, db_session):
        user = _create_user_with_password(
            db_session, "chal2@example.com", "chaluser2", "Chal@pass1", UserRole.VOTER
        )
        user.totp_secret = pyotp.random_base32()
        user.totp_enabled = True
        db_session.commit()

        mfa_token = self._login_get_mfa_token(client, "chaluser2", "Chal@pass1")

        resp = client.post(
            "/auth/mfa/challenge",
            json={"mfa_token": mfa_token, "code": "000000"},
        )
        assert resp.status_code == 400
        assert "invalid" in resp.json()["detail"].lower()

    def test_challenge_expired_token(self, client, db_session):
        from datetime import timedelta

        user = _create_user_with_password(
            db_session, "chal3@example.com", "chaluser3", "Chal@pass1", UserRole.VOTER
        )
        secret = pyotp.random_base32()
        user.totp_secret = secret
        user.totp_enabled = True
        db_session.commit()

        expired_token = create_access_token(
            data={"sub": "chaluser3", "user_id": user.id, "purpose": "mfa"},
            expires_delta=timedelta(seconds=-1),
        )

        code = pyotp.TOTP(secret).now()
        resp = client.post(
            "/auth/mfa/challenge",
            json={"mfa_token": expired_token, "code": code},
        )
        assert resp.status_code == 401

    def test_challenge_regular_token_rejected(self, client, db_session):
        user = _create_user_with_password(
            db_session, "chal4@example.com", "chaluser4", "Chal@pass1", UserRole.VOTER
        )
        secret = pyotp.random_base32()
        user.totp_secret = secret
        user.totp_enabled = True
        db_session.commit()

        regular_token = create_access_token(
            data={"sub": "chaluser4", "user_id": user.id}
        )
        code = pyotp.TOTP(secret).now()

        resp = client.post(
            "/auth/mfa/challenge",
            json={"mfa_token": regular_token, "code": code},
        )
        assert resp.status_code == 401

    def test_challenge_garbage_token(self, client):
        resp = client.post(
            "/auth/mfa/challenge",
            json={"mfa_token": "not-a-real-token", "code": "123456"},
        )
        assert resp.status_code == 401


class TestUserResponseIncludesMFA:

    def test_me_shows_totp_enabled(self, client, db_session, voter_user):
        resp = client.get("/auth/me", headers=auth_headers(voter_user))
        assert resp.status_code == 200
        assert resp.json()["totp_enabled"] is False

        voter_user.totp_secret = pyotp.random_base32()
        voter_user.totp_enabled = True
        db_session.commit()

        resp = client.get("/auth/me", headers=auth_headers(voter_user))
        assert resp.json()["totp_enabled"] is True
