# RankerPilot API Reference

This document is automatically generated from the OpenAPI specification.

## GET /health
**Health Check**

No description provided.

**Authentication:** None

### Responses
- **200**: Successful Response

#### Example Success Response
```json
{}
```

---

## POST /v1/auth/register
**Register a new user**

Creates a new user account and returns an access token along with setting an HTTP-only refresh token cookie.

**Authentication:** None

### Request Body
| Field | Type | Required | Description |
|---|---|---|---|
| `email` | `string` | Yes | The user's email address. |
| `password` | `string` | Yes | The user's chosen password, minimum 8 characters. |

#### Example Request
```json
{
  "email": "string_value",
  "password": "string_value"
}
```

### Responses
- **200**: Successfully registered.
- **400**: Email already registered.
- **429**: Too many registration attempts.
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (400)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## POST /v1/auth/login
**Login user**

Authenticates a user via email and password, returning an access token and setting a refresh token cookie.

**Authentication:** None

### Request Body
| Field | Type | Required | Description |
|---|---|---|---|
| `email` | `string` | Yes | The user's registered email address. |
| `password` | `string` | Yes | The user's password. |

#### Example Request
```json
{
  "email": "string_value",
  "password": "string_value"
}
```

### Responses
- **200**: Successfully logged in.
- **400**: Invalid credentials.
- **429**: Too many login attempts.
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (400)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## POST /v1/auth/refresh
**Refresh access token**

Rotates the refresh token securely and issues a new access token. Requires the `refresh_token` HTTP-only cookie to be present.

**Authentication:** None

### Responses
- **200**: Successfully refreshed tokens.
- **401**: No refresh token provided or token invalid/expired.
- **403**: Refresh token family revoked due to reuse detection.
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (401)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## POST /v1/auth/google
**Google OAuth login**

Exchanges a Google OAuth authorization code for an access token and sets a refresh token cookie.

**Authentication:** None

### Request Body
| Field | Type | Required | Description |
|---|---|---|---|
| `code` | `string` | Yes | The authorization code returned by Google. |
| `code_verifier` | `string` | Yes | The PKCE code verifier used during the initial authorization request. |
| `redirect_uri` | `string` | Yes | The redirect URI used during the initial authorization request. |

#### Example Request
```json
{
  "code": "string_value",
  "code_verifier": "string_value",
  "redirect_uri": "string_value"
}
```

### Responses
- **200**: Successfully logged in via Google.
- **400**: Google authentication failed or returned no email.
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (400)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## POST /v1/auth/logout
**Logout user**

Revokes the refresh token family and deletes the refresh token cookie.

**Authentication:** None

### Responses
- **200**: Successfully logged out.
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## GET /v1/projects/
**List Projects**

No description provided.

**Authentication:** HTTPBearer, APIKeyHeader

### Responses
- **200**: Successful Response

#### Example Success Response
```json
[
  {
    "id": "example_id"
  }
]
```

---

## POST /v1/projects/
**Create Project**

No description provided.

**Authentication:** HTTPBearer, APIKeyHeader

### Request Body
| Field | Type | Required | Description |
|---|---|---|---|
| `domain` | `string` | Yes | The root domain of the project (e.g., example.com). |
| `name` | `string` | Yes | The display name of the project. |
| `industry` | `string` | No | The industry category for this project. |
| `gsc_connected` | `boolean` | No | Whether Google Search Console is connected. |

#### Example Request
```json
{
  "domain": "string_value",
  "name": "string_value",
  "industry": "string_value",
  "gsc_connected": true
}
```

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{
  "domain": "example_string",
  "name": "example_string",
  "industry": "example_string",
  "gsc_connected": true,
  "id": "example_string",
  "org_id": "example_string",
  "created_at": "example_string"
}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## GET /v1/projects/{project_id}
**Get Project**

No description provided.

