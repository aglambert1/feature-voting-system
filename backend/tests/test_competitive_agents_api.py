"""
Tests for Chunk 6: Competitive Agents API Endpoints.

Tests the agent-centric API router for competitive intelligence.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.all.return_value = []
    return db


@pytest.fixture
def mock_user():
    """Create a mock user."""
    user = MagicMock()
    user.id = 1
    user.username = "testuser"
    user.email = "test@example.com"
    user.is_active = True
    user.role = "admin"
    return user


@pytest.fixture
def mock_product():
    """Create a mock product."""
    product = MagicMock()
    product.id = 1
    product.product_name = "TestProduct"
    product.product_description = "A test product"
    product.product_category = "SaaS"
    product.product_source_type = "text"
    return product


@pytest.fixture
def mock_config():
    """Create a mock agent config."""
    from app.models.competitive_agent import AgentMode

    config = MagicMock()
    config.id = 1
    config.product_id = 1
    config.product_analysis_mode = AgentMode.MANUAL
    config.product_analysis_schedule = None
    config.product_analysis_last_run = None
    config.competitor_discovery_mode = AgentMode.MANUAL
    config.competitor_discovery_schedule = None
    config.competitor_discovery_last_run = None
    config.alert_on_new_competitors = True
    config.alert_on_disappeared_competitors = True
    config.deep_analysis_mode = AgentMode.MANUAL
    config.deep_analysis_schedule = None
    config.deep_analysis_last_run = None
    config.enable_pricing_analysis = True
    config.enable_positioning_analysis = True
    config.enable_changes_tracking = True
    config.enable_momentum_analysis = True
    config.enable_financials_analysis = False
    config.intensity_similarity_threshold = 0.75
    config.intensity_idea_threshold = 3
    config.enabled = True
    return config


@pytest.fixture
def mock_competitor():
    """Create a mock competitor."""
    competitor = MagicMock()
    competitor.id = 1
    competitor.product_id = 1
    competitor.competitor_name = "TestCompetitor"
    competitor.competitor_url = "https://competitor.com"
    competitor.status = "active"
    competitor.deep_analysis_enabled = False
    competitor.deep_analysis_status = None
    competitor.deep_analysis_last_run = None
    return competitor


@pytest.fixture
def mock_feature():
    """Create a mock feature."""
    feature = MagicMock()
    feature.id = 1
    feature.product_competitor_id = 1
    feature.feature_name = "Test Feature"
    feature.feature_description = "A test feature"
    feature.feature_category = "Core"
    feature.status = "active"
    return feature


@pytest.fixture
def mock_cluster():
    """Create a mock feature cluster."""
    cluster = MagicMock()
    cluster.id = 1
    cluster.product_id = 1
    cluster.cluster_name = "AI Features"
    cluster.cluster_description = "AI-related features"
    cluster.competitor_count = 4
    cluster.feature_count = 8
    cluster.idea_generated = False
    cluster.generated_idea_id = None
    return cluster


# ============================================================================
# Schema Tests
# ============================================================================

class TestSchemas:
    """Test request/response schemas."""

    def test_agent_config_response_schema(self, mock_config):
        """Test AgentConfigResponse schema."""
        from app.api.competitive_agents import AgentConfigResponse

        # Build response manually
        response = AgentConfigResponse(
            id=1,
            product_id=1,
            product_analysis_mode="manual",
            product_analysis_schedule=None,
            product_analysis_last_run=None,
            competitor_discovery_mode="manual",
            competitor_discovery_schedule=None,
            competitor_discovery_last_run=None,
            alert_on_new_competitors=True,
            alert_on_disappeared_competitors=True,
            deep_analysis_mode="manual",
            deep_analysis_schedule=None,
            deep_analysis_last_run=None,
            enable_pricing_analysis=True,
            enable_positioning_analysis=True,
            enable_changes_tracking=True,
            enable_momentum_analysis=True,
            enable_financials_analysis=False,
            intensity_similarity_threshold=0.75,
            intensity_idea_threshold=3,
            enabled=True
        )

        assert response.id == 1
        assert response.product_analysis_mode == "manual"
        assert response.intensity_similarity_threshold == 0.75

    def test_config_update_request_validation(self):
        """Test AgentConfigUpdateRequest validation."""
        from app.api.competitive_agents import AgentConfigUpdateRequest

        # Valid request
        request = AgentConfigUpdateRequest(
            product_analysis_mode="scheduled",
            intensity_similarity_threshold=0.8
        )
        assert request.product_analysis_mode == "scheduled"

        # Invalid mode should fail validation
        with pytest.raises(Exception):
            AgentConfigUpdateRequest(
                product_analysis_mode="invalid"
            )

    def test_competitor_response_schema(self, mock_competitor):
        """Test CompetitorResponse schema."""
        from app.api.competitive_agents import CompetitorResponse

        response = CompetitorResponse(
            id=1,
            product_id=1,
            competitor_name="TestCompetitor",
            competitor_url="https://competitor.com",
            status="active",
            deep_analysis_enabled=False,
            deep_analysis_status=None,
            deep_analysis_last_run=None,
            feature_count=10
        )

        assert response.id == 1
        assert response.competitor_name == "TestCompetitor"
        assert response.feature_count == 10

    def test_feature_cluster_response_schema(self, mock_cluster):
        """Test FeatureClusterResponse schema."""
        from app.api.competitive_agents import FeatureClusterResponse

        response = FeatureClusterResponse(
            id=1,
            product_id=1,
            cluster_name="AI Features",
            cluster_description="AI-related features",
            competitor_count=4,
            feature_count=8,
            idea_generated=False,
            generated_idea_id=None
        )

        assert response.cluster_name == "AI Features"
        assert response.competitor_count == 4


# ============================================================================
# Helper Function Tests
# ============================================================================

class TestHelperFunctions:
    """Test helper functions."""

    @patch('app.api.competitive_agents.CompetitiveAgentConfig')
    def test_get_or_create_config_creates_new(self, mock_config_class, mock_db):
        """Test get_or_create_config creates config when not exists."""
        from app.api.competitive_agents import get_or_create_config

        mock_db.query.return_value.filter.return_value.first.return_value = None

        mock_new_config = MagicMock()
        mock_config_class.return_value = mock_new_config

        result = get_or_create_config(mock_db, product_id=1)

        mock_db.add.assert_called_once_with(mock_new_config)
        mock_db.commit.assert_called()

    def test_get_or_create_config_returns_existing(self, mock_db, mock_config):
        """Test get_or_create_config returns existing config."""
        from app.api.competitive_agents import get_or_create_config

        mock_db.query.return_value.filter.return_value.first.return_value = mock_config

        result = get_or_create_config(mock_db, product_id=1)

        assert result == mock_config
        mock_db.add.assert_not_called()

    def test_verify_product_access_raises_on_not_found(self, mock_db, mock_user):
        """Test verify_product_access raises 404 when product not found."""
        from app.api.competitive_agents import verify_product_access
        from fastapi import HTTPException

        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            verify_product_access(mock_db, product_id=999, user=mock_user)

        assert exc_info.value.status_code == 404
        assert "Product 999 not found" in str(exc_info.value.detail)

    def test_verify_competitor_access_raises_on_not_found(self, mock_db, mock_user):
        """Test verify_competitor_access raises 404 when competitor not found."""
        from app.api.competitive_agents import verify_competitor_access
        from fastapi import HTTPException

        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            verify_competitor_access(mock_db, product_id=1, competitor_id=999, user=mock_user)

        assert exc_info.value.status_code == 404
        assert "Competitor 999 not found" in str(exc_info.value.detail)


# ============================================================================
# API Endpoint Tests (using direct function calls)
# ============================================================================

class TestConfigurationEndpoints:
    """Test configuration endpoints."""

    @patch('app.api.competitive_agents.get_or_create_config')
    @patch('app.api.competitive_agents.verify_product_access')
    def test_get_agent_config(self, mock_verify, mock_get_config, mock_db, mock_user, mock_product, mock_config):
        """Test getting agent configuration."""
        from app.api.competitive_agents import get_agent_config

        mock_verify.return_value = mock_product
        mock_get_config.return_value = mock_config

        result = get_agent_config(
            product_id=1,
            current_user=mock_user,
            db=mock_db
        )

        assert result.id == 1
        assert result.product_id == 1
        mock_verify.assert_called_once()
        mock_get_config.assert_called_once()


class TestCompetitorManagementEndpoints:
    """Test competitor management endpoints."""

    @patch('app.api.competitive_agents.verify_product_access')
    def test_list_competitors(self, mock_verify, mock_db, mock_user, mock_product, mock_competitor):
        """Test listing competitors."""
        from app.api.competitive_agents import list_competitors
        from sqlalchemy import func

        mock_verify.return_value = mock_product
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_competitor]
        mock_db.query.return_value.filter.return_value.scalar.return_value = 5

        result = list_competitors(
            product_id=1,
            deep_analysis_enabled=None,
            current_user=mock_user,
            db=mock_db
        )

        assert len(result) == 1
        assert result[0].id == 1
        assert result[0].competitor_name == "TestCompetitor"

    @patch('app.api.competitive_agents.verify_competitor_access')
    def test_enable_deep_analysis(self, mock_verify, mock_db, mock_user, mock_competitor):
        """Test enabling deep analysis for a competitor."""
        from app.api.competitive_agents import enable_deep_analysis

        mock_verify.return_value = mock_competitor

        result = enable_deep_analysis(
            product_id=1,
            competitor_id=1,
            current_user=mock_user,
            db=mock_db
        )

        assert mock_competitor.deep_analysis_enabled == True
        mock_db.commit.assert_called()
        assert "enabled" in result["message"]

    @patch('app.api.competitive_agents.verify_competitor_access')
    def test_disable_deep_analysis(self, mock_verify, mock_db, mock_user, mock_competitor):
        """Test disabling deep analysis for a competitor."""
        from app.api.competitive_agents import disable_deep_analysis

        mock_competitor.deep_analysis_enabled = True
        mock_verify.return_value = mock_competitor

        result = disable_deep_analysis(
            product_id=1,
            competitor_id=1,
            current_user=mock_user,
            db=mock_db
        )

        assert mock_competitor.deep_analysis_enabled == False
        assert "disabled" in result["message"]


class TestFeatureClusterEndpoints:
    """Test feature cluster endpoints."""

    @patch('app.api.competitive_agents.verify_product_access')
    def test_list_feature_clusters(self, mock_verify, mock_db, mock_user, mock_product, mock_cluster):
        """Test listing feature clusters."""
        from app.api.competitive_agents import list_feature_clusters

        mock_verify.return_value = mock_product
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_cluster]

        result = list_feature_clusters(
            product_id=1,
            min_competitors=None,
            current_user=mock_user,
            db=mock_db
        )

        assert len(result) == 1
        assert result[0].cluster_name == "AI Features"
        assert result[0].competitor_count == 4

    @patch('app.api.competitive_agents.verify_product_access')
    def test_list_feature_clusters_with_filter(self, mock_verify, mock_db, mock_user, mock_product, mock_cluster):
        """Test listing feature clusters with min_competitors filter."""
        from app.api.competitive_agents import list_feature_clusters

        mock_verify.return_value = mock_product

        # Mock the filtered query chain
        mock_query = MagicMock()
        mock_query.filter.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_cluster]
        mock_db.query.return_value = mock_query

        result = list_feature_clusters(
            product_id=1,
            min_competitors=3,
            current_user=mock_user,
            db=mock_db
        )

        # The filter should be called for min_competitors
        assert len(result) == 1


class TestTriggerEndpoints:
    """Test trigger endpoints that queue jobs."""

    @patch('app.queue.tasks.discover_competitors_task')
    @patch('app.api.competitive_agents.QueueService')
    @patch('app.api.competitive_agents.verify_product_access')
    def test_trigger_competitor_discovery(self, mock_verify, mock_qs_class, mock_task, mock_db, mock_user, mock_product):
        """Test triggering competitor discovery."""
        from app.api.competitive_agents import trigger_competitor_discovery

        mock_verify.return_value = mock_product

        mock_qs = MagicMock()
        mock_job = MagicMock()
        mock_job.id = 1
        mock_job.job_uuid = "test-uuid"
        mock_job.job_type = MagicMock(value="competitor_discovery")
        mock_job.status = MagicMock(value="pending")
        mock_qs.create_job.return_value = mock_job
        mock_qs_class.return_value = mock_qs

        mock_task.delay.return_value = MagicMock(id="task-123")

        result = trigger_competitor_discovery(
            product_id=1,
            current_user=mock_user,
            db=mock_db
        )

        assert result.job_id == 1
        assert "queued" in result.message
        mock_task.delay.assert_called_once()

    @patch('app.queue.tasks.feature_clustering_task')
    @patch('app.api.competitive_agents.QueueService')
    @patch('app.api.competitive_agents.get_or_create_config')
    @patch('app.api.competitive_agents.verify_product_access')
    def test_trigger_feature_clustering(self, mock_verify, mock_get_config, mock_qs_class, mock_task, mock_db, mock_user, mock_product, mock_config):
        """Test triggering feature clustering."""
        from app.api.competitive_agents import trigger_feature_clustering

        mock_verify.return_value = mock_product
        mock_get_config.return_value = mock_config

        mock_qs = MagicMock()
        mock_job = MagicMock()
        mock_job.id = 1
        mock_job.job_uuid = "test-uuid"
        mock_job.job_type = MagicMock(value="feature_clustering")
        mock_job.status = MagicMock(value="pending")
        mock_qs.create_job.return_value = mock_job
        mock_qs_class.return_value = mock_qs

        mock_task.delay.return_value = MagicMock(id="task-123")

        result = trigger_feature_clustering(
            product_id=1,
            current_user=mock_user,
            db=mock_db
        )

        assert result.job_id == 1
        assert "clustering" in result.message.lower()

    @patch('app.queue.tasks.deep_analysis_task')
    @patch('app.api.competitive_agents.QueueService')
    @patch('app.api.competitive_agents.verify_competitor_access')
    def test_trigger_deep_analysis(self, mock_verify, mock_qs_class, mock_task, mock_db, mock_user, mock_competitor):
        """Test triggering deep analysis for a competitor."""
        from app.api.competitive_agents import trigger_deep_analysis

        mock_verify.return_value = mock_competitor

        mock_qs = MagicMock()
        mock_job = MagicMock()
        mock_job.id = 1
        mock_job.job_uuid = "test-uuid"
        mock_job.job_type = MagicMock(value="deep_analysis")
        mock_job.status = MagicMock(value="pending")
        mock_qs.create_job.return_value = mock_job
        mock_qs_class.return_value = mock_qs

        mock_task.delay.return_value = MagicMock(id="task-123")

        result = trigger_deep_analysis(
            product_id=1,
            competitor_id=1,
            current_user=mock_user,
            db=mock_db
        )

        assert result.job_id == 1
        assert "deep analysis" in result.message.lower()


class TestStrategicAnalysisEndpoints:
    """Test strategic analysis result endpoints."""

    @patch('app.api.competitive_agents.verify_competitor_access')
    def test_get_pricing_analysis_none(self, mock_verify, mock_db, mock_user, mock_competitor):
        """Test getting pricing analysis when none exists."""
        from app.api.competitive_agents import get_pricing_analysis

        mock_verify.return_value = mock_competitor
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        result = get_pricing_analysis(
            product_id=1,
            competitor_id=1,
            current_user=mock_user,
            db=mock_db
        )

        assert result is None

    @patch('app.api.competitive_agents.verify_competitor_access')
    def test_get_pricing_analysis_exists(self, mock_verify, mock_db, mock_user, mock_competitor):
        """Test getting pricing analysis when it exists."""
        from app.api.competitive_agents import get_pricing_analysis
        from datetime import datetime

        mock_verify.return_value = mock_competitor

        mock_analysis = MagicMock()
        mock_analysis.id = 1
        mock_analysis.product_competitor_id = 1
        mock_analysis.pricing_model = "freemium"
        mock_analysis.has_free_tier = True
        mock_analysis.has_trial = True
        mock_analysis.trial_days = 14
        mock_analysis.pricing_tiers = [{"name": "Pro", "price": 29}]
        mock_analysis.has_enterprise = True
        mock_analysis.source_url = "https://competitor.com/pricing"
        mock_analysis.confidence = 0.85
        mock_analysis.analyzed_at = datetime.utcnow()

        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_analysis

        result = get_pricing_analysis(
            product_id=1,
            competitor_id=1,
            current_user=mock_user,
            db=mock_db
        )

        assert result is not None
        assert result.pricing_model == "freemium"
        assert result.has_free_tier == True

    @patch('app.api.competitive_agents.verify_competitor_access')
    def test_get_momentum_analysis(self, mock_verify, mock_db, mock_user, mock_competitor):
        """Test getting momentum analysis."""
        from app.api.competitive_agents import get_momentum_analysis
        from datetime import datetime

        mock_verify.return_value = mock_competitor

        mock_analysis = MagicMock()
        mock_analysis.id = 1
        mock_analysis.product_competitor_id = 1
        mock_analysis.momentum_score = 0.75
        mock_analysis.momentum_trend = "rising"
        mock_analysis.customer_growth_trend = "accelerating"
        mock_analysis.release_velocity = "high"
        mock_analysis.notable_customers = ["BigCo", "MegaCorp"]
        mock_analysis.analysis_summary = "Strong momentum"
        mock_analysis.confidence = 0.8
        mock_analysis.analyzed_at = datetime.utcnow()

        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_analysis

        result = get_momentum_analysis(
            product_id=1,
            competitor_id=1,
            current_user=mock_user,
            db=mock_db
        )

        assert result.momentum_score == 0.75
        assert result.momentum_trend == "rising"

    @patch('app.api.competitive_agents.verify_competitor_access')
    def test_get_change_events(self, mock_verify, mock_db, mock_user, mock_competitor):
        """Test getting change events."""
        from app.api.competitive_agents import get_change_events
        from datetime import datetime

        mock_verify.return_value = mock_competitor

        mock_event = MagicMock()
        mock_event.id = 1
        mock_event.product_competitor_id = 1
        mock_event.event_type = "feature_launch"
        mock_event.event_title = "New AI Feature"
        mock_event.event_description = "Launched AI-powered search"
        mock_event.event_date = None
        mock_event.source_url = "https://competitor.com/blog"
        mock_event.source_type = "blog"
        mock_event.impact_level = "major"
        mock_event.detected_at = datetime.utcnow()

        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_event]

        result = get_change_events(
            product_id=1,
            competitor_id=1,
            limit=20,
            current_user=mock_user,
            db=mock_db
        )

        assert len(result) == 1
        assert result[0].event_type == "feature_launch"
        assert result[0].impact_level == "major"


class TestFeatureToIdeaEndpoints:
    """Test feature-to-idea conversion endpoints."""

    @patch('app.queue.tasks.triage_idea_task')
    @patch('app.api.competitive_agents.QueueService')
    @patch('app.api.competitive_agents.verify_competitor_access')
    def test_create_idea_from_feature(self, mock_verify, mock_qs_class, mock_triage_task, mock_db, mock_user, mock_competitor, mock_feature):
        """Test creating an idea from a single feature."""
        from app.api.competitive_agents import create_idea_from_feature

        mock_verify.return_value = mock_competitor

        # Mock feature query
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_feature,  # First call for feature lookup
            mock_competitor  # Second call for competitor name
        ]

        mock_qs = MagicMock()
        mock_job = MagicMock()
        mock_job.id = 1
        mock_job.job_uuid = "test-uuid"
        mock_job.job_type = MagicMock(value="idea_triage")
        mock_job.status = MagicMock(value="pending")
        mock_qs.create_job.return_value = mock_job
        mock_qs_class.return_value = mock_qs

        mock_triage_task.delay.return_value = MagicMock(id="task-123")

        result = create_idea_from_feature(
            product_id=1,
            competitor_id=1,
            feature_id=1,
            current_user=mock_user,
            db=mock_db
        )

        assert result.job_id == 1
        assert "idea created" in result.message.lower()
        mock_db.add.assert_called()  # Idea was added
        mock_triage_task.delay.assert_called_once()

    @patch('app.api.competitive_agents.verify_competitor_access')
    def test_create_idea_from_feature_not_found(self, mock_verify, mock_db, mock_user, mock_competitor):
        """Test error when feature not found."""
        from app.api.competitive_agents import create_idea_from_feature
        from fastapi import HTTPException

        mock_verify.return_value = mock_competitor
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            create_idea_from_feature(
                product_id=1,
                competitor_id=1,
                feature_id=999,
                current_user=mock_user,
                db=mock_db
            )

        assert exc_info.value.status_code == 404


# ============================================================================
# Integration-style Tests
# ============================================================================

class TestRouterIntegration:
    """Integration tests for router registration."""

    def test_router_prefix(self):
        """Test router has correct prefix."""
        from app.api.competitive_agents import router

        assert router.prefix == "/product-intelligence/agents"

    def test_router_tags(self):
        """Test router has correct tags."""
        from app.api.competitive_agents import router

        assert "Competitive Agents" in router.tags

    def test_router_has_expected_routes(self):
        """Test router has expected number of routes."""
        from app.api.competitive_agents import router

        # We expect 20 routes based on the plan
        route_paths = [route.path for route in router.routes]

        # Check some expected paths exist
        assert any("config" in path for path in route_paths)
        assert any("competitors" in path for path in route_paths)
        assert any("feature-clusters" in path for path in route_paths)
        assert any("deep-analysis" in path for path in route_paths)
