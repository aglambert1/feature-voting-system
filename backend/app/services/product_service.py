"""
Product Service for managing CI products independently of analysis.

This service handles CRUD operations for products without automatically
triggering product analysis. Analysis is now a separate, independent operation.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path
import shutil
import hashlib
import json
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.competitor_intelligence import (
    CIProduct, ProductAnalysisHistory, ProductPermissionLevel,
    CompetitorAnalysisSession, SessionStage
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

        # Calculate source hash for change detection
        source_hash = self._calculate_source_hash(
            product_description=product_description,
            source_type=source_type,
            source_data=source_data
        )

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

        # AUTO-CREATE SESSION (Unified Session Architecture)
        # Every product analysis now creates a session
        session = CompetitorAnalysisSession(
            product_id=product_id,
            user_id=user_id,
            session_number=new_version,  # Match analysis version
            analysis_version=new_version,  # Link to specific analysis
            stage_completed=SessionStage.PRODUCT_ANALYSIS,  # Stage 1 complete
            status="completed",  # Product analysis is done
            analysis_type="full",  # No comparison at this stage
            product_source_type=source_type,
            product_source_data=source_data,
            analyzed_product_structure=analyzed_structure,
            product_source_hash=source_hash,
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow()  # Stage 1 is complete
        )

        try:
            self.db.add(history)
            self.db.add(session)

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
            product.last_source_hash = source_hash  # Update source hash

            print(f"[ProductService] Auto-creating session #{new_version} for product analysis...")
            print(f"[ProductService] Committing changes to database...")
            self.db.commit()
            self.db.refresh(product)
            self.db.refresh(session)
            print(f"[ProductService] Created session #{session.session_number} (ID: {session.id}) for product {product_id}")
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

    # ============================================================================
    # Multi-Source Helper Methods
    # ============================================================================

    def _concatenate_sources(self, sources: List[Dict[str, Any]]) -> str:
        """
        Concatenate multiple sources into a single text block.

        Creates clearly delineated sections for each source to help
        the AI understand the context of each piece of content.

        Args:
            sources: List of source dictionaries with 'type' and 'extracted_text'

        Returns:
            Concatenated text with source labels

        Example output:
            ===== SOURCE 1: Text Description =====
            [content]

            ===== SOURCE 2: product_spec.pdf =====
            [content]
        """
        if not sources:
            return ""

        parts = []
        for i, source in enumerate(sources, 1):
            # Get source label
            source_label = self._get_source_label(source)

            # Add labeled section
            parts.append(f"===== SOURCE {i}: {source_label} =====\n")
            parts.append(source.get('extracted_text', source.get('content', '')))
            parts.append("\n\n")

        return "".join(parts).strip()

    def _get_source_label(self, source: Dict[str, Any]) -> str:
        """
        Generate a descriptive label for a source.

        Args:
            source: Source dictionary

        Returns:
            Human-readable label
        """
        source_type = source.get('type', 'unknown')

        if source_type == 'text':
            return "Text Description"
        elif source_type == 'document':
            filename = source.get('filename', 'unknown')
            return filename
        elif source_type == 'url':
            url = source.get('url', 'unknown')
            title = source.get('title', '')
            return f"{url}" if not title else f"{title} ({url})"
        else:
            return source_type

    def _get_product_upload_dir(self, product_id: int) -> Path:
        """
        Get or create the upload directory for a product.

        Args:
            product_id: Product ID

        Returns:
            Path to product upload directory
        """
        upload_dir = Path("uploads") / str(product_id)
        upload_dir.mkdir(parents=True, exist_ok=True)
        return upload_dir

    def _move_temp_files(self, sources: List[Dict[str, Any]], product_id: int) -> None:
        """
        Move uploaded files from temp storage to permanent product storage.

        For document sources, moves files from uploads/temp/{uuid}_{filename}
        to uploads/{product_id}/{uuid}_{filename} and updates the
        file_path in the source dict.

        Args:
            sources: List of source dictionaries (modified in place)
            product_id: Product ID for permanent storage location
        """
        product_dir = self._get_product_upload_dir(product_id)
        temp_dir = Path("uploads/temp")

        for source in sources:
            if source.get('type') == 'document' and source.get('file_id'):
                file_id = source['file_id']
                filename = source.get('filename', 'unknown')
                safe_filename = f"{file_id}_{filename}"

                temp_path = temp_dir / safe_filename
                permanent_path = product_dir / safe_filename

                # Move file if it exists in temp
                if temp_path.exists():
                    try:
                        shutil.move(str(temp_path), str(permanent_path))
                        # Update source with permanent path (relative)
                        source['file_path'] = f"uploads/{product_id}/{safe_filename}"
                        print(f"✓ Moved {safe_filename} to product {product_id} directory")
                    except Exception as e:
                        print(f"✗ Failed to move {safe_filename}: {e}")
                        # Leave file in temp, but update path anyway
                        source['file_path'] = f"uploads/temp/{safe_filename}"

    def _estimate_total_tokens(self, sources: List[Dict[str, Any]]) -> int:
        """
        Estimate total token count for all sources.

        Uses simple heuristic: 1 token ≈ 4 characters

        Args:
            sources: List of source dictionaries

        Returns:
            Estimated total token count
        """
        total_chars = 0
        for source in sources:
            text = source.get('extracted_text', source.get('content', ''))
            total_chars += len(text)

        return total_chars // 4

    def _calculate_source_hash(
        self,
        product_description: str,
        source_type: str,
        source_data: Optional[Dict[str, Any]]
    ) -> str:
        """
        Calculate SHA-256 hash of product sources for change detection.

        Creates a deterministic hash based on source configuration to detect
        when product information has changed and requires re-analysis.

        Args:
            product_description: Product description text
            source_type: Source type (text, document, url)
            source_data: Source metadata

        Returns:
            SHA-256 hash (64 hex characters)
        """
        source_data = source_data or {}

        if source_type == "text":
            # Hash the text content itself
            content = product_description
        elif source_type == "document":
            # Hash file path + upload timestamp if available
            # For multi-source, hash all file paths
            if 'sources' in source_data:
                # Multi-source mode
                file_paths = sorted([
                    s.get('file_path', '') for s in source_data.get('sources', [])
                    if s.get('type') == 'document'
                ])
                content = '_'.join(file_paths)
            else:
                # Single-source mode
                file_path = source_data.get('file_path', '')
                uploaded_at = source_data.get('uploaded_at', '')
                content = f"{file_path}_{uploaded_at}"
        elif source_type == "url":
            # Hash all URLs
            if 'sources' in source_data:
                # Multi-source mode
                urls = sorted([
                    s.get('url', '') for s in source_data.get('sources', [])
                    if s.get('type') == 'url'
                ])
                content = '_'.join(urls)
            else:
                # Single-source mode
                content = source_data.get('url', '')
        else:
            # Unknown source type - hash the description
            content = product_description

        # Generate SHA-256 hash
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