**Authentication:** HTTPBearer, APIKeyHeader

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{
  "domain": "example_string",
  "name": "example_string",
  "industry": "example_string",
  "gsc_connected": true,
  "id": "example_string",
  "org_id": "example_string",
  "created_at": "example_string"
}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## DELETE /v1/projects/{project_id}
**Delete Project**

No description provided.

**Authentication:** HTTPBearer, APIKeyHeader

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## POST /v1/projects/{project_id}/gsc/connect
**Connect Gsc**

No description provided.

**Authentication:** HTTPBearer, APIKeyHeader

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{
  "url": "example_string"
}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## POST /v1/projects/gsc/callback
**Gsc Callback**

No description provided.

**Authentication:** HTTPBearer

### Request Body
| Field | Type | Required | Description |
|---|---|---|---|
| `code` | `string` | Yes |  |
| `state` | `string` | Yes |  |
| `redirect_uri` | `string` | Yes |  |

#### Example Request
```json
{
  "code": "string_value",
  "state": "string_value",
  "redirect_uri": "string_value"
}
```

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## POST /v1/projects/{project_id}/ga4/connect
**Connect Ga4**

No description provided.

**Authentication:** HTTPBearer, APIKeyHeader

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## POST /v1/projects/ga4/callback
**Ga4 Callback**

No description provided.

**Authentication:** HTTPBearer

### Request Body
| Field | Type | Required | Description |
|---|---|---|---|
| `code` | `string` | Yes |  |
| `state` | `string` | Yes |  |
| `redirect_uri` | `string` | Yes |  |

#### Example Request
```json
{
  "code": "string_value",
  "state": "string_value",
  "redirect_uri": "string_value"
}
```

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## POST /v1/projects/{project_id}/gbp/connect
**Connect Gbp**

No description provided.

**Authentication:** HTTPBearer, APIKeyHeader

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## POST /v1/projects/gbp/callback
**Gbp Callback**

No description provided.

**Authentication:** HTTPBearer

### Request Body
| Field | Type | Required | Description |
|---|---|---|---|
| `code` | `string` | Yes |  |
| `state` | `string` | Yes |  |
| `redirect_uri` | `string` | Yes |  |

#### Example Request
```json
{
  "code": "string_value",
  "state": "string_value",
  "redirect_uri": "string_value"
}
```

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## POST /v1/projects/{project_id}/audits
**Create Audit**

No description provided.

**Authentication:** HTTPBearer

### Responses
- **202**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## GET /v1/audits/{audit_id}
**Get Audit**

No description provided.

**Authentication:** HTTPBearer

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{
  "status": "example_string",
  "mode": "example_string",
  "page_limit": 100,
  "root_url": "example_string",
  "score": "example_string",
  "category_scores": "example_string",
  "started_at": "example_string",
  "finished_at": "example_string",
  "error": "example_string",
  "id": "example_string",
  "project_id": "example_string",
  "created_by": "example_string"
}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## GET /v1/audits/{audit_id}/findings
**Get Findings**

No description provided.

**Authentication:** HTTPBearer

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
[
  {
    "id": "example_id"
  }
]
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## GET /v1/audits/{audit_id}/action-plan
**Get Action Plan**

No description provided.

**Authentication:** HTTPBearer

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## GET /v1/audits/{audit_id}/diff/{other_id}
**Get Audit Diff**

No description provided.

**Authentication:** HTTPBearer

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## GET /v1/audits/{audit_id}/pages
**Get Pages**

No description provided.

**Authentication:** HTTPBearer

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
[
  {
    "id": "example_id"
  }
]
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## GET /v1/audits/{audit_id}/events
**Sse Events**

No description provided.

**Authentication:** None

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## POST /v1/audits/{audit_id}/report
**Request Report**

No description provided.

**Authentication:** HTTPBearer

### Responses
- **202**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## GET /v1/reports/{audit_id}
**Get Report**

No description provided.

**Authentication:** HTTPBearer

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## GET /v1/audits/{audit_id}/export.csv
**Export Csv**

No description provided.

