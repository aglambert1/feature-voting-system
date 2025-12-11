"""
Permission Service for managing product access control.

This service integrates with the existing UserRole system to provide
fine-grained access control for CI products.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.user import User, UserRole, ProductAccessMode
from app.models.competitor_intelligence import (
    CIProduct, ProductPermission, ProductPermissionLevel
)


class PermissionService:
    """Service for managing product permissions."""

    def __init__(self, db: Session):
        self.db = db

    def can_access_product(
        self,
        user_id: int,
        product_id: int,
        required_level: ProductPermissionLevel
    ) -> bool:
        """
        Check if user has access to a product at the required permission level.

        Permission hierarchy (from highest to lowest):
        - ADMIN: Can delete product, manage permissions, edit, view
        - EDIT: Can modify product, run analyses, view
        - VIEW: Can only view product and analyses

        Args:
            user_id: User ID to check
            product_id: Product ID to check
            required_level: Minimum permission level required

        Returns:
            True if user has access, False otherwise
        """
        # Get user
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            return False

        # Get product
        product = self.db.query(CIProduct).filter(CIProduct.id == product_id).first()
        if not product:
            return False

        # 1. System admins bypass product permissions
        if user.role == UserRole.ADMIN:
            return True

        # 2. Product creator has implicit ADMIN access
        if product.created_by_user_id == user_id:
            return True

        # 3. Check user's default access mode for team-wide viewing
        if user.default_product_access == ProductAccessMode.TEAM_WIDE:
            # Team-wide mode grants VIEW access to all products
            if required_level == ProductPermissionLevel.VIEW:
                return True

        # 4. Check explicit product permission grants
        permission = self.db.query(ProductPermission).filter(
            ProductPermission.product_id == product_id,
            ProductPermission.user_id == user_id
        ).first()

        if permission:
            # Check if granted level meets or exceeds required level
            return self._permission_level_meets(
                granted=permission.permission_level,
                required=required_level
            )

        return False

    def _permission_level_meets(
        self,
        granted: ProductPermissionLevel,
        required: ProductPermissionLevel
    ) -> bool:
        """
        Check if granted permission level meets or exceeds required level.

        Hierarchy: ADMIN > EDIT > VIEW
        """
        levels = {
            ProductPermissionLevel.VIEW: 1,
            ProductPermissionLevel.EDIT: 2,
            ProductPermissionLevel.ADMIN: 3
        }
        return levels.get(granted, 0) >= levels.get(required, 0)

    def get_accessible_products(
        self,
        user_id: int,
        permission_level: Optional[ProductPermissionLevel] = None
    ) -> List[CIProduct]:
        """
        Get all products accessible to a user at the specified permission level.

        Args:
            user_id: User ID
            permission_level: Minimum permission level (None = VIEW by default)

        Returns:
            List of accessible CIProduct objects
        """
        if permission_level is None:
            permission_level = ProductPermissionLevel.VIEW

        # Get user
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            return []

        # System admins see all products
        if user.role == UserRole.ADMIN:
            return self.db.query(CIProduct).filter(
                CIProduct.status == "active"
            ).all()

        # Build query based on access rules
        query = self.db.query(CIProduct).filter(CIProduct.status == "active")

        # Start with products created by user (implicit ADMIN)
        filters = [CIProduct.created_by_user_id == user_id]

        # Add team-wide products if user has team-wide access and only VIEW required
        if (user.default_product_access == ProductAccessMode.TEAM_WIDE and
                permission_level == ProductPermissionLevel.VIEW):
            # User can see all active products in team-wide mode
            return query.all()

        # Add products with explicit permission grants
        if permission_level == ProductPermissionLevel.VIEW:
            # Include products where user has VIEW, EDIT, or ADMIN permission
            granted_product_ids = self.db.query(ProductPermission.product_id).filter(
                ProductPermission.user_id == user_id,
                ProductPermission.permission_level.in_([
                    ProductPermissionLevel.VIEW,
                    ProductPermissionLevel.EDIT,
                    ProductPermissionLevel.ADMIN
                ])
            ).all()
            if granted_product_ids:
                filters.append(CIProduct.id.in_([p[0] for p in granted_product_ids]))

        elif permission_level == ProductPermissionLevel.EDIT:
            # Include products where user has EDIT or ADMIN permission
            granted_product_ids = self.db.query(ProductPermission.product_id).filter(
                ProductPermission.user_id == user_id,
                ProductPermission.permission_level.in_([
                    ProductPermissionLevel.EDIT,
                    ProductPermissionLevel.ADMIN
                ])
            ).all()
            if granted_product_ids:
                filters.append(CIProduct.id.in_([p[0] for p in granted_product_ids]))

        elif permission_level == ProductPermissionLevel.ADMIN:
            # Include products where user has ADMIN permission
            granted_product_ids = self.db.query(ProductPermission.product_id).filter(
                ProductPermission.user_id == user_id,
                ProductPermission.permission_level == ProductPermissionLevel.ADMIN
            ).all()
            if granted_product_ids:
                filters.append(CIProduct.id.in_([p[0] for p in granted_product_ids]))

        # Combine filters with OR
        if len(filters) > 0:
            return query.filter(or_(*filters)).all()

        return []

    def grant_permission(
        self,
        product_id: int,
        user_id: int,
        permission_level: ProductPermissionLevel,
        granted_by_user_id: int
    ) -> ProductPermission:
        """
        Grant a user permission to access a product.

        The granting user must have ADMIN access to the product.

        Args:
            product_id: Product ID
            user_id: User ID to grant permission to
            permission_level: Permission level to grant
            granted_by_user_id: User ID of the granter

        Returns:
            ProductPermission object

        Raises:
            PermissionError: If granter doesn't have ADMIN access
            ValueError: If product or user not found
        """
        # Verify granter has ADMIN access
        if not self.can_access_product(
            user_id=granted_by_user_id,
            product_id=product_id,
            required_level=ProductPermissionLevel.ADMIN
        ):
            raise PermissionError(
                f"User {granted_by_user_id} does not have ADMIN access to product {product_id}"
            )

        # Verify target user exists
        target_user = self.db.query(User).filter(User.id == user_id).first()
        if not target_user:
            raise ValueError(f"User {user_id} not found")

        # Check if permission already exists
        existing = self.db.query(ProductPermission).filter(
            ProductPermission.product_id == product_id,
            ProductPermission.user_id == user_id
        ).first()

        if existing:
            # Update existing permission
            existing.permission_level = permission_level
            existing.granted_by_user_id = granted_by_user_id
            self.db.commit()
            self.db.refresh(existing)
            return existing
        else:
            # Create new permission
            permission = ProductPermission(
                product_id=product_id,
                user_id=user_id,
                permission_level=permission_level,
                granted_by_user_id=granted_by_user_id
            )
            self.db.add(permission)
            self.db.commit()
            self.db.refresh(permission)
            return permission

    def revoke_permission(
        self,
        product_id: int,
        user_id: int,
        revoked_by_user_id: int
    ) -> bool:
        """
        Revoke a user's permission to access a product.

        The revoking user must have ADMIN access to the product.

        Args:
            product_id: Product ID
            user_id: User ID to revoke permission from
            revoked_by_user_id: User ID of the revoker

        Returns:
            True if permission was revoked, False if no permission existed

        Raises:
            PermissionError: If revoker doesn't have ADMIN access
        """
        # Verify revoker has ADMIN access
        if not self.can_access_product(
            user_id=revoked_by_user_id,
            product_id=product_id,
            required_level=ProductPermissionLevel.ADMIN
        ):
            raise PermissionError(
                f"User {revoked_by_user_id} does not have ADMIN access to product {product_id}"
            )

        # Find and delete permission
        permission = self.db.query(ProductPermission).filter(
            ProductPermission.product_id == product_id,
            ProductPermission.user_id == user_id
        ).first()

        if permission:
            self.db.delete(permission)
            self.db.commit()
            return True

        return False

    def get_product_permissions(
        self,
        product_id: int,
        requesting_user_id: int
    ) -> List[ProductPermission]:
        """
        Get all permissions for a product.

        Requesting user must have ADMIN access to the product.

        Args:
            product_id: Product ID
            requesting_user_id: User ID making the request

        Returns:
            List of ProductPermission objects

        Raises:
            PermissionError: If requesting user doesn't have ADMIN access
        """
        if not self.can_access_product(
            user_id=requesting_user_id,
            product_id=product_id,
            required_level=ProductPermissionLevel.ADMIN
        ):
            raise PermissionError(
                f"User {requesting_user_id} does not have ADMIN access to product {product_id}"
            )

        return self.db.query(ProductPermission).filter(
            ProductPermission.product_id == product_id
        ).all()
