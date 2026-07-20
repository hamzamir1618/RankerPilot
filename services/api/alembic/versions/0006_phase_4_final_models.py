"""Phase 4 final models

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op # type: ignore
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Add theme fields to organizations
    op.add_column('organizations', sa.Column('theme_logo_url', sa.Text(), nullable=True))
    op.add_column('organizations', sa.Column('theme_primary_color', sa.String(length=7), nullable=True))
    op.add_column('organizations', sa.Column('theme_accent_color', sa.String(length=7), nullable=True))
    op.add_column('organizations', sa.Column('theme_agency_name', sa.String(length=100), nullable=True))

    # 2. Create webhooks
    op.create_table('webhooks',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('secret', sa.String(length=64), nullable=False),
    sa.Column('events', postgresql.ARRAY(sa.String()), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # 3. Create webhook_deliveries
    op.create_table('webhook_deliveries',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('webhook_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('event_type', sa.String(length=60), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('response_status', sa.Integer(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['webhook_id'], ['webhooks.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('webhook_deliveries')
    op.drop_table('webhooks')
    op.drop_column('organizations', 'theme_agency_name')
    op.drop_column('organizations', 'theme_accent_color')
    op.drop_column('organizations', 'theme_primary_color')
    op.drop_column('organizations', 'theme_logo_url')
