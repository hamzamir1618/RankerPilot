import datetime
from dateutil.relativedelta import relativedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

async def create_future_partitions(db: AsyncSession, table_name: str, months_ahead: int = 3):
    """
    Creates monthly range partitions for PostgreSQL table `table_name`
    up to `months_ahead` months in the future.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    for i in range(months_ahead + 1):
        target_month_start = current_month_start + relativedelta(months=i)
        next_month_start = target_month_start + relativedelta(months=1)
        
        start_str = target_month_start.strftime('%Y-%m-%d')
        end_str = next_month_start.strftime('%Y-%m-%d')
        part_name = f"{table_name}_y{target_month_start.year}m{target_month_start.month:02d}"
        
        # Check if exists
        check_stmt = text(f"SELECT to_regclass('{part_name}')")
        res = await db.execute(check_stmt)
        exists = res.scalar() is not None
        
        if not exists:
            create_stmt = text(f"""
                CREATE TABLE IF NOT EXISTS {part_name} PARTITION OF {table_name}
                FOR VALUES FROM ('{start_str}') TO ('{end_str}')
            """)
            await db.execute(create_stmt)
            
    await db.commit()
