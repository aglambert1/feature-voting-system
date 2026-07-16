"""
Permission Service for managing product access control.

This service integrates with the existing UserRole system to provide
fine-grained access control for CI products.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_, select

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
        - OWNER: Can delete product, manage permissions, edit, view
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

        # VOTER role is capped at VIEW regardless of granted permission level
        # or product ownership — only PRODUCT_OWNER/ADMIN may edit anything.
        if (
            user.role == UserRole.VOTER
            and required_level != ProductPermissionLevel.VIEW
        ):
            return False

        # Get product
        product = self.db.query(CIProduct).filter(CIProduct.id == product_id).first()
        if not product:
            return False

        # 1. Product creator has implicit OWNER access
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

        Hierarchy: OWNER > EDIT > VIEW
        """
        levels = {
            ProductPermissionLevel.VIEW: 1,
            ProductPermissionLevel.EDIT: 2,
            ProductPermissionLevel.OWNER: 3
        }
        return levels.get(granted, 0) >= levels.get(required, 0)

    def get_product_members(
        self,
        product_id: int,
        min_level: ProductPermissionLevel = ProductPermissionLevel.VIEW,
    ) -> List[User]:
        """
        Get all active users who can access a product at or above min_level.

        Reverse of can_access_product: given a product, return the users.
        Includes the product creator (implicit OWNER, satisfies any level) and
        every user with an explicit ProductPermission grant at or above
        min_level. VOTER-role users are excluded when min_level is above VIEW,
        mirroring the role cap in can_access_product. Inactive users are
        excluded. Results are de-duplicated.

        Note: does not expand TEAM_WIDE default access — that only grants VIEW,
        and this method is used for actionable (EDIT+) alert recipients.
        """
        qualifying_levels = [
            level for level in ProductPermissionLevel
            if self._permission_level_meets(granted=level, required=min_level)
        ]

        product = self.db.query(CIProduct).filter(
            CIProduct.id == product_id
        ).first()
        if not product:
            return []

        members: dict[int, User] = {}

        # Explicit grants at or above min_level
        granted = (
            self.db.query(User)
            .join(ProductPermission, ProductPermission.user_id == User.id)
            .filter(
                ProductPermission.product_id == product_id,
                ProductPermission.permission_level.in_(qualifying_levels),
                User.is_active.is_(True),
            )
            .all()
        )
        for user in granted:
            # A VOTER cannot hold EDIT/OWNER (see can_access_product); guard in
            # case a stale inert grant predates that cap.
            if min_level != ProductPermissionLevel.VIEW and user.role == UserRole.VOTER:
                continue
            members[user.id] = user

        # Product creator has implicit OWNER, which satisfies any min_level
        creator = self.db.query(User).filter(
            User.id == product.created_by_user_id,
            User.is_active.is_(True),
        ).first()
        if creator:
            members[creator.id] = creator

        return list(members.values())

    def get_accessible_products(
        self,
        user_id: int,
        permission_level: Optional[ProductPermissionLevel] = None
    ) -> List[CIProduct]:
        """
        Get all products accessible to a user at the specified permission level.

        Role-based filtering:
        - ADMIN / PRODUCT_OWNER: Products they created (implicit OWNER, satisfies
          any requested level) + products explicitly granted at or above the
          requested level
        - VOTER: Only products with explicit permission grants at or above the
          requested level

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

        # Grant levels that satisfy the requested minimum (mirrors the
        # hierarchy in _permission_level_meets: OWNER > EDIT > VIEW).
        qualifying_levels = [
            level for level in ProductPermissionLevel
            if self._permission_level_meets(granted=level, required=permission_level)
        ]

        # Build base query
        query = self.db.query(CIProduct).filter(CIProduct.status == "active")

        # Role-based filtering
        if user.role in (UserRole.ADMIN, UserRole.PRODUCT_OWNER):
            # ADMINs and POs see products they created (implicit OWNER, so it
            # always satisfies the requested level) + products explicitly
            # granted at or above the requested level
            granted_ids = select(ProductPermission.product_id).where(
                ProductPermission.user_id == user_id,
                ProductPermission.permission_level.in_(qualifying_levels)
            )
            return query.filter(
                or_(
                    CIProduct.created_by_user_id == user_id,
                    CIProduct.id.in_(granted_ids)
                )
            ).all()

        elif user.role == UserRole.VOTER:
            # VOTER role is capped at VIEW (mirrors can_access_product):
            # no product qualifies at EDIT/OWNER level regardless of grants
            if permission_level != ProductPermissionLevel.VIEW:
                return []

            # VOTERs only see products they have explicit permission for,
            # at or above the requested level
            permitted_ids = select(ProductPermission.product_id).where(
                ProductPermission.user_id == user_id,
                ProductPermission.permission_level.in_(qualifying_levels)
            )
            return query.filter(CIProduct.id.in_(permitted_ids)).all()

        # Fallback: no access
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

        The granting user must have OWNER access to the product.

        Args:
            product_id: Product ID
            user_id: User ID to grant permission to
            permission_level: Permission level to grant
            granted_by_user_id: User ID of the granter

        Returns:
            ProductPermission object

        Raises:
            PermissionError: If granter doesn't have OWNER access
            ValueError: If product or user not found
        """
        # Verify granter has OWNER access
        if not self.can_access_product(
            user_id=granted_by_user_id,
            product_id=product_id,
            required_level=ProductPermissionLevel.OWNER
        ):
            raise PermissionError(
                f"User {granted_by_user_id} does not have OWNER access to product {product_id}"
            )

        # Verify target user exists
        target_user = self.db.query(User).filter(User.id == user_id).first()
        if not target_user:
            raise ValueError(f"User {user_id} not found")

        # VOTER role is capped at VIEW (see can_access_product) — reject
        # grants that would be silently inert rather than storing them
        if (
            target_user.role == UserRole.VOTER
            and permission_level != ProductPermissionLevel.VIEW
        ):
            raise ValueError(
                f"Cannot grant {permission_level.value} access to a voter. "
                "Voters are limited to view access — change their role to "
                "Product Owner first, or grant view."
            )

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

        The revoking user must have OWNER access to the product.

        Args:
            product_id: Product ID
            user_id: User ID to revoke permission from
            revoked_by_user_id: User ID of the revoker

        Returns:
            True if permission was revoked, False if no permission existed

        Raises:
            PermissionError: If revoker doesn't have OWNER access
        """
        # Verify revoker has OWNER access
        if not self.can_access_product(
            user_id=revoked_by_user_id,
            product_id=product_id,
            required_level=ProductPermissionLevel.OWNER
        ):
            raise PermissionError(
                f"User {revoked_by_user_id} does not have OWNER access to product {product_id}"
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

        Requesting user must have OWNER access to the product.

        Args:
            product_id: Product ID
            requesting_user_id: User ID making the request

        Returns:
            List of ProductPermission objects

        Raises:
            PermissionError: If requesting user doesn't have OWNER access
        """
        if not self.can_access_product(
            user_id=requesting_user_id,
            product_id=product_id,
            required_level=ProductPermissionLevel.OWNER
        ):
            raise PermissionError(
                f"User {requesting_user_id} does not have OWNER access to product {product_id}"
            )

        return self.db.query(ProductPermission).filter(
            ProductPermission.product_id == product_id
        ).all()
