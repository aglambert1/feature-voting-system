"""Tests for MCP permission helpers and tool-level permission enforcement."""

import pytest
from unittest.mock import patch

from app.models.competitor_intelligence import (
    CIProduct,
    ProductPermission,
    ProductPermissionLevel,
)
from app.models.user import User, UserRole
from mcp_server.permissions import require_product_access, get_permitted_products


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def owner_user(db_session):
    """Product owner who creates the product."""
    user = User(
        email="owner@test.com",
        username="owner",
        hashed_password="hashed",
        full_name="Owner",
        role=UserRole.PRODUCT_OWNER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def viewer_user(db_session):
    """Voter with explicit VIEW permission."""
    user = User(
        email="viewer@test.com",
        username="viewer",
        hashed_password="hashed",
        full_name="Viewer",
        role=UserRole.VOTER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def no_access_user(db_session):
    """Voter with no permission grants."""
    user = User(
        email="noaccess@test.com",
        username="noaccess",
        hashed_password="hashed",
        full_name="No Access",
        role=UserRole.VOTER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_user(db_session):
    """Admin user — bypasses all permission checks."""
    user = User(
        email="admin@test.com",
        username="adminuser",
        hashed_password="hashed",
        full_name="Admin",
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def product(db_session, owner_user):
    """Active product owned by owner_user."""
    p = CIProduct(
        product_name="Test Product",
        product_description="desc",
        product_category="Testing",
        created_by_user_id=owner_user.id,
        status="active",
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def product_b(db_session, owner_user):
    """Second product — viewer has no access to this one."""
    p = CIProduct(
        product_name="Product B",
        product_description="desc",
        product_category="Testing",
        created_by_user_id=owner_user.id,
        status="active",
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def view_permission(db_session, product, viewer_user, owner_user):
    """Grant viewer_user VIEW access to product."""
    perm = ProductPermission(
        product_id=product.id,
        user_id=viewer_user.id,
        permission_level=ProductPermissionLevel.VIEW,
        granted_by_user_id=owner_user.id,
    )
    db_session.add(perm)
    db_session.commit()
    return perm


# ---------------------------------------------------------------------------
# Helper to mock get_mcp_user_id
# ---------------------------------------------------------------------------

def _patch_user_id(user_id):
    return patch("mcp_server.permissions.get_mcp_user_id", return_value=user_id)


# ---------------------------------------------------------------------------
# require_product_access tests
# ---------------------------------------------------------------------------

class TestRequireProductAccess:
    """Tests for the require_product_access helper."""

    def test_stdio_bypasses_all_checks(self, db_session, product):
        """user_id=0 (stdio) should always return None (allowed)."""
        with _patch_user_id(0):
            result = require_product_access(db_session, product.id, ProductPermissionLevel.OWNER)
            assert result is None

    def test_owner_has_full_access(self, db_session, product, owner_user):
        """Product creator has implicit OWNER access."""
        with _patch_user_id(owner_user.id):
            assert require_product_access(db_session, product.id, ProductPermissionLevel.VIEW) is None
            assert require_product_access(db_session, product.id, ProductPermissionLevel.EDIT) is None
            assert require_product_access(db_session, product.id, ProductPermissionLevel.OWNER) is None

    def test_viewer_has_view_access(self, db_session, product, viewer_user, view_permission):
        """User with VIEW permission can view but not edit."""
        with _patch_user_id(viewer_user.id):
            assert require_product_access(db_session, product.id, ProductPermissionLevel.VIEW) is None
            denied = require_product_access(db_session, product.id, ProductPermissionLevel.EDIT)
            assert denied is not None
            assert "error" in denied
            assert "EDIT" in denied["error"]

    def test_no_access_denied(self, db_session, product, no_access_user):
        """User with no grants is denied."""
        with _patch_user_id(no_access_user.id):
            denied = require_product_access(db_session, product.id, ProductPermissionLevel.VIEW)
            assert denied is not None
            assert "error" in denied

    def test_admin_bypasses_checks(self, db_session, product, admin_user):
        """Admin users bypass all product permission checks."""
        with _patch_user_id(admin_user.id):
            assert require_product_access(db_session, product.id, ProductPermissionLevel.OWNER) is None

    def test_denied_returns_error_dict(self, db_session, product, no_access_user):
        """Denied result is a dict with 'error' key, not an exception."""
        with _patch_user_id(no_access_user.id):
            result = require_product_access(db_session, product.id)
            assert isinstance(result, dict)
            assert "error" in result
            assert "Permission denied" in result["error"]


# ---------------------------------------------------------------------------
# get_permitted_products tests
# ---------------------------------------------------------------------------

class TestGetPermittedProducts:
    """Tests for the get_permitted_products helper."""

    def test_stdio_returns_all_active(self, db_session, product, product_b):
        """Stdio (user_id=0) sees all active products."""
        with _patch_user_id(0):
            products = get_permitted_products(db_session)
            ids = {p.id for p in products}
            assert product.id in ids
            assert product_b.id in ids

    def test_owner_sees_own_products(self, db_session, product, product_b, owner_user):
        """Owner sees products they created."""
        with _patch_user_id(owner_user.id):
            products = get_permitted_products(db_session)
            ids = {p.id for p in products}
            assert product.id in ids
            assert product_b.id in ids

    def test_viewer_sees_granted_only(self, db_session, product, product_b, viewer_user, view_permission):
        """Viewer only sees products with explicit permission."""
        with _patch_user_id(viewer_user.id):
            products = get_permitted_products(db_session)
            ids = {p.id for p in products}
            assert product.id in ids
            assert product_b.id not in ids

    def test_no_access_sees_nothing(self, db_session, product, no_access_user):
        """User with no grants sees no products."""
        with _patch_user_id(no_access_user.id):
            products = get_permitted_products(db_session)
            assert len(products) == 0

    def test_admin_sees_all(self, db_session, product, product_b, admin_user):
        """Admin sees all active products."""
        with _patch_user_id(admin_user.id):
            products = get_permitted_products(db_session)
            ids = {p.id for p in products}
            assert product.id in ids
            assert product_b.id in ids
