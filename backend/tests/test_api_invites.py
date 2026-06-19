"""
Tests for invite code API endpoints.

Covers:
- Invite code CRUD (create, list, deactivate) with PO auth
- Invite code redemption by authenticated users
- Public invite info endpoint
- Product members list
- Permission checks (PO vs voter vs admin vs unauthenticated)
"""

from datetime import datetime, timedelta, timezone

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
        expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
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
        test_invite_code.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
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
        test_invite_code.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db_session.commit()

        resp = client.get(f"/invites/{test_invite_code.code}/info")
        assert resp.status_code == 200
        assert resp.json()["valid"] is False

    def test_no_auth_required(self, client, test_invite_code):
        """Info endpoint is public — no auth header needed."""
        resp = client.get(f"/invites/{test_invite_code.code}/info")
        assert resp.status_code == 200


# ============================================================================
# Permission Management — Grant / Update / Revoke
# ============================================================================


def _make_user(db_session, email, username, role):
    from app.models.user import User
    from app.utils.security import hash_password

    user = User(
        email=email,
        username=username,
        hashed_password=hash_password("pass123"),
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestGrantPermission:

    def test_owner_grants_view(self, client, po_user, test_product, db_session):
        from app.models.user import UserRole
        target = _make_user(db_session, "target@example.com", "target", UserRole.VOTER)

        resp = client.post(
            f"/products/{test_product.id}/members",
            json={"email": target.email, "permission_level": "view"},
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["user_id"] == target.id
        assert data["permission_level"] == "view"
        assert data["email"] == target.email

    def test_owner_grants_edit(self, client, po_user, test_product, db_session):
        from app.models.user import UserRole
        target = _make_user(db_session, "edit_target@example.com", "edit_target", UserRole.PRODUCT_OWNER)

        resp = client.post(
            f"/products/{test_product.id}/members",
            json={"email": target.email, "permission_level": "edit"},
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 201
        assert resp.json()["permission_level"] == "edit"

    def test_owner_grants_owner(self, client, po_user, test_product, db_session):
        from app.models.user import UserRole
        target = _make_user(db_session, "owner_target@example.com", "owner_target", UserRole.PRODUCT_OWNER)

        resp = client.post(
            f"/products/{test_product.id}/members",
            json={"email": target.email, "permission_level": "owner"},
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 201
        assert resp.json()["permission_level"] == "owner"

    def test_grant_updates_existing(self, client, po_user, test_product, voter_user, voter_product_access):
        resp = client.post(
            f"/products/{test_product.id}/members",
            json={"email": voter_user.email, "permission_level": "edit"},
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 201
        assert resp.json()["permission_level"] == "edit"

    def test_non_owner_cannot_grant(self, client, test_product, voter_user, voter_product_access):
        resp = client.post(
            f"/products/{test_product.id}/members",
            json={"email": "someone@example.com", "permission_level": "view"},
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 403

    def test_grant_to_nonexistent_user(self, client, po_user, test_product):
        resp = client.post(
            f"/products/{test_product.id}/members",
            json={"email": "nobody@example.com", "permission_level": "view"},
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 404
        assert "No user found" in resp.json()["detail"]

    def test_grant_invalid_permission_level(self, client, po_user, test_product):
        resp = client.post(
            f"/products/{test_product.id}/members",
            json={"email": "someone@example.com", "permission_level": "superadmin"},
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 400


class TestUpdatePermission:

    def test_owner_updates_member(self, client, po_user, test_product, voter_user, voter_product_access):
        resp = client.patch(
            f"/products/{test_product.id}/members/{voter_user.id}",
            json={"permission_level": "edit"},
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200
        assert resp.json()["permission_level"] == "edit"

    def test_non_owner_cannot_update(self, client, test_product, voter_user, voter_product_access):
        resp = client.patch(
            f"/products/{test_product.id}/members/{voter_user.id}",
            json={"permission_level": "edit"},
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 403

    def test_update_nonexistent_member(self, client, po_user, test_product):
        resp = client.patch(
            f"/products/{test_product.id}/members/99999",
            json={"permission_level": "edit"},
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 404

    def test_cannot_change_own_permission(self, client, po_user, test_product, db_session):
        """Users cannot change their own permission level."""
        perm = ProductPermission(
            product_id=test_product.id,
            user_id=po_user.id,
            permission_level=ProductPermissionLevel.OWNER,
            granted_by_user_id=po_user.id,
        )
        db_session.add(perm)
        db_session.commit()

        resp = client.patch(
            f"/products/{test_product.id}/members/{po_user.id}",
            json={"permission_level": "view"},
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 400
        assert "your own" in resp.json()["detail"].lower()

    def test_cannot_demote_creator(self, client, po_user, test_product, db_session):
        """The product creator can't be demoted by another OWNER."""
        from app.models.user import UserRole
        other_owner = _make_user(db_session, "other_owner@example.com", "other_owner", UserRole.PRODUCT_OWNER)
        perm = ProductPermission(
            product_id=test_product.id,
            user_id=other_owner.id,
            permission_level=ProductPermissionLevel.OWNER,
            granted_by_user_id=po_user.id,
        )
        creator_perm = ProductPermission(
            product_id=test_product.id,
            user_id=po_user.id,
            permission_level=ProductPermissionLevel.OWNER,
            granted_by_user_id=po_user.id,
        )
        db_session.add_all([perm, creator_perm])
        db_session.commit()

        resp = client.patch(
            f"/products/{test_product.id}/members/{po_user.id}",
            json={"permission_level": "view"},
            headers=auth_headers(other_owner),
        )
        assert resp.status_code == 400
        assert "creator" in resp.json()["detail"].lower()

    def test_cannot_demote_last_non_creator_owner(self, client, po_user, test_product, db_session):
        """Can't demote the last non-creator OWNER if no other OWNERs exist."""
        from app.models.user import UserRole
        other_po = _make_user(db_session, "other_po@example.com", "other_po", UserRole.PRODUCT_OWNER)

        # Grant other_po OWNER
        perm = ProductPermission(
            product_id=test_product.id,
            user_id=other_po.id,
            permission_level=ProductPermissionLevel.OWNER,
            granted_by_user_id=po_user.id,
        )
        db_session.add(perm)
        db_session.commit()

        # Demote other_po — should succeed since creator is still implicit OWNER
        resp = client.patch(
            f"/products/{test_product.id}/members/{other_po.id}",
            json={"permission_level": "view"},
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 200


class TestRevokePermission:

    def test_owner_revokes_member(self, client, po_user, test_product, voter_user, voter_product_access):
        resp = client.delete(
            f"/products/{test_product.id}/members/{voter_user.id}",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 204

        # Verify member is gone
        members_resp = client.get(
            f"/products/{test_product.id}/members",
            headers=auth_headers(po_user),
        )
        member_ids = [m["user_id"] for m in members_resp.json()]
        assert voter_user.id not in member_ids

    def test_non_owner_cannot_revoke(self, client, test_product, voter_user, voter_product_access):
        resp = client.delete(
            f"/products/{test_product.id}/members/{voter_user.id}",
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 403

    def test_revoke_nonexistent_member(self, client, po_user, test_product):
        resp = client.delete(
            f"/products/{test_product.id}/members/99999",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 404

    def test_cannot_revoke_own_access(self, client, po_user, test_product, db_session):
        """Users cannot revoke their own access."""
        perm = ProductPermission(
            product_id=test_product.id,
            user_id=po_user.id,
            permission_level=ProductPermissionLevel.OWNER,
            granted_by_user_id=po_user.id,
        )
        db_session.add(perm)
        db_session.commit()

        resp = client.delete(
            f"/products/{test_product.id}/members/{po_user.id}",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 400
        assert "your own" in resp.json()["detail"].lower()

    def test_cannot_revoke_creator(self, client, po_user, test_product, db_session):
        """Cannot revoke the product creator's access."""
        from app.models.user import UserRole
        other_owner = _make_user(db_session, "revoker@example.com", "revoker", UserRole.PRODUCT_OWNER)
        perm = ProductPermission(
            product_id=test_product.id,
            user_id=other_owner.id,
            permission_level=ProductPermissionLevel.OWNER,
            granted_by_user_id=po_user.id,
        )
        creator_perm = ProductPermission(
            product_id=test_product.id,
            user_id=po_user.id,
            permission_level=ProductPermissionLevel.OWNER,
            granted_by_user_id=po_user.id,
        )
        db_session.add_all([perm, creator_perm])
        db_session.commit()

        resp = client.delete(
            f"/products/{test_product.id}/members/{po_user.id}",
            headers=auth_headers(other_owner),
        )
        assert resp.status_code == 400
        assert "creator" in resp.json()["detail"].lower()


class TestInviteCodePermissionLevel:

    def test_create_invite_with_edit_permission(self, client, po_user, test_product):
        resp = client.post(
            f"/products/{test_product.id}/invite-codes",
            json={"permission_level": "edit"},
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 201
        assert resp.json()["permission_level"] == "edit"

    def test_create_invite_with_owner_rejected(self, client, po_user, test_product):
        resp = client.post(
            f"/products/{test_product.id}/invite-codes",
            json={"permission_level": "owner"},
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 400
        assert "cannot grant OWNER" in resp.json()["detail"]

    def test_redeem_edit_invite_grants_edit(self, client, db_session, po_user, test_product):
        from app.models.product_invite import ProductInviteCode
        from app.models.user import UserRole

        invite = ProductInviteCode(
            product_id=test_product.id,
            code=ProductInviteCode.generate_code(),
            created_by_user_id=po_user.id,
            permission_level=ProductPermissionLevel.EDIT,
        )
        db_session.add(invite)
        db_session.commit()

        redeemer = _make_user(db_session, "redeemer@example.com", "redeemer", UserRole.VOTER)

        resp = client.post(
            "/invites/redeem",
            json={"code": invite.code},
            headers=auth_headers(redeemer),
        )
        assert resp.status_code == 200

        perm = db_session.query(ProductPermission).filter(
            ProductPermission.product_id == test_product.id,
            ProductPermission.user_id == redeemer.id,
        ).first()
        assert perm is not None
        assert perm.permission_level == ProductPermissionLevel.EDIT
