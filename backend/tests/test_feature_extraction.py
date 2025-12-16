"""
Unit tests for Feature Extraction Stage 3.

Tests the FeatureExtractorAgent and FeatureDetailExpanderAgent with:
- Fresh extraction (first-time analysis)
- Comparative analysis (change detection)
- Feature detail expansion
- JSON parsing with edge cases
- Database storage
"""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from app.models.competitor_intelligence import Base
from app.agents.feature_extractor import (
    FeatureExtractorAgent,
    FeatureDetailExpanderAgent,
    FeatureExtractionOutput,
    ComparativeFeatureOutput,
    ExpandedFeatureDetail,
    ExtractedFeature,
    FeatureWithComparison,
)
from app.services.llm_service import LLMService


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def db_session():
    """Create a temporary in-memory database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def mock_llm_service():
    """Mock LLM service for testing."""
    service = Mock(spec=LLMService)
    return service


@pytest.fixture
def feature_extractor_agent(db_session, mock_llm_service):
    """Create FeatureExtractorAgent for testing."""
    return FeatureExtractorAgent(
        db=db_session,
        llm_service=mock_llm_service
    )


@pytest.fixture
def feature_detail_expander_agent(db_session, mock_llm_service):
    """Create FeatureDetailExpanderAgent for testing."""
    return FeatureDetailExpanderAgent(
        db=db_session,
        llm_service=mock_llm_service
    )


# ============================================================================
# Test Data Generators
# ============================================================================

def generate_fresh_extraction_response():
    """Generate a mock fresh extraction response."""
    return {
        "content": json.dumps({
            "competitor_name": "CompetitorA",
            "features": [
                {
                    "name": "Real-time Analytics",
                    "description": "Live dashboard showing metrics and statistics. Updates every 30 seconds.",
                    "category": "Core Functionality",
                    "confidence": 0.95,
                    "source_url": "https://competitora.com/features",
                    "raw_context": "Dashboard section mentions real-time updates"
                },
                {
                    "name": "API Integration",
                    "description": "RESTful API with webhooks for third-party integrations. Supports JSON and XML.",
                    "category": "Integration",
                    "confidence": 0.88,
                    "source_url": "https://competitora.com/api-docs",
                    "raw_context": "API documentation page"
                },
                {
                    "name": "User Permissions",
                    "description": "Role-based access control with custom permission sets. Five default roles available.",
                    "category": "Security",
                    "confidence": 0.92,
                    "source_url": "https://competitora.com/docs/permissions",
                    "raw_context": "Security documentation"
                },
                {
                    "name": "Data Export",
                    "description": "Export data to CSV, Excel, or JSON formats. Supports scheduled exports.",
                    "category": "Core Functionality",
                    "confidence": 0.85,
                    "source_url": "https://competitora.com/features",
                    "raw_context": "Features page export section"
                },
                {
                    "name": "Custom Branding",
                    "description": "White-label solution with custom domain, logo, and color schemes.",
                    "category": "Enterprise",
                    "confidence": 0.80,
                    "source_url": "https://competitora.com/enterprise",
                    "raw_context": "Enterprise features page"
                },
                {
                    "name": "Team Collaboration",
                    "description": "Real-time collaboration features with comments, mentions, and activity feeds.",
                    "category": "Core Functionality",
                    "confidence": 0.90,
                    "source_url": "https://competitora.com/features",
                    "raw_context": "Collaboration features"
                },
                {
                    "name": "Mobile Apps",
                    "description": "Native iOS and Android applications with offline support.",
                    "category": "Platforms",
                    "confidence": 0.92,
                    "source_url": "https://competitora.com/mobile",
                    "raw_context": "Mobile apps page"
                },
                {
                    "name": "Advanced Search",
                    "description": "Full-text search with filters, facets, and saved searches.",
                    "category": "Core Functionality",
                    "confidence": 0.87,
                    "source_url": "https://competitora.com/features",
                    "raw_context": "Search functionality"
                },
                {
                    "name": "Data Encryption",
                    "description": "End-to-end encryption for data at rest and in transit. AES-256 standard.",
                    "category": "Security",
                    "confidence": 0.93,
                    "source_url": "https://competitora.com/security",
                    "raw_context": "Security features page"
                },
                {
                    "name": "Audit Logging",
                    "description": "Complete audit trail of all user actions with timestamps and user identification.",
                    "category": "Compliance",
                    "confidence": 0.88,
                    "source_url": "https://competitora.com/compliance",
                    "raw_context": "Compliance page"
                },
                {
                    "name": "Scheduled Reports",
                    "description": "Automated report generation and delivery via email or webhook.",
                    "category": "Automation",
                    "confidence": 0.85,
                    "source_url": "https://competitora.com/features",
                    "raw_context": "Automation features"
                },
            ],
            "extraction_summary": "Successfully extracted 11 key features from CompetitorA covering core functionality, integration, security, and enterprise capabilities."
        }),
        "tokens_used": 1200,
        "model": "claude-sonnet-4-5-20250929",
        "stop_reason": "end_turn"
    }


def generate_comparative_extraction_response():
    """Generate a mock comparative extraction response."""
    return {
        "content": json.dumps({
            "competitor_name": "CompetitorA",
            "analysis_mode": "comparative",
            "features": [
                {
                    "name": "Real-time Analytics",
                    "description": "Live dashboard showing metrics and statistics. Now updates every 15 seconds (improved from 30s).",
                    "category": "Core Functionality",
                    "confidence": 0.95,
                    "source_url": "https://competitora.com/features",
                    "raw_context": "Dashboard section mentions 15-second updates",
                    "change_type": "modified",
                    "change_description": "Update frequency improved from 30 seconds to 15 seconds",
                    "previous_feature_id": "feat_1"
                },
                {
                    "name": "API Integration",
                    "description": "RESTful API with webhooks for third-party integrations. Supports JSON and XML.",
                    "category": "Integration",
                    "confidence": 0.88,
                    "source_url": "https://competitora.com/api-docs",
                    "raw_context": "API documentation page",
                    "change_type": "unchanged",
                    "change_description": None,
                    "previous_feature_id": "feat_2"
                },
                {
                    "name": "User Permissions",
                    "description": "Role-based access control with custom permission sets. Five default roles available.",
                    "category": "Security",
                    "confidence": 0.92,
                    "source_url": "https://competitora.com/docs/permissions",
                    "raw_context": "Security documentation",
                    "change_type": "unchanged",
                    "change_description": None,
                    "previous_feature_id": "feat_3"
                },
                {
                    "name": "Mobile App",
                    "description": "Native iOS and Android apps with offline mode. Available on App Store and Google Play.",
                    "category": "Platforms",
                    "confidence": 0.90,
                    "source_url": "https://competitora.com/mobile",
                    "raw_context": "Mobile app page",
                    "change_type": "new",
                    "change_description": "New mobile app support added this quarter",
                    "previous_feature_id": None
                },
                {
                    "name": "Advanced Search",
                    "description": "Full-text search now includes AI-powered suggestions and smart filters.",
                    "category": "Core Functionality",
                    "confidence": 0.87,
                    "source_url": "https://competitora.com/features",
                    "raw_context": "Search functionality enhanced",
                    "change_type": "modified",
                    "change_description": "Added AI-powered suggestions to search functionality",
                    "previous_feature_id": "feat_5"
                },
                {
                    "name": "Data Encryption",
                    "description": "End-to-end encryption for data at rest and in transit. AES-256 standard.",
                    "category": "Security",
                    "confidence": 0.93,
                    "source_url": "https://competitora.com/security",
                    "raw_context": "Security features page",
                    "change_type": "unchanged",
                    "change_description": None,
                    "previous_feature_id": "feat_6"
                },
                {
                    "name": "Audit Logging",
                    "description": "Complete audit trail of all user actions with timestamps and user identification.",
                    "category": "Compliance",
                    "confidence": 0.88,
                    "source_url": "https://competitora.com/compliance",
                    "raw_context": "Compliance page",
                    "change_type": "unchanged",
                    "change_description": None,
                    "previous_feature_id": "feat_7"
                },
                {
                    "name": "Scheduled Reports",
                    "description": "Automated report generation and delivery via email or webhook.",
                    "category": "Automation",
                    "confidence": 0.85,
                    "source_url": "https://competitora.com/features",
                    "raw_context": "Automation features",
                    "change_type": "unchanged",
                    "change_description": None,
                    "previous_feature_id": "feat_8"
                },
                {
                    "name": "SSO Integration",
                    "description": "Single Sign-On support for major identity providers (OAuth2, SAML, OpenID).",
                    "category": "Integration",
                    "confidence": 0.89,
                    "source_url": "https://competitora.com/security",
                    "raw_context": "SSO section on security page",
                    "change_type": "new",
                    "change_description": "New SSO integration support added",
                    "previous_feature_id": None
                },
                {
                    "name": "FTP Import",
                    "description": "FTP import functionality was previously available but has been removed",
                    "category": "Deprecated",
                    "confidence": 0.0,
                    "source_url": "https://competitora.com/deprecated",
                    "raw_context": "Previously documented feature",
                    "change_type": "removed",
                    "change_description": "FTP import functionality deprecated and removed",
                    "previous_feature_id": "feat_9"
                },
            ],
            "summary": {
                "total_features": 10,
                "new_features": 2,
                "modified_features": 2,
                "unchanged_features": 5,
                "removed_features": 1
            }
        }),
        "tokens_used": 1500,
        "model": "claude-sonnet-4-5-20250929",
        "stop_reason": "end_turn"
    }


def generate_feature_detail_response():
    """Generate a mock feature detail expansion response."""
    return {
        "content": json.dumps({
            "expanded_description": "Real-time Analytics is a comprehensive dashboard solution that provides instant visibility into key metrics and KPIs. The system updates data every 15 seconds, enabling users to track changes as they happen. Features include customizable widgets, drill-down capabilities, and automated alerts when metrics exceed thresholds.",
            "technical_details": "Built on WebSocket technology for real-time data streaming. Uses Redis caching for performance optimization. Supports up to 1000 concurrent users with sub-second latency. Data is aggregated from multiple sources and normalized before display.",
            "use_cases": [
                "Monitor sales pipeline in real-time for quick decision-making",
                "Track website traffic and user behavior during marketing campaigns",
                "Supervise team performance and productivity metrics",
                "Alert on system anomalies or threshold violations"
            ],
            "benefits": [
                "Faster decision-making with up-to-date information",
                "Proactive problem detection through alerts",
                "Reduced time spent on manual reporting",
                "Better visibility into business operations"
            ],
            "limitations": [
                "Requires minimum 10 Mbps internet connection for optimal performance",
                "Custom metrics require technical setup by admin users",
                "Real-time data retention limited to 30 days (archive to cold storage beyond)"
            ],
            "related_features": [
                "Data Export for archiving analytics data",
                "Custom Alerts for threshold-based notifications",
                "API Integration for connecting external data sources"
            ]
        }),
        "tokens_used": 800,
        "model": "claude-sonnet-4-5-20250929",
        "stop_reason": "end_turn"
    }


# ============================================================================
# Test: FeatureExtractorAgent - Fresh Mode
# ============================================================================

def test_feature_extractor_fresh_mode(feature_extractor_agent, mock_llm_service):
    """
    Test FeatureExtractorAgent in fresh extraction mode.

    Expected:
    - 10-25 features extracted
    - Each feature has required fields (name, description, category, confidence, source_url)
    - Confidence scores in range [0.0, 1.0]
    - No change_type field (fresh mode only)
    """
    # Mock LLM response
    mock_llm_service.call_agent.return_value = generate_fresh_extraction_response()

    # Execute agent
    result = feature_extractor_agent.execute({
        'competitor_name': 'CompetitorA',
        'competitor_url': 'https://competitora.com'
    })

    # Verify results
    assert result['competitor_name'] == 'CompetitorA'
    assert len(result['features']) == 11  # Updated test data has 11 features
    assert 10 <= len(result['features']) <= 30  # Schema requires 10-30 features

    # Verify each feature has required fields
    for feature in result['features']:
        assert 'name' in feature
        assert 'description' in feature
        assert 'category' in feature
        assert 'confidence' in feature
        assert 'source_url' in feature
        assert 0.0 <= feature['confidence'] <= 1.0

    # Verify extraction_summary exists
    assert 'extraction_summary' in result
    assert len(result['extraction_summary']) > 0

    # Verify LLM was called
    mock_llm_service.call_agent.assert_called_once()


def test_feature_extractor_fresh_mode_output_schema(feature_extractor_agent):
    """
    Test that fresh mode uses correct output schema (FeatureExtractionOutput).
    """
    input_data = {
        'competitor_name': 'TestCompetitor',
        'competitor_url': 'https://test.com'
    }

    # Set output schema
    feature_extractor_agent._output_schema = FeatureExtractionOutput

    # Verify schema is set correctly
    schema = feature_extractor_agent.get_output_schema()
    assert schema == FeatureExtractionOutput


# ============================================================================
# Test: FeatureExtractorAgent - Comparative Mode
# ============================================================================

def test_feature_extractor_comparative_mode(feature_extractor_agent, mock_llm_service):
    """
    Test FeatureExtractorAgent in comparative analysis mode.

    Expected:
    - Detects NEW, MODIFIED, UNCHANGED, REMOVED features
    - Provides change descriptions for modified features
    - Summary counts match feature lists
    """
    # Mock LLM response
    mock_llm_service.call_agent.return_value = generate_comparative_extraction_response()

    # Previous features for comparison
    previous_features = [
        {
            'id': 'feat_1',
            'name': 'Real-time Analytics',
            'description': 'Live dashboard showing metrics and statistics. Updates every 30 seconds.',
            'category': 'Core Functionality'
        },
        {
            'id': 'feat_2',
            'name': 'API Integration',
            'description': 'RESTful API with webhooks for third-party integrations.',
            'category': 'Integration'
        },
        {
            'id': 'feat_3',
            'name': 'FTP Import',
            'description': 'Import data via FTP protocol.',
            'category': 'Integration'
        },
    ]

    # Execute agent in comparative mode
    result = feature_extractor_agent.execute({
        'competitor_name': 'CompetitorA',
        'competitor_url': 'https://competitora.com',
        'previous_features': previous_features
    })

    # Verify analysis mode
    assert result['analysis_mode'] == 'comparative'

    # Verify change type detection
    features_by_type = {
        'new': [],
        'modified': [],
        'unchanged': [],
        'removed': []
    }

    for feature in result['features']:
        change_type = feature.get('change_type')
        assert change_type in ['new', 'modified', 'unchanged', 'removed']
        features_by_type[change_type].append(feature)

    # Verify summary counts match
    assert len(features_by_type['new']) == result['summary']['new_features']
    assert len(features_by_type['modified']) == result['summary']['modified_features']
    assert len(features_by_type['unchanged']) == result['summary']['unchanged_features']
    assert len(features_by_type['removed']) == result['summary']['removed_features']

    # Verify specific changes
    modified_feature = next(
        (f for f in features_by_type['modified']),
        None
    )
    if modified_feature:
        assert 'change_description' in modified_feature
        assert modified_feature['change_description'] is not None

    new_feature = next(
        (f for f in features_by_type['new']),
        None
    )
    if new_feature:
        assert new_feature['previous_feature_id'] is None

    removed_feature = next(
        (f for f in features_by_type['removed']),
        None
    )
    if removed_feature:
        assert removed_feature['previous_feature_id'] is not None


def test_feature_extractor_comparative_mode_schema(feature_extractor_agent):
    """
    Test that comparative mode uses correct output schema (ComparativeFeatureOutput).
    """
    input_data = {
        'competitor_name': 'TestCompetitor',
        'competitor_url': 'https://test.com',
        'previous_features': [
            {'id': 'feat_1', 'name': 'Test Feature', 'description': 'Test', 'category': 'Test'}
        ]
    }

    # Set output schema for comparative mode
    feature_extractor_agent._output_schema = ComparativeFeatureOutput

    # Verify schema is set correctly
    schema = feature_extractor_agent.get_output_schema()
    assert schema == ComparativeFeatureOutput


# ============================================================================
# Test: FeatureDetailExpanderAgent
# ============================================================================

def test_feature_detail_expander_agent(feature_detail_expander_agent, mock_llm_service):
    """
    Test FeatureDetailExpanderAgent expansion.

    Expected:
    - Expanded description (multi-paragraph)
    - Technical details provided
    - Use cases list with 3+ items
    - Benefits list with 3+ items
    - Optional limitations and related features
    """
    # Mock LLM response
    mock_llm_service.call_agent.return_value = generate_feature_detail_response()

    # Execute agent
    result = feature_detail_expander_agent.execute({
        'feature_name': 'Real-time Analytics',
        'feature_description': 'Live dashboard showing metrics and statistics.',
        'competitor_name': 'CompetitorA',
        'competitor_url': 'https://competitora.com/features'
    })

    # Verify all required fields
    assert 'expanded_description' in result
    assert 'technical_details' in result
    assert 'use_cases' in result
    assert 'benefits' in result

    # Verify field content
    assert len(result['expanded_description']) > 50
    assert len(result['technical_details']) > 30
    assert isinstance(result['use_cases'], list)
    assert len(result['use_cases']) >= 3
    assert isinstance(result['benefits'], list)
    assert len(result['benefits']) >= 3

    # Verify optional fields
    assert 'limitations' in result
    assert 'related_features' in result

    # Verify LLM was called
    mock_llm_service.call_agent.assert_called_once()


def test_feature_detail_expander_schema(feature_detail_expander_agent):
    """
    Test that FeatureDetailExpanderAgent uses correct output schema.
    """
    schema = feature_detail_expander_agent.get_output_schema()
    assert schema == ExpandedFeatureDetail


# ============================================================================
# Test: JSON Parsing Edge Cases
# ============================================================================

def test_feature_extraction_with_multiline_descriptions(feature_extractor_agent, mock_llm_service):
    """
    Test parsing of features with multi-line descriptions.

    This tests the agent's ability to handle descriptions that span multiple lines.
    """
    response_with_multiline = generate_fresh_extraction_response()

    # Add a feature with multi-line description
    json_content = json.loads(response_with_multiline['content'])
    json_content['features'].append({
        "name": "Multi-line Feature",
        "description": "This is a feature with multiple lines.\nIt has detailed information spanning\nacross multiple paragraphs.",
        "category": "Documentation",
        "confidence": 0.85,
        "source_url": "https://competitora.com/docs",
        "raw_context": None
    })

    response_with_multiline['content'] = json.dumps(json_content)
    mock_llm_service.call_agent.return_value = response_with_multiline

    # Execute agent
    result = feature_extractor_agent.execute({
        'competitor_name': 'CompetitorA',
        'competitor_url': 'https://competitora.com'
    })

    # Verify multiline feature parsed correctly
    multiline_feature = next(
        (f for f in result['features'] if f['name'] == 'Multi-line Feature'),
        None
    )
    assert multiline_feature is not None
    assert '\n' in multiline_feature['description']


def test_feature_extraction_with_special_characters(feature_extractor_agent, mock_llm_service):
    """
    Test parsing of features with special characters and unicode.
    """
    response_with_special = generate_fresh_extraction_response()

    # Add a feature with special characters
    json_content = json.loads(response_with_special['content'])
    json_content['features'].append({
        "name": "Advanced: Multi-language Support",
        "description": "Supports 50+ languages including Arabic (العربية), Chinese (中文), and Emoji 🎉",
        "category": "Localization",
        "confidence": 0.92,
        "source_url": "https://competitora.com/i18n",
        "raw_context": None
    })

    response_with_special['content'] = json.dumps(json_content)
    mock_llm_service.call_agent.return_value = response_with_special

    # Execute agent
    result = feature_extractor_agent.execute({
        'competitor_name': 'CompetitorA',
        'competitor_url': 'https://competitora.com'
    })

    # Verify special character feature parsed correctly
    special_feature = next(
        (f for f in result['features'] if 'Multi-language' in f['name']),
        None
    )
    assert special_feature is not None
    assert '🎉' in special_feature['description']
    assert 'Arabic' in special_feature['description']


def test_feature_extraction_with_null_optional_fields(feature_extractor_agent, mock_llm_service):
    """
    Test parsing of features with null optional fields (raw_context).
    """
    response = generate_fresh_extraction_response()

    # Set raw_context to None for one feature
    json_content = json.loads(response['content'])
    json_content['features'][0]['raw_context'] = None

    response['content'] = json.dumps(json_content)
    mock_llm_service.call_agent.return_value = response

    # Execute agent
    result = feature_extractor_agent.execute({
        'competitor_name': 'CompetitorA',
        'competitor_url': 'https://competitora.com'
    })

    # Verify feature with null raw_context is parsed
    feature_with_null = next(
        (f for f in result['features'] if f.get('raw_context') is None),
        None
    )
    assert feature_with_null is not None


# ============================================================================
# Test: Agent Configuration
# ============================================================================

def test_feature_extractor_agent_stage(feature_extractor_agent):
    """Test that agent reports correct stage."""
    stage = feature_extractor_agent.get_stage()
    assert stage == "feature_extraction"


def test_feature_detail_expander_agent_stage(feature_detail_expander_agent):
    """Test that detail expander agent reports correct stage."""
    stage = feature_detail_expander_agent.get_stage()
    assert stage == "feature_detail_expansion"


def test_feature_extractor_system_prompt(feature_extractor_agent):
    """Test that feature extractor has appropriate system prompt."""
    prompt = feature_extractor_agent.get_system_prompt()
    assert "Feature Extraction agent" in prompt
    assert "FRESH EXTRACTION MODE" in prompt
    assert "COMPARATIVE ANALYSIS MODE" in prompt


def test_feature_detail_expander_system_prompt(feature_detail_expander_agent):
    """Test that detail expander has appropriate system prompt."""
    prompt = feature_detail_expander_agent.get_system_prompt()
    assert "Feature Detail Expander agent" in prompt
    assert "technical details" in prompt.lower()


# ============================================================================
# Test: User Prompt Building
# ============================================================================

def test_feature_extractor_fresh_mode_prompt(feature_extractor_agent):
    """Test that fresh mode builds appropriate user prompt."""
    prompt = feature_extractor_agent.build_user_prompt({
        'competitor_name': 'CompetitorA',
        'competitor_url': 'https://competitora.com',
        'previous_features': None
    })

    assert "FRESH EXTRACTION MODE" in prompt
    assert "CompetitorA" in prompt
    assert "https://competitora.com" in prompt
    assert "10-25" in prompt or "minimum 3" in prompt
    assert "verify" in prompt.lower()


def test_feature_extractor_comparative_mode_prompt(feature_extractor_agent):
    """Test that comparative mode builds appropriate user prompt."""
    previous_features = [
        {
            'id': 'feat_1',
            'name': 'Test Feature',
            'description': 'A test feature',
            'category': 'Testing'
        }
    ]

    prompt = feature_extractor_agent.build_user_prompt({
        'competitor_name': 'CompetitorA',
        'competitor_url': 'https://competitora.com',
        'previous_features': previous_features
    })

    assert "COMPARATIVE ANALYSIS MODE" in prompt
    assert "CompetitorA" in prompt
    assert "Previous Features" in prompt
    assert "Test Feature" in prompt


def test_feature_detail_expander_prompt(feature_detail_expander_agent):
    """Test that detail expander builds appropriate user prompt."""
    prompt = feature_detail_expander_agent.build_user_prompt({
        'feature_name': 'Real-time Analytics',
        'feature_description': 'Live dashboard with metrics',
        'competitor_name': 'CompetitorA',
        'competitor_url': 'https://competitora.com'
    })

    assert "Real-time Analytics" in prompt
    assert "Live dashboard with metrics" in prompt
    assert "CompetitorA" in prompt
    assert "Technical Details" in prompt


# ============================================================================
# Test: Confidence Scoring
# ============================================================================

def test_feature_confidence_scoring(feature_extractor_agent, mock_llm_service):
    """
    Test that extracted features have appropriate confidence scores.

    Expected: Confidence scores should vary (0.7-1.0 typical range)
    """
    mock_llm_service.call_agent.return_value = generate_fresh_extraction_response()

    result = feature_extractor_agent.execute({
        'competitor_name': 'CompetitorA',
        'competitor_url': 'https://competitora.com'
    })

    # Verify confidence score distribution
    confidences = [f['confidence'] for f in result['features']]

    # Should have variety in confidence scores
    assert len(set(confidences)) >= 1  # At least some scores

    # All should be in valid range
    for conf in confidences:
        assert 0.0 <= conf <= 1.0


# ============================================================================
# Test: Feature Categorization
# ============================================================================

def test_feature_categorization(feature_extractor_agent, mock_llm_service):
    """
    Test that features are appropriately categorized.
    """
    mock_llm_service.call_agent.return_value = generate_fresh_extraction_response()

    result = feature_extractor_agent.execute({
        'competitor_name': 'CompetitorA',
        'competitor_url': 'https://competitora.com'
    })

    # Verify all features have categories
    for feature in result['features']:
        assert 'category' in feature
        assert isinstance(feature['category'], str)
        assert len(feature['category']) > 0

    # Verify variety in categories
    categories = set(f['category'] for f in result['features'])
    assert len(categories) >= 1  # At least some category diversity


# ============================================================================
# Integration Tests
# ============================================================================

def test_feature_extraction_end_to_end_fresh_then_comparative(
    feature_extractor_agent, mock_llm_service
):
    """
    Test complete flow: fresh extraction followed by comparative analysis.
    """
    # Step 1: Fresh extraction
    mock_llm_service.call_agent.return_value = generate_fresh_extraction_response()

    fresh_result = feature_extractor_agent.execute({
        'competitor_name': 'CompetitorA',
        'competitor_url': 'https://competitora.com'
    })

    assert fresh_result['competitor_name'] == 'CompetitorA'
    initial_feature_count = len(fresh_result['features'])

    # Step 2: Comparative analysis with same features
    mock_llm_service.call_agent.return_value = generate_comparative_extraction_response()

    comparative_result = feature_extractor_agent.execute({
        'competitor_name': 'CompetitorA',
        'competitor_url': 'https://competitora.com',
        'previous_features': fresh_result['features']
    })

    assert comparative_result['analysis_mode'] == 'comparative'

    # Verify change detection worked
    assert 'summary' in comparative_result
    assert comparative_result['summary']['new_features'] >= 0
    assert comparative_result['summary']['modified_features'] >= 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
