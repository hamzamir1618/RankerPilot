# RankerPilot API Reference

RankerPilot provides a fully-featured REST API that powers its automated SEO auditing and intelligence platform. Every action available in the dashboard—from triggering multi-agent technical SEO crawls to discovering keyword gaps and generating whitelabel PDF reports—is available programmatically. The API is designed to be easily embedded into your existing build pipelines, Zapier workflows, or custom internal tools.

## Quick Reference

| Method | Path | Description |
|--------|------|-------------|
| **Auth** | | |
| POST | `/v1/auth/register` | Create a new user + personal organization |
| POST | `/v1/auth/login` | Log in via email and password |
| POST | `/v1/auth/refresh` | Exchange a refresh token for a new access token |
| POST | `/v1/auth/google` | OAuth callback to log in via Google |
| POST | `/v1/auth/logout` | Revoke your session entirely |
| | | |
| **Projects** | | |
| GET | `/v1/projects/` | List all projects in your organization |
| POST | `/v1/projects/` | Create a new project |
| GET | `/v1/projects/{id}` | Fetch details of a specific project |
| DELETE | `/v1/projects/{id}` | Delete a project and all associated data |
| POST | `/v1/projects/{id}/gsc/connect` | Initialize a Google Search Console OAuth connection |
| POST | `/v1/projects/gsc/callback` | Finalize Google Search Console connection |
| POST | `/v1/projects/{id}/ga4/connect` | Initialize Google Analytics 4 OAuth connection |
| POST | `/v1/projects/ga4/callback` | Finalize Google Analytics 4 connection |
| POST | `/v1/projects/{id}/gbp/connect` | Initialize Google Business Profile connection |
| POST | `/v1/projects/gbp/callback` | Finalize Google Business Profile connection |
| | | |
| **Audits** | | |
| POST | `/v1/projects/{id}/audits` | Start a full or single-page audit |
| GET | `/v1/audits/{id}` | Check the status and high-level score of an audit |
| GET | `/v1/audits/{id}/findings` | Retrieve all specific SEO issues found |
| GET | `/v1/audits/{id}/action-plan` | Retrieve the AI-generated repair plan |
| GET | `/v1/audits/{id}/diff/{other_id}` | Compare two audits to see what changed |
| GET | `/v1/audits/{id}/pages` | View the specific pages crawled |
| GET | `/v1/audits/{id}/events` | Live SSE progress stream for a running audit |
| POST | `/v1/audits/{id}/report` | Generate a downloadable PDF report |
| GET | `/v1/reports/{id}` | Download the generated PDF |
| GET | `/v1/audits/{id}/export.csv` | Export findings as a CSV spreadsheet |
| | | |
| **Keywords** | | |
| POST | `/v1/projects/{id}/keywords/discover` | Run an AI keyword discovery job |
| POST | `/v1/projects/{id}/keywords/gap` | Find keywords competitors rank for that you don't |
| GET | `/v1/keyword-sets/{id}` | Retrieve a saved set of keywords |
| POST | `/v1/keywords/{id}/serp` | Pull a live Google Search Results snapshot |
| POST | `/v1/projects/{id}/tracking` | Set up recurring rank tracking |
| GET | `/v1/projects/{id}/tracking/trends` | View historical ranking movements |
| GET | `/v1/projects/{id}/keywords/export.csv` | Export keyword data as CSV |
| | | |
| **Drift & Baselines** | | |
| POST | `/v1/projects/{id}/baselines` | Lock an audit as the known "good state" |
| GET | `/v1/projects/{id}/drift` | View accidental SEO regressions (Drift) |
| POST | `/v1/projects/{id}/drift/{id}/acknowledge` | Dismiss a Drift alert |
| | | |
| **Reports & Sharing** | | |
| POST | `/v1/audits/{id}/share` | Generate a public, passwordless link to an audit |
| POST | `/v1/audits/{id}/share/{token}/revoke` | Destroy a public sharing link |
| GET | `/v1/shared/{token}` | View an audit without logging in (Public route) |
| | | |
| **Organizations & Admin** | | |
| PUT | `/v1/organizations/{id}/theme` | Update whitelabel colors and branding |
| POST | `/v1/organizations/{id}/logo` | Upload a whitelabel logo |
| POST | `/v1/admin/organizations/{id}/credits/top-up` | Add API credits to an org |
| | | |
| **API Keys & Webhooks** | | |
| POST | `/v1/organizations/{id}/api-keys` | Generate a programmatic API key |
| GET | `/v1/organizations/{id}/api-keys` | List active API keys |
| DELETE| `/v1/organizations/{id}/api-keys/{id}`| Revoke an API key |
| POST | `/v1/organizations/{id}/webhooks` | Register a new webhook endpoint |
| GET | `/v1/organizations/{id}/webhooks` | List registered webhooks |
| DELETE| `/v1/organizations/{id}/webhooks/{id}`| Remove a webhook |

