"""
Shared FastAPI endpoint helpers.

Product access control used across all product-scoped routers. Import from
here instead of redefining per-router copies.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.competitor_intelligence import CIProduct, ProductPermissionLevel
from app.models.user import User
from app.services.permission_service import PermissionService


def verify_product_access(
    db: Session,
    product_id: int,
    user: User,
    required_level: ProductPermissionLevel = ProductPermissionLevel.VIEW,
) -> CIProduct:
    """Verify product exists and user has the required permission level.

    Raises 404 if the product doesn't exist, 403 if the user lacks
    required_level. Returns the product on success.
    """
    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found",
        )
    if not PermissionService(db).can_access_product(
        user_id=user.id,
        product_id=product_id,
        required_level=required_level,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have {required_level.value} permission for product {product_id}",
        )
    return product
