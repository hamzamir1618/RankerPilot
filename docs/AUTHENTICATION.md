# Authentication in RankerPilot

RankerPilot supports two primary authentication modes to securely protect resources: **Browser-Based (JWT Cookies)** and **Programmatic (API Keys)**.

## 1. Browser-Based Authentication (JWT Cookies)

When interacting with RankerPilot via the web dashboard (e.g., logging in with your email or via Google OAuth), the system utilizes **HTTP-only, Secure Cookies** to manage your session.

### How it works:
- **Login/Register:** You submit your credentials or OAuth code to `POST /v1/auth/login`, `POST /v1/auth/register`, or `POST /v1/auth/google`.
- **Response:** The API responds with a short-lived `access_token` (JWT) in the JSON body, and securely sets a `refresh_token` in an `HttpOnly` cookie.
- **Subsequent Requests:** Your frontend includes the `access_token` in the `Authorization: Bearer <token>` header for all API calls.
- **Refreshing:** When the `access_token` expires (typically in 15 minutes), the frontend calls `POST /v1/auth/refresh`. The browser automatically includes the `HttpOnly` refresh token cookie, and the API issues a fresh `access_token` and transparently rotates the refresh cookie.

This approach is highly secure against XSS (Cross-Site Scripting) attacks because malicious JavaScript cannot read the `HttpOnly` refresh token cookie.

---

## 2. Programmatic Authentication (API Keys)

If you are a developer integrating RankerPilot's capabilities into your own custom software, workflows, or scripts, you should use **API Keys**. API Keys are tied to your Organization, meaning they can access any project or audit within that Organization.

### How to generate an API Key:
1. Log in to the RankerPilot dashboard.
2. Navigate to **Organization Settings** > **API Keys**.
3. Click **Generate New Key** and give it a descriptive name (e.g., "Zapier Integration").
4. **Important:** The raw API key will be displayed **exactly once**. Copy it and store it securely (e.g., in a password manager or environment variable). RankerPilot only stores a one-way cryptographic hash of the key.

### How to use your API Key:
Include the API key in the `Authorization` header of your HTTP requests as a `Bearer` token.

**Example Request:**
```bash
curl -X GET "https://api.rankerpilot.com/v1/projects/" \
  -H "Authorization: Bearer rp_live_abc123.your_long_secret_key_string_here"
```

If the API key is missing, invalid, or revoked, the API will respond with a `401 Unauthorized`.
