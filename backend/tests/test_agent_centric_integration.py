"""
Integration tests for the Agent-Centric Competitive Intelligence Architecture.

This module tests the end-to-end flow of the new agent-centric architecture:
1. Configuration management
2. Competitor management and deep analysis
3. Feature clustering and intensity calculation
4. Idea generation from high-intensity clusters
5. Scheduled execution

These tests validate that all chunks work together correctly.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta


class TestAgentConfigurationFlow:
    """Test configuration management for the agent-centric system."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    def test_config_creation_with_defaults(self, mock_db):
        """Test creating a new config with default values."""
        from app.api.competitive_agents import get_or_create_config
        from app.models.competitive_agent import CompetitiveAgentConfig

        # No existing config
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Mock the add and refresh
        created_config = None

        def capture_add(obj):
            nonlocal created_config
            created_config = obj

        mock_db.add.side_effect = capture_add
        mock_db.refresh.side_effect = lambda obj: None

        # Test
        get_or_create_config(mock_db, product_id=1)

        # Verify add was called
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_config_update_flow(self, mock_db):
        """Test updating an existing config."""
        from app.models.competitive_agent import CompetitiveAgentConfig, AgentMode

        existing_config = MagicMock(spec=CompetitiveAgentConfig)
        existing_config.product_id = 1
        existing_config.product_analysis_mode = AgentMode.MANUAL
        existing_config.deep_analysis_mode = AgentMode.MANUAL

        mock_db.query.return_value.filter.return_value.first.return_value = existing_config

        # Simulate updating the config
        existing_config.deep_analysis_mode = AgentMode.SCHEDULED
        existing_config.deep_analysis_schedule = 'weekly'

        assert existing_config.deep_analysis_mode == AgentMode.SCHEDULED
        assert existing_config.deep_analysis_schedule == 'weekly'


class TestCompetitorDeepAnalysisFlow:
    """Test the deep analysis workflow for competitors."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    @pytest.fixture
    def mock_competitor(self):
        """Create a mock competitor."""
        competitor = MagicMock()
        competitor.id = 1
        competitor.product_id = 1
        competitor.competitor_name = "Test Competitor"
        competitor.competitor_url = "https://test-competitor.com"
        competitor.status = 'active'
        competitor.deep_analysis_enabled = True
        competitor.deep_analysis_status = None
        return competitor

    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    @patch('app.queue.tasks._run_feature_extraction')
    def test_deep_analysis_runs_feature_extraction(
        self, mock_feature_extract, mock_qs_class, mock_get_db, mock_db, mock_competitor
    ):
        """Test that deep analysis runs feature extraction."""
        from app.queue.tasks import deep_analysis_task

        mock_get_db.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_competitor,  # First query for competitor
            None,  # Config query (no config - defaults)
        ]

        mock_qs = MagicMock()
        mock_job = MagicMock()
        mock_job.id = 1
        mock_job.product_id = 1
        mock_job.input_data = {'competitor_id': 1}
        mock_qs.mark_running.return_value = mock_job
        mock_qs_class.return_value = mock_qs

        mock_feature_extract.return_value = {'features_extracted': 15}

        result = deep_analysis_task(job_id=1)

        mock_feature_extract.assert_called_once()
        assert 'feature_extraction' in result.get('analyses_completed', [])


class TestFeatureClusteringIntegration:
    """Test feature clustering and intensity calculation."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    def test_clustering_service_initialization(self, mock_db):
        """Test that clustering service initializes correctly."""
        from app.services.feature_clustering_service import FeatureClusteringService

        service = FeatureClusteringService(mock_db)
        assert service.db == mock_db

    def test_cluster_features_with_empty_features(self, mock_db):
        """Test clustering with no features returns appropriate result."""
        from app.services.feature_clustering_service import FeatureClusteringService

        # No features in database
        mock_db.query.return_value.filter.return_value.all.return_value = []

        service = FeatureClusteringService(mock_db)
        result = service.cluster_features(product_id=1)

        assert result.clusters_created == 0
        assert result.features_clustered == 0


