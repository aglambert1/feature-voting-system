"""
Session Service for managing competitor analysis sessions.

This service handles the creation and management of analysis sessions.
Sessions are lightweight workflow containers that track the progression
through competitive intelligence stages (competitor discovery, feature analysis, etc.).

Product creation and analysis are now independent operations handled by ProductService.
"""

from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.models.competitor_intelligence import (
    CIProduct, CompetitorAnalysisSession, ProductPermissionLevel
)
from app.services.permission_service import PermissionService


class SessionService:
    """Service for managing analysis sessions."""

    def __init__(self, db: Session):
        self.db = db
        self.permission_service = PermissionService(db)

    def create_session(
        self,
        user_id: int,
        product_id: int,
        session_name: Optional[str] = None,
        enable_comparison: bool = True
    ) -> CompetitorAnalysisSession:
        """
        Create a new analysis session for an existing product.

        Sessions are workflow containers that track progression through
        competitive intelligence stages. Product must already exist and
        be analyzed before creating a session.

        Args:
            user_id: ID of the user creating the session
            product_id: ID of existing product (must be analyzed)
            session_name: Optional session name
            enable_comparison: Enable differential analysis if previous sessions exist

        Returns:
            Created CompetitorAnalysisSession

        Raises:
            PermissionError: If user lacks VIEW permission
            ValueError: If product not found or not analyzed
        """
        # Check permission - user needs at least VIEW access
        if not self.permission_service.can_access_product(
            user_id=user_id,
            product_id=product_id,
            required_level=ProductPermissionLevel.VIEW
        ):
            raise PermissionError(
                f"User {user_id} does not have VIEW permission for product {product_id}"
            )

        # Get product and verify it's analyzed
        product = self.db.query(CIProduct).filter(CIProduct.id == product_id).first()
        if not product:
            raise ValueError(f"Product {product_id} not found")

        if not product.structured_product_data:
            raise ValueError(
                f"Product {product_id} has not been analyzed yet. "
                "Please analyze the product before creating a session."
            )

        # Determine session number
        session_number = self._get_next_session_number(product.id)

        # Check if we should do comparison analysis
        analysis_type = "full"
        comparison_to_session_id = None

        if session_number > 1 and enable_comparison:
            # Get previous session for comparison
            previous_session = self._get_previous_session(product.id)
            if previous_session:
                analysis_type = "differential"
                comparison_to_session_id = previous_session.id

        # Create session (lightweight - just tracks workflow)
        session = CompetitorAnalysisSession(
            product_id=product.id,
            user_id=user_id,
            session_number=session_number,
            session_name=session_name or f"Session {session_number}",
            analysis_type=analysis_type,
            comparison_to_session_id=comparison_to_session_id,
            product_source_type="text",  # Legacy field - not critical
            product_source_data=None,
            analyzed_product_structure=product.structured_product_data,
            status="active"
        )

        try:
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)
        except IntegrityError as e:
            self.db.rollback()
            raise ValueError(f"Failed to create session: {str(e)}")

        return session

    def get_session(
        self,
        session_id: int,
        user_id: int
    ) -> Optional[CompetitorAnalysisSession]:
        """
        Get session by ID with permission check.

        Args:
            session_id: Session ID
            user_id: User ID

        Returns:
            Session if found and user has access, None otherwise
        """
        session = self.db.query(CompetitorAnalysisSession).filter(
            CompetitorAnalysisSession.id == session_id
        ).first()

        if not session:
            return None

        # Check if user has permission to view the product
        if not self.permission_service.can_access_product(
            user_id=user_id,
            product_id=session.product_id,
            required_level=ProductPermissionLevel.VIEW
        ):
            return None

        return session

    def list_product_sessions(
        self,
        product_id: int,
        user_id: int
    ) -> list[CompetitorAnalysisSession]:
        """
        List all sessions for a product.

        Args:
            product_id: Product ID
            user_id: User ID

        Returns:
            List of sessions ordered by session number (newest first)

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

        return self.db.query(CompetitorAnalysisSession).filter(
            CompetitorAnalysisSession.product_id == product_id
        ).order_by(CompetitorAnalysisSession.session_number.desc()).all()

    def update_session_status(
        self,
        session_id: int,
        user_id: int,
        status: str
    ) -> bool:
        """
        Update session status.

        Args:
            session_id: Session ID
            user_id: User ID
            status: New status (active, completed, archived)

        Returns:
            True if updated, False if not found

        Raises:
            PermissionError: If user lacks EDIT permission
        """
        session = self.db.query(CompetitorAnalysisSession).filter(
            CompetitorAnalysisSession.id == session_id
        ).first()

        if not session:
            return False

        # Check permission - user needs EDIT access to modify session
        if not self.permission_service.can_access_product(
            user_id=user_id,
            product_id=session.product_id,
            required_level=ProductPermissionLevel.EDIT
        ):
            raise PermissionError(
                f"User {user_id} does not have EDIT permission for product {session.product_id}"
            )

        session.status = status

        if status == "completed":
            session.completed_at = datetime.utcnow()

        self.db.commit()
        return True

    def delete_session(
        self,
        session_id: int,
        user_id: int
    ) -> bool:
        """
        Delete a session.

        Args:
            session_id: Session ID
            user_id: User ID

        Returns:
            True if deleted, False if not found

        Raises:
            PermissionError: If user lacks ADMIN permission
        """
        session = self.db.query(CompetitorAnalysisSession).filter(
            CompetitorAnalysisSession.id == session_id
        ).first()

        if not session:
            return False

        # Check permission - user needs ADMIN access to delete session
        if not self.permission_service.can_access_product(
            user_id=user_id,
            product_id=session.product_id,
            required_level=ProductPermissionLevel.ADMIN
        ):
            raise PermissionError(
                f"User {user_id} does not have ADMIN permission for product {session.product_id}"
            )

        self.db.delete(session)
        self.db.commit()
        return True

    def _get_next_session_number(self, product_id: int) -> int:
        """Get the next session number for a product."""
        max_session = self.db.query(
            func.max(CompetitorAnalysisSession.session_number)
        ).filter(
            CompetitorAnalysisSession.product_id == product_id
        ).scalar()

        return (max_session or 0) + 1

    def _get_previous_session(
        self,
        product_id: int
    ) -> Optional[CompetitorAnalysisSession]:
        """Get the most recent completed session for a product."""
        return self.db.query(CompetitorAnalysisSession).filter(
            CompetitorAnalysisSession.product_id == product_id,
            CompetitorAnalysisSession.status == "completed"
        ).order_by(
            CompetitorAnalysisSession.session_number.desc()
        ).first()
