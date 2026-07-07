FROM mcr.microsoft.com/playwright/python:v1.43.0-jammy

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=ghcr.io/astral-sh/uv:0.4 /uv /bin/uv

COPY services/api/pyproject.toml ./

RUN uv sync --no-dev

COPY services/api/app ./app

CMD ["celery", "-A", "app.workers", "worker", "-Q", "crawl,agents,reports", "-c", "4"]
