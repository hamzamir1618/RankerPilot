FROM mcr.microsoft.com/playwright/python:v1.43.0-jammy

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=ghcr.io/astral-sh/uv:0.4 /uv /bin/uv

COPY services/api/pyproject.toml ./

RUN uv sync --no-dev

COPY services/api/app ./app

# Start celery, falling back to 4 concurrent workers if not specified
CMD ["sh", "-c", "celery -A app.workers worker -Q crawl,agents,reports -c ${CELERY_CONCURRENCY:-4}"]
