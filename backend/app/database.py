"""
Database setup and session management.

This file configures SQLAlchemy to connect to the database and
provides a way to get database sessions for handling requests.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import settings


# Create the database engine
# The engine is the starting point for any SQLAlchemy application
# connect_args is needed for SQLite (not needed for PostgreSQL)
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False}  # Only needed for SQLite
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
    In production, you'd use migrations (Alembic) instead.
    """
    Base.metadata.create_all(bind=engine)


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

    db = SessionLocal()
    try:
        # Check if the bootstrap admin user exists
        bootstrap_admin = db.query(User).filter(
            User.username == settings.admin_username
        ).first()

        if bootstrap_admin:
            if bootstrap_admin.is_active:
                print(f"✓ Bootstrap admin user exists and is active: {settings.admin_username}")
            else:
                # Reactivate the bootstrap admin
                bootstrap_admin.is_active = True
                bootstrap_admin.role = UserRole.ADMIN  # Ensure they're still admin
                db.commit()
                print(f"✓ Reactivated bootstrap admin user: {settings.admin_username}")
        else:
            # Check if ANY active admin exists
            any_active_admin = db.query(User).filter(
                User.role == UserRole.ADMIN,
                User.is_active == True
            ).first()

            if any_active_admin:
                print(f"✓ Active admin exists: {any_active_admin.username}")
                print(f"  (Bootstrap admin '{settings.admin_username}' not created)")
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
                print(f"✓ Created bootstrap admin user: {settings.admin_username}")
                print(f"  No other active admin found - bootstrap admin is required")
    except Exception as e:
        print(f"✗ Error managing bootstrap admin user: {e}")
        db.rollback()
    finally:
        db.close()
