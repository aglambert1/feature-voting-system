"""
Unit tests for Competitor Intelligence models.

Tests database relationships, constraints, and basic CRUD operations.
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.database import Base
from app.models.user import User, UserRole, ProductAccessMode
from app.models.competitor_intelligence import (
    CIProduct,
    CompetitorAnalysisSession,
    ProductCompetitor,
    SessionCompetitor,
    ProductCompetitorFeature,
    CompetitorFeature,
    AgentExecutionLog,
    ProductPermission,
    ProductPermissionLevel,
    ProductAnalysisHistory
)


@pytest.fixture(scope="function")
def db_session():
    """Create a temporary database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    yield session

    session.close()


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password="hashed123",
        full_name="Test User",
        role=UserRole.VOTER
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_create_ci_product(db_session, test_user):
    """Test creating a CI product."""
    product = CIProduct(
        created_by_user_id=test_user.id,
        product_name="Test Product",
        product_description="A test product for CI analysis"
    )
    db_session.add(product)
    db_session.commit()

    assert product.id is not None
    assert product.product_name == "Test Product"
    assert product.analysis_version == 0
    assert product.analysis_count == 0
    assert product.status == "active"
    assert product.created_at is not None


def test_unique_product_name_globally(db_session, test_user):
    """Test that product names must be globally unique (across all users)."""
    # Create another user
    user2 = User(
        email="user2@example.com",
        username="testuser2",
        hashed_password="hashed123",
        full_name="Test User 2",
        role=UserRole.VOTER
    )
    db_session.add(user2)
    db_session.commit()

    # First product by user 1
    product1 = CIProduct(
        created_by_user_id=test_user.id,
        product_name="Same Name",
        product_description="First product"
    )
    db_session.add(product1)
    db_session.commit()

    # Second product by user 2 with same name should fail
    product2 = CIProduct(
        created_by_user_id=user2.id,
        product_name="Same Name",
        product_description="Second product"
    )
    db_session.add(product2)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_product_session_relationship(db_session, test_user):
    """Test relationship between products and sessions."""
    product = CIProduct(
        created_by_user_id=test_user.id,
        product_name="Test Product",
        product_description="Description"
    )
    db_session.add(product)
    db_session.commit()

    session = CompetitorAnalysisSession(
        product_id=product.id,
        user_id=test_user.id,
        session_number=1,
        product_source_type="text",
        status="active"
    )
    db_session.add(session)
    db_session.commit()

    assert len(product.sessions) == 1
    assert product.sessions[0].session_number == 1
    assert session.product.product_name == "Test Product"


def test_cascade_delete_product(db_session, test_user):
    """Test that deleting a product cascades to sessions."""
    product = CIProduct(
        created_by_user_id=test_user.id,
        product_name="Test Product",
        product_description="Description"
    )
    db_session.add(product)
    db_session.commit()

    session = CompetitorAnalysisSession(
        product_id=product.id,
        user_id=test_user.id,
        session_number=1,
        product_source_type="text",
        status="active"
    )
    db_session.add(session)
    db_session.commit()

    product_id = product.id
    session_id = session.id

    db_session.delete(product)
    db_session.commit()

    # Session should be deleted
    assert db_session.query(CompetitorAnalysisSession).filter_by(id=session_id).first() is None


def test_competitor_discovery_flow(db_session, test_user):
    """Test the full competitor discovery flow."""
    # Create product and session
    product = CIProduct(
        created_by_user_id=test_user.id,
        product_name="My Product",
        product_description="My product description"
    )
    db_session.add(product)
    db_session.commit()

    session = CompetitorAnalysisSession(
        product_id=product.id,
        user_id=test_user.id,
        session_number=1,
        product_source_type="text",
        status="active"
    )
    db_session.add(session)
    db_session.commit()

    # Discover a competitor
    product_competitor = ProductCompetitor(
        product_id=product.id,
        competitor_name="Competitor A",
        competitor_url="https://competitor-a.com",
        first_discovered_session_id=session.id,
        status="active"
    )
    db_session.add(product_competitor)
    db_session.commit()

    # Add to session
    session_competitor = SessionCompetitor(
        session_id=session.id,
        product_competitor_id=product_competitor.id,
        competitor_name="Competitor A",
        competitor_url="https://competitor-a.com",
        discovery_source="ai_search",
        is_new_discovery=True,
        selected_by_user=True
    )
    db_session.add(session_competitor)
    db_session.commit()

    # Verify relationships
    assert len(product.competitors) == 1
    assert len(session.session_competitors) == 1
    assert session_competitor.product_competitor == product_competitor


