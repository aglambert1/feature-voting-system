"""
Tests for admin product assignment and registration invite code flow.

Covers:
- GET /auth/users/{user_id}/products (admin only)
- PUT /auth/users/{user_id}/products (admin only)
- Registration with invite code (self-registration)
- Registration via admin (no invite code required)
- Permission checks on all endpoints
"""

from app.models.competitor_intelligence import ProductPermission, ProductPermissionLevel
from conftest import auth_headers


# ============================================================================
# Admin Product Assignment — GET
# ============================================================================


class TestGetUserProducts:

    def test_admin_gets_user_products(self, client, admin_user, voter_user, test_product, voter_product_access):
        resp = client.get(
            f"/auth/users/{voter_user.id}/products",
            headers=auth_headers(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        product_ids = [p["product_id"] for p in data]
        assert test_product.id in product_ids

    def test_returns_empty_for_user_with_no_products(self, client, admin_user, voter_user):
        resp = client.get(
            f"/auth/users/{voter_user.id}/products",
            headers=auth_headers(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_nonexistent_user(self, client, admin_user):
        resp = client.get(
            "/auth/users/99999/products",
            headers=auth_headers(admin_user),
        )
        assert resp.status_code == 404

    def test_voter_cannot_get_user_products(self, client, voter_user):
        resp = client.get(
            f"/auth/users/{voter_user.id}/products",
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 403

    def test_po_cannot_get_user_products(self, client, po_user, voter_user):
        resp = client.get(
            f"/auth/users/{voter_user.id}/products",
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 403

    def test_unauthenticated_cannot_get(self, client, voter_user):
        resp = client.get(f"/auth/users/{voter_user.id}/products")
        assert resp.status_code == 401


# ============================================================================
# Admin Product Assignment — PUT
# ============================================================================


class TestSetUserProducts:

    def test_admin_sets_user_products(self, client, db_session, admin_user, voter_user, test_product, second_product):
        resp = client.put(
            f"/auth/users/{voter_user.id}/products",
            json={"product_ids": [test_product.id, second_product.id]},
            headers=auth_headers(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        product_ids = sorted([p["product_id"] for p in data])
        assert product_ids == sorted([test_product.id, second_product.id])

    def test_replaces_existing_assignments(self, client, db_session, admin_user, voter_user, test_product, second_product, voter_product_access):
        """PUT replaces — setting to only second_product removes test_product."""
        resp = client.put(
            f"/auth/users/{voter_user.id}/products",
            json={"product_ids": [second_product.id]},
            headers=auth_headers(admin_user),
        )
        assert resp.status_code == 200
        product_ids = [p["product_id"] for p in resp.json()]
        assert second_product.id in product_ids
        assert test_product.id not in product_ids

    def test_empty_product_ids_removes_all(self, client, db_session, admin_user, voter_user, voter_product_access):
        resp = client.put(
            f"/auth/users/{voter_user.id}/products",
            json={"product_ids": []},
            headers=auth_headers(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_po_gets_edit_permission(self, client, db_session, admin_user, po_user, test_product):
        """When assigning products to a PO, permission level should be EDIT."""
        # po_user already created the product, so use a different PO
        from app.models.user import User, UserRole
        from app.utils.security import hash_password

        new_po = User(
            email="newpo@example.com",
            username="newpo",
            hashed_password=hash_password("pass123"),
            role=UserRole.PRODUCT_OWNER,
        )
        db_session.add(new_po)
        db_session.commit()
        db_session.refresh(new_po)

        resp = client.put(
            f"/auth/users/{new_po.id}/products",
            json={"product_ids": [test_product.id]},
            headers=auth_headers(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["permission_level"] == "edit"

    def test_voter_gets_view_permission(self, client, admin_user, voter_user, test_product):
        resp = client.put(
            f"/auth/users/{voter_user.id}/products",
            json={"product_ids": [test_product.id]},
            headers=auth_headers(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["permission_level"] == "view"

    def test_cannot_modify_own_products(self, client, admin_user):
        resp = client.put(
            f"/auth/users/{admin_user.id}/products",
            json={"product_ids": []},
            headers=auth_headers(admin_user),
        )
        assert resp.status_code == 400
        assert "own" in resp.json()["detail"].lower()

    def test_nonexistent_user(self, client, admin_user):
        resp = client.put(
            "/auth/users/99999/products",
            json={"product_ids": []},
            headers=auth_headers(admin_user),
        )
        assert resp.status_code == 404

    def test_ignores_nonexistent_product_ids(self, client, admin_user, voter_user, test_product):
        """Non-existent product IDs are silently skipped."""
        resp = client.put(
            f"/auth/users/{voter_user.id}/products",
            json={"product_ids": [test_product.id, 99999]},
            headers=auth_headers(admin_user),
        )
        assert resp.status_code == 200
        product_ids = [p["product_id"] for p in resp.json()]
        assert test_product.id in product_ids
        assert 99999 not in product_ids

    def test_voter_cannot_set_products(self, client, voter_user):
        resp = client.put(
            f"/auth/users/{voter_user.id}/products",
            json={"product_ids": []},
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 403

    def test_po_cannot_set_products(self, client, po_user, voter_user):
        resp = client.put(
            f"/auth/users/{voter_user.id}/products",
            json={"product_ids": []},
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 403

    def test_unauthenticated_cannot_set(self, client, voter_user):
        resp = client.put(
            f"/auth/users/{voter_user.id}/products",
            json={"product_ids": []},
        )
        assert resp.status_code == 401


# ============================================================================
# Registration with Invite Code
# ============================================================================


class TestRegistrationWithInviteCode:

    def test_self_register_with_valid_code(self, client, db_session, test_invite_code, test_product):
        resp = client.post("/auth/register", json={
            "email": "invitee@example.com",
            "username": "invitee",
            "password": "securepass123",
            "full_name": "Invited User",
            "invite_code": test_invite_code.code,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "invitee"
        assert data["role"] == "voter"

        # Verify product access was granted
        perm = db_session.query(ProductPermission).filter(
            ProductPermission.user_id == data["id"],
            ProductPermission.product_id == test_product.id,
        ).first()
        assert perm is not None
        assert perm.permission_level == ProductPermissionLevel.VIEW

        # Verify invite code usage incremented
        db_session.refresh(test_invite_code)
        assert test_invite_code.current_uses == 1

    def test_self_register_without_code_fails(self, client):
        resp = client.post("/auth/register", json={
            "email": "nocode@example.com",
            "username": "nocode",
            "password": "securepass123",
        })
        assert resp.status_code == 400
        assert "invite code" in resp.json()["detail"].lower()

    def test_self_register_with_invalid_code(self, client):
        resp = client.post("/auth/register", json={
            "email": "badcode@example.com",
            "username": "badcode",
            "password": "securepass123",
            "invite_code": "INVALID_CODE",
        })
        assert resp.status_code == 400
        assert "invalid" in resp.json()["detail"].lower()

    def test_self_register_with_deactivated_code(self, client, db_session, test_invite_code):
        test_invite_code.is_active = False
        db_session.commit()

        resp = client.post("/auth/register", json={
            "email": "deactivated@example.com",
            "username": "deactivated",
            "password": "securepass123",
            "invite_code": test_invite_code.code,
        })
        assert resp.status_code == 400

    def test_admin_creates_user_without_code(self, client, admin_user, test_product):
        resp = client.post("/auth/register", json={
            "email": "adminmade@example.com",
            "username": "adminmade",
            "password": "securepass123",
            "full_name": "Admin Made",
            "product_ids": [test_product.id],
        }, headers=auth_headers(admin_user))
        assert resp.status_code == 201
        assert resp.json()["username"] == "adminmade"

    def test_admin_creates_user_with_product_access(self, client, db_session, admin_user, test_product, second_product):
        resp = client.post("/auth/register", json={
            "email": "multiproduct@example.com",
            "username": "multiproduct",
            "password": "securepass123",
            "product_ids": [test_product.id, second_product.id],
        }, headers=auth_headers(admin_user))
        assert resp.status_code == 201
        new_user_id = resp.json()["id"]

        perms = db_session.query(ProductPermission).filter(
            ProductPermission.user_id == new_user_id,
        ).all()
        assert len(perms) == 2
        product_ids = sorted([p.product_id for p in perms])
        assert product_ids == sorted([test_product.id, second_product.id])

    def test_admin_creates_po_with_edit_permission(self, client, db_session, admin_user, test_product):
        resp = client.post("/auth/register", json={
            "email": "newpo2@example.com",
            "username": "newpo2",
            "password": "securepass123",
            "role": "product_owner",
            "product_ids": [test_product.id],
        }, headers=auth_headers(admin_user))
        assert resp.status_code == 201
        new_user_id = resp.json()["id"]

        perm = db_session.query(ProductPermission).filter(
            ProductPermission.user_id == new_user_id,
            ProductPermission.product_id == test_product.id,
        ).first()
        assert perm is not None
        assert perm.permission_level == ProductPermissionLevel.EDIT

    def test_po_auth_header_does_not_bypass_invite_code(self, client, po_user):
        """A PO's auth header should NOT bypass the invite code requirement."""
        resp = client.post("/auth/register", json={
            "email": "pobypass@example.com",
            "username": "pobypass",
            "password": "securepass123",
        }, headers=auth_headers(po_user))
        assert resp.status_code == 400
        assert "invite code" in resp.json()["detail"].lower()

    def test_voter_auth_header_does_not_bypass_invite_code(self, client, voter_user):
        """A voter's auth header should NOT bypass the invite code requirement."""
        resp = client.post("/auth/register", json={
            "email": "voterbypass@example.com",
            "username": "voterbypass",
            "password": "securepass123",
        }, headers=auth_headers(voter_user))
        assert resp.status_code == 400
        assert "invite code" in resp.json()["detail"].lower()
