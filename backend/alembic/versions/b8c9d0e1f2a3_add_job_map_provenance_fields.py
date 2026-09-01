"""Add provenance, validation, serve intent and statement timestamp to product_jobs

Supports measuring how circular a job map is. A map built entirely from the product's own
description makes coverage scores near-tautological and hides unserved jobs, so entry
provenance is recorded to make that visible. Corroboration — the signals establishing a job
is real — is derived from existing job_id_key linkage and deliberately not stored.

serve_intent exists so a job we deliberately don't serve can stay in the map without reading
as a gap. Without it a PM would reject exactly the competitor- and signal-derived jobs that
make the map less circular.

provenance is nullable with no backfill: existing rows have no recorded origin and guessing
one would assert a lineage we never observed. Defaults for the two string columns are safe
for existing rows — an unreviewed, in-target job is the correct reading of a job created
before either concept existed.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-08-31
"""
from alembic import op
import sqlalchemy as sa


revision = 'b8c9d0e1f2a3'
down_revision = 'a7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('product_jobs') as batch_op:
        batch_op.add_column(sa.Column('provenance', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column(
            'validation_state',
            sa.String(length=50),
            nullable=False,
            server_default='unvalidated',
        ))
        batch_op.add_column(sa.Column(
            'serve_intent',
            sa.String(length=50),
            nullable=False,
            server_default='in_target',
        ))
        batch_op.add_column(sa.Column(
            'statement_updated_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ))


def downgrade():
    with op.batch_alter_table('product_jobs') as batch_op:
        batch_op.drop_column('statement_updated_at')
        batch_op.drop_column('serve_intent')
        batch_op.drop_column('validation_state')
        batch_op.drop_column('provenance')
