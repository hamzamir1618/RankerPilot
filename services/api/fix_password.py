import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.config import settings
from app.services.auth_service import hash_password

async def run():
    engine = create_async_engine(str(settings.DATABASE_URL))
    async with engine.begin() as conn:
        h = hash_password('demo_password')
        await conn.execute(text("UPDATE users SET password_hash = :h WHERE email = :email"), {"h": h, "email": "demo@rankerpilot.com"})
    print("Password updated successfully")

if __name__ == '__main__':
    asyncio.run(run())