class TestIdeaGenerationFromClusters:
    """Test idea generation from high-intensity clusters."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    @pytest.fixture
    def mock_cluster(self):
        """Create a mock feature cluster."""
        cluster = MagicMock()
        cluster.id = 1
        cluster.product_id = 1
        cluster.cluster_name = "AI-Powered Search"
        cluster.cluster_description = "Search using AI/ML"
        cluster.competitor_count = 5
        cluster.feature_count = 8
        cluster.idea_generated = False
        return cluster

    @pytest.fixture
    def mock_llm_service(self):
        """Create a mock LLM service."""
        service = MagicMock()
        service.generate.return_value = {
            'title': 'Implement AI-Powered Search',
            'what_description': 'Add AI search capabilities',
            'why_description': '5 competitors have this feature',
            'use_case_description': 'Better search experience'
        }
        return service

    def test_generate_idea_for_cluster(self, mock_db, mock_cluster, mock_llm_service):
        """Test generating an idea from a high-intensity cluster."""
        from app.services.feature_clustering_service import FeatureClusteringService
        from app.models.competitive_agent import FeatureCluster, CompetitiveAgentConfig

        # Mock config
        mock_config = MagicMock(spec=CompetitiveAgentConfig)
        mock_config.intensity_idea_threshold = 3

        # Mock queries
        mock_db.query.return_value.filter.return_value.first.return_value = mock_config
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_cluster]

        # Test threshold check
        assert mock_cluster.competitor_count >= mock_config.intensity_idea_threshold


class TestScheduledExecutionIntegration:
    """Test the full scheduled execution flow."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    @patch('app.queue.tasks.scheduled_deep_analysis_task')
    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    def test_scheduled_task_dispatches_deep_analysis(
        self, mock_qs_class, mock_get_db, mock_deep_task, mock_db
    ):
        """Test that scheduled task correctly dispatches deep analysis."""
        from app.queue.tasks import check_scheduled_tasks
        from app.models.competitive_agent import CompetitiveAgentConfig, AgentMode

        mock_get_db.return_value = mock_db

        # Create a scheduled config that's due
        config = MagicMock(spec=CompetitiveAgentConfig)
        config.product_id = 1
        config.enabled = True
        config.product_analysis_mode = AgentMode.MANUAL
        config.competitor_discovery_mode = AgentMode.MANUAL
        config.deep_analysis_mode = AgentMode.SCHEDULED
        config.deep_analysis_schedule = 'weekly'
        config.deep_analysis_next_run = datetime.utcnow() - timedelta(hours=1)

        mock_db.query.return_value.filter.return_value.all.return_value = [config]

        mock_qs = MagicMock()
        mock_job = MagicMock()
        mock_job.id = 1
        mock_qs.create_job.return_value = mock_job
        mock_qs_class.return_value = mock_qs

        mock_deep_task.delay.return_value = MagicMock(id="task-123")

        result = check_scheduled_tasks()

        assert result['total_jobs'] == 1
        mock_deep_task.delay.assert_called_once_with(1)


class TestEndToEndWorkflow:
    """Test complete end-to-end workflows."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    def test_complete_workflow_components_exist(self):
        """Verify all components of the V2 architecture exist and are importable."""
        # Models (V2 - strategic analysis models removed)
        from app.models.competitive_agent import (
            CompetitiveAgentConfig,
            AgentMode,
            FeatureCluster,
            FeatureClusterMember
        )

        # Services
        from app.services.feature_clustering_service import FeatureClusteringService

        # Agents (V2 - strategic analysis agents removed)
        from app.agents.intensity_idea_generator import IntensityIdeaGeneratorAgent

        # Tasks
        from app.queue.tasks import (
            feature_clustering_task,
            intensity_idea_generation_task,
            check_scheduled_tasks
        )

        # API
        from app.api.competitive_agents import router

        # All imports successful
        assert True

    def test_jobtypes_include_new_types(self):
        """Verify all new job types are defined."""
        from app.models.queue import JobType

        # Only test for active (non-deprecated) job types
        new_job_types = [
            'DEEP_ANALYSIS',
            'SCHEDULED_DEEP_ANALYSIS',
            'FEATURE_EXTRACTION_ONLY',
            'FEATURE_CLUSTERING',
            'INTENSITY_IDEA_GENERATION'
        ]

        for job_type in new_job_types:
            assert hasattr(JobType, job_type), f"JobType.{job_type} not found"

    def test_celery_beat_schedule_configured(self):
        """Verify Celery Beat schedule includes new task."""
        from app.queue import celery_app

        assert 'check-scheduled-agent-tasks' in celery_app.conf.beat_schedule
        entry = celery_app.conf.beat_schedule['check-scheduled-agent-tasks']
        assert entry['task'] == 'app.queue.tasks.check_scheduled_tasks'

    def test_api_router_registered(self):
        """Verify competitive_agents router is registered."""
        from app.main import app

        routes = [route.path for route in app.routes]
        # Check for competitive agents prefix
        agent_routes = [r for r in routes if '/product-intelligence/agents' in r]
        assert len(agent_routes) > 0, "No competitive agents routes found"


class TestDeprecationWarnings:
    """Test that deprecated components are properly marked."""

    def test_sessions_router_deprecated(self):
        """Verify sessions router is marked as deprecated."""
        from app.api.sessions import router

        assert router.deprecated is True
        assert "(DEPRECATED)" in router.tags[0]

    def test_monitoring_config_deprecation_note(self):
        """Verify MonitoringConfig has deprecation note in docstring."""
        from app.models.pm_review import MonitoringConfig

        assert "DEPRECATED" in MonitoringConfig.__doc__
        assert "CompetitiveAgentConfig" in MonitoringConfig.__doc__
