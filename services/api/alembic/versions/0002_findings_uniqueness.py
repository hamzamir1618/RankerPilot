"""findings_uniqueness

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-07 17:38:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_unique_constraint('uq_finding_audit_page_check', 'findings', ['audit_id', 'page_id', 'check_id'])

def downgrade() -> None:
    op.drop_constraint('uq_finding_audit_page_check', 'findings', type_='unique')
