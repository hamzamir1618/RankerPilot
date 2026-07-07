from fastapi import FastAPI

app = FastAPI(title="Rankerpilot API")

@app.get("/health")
async def health_check():
    return {"status": "ok"}
