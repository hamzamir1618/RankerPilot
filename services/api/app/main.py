from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.core.config import settings
from app.core.deps import async_session_factory
from app.core.rate_limit import redis_client
from app.routers import auth, projects, audits, keywords, admin, drift, shared, organizations, api_keys, webhooks

app = FastAPI(title="Rankerpilot API")

origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", tags=["Health"])
async def health_check():
    db_ok = False
    redis_ok = False
    errors = []

    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        errors.append(f"DB Error: {str(e)}")

    try:
        await redis_client.ping()
        redis_ok = True
    except Exception as e:
        errors.append(f"Redis Error: {str(e)}")

    if not db_ok or not redis_ok:
        raise HTTPException(status_code=503, detail={"status": "error", "errors": errors})
        
    return {"status": "ok", "db": "ok", "redis": "ok"}

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(audits.router)
app.include_router(keywords.router)
app.include_router(admin.router)
app.include_router(drift.router)
app.include_router(shared.router)
app.include_router(organizations.router)
app.include_router(api_keys.router)
app.include_router(webhooks.router)