## Table of Contents
1. [Authentication](#authentication)
2. [Auth](#auth)
3. [Projects](#projects)
4. [Audits](#audits)
5. [Keywords](#keywords)
6. [Drift & Baselines](#drift--baselines)
7. [Reports & Sharing](#reports--sharing)
8. [Organizations & Admin](#organizations--admin)
9. [API Keys & Webhooks](#api-keys--webhooks)
10. [SSE Event Contract](#sse-event-contract)

---

## Authentication
RankerPilot uses two forms of authentication depending on your use case: **JWT Cookies** (for browsers and frontend apps) and **Bearer API Keys** (for backend automation). Most endpoints require authentication, but public sharing routes (like `/v1/shared/{token}`) do not.

To use an API Key, include it in your header:
```http
Authorization: Bearer rp_live_ab12cd34.xxxxxxxxxxxx
```
> For a deep dive into session lifecycles, see [docs/AUTHENTICATION.md](AUTHENTICATION.md).

---

## Auth

These endpoints handle human users signing up and securely logging in via the Next.js frontend. They rely heavily on setting `HttpOnly` refresh token cookies.

#### `POST /v1/auth/register`
Creates a brand new user account and provisions a personal Organization workspace for them.

**When to use it:** You are building your own custom frontend and want to sign up a new human user to the platform.

**Request:**
```json
{
  "email": "hello@example.com",
  "password": "supersecurepassword"
}
```

**Example (curl):**
```bash
curl -X POST https://api.rankerpilot.app/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "hello@example.com", "password": "supersecurepassword"}'
```

**Success response — 200 OK:**
```json
{
  "access_token": "eyJhbGciOi...",
  "user_id": "8f14e45f-..."
}
```
*Note: A `Set-Cookie: refresh_token=...` header is also returned.*

**Gotchas / notes:**
- User passwords must be at least 8 characters.
- Registration implicitly spins up an `Organization`. API Keys and credits are tied to the Organization, not the individual user, allowing team sharing in the future.

---

## Projects

Projects are the root containers for all your work. A Project is tied to a specific root domain (like `example.com`), and all Audits, Keywords, and baselines belong to a Project.

#### `GET /v1/projects/`
Lists all Projects that the currently authenticated user's Organization has access to.

**When to use it:** Fetching the dashboard index view to show a user all their active properties.

**Example (curl):**
```bash
curl -X GET https://api.rankerpilot.app/v1/projects/ \
  -H "Authorization: Bearer <YOUR_API_KEY>"
```

**Success response — 200 OK:**
```json
[
  {
    "id": "11111111-...",
    "org_id": "22222222-...",
    "domain": "example.com",
    "name": "My Main Site",
    "industry": "ecommerce",
    "gsc_connected": true,
    "created_at": "2026-07-20T12:00:00Z"
  }
]
```

#### `POST /v1/projects/`
Creates a new container for a domain.

**When to use it:** A user types in a URL they want to track. You must create a Project before you can run an Audit.

**Request:**
```json
{
  "domain": "acmecorp.com",
  "name": "Acme Corp B2B",
  "industry": "b2b_saas"
}
```

**Example (curl):**
```bash
curl -X POST https://api.rankerpilot.app/v1/projects/ \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"domain": "acmecorp.com", "name": "Acme Corp B2B", "industry": "b2b_saas"}'
```

**Success response — 200 OK:**
```json
{
  "id": "3fa85f64...",
  "org_id": "...",
  "domain": "acmecorp.com",
  "name": "Acme Corp B2B",
  "industry": "b2b_saas",
  "gsc_connected": false,
  "created_at": "2026-07-20T12:05:00Z"
}
```

**Gotchas / notes:**
- The `industry` flag adjusts the severity of certain SEO checks (e.g. YMYL compliance is heavily prioritized if industry is `health` or `finance`).
- `domain` should be raw (e.g., `acmecorp.com`, not `https://www.acmecorp.com/path`).

#### `POST /v1/projects/{id}/gsc/connect`
Initiates an OAuth connection to Google Search Console to pull in real click data.

**When to use it:** A user clicks "Connect GSC" on their dashboard.

**Example (curl):**
```bash
curl -X POST https://api.rankerpilot.app/v1/projects/3fa85f64.../gsc/connect \
  -H "Authorization: Bearer <YOUR_API_KEY>"
```

**Success response — 200 OK:**
```json
{
  "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?..."
}
```
**Gotchas:**
- Your frontend must redirect the user to the `auth_url`. Upon completion, Google redirects them back to the `POST /v1/projects/gsc/callback` route.

---

## Audits

The core engine of RankerPilot. Endpoints here allow you to spawn asynchronous crawls and view the AI-analyzed findings.

#### `POST /v1/projects/{id}/audits`
Kicks off a background SEO analysis job.

**When to use it:** Trigger this after connecting a project to kick off its first health check, or on a recurring basis from your own scheduler if you don't want to use RankerPilot's built-in Celery Beat scheduling.

**Request:**
```json
{
  "mode": "full",
  "page_limit": 50,
  "root_url": "https://acmecorp.com/"
}
```

**Example (curl):**
```bash
curl -X POST https://api.rankerpilot.app/v1/projects/3fa85f64.../audits \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"mode": "full", "page_limit": 50, "root_url": "https://acmecorp.com/"}'
```

**Success response — 202 Accepted:**
```json
{
  "id": "99999999-...",
  "project_id": "3fa85f64...",
  "status": "queued",
  "mode": "full",
  "page_limit": 50,
  "root_url": "https://acmecorp.com/",
  "created_by": "8f14e45f-..."
}
```
*Note: 202 means the audit has been accepted and queued, not that it's finished — poll GET /v1/audits/{id} or subscribe to the SSE stream below to track progress.*

**Error response — 402 Payment Required** (insufficient credits):
```json
{
  "detail": {
    "error": "insufficient_credits",
    "current_balance": 2,
    "required": 10,
    "shortfall": 8
  }
}
```

**Gotchas / notes:**
- A `single_page` audit costs fewer credits than `full`.
- The `root_url` field validates against the crawler's SSRF protections — private/internal/localhost URLs are rejected with a 422 before any credit is spent.
- If the target site's `robots.txt` fully disallows crawling, the audit will complete with status `partial` and zero pages crawled rather than failing outright. Check the `error` field on `GET /v1/audits/{id}`.

#### `GET /v1/audits/{id}`
Check the status and top-level SEO score of an Audit.

**When to use it:** Loading the header of an audit report, or polling to see if a queued audit has finished.

**Example (curl):**
```bash
curl -X GET https://api.rankerpilot.app/v1/audits/99999999... \
  -H "Authorization: Bearer <YOUR_API_KEY>"
```

**Success response — 200 OK:**
```json
{
  "id": "99999999-...",
  "project_id": "...",
  "status": "done",
  "mode": "full",
  "page_limit": 50,
  "root_url": "https://acmecorp.com/",
  "score": 84.5,
  "category_scores": {
    "technical": 90,
    "content": 79
  },
  "started_at": "2026-07-20T12:06:00Z",
  "finished_at": "2026-07-20T12:10:00Z",
  "error": null
}
```

#### `GET /v1/audits/{id}/findings`
Returns the exact list of SEO issues discovered during the crawl.

**When to use it:** Rendering the table of errors (like "Missing H1s" or "Slow LCP") in the dashboard.

**Example (curl):**
```bash
curl -X GET https://api.rankerpilot.app/v1/audits/99999999.../findings \
  -H "Authorization: Bearer <YOUR_API_KEY>"
```

**Success response — 200 OK:**
```json
[
  {
    "id": "abcde...",
    "audit_id": "99999999...",
    "agent": "technical_seo",
    "check_id": "missing_h1",
    "status": "fail",
    "severity": "high",
    "category": "technical",
    "title": "Homepage is missing an H1 tag",
    "fix": "Add exactly one <h1> tag to the top of the body.",
    "effort": "low",
    "page_id": "..."
  }
]
```

---

## Keywords

RankerPilot interfaces with DataForSEO to pull live search volume, SERP features, and Keyword Gap data.

#### `POST /v1/projects/{id}/keywords/gap`
Identifies high-value keywords that your competitors rank for, but you don't.

**When to use it:** A user wants to find new content opportunities by entering 3 competitor URLs.

**Request:**
```json
{
  "competitors": ["stripe.com", "paddle.com", "lemonsqueezy.com"],
  "country": "US"
}
```

**Example (curl):**
```bash
curl -X POST https://api.rankerpilot.app/v1/projects/.../keywords/gap \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"competitors": ["stripe.com", "paddle.com"], "country": "US"}'
```

**Success response — 200 OK:**
```json
{
  "set_id": "55555555...",
  "status": "processing"
}
```
**Gotchas / notes:**
- This triggers a heavily rate-limited background task to DataForSEO. It does not return the list immediately. You must wait for the worker to finish, then fetch `GET /v1/keyword-sets/{set_id}`.

---

## Drift & Baselines

RankerPilot helps prevent accidental SEO regressions by locking an audit as a "Baseline", and then alerting you if future audits deviate negatively.

#### `POST /v1/projects/{id}/baselines`
Locks the results of the most recent audit as the "Good" state.

**When to use it:** A user just finished a massive site overhaul, got a 100/100 score, and wants to lock it in before the marketing team makes wild changes.

**Request:**
```json
{
  "audit_id": "99999999..."
}
```

**Example (curl):**
```bash
curl -X POST https://api.rankerpilot.app/v1/projects/.../baselines \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"audit_id": "99999999..."}'
```

**Success response — 202 Accepted:**
```json
{
  "status": "baseline_created",
  "baseline_count": 42
}
```

---

## Reports & Sharing

Generate client-ready PDFs or secure public sharing links.

#### `POST /v1/audits/{id}/share`
Generates a cryptographically secure, long-lived token that allows anyone to view the audit without logging in.

**When to use it:** An agency wants to send an audit report link to their client over Slack.

**Example (curl):**
```bash
curl -X POST https://api.rankerpilot.app/v1/audits/.../share \
  -H "Authorization: Bearer <YOUR_API_KEY>"
```

**Success response — 200 OK:**
```json
{
  "share_token": "<GENERATED_SHARE_TOKEN>",
  "url": "https://rankerpilot.app/shared/<GENERATED_SHARE_TOKEN>"
}
```

---

## Organizations & Admin

Whitelabel controls.

#### `PUT /v1/organizations/{id}/theme`
Applies a custom color palette to the dashboard and PDF reports.

**When to use it:** Agency accounts want the system to look like their own proprietary software.

**Request:**
```json
{
  "primary_color": "#FF0000",
  "secondary_color": "#00FF00"
}
```

**Example (curl):**
```bash
curl -X PUT https://api.rankerpilot.app/v1/organizations/.../theme \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"primary_color": "#FF0000", "secondary_color": "#00FF00"}'
```

**Success response — 200 OK:**
```json
{
  "org_id": "...",
  "primary_color": "#FF0000",
  "secondary_color": "#00FF00"
}
```

---

## API Keys & Webhooks

Set up programmatic access and event-driven architectures.

#### `POST /v1/organizations/{id}/webhooks`
Registers a URL that RankerPilot will automatically POST to when an event occurs.

**When to use it:** You want to be pinged in Slack (via Zapier) the moment a long-running SEO audit finishes.

**Request:**
```json
{
  "url": "https://hooks.zapier.com/hooks/catch/123/",
  "events": ["audit.completed", "drift.detected"]
}
```

**Example (curl):**
```bash
curl -X POST https://api.rankerpilot.app/v1/organizations/.../webhooks \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://hooks.zapier.com...", "events": ["audit.completed"]}'
```

**Success response — 200 OK:**
```json
{
  "id": "whk_77777777...",
  "url": "https://hooks.zapier.com/hooks/catch/123/",
  "events": ["audit.completed"],
  "secret": "whsec_..."
}
```
**Gotchas / notes:**
- The `secret` is returned exactly once. You must use it to verify the HMAC `X-Rankerpilot-Signature` on incoming requests to ensure they actually came from RankerPilot.

---

## SSE Event Contract

RankerPilot supports Server-Sent Events (SSE) to stream live progress to your frontend while an Audit is actively crawling pages and running AI models in the background.

#### `GET /v1/audits/{id}/events`

**When to use it:** You want a live progress bar and a scrolling terminal-like UI on the frontend while the user waits for the audit to finish. It establishes a persistent HTTP connection.

**Example (curl):**
```bash
curl -N -H "Accept: text/event-stream" \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  https://api.rankerpilot.app/v1/audits/99999999.../events
```

**Live Event Stream Response:**
*(Note: These arrive iteratively over several minutes, not all at once)*

```text
id: evt_1
event: audit.started
data: {"audit_id": "99999999-...", "timestamp": "2026-07-20T12:06:00Z"}

id: evt_2
event: crawl.progress
data: {"url": "https://acmecorp.com/about", "status_code": 200, "pages_crawled": 1, "total_limit": 50}

id: evt_3
event: agent.started
data: {"agent": "technical_seo", "message": "Analyzing Core Web Vitals..."}

id: evt_4
event: finding.discovered
data: {"check_id": "missing_h1", "severity": "high", "title": "Homepage is missing an H1 tag"}

id: evt_5
event: agent.completed
data: {"agent": "technical_seo"}

id: evt_6
event: audit.done
data: {"audit_id": "99999999-...", "score": 84.5}
```

**Gotchas / notes:**
- If the frontend disconnects, the audit *continues* running in the background via Celery.
- The browser's native `EventSource` API does not allow sending custom `Authorization` headers. If you are authenticating from a browser, the API relies on the `HttpOnly` cookie. If you are authenticating from a script, you must use a library that supports SSE over custom headers (e.g., `httpx-sse` in Python).
