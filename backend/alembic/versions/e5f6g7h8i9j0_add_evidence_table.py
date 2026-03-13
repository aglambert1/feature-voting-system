"""add evidence table for product factbase

Create the evidence table for storing flexible, source-agnostic
product intelligence (competitive intel, interview insights,
market signals, research notes, etc.).

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-03-10 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e5f6g7h8i9j0"
down_revision: Union[str, None] = "d4e5f6g7h8i9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evidence",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("ci_products.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "evidence_type",
            sa.Enum(
                "competitive_intel",
                "customer_interview",
                "market_signal",
                "internal_note",
                "research",
                "pricing_change",
                "partnership",
                "product_launch",
                "analyst_report",
                name="evidencetype",
            ),
            nullable=False,
            index=True,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("source_description", sa.String(255), nullable=True),
        sa.Column(
            "competitor_id",
            sa.Integer(),
            sa.ForeignKey("product_competitors.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("extra_data", sa.JSON(), nullable=True),
        sa.Column("jtbd_statement", sa.Text(), nullable=True),
        sa.Column("jtbd_embedding", sa.JSON(), nullable=True),
        sa.Column("content_embedding", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.String(100), nullable=False, server_default="api"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("evidence")
    # Drop the enum type (PostgreSQL only; SQLite ignores this)
    op.execute("DROP TYPE IF EXISTS evidencetype")
