"""ensure product_features.embedding column exists (pgvector)

The fast "does this feature already exist?" lookup
(VectorService.find_similar_product_features) queries
``product_features.embedding`` on PostgreSQL. That column was previously
created only by a runtime ``ALTER TABLE`` in ``init_db()`` (app/database.py),
not by a migration — so its existence depended on app startup having run that
code. This migration makes the column part of the managed schema.

PostgreSQL: add ``embedding vector(1024)`` if missing (idempotent; requires the
``vector`` extension, which init_db / earlier setup enables).

SQLite (local/CI): no-op. SQLite stores these embeddings in the
``vec_product_features`` sqlite-vec virtual table (created in init_db), not in a
column on product_features, so there is nothing to add here.

Revision ID: q7r8s9t0u1v2
Revises: o5p6q7r8s9t0
Create Date: 2026-06-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "q7r8s9t0u1v2"
down_revision: Union[str, None] = "o5p6q7r8s9t0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _pg_column_exists(conn, table: str, column: str) -> bool:
    return conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    ).first() is not None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        # SQLite uses the vec_product_features virtual table, not a column.
        return

    # Ensure pgvector is available, then add the column if it isn't there.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    if not _pg_column_exists(conn, "product_features", "embedding"):
        op.execute("ALTER TABLE product_features ADD COLUMN embedding vector(1024)")


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return
    if _pg_column_exists(conn, "product_features", "embedding"):
        op.execute("ALTER TABLE product_features DROP COLUMN embedding")
