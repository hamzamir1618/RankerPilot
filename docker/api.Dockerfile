FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.4 /uv /bin/uv

COPY services/api/pyproject.toml ./

RUN uv sync --no-dev

COPY services/api/app ./app
COPY services/api/alembic ./alembic
COPY services/api/alembic.ini ./

COPY services/api/scripts/start_api.sh ./scripts/start_api.sh
RUN chmod +x ./scripts/start_api.sh

EXPOSE 8000

CMD ["./scripts/start_api.sh"]
