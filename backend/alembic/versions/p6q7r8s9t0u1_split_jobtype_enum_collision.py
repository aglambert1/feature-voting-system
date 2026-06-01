"""split colliding jobtype enum into queue_job_type + jtbd_job_type

Two distinct ``JobType`` enum classes both derived the PostgreSQL enum type
name ``jobtype`` (SQLAlchemy names a native enum after the Python class):

  - ``app.models.queue.JobType``                 -> queue_jobs.job_type
        (PRODUCT_ANALYSIS, COMPETITOR_DISCOVERY, ... )
  - ``app.models.competitor_intelligence.JobType`` -> product_jobs.job_type
        (FUNCTIONAL, EMOTIONAL, SOCIAL)

``Base.metadata.create_all()`` creates each type name once. Because
``app/models/__init__.py`` imports competitor_intelligence before queue, the
JTBD enum won, so on PostgreSQL the shared ``jobtype`` type only contained
FUNCTIONAL/EMOTIONAL/SOCIAL. Every insert into ``queue_jobs`` (any background
job) failed with ``invalid input value for enum jobtype: "PRODUCT_ANALYSIS"``.
SQLite never reproduced this (Enum -> VARCHAR+CHECK), so CI stayed green.

Fix: the models now pin explicit, distinct type names
(``queue_job_type`` and ``jtbd_job_type``). This migration re-points both
columns on PostgreSQL and drops the old shared ``jobtype`` type. On a fresh
DB built by create_all the new names already exist, so every step is guarded
and idempotent.

On SQLite there are no native enum types — enum columns are plain VARCHAR with
a CHECK constraint keyed on the *values* (lowercase), which never collided.
Nothing to do.

Revision ID: p6q7r8s9t0u1
Revises: n4o5p6q7r8s9
Create Date: 2026-06-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "p6q7r8s9t0u1"
down_revision: Union[str, None] = "n4o5p6q7r8s9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Canonical labels (UPPERCASE member names — matches SQLAlchemy's default
# name-based persistence and the existing prod enum labels).
QUEUE_JOB_TYPE_LABELS = [
    "PRODUCT_ANALYSIS",
    "COMPETITOR_DISCOVERY",
    "FEATURE_EXTRACTION",
    "FULL_WORKFLOW",
    "IDEA_NORMALIZATION",
    "IDEA_TRIAGE",
    "COMPETITIVE_MONITORING",
    "REPORT_GENERATION",
    "SCHEDULED_DEEP_ANALYSIS",
    "FEATURE_EXTRACTION_ONLY",
    "FUNCTIONAL_AUDIT",
    "LANDSCAPE_SYNTHESIS",
    "INTERNAL_DISCOVERY",
    "OPPORTUNITY_SYNTHESIS",
    "UNIFIED_SYNTHESIS",
    "ACTIVITY_INSIGHT",
    "JOB_MAP_EXTRACTION",
    "STRATEGIC_ANALYSIS_ONLY",
    "PRICING_ANALYSIS",
    "POSITIONING_ANALYSIS",
    "CHANGES_TRACKING",
    "MOMENTUM_ANALYSIS",
    "FINANCIALS_ANALYSIS",
]

JTBD_JOB_TYPE_LABELS = ["FUNCTIONAL", "EMOTIONAL", "SOCIAL"]


def _pg_type_exists(conn, name: str) -> bool:
    return conn.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = :name"),
        {"name": name},
    ).first() is not None


def _create_pg_enum(conn, name: str, labels: list) -> None:
    if _pg_type_exists(conn, name):
        return
    quoted = ", ".join("'%s'" % lbl for lbl in labels)
    op.execute("CREATE TYPE %s AS ENUM (%s)" % (name, quoted))


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        # SQLite: enum columns are VARCHAR+CHECK on values; no shared native
        # type, so the collision never existed. Nothing to migrate.
        return

    # 1. Ensure the two distinct enum types exist.
    _create_pg_enum(conn, "queue_job_type", QUEUE_JOB_TYPE_LABELS)
    _create_pg_enum(conn, "jtbd_job_type", JTBD_JOB_TYPE_LABELS)

    # 2. Re-point queue_jobs.job_type to queue_job_type (cast via text).
    #    Both tables are empty in the affected env, so the USING cast moves
    #    no rows; the cast is still correct if rows exist with valid labels.
    op.execute(
        "ALTER TABLE queue_jobs "
        "ALTER COLUMN job_type TYPE queue_job_type "
        "USING job_type::text::queue_job_type"
    )

    # 3. Re-point product_jobs.job_type to jtbd_job_type.
    op.execute(
        "ALTER TABLE product_jobs "
        "ALTER COLUMN job_type TYPE jtbd_job_type "
        "USING job_type::text::jtbd_job_type"
    )

    # 4. Drop the now-orphaned shared type (no columns reference it anymore).
    if _pg_type_exists(conn, "jobtype"):
        op.execute("DROP TYPE jobtype")


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    # Recreate the shared jobtype with the JTBD labels (its original content)
    # and collapse both columns back onto it.
    _create_pg_enum(conn, "jobtype", JTBD_JOB_TYPE_LABELS)

    op.execute(
        "ALTER TABLE product_jobs "
        "ALTER COLUMN job_type TYPE jobtype "
        "USING job_type::text::jobtype"
    )
    # queue_jobs labels are not a subset of jobtype's JTBD labels; a faithful
    # rollback only makes sense when queue_jobs is empty (the state this
    # migration was written for). Cast through text; this errors if
    # incompatible rows exist, which is the correct signal not to roll back.
    op.execute(
        "ALTER TABLE queue_jobs "
        "ALTER COLUMN job_type TYPE jobtype "
        "USING job_type::text::jobtype"
    )

    if _pg_type_exists(conn, "queue_job_type"):
        op.execute("DROP TYPE queue_job_type")
    if _pg_type_exists(conn, "jtbd_job_type"):
        op.execute("DROP TYPE jtbd_job_type")
