"""
User model for database.

This defines the structure of the 'users' table in the database.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class UserRole(str, enum.Enum):
    """
    User roles that determine what actions a user can perform.

    - ADMIN: Full access to everything including user management and all products
    - VOTER: Can vote and submit ideas only (no product management)
    - PRODUCT_OWNER: All VOTER permissions plus product management and competitive intelligence
    """
    ADMIN = "admin"
    VOTER = "voter"
    PRODUCT_OWNER = "product_owner"


class ProductAccessMode(str, enum.Enum):
    """
    Default product access mode for a user.

    - SINGLE_USER: User can only see products they created
    - TEAM_WIDE: User can see all products (team collaboration mode)
    """
    SINGLE_USER = "single_user"
    TEAM_WIDE = "team_wide"


class User(Base):
    """
    User model representing a user account.

    SQLAlchemy will automatically create a 'users' table with these columns.
    Each instance of this class represents one row in the table.
    """

    # Table name in the database
    __tablename__ = "users"

    # Primary key - unique ID for each user
    # autoincrement=True means the database automatically assigns the next number
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Email address - must be unique (no two users with same email)
    # index=True makes lookups by email faster
    email = Column(String, unique=True, index=True, nullable=False)

    # Username - must be unique
    username = Column(String, unique=True, index=True, nullable=False)

    # Hashed password (we NEVER store plain text passwords!)
    # This will be set using bcrypt hashing
    hashed_password = Column(String, nullable=False)

    # User's full name (optional)
    full_name = Column(String, nullable=True)

    # User role - defaults to VOTER
    role = Column(Enum(UserRole), default=UserRole.VOTER, nullable=False)

    # Product access mode - defaults to SINGLE_USER (only see own products)
    # Set to TEAM_WIDE to allow viewing all products in team collaboration mode
    default_product_access = Column(
        Enum(ProductAccessMode),
        default=ProductAccessMode.SINGLE_USER,
        nullable=False
    )

    # Is the account active? (can be used to disable accounts)
    is_active = Column(Boolean, default=True, nullable=False)

    # When the account was created
    # server_default=func.now() means the database sets this automatically
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # When the account was last updated
    # onupdate=func.now() means this updates automatically when the row changes
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Relationships
    ideas = relationship("Idea", back_populates="submitter", foreign_keys="[Idea.submitter_id]")
    votes = relationship("Vote", back_populates="user")
    submissions = relationship("Submission", back_populates="submitter")

    def __repr__(self):
        """
        String representation of the User object (helpful for debugging).
        """
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"
