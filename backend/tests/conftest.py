"""
Shared test fixtures for the backend test suite.

Provides common database session, mock services, test data fixtures,
and FastAPI TestClient fixtures for API endpoint testing.
"""

import os
import pytest
from unittest.mock import Mock
from sqlalchemy import create_engine, pool
from sqlalchemy.orm import sessionmaker

# Ensure test environment settings
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only-32chars!")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app.database import Base, get_db
# Import all models so Base.metadata knows about every table
import app.models  # noqa: F401
from app.models.user import User, UserRole
from app.services.llm_service import LLMService
from app.utils.security import hash_password, create_access_token


@pytest.fixture(scope="function")
def db_session():
    """Create a temporary in-memory database for testing.

    Each test function gets a fresh database with all tables created.
    The session is automatically closed after the test.

    Uses StaticPool so the same in-memory database is shared across
    threads (FastAPI TestClient runs sync handlers in a worker thread,
    which would otherwise get a separate empty in-memory DB).
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=pool.StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def mock_llm_service():
    """Mock LLM service for testing agent interactions."""
    service = Mock(spec=LLMService)
    return service


@pytest.fixture
def test_user(db_session):
    """Create a standard test user (VOTER role)."""
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


@pytest.fixture
def test_admin(db_session):
    """Create a test admin user."""
    user = User(
        email="admin@example.com",
        username="admin",
        hashed_password="hashed123",
        full_name="Test Admin",
        role=UserRole.ADMIN
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_po(db_session):
    """Create a test product owner user."""
    user = User(
        email="po@example.com",
        username="productowner",
        hashed_password="hashed123",
        full_name="Test PO",
        role=UserRole.PRODUCT_OWNER
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ============================================================================
# API Testing Fixtures
# ============================================================================

@pytest.fixture
def client(db_session):
    """FastAPI TestClient with DB dependency override.

    Provides a test client that uses the in-memory test database.
    Rate limiting is disabled for tests.
    """
    from fastapi.testclient import TestClient
    from app.main import app
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    # Override database dependency
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Disable rate limiting for tests
    app.state.limiter = Limiter(key_func=get_remote_address, enabled=False)

    yield TestClient(app)

    app.dependency_overrides.clear()


def _create_user_with_password(db_session, email, username, password, role, full_name=None):
    """Helper to create a user with a properly hashed password."""
    user = User(
        email=email,
        username=username,
        hashed_password=hash_password(password),
        full_name=full_name or username.title(),
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def voter_user(db_session):
    """Create a VOTER user with a known password for API tests."""
    return _create_user_with_password(
        db_session, "voter@example.com", "voter", "password123", UserRole.VOTER
    )


@pytest.fixture
def admin_user(db_session):
    """Create an ADMIN user with a known password for API tests."""
    return _create_user_with_password(
        db_session, "apiadmin@example.com", "apiadmin", "adminpass123", UserRole.ADMIN
    )


@pytest.fixture
def po_user(db_session):
    """Create a PRODUCT_OWNER user with a known password for API tests."""
    return _create_user_with_password(
        db_session, "apiowner@example.com", "apiowner", "ownerpass123", UserRole.PRODUCT_OWNER
    )


def auth_headers(user: User) -> dict:
    """Generate Authorization headers with a valid JWT for the given user."""
    token = create_access_token(data={"sub": user.username, "user_id": user.id})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_product(db_session, po_user):
    """Create a test CIProduct owned by the PO user."""
    from app.models.competitor_intelligence import CIProduct

    product = CIProduct(
        product_name="Test Product",
        product_description="A test product for testing",
        product_category="Testing",
        created_by_user_id=po_user.id,
        status="active",
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


@pytest.fixture
def test_idea(db_session, test_product, voter_user):
    """Create a test Idea linked to the test product."""
    from app.models.idea import Idea, IdeaStatus, SourceType

    idea = Idea(
        title="Test Idea",
        what_description="A test feature description",
        why_description="Because testing is valuable",
        use_case_description="Used to verify API endpoints work correctly",
        product_id=test_product.id,
        submitter_id=voter_user.id,
        source_type=SourceType.CUSTOMER_SUBMISSION,
        status=IdeaStatus.ACCEPTED,
        is_active=True,
    )
    db_session.add(idea)
    db_session.commit()
    db_session.refresh(idea)
    return idea
