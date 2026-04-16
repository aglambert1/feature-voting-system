"""add evidence job linkage and citation tracking

Phase 4a of the JTBD competitive-analysis redesign:
- Add job_id_key column + index to evidence (auto-linked via embedding similarity)
- Add citation_count column to evidence (incremented by agents that cite evidence)
- Add last_cited_in column to evidence (context label of last citation)

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-04-14 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "k1l2m3n4o5p6"
down_revision: Union[str, None] = "j0k1l2m3n4o5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Job linkage column + index (set automatically via embedding similarity)
    op.add_column(
        "evidence",
        sa.Column("job_id_key", sa.String(length=50), nullable=True),
    )
    op.create_index("ix_evidence_job_id_key", "evidence", ["job_id_key"])

    # Citation tracking columns
    op.add_column(
        "evidence",
        sa.Column(
            "citation_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "evidence",
        sa.Column("last_cited_in", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("evidence", "last_cited_in")
    op.drop_column("evidence", "citation_count")
    op.drop_index("ix_evidence_job_id_key", table_name="evidence")
    op.drop_column("evidence", "job_id_key")
