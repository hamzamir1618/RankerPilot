from fastapi import FastAPI
from app.routers import auth, projects, audits

app = FastAPI(title="Rankerpilot API")

@app.get("/health")
async def health_check():
    return {"status": "ok"}

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(audits.router)
