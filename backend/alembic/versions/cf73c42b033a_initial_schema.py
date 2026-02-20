"""initial_schema

Revision ID: cf73c42b033a
Revises:
Create Date: 2026-02-19 16:27:57.690268

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cf73c42b033a'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Baseline migration — schema already exists via create_all().

    Future migrations will contain actual DDL changes.
    For a fresh PostgreSQL database, run create_all() first, then
    stamp this revision with: alembic stamp head
    """
    pass


def downgrade() -> None:
    """Cannot downgrade past the initial schema."""
    pass
