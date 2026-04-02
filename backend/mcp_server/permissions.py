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


def require_product_analyzed(db: Session, product_id: int) -> Optional[dict]:
    """Check that a product has been analyzed (has structured_product_data).

    Many operations (discovery, feature search, audits) require analysis
    data to function. Returns an error dict with guidance if not analyzed.
    """
    product = db.query(CIProduct).get(product_id)
    if not product:
        return {"error": f"Product {product_id} not found"}
    if not product.structured_product_data:
        return {
            "error": f"Product '{product.product_name}' has not been analyzed yet. "
                     "Run product_run_analysis first (provide a source_url or ensure the product has a detailed description).",
        }
    return None


def require_no_active_job(db: Session, product_id: int, job_type, label: str) -> Optional[dict]:
    """Check that no active job of the given type is running for this product.

    Returns error dict with the active job UUID if one exists.
    """
    from app.services.queue_service import QueueService
    queue_service = QueueService(db)
    active = queue_service.get_active_jobs(product_id=product_id)
    conflicts = [j for j in active if j.job_type == job_type]
    if conflicts:
        return {
            "error": f"{label} already in progress for this product.",
            "active_job_uuid": conflicts[0].job_uuid,
        }
    return None


def get_permitted_products(db: Session) -> List[CIProduct]:
    """Return the list of products the current MCP user can view.

    Stdio transport (user_id=0) returns all active products.
    """
    user_id = get_mcp_user_id()
    if user_id == 0:
        return db.query(CIProduct).filter(CIProduct.status == "active").all()

    svc = PermissionService(db)
    return svc.get_accessible_products(user_id)
