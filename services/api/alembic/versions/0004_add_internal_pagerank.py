"""add_internal_pagerank

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add internal_pagerank column to pages table
    op.add_column('pages', sa.Column('internal_pagerank', sa.Numeric(), nullable=True))


def downgrade() -> None:
    # Remove internal_pagerank column
    op.drop_column('pages', 'internal_pagerank')
