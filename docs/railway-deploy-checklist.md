# Railway Deployment Checklist

Use this simple step-by-step checklist to deploy RankerPilot on Railway without missing any crucial configuration.

- [ ] **1. Prepare Accounts**
  - [ ] Created a [Railway](https://railway.app/) account and added a payment method (required for databases).
  - [ ] Forked/connected this GitHub repository to your own GitHub account.
  - [ ] Collected API keys for Google Cloud (OAuth), DataForSEO, PageSpeed Insights, Anthropic, and S3.

- [ ] **2. Setup Railway Project**
  - [ ] Clicked "New Project" in Railway and selected "Deploy from GitHub repo".
  - [ ] Selected the `rankerpilot` repository. Railway will automatically detect the monolithic `railway.toml` and provision three services: `api`, `worker`, and `web`.
  - [ ] Added a **PostgreSQL** database plugin to the project.
  - [ ] Added a **Redis** cache plugin to the project.

- [ ] **3. Configure Environment Variables**
  - [ ] Copied all required variables from the table in the `README.md` into Railway's "Shared Variables" so they apply to all services.
  - [ ] Confirmed `DATABASE_URL` and `REDIS_URL` automatically populated from the managed plugins.

- [ ] **4. First-Pass Deployment (Backend)**
  - [ ] Triggered a manual deploy of the **API** service.
  - [ ] Clicked on the API service settings and generated a public Domain (e.g., `rankerpilot-api.up.railway.app`).
  - [ ] Verified the API is running by visiting `https://<YOUR_API_DOMAIN>/health` and seeing `{"status": "ok", "db": "ok", "redis": "ok"}`.
  - [ ] Triggered a manual deploy of the **Worker** service.
  - [ ] Checked the Worker logs and confirmed you see `celery@... ready` indicating it successfully connected to Redis.

- [ ] **5. Second-Pass Deployment (Frontend)**
  - [ ] Went back to Shared Variables and set `NEXT_PUBLIC_API_BASE_URL` to the public domain you generated for the API service.
  - [ ] Set `ALLOWED_ORIGINS` to the domain you plan to generate for the Web service (e.g., `https://rankerpilot.up.railway.app`).
  - [ ] Triggered a manual deploy of the **Web** service.
  - [ ] Clicked on the Web service settings and generated its public Domain.

- [ ] **6. Final Verification**
  - [ ] Opened your new Web application URL in the browser.
  - [ ] Successfully registered a new user account.
  - [ ] Created a Project and ran a test Audit, confirming the Audit progresses to "Done" (which verifies the Worker is correctly processing tasks).
