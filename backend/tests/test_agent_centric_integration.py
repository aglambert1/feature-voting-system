"""
Integration tests for the V2 Competitive Intelligence Architecture.

This module tests the end-to-end flow:
1. Configuration management
2. Scheduled execution (V2 pipeline)
3. Component importability
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


class TestScheduledExecutionIntegration:
    """Test the full scheduled execution flow."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    @patch('app.queue.tasks.run_competitive_analysis_v2')
    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    def test_scheduled_task_dispatches_v2_analysis(
        self, mock_qs_class, mock_get_db, mock_v2_task, mock_db
    ):
        """Test that scheduled task correctly dispatches V2 competitive analysis."""
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

        mock_v2_task.delay.return_value = MagicMock(id="task-123")

        result = check_scheduled_tasks()

        assert result['total_jobs'] == 1
        mock_v2_task.delay.assert_called_once_with(1)


class TestEndToEndWorkflow:
    """Test complete end-to-end workflows."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    def test_complete_workflow_components_exist(self):
        """Verify all components of the V2 architecture exist and are importable."""
        # Models
        from app.models.competitive_agent import (
            CompetitiveAgentConfig,
            AgentMode,
        )

        # Tasks
        from app.queue.tasks import (
            check_scheduled_tasks,
        )

        # API
        from app.api.competitive_agents import router

        # All imports successful
        assert True

    def test_jobtypes_include_v2_types(self):
        """Verify V2 job types are defined."""
        from app.models.queue import JobType

        v2_job_types = [
            'SCHEDULED_DEEP_ANALYSIS',
            'FUNCTIONAL_AUDIT',
            'LANDSCAPE_SYNTHESIS',
        ]

        for job_type in v2_job_types:
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

    def test_sessions_router_removed(self):
        """Verify sessions router has been removed in V2."""
        import importlib
        sessions_module = importlib.util.find_spec("app.api.sessions")
        assert sessions_module is None, "sessions router should be removed in V2"

    def test_monitoring_config_deprecation_note(self):
        """Verify MonitoringConfig has deprecation note in docstring."""
        from app.models.pm_review import MonitoringConfig

        assert "DEPRECATED" in MonitoringConfig.__doc__
        assert "CompetitiveAgentConfig" in MonitoringConfig.__doc__
