"""
Tests for Chunk 7: Scheduled Execution Tasks.

This module tests the scheduling functionality that enables periodic
execution via Celery Beat.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timedelta


class TestCalculateNextRun:
    """Test the _calculate_next_run helper function."""

    def test_daily_schedule(self):
        """Test daily schedule calculation."""
        from app.queue.tasks import _calculate_next_run

        with patch('app.queue.tasks.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 15, 10, 0, 0)
            mock_datetime.utcnow.return_value = mock_now

            result = _calculate_next_run('daily')
            expected = mock_now + timedelta(days=1)
            assert result == expected

    def test_weekly_schedule(self):
        """Test weekly schedule calculation."""
        from app.queue.tasks import _calculate_next_run

        with patch('app.queue.tasks.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 15, 10, 0, 0)
            mock_datetime.utcnow.return_value = mock_now

            result = _calculate_next_run('weekly')
            expected = mock_now + timedelta(weeks=1)
            assert result == expected

    def test_biweekly_schedule(self):
        """Test biweekly schedule calculation."""
        from app.queue.tasks import _calculate_next_run

        with patch('app.queue.tasks.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 15, 10, 0, 0)
            mock_datetime.utcnow.return_value = mock_now

            result = _calculate_next_run('biweekly')
            expected = mock_now + timedelta(weeks=2)
            assert result == expected

    def test_monthly_schedule(self):
        """Test monthly schedule calculation."""
        from app.queue.tasks import _calculate_next_run

        with patch('app.queue.tasks.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 15, 10, 0, 0)
            mock_datetime.utcnow.return_value = mock_now

            result = _calculate_next_run('monthly')
            expected = mock_now + timedelta(days=30)
            assert result == expected

    def test_unknown_schedule_defaults_to_weekly(self):
        """Test that unknown schedule defaults to weekly."""
        from app.queue.tasks import _calculate_next_run

        with patch('app.queue.tasks.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 15, 10, 0, 0)
            mock_datetime.utcnow.return_value = mock_now

            result = _calculate_next_run('unknown')
            expected = mock_now + timedelta(weeks=1)
            assert result == expected


class TestCheckScheduledTasks:
    """Test the check_scheduled_tasks master scheduler."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return MagicMock()

    @pytest.fixture
    def mock_config(self):
        """Create a mock CompetitiveAgentConfig."""
        config = MagicMock()
        config.product_id = 1
        config.enabled = True
        config.product_analysis_mode = MagicMock()
        config.product_analysis_mode.value = 'manual'
        config.competitor_discovery_mode = MagicMock()
        config.competitor_discovery_mode.value = 'manual'
        config.deep_analysis_mode = MagicMock()
        config.deep_analysis_mode.value = 'manual'
        return config

    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    def test_no_configs_returns_empty(self, mock_qs_class, mock_get_db, mock_db):
        """Test with no configs returns zero jobs."""
        from app.queue.tasks import check_scheduled_tasks

        mock_get_db.return_value = mock_db
        mock_db.query.return_value.filter.return_value.all.return_value = []

        mock_qs = MagicMock()
        mock_qs_class.return_value = mock_qs

        result = check_scheduled_tasks()

        assert result['products_checked'] == 0
        assert result['total_jobs'] == 0
        assert result['jobs_queued']['product_analysis'] == []
        assert result['jobs_queued']['competitor_discovery'] == []
        assert result['jobs_queued']['deep_analysis'] == []

    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    def test_manual_configs_not_queued(self, mock_qs_class, mock_get_db, mock_db, mock_config):
        """Test configs in manual mode are not queued."""
        from app.queue.tasks import check_scheduled_tasks
        from app.models.competitive_agent import AgentMode

        mock_get_db.return_value = mock_db

        # Set all modes to MANUAL
        mock_config.product_analysis_mode = AgentMode.MANUAL
        mock_config.competitor_discovery_mode = AgentMode.MANUAL
        mock_config.deep_analysis_mode = AgentMode.MANUAL

        mock_db.query.return_value.filter.return_value.all.return_value = [mock_config]

        mock_qs = MagicMock()
        mock_qs_class.return_value = mock_qs

        result = check_scheduled_tasks()

        assert result['products_checked'] == 1
        assert result['total_jobs'] == 0
        mock_qs.create_job.assert_not_called()

    @patch('app.queue.tasks.scheduled_deep_analysis_task')
    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    def test_scheduled_deep_analysis_queued_when_due(
        self, mock_qs_class, mock_get_db, mock_deep_task, mock_db, mock_config
    ):
        """Test that deep analysis is queued when scheduled and due."""
        from app.queue.tasks import check_scheduled_tasks
        from app.models.competitive_agent import AgentMode

        mock_get_db.return_value = mock_db

        # Set deep analysis to SCHEDULED and due NOW
        mock_config.product_analysis_mode = AgentMode.MANUAL
        mock_config.competitor_discovery_mode = AgentMode.MANUAL
        mock_config.deep_analysis_mode = AgentMode.SCHEDULED
        mock_config.deep_analysis_schedule = 'weekly'
        mock_config.deep_analysis_next_run = datetime.utcnow() - timedelta(hours=1)  # Past due

        mock_db.query.return_value.filter.return_value.all.return_value = [mock_config]

        mock_qs = MagicMock()
        mock_job = MagicMock()
        mock_job.id = 1
        mock_qs.create_job.return_value = mock_job
        mock_qs_class.return_value = mock_qs

        mock_deep_task.delay.return_value = MagicMock(id="task-123")

        result = check_scheduled_tasks()

        assert result['products_checked'] == 1
        assert result['total_jobs'] == 1
        assert len(result['jobs_queued']['deep_analysis']) == 1
        mock_deep_task.delay.assert_called_once_with(1)

    @patch('app.queue.tasks.discover_competitors_task')
    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    def test_scheduled_discovery_queued_when_due(
        self, mock_qs_class, mock_get_db, mock_discover_task, mock_db, mock_config
    ):
        """Test that competitor discovery is queued when scheduled and due."""
        from app.queue.tasks import check_scheduled_tasks
        from app.models.competitive_agent import AgentMode

        mock_get_db.return_value = mock_db

        mock_config.product_analysis_mode = AgentMode.MANUAL
        mock_config.competitor_discovery_mode = AgentMode.SCHEDULED
        mock_config.competitor_discovery_schedule = 'weekly'
        mock_config.competitor_discovery_next_run = datetime.utcnow() - timedelta(hours=1)
        mock_config.deep_analysis_mode = AgentMode.MANUAL

        mock_db.query.return_value.filter.return_value.all.return_value = [mock_config]

        mock_qs = MagicMock()
        mock_job = MagicMock()
        mock_job.id = 1
        mock_qs.create_job.return_value = mock_job
        mock_qs_class.return_value = mock_qs

        mock_discover_task.delay.return_value = MagicMock(id="task-123")

        result = check_scheduled_tasks()

        assert result['total_jobs'] == 1
        assert len(result['jobs_queued']['competitor_discovery']) == 1
        mock_discover_task.delay.assert_called_once_with(1)

    @patch('app.queue.tasks.analyze_product_task')
    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    def test_scheduled_product_analysis_queued_when_due(
        self, mock_qs_class, mock_get_db, mock_product_task, mock_db, mock_config
    ):
        """Test that product analysis is queued when scheduled and due."""
        from app.queue.tasks import check_scheduled_tasks
        from app.models.competitive_agent import AgentMode

        mock_get_db.return_value = mock_db

        mock_config.product_analysis_mode = AgentMode.SCHEDULED
        mock_config.product_analysis_schedule = 'daily'
        mock_config.product_analysis_next_run = datetime.utcnow() - timedelta(hours=1)
        mock_config.competitor_discovery_mode = AgentMode.MANUAL
        mock_config.deep_analysis_mode = AgentMode.MANUAL

        mock_db.query.return_value.filter.return_value.all.return_value = [mock_config]

        mock_qs = MagicMock()
        mock_job = MagicMock()
        mock_job.id = 1
        mock_qs.create_job.return_value = mock_job
        mock_qs_class.return_value = mock_qs

        mock_product_task.delay.return_value = MagicMock(id="task-123")

        result = check_scheduled_tasks()

        assert result['total_jobs'] == 1
        assert len(result['jobs_queued']['product_analysis']) == 1
        mock_product_task.delay.assert_called_once_with(1)

    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    def test_scheduled_not_due_yet(self, mock_qs_class, mock_get_db, mock_db, mock_config):
        """Test that scheduled tasks not yet due are not queued."""
        from app.queue.tasks import check_scheduled_tasks
        from app.models.competitive_agent import AgentMode

        mock_get_db.return_value = mock_db

        # Scheduled but not due (next_run is in the future)
        mock_config.product_analysis_mode = AgentMode.SCHEDULED
        mock_config.product_analysis_schedule = 'weekly'
        mock_config.product_analysis_next_run = datetime.utcnow() + timedelta(days=3)
        mock_config.competitor_discovery_mode = AgentMode.MANUAL
        mock_config.deep_analysis_mode = AgentMode.MANUAL

        mock_db.query.return_value.filter.return_value.all.return_value = [mock_config]

        mock_qs = MagicMock()
        mock_qs_class.return_value = mock_qs

        result = check_scheduled_tasks()

        assert result['products_checked'] == 1
        assert result['total_jobs'] == 0
        mock_qs.create_job.assert_not_called()

    @patch('app.queue.tasks.scheduled_deep_analysis_task')
    @patch('app.queue.tasks.discover_competitors_task')
    @patch('app.queue.tasks.analyze_product_task')
    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    def test_multiple_tasks_queued_for_one_product(
        self, mock_qs_class, mock_get_db, mock_product_task,
        mock_discover_task, mock_deep_task, mock_db, mock_config
    ):
        """Test multiple tasks can be queued for a single product."""
        from app.queue.tasks import check_scheduled_tasks
        from app.models.competitive_agent import AgentMode

        mock_get_db.return_value = mock_db

        # All three are scheduled and due
        past = datetime.utcnow() - timedelta(hours=1)
        mock_config.product_analysis_mode = AgentMode.SCHEDULED
        mock_config.product_analysis_schedule = 'weekly'
        mock_config.product_analysis_next_run = past
        mock_config.competitor_discovery_mode = AgentMode.SCHEDULED
        mock_config.competitor_discovery_schedule = 'weekly'
        mock_config.competitor_discovery_next_run = past
        mock_config.deep_analysis_mode = AgentMode.SCHEDULED
        mock_config.deep_analysis_schedule = 'weekly'
        mock_config.deep_analysis_next_run = past

        mock_db.query.return_value.filter.return_value.all.return_value = [mock_config]

        mock_qs = MagicMock()
        mock_job = MagicMock()
        mock_job.id = 1
        mock_qs.create_job.return_value = mock_job
        mock_qs_class.return_value = mock_qs

        for task in [mock_product_task, mock_discover_task, mock_deep_task]:
            task.delay.return_value = MagicMock(id="task-123")

        result = check_scheduled_tasks()

        assert result['products_checked'] == 1
        assert result['total_jobs'] == 3
        assert len(result['jobs_queued']['product_analysis']) == 1
        assert len(result['jobs_queued']['competitor_discovery']) == 1
        assert len(result['jobs_queued']['deep_analysis']) == 1

    @patch('app.queue.tasks.scheduled_deep_analysis_task')
    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    def test_multiple_products(self, mock_qs_class, mock_get_db, mock_deep_task, mock_db):
        """Test scheduler handles multiple products."""
        from app.queue.tasks import check_scheduled_tasks
        from app.models.competitive_agent import AgentMode

        mock_get_db.return_value = mock_db

        # Create two configs, both with due deep analysis
        past = datetime.utcnow() - timedelta(hours=1)

        config1 = MagicMock()
        config1.product_id = 1
        config1.product_analysis_mode = AgentMode.MANUAL
        config1.competitor_discovery_mode = AgentMode.MANUAL
        config1.deep_analysis_mode = AgentMode.SCHEDULED
        config1.deep_analysis_schedule = 'weekly'
        config1.deep_analysis_next_run = past

        config2 = MagicMock()
        config2.product_id = 2
        config2.product_analysis_mode = AgentMode.MANUAL
        config2.competitor_discovery_mode = AgentMode.MANUAL
        config2.deep_analysis_mode = AgentMode.SCHEDULED
        config2.deep_analysis_schedule = 'weekly'
        config2.deep_analysis_next_run = past

        mock_db.query.return_value.filter.return_value.all.return_value = [config1, config2]

        mock_qs = MagicMock()
        mock_job = MagicMock()
        mock_job.id = 1
        mock_qs.create_job.return_value = mock_job
        mock_qs_class.return_value = mock_qs

        mock_deep_task.delay.return_value = MagicMock(id="task-123")

        result = check_scheduled_tasks()

        assert result['products_checked'] == 2
        assert result['total_jobs'] == 2
        assert len(result['jobs_queued']['deep_analysis']) == 2

    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    def test_continues_on_product_error(self, mock_qs_class, mock_get_db, mock_db):
        """Test that errors on one product don't stop processing others."""
        from app.queue.tasks import check_scheduled_tasks
        from app.models.competitive_agent import AgentMode

        mock_get_db.return_value = mock_db

        # Config that will raise error
        config1 = MagicMock()
        config1.product_id = 1
        config1.product_analysis_mode = AgentMode.SCHEDULED
        config1.product_analysis_next_run = datetime.utcnow() - timedelta(hours=1)
        # This will cause AttributeError when we access product_analysis_schedule

        def raise_error(*args, **kwargs):
            raise Exception("Test error")

        config1.product_analysis_schedule = PropertyMock(side_effect=raise_error)

        # Config that should work
        config2 = MagicMock()
        config2.product_id = 2
        config2.product_analysis_mode = AgentMode.MANUAL
        config2.competitor_discovery_mode = AgentMode.MANUAL
        config2.deep_analysis_mode = AgentMode.MANUAL

        mock_db.query.return_value.filter.return_value.all.return_value = [config1, config2]

        mock_qs = MagicMock()
        mock_qs_class.return_value = mock_qs

        # Should not raise, should continue to config2
        result = check_scheduled_tasks()

        assert result['products_checked'] == 2
        # Only config2 processed successfully (with 0 jobs since it's all MANUAL)


