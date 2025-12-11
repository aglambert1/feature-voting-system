"""
Product Service for managing CI products independently of analysis.

This service handles CRUD operations for products without automatically
triggering product analysis. Analysis is now a separate, independent operation.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.competitor_intelligence import (
    CIProduct, ProductAnalysisHistory, ProductPermissionLevel
)
from app.models.user import User
from app.agents.product_analyzer import ProductAnalyzerAgent
from app.services.llm_service import LLMService
from app.services.permission_service import PermissionService


class ProductService:
    """Service for managing CI products."""

    def __init__(self, db: Session):
        self.db = db
        self.permission_service = PermissionService(db)

    def create_product(
        self,
        product_name: str,
        product_description: str,
        created_by_user_id: int,
        source_type: str = "text",
        source_data: Optional[Dict[str, Any]] = None
    ) -> CIProduct:
        """
        Create a new product without automatic analysis.

        Products are created as team resources with the creator
        getting implicit ADMIN access.

        Args:
            product_name: Product name (must be unique)
            product_description: Product description
            created_by_user_id: User creating the product
            source_type: Source type (text, document, url)
            source_data: Source metadata (url or filename)

        Returns:
            Created CIProduct

        Raises:
            ValueError: If product name already exists or validation fails
        """
        # Check if product with this name already exists
        existing = self.db.query(CIProduct).filter(
            CIProduct.product_name == product_name
        ).first()

        if existing:
            raise ValueError(
                f"Product '{product_name}' already exists. "
                "Please use a different name."
            )

        # Verify user exists
        user = self.db.query(User).filter(User.id == created_by_user_id).first()
        if not user:
            raise ValueError(f"User {created_by_user_id} not found")

        # Create product (no analysis yet)
        product = CIProduct(
            product_name=product_name,
            product_description=product_description,
            created_by_user_id=created_by_user_id,
            last_modified_by_user_id=created_by_user_id,
            product_source_type=source_type,
            product_source_data=source_data,
            analysis_version=0,  # No analysis yet
            analysis_count=0,
            status="active"
        )

        try:
            self.db.add(product)
            self.db.commit()
            self.db.refresh(product)
        except IntegrityError as e:
            self.db.rollback()
            raise ValueError(f"Failed to create product: {str(e)}")

        return product

    def analyze_product(
        self,
        product_id: int,
        user_id: int,
        product_description: str,
        source_type: str,
        source_data: Optional[Dict[str, Any]],
        llm_service: LLMService
    ) -> Dict[str, Any]:
        """
        Analyze a product with AI (Stage 1 - independent operation).

        This can be called multiple times to re-analyze a product,
        creating a versioned history of analyses.

        Args:
            product_id: Product ID to analyze
            user_id: User performing the analysis
            product_description: Updated product description to analyze
            source_type: Source type (text, document, url)
            source_data: Additional source data
            llm_service: LLM service instance

        Returns:
            Analyzed product structure

        Raises:
            PermissionError: If user lacks EDIT permission
            ValueError: If product not found
        """
        # Check permission
        if not self.permission_service.can_access_product(
            user_id=user_id,
            product_id=product_id,
            required_level=ProductPermissionLevel.EDIT
        ):
            raise PermissionError(
                f"User {user_id} does not have EDIT permission for product {product_id}"
            )

        # Get product
        product = self.db.query(CIProduct).filter(CIProduct.id == product_id).first()
        if not product:
            raise ValueError(f"Product {product_id} not found")

        # Run AI analysis with the provided (possibly updated) description
        agent = ProductAnalyzerAgent(
            db=self.db,
            llm_service=llm_service,
            session_id=None,  # No session - this is independent
            product_id=product_id
        )

        analyzed_structure = agent.execute({
            'product_name': product.product_name,
            'product_description': product_description,
            'source_type': source_type
        })

        # Increment version
        new_version = product.analysis_version + 1

        # Save to analysis history with the analyzed description
        history = ProductAnalysisHistory(
            product_id=product_id,
            analysis_version=new_version,
            analyzed_by_user_id=user_id,
            product_description=product_description,
            product_source_type=source_type,
            product_source_data=source_data,
            analyzed_structure=analyzed_structure,
            tokens_used=None  # Could be extracted from agent logs
        )

        try:
            self.db.add(history)

            # Update product with latest analysis and description
            print(f"[ProductService] Updating product {product_id} description: {product_description[:100]}...")
            product.product_description = product_description
            product.structured_product_data = analyzed_structure
            product.product_category = analyzed_structure.get('product_category')
            product.product_source_type = source_type
            product.product_source_data = source_data
            product.analysis_version = new_version
            product.last_analyzed_at = datetime.utcnow()
            product.last_analyzed_by_user_id = user_id
            product.analysis_count = new_version
            product.last_modified_by_user_id = user_id

            print(f"[ProductService] Committing changes to database...")
            self.db.commit()
            self.db.refresh(product)
            print(f"[ProductService] After commit, product.product_description: {product.product_description[:100]}...")
        except IntegrityError as e:
            self.db.rollback()
            raise ValueError(f"Failed to save analysis: {str(e)}")

        return analyzed_structure

    def get_product(
        self,
        product_id: int,
        user_id: int
    ) -> Optional[CIProduct]:
        """
        Get product by ID with permission check.

        Args:
            product_id: Product ID
            user_id: User requesting the product

        Returns:
            CIProduct if found and user has VIEW access, None otherwise
        """
        # Check permission
        if not self.permission_service.can_access_product(
            user_id=user_id,
            product_id=product_id,
            required_level=ProductPermissionLevel.VIEW
        ):
            return None

        product = self.db.query(CIProduct).filter(
            CIProduct.id == product_id
        ).first()

        if product:
            print(f"[ProductService] get_product({product_id}) returning description: {product.product_description[:100]}...")

        return product

    def update_product(
        self,
        product_id: int,
        user_id: int,
        product_name: Optional[str] = None,
        product_description: Optional[str] = None
    ) -> CIProduct:
        """
        Update product information.

        Requires EDIT permission. Does NOT trigger re-analysis.
        Use analyze_product() separately to re-analyze after updates.

        Args:
            product_id: Product ID
            user_id: User updating the product
            product_name: New product name (optional)
            product_description: New product description (optional)

        Returns:
            Updated CIProduct

        Raises:
            PermissionError: If user lacks EDIT permission
            ValueError: If product not found or validation fails
        """
        # Check permission
        if not self.permission_service.can_access_product(
            user_id=user_id,
            product_id=product_id,
            required_level=ProductPermissionLevel.EDIT
        ):
            raise PermissionError(
                f"User {user_id} does not have EDIT permission for product {product_id}"
            )

        product = self.db.query(CIProduct).filter(CIProduct.id == product_id).first()
        if not product:
            raise ValueError(f"Product {product_id} not found")

        # Update fields
        if product_name is not None:
            # Check if new name conflicts with existing product
            if product_name != product.product_name:
                existing = self.db.query(CIProduct).filter(
                    CIProduct.product_name == product_name
                ).first()
                if existing:
                    raise ValueError(
                        f"Product '{product_name}' already exists. "
                        "Please use a different name."
                    )
                product.product_name = product_name

        if product_description is not None:
            product.product_description = product_description

        product.last_modified_by_user_id = user_id

        try:
            self.db.commit()
            self.db.refresh(product)
        except IntegrityError as e:
            self.db.rollback()
            raise ValueError(f"Failed to update product: {str(e)}")

        return product

    def delete_product(
        self,
        product_id: int,
        user_id: int
    ) -> bool:
        """
        Delete a product.

        Requires ADMIN permission. Cascades to delete all related data.

        Args:
            product_id: Product ID
            user_id: User deleting the product

        Returns:
            True if deleted, False if not found

        Raises:
            PermissionError: If user lacks ADMIN permission
        """
        # Check permission
        if not self.permission_service.can_access_product(
            user_id=user_id,
            product_id=product_id,
            required_level=ProductPermissionLevel.ADMIN
        ):
            raise PermissionError(
                f"User {user_id} does not have ADMIN permission for product {product_id}"
            )

        product = self.db.query(CIProduct).filter(CIProduct.id == product_id).first()
        if not product:
            return False

        self.db.delete(product)
        self.db.commit()
        return True

    def list_products(
        self,
        user_id: int,
        permission_level: Optional[ProductPermissionLevel] = None
    ) -> list[CIProduct]:
        """
        List all products accessible to a user.

        Args:
            user_id: User ID
            permission_level: Minimum permission level filter (default: VIEW)

        Returns:
            List of accessible products
        """
        return self.permission_service.get_accessible_products(
            user_id=user_id,
            permission_level=permission_level
        )

    def get_analysis_history(
        self,
        product_id: int,
        user_id: int
    ) -> list[ProductAnalysisHistory]:
        """
        Get analysis history for a product.

        Args:
            product_id: Product ID
            user_id: User requesting history

        Returns:
            List of ProductAnalysisHistory ordered by version (newest first)

        Raises:
            PermissionError: If user lacks VIEW permission
        """
        # Check permission
        if not self.permission_service.can_access_product(
            user_id=user_id,
            product_id=product_id,
            required_level=ProductPermissionLevel.VIEW
        ):
            raise PermissionError(
                f"User {user_id} does not have VIEW permission for product {product_id}"
            )

        return self.db.query(ProductAnalysisHistory).filter(
            ProductAnalysisHistory.product_id == product_id
        ).order_by(ProductAnalysisHistory.analysis_version.desc()).all()
