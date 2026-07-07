# Rankerpilot

## Local Development Bootstrap

To get started with local development, run the following commands:

```bash
git clone ... && cd rankerpilot
cp .env.example .env
docker compose -f docker/compose.yaml up -d
cd services/api && uv sync && uv run alembic upgrade head
uv run uvicorn app.main:app --reload
uv run celery -A app.workers worker -Q crawl,agents,reports -c 4
cd ../../apps/web && pnpm i && pnpm dev
```