**Authentication:** HTTPBearer

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## POST /v1/projects/{project_id}/keywords/discover
**Discover Keywords**

No description provided.

**Authentication:** HTTPBearer

### Request Body
| Field | Type | Required | Description |
|---|---|---|---|
| `seed` | `string` | No |  |
| `url` | `string` | No |  |
| `country` | `string` | No |  |
| `language` | `string` | No |  |
| `keyword_set_name` | `string` | No |  |

#### Example Request
```json
{
  "seed": "string_value",
  "url": "string_value",
  "country": "string_value",
  "language": "string_value",
  "keyword_set_name": "string_value"
}
```

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## POST /v1/projects/{project_id}/keywords/gap
**Keyword Gap Analysis**

No description provided.

**Authentication:** HTTPBearer

### Request Body
| Field | Type | Required | Description |
|---|---|---|---|
| `competitors` | `array` | Yes | Max 3 competitors |
| `country` | `string` | No |  |
| `language` | `string` | No |  |
| `keyword_set_name` | `string` | No |  |

#### Example Request
```json
{
  "competitors": {},
  "country": "string_value",
  "language": "string_value",
  "keyword_set_name": "string_value"
}
```

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## GET /v1/keyword-sets/{set_id}
**Get Keyword Set**

No description provided.

**Authentication:** HTTPBearer

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## POST /v1/keywords/{keyword_id}/serp
**Fetch Keyword Serp**

No description provided.

**Authentication:** HTTPBearer

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## POST /v1/projects/{project_id}/tracking
**Register Tracking**

No description provided.

**Authentication:** HTTPBearer

### Request Body
| Field | Type | Required | Description |
|---|---|---|---|
| `keyword_ids` | `array` | Yes |  |
| `schedule` | `string` | Yes |  |

#### Example Request
```json
{
  "keyword_ids": {},
  "schedule": "string_value"
}
```

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## GET /v1/projects/{project_id}/tracking/trends
**Get Tracking Trends**

No description provided.

**Authentication:** HTTPBearer

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## GET /v1/projects/{project_id}/keywords/export.csv
**Export Keywords Csv**

No description provided.

**Authentication:** HTTPBearer

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## POST /v1/organizations/{org_id}/credits/top-up
**Top Up Credits**

No description provided.

**Authentication:** HTTPBearer

### Request Body
| Field | Type | Required | Description |
|---|---|---|---|
| `amount` | `integer` | Yes | Amount of credits to add |
| `reason` | `string` | Yes |  |

#### Example Request
```json
{
  "amount": 123,
  "reason": "string_value"
}
```

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## POST /v1/projects/{project_id}/baselines
**Create Baselines**

No description provided.

**Authentication:** HTTPBearer

### Request Body
| Field | Type | Required | Description |
|---|---|---|---|
| `urls` | `array` | Yes |  |

#### Example Request
```json
{
  "urls": {}
}
```

### Responses
- **202**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## GET /v1/projects/{project_id}/drift
**Get Drift Events**

No description provided.

**Authentication:** HTTPBearer

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## POST /v1/projects/{project_id}/drift/{event_id}/acknowledge
**Acknowledge Drift Event**

No description provided.

**Authentication:** HTTPBearer

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## POST /v1/audits/{audit_id}/share
**Generate Share Token**

No description provided.

**Authentication:** HTTPBearer, APIKeyHeader

### Request Body
| Field | Type | Required | Description |
|---|---|---|---|
| `expires_in_days` | `string` | No |  |

#### Example Request
```json
{
  "expires_in_days": "string_value"
}
```

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## POST /v1/audits/{audit_id}/share/{token_id}/revoke
**Revoke Share Token**

No description provided.

**Authentication:** HTTPBearer, APIKeyHeader

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## GET /v1/shared/{token}
**Get Shared Report**

No description provided.

**Authentication:** None

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## PUT /v1/organizations/{org_id}/theme
**Update Theme**

No description provided.

**Authentication:** HTTPBearer, APIKeyHeader

