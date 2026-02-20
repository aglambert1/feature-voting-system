"""remove_downvotes

Remove downvote support from voting system. Votes are now upvote-only
(vote_value=1). Updates the check constraint on the votes table.

Revision ID: a1b2c3d4e5f6
Revises: cf73c42b033a
Create Date: 2026-02-19 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'cf73c42b033a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Delete any existing downvotes (should be none, but defensive)
    op.execute("DELETE FROM votes WHERE vote_value != 1")

    # SQLite requires batch mode for constraint changes
    with op.batch_alter_table('votes') as batch_op:
        batch_op.drop_constraint('check_vote_value', type_='check')
        batch_op.create_check_constraint('check_vote_value', 'vote_value = 1')


def downgrade() -> None:
    with op.batch_alter_table('votes') as batch_op:
        batch_op.drop_constraint('check_vote_value', type_='check')
        batch_op.create_check_constraint('check_vote_value', 'vote_value IN (-1, 1)')
