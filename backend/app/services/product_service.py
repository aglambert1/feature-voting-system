"""
Product Service for managing CI products independently of analysis.

This service handles CRUD operations for products without automatically
triggering product analysis. Analysis is now a separate, independent operation.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path
import logging
import shutil
import hashlib
import json
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.competitor_intelligence import (
    CIProduct, ProductAnalysisHistory, ProductPermission, ProductPermissionLevel,
    ProductFeature
)
from app.models.user import User
from app.services.permission_service import PermissionService
from app.services.vector_service import VectorService

logger = logging.getLogger(__name__)


def create_product_features_with_embeddings(
    db: Session,
    *,
    product_id: int,
    analysis_history_id: int,
    analysis_version: int,
    detailed_features: List[Dict[str, Any]],
    source_url: Optional[str] = None,
) -> List[ProductFeature]:
    """Create ProductFeature rows AND populate their embeddings (batched).

    This is the single source of truth for persisting a product's detailed
    features so the synchronous (ProductService) and queued (analyze_product_task)
    analysis paths cannot drift. Embeddings are what the fast feature-match /
    "does this feature exist?" lookup relies on; if they are missing, every
    query falls through to a slow per-feature on-the-fly embedding path.

    Embeddings are generated in a single Voyage batch call rather than one call
    per feature. Embedding failures are logged but do not abort feature
    creation — the rows are still useful as LLM context and matching degrades
    gracefully (and can be backfilled by re-analysis).

    Returns the created ProductFeature rows (already flushed, so .id is set).
    """
    if not detailed_features:
        return []

    created: List[ProductFeature] = []
    embed_items = []  # (feature_id, feature_text)
    for feat in detailed_features:
        pf = ProductFeature(
            product_id=product_id,
            analysis_history_id=analysis_history_id,
            analysis_version=analysis_version,
            feature_name=feat.get('name', ''),
            feature_description=feat.get('description', ''),
            feature_category=feat.get('category', ''),
            extraction_confidence=feat.get('confidence', 0.0),
            source_reference=feat.get('source_reference', ''),
            source_url=source_url,
            status='active',
        )
        db.add(pf)
        created.append(pf)

    db.flush()  # Assign ids before storing embeddings

    for pf, feat in zip(created, detailed_features):
        feature_text = f"{feat.get('name', '')}\n{feat.get('description', '')}"
        embed_items.append((pf.id, feature_text))

    try:
        from app.services.similarity_detector import SimilarityDetectorService
        SimilarityDetectorService(db).store_product_feature_embeddings_batch(embed_items)
    except Exception as e:
        logger.warning(
            "Failed to store product-feature embeddings for product %s "
            "(features created without embeddings; matching will use the slow "
            "fallback until re-analyzed): %s",
            product_id, e,
        )

    return created


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
        getting implicit OWNER access.

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
            self.db.flush()

            # Grant explicit OWNER permission to the creator
            if created_by_user_id:
                owner_permission = ProductPermission(
                    product_id=product.id,
                    user_id=created_by_user_id,
                    permission_level=ProductPermissionLevel.OWNER,
                    granted_by_user_id=created_by_user_id,
                )
                self.db.add(owner_permission)

            self.db.commit()
            self.db.refresh(product)
        except IntegrityError as e:
            self.db.rollback()
            raise ValueError(f"Failed to create product: {str(e)}")

        return product

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

    def get_delete_preview(self, product_id: int) -> Optional[Dict[str, Any]]:
        """
        Build a preview of what would be deleted for a product.

        Returns None if product not found. Otherwise returns a dict with
        product info, row counts per table, file paths, and embedding counts.
        """
        product = self.db.query(CIProduct).filter(CIProduct.id == product_id).first()
        if not product:
            return None

        # Count rows in all related tables
        table_counts = {}
        count_queries = [
            ("competitors", "SELECT COUNT(*) FROM product_competitors WHERE product_id = :pid"),
            ("competitor_features", """
                SELECT COUNT(*) FROM product_competitor_features
                WHERE product_competitor_id IN (
                    SELECT id FROM product_competitors WHERE product_id = :pid
                )
            """),
            ("analysis_sessions", "SELECT COUNT(*) FROM competitor_analysis_sessions WHERE product_id = :pid"),
            ("product_features", "SELECT COUNT(*) FROM product_features WHERE product_id = :pid"),
            ("analysis_history", "SELECT COUNT(*) FROM product_analysis_history WHERE product_id = :pid"),
            ("permissions", "SELECT COUNT(*) FROM product_permissions WHERE product_id = :pid"),
            ("generated_ideas", "SELECT COUNT(*) FROM competitor_generated_ideas WHERE product_id = :pid"),
            ("ideas", "SELECT COUNT(*) FROM ideas WHERE product_id = :pid"),
            ("functional_reports", "SELECT COUNT(*) FROM competitor_functional_reports WHERE product_id = :pid"),
            ("landscape_reports", "SELECT COUNT(*) FROM landscape_opportunity_reports WHERE product_id = :pid"),
            ("synthesis_runs", "SELECT COUNT(*) FROM synthesis_runs WHERE product_id = :pid"),
            ("internal_feedback_imports", "SELECT COUNT(*) FROM internal_feedback_imports WHERE product_id = :pid"),
            ("activity_imports", "SELECT COUNT(*) FROM activity_imports WHERE product_id = :pid"),
        ]

        for name, query in count_queries:
            try:
                table_counts[name] = self.db.execute(
                    text(query), {"pid": product_id}
                ).scalar() or 0
            except Exception:
                table_counts[name] = -1  # table may not exist

        # Count preserved records (SET NULL, not deleted)
        preserved_counts = {}
        preserved_queries = [
            ("queue_jobs", "SELECT COUNT(*) FROM queue_jobs WHERE product_id = :pid"),
            ("llm_usage_logs", "SELECT COUNT(*) FROM llm_usage_logs WHERE product_id = :pid"),
            ("agent_execution_logs", "SELECT COUNT(*) FROM agent_execution_logs WHERE product_id = :pid"),
        ]
        for name, query in preserved_queries:
            try:
                preserved_counts[name] = self.db.execute(
                    text(query), {"pid": product_id}
                ).scalar() or 0
            except Exception:
                preserved_counts[name] = -1

        # Count vector embeddings
        try:
            embedding_counts = VectorService.count_product_embeddings(self.db, product_id)
        except Exception:
            embedding_counts = {}

        # Check for file-based reports
        reports_dir = Path(__file__).parent.parent.parent / "data" / "competitive_reports" / str(product_id)
        file_info = {
            "reports_directory": str(reports_dir),
            "directory_exists": reports_dir.exists(),
        }
        if reports_dir.exists():
            report_runs = [d.name for d in reports_dir.iterdir() if d.is_dir()]
            file_info["report_runs"] = len(report_runs)

        return {
            "product": {
                "id": product.id,
                "name": product.product_name,
                "status": product.status,
                "created_at": str(product.created_at),
            },
            "will_delete": table_counts,
            "will_preserve_with_null_product_id": preserved_counts,
            "embeddings": embedding_counts,
            "files": file_info,
        }

    def delete_product(
        self,
        product_id: int,
        user_id: int,
        dry_run: bool = False
    ) -> Dict[str, Any] | bool:
        """
        Delete a product and all associated data.

        Requires OWNER permission. When dry_run=True, returns a preview
        of what would be deleted without making changes.

        Args:
            product_id: Product ID
            user_id: User deleting the product
            dry_run: If True, return preview without deleting

        Returns:
            - dry_run=True: Dict with deletion preview, or False if not found
            - dry_run=False: True if deleted, False if not found

        Raises:
            PermissionError: If user lacks OWNER permission
        """
        # Check permission
        if not self.permission_service.can_access_product(
            user_id=user_id,
            product_id=product_id,
            required_level=ProductPermissionLevel.OWNER
        ):
            raise PermissionError(
                f"User {user_id} does not have OWNER permission for product {product_id}"
            )

        preview = self.get_delete_preview(product_id)
        if preview is None:
            return False

        if dry_run:
            return preview

        # 1. Delete vector embeddings (not covered by cascades)
        try:
            VectorService.delete_all_product_embeddings(self.db, product_id)
        except Exception as e:
            logger.warning("Failed to delete vector embeddings for product %d: %s", product_id, e)

        # 2. Delete file-based reports
        reports_dir = Path(__file__).parent.parent.parent / "data" / "competitive_reports" / str(product_id)
        if reports_dir.exists():
            try:
                shutil.rmtree(reports_dir)
                logger.info("Deleted report files at %s", reports_dir)
            except Exception as e:
                logger.warning("Failed to delete report files for product %d: %s", product_id, e)

        # 3. Delete the product (ORM cascade + DB-level CASCADE handle related rows)
        product = self.db.query(CIProduct).filter(CIProduct.id == product_id).first()
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

    def _get_source_url(
        self,
        source_type: str,
        source_data: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Extract source URL from product source information.

        Used to populate source_url field in ProductFeature for
        feature exists detection linking.

        Args:
            source_type: Product source type (text, document, url)
            source_data: Product source data

        Returns:
            URL string if available, None otherwise
        """
        if not source_data:
            return None

        if source_type == 'url':
            # Single URL source
            if 'url' in source_data:
                return source_data.get('url')
            # Multi-source mode - return first URL
            if 'sources' in source_data:
                for src in source_data.get('sources', []):
                    if src.get('type') == 'url' and src.get('url'):
                        return src.get('url')
        # For text and document sources, return None (no URL available)
        return None