class TestCeleryBeatConfiguration:
    """Test that Celery Beat is properly configured."""

    def test_beat_schedule_includes_check_scheduled_tasks(self):
        """Verify check_scheduled_tasks is in beat schedule."""
        from app.queue import celery_app

        assert 'check-scheduled-agent-tasks' in celery_app.conf.beat_schedule

        schedule_entry = celery_app.conf.beat_schedule['check-scheduled-agent-tasks']
        assert schedule_entry['task'] == 'app.queue.tasks.check_scheduled_tasks'
        assert schedule_entry['schedule'] == 3600.0  # Hourly

    def test_beat_schedule_includes_legacy_monitoring(self):
        """Verify legacy scheduled_monitoring_task is still in beat schedule."""
        from app.queue import celery_app

        assert 'scheduled-monitoring-daily' in celery_app.conf.beat_schedule

        schedule_entry = celery_app.conf.beat_schedule['scheduled-monitoring-daily']
        assert schedule_entry['task'] == 'app.queue.tasks.scheduled_monitoring_task'
        assert schedule_entry['schedule'] == 86400.0  # Daily


class TestNextRunUpdates:
    """Test that next_run times are properly updated after scheduling."""

    @patch('app.queue.tasks.scheduled_deep_analysis_task')
    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    def test_next_run_updated_after_scheduling(
        self, mock_qs_class, mock_get_db, mock_deep_task
    ):
        """Test that last_run and next_run are updated after scheduling."""
        from app.queue.tasks import check_scheduled_tasks
        from app.models.competitive_agent import AgentMode

        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        config = MagicMock()
        config.product_id = 1
        config.product_analysis_mode = AgentMode.MANUAL
        config.competitor_discovery_mode = AgentMode.MANUAL
        config.deep_analysis_mode = AgentMode.SCHEDULED
        config.deep_analysis_schedule = 'weekly'
        config.deep_analysis_next_run = datetime.utcnow() - timedelta(hours=1)
        config.deep_analysis_last_run = None

        mock_db.query.return_value.filter.return_value.all.return_value = [config]

        mock_qs = MagicMock()
        mock_job = MagicMock()
        mock_job.id = 1
        mock_qs.create_job.return_value = mock_job
        mock_qs_class.return_value = mock_qs

        mock_deep_task.delay.return_value = MagicMock(id="task-123")

        check_scheduled_tasks()

        # Verify last_run was updated
        assert config.deep_analysis_last_run is not None

        # Verify next_run was updated to approximately 1 week from now
        assert config.deep_analysis_next_run is not None
        time_diff = config.deep_analysis_next_run - datetime.utcnow()
        # Should be approximately 7 days (allowing for timing variations)
        assert 6 <= time_diff.days <= 7
