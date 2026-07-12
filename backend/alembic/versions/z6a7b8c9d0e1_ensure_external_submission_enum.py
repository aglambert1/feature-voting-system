"""Ensure EXTERNAL_SUBMISSION exists in the PG sourcetype enum.

The sourcetype enum was created by create_all() at DB bootstrap, not by a
migration. EXTERNAL_SUBMISSION was added to the model on 2026-02-19; a
database bootstrapped before that date lacks the label and inserts of
externally-imported ideas would fail on PostgreSQL. ADD VALUE IF NOT EXISTS
is idempotent, so this is safe on databases that already have it.

SQLite stores enum columns as strings — no-op there.

Revision ID: z6a7b8c9d0e1
Revises: y5z6a7b8c9d0
Create Date: 2026-07-11
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'z6a7b8c9d0e1'
down_revision = 'y5z6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        # Uppercase member NAME, not lowercase value — PG stores enum labels
        # as the Python enum member names in this codebase (see CLAUDE.md).
        op.execute("ALTER TYPE sourcetype ADD VALUE IF NOT EXISTS 'EXTERNAL_SUBMISSION'")


def downgrade() -> None:
    # Removing an enum value requires a type rebuild; the label is harmless
    # if unused, so downgrade is a no-op.
    pass
