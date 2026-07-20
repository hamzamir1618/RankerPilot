# RankerPilot

## What is this?
RankerPilot is an automated SEO auditing and intelligence platform. Think of it as a virtual SEO expert that scans websites, identifies exactly what needs to be fixed to improve Google and AI search rankings, and generates actionable, step-by-step repair plans. It coordinates complex checks in the background and presents the results in an easy-to-use dashboard and beautiful PDF reports.

---

## Prerequisites
Before you can run or deploy RankerPilot, you need a few accounts and API keys. You do not need to be a developer to get these, but you will need to sign up for them:

- **A Railway Account**: RankerPilot uses databases and background task runners that must run continuously. You will need a paid [Railway Hobby plan](https://railway.app/pricing) (typically $5 - $10/month depending on usage) to host this reliably.
- **A GitHub Account**: To securely copy (fork) this code repository and connect it to your deployment platform.

### Required External Services
| Service | Required or Optional? | What breaks without it? |
|---------|------------------------|-------------------------|
| **Anthropic API Key** | **Required** | The platform's AI-based recommendations and AI-Readiness SEO checks will completely fail. [Get it here](https://console.anthropic.com/). |
| **Google Cloud OAuth** | **Required** | Users will not be able to log in with Google, nor connect their Search Console (GSC), Analytics (GA4), or Business Profiles (GBP). [Setup instructions](https://console.cloud.google.com/). |
| **DataForSEO** | **Required** | You will not be able to pull Keyword search volumes, CPC data, or Live SERP (Search Engine Results Page) data. [Sign up here](https://dataforseo.com/). |
| **Google PageSpeed API** | **Required** | The platform won't be able to calculate Core Web Vitals performance scores for audited pages. [Get it here](https://developers.google.com/speed/docs/insights/v5/get-started). |
| **S3 Storage (e.g. AWS/R2)** | **Required** | The system won't be able to store or serve PDF reports and page HTML snapshots. Cloudflare R2 is highly recommended for affordability. |
| **Moz API** | *Optional* | Backlink and Domain Authority data will be omitted from the reports. |
| **SMTP / Email Provider** | *Optional* | The system will not be able to send email alerts when it detects changes (SEO Drift) on your websites. |

---

## One-click / Fastest path: Deploy to Railway

We use Railway to make deployment incredibly simple. You deploy the system in **two passes** to resolve a "chicken-and-egg" issue (the website needs to know the API's URL, and the API needs to know the website's URL for security).

### Pass 1: Deploy the Backend (API & Worker)
1. Log in to your [Railway Dashboard](https://railway.app/).
2. Click **New Project** -> **Deploy from GitHub repo** and select your fork of `rankerpilot`.
3. Because the repository contains a `railway.toml` file, Railway will automatically create 3 services for you: `api`, `worker`, and `web`.
4. Right-click the empty space in your Railway project canvas -> **New** -> **Database** -> Add **PostgreSQL**.
5. Right-click the canvas again -> **New** -> **Database** -> Add **Redis**.
6. Open the **Variables** settings for the Project (Shared Variables) and fill in the Environment Variables listed in the table below. (Railway will auto-fill `DATABASE_URL` and `REDIS_URL` for you).
7. Wait for the `api` and `worker` services to finish deploying.
8. Click on the `api` service -> **Settings** -> **Generate Domain**. *Copy this generated URL (e.g., `https://rankerpilot-api.up.railway.app`).*

**How do I know Pass 1 worked?** 
Visit `https://<YOUR_API_DOMAIN>/health` in your browser. You should see `{"status": "ok", "db": "ok", "redis": "ok"}`. 

### Pass 2: Deploy the Frontend (Web)
1. Go back to the **Shared Variables** settings in Railway.
2. Add a new variable called `NEXT_PUBLIC_API_BASE_URL` and paste the API URL you just copied.
3. Add a new variable called `ALLOWED_ORIGINS`. Click on your `web` service -> **Settings** -> **Generate Domain**. Paste this web domain into `ALLOWED_ORIGINS` (e.g., `https://rankerpilot-web.up.railway.app`).
4. Railway will automatically redeploy the services with the new variables.

**How do I know Pass 2 worked?**
Open your newly generated Web Domain in your browser. You should see the RankerPilot landing page, and you should be able to register a new account successfully!

> 📝 **Need a step-by-step checklist?** Use the [docs/railway-deploy-checklist.md](docs/railway-deploy-checklist.md).

---

## Environment Variables

Copy these variables into Railway's "Shared Variables" section.

### Database & Cache
| Variable | Required? | Description | Example |
|----------|-----------|-------------|---------|
| `DATABASE_URL` | Yes | Auto-injected by Railway. Points to Postgres. | `postgresql://...` |
| `REDIS_URL` | Yes | Auto-injected by Railway. Points to Redis. | `redis://...` |

### Authentication & Security
| Variable | Required? | Description | Example |
|----------|-----------|-------------|---------|
| `JWT_SECRET` | Yes | Random secure string used to sign login sessions. | `super_secret_string_123` |
| `JWT_REFRESH_SECRET`| Yes | Random secure string for the refresh token. | `another_secret_string_456` |
| `TOKEN_ENCRYPTION_KEY`| Yes | Random 32-character string to encrypt Google tokens in the database. | `32_character_random_string_here_` |
| `ALLOWED_ORIGINS` | Yes | The URL of your deployed frontend to allow secure browser communication (CORS). | `https://your-frontend.up.railway.app` |

### Google Integrations
| Variable | Required? | Description | Example |
|----------|-----------|-------------|---------|
| `GOOGLE_OAUTH_CLIENT_ID`| Yes | From Google Cloud Console. | `12345-abcde.apps.googleusercontent.com`|
| `GOOGLE_OAUTH_CLIENT_SECRET`| Yes| From Google Cloud Console. | `GOCSPX-secret123...` |
| `PSI_API_KEY` | Yes | Google PageSpeed Insights API Key. | `AIzaSyB_...` |

### SEO Data Providers & AI
| Variable | Required? | Description | Example |
|----------|-----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Yes | Claude API Key. | `sk-ant-api03-...` |
| `DATAFORSEO_LOGIN` | Yes | Your DataForSEO account email. | `you@email.com` |
| `DATAFORSEO_PASSWORD`| Yes | Your DataForSEO account password. | `password123` |
| `DFS_AUDIT_BUDGET_USD`| Yes | The maximum monthly dollar spend allowed on DataForSEO. | `50.00` |
| `MOZ_ACCESS_ID` | No | Moz API ID (optional). | `mozscape-123...` |
| `MOZ_SECRET_KEY` | No | Moz API Key (optional). | `secret...` |

### Storage
| Variable | Required? | Description | Example |
|----------|-----------|-------------|---------|
| `S3_ENDPOINT` | Yes | The connection URL to your S3 bucket. | `https://<account_id>.r2.cloudflarestorage.com` |
| `S3_BUCKET` | Yes | The name of the bucket you created. | `rankerpilot-storage` |
| `S3_ACCESS_KEY` | Yes | From your storage provider. | `access_key_123` |
| `S3_SECRET_KEY` | Yes | From your storage provider. | `secret_key_123` |

### Frontend
| Variable | Required? | Description | Example |
|----------|-----------|-------------|---------|
| `NEXT_PUBLIC_API_BASE_URL`| Yes | The public URL of your deployed API backend. | `https://rankerpilot-api.up.railway.app/v1` |

---

## Local development (for engineers)

If you are an engineer modifying the codebase, you do not need Railway to run it locally. We provide a `docker-compose.yml` to spin up local instances of PostgreSQL, Redis, and a local S3 emulator (MinIO).

1. Clone the repository.
2. Copy `.env.example` to `.env` and fill in your actual API keys.
3. Run the backing services:
   ```bash
   docker compose up -d
   ```
4. Start the API (in `services/api`):
   ```bash
   uv run alembic upgrade head
   uv run uvicorn app.main:app --reload
   ```
5. Start the background worker (in `services/api`):
   ```bash
   uv run celery -A app.workers worker --loglevel=info
   ```
6. Start the frontend web app (in `apps/web`):
   ```bash
   pnpm install
   pnpm dev
   ```

---

## Architecture overview

RankerPilot consists of four main pieces working together. When you view the dashboard, you are interacting with the **Web Application** (built on Next.js). When you click a button to start an audit, the Web Application talks to the **API** (built on Python FastAPI). The API saves the request to the **Database** (PostgreSQL) and sends a message through the **Cache/Queue** (Redis) to the **Background Worker** (Celery). The Worker does the heavy lifting: crawling websites, talking to AI (Claude), fetching SEO data, and saving PDF reports to **Storage** (S3), entirely in the background so your browser doesn't freeze.

---

## Troubleshooting (How to check if something's wrong)

- **The deployment failed in Railway immediately**: 90% of the time, this is due to a missing or malformed Environment Variable. Check the "Deploy Logs" tab in Railway. If it complains about a missing variable, add it to Shared Variables and Railway will automatically retry.
- **The app deploys, but Audits get stuck on "Queued"**: This means the API is working, but the Background Worker is either dead or disconnected. Click on your `worker` service in Railway and view the logs. Ensure it says `celery@... ready`. If it crashes, verify your `REDIS_URL` is correctly injected.
- **I can't log in with Google**: When you set up Google Cloud OAuth, you explicitly whitelist "Redirect URIs". If you try to log in from `https://rankerpilot.up.railway.app` but you only whitelisted `http://localhost:3000` in Google Cloud, Google will block the login with a "Redirect URI mismatch" error. Copy your Railway Web URL and add it to the Google Cloud Console.

---

## Support / Ownership

For internal support, questions, or if the platform goes offline unexpectedly, please contact:
**[hamzamirexe@gmail.com]**

---

*For detailed technical API integration documentation, see [docs/API.md](docs/API.md) and [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md).*
