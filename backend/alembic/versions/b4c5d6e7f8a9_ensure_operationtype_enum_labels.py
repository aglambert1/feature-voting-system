"""Ensure every OperationType label exists in the PG operationtype enum.

The operationtype enum was created by create_all() at DB bootstrap, not by a
migration, and no migration has added a label since. A database bootstrapped
before a member was added to the model lacks that label, and the llm_usage_logs
insert for that operation fails on PostgreSQL (seen for SELF_ASSESSMENT, which
also rolled back the calling task's session). ADD VALUE IF NOT EXISTS is
idempotent, so this is safe on databases that already have every label.

SQLite stores enum columns as strings — no-op there.

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-10-27
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'b4c5d6e7f8a9'
down_revision = 'a3b4c5d6e7f8'
branch_labels = None
depends_on = None

# Uppercase member NAMES, not lowercase values — PG stores enum labels as the
# Python enum member names in this codebase (see CLAUDE.md). Listed here rather
# than imported so the migration stays fixed as the model evolves.
OPERATION_TYPE_LABELS = [
    'IDEA_TRIAGE',
    'IDEA_STRUCTURING',
    'PRODUCT_ANALYSIS',
    'COMPETITOR_DISCOVERY',
    'COMPETITOR_FEATURE_EXTRACTION',
    'GAP_ANALYSIS',
    'OPPORTUNITY_SYNTHESIS',
    'FUNCTIONAL_AUDIT',
    'LANDSCAPE_SYNTHESIS',
    'ACTIVITY_INSIGHT',
    'INTERNAL_DISCOVERY',
    'SELF_ASSESSMENT',
    'OTHER',
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        for label in OPERATION_TYPE_LABELS:
            op.execute(f"ALTER TYPE operationtype ADD VALUE IF NOT EXISTS '{label}'")


def downgrade() -> None:
    # Removing an enum value requires a type rebuild; the labels are harmless
    # if unused, so downgrade is a no-op.
    pass
