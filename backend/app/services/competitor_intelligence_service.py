"""
Competitor Intelligence Service for orchestrating competitor discovery and management.

This service coordinates:
- Competitor research via AI web search
- Differential analysis comparing with previous sessions
- Competitor confirmation and selection
"""

from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from app.models.competitor_intelligence import (
    CompetitorAnalysisSession,
    ProductCompetitor,
    SessionCompetitor
)
from app.agents.competitor_researcher import (
    CompetitorResearcherAgent,
    DifferentialAnalysisAgent
)
from app.services.llm_service import LLMService


class CompetitorIntelligenceService:
    """Service for competitor intelligence operations"""

    def __init__(self, db: Session):
        self.db = db

    async def discover_competitors(
        self,
        session_id: int,
        llm_service: LLMService
    ) -> Dict:
        """
        Discover competitors for a session.

        If session has comparison enabled, performs differential analysis.
        """
        # Get session
        session = self.db.query(CompetitorAnalysisSession).filter(
            CompetitorAnalysisSession.id == session_id
        ).first()

        if not session:
            raise ValueError("Session not found")

        # Preserve user-added competitors before clearing
        user_added_competitors = self.db.query(SessionCompetitor).filter(
            SessionCompetitor.session_id == session_id,
            SessionCompetitor.discovery_source == 'user_added'
        ).all()

        # Clear existing AI-discovered competitors from this session before rediscovery
        # This prevents duplication when user clicks "Re-discover Competitors"
        # but preserves user-added custom competitors
        self.db.query(SessionCompetitor).filter(
            SessionCompetitor.session_id == session_id,
            SessionCompetitor.discovery_source != 'user_added'
        ).delete()
        self.db.commit()

        # Get product info for research
        product_data = session.analyzed_product_structure

        # Run competitor research
        researcher = CompetitorResearcherAgent(
            db=self.db,
            llm_service=llm_service,
            session_id=session_id,
            product_id=session.product_id
        )

        research_result = researcher.execute({
            'product_name': product_data.get('product_name'),
            'product_category': product_data.get('product_category'),
            'core_features': product_data.get('core_features', []),
            'target_users': product_data.get('target_users'),
            'competitor_search_keywords': product_data.get('competitor_search_keywords', [])
        })

        # If differential analysis, compare with previous
        if session.analysis_type == "differential" and session.comparison_to_session_id:
            previous_competitors = self._get_previous_competitors(
                session.comparison_to_session_id
            )

            differential_agent = DifferentialAnalysisAgent(
                db=self.db,
                llm_service=llm_service,
                session_id=session_id,
                product_id=session.product_id
            )

            comparison_result = differential_agent.execute({
                'current_competitors': research_result['competitors'],
                'previous_competitors': previous_competitors,
                'product_name': product_data.get('product_name')
            })

            # Store competitors with status
            stored_competitors = self._store_competitors_with_status(
                session_id=session_id,
                product_id=session.product_id,
                competitors_data=comparison_result['competitors']
            )

            # Add back preserved user-added competitors
            for user_comp in user_added_competitors:
                stored_competitors.append({
                    'id': str(user_comp.id),
                    'name': user_comp.competitor_name,
                    'url': user_comp.competitor_url,
                    'summary': user_comp.ai_summary,
                    'discovery_source': user_comp.discovery_source,
                    'is_new_discovery': user_comp.is_new_discovery,
                    'selected': user_comp.selected_by_user,
                    'status_change': user_comp.status_change
                })

            return {
                'competitors': stored_competitors,
                'change_summary': comparison_result['summary'],
                'research_summary': research_result.get('research_summary'),
                'has_comparison': True
            }

        else:
            # Store competitors without status
            stored_competitors = self._store_competitors_without_status(
                session_id=session_id,
                product_id=session.product_id,
                competitors_data=research_result['competitors']
            )

            # Add back preserved user-added competitors
            for user_comp in user_added_competitors:
                stored_competitors.append({
                    'id': str(user_comp.id),
                    'name': user_comp.competitor_name,
                    'url': user_comp.competitor_url,
                    'summary': user_comp.ai_summary,
                    'discovery_source': user_comp.discovery_source,
                    'is_new_discovery': user_comp.is_new_discovery,
                    'selected': user_comp.selected_by_user
                })

            return {
                'competitors': stored_competitors,
                'change_summary': None,
                'research_summary': research_result.get('research_summary'),
                'has_comparison': False
            }

    def _get_previous_competitors(self, previous_session_id: int) -> List[Dict]:
        """Get competitors from previous session"""
        competitors = self.db.query(SessionCompetitor).filter(
            SessionCompetitor.session_id == previous_session_id,
            SessionCompetitor.selected_by_user == True
        ).all()

        return [
            {
                'id': str(comp.id),
                'name': comp.competitor_name,
                'url': comp.competitor_url,
                'summary': comp.ai_summary
            }
            for comp in competitors
        ]

    def _store_competitors_with_status(
        self,
        session_id: int,
        product_id: int,
        competitors_data: List[Dict]
    ) -> List[Dict]:
        """Store competitors with change status from differential analysis"""
        stored = []

        for comp_data in competitors_data:
            # Get or create product-level competitor
            product_competitor = self._get_or_create_product_competitor(
                product_id=product_id,
                competitor_name=comp_data['name'],
                competitor_url=comp_data['url'],
                session_id=session_id
            )

            # Create session-specific competitor
            session_competitor = SessionCompetitor(
                session_id=session_id,
                product_competitor_id=product_competitor.id,
                competitor_name=comp_data['name'],
                competitor_url=comp_data['url'],
                ai_summary=comp_data.get('summary'),
                discovery_source='ai_search',
                is_new_discovery=(comp_data['status'] == 'new'),
                selected_by_user=False,  # User will select later
                status_change=comp_data['status']
            )

            self.db.add(session_competitor)
            self.db.commit()
            self.db.refresh(session_competitor)

            stored.append({
                'id': str(session_competitor.id),
                'name': comp_data['name'],
                'url': comp_data['url'],
                'summary': comp_data.get('summary'),
                'relevance_score': comp_data.get('relevance_score'),
                'status': comp_data['status'],
                'status_explanation': comp_data.get('status_explanation'),
                'significance': comp_data.get('significance'),
                'selected': False
            })

        return stored

    def _store_competitors_without_status(
        self,
        session_id: int,
        product_id: int,
        competitors_data: List[Dict]
    ) -> List[Dict]:
        """Store competitors without change status (first analysis)"""
        stored = []

        for comp_data in competitors_data:
            # Get or create product-level competitor
            product_competitor = self._get_or_create_product_competitor(
                product_id=product_id,
                competitor_name=comp_data['name'],
                competitor_url=comp_data['url'],
                session_id=session_id
            )

            # Create session-specific competitor
            session_competitor = SessionCompetitor(
                session_id=session_id,
                product_competitor_id=product_competitor.id,
                competitor_name=comp_data['name'],
                competitor_url=comp_data['url'],
                ai_summary=comp_data.get('summary'),
                discovery_source='ai_search',
                is_new_discovery=True,
                selected_by_user=False,
                status_change=None
            )

            self.db.add(session_competitor)
            self.db.commit()
            self.db.refresh(session_competitor)

            stored.append({
                'id': str(session_competitor.id),
                'name': comp_data['name'],
                'url': comp_data['url'],
                'summary': comp_data.get('summary'),
                'relevance_score': comp_data.get('relevance_score'),
                'selected': False
            })

        return stored

    def _get_or_create_product_competitor(
        self,
        product_id: int,
        competitor_name: str,
        competitor_url: str,
        session_id: int
    ) -> ProductCompetitor:
        """Get existing or create new product-level competitor"""
        # Try to find existing by name
        existing = self.db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == product_id,
            ProductCompetitor.competitor_name == competitor_name
        ).first()

        if existing:
            # Update last_seen
            existing.last_seen_session_id = session_id
            existing.status = "active"
            self.db.commit()
            return existing

        # Create new
        product_competitor = ProductCompetitor(
            product_id=product_id,
            competitor_name=competitor_name,
            competitor_url=competitor_url,
            first_discovered_session_id=session_id,
            last_seen_session_id=session_id,
            status="active"
        )

        self.db.add(product_competitor)
        self.db.commit()
        self.db.refresh(product_competitor)

        return product_competitor

    async def confirm_competitors(
        self,
        session_id: int,
        selected_ids: List[int],
        custom_competitors: Optional[List[Dict]] = None
    ) -> Dict:
        """
        User confirms which competitors to analyze.

        Args:
            session_id: The session ID
            selected_ids: IDs of session_competitors to include
            custom_competitors: Additional competitors added manually
        """
        # Update selected competitors
        self.db.query(SessionCompetitor).filter(
            SessionCompetitor.session_id == session_id
        ).update({"selected_by_user": False})

        if selected_ids:
            self.db.query(SessionCompetitor).filter(
                SessionCompetitor.id.in_(selected_ids)
            ).update({"selected_by_user": True}, synchronize_session=False)

        # Add custom competitors
        if custom_competitors:
            session = self.db.query(CompetitorAnalysisSession).filter(
                CompetitorAnalysisSession.id == session_id
            ).first()

            for custom in custom_competitors:
                product_competitor = self._get_or_create_product_competitor(
                    product_id=session.product_id,
                    competitor_name=custom['name'],
                    competitor_url=custom.get('url', ''),
                    session_id=session_id
                )

                session_competitor = SessionCompetitor(
                    session_id=session_id,
                    product_competitor_id=product_competitor.id,
                    competitor_name=custom['name'],
                    competitor_url=custom.get('url', ''),
                    ai_summary=custom.get('summary', 'User-added competitor'),
                    discovery_source='user_added',
                    is_new_discovery=True,
                    selected_by_user=True,
                    status_change=None
                )

                self.db.add(session_competitor)

        self.db.commit()

        # Get count of selected
        selected_count = self.db.query(SessionCompetitor).filter(
            SessionCompetitor.session_id == session_id,
            SessionCompetitor.selected_by_user == True
        ).count()

        return {
            'confirmed': True,
            'selected_count': selected_count
        }

    async def copy_competitors_from_session(
        self,
        from_session_id: int,
        to_session_id: int
    ) -> Dict:
        """
        Copy competitors from one session to another, avoiding duplicates.

        Args:
            from_session_id: Source session ID
            to_session_id: Destination session ID

        Returns:
            Dict with copied_count and skipped_count
        """
        # Get source competitors
        source_competitors = self.db.query(SessionCompetitor).filter(
            SessionCompetitor.session_id == from_session_id
        ).all()

        # Get destination session
        dest_session = self.db.query(CompetitorAnalysisSession).filter(
            CompetitorAnalysisSession.id == to_session_id
        ).first()

        if not dest_session:
            raise ValueError(f"Destination session {to_session_id} not found")

        copied_count = 0
        skipped_count = 0

        for source_comp in source_competitors:
            # Check if this competitor already exists in destination session
            # Check by product_competitor_id if available, otherwise by name
            if source_comp.product_competitor_id:
                existing = self.db.query(SessionCompetitor).filter(
                    SessionCompetitor.session_id == to_session_id,
                    SessionCompetitor.product_competitor_id == source_comp.product_competitor_id
                ).first()
            else:
                existing = self.db.query(SessionCompetitor).filter(
                    SessionCompetitor.session_id == to_session_id,
                    SessionCompetitor.competitor_name == source_comp.competitor_name
                ).first()

            if existing:
                # Already exists, skip
                skipped_count += 1
                continue

            # Create copy in destination session
            new_competitor = SessionCompetitor(
                session_id=to_session_id,
                product_competitor_id=source_comp.product_competitor_id,
                competitor_name=source_comp.competitor_name,
                competitor_url=source_comp.competitor_url,
                ai_summary=source_comp.ai_summary,
                discovery_source=source_comp.discovery_source,
                is_new_discovery=False,  # Not new since it's copied
                selected_by_user=source_comp.selected_by_user,  # Preserve selection
                status_change=None
            )

            self.db.add(new_competitor)
            copied_count += 1

        self.db.commit()

        return {
            'copied_count': copied_count,
            'skipped_count': skipped_count,
            'total_source': len(source_competitors)
        }

    async def get_session_competitors(
        self,
        session_id: int
    ) -> List[Dict]:
        """Get all competitors for a session"""
        competitors = self.db.query(SessionCompetitor).filter(
            SessionCompetitor.session_id == session_id
        ).all()

        return [
            {
                'id': str(comp.id),
                'name': comp.competitor_name,
                'url': comp.competitor_url,
                'summary': comp.ai_summary,
                'discovery_source': comp.discovery_source,
                'is_new_discovery': comp.is_new_discovery,
                'selected': comp.selected_by_user,
                'status_change': comp.status_change
            }
            for comp in competitors
        ]
