"""
Permission helpers for MCP tools.

Provides two helpers that all product-scoped tools should call:
- require_product_access: gate a single product by permission level
- get_permitted_products: return filtered product list for the current user
"""

import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.competitor_intelligence import CIProduct, ProductPermissionLevel
from app.services.permission_service import PermissionService
from mcp_server.user_context import get_mcp_user_id

logger = logging.getLogger(__name__)


def require_product_access(
    db: Session,
    product_id: int,
    level: ProductPermissionLevel = ProductPermissionLevel.VIEW,
) -> Optional[dict]:
    """Check that the current MCP user can access a product at the given level.

    Stdio transport (user_id=0) bypasses all checks.

    Returns:
        None on success, or an error dict on denial.
    """
    user_id = get_mcp_user_id()
    if user_id == 0:
        return None

    svc = PermissionService(db)
    if svc.can_access_product(user_id, product_id, level):
        return None

    level_label = level.value.upper()
    logger.warning(
        "MCP permission denied: user=%d product=%d level=%s", user_id, product_id, level_label
    )
    return {"error": f"Permission denied: you need {level_label} access to product {product_id}."}


def get_permitted_products(db: Session) -> List[CIProduct]:
    """Return the list of products the current MCP user can view.

    Stdio transport (user_id=0) returns all active products.
    """
    user_id = get_mcp_user_id()
    if user_id == 0:
        return db.query(CIProduct).filter(CIProduct.status == "active").all()

    svc = PermissionService(db)
    return svc.get_accessible_products(user_id)
