"""
Tests for invite code API endpoints.

Covers:
- Invite code CRUD (create, list, deactivate) with PO auth
- Invite code redemption by authenticated users
- Public invite info endpoint
- Product members list
- Permission checks (PO vs voter vs admin vs unauthenticated)
"""

from datetime import datetime, timedelta

from app.models.product_invite import ProductInviteCode
from app.models.competitor_intelligence import ProductPermission, ProductPermissionLevel
from conftest import auth_headers


# ============================================================================
# Invite Code CRUD — PO endpoints
# ============================================================================


class TestCreateInviteCode:

    def test_po_creates_invite_code(self, client, po_user, test_product):
        resp = client.post(
            f"/products/{test_product.id}/invite-codes",
            json={},
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["product_id"] == test_product.id
        assert data["is_active"] is True
        assert data["current_uses"] == 0
        assert data["max_uses"] is None
        assert data["expires_at"] is None
        assert data["permission_level"] == "view"
        assert len(data["code"]) > 0
        assert data["invite_url"] == f"/join/{data['code']}"

    def test_create_with_max_uses(self, client, po_user, test_product):
        resp = client.post(
            f"/products/{test_product.id}/invite-codes",
            json={"max_uses": 5},
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 201
        assert resp.json()["max_uses"] == 5

    def test_create_with_expiration(self, client, po_user, test_product):
        expires = (datetime.utcnow() + timedelta(days=7)).isoformat()
        resp = client.post(
            f"/products/{test_product.id}/invite-codes",
            json={"expires_at": expires},
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 201
        assert resp.json()["expires_at"] is not None

    def test_voter_cannot_create_invite_code(self, client, voter_user, test_product, voter_product_access):
        resp = client.post(
            f"/products/{test_product.id}/invite-codes",
            json={},
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 403

    def test_unauthenticated_cannot_create(self, client, test_product):
        resp = client.post(
            f"/products/{test_product.id}/invite-codes",
            json={},
        )
        assert resp.status_code == 401

    def test_create_for_nonexistent_product(self, client, po_user):
        resp = client.post(
            "/products/99999/invite-codes",
            json={},
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 404

    def test_po_cannot_create_for_other_pos_product(self, client, db_session, test_product):
        """A PO who doesn't own or have EDIT access to a product cannot create codes."""
        from app.models.user import User, UserRole
        from app.utils.security import hash_password

        other_po = User(
            email="other_po@example.com",
            username="other_po",
            hashed_password=hash_password("pass123"),
            role=UserRole.PRODUCT_OWNER,
        )
        db_session.add(other_po)
        db_session.commit()
        db_session.refresh(other_po)

        resp = client.post(
            f"/products/{test_product.id}/invite-codes",
            json={},
            headers=auth_headers(other_po),
        )
        assert resp.status_code == 403


class TestListInviteCodes:

    def test_po_lists_codes(self, client, po_user, test_product, test_invite_code):
        resp = client.get(
            f"/products/{test_product.id}/invite-codes",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["product_id"] == test_product.id

    def test_list_returns_empty_when_no_codes(self, client, po_user, test_product):
        resp = client.get(
            f"/products/{test_product.id}/invite-codes",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_voter_cannot_list_codes(self, client, voter_user, test_product, voter_product_access):
        resp = client.get(
            f"/products/{test_product.id}/invite-codes",
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 403

    def test_unauthenticated_cannot_list(self, client, test_product):
        resp = client.get(f"/products/{test_product.id}/invite-codes")
        assert resp.status_code == 401


class TestDeactivateInviteCode:

    def test_po_deactivates_code(self, client, po_user, test_product, test_invite_code):
        resp = client.delete(
            f"/products/{test_product.id}/invite-codes/{test_invite_code.id}",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 204

        # Verify it's deactivated
        list_resp = client.get(
            f"/products/{test_product.id}/invite-codes",
            headers=auth_headers(po_user),
        )
        codes = list_resp.json()
        deactivated = [c for c in codes if c["id"] == test_invite_code.id]
        assert len(deactivated) == 1
        assert deactivated[0]["is_active"] is False

    def test_deactivate_nonexistent_code(self, client, po_user, test_product):
        resp = client.delete(
            f"/products/{test_product.id}/invite-codes/99999",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 404

    def test_voter_cannot_deactivate(self, client, voter_user, test_product, test_invite_code, voter_product_access):
        resp = client.delete(
            f"/products/{test_product.id}/invite-codes/{test_invite_code.id}",
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 403

    def test_unauthenticated_cannot_deactivate(self, client, test_product, test_invite_code):
        resp = client.delete(
            f"/products/{test_product.id}/invite-codes/{test_invite_code.id}",
        )
        assert resp.status_code == 401


# ============================================================================
# Product Members
# ============================================================================


class TestProductMembers:

    def test_po_lists_members(self, client, po_user, test_product, voter_user, voter_product_access):
        resp = client.get(
            f"/products/{test_product.id}/members",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        usernames = [m["username"] for m in data]
        assert voter_user.username in usernames

    def test_members_shows_permission_level(self, client, po_user, test_product, voter_product_access):
        resp = client.get(
            f"/products/{test_product.id}/members",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all("permission_level" in m for m in data)
        assert all("granted_at" in m for m in data)

    def test_empty_members(self, client, po_user, test_product):
        resp = client.get(
            f"/products/{test_product.id}/members",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_voter_cannot_list_members(self, client, voter_user, test_product, voter_product_access):
        resp = client.get(
            f"/products/{test_product.id}/members",
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 403

    def test_unauthenticated_cannot_list_members(self, client, test_product):
        resp = client.get(f"/products/{test_product.id}/members")
        assert resp.status_code == 401


# ============================================================================
# Invite Code Redemption
# ============================================================================


class TestRedeemInviteCode:

    def test_voter_redeems_code(self, client, db_session, voter_user, test_product, test_invite_code):
        resp = client.post(
            "/invites/redeem",
            json={"code": test_invite_code.code},
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["product_id"] == test_product.id
        assert data["product_name"] == test_product.product_name
        assert "access" in data["message"].lower()

        # Verify permission was created
        perm = db_session.query(ProductPermission).filter(
            ProductPermission.user_id == voter_user.id,
            ProductPermission.product_id == test_product.id,
        ).first()
        assert perm is not None
        assert perm.permission_level == ProductPermissionLevel.VIEW

        # Verify usage was incremented
        db_session.refresh(test_invite_code)
        assert test_invite_code.current_uses == 1

    def test_redeem_already_has_access(self, client, voter_user, test_product, test_invite_code, voter_product_access):
        """Redeeming when user already has access returns success without error."""
        resp = client.post(
            "/invites/redeem",
            json={"code": test_invite_code.code},
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 200
        assert "already" in resp.json()["message"].lower()

    def test_redeem_invalid_code(self, client, voter_user):
        resp = client.post(
            "/invites/redeem",
            json={"code": "NONEXISTENT_CODE"},
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 404

    def test_redeem_deactivated_code(self, client, db_session, voter_user, test_invite_code):
        test_invite_code.is_active = False
        db_session.commit()

        resp = client.post(
            "/invites/redeem",
            json={"code": test_invite_code.code},
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 400
        assert "deactivated" in resp.json()["detail"].lower()

    def test_redeem_expired_code(self, client, db_session, voter_user, test_invite_code):
        test_invite_code.expires_at = datetime.utcnow() - timedelta(hours=1)
        db_session.commit()

        resp = client.post(
            "/invites/redeem",
            json={"code": test_invite_code.code},
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 400
        assert "expired" in resp.json()["detail"].lower()

    def test_redeem_maxed_out_code(self, client, db_session, voter_user, test_invite_code):
        test_invite_code.max_uses = 1
        test_invite_code.current_uses = 1
        db_session.commit()

        resp = client.post(
            "/invites/redeem",
            json={"code": test_invite_code.code},
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 400
        assert "usage limit" in resp.json()["detail"].lower()

    def test_unauthenticated_cannot_redeem(self, client, test_invite_code):
        resp = client.post(
            "/invites/redeem",
            json={"code": test_invite_code.code},
        )
        assert resp.status_code == 401


# ============================================================================
# Public Invite Info
# ============================================================================


class TestInviteInfo:

    def test_valid_code_returns_product_info(self, client, test_invite_code, test_product):
        resp = client.get(f"/invites/{test_invite_code.code}/info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["product_name"] == test_product.product_name
        assert test_product.product_name in data["message"]

    def test_invalid_code(self, client):
        resp = client.get("/invites/NONEXISTENT_CODE/info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert data["product_name"] is None

    def test_deactivated_code_shows_invalid(self, client, db_session, test_invite_code):
        test_invite_code.is_active = False
        db_session.commit()

        resp = client.get(f"/invites/{test_invite_code.code}/info")
        assert resp.status_code == 200
        assert resp.json()["valid"] is False

    def test_expired_code_shows_invalid(self, client, db_session, test_invite_code):
        test_invite_code.expires_at = datetime.utcnow() - timedelta(hours=1)
        db_session.commit()

        resp = client.get(f"/invites/{test_invite_code.code}/info")
        assert resp.status_code == 200
        assert resp.json()["valid"] is False

    def test_no_auth_required(self, client, test_invite_code):
        """Info endpoint is public — no auth header needed."""
        resp = client.get(f"/invites/{test_invite_code.code}/info")
        assert resp.status_code == 200
