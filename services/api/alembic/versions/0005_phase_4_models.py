"""Phase 4 models

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-20 10:36:00.000000

"""
from typing import Sequence, Union

from alembic import op # type: ignore
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Create project_schedules
    op.create_table('project_schedules',
    sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('audit_cadence', sa.String(length=20), nullable=True),
    sa.Column('rank_cadence', sa.String(length=20), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('project_id')
    )
    
    # 2. Create shared_report_tokens
    op.create_table('shared_report_tokens',
    sa.Column('token', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('audit_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=True),
    sa.Column('revoked', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['audit_id'], ['audits.id'], ),
    sa.PrimaryKeyConstraint('token')
    )
    
    # 3. Alter keywords add is_tracked
    op.add_column('keywords', sa.Column('is_tracked', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    
    # 4. Alter audits alter created_by nullable
    op.alter_column('audits', 'created_by',
               existing_type=postgresql.UUID(as_uuid=True),
               nullable=True)


def downgrade() -> None:
    op.alter_column('audits', 'created_by',
               existing_type=postgresql.UUID(as_uuid=True),
               nullable=False)
    op.drop_column('keywords', 'is_tracked')
    op.drop_table('shared_report_tokens')
    op.drop_table('project_schedules')
