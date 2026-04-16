"""add job_assessments, evidence_citations, and audit workflow fields

Add columns for JTBD-centric functional audits and decoupled audit/synthesis:
- competitor_functional_reports: job_assessments, evidence_citations
- product_competitors: audit_enabled, audit_status, audit_last_run, synthesis_included

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-04-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "i9j0k1l2m3n4"
down_revision: Union[str, None] = "h8i9j0k1l2m3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- CompetitorFunctionalReport: JTBD job assessments + evidence citations ---

    op.add_column(
        "competitor_functional_reports",
        sa.Column("job_assessments", sa.JSON(), nullable=True),
    )
    op.add_column(
        "competitor_functional_reports",
        sa.Column("evidence_citations", sa.JSON(), nullable=True),
    )

    # --- ProductCompetitor: decoupled audit/synthesis workflow ---

    op.add_column(
        "product_competitors",
        sa.Column("audit_enabled", sa.Boolean(), nullable=False, server_default='0'),
    )
    op.add_column(
        "product_competitors",
        sa.Column("audit_status", sa.String(50), nullable=True),
    )
    op.add_column(
        "product_competitors",
        sa.Column("audit_last_run", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "product_competitors",
        sa.Column("synthesis_included", sa.Boolean(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    # Reverse order of additions
    op.drop_column("product_competitors", "synthesis_included")
    op.drop_column("product_competitors", "audit_last_run")
    op.drop_column("product_competitors", "audit_status")
    op.drop_column("product_competitors", "audit_enabled")

    op.drop_column("competitor_functional_reports", "evidence_citations")
    op.drop_column("competitor_functional_reports", "job_assessments")
