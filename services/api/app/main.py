from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, projects, audits, keys, crawler, keywords, admin, drift, shared

app = FastAPI(title="Rankerpilot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(audits.router)
app.include_router(keys.router)
app.include_router(crawler.router)
app.include_router(keywords.router)
app.include_router(admin.router)
app.include_router(drift.router)
app.include_router(shared.router)
