# RankerPilot

RankerPilot is an AI-powered SEO Auditing Platform. It features a modern Next.js React frontend, a high-performance FastAPI Python backend, and a Celery-based background task runner for executing distributed web crawling and AI agent evaluation pipelines.

This repository is organized into a monorepo structure:
- `/apps/web`: Next.js 15 App Router frontend (TailwindCSS, shadcn/ui).
- `/services/api`: FastAPI backend & Celery worker node (SQLAlchemy, AsyncPG).
- `/packages/shared`: Shared OpenAPI TypeScript client definitions.

---

## 1. System Requirements
Ensure you have the following installed on your machine:
- **Python 3.12+**
- **Node.js 18+** & npm
- **Docker & Docker Compose** (for PostgreSQL, Redis, and MinIO)
- **uv** (preferred) or **pip** (for Python package management)

## 2. Environment Setup

Before running anything, ensure your `.env` file in the root directory is populated. Here is a minimal example:

```env
ENV=development

# Database & Cache
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/rankerpilot
REDIS_URL=redis://localhost:6379/0

# S3 (MinIO Local)
S3_ENDPOINT=http://localhost:9000
S3_BUCKET=snapshots
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin

# Auth & Encryption
JWT_SECRET=super_secret_jwt_key
JWT_REFRESH_SECRET=super_secret_refresh_key
TOKEN_ENCRYPTION_KEY=super_secret_32_byte_key_here!
GOOGLE_OAUTH_CLIENT_ID=dummy_client_id
GOOGLE_OAUTH_CLIENT_SECRET=dummy_client_secret

# External APIs
ANTHROPIC_API_KEY=dummy
OPENAI_COMPAT_BASE_URL=http://dummy
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## 3. Installation

Navigate to the `services/api` directory and install the dependencies:

```bash
cd services/api

# Using uv (recommended)
uv sync

# Or using standard pip
pip install -e .
```

### Install Playwright Browsers
Because the crawler has a JS-rendering fallback, you must install the Chromium binary for Playwright:
```bash
uv run playwright install chromium
```

### Install Frontend Dependencies
Navigate to the `apps/web` directory and install the Node.js packages. This will also install the `@rankerpilot/shared` OpenAPI types.
```bash
cd apps/web
npm install
```

## 4. Database Setup

Ensure your local PostgreSQL daemon is running via Docker, then apply all Alembic migrations to build the tables, partitions, and constraints:

```bash
# Inside services/api/
uv run alembic upgrade head
```

### Optional: Seed Script
If you want to quickly test the UI without running the crawler, you can seed the database with dummy organizations, users, and audits (Note: this drops and recreates tables):
```powershell
$env:ENV="dev"  # Required to prevent running in production
python -m app.scripts.seed
```

## 5. Running the Application

To run the full stack locally, you need three separate terminal windows.

**Terminal 1: Start the FastAPI Server**
```bash
cd services/api
uv run uvicorn app.main:app --reload --port 8000
```

**Terminal 2: Start the Celery Worker**
*Note: On Windows, the `--pool=solo` flag is required to prevent multiprocessing crash loops.*
```bash
cd services/api
uv run celery -A app.workers.celery_app worker --loglevel=info -Q crawl,agents,reports --pool=solo
```

**Terminal 3: Start the Next.js Web App**
```bash
cd apps/web
npm run dev
```
The frontend will be available at `http://localhost:3000`.

## 6. Testing the Application

We have a comprehensive `pytest` suite that tests Auth, Project CRUD, Crawler logic, and the Celery Audits Pipeline (including Server-Sent Events).

Run the tests using:
```bash
cd services/api
uv run pytest tests/ -v
```
