"""
Tests for multi-tenant isolation.

Verifies that users can only access data from products they have permission for.
Covers cross-tenant denial on ideas, products, and invite codes.
"""

from app.models.idea import Idea, IdeaStatus, SourceType
from app.models.user import User, UserRole
from app.models.competitor_intelligence import (
    CIProduct, ProductPermission, ProductPermissionLevel
)
from app.utils.security import hash_password
from conftest import auth_headers


def _make_user(db_session, email, username, role):
    """Helper to create a user with a hashed password."""
    user = User(
        email=email,
        username=username,
        hashed_password=hash_password("password123"),
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_product(db_session, name, owner_id):
    """Helper to create a product."""
    product = CIProduct(
        product_name=name,
        product_description=f"Description for {name}",
        product_category="Testing",
        created_by_user_id=owner_id,
        status="active",
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


def _grant_access(db_session, product_id, user_id, granted_by, level=ProductPermissionLevel.VIEW):
    """Helper to grant product access."""
    perm = ProductPermission(
        product_id=product_id,
        user_id=user_id,
        permission_level=level,
        granted_by_user_id=granted_by,
    )
    db_session.add(perm)
    db_session.commit()
    return perm


def _make_idea(db_session, title, product_id, submitter_id, status=IdeaStatus.ACCEPTED):
    """Helper to create an idea."""
    idea = Idea(
        title=title,
        what_description=f"What: {title}",
        why_description=f"Why: {title}",
        use_case_description=f"Use case: {title}",
        product_id=product_id,
        submitter_id=submitter_id,
        source_type=SourceType.CUSTOMER_SUBMISSION,
        status=status,
        is_active=True,
    )
    db_session.add(idea)
    db_session.commit()
    db_session.refresh(idea)
    return idea


# ============================================================================
# Cross-Tenant Idea Access
# ============================================================================


class TestIdeaCrossTenantIsolation:
    """Voters and POs should only see ideas from products they have access to."""

    def test_voter_cannot_get_idea_from_other_product(self, client, db_session):
        """GET /ideas/{id} returns 403 when voter has no access to the idea's product."""
        po_a = _make_user(db_session, "po_a@test.com", "po_a", UserRole.PRODUCT_OWNER)
        po_b = _make_user(db_session, "po_b@test.com", "po_b", UserRole.PRODUCT_OWNER)
        voter_a = _make_user(db_session, "voter_a@test.com", "voter_a", UserRole.VOTER)

        product_a = _make_product(db_session, "Product A", po_a.id)
        product_b = _make_product(db_session, "Product B", po_b.id)

        _grant_access(db_session, product_a.id, voter_a.id, po_a.id)
        idea_b = _make_idea(db_session, "Idea in Product B", product_b.id, po_b.id)

        resp = client.get(f"/ideas/{idea_b.id}", headers=auth_headers(voter_a))
        assert resp.status_code == 403

    def test_voter_can_get_idea_from_own_product(self, client, db_session):
        """GET /ideas/{id} returns 200 when voter has access to the idea's product."""
        po = _make_user(db_session, "po@test.com", "po_own", UserRole.PRODUCT_OWNER)
        voter = _make_user(db_session, "voter@test.com", "voter_own", UserRole.VOTER)

        product = _make_product(db_session, "My Product", po.id)
        _grant_access(db_session, product.id, voter.id, po.id)
        idea = _make_idea(db_session, "My Idea", product.id, voter.id)

        resp = client.get(f"/ideas/{idea.id}", headers=auth_headers(voter))
        assert resp.status_code == 200
        assert resp.json()["id"] == idea.id

    def test_po_cannot_get_idea_from_other_pos_product(self, client, db_session):
        """PO-A cannot access ideas in PO-B's product."""
        po_a = _make_user(db_session, "poa@test.com", "poa_iso", UserRole.PRODUCT_OWNER)
        po_b = _make_user(db_session, "pob@test.com", "pob_iso", UserRole.PRODUCT_OWNER)

        product_b = _make_product(db_session, "PO-B Product", po_b.id)
        idea_b = _make_idea(db_session, "PO-B Idea", product_b.id, po_b.id)

        resp = client.get(f"/ideas/{idea_b.id}", headers=auth_headers(po_a))
        assert resp.status_code == 403

    def test_admin_cannot_access_without_permission(self, client, db_session):
        """Admin without explicit product access is denied."""
        admin = _make_user(db_session, "admin@test.com", "admin_iso", UserRole.ADMIN)
        po = _make_user(db_session, "po_any@test.com", "po_any", UserRole.PRODUCT_OWNER)

        product = _make_product(db_session, "Any Product", po.id)
        idea = _make_idea(db_session, "Any Idea", product.id, po.id)

        resp = client.get(f"/ideas/{idea.id}", headers=auth_headers(admin))
        assert resp.status_code == 403


# ============================================================================
# Cross-Tenant Idea Listing
# ============================================================================


class TestIdeaListIsolation:
    """list_ideas should scope results by product permission."""

    def test_voter_only_sees_ideas_from_permitted_products(self, client, db_session):
        """Voter with access to Product-A should NOT see Product-B ideas in list."""
        po_a = _make_user(db_session, "list_poa@test.com", "list_poa", UserRole.PRODUCT_OWNER)
        po_b = _make_user(db_session, "list_pob@test.com", "list_pob", UserRole.PRODUCT_OWNER)
        voter = _make_user(db_session, "list_voter@test.com", "list_voter", UserRole.VOTER)

        product_a = _make_product(db_session, "List Product A", po_a.id)
        product_b = _make_product(db_session, "List Product B", po_b.id)

        _grant_access(db_session, product_a.id, voter.id, po_a.id)

        idea_a = _make_idea(db_session, "Idea A (visible)", product_a.id, po_a.id)
        _make_idea(db_session, "Idea B (hidden)", product_b.id, po_b.id)

        resp = client.get("/ideas/", headers=auth_headers(voter))
        assert resp.status_code == 200
        data = resp.json()
        idea_ids = [i["id"] for i in data["ideas"]]
        assert idea_a.id in idea_ids
        # Should NOT contain ideas from product_b
        for idea in data["ideas"]:
            assert idea["product_id"] != product_b.id

    def test_voter_with_no_permissions_sees_only_own_submissions(self, client, db_session):
        """Voter without any ProductPermission sees only their own submitted ideas."""
        po = _make_user(db_session, "noperm_po@test.com", "noperm_po", UserRole.PRODUCT_OWNER)
        voter = _make_user(db_session, "noperm_voter@test.com", "noperm_voter", UserRole.VOTER)

        product = _make_product(db_session, "Noperm Product", po.id)
        # Create an idea submitted by the voter (even without product access)
        own_idea = _make_idea(db_session, "Own Submission", product.id, voter.id, IdeaStatus.PENDING)

        # Create another idea the voter did NOT submit
        _make_idea(db_session, "Other Idea", product.id, po.id)

        resp = client.get("/ideas/", headers=auth_headers(voter))
        assert resp.status_code == 200
        data = resp.json()
        idea_ids = [i["id"] for i in data["ideas"]]
        assert own_idea.id in idea_ids
        # Should only contain their own submission
        for idea in data["ideas"]:
            assert idea["submitter_id"] == voter.id

    def test_voter_multi_product_sees_all_permitted(self, client, db_session):
        """Voter with access to Product-A and Product-C sees ideas from both."""
        po = _make_user(db_session, "multi_po@test.com", "multi_po", UserRole.PRODUCT_OWNER)
        voter = _make_user(db_session, "multi_voter@test.com", "multi_voter", UserRole.VOTER)

        product_a = _make_product(db_session, "Multi Product A", po.id)
        product_b = _make_product(db_session, "Multi Product B", po.id)
        product_c = _make_product(db_session, "Multi Product C", po.id)

        _grant_access(db_session, product_a.id, voter.id, po.id)
        _grant_access(db_session, product_c.id, voter.id, po.id)

        idea_a = _make_idea(db_session, "Multi A Idea", product_a.id, po.id)
        _make_idea(db_session, "Multi B Idea (hidden)", product_b.id, po.id)
        idea_c = _make_idea(db_session, "Multi C Idea", product_c.id, po.id)

        resp = client.get("/ideas/", headers=auth_headers(voter))
        assert resp.status_code == 200
        data = resp.json()
        idea_ids = [i["id"] for i in data["ideas"]]
        assert idea_a.id in idea_ids
        assert idea_c.id in idea_ids
        for idea in data["ideas"]:
            assert idea["product_id"] != product_b.id


# ============================================================================
# Cross-Tenant Product Listing
# ============================================================================


class TestProductListIsolation:
    """GET /ideas/products should return only permitted products per role."""

    def test_voter_only_sees_permitted_products(self, client, db_session):
        po_a = _make_user(db_session, "pliso_poa@test.com", "pliso_poa", UserRole.PRODUCT_OWNER)
        po_b = _make_user(db_session, "pliso_pob@test.com", "pliso_pob", UserRole.PRODUCT_OWNER)
        voter = _make_user(db_session, "pliso_voter@test.com", "pliso_voter", UserRole.VOTER)

        product_a = _make_product(db_session, "PLIso Product A", po_a.id)
        product_b = _make_product(db_session, "PLIso Product B", po_b.id)

        _grant_access(db_session, product_a.id, voter.id, po_a.id)

        resp = client.get("/ideas/products", headers=auth_headers(voter))
        assert resp.status_code == 200
        data = resp.json()
        product_ids = [p["id"] for p in data]
        assert product_a.id in product_ids
        assert product_b.id not in product_ids

    def test_voter_without_permissions_sees_no_products(self, client, db_session):
        po = _make_user(db_session, "plnone_po@test.com", "plnone_po", UserRole.PRODUCT_OWNER)
        voter = _make_user(db_session, "plnone_voter@test.com", "plnone_voter", UserRole.VOTER)

        _make_product(db_session, "PLNone Product", po.id)

        resp = client.get("/ideas/products", headers=auth_headers(voter))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_po_sees_own_and_granted_products(self, client, db_session):
        po_a = _make_user(db_session, "plpo_a@test.com", "plpo_a", UserRole.PRODUCT_OWNER)
        po_b = _make_user(db_session, "plpo_b@test.com", "plpo_b", UserRole.PRODUCT_OWNER)

        product_own = _make_product(db_session, "PO-A Own", po_a.id)
        product_granted = _make_product(db_session, "PO-B Granted", po_b.id)
        product_hidden = _make_product(db_session, "PO-B Hidden", po_b.id)

        _grant_access(db_session, product_granted.id, po_a.id, po_b.id, ProductPermissionLevel.EDIT)

        resp = client.get("/ideas/products", headers=auth_headers(po_a))
        assert resp.status_code == 200
        data = resp.json()
        product_ids = [p["id"] for p in data]
        assert product_own.id in product_ids
        assert product_granted.id in product_ids
        assert product_hidden.id not in product_ids

    def test_po_does_not_see_other_pos_products(self, client, db_session):
        po_a = _make_user(db_session, "pliso_a@test.com", "pliso_a", UserRole.PRODUCT_OWNER)
        po_b = _make_user(db_session, "pliso_b@test.com", "pliso_b", UserRole.PRODUCT_OWNER)

        _make_product(db_session, "PO-A Product", po_a.id)
        product_b = _make_product(db_session, "PO-B Product Only", po_b.id)

        resp = client.get("/ideas/products", headers=auth_headers(po_a))
        assert resp.status_code == 200
        product_ids = [p["id"] for p in resp.json()]
        assert product_b.id not in product_ids

    def test_admin_sees_only_permitted_products(self, client, db_session):
        admin = _make_user(db_session, "pladmin@test.com", "pladmin", UserRole.ADMIN)
        po_a = _make_user(db_session, "plall_a@test.com", "plall_a", UserRole.PRODUCT_OWNER)
        po_b = _make_user(db_session, "plall_b@test.com", "plall_b", UserRole.PRODUCT_OWNER)

        product_a = _make_product(db_session, "Admin Sees A", po_a.id)
        product_b = _make_product(db_session, "Admin Sees B", po_b.id)

        _grant_access(db_session, product_a.id, admin.id, admin.id, ProductPermissionLevel.OWNER)

        resp = client.get("/ideas/products", headers=auth_headers(admin))
        assert resp.status_code == 200
        product_ids = [p["id"] for p in resp.json()]
        assert product_a.id in product_ids
        assert product_b.id not in product_ids


# ============================================================================
# Invite Code Cross-Tenant Isolation
# ============================================================================


class TestInviteCodeIsolation:
    """POs should only manage invite codes for their own products."""

    def test_po_cannot_list_other_pos_invite_codes(self, client, db_session):
        po_a = _make_user(db_session, "inv_poa@test.com", "inv_poa", UserRole.PRODUCT_OWNER)
        po_b = _make_user(db_session, "inv_pob@test.com", "inv_pob", UserRole.PRODUCT_OWNER)

        product_b = _make_product(db_session, "Inv PO-B Product", po_b.id)

        resp = client.get(
            f"/products/{product_b.id}/invite-codes",
            headers=auth_headers(po_a),
        )
        assert resp.status_code == 403

    def test_po_cannot_list_other_pos_members(self, client, db_session):
        po_a = _make_user(db_session, "mem_poa@test.com", "mem_poa", UserRole.PRODUCT_OWNER)
        po_b = _make_user(db_session, "mem_pob@test.com", "mem_pob", UserRole.PRODUCT_OWNER)

        product_b = _make_product(db_session, "Mem PO-B Product", po_b.id)

        resp = client.get(
            f"/products/{product_b.id}/members",
            headers=auth_headers(po_a),
        )
        assert resp.status_code == 403

    def test_po_with_granted_edit_can_manage_codes(self, client, db_session):
        """PO-B with EDIT permission on PO-A's product can create invite codes."""
        po_a = _make_user(db_session, "grant_poa@test.com", "grant_poa", UserRole.PRODUCT_OWNER)
        po_b = _make_user(db_session, "grant_pob@test.com", "grant_pob", UserRole.PRODUCT_OWNER)

        product_a = _make_product(db_session, "Grant PO-A Product", po_a.id)
        _grant_access(db_session, product_a.id, po_b.id, po_a.id, ProductPermissionLevel.EDIT)

        resp = client.post(
            f"/products/{product_a.id}/invite-codes",
            json={},
            headers=auth_headers(po_b),
        )
        assert resp.status_code == 201
