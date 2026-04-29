"""drop orphan intensity_* columns from competitive_agent_configs

Both `intensity_similarity_threshold` and `intensity_idea_threshold` were
left over from the pre-JTBD-redesign auto-idea-generation flow. The PR #33
JTBD redesign moved auto-idea-generation onto `SynthesisConfig`
(`auto_generate_ideas` + `idea_priority_threshold`), and the `intensity_*`
fields have had no backend consumer since. The UI that wrote them was
removed earlier; the API + MCP read/write surface has been carrying dead
weight ever since.

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-04-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "n4o5p6q7r8s9"
down_revision: Union[str, None] = "m3n4o5p6q7r8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("competitive_agent_configs", "intensity_idea_threshold")
    op.drop_column("competitive_agent_configs", "intensity_similarity_threshold")


def downgrade() -> None:
    # Restore the columns with their original defaults so a rollback yields a
    # schema indistinguishable from the pre-upgrade state. Existing data is
    # NOT recovered (the columns held no live signal anyway).
    op.add_column(
        "competitive_agent_configs",
        sa.Column(
            "intensity_similarity_threshold",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.75"),
        ),
    )
    op.add_column(
        "competitive_agent_configs",
        sa.Column(
            "intensity_idea_threshold",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.0"),
        ),
    )
