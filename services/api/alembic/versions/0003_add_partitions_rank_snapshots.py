"""add_partitions_rank_snapshots

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone
import calendar

# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Creates the first 3 months of partitions for the rank_snapshots table.
    
    NOTE: In production, you must set up a scheduled job (e.g. cron, celery beat, 
    or pg_cron) to run monthly and execute:
    CREATE TABLE rank_snapshots_YYYY_MM PARTITION OF rank_snapshots 
    FOR VALUES FROM ('YYYY-MM-01') TO ('YYYY-MM-01' + interval '1 month');
    """
    conn = op.get_bind()
    
    now = datetime.now(timezone.utc)
    
    # We will create partitions for the current month, and the next 2 months
    for i in range(3):
        # Calculate year and month
        month = now.month + i
        year = now.year
        if month > 12:
            month -= 12
            year += 1
            
        # Calculate next month for the upper bound
        next_month = month + 1
        next_year = year
        if next_month > 12:
            next_month -= 12
            next_year += 1
            
        start_date_str = f"{year}-{month:02d}-01"
        end_date_str = f"{next_year}-{next_month:02d}-01"
        partition_name = f"rank_snapshots_{year}_{month:02d}"
        
        # PostgreSQL syntax for creating a partition
        stmt = f"""
        CREATE TABLE IF NOT EXISTS {partition_name} 
        PARTITION OF rank_snapshots 
        FOR VALUES FROM ('{start_date_str}') TO ('{end_date_str}');
        """
        conn.execute(sa.text(stmt))


def downgrade() -> None:
    conn = op.get_bind()
    now = datetime.now(timezone.utc)
    
    for i in range(3):
        month = now.month + i
        year = now.year
        if month > 12:
            month -= 12
            year += 1
            
        partition_name = f"rank_snapshots_{year}_{month:02d}"
        conn.execute(sa.text(f"DROP TABLE IF EXISTS {partition_name}"))