def test_feature_extraction_flow(db_session, test_user):
    """Test the feature extraction flow."""
    # Setup product, session, competitor
    product = CIProduct(
        created_by_user_id=test_user.id,
        product_name="My Product 2",
        product_description="Description"
    )
    db_session.add(product)
    db_session.commit()

    session = CompetitorAnalysisSession(
        product_id=product.id,
        user_id=test_user.id,
        session_number=1,
        product_source_type="text",
        status="active"
    )
    db_session.add(session)
    db_session.commit()

    product_competitor = ProductCompetitor(
        product_id=product.id,
        competitor_name="Competitor A",
        first_discovered_session_id=session.id,
        status="active"
    )
    db_session.add(product_competitor)
    db_session.commit()

    session_competitor = SessionCompetitor(
        session_id=session.id,
        product_competitor_id=product_competitor.id,
        competitor_name="Competitor A",
        discovery_source="ai_search",
        is_new_discovery=True
    )
    db_session.add(session_competitor)
    db_session.commit()

    # Extract a feature
    competitor_feature = CompetitorFeature(
        session_competitor_id=session_competitor.id,
        feature_name="Advanced Analytics",
        feature_description="Detailed analytics dashboard",
        feature_category="analytics",
        extraction_confidence=0.95,
        selected_by_user=True
    )
    db_session.add(competitor_feature)
    db_session.commit()

    # Verify
    assert len(session_competitor.features) == 1
    assert competitor_feature.feature_name == "Advanced Analytics"


def test_agent_execution_logging(db_session, test_user):
    """Test agent execution logging."""
    product = CIProduct(
        created_by_user_id=test_user.id,
        product_name="Test Product 4",
        product_description="Description"
    )
    db_session.add(product)
    db_session.commit()

    session = CompetitorAnalysisSession(
        product_id=product.id,
        user_id=test_user.id,
        session_number=1,
        product_source_type="text",
        status="active"
    )
    db_session.add(session)
    db_session.commit()

    # Log an agent execution
    log = AgentExecutionLog(
        session_id=session.id,
        product_id=product.id,
        agent_name="ProductAnalyzerAgent",
        stage="product_analysis",
        input_data={"product_name": "Test Product"},
        output_data={"category": "SaaS"},
        llm_tokens_used=1500,
        execution_time_ms=2500,
        status="success"
    )
    db_session.add(log)
    db_session.commit()

    # Verify
    assert log.id is not None
    assert log.agent_name == "ProductAnalyzerAgent"
    assert log.llm_tokens_used == 1500
    assert len(session.agent_logs) == 1


def test_product_permissions(db_session, test_user):
    """Test product permission grants."""
    # Create another user
    user2 = User(
        email="user2@example.com",
        username="permuser",
        hashed_password="hashed123",
        full_name="Permission User",
        role=UserRole.VOTER
    )
    db_session.add(user2)
    db_session.commit()

    # Create product
    product = CIProduct(
        created_by_user_id=test_user.id,
        product_name="Shared Product",
        product_description="A product to test permissions"
    )
    db_session.add(product)
    db_session.commit()

    # Grant permission to user2
    permission = ProductPermission(
        product_id=product.id,
        user_id=user2.id,
        permission_level=ProductPermissionLevel.VIEW,
        granted_by_user_id=test_user.id
    )
    db_session.add(permission)
    db_session.commit()

    # Verify
    assert permission.id is not None
    assert permission.permission_level == ProductPermissionLevel.VIEW
    assert len(product.permissions) == 1
    assert product.permissions[0].user_id == user2.id


