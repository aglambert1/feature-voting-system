"""add has_seen_welcome column to users

The welcome page (/welcome) is shown to PO/Admin users on first login.
Previously the "seen" flag lived in browser localStorage, which broke
when the same browser hosted multiple users (admin creating a new PO
account, then logging in as that PO on the same browser, never saw
the welcome). Move the flag to the User row so it follows the user
across devices.

Revision ID: o5p6q7r8s9t0
Revises: p6q7r8s9t0u1
Create Date: 2026-05-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "o5p6q7r8s9t0"
down_revision: Union[str, None] = "p6q7r8s9t0u1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default='0' is portable across SQLite and PostgreSQL — per CLAUDE.md
    # boolean conventions for migrations.
    op.add_column(
        "users",
        sa.Column(
            "has_seen_welcome",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "has_seen_welcome")
