"""Tests for the VOTER role edit gate (R1) and admin API-key access (R2).

VOTER role is capped at VIEW everywhere: an explicit EDIT/OWNER grant — or
even product creatorship — never lets a VOTER pass an EDIT/OWNER permission
check. Only PRODUCT_OWNER/ADMIN roles can edit; VOTER keeps submit / vote /
comment / read access, which are all VIEW-gated.
"""

import pytest
from conftest import auth_headers

from app.models.competitor_intelligence import (
    CIProduct,
    ProductPermission,
    ProductPermissionLevel,
)
from app.models.user import User, UserRole
from app.services.permission_service import PermissionService
from app.utils.security import hash_password


def _grant(db_session, product, user, level):
    perm = ProductPermission(
        product_id=product.id,
        user_id=user.id,
        permission_level=level,
        granted_by_user_id=product.created_by_user_id,
    )
    db_session.add(perm)
    db_session.commit()
    return perm


@pytest.fixture
def second_po_user(db_session):
    """A PRODUCT_OWNER who did not create test_product (no implicit OWNER)."""
    user = User(
        email="po2@example.com",
        username="po2",
        hashed_password=hash_password("Owner@pass2"),
        full_name="Second PO",
        role=UserRole.PRODUCT_OWNER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestVoterRoleGateUnit:
    """PermissionService.can_access_product caps VOTER at VIEW."""

    def test_voter_with_edit_grant_denied_edit_allowed_view(
        self, db_session, test_product, voter_user
    ):
        _grant(db_session, test_product, voter_user, ProductPermissionLevel.EDIT)
        svc = PermissionService(db_session)
        assert not svc.can_access_product(
            voter_user.id, test_product.id, ProductPermissionLevel.EDIT
        )
        assert svc.can_access_product(
            voter_user.id, test_product.id, ProductPermissionLevel.VIEW
        )

    def test_voter_with_owner_grant_denied_owner_and_edit(
        self, db_session, test_product, voter_user
    ):
        _grant(db_session, test_product, voter_user, ProductPermissionLevel.OWNER)
        svc = PermissionService(db_session)
        assert not svc.can_access_product(
            voter_user.id, test_product.id, ProductPermissionLevel.OWNER
        )
        assert not svc.can_access_product(
            voter_user.id, test_product.id, ProductPermissionLevel.EDIT
        )
        assert svc.can_access_product(
            voter_user.id, test_product.id, ProductPermissionLevel.VIEW
        )

    def test_voter_product_creator_capped_at_view(self, db_session, voter_user):
        product = CIProduct(
            product_name="Voter Created Product",
            product_description="Created before a role downgrade",
            product_category="Testing",
            created_by_user_id=voter_user.id,
            status="active",
        )
        db_session.add(product)
        db_session.commit()
        svc = PermissionService(db_session)
        assert svc.can_access_product(
            voter_user.id, product.id, ProductPermissionLevel.VIEW
        )
        assert not svc.can_access_product(
            voter_user.id, product.id, ProductPermissionLevel.EDIT
        )

    def test_po_with_edit_grant_allowed_edit(
        self, db_session, test_product, second_po_user
    ):
        _grant(db_session, test_product, second_po_user, ProductPermissionLevel.EDIT)
        svc = PermissionService(db_session)
        assert svc.can_access_product(
            second_po_user.id, test_product.id, ProductPermissionLevel.EDIT
        )

    def test_admin_with_edit_grant_allowed_edit(
        self, db_session, test_product, admin_user
    ):
        _grant(db_session, test_product, admin_user, ProductPermissionLevel.EDIT)
        svc = PermissionService(db_session)
        assert svc.can_access_product(
            admin_user.id, test_product.id, ProductPermissionLevel.EDIT
        )

    def test_get_accessible_products_voter_empty_at_edit_level(
        self, db_session, test_product, voter_user
    ):
        _grant(db_session, test_product, voter_user, ProductPermissionLevel.EDIT)
        svc = PermissionService(db_session)
        assert svc.get_accessible_products(
            voter_user.id, ProductPermissionLevel.EDIT
        ) == []
        view_products = svc.get_accessible_products(
            voter_user.id, ProductPermissionLevel.VIEW
        )
        assert [p.id for p in view_products] == [test_product.id]


class TestVoterRoleGateAPI:
    """EDIT-gated endpoints reject a VOTER even with an explicit EDIT grant."""

    def test_voter_with_edit_grant_cannot_update_product(
        self, client, db_session, test_product, voter_user
    ):
        _grant(db_session, test_product, voter_user, ProductPermissionLevel.EDIT)
        resp = client.patch(
            f"/product-intelligence/products/{test_product.id}",
            json={"product_name": "Renamed by voter"},
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 403

    def test_voter_with_edit_grant_cannot_read_pm_review_queue(
        self, client, db_session, test_product, voter_user
    ):
        _grant(db_session, test_product, voter_user, ProductPermissionLevel.EDIT)
        resp = client.get(
            "/pm-review/queue",
            params={"product_id": test_product.id},
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 403

    def test_po_with_edit_grant_can_read_pm_review_queue(
        self, client, db_session, test_product, second_po_user
    ):
        _grant(db_session, test_product, second_po_user, ProductPermissionLevel.EDIT)
        resp = client.get(
            "/pm-review/queue",
            params={"product_id": test_product.id},
            headers=auth_headers(second_po_user),
        )
        assert resp.status_code == 200

    def test_voter_with_edit_grant_can_still_vote(
        self, client, db_session, voter_user, test_idea, voter_product_access
    ):
        # test_idea's fixture already grants VIEW; upgrade it to EDIT
        voter_product_access.permission_level = ProductPermissionLevel.EDIT
        db_session.commit()
        resp = client.post(
            f"/ideas/{test_idea.id}/vote",
            json={"vote_value": 1},
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 200

    def test_voter_with_edit_grant_can_still_comment(
        self, client, db_session, voter_user, test_idea, voter_product_access
    ):
        voter_product_access.permission_level = ProductPermissionLevel.EDIT
        db_session.commit()
        resp = client.post(
            f"/ideas/{test_idea.id}/comments",
            json={"comment_text": "Voter comment still works"},
            headers=auth_headers(voter_user),
        )
        assert resp.status_code in (200, 201)


class TestAdminAPIKeys:
    """R2: API-key management allows PRODUCT_OWNER or ADMIN, rejects VOTER."""

    def test_admin_can_create_api_key(self, client, admin_user):
        resp = client.post(
            "/api-keys",
            json={"name": "admin key"},
            headers=auth_headers(admin_user),
        )
        assert resp.status_code == 201
        assert resp.json()["api_key"].startswith("fiq_")

    def test_po_can_create_api_key(self, client, po_user):
        resp = client.post(
            "/api-keys",
            json={"name": "po key"},
            headers=auth_headers(po_user),
        )
        assert resp.status_code == 201

    def test_voter_cannot_create_api_key(self, client, voter_user):
        resp = client.post(
            "/api-keys",
            json={"name": "voter key"},
            headers=auth_headers(voter_user),
        )
        assert resp.status_code == 403

    def test_admin_can_list_and_revoke_own_keys(self, client, admin_user):
        created = client.post(
            "/api-keys",
            json={"name": "to revoke"},
            headers=auth_headers(admin_user),
        ).json()
        resp = client.get("/api-keys", headers=auth_headers(admin_user))
        assert resp.status_code == 200
        assert any(k["id"] == created["id"] for k in resp.json())

        resp = client.delete(
            f"/api-keys/{created['id']}", headers=auth_headers(admin_user)
        )
        assert resp.status_code == 200
