#!/usr/bin/env bash
set -e

echo "Running database migrations..."
uv run alembic upgrade head

echo "Starting Uvicorn..."
# Bind to PORT environment variable, defaulting to 8000
exec uv run uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
