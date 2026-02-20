"""
Database setup and session management.

This file configures SQLAlchemy to connect to the database and
provides a way to get database sessions for handling requests.
"""

import logging
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import Engine

from app.config import settings

logger = logging.getLogger(__name__)


# Create the database engine
# The engine is the starting point for any SQLAlchemy application
# check_same_thread is only needed for SQLite (not needed for PostgreSQL)
_connect_args = {"check_same_thread": False} if "sqlite" in settings.database_url else {}
engine = create_engine(
    settings.database_url,
    connect_args=_connect_args
)

# SessionLocal is a factory for creating database sessions
# A session is like a "workspace" for database operations
# commit() saves changes, rollback() undoes them
SessionLocal = sessionmaker(
    autocommit=False,  # Don't auto-save changes
    autoflush=False,   # Don't auto-send changes to database
    bind=engine        # Connect to our engine
)

# Base class for all database models
# All your models (User, Idea, Vote, etc.) will inherit from this
Base = declarative_base()


# Load SQLite extensions on connection (for vector search)
@event.listens_for(Engine, "connect")
def configure_sqlite(dbapi_conn, connection_record):
    """
    Configure SQLite-specific settings.

    Loads the sqlite-vec extension for vector similarity search.
    Only applies to SQLite connections (not PostgreSQL).
    """
    # Check if this is a SQLite connection (not PostgreSQL)
    if 'sqlite' in str(settings.database_url).lower():
        try:
            # Enable extension loading
            dbapi_conn.enable_load_extension(True)

            # Load sqlite-vec extension using the installed package path
            import sqlite_vec
            ext_path = sqlite_vec.loadable_path()
            dbapi_conn.load_extension(ext_path)
            logger.debug("Loaded sqlite-vec extension")
        except Exception as e:
            logger.warning("Failed to load sqlite-vec: %s (Vector search will not be available)", e)

        # Enable foreign key constraint enforcement (off by default in SQLite)
        dbapi_conn.execute("PRAGMA foreign_keys = ON")


def get_db():
    """
    Dependency function that provides a database session.

    This is used in FastAPI routes like this:
        @app.get("/users/")
        def get_users(db: Session = Depends(get_db)):
            ...

    The 'yield' keyword makes this a generator that:
    1. Creates a new database session
    2. Gives it to your route function
    3. Automatically closes it when the request is done (even if there's an error)
    """
    db = SessionLocal()
    try:
        yield db  # Provide the session to the route
    finally:
        db.close()  # Always close the session when done


def init_db():
    """
    Initialize the database by creating all tables.

    This creates tables for all models that inherit from Base.
    Also sets up vector search infrastructure (database-specific).
    In production, you'd use migrations (Alembic) instead.
    """
    # Import all models so they are registered with Base.metadata
    # This must happen before create_all() is called
    import app.models.user  # noqa: F401
    import app.models.idea  # noqa: F401
    import app.models.vote  # noqa: F401
    import app.models.competitor_intelligence  # noqa: F401
    import app.models.queue  # noqa: F401
    import app.models.competitive_agent  # noqa: F401
    import app.models.idea_lifecycle_status  # noqa: F401

    # Create standard tables
    Base.metadata.create_all(bind=engine)

    # Database-specific vector search initialization
    db = SessionLocal()
    try:
        if 'postgresql' in str(engine.url):
            # PostgreSQL: Enable pgvector extension
            db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            logger.info("pgvector extension enabled")

            # Add embedding column to ci_products if not exists
            # Note: This will error if column already exists, which is fine
            try:
                db.execute(text("ALTER TABLE ci_products ADD COLUMN embedding vector(384)"))
                db.commit()
                logger.info("Added embedding column to ci_products table")
            except Exception as e:
                db.rollback()
                # Column likely already exists, which is fine
                pass
        else:
            # SQLite: Create vec_ideas virtual table for vector search
            db.execute(text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS vec_ideas
                USING vec0(
                    idea_id INTEGER PRIMARY KEY,
                    embedding FLOAT[384]
                )
            """))
            logger.info("sqlite-vec vec_ideas virtual table created")

            # SQLite: Create vec_products virtual table for product embeddings
            # Note: vec0 uses first column as primary key automatically
            db.execute(text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS vec_products
                USING vec0(
                    embedding FLOAT[384]
                )
            """))

            # Create a regular table to store product chunk metadata
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS product_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    chunk_text TEXT,
                    vec_rowid INTEGER,
                    UNIQUE(product_id, chunk_index)
                )
            """))
            logger.info("sqlite-vec vec_products virtual table created")

            # SQLite: Create vec_competitor_features virtual table for competitor feature embeddings
            db.execute(text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS vec_competitor_features
                USING vec0(
                    feature_id INTEGER PRIMARY KEY,
                    embedding FLOAT[384]
                )
            """))
            logger.info("sqlite-vec vec_competitor_features virtual table created")

            # SQLite: Create vec_product_features virtual table for product's own feature embeddings
            db.execute(text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS vec_product_features
                USING vec0(
                    feature_id INTEGER PRIMARY KEY,
                    embedding FLOAT[384]
                )
            """))
            logger.info("sqlite-vec vec_product_features virtual table created")

        db.commit()
    except Exception as e:
        logger.warning("Vector extension setup: %s (Vector search may not be available)", e)
    finally:
        db.close()


def create_initial_admin():
    """
    Create the initial admin user if no active admin exists.

    This runs on startup to ensure there's always at least one active admin user.
    The admin credentials are loaded from environment variables.

    Logic:
    - If the bootstrap admin username exists and is active: do nothing
    - If the bootstrap admin exists but is inactive: reactivate it
    - If no active admin exists anywhere: create the bootstrap admin
    """
    from app.config import settings
    from app.models.user import User, UserRole
    from app.utils.security import hash_password

    # Skip bootstrap admin creation if no password is configured
    if not settings.admin_password:
        logger.info("No ADMIN_PASSWORD set — skipping bootstrap admin creation")
        return

    db = SessionLocal()
    try:
        # Check if the bootstrap admin user exists
        bootstrap_admin = db.query(User).filter(
            User.username == settings.admin_username
        ).first()

        if bootstrap_admin:
            if bootstrap_admin.is_active:
                logger.info("Bootstrap admin user exists and is active: %s", settings.admin_username)
            else:
                # Reactivate the bootstrap admin
                bootstrap_admin.is_active = True
                bootstrap_admin.role = UserRole.ADMIN  # Ensure they're still admin
                db.commit()
                logger.info("Reactivated bootstrap admin user: %s", settings.admin_username)
        else:
            # Check if ANY active admin exists
            any_active_admin = db.query(User).filter(
                User.role == UserRole.ADMIN,
                User.is_active == True
            ).first()

            if any_active_admin:
                logger.info("Active admin exists: %s (bootstrap admin '%s' not created)",
                            any_active_admin.username, settings.admin_username)
            else:
                # No active admin exists - create bootstrap admin
                admin_user = User(
                    email=settings.admin_email,
                    username=settings.admin_username,
                    hashed_password=hash_password(settings.admin_password),
                    full_name=settings.admin_full_name,
                    role=UserRole.ADMIN,
                    is_active=True
                )
                db.add(admin_user)
                db.commit()
                logger.info("Created bootstrap admin user: %s (no other active admin found)", settings.admin_username)
    except Exception as e:
        logger.error("Error managing bootstrap admin user: %s", e)
        db.rollback()
    finally:
        db.close()