def test_unique_product_user_permission(db_session, test_user):
    """Test that a user can only have one permission per product."""
    # Create another user
    user2 = User(
        email="user3@example.com",
        username="uniqueuser",
        hashed_password="hashed123",
        full_name="Unique User",
        role=UserRole.VOTER
    )
    db_session.add(user2)
    db_session.commit()

    # Create product
    product = CIProduct(
        created_by_user_id=test_user.id,
        product_name="Unique Permission Product",
        product_description="Testing unique constraint"
    )
    db_session.add(product)
    db_session.commit()

    # Grant first permission
    permission1 = ProductPermission(
        product_id=product.id,
        user_id=user2.id,
        permission_level=ProductPermissionLevel.VIEW,
        granted_by_user_id=test_user.id
    )
    db_session.add(permission1)
    db_session.commit()

    # Try to grant duplicate permission
    permission2 = ProductPermission(
        product_id=product.id,
        user_id=user2.id,
        permission_level=ProductPermissionLevel.EDIT,
        granted_by_user_id=test_user.id
    )
    db_session.add(permission2)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_product_analysis_history(db_session, test_user):
    """Test product analysis history versioning."""
    # Create product
    product = CIProduct(
        created_by_user_id=test_user.id,
        product_name="Versioned Product",
        product_description="A product to test analysis history"
    )
    db_session.add(product)
    db_session.commit()

    # Create first analysis
    analysis1 = ProductAnalysisHistory(
        product_id=product.id,
        analysis_version=1,
        analyzed_by_user_id=test_user.id,
        product_description="First analysis",
        product_source_type="text",
        analyzed_structure={"category": "SaaS", "features": ["Feature 1"]},
        tokens_used=500
    )
    db_session.add(analysis1)
    db_session.commit()

    # Create second analysis
    analysis2 = ProductAnalysisHistory(
        product_id=product.id,
        analysis_version=2,
        analyzed_by_user_id=test_user.id,
        product_description="Second analysis",
        product_source_type="text",
        analyzed_structure={"category": "SaaS", "features": ["Feature 1", "Feature 2"]},
        tokens_used=600
    )
    db_session.add(analysis2)
    db_session.commit()

    # Verify
    assert len(product.analysis_history) == 2
    assert product.analysis_history[0].analysis_version == 1
    assert product.analysis_history[1].analysis_version == 2
    assert product.analysis_history[1].tokens_used == 600


def test_unique_product_analysis_version(db_session, test_user):
    """Test that analysis versions must be unique per product."""
    # Create product
    product = CIProduct(
        created_by_user_id=test_user.id,
        product_name="Version Unique Product",
        product_description="Testing unique version constraint"
    )
    db_session.add(product)
    db_session.commit()

    # Create first analysis
    analysis1 = ProductAnalysisHistory(
        product_id=product.id,
        analysis_version=1,
        analyzed_by_user_id=test_user.id,
        product_description="First",
        product_source_type="text"
    )
    db_session.add(analysis1)
    db_session.commit()

    # Try to create duplicate version
    analysis2 = ProductAnalysisHistory(
        product_id=product.id,
        analysis_version=1,
        analyzed_by_user_id=test_user.id,
        product_description="Second",
        product_source_type="text"
    )
    db_session.add(analysis2)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_product_competitor_research_cache_columns_default_null(db_session, test_user):
    """Phase B: cached_search_results and cached_search_at default to NULL.

    Exercising the column definitions end-to-end catches migration drift and
    ORM mismatches before they cause obscure failures during audits.
    """
    product = CIProduct(
        created_by_user_id=test_user.id,
        product_name="Cache Host",
        product_description="desc",
    )
    db_session.add(product)
    db_session.commit()

    competitor = ProductCompetitor(
        product_id=product.id,
        competitor_name="Acme",
        competitor_url="https://acme.com",
        status="active",
    )
    db_session.add(competitor)
    db_session.commit()
    db_session.refresh(competitor)

    assert competitor.cached_search_results is None
    assert competitor.cached_search_at is None

    # Also confirm the columns accept a JSON payload + timestamp and persist them.
    competitor.cached_search_results = [
        {"url": "https://acme.com/f", "title": "Features", "snippet": "x"},
    ]
    competitor.cached_search_at = datetime.now(timezone.utc)
    db_session.commit()
    db_session.refresh(competitor)

    assert len(competitor.cached_search_results) == 1
    assert competitor.cached_search_results[0]["url"] == "https://acme.com/f"
    assert competitor.cached_search_at is not None
