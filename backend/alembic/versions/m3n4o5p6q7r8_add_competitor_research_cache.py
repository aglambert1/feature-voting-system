"""add competitor research cache columns

Phase B of the analysis-performance plan. Adds two columns on
product_competitors to cache Brave web-search results per-competitor
(TTL configurable via settings.competitor_research_cache_ttl_hours).
Subsequent audits within TTL can reuse the cache and skip the tool-use
loop entirely.

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-04-16 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "m3n4o5p6q7r8"
down_revision: Union[str, None] = "l2m3n4o5p6q7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "product_competitors",
        sa.Column("cached_search_results", sa.JSON(), nullable=True),
    )
    op.add_column(
        "product_competitors",
        sa.Column("cached_search_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("product_competitors", "cached_search_at")
    op.drop_column("product_competitors", "cached_search_results")
