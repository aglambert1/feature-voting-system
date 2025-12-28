"""
Competitive Monitor Service for Phase 4.

This service orchestrates competitive monitoring:
1. Runs feature extraction for all competitors
2. Creates snapshots of current state
3. Compares with previous snapshots to detect changes
4. Generates alerts for significant changes
5. Adds alerts to PM review queue

The service uses existing agents (FeatureExtractorAgent) and coordinates
the monitoring workflow.
"""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Tuple
from sqlalchemy.orm import Session

from app.models.competitor_intelligence import (
    CIProduct, ProductCompetitor, ProductCompetitorFeature
)
from app.models.pm_review import (
    CompetitorSnapshot, MonitoringConfig, AlertType
)
from app.services.pm_review_service import PMReviewService
from app.services.llm_service import LLMService
from app.agents.feature_extractor import FeatureExtractorAgent


class CompetitiveMonitorService:
    """
    Orchestrates competitive monitoring for products.

    This service:
    - Monitors all active competitors for a product
    - Detects feature changes (new, modified, removed)
    - Creates historical snapshots
    - Generates alerts for PM review
    """

    def __init__(self, db: Session):
        self.db = db
        self.pm_service = PMReviewService(db)

    def run_monitoring(
        self,
        product_id: int,
        job_id: Optional[int] = None,
        force_full: bool = False,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Run competitive monitoring for a product.

        Args:
            product_id: Product to monitor
            job_id: Optional queue job ID for tracking
            force_full: If True, re-extract all features instead of differential
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary with monitoring results
        """
        # Get product
        product = self.db.query(CIProduct).filter(CIProduct.id == product_id).first()
        if not product:
            raise ValueError(f"Product {product_id} not found")

        # Get monitoring config
        config = self.pm_service.get_monitoring_config(product_id)
        if not config:
            config = self.pm_service.create_or_update_monitoring_config(
                product_id=product_id,
                enabled=True,
                frequency="weekly"
            )

        # Get active competitors
        competitors = self.db.query(ProductCompetitor).filter(
            ProductCompetitor.product_id == product_id,
            ProductCompetitor.status == 'active'
        ).all()

        if not competitors:
            return {
                'product_id': product_id,
                'message': 'No active competitors to monitor',
                'competitors_monitored': 0,
                'alerts_generated': 0,
            }

        if progress_callback:
            progress_callback(15.0, f"Found {len(competitors)} competitors to monitor...")

        # Monitor each competitor
        results = []
        total_alerts = 0
        new_features_total = 0
        removed_features_total = 0

        for i, competitor in enumerate(competitors):
            try:
                if progress_callback:
                    pct = 20 + (60 * (i / len(competitors)))
                    progress_callback(pct, f"Monitoring {competitor.competitor_name}...")

                result = self._monitor_competitor(
                    competitor=competitor,
                    product=product,
                    job_id=job_id,
                    config=config,
                    force_full=force_full
                )
                results.append(result)

                if result.get('alert_generated'):
                    total_alerts += 1
                new_features_total += result.get('new_features_count', 0)
                removed_features_total += result.get('removed_features_count', 0)

            except Exception as e:
                print(f"[CompetitiveMonitorService] Error monitoring {competitor.competitor_name}: {e}")
                results.append({
                    'competitor_id': competitor.id,
                    'competitor_name': competitor.competitor_name,
                    'error': str(e),
                })

        # Update monitoring config timestamps
        if progress_callback:
            progress_callback(85.0, "Updating monitoring timestamps...")

        config.last_monitored_at = datetime.utcnow()
        config.next_scheduled_at = self._calculate_next_schedule(config.monitoring_frequency)
        self.db.commit()

        if progress_callback:
            progress_callback(95.0, "Finalizing monitoring results...")

        return {
            'product_id': product_id,
            'product_name': product.product_name,
            'competitors_monitored': len(competitors),
            'alerts_generated': total_alerts,
            'new_features_total': new_features_total,
            'removed_features_total': removed_features_total,
            'results': results,
            'monitoring_completed_at': datetime.utcnow().isoformat(),
        }

    def _monitor_competitor(
        self,
        competitor: ProductCompetitor,
        product: CIProduct,
        job_id: Optional[int],
        config: MonitoringConfig,
        force_full: bool = False
    ) -> Dict[str, Any]:
        """
        Monitor a single competitor for changes.

        Args:
            competitor: Competitor to monitor
            product: Product being monitored
            job_id: Queue job ID
            config: Monitoring configuration
            force_full: Force full re-extraction

        Returns:
            Dictionary with monitoring results for this competitor
        """
        # Get current features
        current_features = self.db.query(ProductCompetitorFeature).filter(
            ProductCompetitorFeature.product_competitor_id == competitor.id,
            ProductCompetitorFeature.status == 'active'
        ).all()

        # Build features JSON for snapshot
        features_json = [
            {
                'id': f.id,
                'name': f.feature_name,
                'description': f.feature_description,
                'category': f.feature_category,
            }
            for f in current_features
        ]

        # Calculate hash for change detection
        features_hash = self._calculate_features_hash(features_json)

        # Get previous snapshot
        previous_snapshot = self.db.query(CompetitorSnapshot).filter(
            CompetitorSnapshot.product_competitor_id == competitor.id
        ).order_by(CompetitorSnapshot.snapshot_date.desc()).first()

        # Detect changes
        changes_detected = None
        has_changes = False
        change_summary = None

        if previous_snapshot:
            if previous_snapshot.features_hash != features_hash or force_full:
                # Changes detected - compare in detail
                changes_detected = self._detect_feature_changes(
                    previous_features=previous_snapshot.features_json or [],
                    current_features=features_json
                )
                has_changes = bool(
                    changes_detected.get('new_features') or
                    changes_detected.get('removed_features') or
                    changes_detected.get('modified_features')
                )
                change_summary = self._generate_change_summary(changes_detected, competitor.competitor_name)
        else:
            # First snapshot for this competitor
            changes_detected = {
                'new_features': features_json,
                'removed_features': [],
                'modified_features': [],
                'is_new_competitor': True,
            }
            has_changes = True
            change_summary = f"First snapshot for {competitor.competitor_name}: {len(features_json)} features discovered."

        # Create snapshot
        snapshot = CompetitorSnapshot(
            product_competitor_id=competitor.id,
            snapshot_date=datetime.utcnow(),
            features_json=features_json,
            features_hash=features_hash,
            feature_count=len(features_json),
            changes_detected=changes_detected,
            has_changes=has_changes,
            change_summary=change_summary,
            queue_job_id=job_id,
            previous_snapshot_id=previous_snapshot.id if previous_snapshot else None,
        )
        self.db.add(snapshot)
        self.db.flush()

        # Update competitor last monitored
        competitor.last_monitored_at = datetime.utcnow()

        # Generate alert if changes exceed threshold
        alert_generated = False
        if has_changes and self._should_generate_alert(changes_detected, config):
            alert_type = self._determine_alert_type(changes_detected)
            severity = self._determine_severity(changes_detected)

            self.pm_service.add_competitive_alert(
                snapshot=snapshot,
                alert_type=alert_type,
                severity=severity,
            )
            alert_generated = True

        self.db.commit()

        return {
            'competitor_id': competitor.id,
            'competitor_name': competitor.competitor_name,
            'snapshot_id': snapshot.id,
            'feature_count': len(features_json),
            'has_changes': has_changes,
            'new_features_count': len(changes_detected.get('new_features', [])) if changes_detected else 0,
            'removed_features_count': len(changes_detected.get('removed_features', [])) if changes_detected else 0,
            'modified_features_count': len(changes_detected.get('modified_features', [])) if changes_detected else 0,
            'alert_generated': alert_generated,
            'change_summary': change_summary,
        }

    def _calculate_features_hash(self, features_json: List[Dict]) -> str:
        """Calculate SHA-256 hash of features for change detection."""
        # Sort by name for consistent hashing
        sorted_features = sorted(features_json, key=lambda f: f.get('name', ''))
        content = json.dumps(sorted_features, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def _detect_feature_changes(
        self,
        previous_features: List[Dict],
        current_features: List[Dict]
    ) -> Dict[str, List]:
        """
        Detect changes between previous and current feature sets.

        Returns dict with new_features, removed_features, modified_features.
        """
        prev_by_name = {f['name']: f for f in previous_features}
        curr_by_name = {f['name']: f for f in current_features}

        new_features = []
        removed_features = []
        modified_features = []

        # Find new and modified features
        for name, curr_feat in curr_by_name.items():
            if name not in prev_by_name:
                new_features.append(curr_feat)
            else:
                prev_feat = prev_by_name[name]
                # Check for modifications (description or category changed)
                if (prev_feat.get('description') != curr_feat.get('description') or
                    prev_feat.get('category') != curr_feat.get('category')):
                    modified_features.append({
                        'feature': curr_feat,
                        'changes': {
                            'description_changed': prev_feat.get('description') != curr_feat.get('description'),
                            'category_changed': prev_feat.get('category') != curr_feat.get('category'),
                            'previous_description': prev_feat.get('description'),
                            'previous_category': prev_feat.get('category'),
                        }
                    })

        # Find removed features
        for name, prev_feat in prev_by_name.items():
            if name not in curr_by_name:
                removed_features.append(prev_feat)

        return {
            'new_features': new_features,
            'removed_features': removed_features,
            'modified_features': modified_features,
            'is_new_competitor': False,
        }

    def _generate_change_summary(self, changes: Dict, competitor_name: str) -> str:
        """Generate human-readable summary of changes."""
        parts = []

        new_count = len(changes.get('new_features', []))
        removed_count = len(changes.get('removed_features', []))
        modified_count = len(changes.get('modified_features', []))

        if new_count:
            parts.append(f"{new_count} new feature{'s' if new_count > 1 else ''}")
        if removed_count:
            parts.append(f"{removed_count} removed feature{'s' if removed_count > 1 else ''}")
        if modified_count:
            parts.append(f"{modified_count} modified feature{'s' if modified_count > 1 else ''}")

        if parts:
            return f"{competitor_name}: {', '.join(parts)}"
        return f"{competitor_name}: No significant changes"

    def _should_generate_alert(self, changes: Dict, config: MonitoringConfig) -> bool:
        """Determine if changes warrant an alert based on config."""
        if not changes:
            return False

        new_features = changes.get('new_features', [])
        removed_features = changes.get('removed_features', [])
        is_new = changes.get('is_new_competitor', False)

        # Check config settings
        if is_new and config.alert_on_new_competitors:
            return True

        if config.alert_on_new_features and len(new_features) >= config.min_feature_change_threshold:
            return True

        if config.alert_on_removed_features and len(removed_features) >= config.min_feature_change_threshold:
            return True

        return False

    def _determine_alert_type(self, changes: Dict) -> AlertType:
        """Determine the appropriate alert type based on changes."""
        if changes.get('is_new_competitor'):
            return AlertType.NEW_COMPETITOR

        new_features = changes.get('new_features', [])
        removed_features = changes.get('removed_features', [])

        # Major feature launch takes precedence
        if len(new_features) >= 3:
            return AlertType.MAJOR_FEATURE_LAUNCH
        elif new_features:
            return AlertType.MAJOR_FEATURE_LAUNCH  # Any new feature is notable
        elif removed_features:
            return AlertType.FEATURE_REMOVED

        return AlertType.TREND_DETECTED

    def _determine_severity(self, changes: Dict) -> str:
        """Determine alert severity based on changes."""
        if changes.get('is_new_competitor'):
            return "warning"

        new_features = changes.get('new_features', [])
        removed_features = changes.get('removed_features', [])

        total_changes = len(new_features) + len(removed_features)

        if total_changes >= 5:
            return "critical"
        elif total_changes >= 3:
            return "warning"
        else:
            return "info"

    def _calculate_next_schedule(self, frequency: str) -> datetime:
        """Calculate next scheduled monitoring time based on frequency."""
        now = datetime.utcnow()

        if frequency == "daily":
            return now + timedelta(days=1)
        elif frequency == "weekly":
            return now + timedelta(weeks=1)
        elif frequency == "biweekly":
            return now + timedelta(weeks=2)
        elif frequency == "monthly":
            return now + timedelta(days=30)
        else:
            return now + timedelta(weeks=1)  # Default to weekly

    def run_feature_extraction(
        self,
        competitor: ProductCompetitor,
        product_id: int,
        force_full: bool = False
    ) -> List[Dict]:
        """
        Run feature extraction for a competitor.

        Uses the FeatureExtractorAgent to discover features.
        This is called when we want to refresh competitor features
        before taking a snapshot.

        Args:
            competitor: Competitor to extract features from
            product_id: Product ID
            force_full: If True, ignore previous features

        Returns:
            List of extracted feature dictionaries
        """
        llm_service = LLMService()
        agent = FeatureExtractorAgent(
            db=self.db,
            llm_service=llm_service,
            product_id=product_id
        )

        # Get previous features for differential extraction
        previous_features = []
        if not force_full:
            existing = self.db.query(ProductCompetitorFeature).filter(
                ProductCompetitorFeature.product_competitor_id == competitor.id,
                ProductCompetitorFeature.status == 'active'
            ).all()
            previous_features = [
                {
                    'id': str(f.id),
                    'name': f.feature_name,
                    'description': f.feature_description,
                    'category': f.feature_category,
                }
                for f in existing
            ]

        # Build input
        agent_input = {
            'competitor_name': competitor.competitor_name,
            'competitor_url': competitor.competitor_url,
        }
        if previous_features:
            agent_input['previous_features'] = previous_features

        # Execute agent
        result = agent.execute(agent_input)
        features = result.get('features', [])

        # Store new features
        new_features = []
        for feat_data in features:
            change_type = feat_data.get('change_type', 'new')

            if change_type == 'removed':
                # Mark as inactive
                prev_id = feat_data.get('previous_feature_id')
                if prev_id:
                    try:
                        prev_feature = self.db.query(ProductCompetitorFeature).filter(
                            ProductCompetitorFeature.id == int(prev_id)
                        ).first()
                        if prev_feature:
                            prev_feature.status = 'removed'
                    except (ValueError, TypeError):
                        pass
            else:
                # Create new feature
                feature = ProductCompetitorFeature(
                    product_competitor_id=competitor.id,
                    feature_name=feat_data.get('name', ''),
                    feature_description=feat_data.get('description', ''),
                    feature_category=feat_data.get('category', ''),
                    status='active'
                )
                self.db.add(feature)
                self.db.flush()
                new_features.append({
                    'id': feature.id,
                    'name': feature.feature_name,
                    'description': feature.feature_description,
                    'category': feature.feature_category,
                })

        self.db.commit()
        return new_features
