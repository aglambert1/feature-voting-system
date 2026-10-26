"""Product access comes only from creatorship or an explicit ProductPermission grant.

Regression coverage for the removal of the per-user TEAM_WIDE access mode, which
used to grant VIEW on every product with no grant.
"""

import pytest

from app.models.competitor_intelligence import ProductPermission, ProductPermissionLevel
from app.models.user import User, UserRole
from app.services.permission_service import PermissionService
from app.utils.security import hash_password


@pytest.fixture
def other_po_user(db_session):
    """A PRODUCT_OWNER who did not create test_product and has no grant on it."""
    user = User(
        email="po-other@example.com",
        username="po_other",
        hashed_password=hash_password("Owner@pass3"),
        full_name="Other PO",
        role=UserRole.PRODUCT_OWNER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_user_without_grant_has_no_access(db_session, test_product, other_po_user):
    svc = PermissionService(db_session)
    assert not svc.can_access_product(
        other_po_user.id, test_product.id, ProductPermissionLevel.VIEW
    )
    assert test_product not in svc.get_accessible_products(other_po_user.id)


def test_grant_gives_exactly_the_granted_level(db_session, test_product, other_po_user):
    db_session.add(ProductPermission(
        product_id=test_product.id,
        user_id=other_po_user.id,
        permission_level=ProductPermissionLevel.VIEW,
        granted_by_user_id=test_product.created_by_user_id,
    ))
    db_session.commit()

    svc = PermissionService(db_session)
    assert svc.can_access_product(
        other_po_user.id, test_product.id, ProductPermissionLevel.VIEW
    )
    assert not svc.can_access_product(
        other_po_user.id, test_product.id, ProductPermissionLevel.EDIT
    )
    assert test_product in svc.get_accessible_products(other_po_user.id)


def test_user_has_no_default_product_access_column():
    assert not hasattr(User, "default_product_access")
