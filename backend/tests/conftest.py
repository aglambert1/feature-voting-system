"""
Shared test fixtures for the backend test suite.

Provides common database session, mock services, test data fixtures,
and FastAPI TestClient fixtures for API endpoint testing.
"""

import os
import pytest
from unittest.mock import Mock
from sqlalchemy import create_engine, event, pool, text
from sqlalchemy.orm import sessionmaker, Session

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

_TEST_DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///:memory:")
_USE_PG = _TEST_DATABASE_URL.startswith("postgresql")

if _USE_PG:
    _pg_engine = create_engine(_TEST_DATABASE_URL)
else:
    _pg_engine = None


def _setup_pg_schema(engine):
    _has_pgvector = False
    with engine.connect() as conn:
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
            _has_pgvector = True
        except Exception:
            conn.rollback()
    Base.metadata.create_all(bind=engine)
    if _has_pgvector:
        with engine.connect() as conn:
            for table, col in [
                ("ideas", "embedding"),
                ("ci_products", "embedding"),
                ("product_features", "embedding"),
                ("product_competitor_features", "embedding"),
            ]:
                try:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} vector(1024)"))
                    conn.commit()
                except Exception:
                    conn.rollback()


if _USE_PG:
    _setup_pg_schema(_pg_engine)


@pytest.fixture(scope="function")
def db_session():
    if _USE_PG:
        conn = _pg_engine.connect()
        transaction = conn.begin()
        session = Session(bind=conn)

        nested = conn.begin_nested()

        @event.listens_for(session, "after_transaction_end")
        def restart_savepoint(session, transaction_inner):
            nonlocal nested
            if transaction_inner.nested and not transaction_inner.parent.nested:
                nested = conn.begin_nested()

        yield session

        session.close()
        transaction.rollback()
        conn.close()
    else:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=pool.StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        session = sessionmaker(bind=engine)()
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

    # Also disable the module-level limiter in auth (used by @limiter.limit decorators)
    from app.api.auth import limiter as auth_limiter
    auth_limiter.enabled = False

    yield TestClient(app)

    auth_limiter.enabled = True
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
        db_session, "voter@example.com", "voter", "Voter@pass1", UserRole.VOTER
    )


@pytest.fixture
def admin_user(db_session):
    """Create an ADMIN user with a known password for API tests."""
    return _create_user_with_password(
        db_session, "apiadmin@example.com", "apiadmin", "Admin@pass1", UserRole.ADMIN
    )


@pytest.fixture
def po_user(db_session):
    """Create a PRODUCT_OWNER user with a known password for API tests."""
    return _create_user_with_password(
        db_session, "apiowner@example.com", "apiowner", "Owner@pass1", UserRole.PRODUCT_OWNER
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
def voter_product_access(db_session, test_product, voter_user):
    """Grant voter_user VIEW access to test_product."""
    from app.models.competitor_intelligence import ProductPermission, ProductPermissionLevel

    perm = ProductPermission(
        product_id=test_product.id,
        user_id=voter_user.id,
        permission_level=ProductPermissionLevel.VIEW,
        granted_by_user_id=test_product.created_by_user_id,
    )
    db_session.add(perm)
    db_session.commit()
    return perm


@pytest.fixture
def test_invite_code(db_session, test_product, po_user):
    """Create a test invite code for the test product."""
    from app.models.product_invite import ProductInviteCode
    from app.models.competitor_intelligence import ProductPermissionLevel

    invite = ProductInviteCode(
        product_id=test_product.id,
        code=ProductInviteCode.generate_code(),
        created_by_user_id=po_user.id,
        permission_level=ProductPermissionLevel.VIEW,
    )
    db_session.add(invite)
    db_session.commit()
    db_session.refresh(invite)
    return invite


@pytest.fixture
def second_product(db_session, po_user):
    """Create a second test product owned by the same PO."""
    from app.models.competitor_intelligence import CIProduct

    product = CIProduct(
        product_name="Second Product",
        product_description="Another product for testing",
        product_category="Testing",
        created_by_user_id=po_user.id,
        status="active",
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


@pytest.fixture
def test_idea(db_session, test_product, voter_user, voter_product_access):
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
