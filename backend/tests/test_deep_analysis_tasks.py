"""
Tests for Chunk 5: Deep Analysis Celery Tasks.

Tests the agent-centric architecture tasks for competitive intelligence:
- deep_analysis_task (per-competitor)
- feature_clustering_task
- intensity_idea_generation_task
- scheduled_deep_analysis_task
- aggregate_deep_analysis_results
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# Mock database models and services before importing tasks
@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.all.return_value = []
    return db


@pytest.fixture
def mock_queue_service():
    """Create a mock queue service."""
    service = MagicMock()
    service.mark_running.return_value = MagicMock(
        id=1,
        job_uuid='test-uuid',
        input_data={},
        product_id=1,
        user_id=1
    )
    service.get_job.return_value = MagicMock(
        id=1,
        job_uuid='test-uuid',
        input_data={},
        product_id=1,
        user_id=1
    )
    service.create_job.return_value = MagicMock(id=2, job_uuid='child-uuid')
    return service


@pytest.fixture
def mock_competitor():
    """Create a mock competitor."""
    competitor = MagicMock()
    competitor.id = 1
    competitor.competitor_name = "TestCompetitor"
    competitor.competitor_url = "https://competitor.com"
    competitor.product_id = 1
    competitor.deep_analysis_status = None
    competitor.deep_analysis_enabled = True
    competitor.status = 'active'
    return competitor


@pytest.fixture
def mock_product():
    """Create a mock product."""
    product = MagicMock()
    product.id = 1
    product.product_name = "TestProduct"
    product.product_category = "SaaS"
    return product


@pytest.fixture
def mock_config():
    """Create a mock competitive agent config."""
    config = MagicMock()
    config.product_id = 1
    config.enable_pricing_analysis = True
    config.enable_positioning_analysis = True
    config.enable_changes_tracking = True
    config.enable_momentum_analysis = True
    config.enable_financials_analysis = False
    return config


# ============================================================================
# deep_analysis_task Tests
# ============================================================================

class TestDeepAnalysisTask:
    """Tests for deep_analysis_task."""

    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    @patch('app.queue.tasks._run_feature_extraction')
    @patch('app.queue.tasks._run_pricing_analysis')
    @patch('app.queue.tasks._run_positioning_analysis')
    @patch('app.queue.tasks._run_changes_tracking')
    @patch('app.queue.tasks._run_momentum_analysis')
    def test_deep_analysis_runs_all_analyses(
        self, mock_momentum, mock_changes, mock_positioning, mock_pricing,
        mock_features, mock_qs_class, mock_get_db, mock_db, mock_competitor, mock_config
    ):
        """Test that deep analysis runs all enabled analyses."""
        from app.queue.tasks import deep_analysis_task

        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_qs = MagicMock()
        mock_qs.mark_running.return_value = MagicMock(
            id=1, input_data={'competitor_id': 1}, product_id=1
        )
        mock_qs_class.return_value = mock_qs

        # Mock query returns
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_competitor,  # ProductCompetitor query
            mock_config,      # CompetitiveAgentConfig query
        ]

        # Setup analysis mocks
        mock_features.return_value = {'features_extracted': 10}
        mock_pricing.return_value = {'pricing_model': 'tiered'}
        mock_positioning.return_value = {'market_segment': 'SMB'}
        mock_changes.return_value = {'total_changes': 5}
        mock_momentum.return_value = {'momentum_score': 0.7}

        # Execute
        result = deep_analysis_task(job_id=1)

        # Verify all analyses were called
        mock_features.assert_called_once()
        mock_pricing.assert_called_once()
        mock_positioning.assert_called_once()
        mock_changes.assert_called_once()
        mock_momentum.assert_called_once()

        # Verify result structure
        assert 'competitor_id' in result
        assert 'analyses_completed' in result
        assert 'feature_extraction' in result['analyses_completed']

    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    @patch('app.queue.tasks._run_feature_extraction')
    @patch('app.queue.tasks._run_financials_analysis')
    def test_deep_analysis_skips_disabled_analyses(
        self, mock_financials, mock_features, mock_qs_class, mock_get_db,
        mock_db, mock_competitor, mock_config
    ):
        """Test that deep analysis skips disabled analyses."""
        from app.queue.tasks import deep_analysis_task

        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_qs = MagicMock()
        mock_qs.mark_running.return_value = MagicMock(
            id=1, input_data={'competitor_id': 1}, product_id=1
        )
        mock_qs_class.return_value = mock_qs

        # Config with financials disabled
        mock_config.enable_financials_analysis = False
        mock_config.enable_pricing_analysis = False
        mock_config.enable_positioning_analysis = False
        mock_config.enable_changes_tracking = False
        mock_config.enable_momentum_analysis = False

        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_competitor,
            mock_config,
        ]

        mock_features.return_value = {'features_extracted': 10}

        # Execute
        result = deep_analysis_task(job_id=1)

        # Financials should not be called
        mock_financials.assert_not_called()

        # Features should always run
        mock_features.assert_called_once()

    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    @patch('app.queue.tasks._run_feature_extraction')
    def test_deep_analysis_handles_analysis_errors(
        self, mock_features, mock_qs_class, mock_get_db, mock_db, mock_competitor, mock_config
    ):
        """Test that deep analysis continues when individual analyses fail."""
        from app.queue.tasks import deep_analysis_task

        # Setup mocks
        mock_get_db.return_value = mock_db
        mock_qs = MagicMock()
        mock_qs.mark_running.return_value = MagicMock(
            id=1, input_data={'competitor_id': 1}, product_id=1
        )
        mock_qs_class.return_value = mock_qs

        # Disable all but feature extraction
        mock_config.enable_pricing_analysis = False
        mock_config.enable_positioning_analysis = False
        mock_config.enable_changes_tracking = False
        mock_config.enable_momentum_analysis = False
        mock_config.enable_financials_analysis = False

        mock_db.query.return_value.filter.return_value.first.side_effect = [
            mock_competitor,
            mock_config,
        ]

        # Make feature extraction fail
        mock_features.side_effect = Exception("Feature extraction failed")

        # Execute
        result = deep_analysis_task(job_id=1)

        # Should complete but record error
        assert 'errors' in result
        assert len(result['errors']) == 1
        assert result['errors'][0]['analysis'] == 'feature_extraction'

    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    def test_deep_analysis_requires_competitor_id(
        self, mock_qs_class, mock_get_db, mock_db
    ):
        """Test that deep analysis fails without competitor_id."""
        from app.queue.tasks import deep_analysis_task

        mock_get_db.return_value = mock_db
        mock_qs = MagicMock()
        mock_qs.mark_running.return_value = MagicMock(
            id=1, input_data={}, product_id=1  # No competitor_id
        )
        mock_qs_class.return_value = mock_qs

        with pytest.raises(ValueError, match="Competitor ID is required"):
            deep_analysis_task(job_id=1)


# ============================================================================
# feature_clustering_task Tests
# ============================================================================

class TestFeatureClusteringTask:
    """Tests for feature_clustering_task."""

    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    @patch('app.services.feature_clustering_service.FeatureClusteringService')
    def test_feature_clustering_runs_successfully(
        self, mock_service_class, mock_qs_class, mock_get_db, mock_db
    ):
        """Test feature clustering task runs successfully."""
        from app.queue.tasks import feature_clustering_task

        mock_get_db.return_value = mock_db
        mock_qs = MagicMock()
        mock_qs.mark_running.return_value = MagicMock(
            id=1, input_data={'similarity_threshold': 0.75}, product_id=1
        )
        mock_qs_class.return_value = mock_qs

        # Mock the clustering service
        mock_service = MagicMock()
        mock_service.cluster_features.return_value = MagicMock(
            clusters_created=5,
            clusters_updated=2,
            features_clustered=50,
            high_intensity_clusters=3,
            execution_time_ms=150
        )
        mock_service_class.return_value = mock_service

        result = feature_clustering_task(job_id=1)

        assert result['clusters_created'] == 5
        assert result['clusters_updated'] == 2
        assert result['features_clustered'] == 50
        assert result['high_intensity_clusters'] == 3

    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    @patch('app.services.feature_clustering_service.FeatureClusteringService')
    def test_feature_clustering_uses_custom_threshold(
        self, mock_service_class, mock_qs_class, mock_get_db, mock_db
    ):
        """Test feature clustering uses custom similarity threshold."""
        from app.queue.tasks import feature_clustering_task

        mock_get_db.return_value = mock_db
        mock_qs = MagicMock()
        mock_qs.mark_running.return_value = MagicMock(
            id=1, input_data={'similarity_threshold': 0.85}, product_id=1
        )
        mock_qs_class.return_value = mock_qs

        mock_service = MagicMock()
        mock_service.cluster_features.return_value = MagicMock(
            clusters_created=3, clusters_updated=0, features_clustered=30,
            high_intensity_clusters=1, execution_time_ms=100
        )
        mock_service_class.return_value = mock_service

        feature_clustering_task(job_id=1)

        # Verify threshold was passed
        mock_service.cluster_features.assert_called_once_with(
            product_id=1,
            similarity_threshold=0.85
        )

    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    def test_feature_clustering_requires_product_id(
        self, mock_qs_class, mock_get_db, mock_db
    ):
        """Test feature clustering fails without product_id."""
        from app.queue.tasks import feature_clustering_task

        mock_get_db.return_value = mock_db
        mock_qs = MagicMock()
        mock_qs.mark_running.return_value = MagicMock(
            id=1, input_data={}, product_id=None  # No product_id
        )
        mock_qs_class.return_value = mock_qs

        with pytest.raises(ValueError, match="Product ID is required"):
            feature_clustering_task(job_id=1)


# ============================================================================
# intensity_idea_generation_task Tests
# ============================================================================

class TestIntensityIdeaGenerationTask:
    """Tests for intensity_idea_generation_task."""

    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    @patch('app.queue.tasks.LLMService')
    @patch('app.services.feature_clustering_service.FeatureClusteringService')
    def test_idea_generation_creates_ideas(
        self, mock_service_class, mock_llm_class, mock_qs_class, mock_get_db, mock_db
    ):
        """Test idea generation creates ideas from clusters."""
        from app.queue.tasks import intensity_idea_generation_task

        mock_get_db.return_value = mock_db
        mock_qs = MagicMock()
        mock_qs.mark_running.return_value = MagicMock(
            id=1, input_data={'threshold': 3, 'chain_triage': False}, product_id=1, user_id=1
        )
        mock_qs_class.return_value = mock_qs

        mock_service = MagicMock()
        mock_service.generate_ideas_for_high_intensity_clusters.return_value = [
            {'cluster_id': 1, 'status': 'generated', 'idea_id': 1},
            {'cluster_id': 2, 'status': 'generated', 'idea_id': 2},
            {'cluster_id': 3, 'status': 'skipped', 'reason': 'already_generated'},
        ]
        mock_service_class.return_value = mock_service

        result = intensity_idea_generation_task(job_id=1)

        assert result['ideas_generated'] == 2
        assert result['ideas_skipped'] == 1
        assert result['errors'] == 0

    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    @patch('app.queue.tasks.LLMService')
    @patch('app.queue.tasks.triage_idea_task')
    @patch('app.services.feature_clustering_service.FeatureClusteringService')
    def test_idea_generation_chains_to_triage(
        self, mock_service_class, mock_triage_task, mock_llm_class, mock_qs_class, mock_get_db, mock_db
    ):
        """Test idea generation chains to triage when enabled."""
        from app.queue.tasks import intensity_idea_generation_task

        mock_get_db.return_value = mock_db
        mock_qs = MagicMock()
        mock_qs.mark_running.return_value = MagicMock(
            id=1, input_data={'chain_triage': True}, product_id=1, user_id=1
        )
        mock_qs.create_job.return_value = MagicMock(id=10)
        mock_qs_class.return_value = mock_qs

        mock_service = MagicMock()
        mock_service.generate_ideas_for_high_intensity_clusters.return_value = [
            {'cluster_id': 1, 'status': 'generated', 'idea_id': 1},
        ]
        mock_service_class.return_value = mock_service

        result = intensity_idea_generation_task(job_id=1)

        # Verify triage job was created
        mock_qs.create_job.assert_called()
        mock_triage_task.delay.assert_called_once_with(10)

        # Verify triage_job_id was added to result
        assert result['results'][0].get('triage_job_id') == 10

    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    @patch('app.queue.tasks.LLMService')
    @patch('app.services.feature_clustering_service.FeatureClusteringService')
    def test_idea_generation_handles_errors(
        self, mock_service_class, mock_llm_class, mock_qs_class, mock_get_db, mock_db
    ):
        """Test idea generation handles errors gracefully."""
        from app.queue.tasks import intensity_idea_generation_task

        mock_get_db.return_value = mock_db
        mock_qs = MagicMock()
        mock_qs.mark_running.return_value = MagicMock(
            id=1, input_data={'chain_triage': False}, product_id=1
        )
        mock_qs_class.return_value = mock_qs

        mock_service = MagicMock()
        mock_service.generate_ideas_for_high_intensity_clusters.return_value = [
            {'cluster_id': 1, 'status': 'error', 'error': 'Agent failed'},
        ]
        mock_service_class.return_value = mock_service

        result = intensity_idea_generation_task(job_id=1)

        assert result['errors'] == 1


# ============================================================================
# scheduled_deep_analysis_task Tests
# ============================================================================

class TestScheduledDeepAnalysisTask:
    """Tests for scheduled_deep_analysis_task."""

    @patch('celery.chord')
    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    def test_scheduled_analysis_dispatches_chord(
        self, mock_qs_class, mock_get_db, mock_chord, mock_db, mock_competitor
    ):
        """Test scheduled analysis dispatches chord for enabled competitors."""
        from app.queue.tasks import scheduled_deep_analysis_task

        mock_get_db.return_value = mock_db
        mock_qs = MagicMock()
        mock_qs.mark_running.return_value = MagicMock(
            id=1, input_data={}, product_id=1, user_id=1
        )
        mock_qs.create_job.return_value = MagicMock(id=2)
        mock_qs_class.return_value = mock_qs

        # Mock competitors query
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_competitor]

        # Mock chord
        mock_chord_result = MagicMock()
        mock_chord_result.id = 'chord-id'
        mock_chord.return_value.apply_async.return_value = mock_chord_result

        result = scheduled_deep_analysis_task(job_id=1)

        assert result['status'] == 'chord_dispatched'
        assert result['parent_job_id'] == 1
        assert len(result['child_job_ids']) == 1
        mock_chord.assert_called_once()

    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    def test_scheduled_analysis_handles_no_competitors(
        self, mock_qs_class, mock_get_db, mock_db
    ):
        """Test scheduled analysis handles case with no enabled competitors."""
        from app.queue.tasks import scheduled_deep_analysis_task

        mock_get_db.return_value = mock_db
        mock_qs = MagicMock()
        mock_qs.mark_running.return_value = MagicMock(
            id=1, input_data={}, product_id=1
        )
        mock_qs_class.return_value = mock_qs

        # No competitors
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = scheduled_deep_analysis_task(job_id=1)

        assert result['competitors_processed'] == 0
        assert 'No competitors enabled' in result['message']

    @patch('celery.chord')
    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    def test_scheduled_analysis_creates_child_jobs(
        self, mock_qs_class, mock_get_db, mock_chord, mock_db
    ):
        """Test scheduled analysis creates child jobs for each competitor."""
        from app.queue.tasks import scheduled_deep_analysis_task

        mock_get_db.return_value = mock_db
        mock_qs = MagicMock()
        mock_qs.mark_running.return_value = MagicMock(
            id=1, input_data={}, product_id=1, user_id=1
        )

        # Track create_job calls
        job_counter = [2]  # Start at 2
        def create_job_side_effect(**kwargs):
            job_id = job_counter[0]
            job_counter[0] += 1
            return MagicMock(id=job_id)

        mock_qs.create_job.side_effect = create_job_side_effect
        mock_qs_class.return_value = mock_qs

        # Two competitors
        competitor1 = MagicMock(id=1, deep_analysis_enabled=True, status='active')
        competitor2 = MagicMock(id=2, deep_analysis_enabled=True, status='active')
        mock_db.query.return_value.filter.return_value.all.return_value = [competitor1, competitor2]

        mock_chord.return_value.apply_async.return_value = MagicMock(id='chord-id')

        result = scheduled_deep_analysis_task(job_id=1)

        # Should create 2 child jobs
        assert mock_qs.create_job.call_count == 2
        assert len(result['child_job_ids']) == 2


# ============================================================================
# aggregate_deep_analysis_results Tests
# ============================================================================

class TestAggregateDeepAnalysisResults:
    """Tests for aggregate_deep_analysis_results."""

    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    @patch('app.queue.tasks.LLMService')
    @patch('app.services.feature_clustering_service.FeatureClusteringService')
    def test_aggregate_results_runs_clustering(
        self, mock_service_class, mock_llm_class, mock_qs_class, mock_get_db, mock_db
    ):
        """Test aggregate task runs clustering and idea generation."""
        from app.queue.tasks import aggregate_deep_analysis_results

        mock_get_db.return_value = mock_db
        mock_qs = MagicMock()
        mock_qs.get_job.return_value = MagicMock(id=1, product_id=1)
        mock_qs_class.return_value = mock_qs

        mock_service = MagicMock()
        mock_service.cluster_features.return_value = MagicMock(
            clusters_created=5, high_intensity_clusters=2
        )
        mock_service.generate_ideas_for_high_intensity_clusters.return_value = [
            {'status': 'generated'},
            {'status': 'skipped'},
        ]
        mock_service_class.return_value = mock_service

        results = [
            {'analyses_completed': ['feature_extraction'], 'feature_extraction': {'features_extracted': 10}},
            {'analyses_completed': ['feature_extraction'], 'feature_extraction': {'features_extracted': 15}},
        ]

        result = aggregate_deep_analysis_results(
            results=results,
            parent_job_id=1,
            child_job_ids=[2, 3],
            product_id=1
        )

        assert result['competitors_analyzed'] == 2
        assert result['successful_analyses'] == 2
        assert result['total_features_extracted'] == 25
        assert result['clusters_created'] == 5
        assert result['ideas_generated'] == 1

    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    @patch('app.queue.tasks.LLMService')
    @patch('app.services.feature_clustering_service.FeatureClusteringService')
    def test_aggregate_handles_partial_results(
        self, mock_service_class, mock_llm_class, mock_qs_class, mock_get_db, mock_db
    ):
        """Test aggregate handles partial/failed results."""
        from app.queue.tasks import aggregate_deep_analysis_results

        mock_get_db.return_value = mock_db
        mock_qs = MagicMock()
        mock_qs.get_job.return_value = MagicMock(id=1, product_id=1)
        mock_qs_class.return_value = mock_qs

        mock_service = MagicMock()
        mock_service.cluster_features.return_value = MagicMock(
            clusters_created=2, high_intensity_clusters=1
        )
        mock_service.generate_ideas_for_high_intensity_clusters.return_value = []
        mock_service_class.return_value = mock_service

        results = [
            {'analyses_completed': ['feature_extraction'], 'feature_extraction': {'features_extracted': 10}},
            None,  # Failed task
            {'analyses_completed': []},  # Completed but no analyses
        ]

        result = aggregate_deep_analysis_results(
            results=results,
            parent_job_id=1,
            child_job_ids=[2, 3, 4],
            product_id=1
        )

        assert result['successful_analyses'] == 1
        assert result['total_features_extracted'] == 10


# ============================================================================
# Helper Function Tests
# ============================================================================

class TestHelperFunctions:
    """Tests for analysis helper functions."""

    @patch('app.queue.tasks.LLMService')
    @patch('app.queue.tasks.FeatureExtractorAgent')
    def test_run_feature_extraction(self, mock_agent_class, mock_llm_class, mock_db, mock_competitor):
        """Test _run_feature_extraction helper."""
        from app.queue.tasks import _run_feature_extraction

        mock_agent = MagicMock()
        mock_agent.execute.return_value = {
            'features': [
                {'name': 'Feature 1', 'description': 'Desc 1', 'category': 'Cat1'},
                {'name': 'Feature 2', 'description': 'Desc 2', 'category': 'Cat2'},
            ],
            'extraction_summary': 'Extracted 2 features'
        }
        mock_agent_class.return_value = mock_agent

        # Mock similarity service at the service module level
        with patch('app.services.similarity_detector.SimilarityDetectorService') as mock_sim_class:
            mock_sim = MagicMock()
            mock_sim_class.return_value = mock_sim

            result = _run_feature_extraction(mock_db, mock_competitor, product_id=1)

            assert result['features_extracted'] == 2
            assert result['extraction_summary'] == 'Extracted 2 features'
            assert mock_db.add.call_count >= 2  # Two features added

    @patch('app.queue.tasks.LLMService')
    @patch('app.agents.pricing_analyzer.PricingAnalyzerAgent')
    def test_run_pricing_analysis(self, mock_agent_class, mock_llm_class, mock_db, mock_competitor, mock_product):
        """Test _run_pricing_analysis helper."""
        from app.queue.tasks import _run_pricing_analysis

        # Mock product query
        mock_db.query.return_value.filter.return_value.first.return_value = mock_product

        mock_agent = MagicMock()
        mock_agent.execute.return_value = {
            'pricing_model': 'freemium',
            'has_free_tier': True,
            'has_trial': True,
            'trial_days': 14,
            'pricing_tiers': [],
            'has_enterprise': True,
            'source_url': 'https://competitor.com/pricing',
            'confidence': 0.85
        }
        mock_agent_class.return_value = mock_agent

        result = _run_pricing_analysis(mock_db, mock_competitor, product_id=1)

        assert result['pricing_model'] == 'freemium'
        assert result['has_free_tier'] == True
        assert result['confidence'] == 0.85
        assert mock_db.add.called  # Pricing analysis record added

    @patch('app.queue.tasks.LLMService')
    @patch('app.agents.positioning_analyzer.PositioningAnalyzerAgent')
    def test_run_positioning_analysis(self, mock_agent_class, mock_llm_class, mock_db, mock_competitor, mock_product):
        """Test _run_positioning_analysis helper."""
        from app.queue.tasks import _run_positioning_analysis

        mock_db.query.return_value.filter.return_value.first.return_value = mock_product

        mock_agent = MagicMock()
        mock_agent.execute.return_value = {
            'tagline': 'The best solution',
            'value_propositions': ['VP1', 'VP2'],
            'target_audience': 'SMBs',
            'key_differentiators': ['D1'],
            'positioning_statement': 'Statement',
            'market_segment': 'SMB',
            'source_urls': [],
            'confidence': 0.8
        }
        mock_agent_class.return_value = mock_agent

        result = _run_positioning_analysis(mock_db, mock_competitor, product_id=1)

        assert result['market_segment'] == 'SMB'
        assert result['tagline'] == 'The best solution'
        assert mock_db.add.called

    @patch('app.queue.tasks.LLMService')
    @patch('app.agents.changes_tracker.ChangesTrackerAgent')
    def test_run_changes_tracking(self, mock_agent_class, mock_llm_class, mock_db, mock_competitor, mock_product):
        """Test _run_changes_tracking helper."""
        from app.queue.tasks import _run_changes_tracking

        mock_db.query.return_value.filter.return_value.first.return_value = mock_product

        mock_agent = MagicMock()
        mock_agent.execute.return_value = {
            'changes': [
                {
                    'event_type': 'feature_launch',
                    'event_title': 'New Feature',
                    'event_description': 'Description',
                    'impact_level': 'major'
                }
            ],
            'total_changes': 1,
            'major_changes': 1,
            'release_velocity': 'high'
        }
        mock_agent_class.return_value = mock_agent

        result = _run_changes_tracking(mock_db, mock_competitor, product_id=1)

        assert result['total_changes'] == 1
        assert result['major_changes'] == 1
        assert result['release_velocity'] == 'high'

    @patch('app.queue.tasks.LLMService')
    @patch('app.agents.momentum_analyzer.MomentumAnalyzerAgent')
    def test_run_momentum_analysis(self, mock_agent_class, mock_llm_class, mock_db, mock_competitor, mock_product):
        """Test _run_momentum_analysis helper."""
        from app.queue.tasks import _run_momentum_analysis

        mock_db.query.return_value.filter.return_value.first.return_value = mock_product

        mock_agent = MagicMock()
        mock_agent.execute.return_value = {
            'customer_wins': [],
            'customer_growth_trend': 'accelerating',
            'notable_customers': ['BigCo'],
            'market_expansions': [],
            'partnerships': [],
            'release_velocity': 'high',
            'major_launches_count': 2,
            'community_signals': {},
            'momentum_score': 0.75,
            'momentum_trend': 'rising',
            'analysis_summary': 'Good momentum',
            'confidence': 0.7
        }
        mock_agent_class.return_value = mock_agent

        result = _run_momentum_analysis(mock_db, mock_competitor, product_id=1)

        assert result['momentum_score'] == 0.75
        assert result['momentum_trend'] == 'rising'

    @patch('app.queue.tasks.LLMService')
    @patch('app.agents.financials_analyzer.FinancialsAnalyzerAgent')
    def test_run_financials_analysis(self, mock_agent_class, mock_llm_class, mock_db, mock_competitor, mock_product):
        """Test _run_financials_analysis helper."""
        from app.queue.tasks import _run_financials_analysis

        mock_db.query.return_value.filter.return_value.first.return_value = mock_product

        mock_agent = MagicMock()
        mock_agent.execute.return_value = {
            'company_type': 'private',
            'total_funding': 50000000,
            'funding_rounds': [{'round_type': 'series_b'}],
            'funding_stage': 'series_b',
            'market_cap': None,
            'revenue_estimate': 10000000,
            'revenue_growth_yoy': 80,
            'employee_count': 100,
            'employee_growth_yoy': 50,
            'financial_health': 'strong',
            'analysis_summary': 'Strong financials',
            'data_sources': ['Crunchbase'],
            'confidence': 0.7
        }
        mock_agent_class.return_value = mock_agent

        result = _run_financials_analysis(mock_db, mock_competitor, product_id=1)

        assert result['company_type'] == 'private'
        assert result['financial_health'] == 'strong'


# ============================================================================
# Integration-style Tests
# ============================================================================

class TestTaskIntegration:
    """Integration-style tests for task flow."""

    @patch('app.queue.tasks.get_db')
    @patch('app.queue.tasks.QueueService')
    def test_full_deep_analysis_flow(
        self, mock_qs_class, mock_get_db, mock_db, mock_competitor, mock_config, mock_product
    ):
        """Test full deep analysis flow with all steps."""
        from app.queue.tasks import deep_analysis_task

        mock_get_db.return_value = mock_db
        mock_qs = MagicMock()
        mock_qs.mark_running.return_value = MagicMock(
            id=1, input_data={'competitor_id': 1}, product_id=1
        )
        mock_qs_class.return_value = mock_qs

        # Setup query returns for each lookup
        query_returns = [
            mock_competitor,    # ProductCompetitor
            mock_config,        # CompetitiveAgentConfig
            mock_product,       # CIProduct (for pricing)
            mock_product,       # CIProduct (for positioning)
            mock_product,       # CIProduct (for changes)
            mock_product,       # CIProduct (for momentum)
        ]
        mock_db.query.return_value.filter.return_value.first.side_effect = query_returns

        # Mock all agents
        with patch('app.queue.tasks._run_feature_extraction') as mock_features, \
             patch('app.queue.tasks._run_pricing_analysis') as mock_pricing, \
             patch('app.queue.tasks._run_positioning_analysis') as mock_positioning, \
             patch('app.queue.tasks._run_changes_tracking') as mock_changes, \
             patch('app.queue.tasks._run_momentum_analysis') as mock_momentum:

            mock_features.return_value = {'features_extracted': 15}
            mock_pricing.return_value = {'pricing_model': 'tiered', 'confidence': 0.8}
            mock_positioning.return_value = {'market_segment': 'Enterprise', 'confidence': 0.75}
            mock_changes.return_value = {'total_changes': 3, 'major_changes': 1}
            mock_momentum.return_value = {'momentum_score': 0.7, 'momentum_trend': 'rising'}

            result = deep_analysis_task(job_id=1)

            # Verify all analyses completed
            assert len(result['analyses_completed']) == 5
            assert 'feature_extraction' in result['analyses_completed']
            assert 'pricing_analysis' in result['analyses_completed']
            assert 'positioning_analysis' in result['analyses_completed']
            assert 'changes_tracking' in result['analyses_completed']
            assert 'momentum_analysis' in result['analyses_completed']

            # Verify no errors
            assert len(result['errors']) == 0

            # Verify competitor status updated
            assert mock_competitor.deep_analysis_status == 'completed'
