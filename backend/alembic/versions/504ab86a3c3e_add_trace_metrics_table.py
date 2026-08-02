"""add trace_metrics table

Revision ID: 504ab86a3c3e
Revises: 4acecc740be0
Create Date: 2026-08-02 11:22:55.427291

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '504ab86a3c3e'
down_revision: Union[str, Sequence[str], None] = '4acecc740be0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('trace_metrics',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('trace_id', sa.UUID(), nullable=False),
    sa.Column('avg_similarity', sa.Float(), nullable=True),
    sa.Column('max_similarity', sa.Float(), nullable=True),
    sa.Column('min_similarity', sa.Float(), nullable=True),
    sa.Column('chunk_count', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['trace_id'], ['traces.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('trace_id')
    )

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('trace_metrics')