### Request Body
| Field | Type | Required | Description |
|---|---|---|---|
| `theme_primary_color` | `string` | No |  |
| `theme_accent_color` | `string` | No |  |
| `theme_agency_name` | `string` | No |  |

#### Example Request
```json
{
  "theme_primary_color": "string_value",
  "theme_accent_color": "string_value",
  "theme_agency_name": "string_value"
}
```

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{
  "theme_logo_url": "example_string",
  "theme_primary_color": "example_string",
  "theme_accent_color": "example_string",
  "theme_agency_name": "example_string"
}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## POST /v1/organizations/{org_id}/logo
**Upload Logo**

No description provided.

**Authentication:** HTTPBearer, APIKeyHeader

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{
  "theme_logo_url": "example_string",
  "theme_primary_color": "example_string",
  "theme_accent_color": "example_string",
  "theme_agency_name": "example_string"
}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## POST /v1/organizations/{org_id}/api-keys
**Create Api Key**

No description provided.

**Authentication:** HTTPBearer, APIKeyHeader

### Request Body
| Field | Type | Required | Description |
|---|---|---|---|
| `name` | `string` | Yes |  |

#### Example Request
```json
{
  "name": "string_value"
}
```

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{
  "id": "example_string",
  "prefix": "example_string",
  "name": "example_string",
  "last_used_at": "example_string",
  "secret_key": "example_string"
}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## GET /v1/organizations/{org_id}/api-keys
**List Api Keys**

No description provided.

**Authentication:** HTTPBearer, APIKeyHeader

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
[
  {
    "id": "example_id"
  }
]
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## DELETE /v1/organizations/{org_id}/api-keys/{key_id}
**Revoke Api Key**

No description provided.

**Authentication:** HTTPBearer, APIKeyHeader

### Responses
- **204**: Successful Response
- **422**: Validation Error

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## POST /v1/organizations/{org_id}/webhooks
**Create Webhook**

No description provided.

**Authentication:** HTTPBearer, APIKeyHeader

### Request Body
| Field | Type | Required | Description |
|---|---|---|---|
| `url` | `string` | Yes |  |
| `events` | `array` | Yes |  |

#### Example Request
```json
{
  "url": "string_value",
  "events": {}
}
```

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
{
  "id": "example_string",
  "url": "example_string",
  "secret": "example_string",
  "events": {},
  "is_active": true
}
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## GET /v1/organizations/{org_id}/webhooks
**List Webhooks**

No description provided.

**Authentication:** HTTPBearer, APIKeyHeader

### Responses
- **200**: Successful Response
- **422**: Validation Error

#### Example Success Response
```json
[
  {
    "id": "example_id"
  }
]
```

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## DELETE /v1/organizations/{org_id}/webhooks/{webhook_id}
**Delete Webhook**

No description provided.

**Authentication:** HTTPBearer, APIKeyHeader

### Responses
- **204**: Successful Response
- **422**: Validation Error

#### Example Error Response (422)
```json
{
  "detail": "Error description corresponding to the status code."
}
```

---

## Server-Sent Events (SSE)
`GET /v1/audits/{id}/events`
Streams live audit events.
### Event Types
- `crawl.progress`: Fired when pages are crawled. `{"url": "...", "status": 200}`
- `agent.started`: Fired when an AI agent starts. `{"agent": "..."}`
- `agent.completed`: Fired when an agent finishes. `{"agent": "..."}`
- `audit.done`: Fired when the audit is successfully completed.

## Webhook Payload & Verification
When a webhook is triggered, RankerPilot sends a POST request with the event payload.
### Example Payload
```json
{
  "event": "audit.completed",
  "audit_id": "123",
  "status": "done"
}
```
### Signature Verification (Python)
```python
import hmac, hashlib
signature = hmac.new(SECRET.encode('utf-8'), payload_bytes, hashlib.sha256).hexdigest()
if f'sha256={signature}' == request.headers.get('X-Rankerpilot-Signature'):
    print('Valid!')
```
