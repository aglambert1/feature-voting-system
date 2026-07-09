"""Unit tests for app/api/deps.py — the shared product access check.

verify_product_access replaced per-router copies of the same 404/403 logic;
these tests pin its contract so router conversions stay safe.
"""

import pytest
from fastapi import HTTPException

from app.api.deps import verify_product_access
from app.models.competitor_intelligence import CIProduct, ProductPermissionLevel


class TestVerifyProductAccess:
    def test_missing_product_raises_404(self, db_session, po_user):
        with pytest.raises(HTTPException) as exc:
            verify_product_access(db_session, 99999, po_user)
        assert exc.value.status_code == 404

    def test_user_without_grant_raises_403(self, db_session, test_product, voter_user):
        with pytest.raises(HTTPException) as exc:
            verify_product_access(db_session, test_product.id, voter_user)
        assert exc.value.status_code == 403

    def test_creator_has_implicit_owner(self, db_session, test_product, po_user):
        product = verify_product_access(
            db_session, test_product.id, po_user, ProductPermissionLevel.OWNER
        )
        assert product.id == test_product.id

    def test_view_grant_allows_view(
        self, db_session, test_product, voter_user, voter_product_access
    ):
        product = verify_product_access(db_session, test_product.id, voter_user)
        assert isinstance(product, CIProduct)

    def test_view_grant_denies_edit(
        self, db_session, test_product, voter_user, voter_product_access
    ):
        with pytest.raises(HTTPException) as exc:
            verify_product_access(
                db_session, test_product.id, voter_user, ProductPermissionLevel.EDIT
            )
        assert exc.value.status_code == 403
