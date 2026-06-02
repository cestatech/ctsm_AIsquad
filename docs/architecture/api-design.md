# API Design — Celerius REST API v1

Base URL: `/api/v1`

All endpoints require `Authorization: Bearer {access_token}` unless noted.

Error responses follow: `{"detail": "...", "code": "ERROR_CODE", "field": "optional"}`

---

## Authentication

| Method | Path | Description | Auth Required | Roles |
|--------|------|-------------|---------------|-------|
| POST | `/auth/login` | Authenticate and receive tokens | No | — |
| POST | `/auth/refresh` | Rotate refresh token | Cookie only | — |
| POST | `/auth/logout` | Revoke refresh token | Yes | All |
| POST | `/auth/register` | Register organization + admin user | No | — |
| POST | `/auth/change-password` | Change own password | Yes | All |

### POST /auth/login
```json
// Request
{"email": "user@example.com", "password": "..."}

// Response 200
{"access_token": "eyJ...", "token_type": "bearer", "expires_in": 900}
// + Set-Cookie: refresh_token=...; HttpOnly; Secure; SameSite=Strict
```

---

## Users

| Method | Path | Description | Roles |
|--------|------|-------------|-------|
| GET | `/users/me` | Get current user profile | All |
| PUT | `/users/me` | Update own profile | All |
| GET | `/users` | List org users | Admin |
| POST | `/users` | Invite user to org | Admin |
| GET | `/users/{user_id}` | Get user detail | Admin |
| PUT | `/users/{user_id}` | Update user | Admin |
| DELETE | `/users/{user_id}` | Deactivate user | Admin |

---

## Organizations

| Method | Path | Description | Roles |
|--------|------|-------------|-------|
| GET | `/organizations/me` | Get own organization | All |
| PUT | `/organizations/me` | Update org settings | Admin |
| GET | `/organizations/me/members` | List org members | Admin |

---

## Studies

| Method | Path | Description | Roles |
|--------|------|-------------|-------|
| GET | `/studies` | List studies in org | All |
| POST | `/studies` | Create study | Admin |
| GET | `/studies/{study_id}` | Get study detail | Members |
| PUT | `/studies/{study_id}` | Update study | Admin |
| POST | `/studies/{study_id}/archive` | Archive study | Admin |
| GET | `/studies/{study_id}/members` | List study members | Members |
| POST | `/studies/{study_id}/members` | Add study member | Admin |
| PUT | `/studies/{study_id}/members/{user_id}` | Update member role | Admin |
| DELETE | `/studies/{study_id}/members/{user_id}` | Remove member | Admin |

---

## Artifacts

| Method | Path | Description | Roles |
|--------|------|-------------|-------|
| GET | `/studies/{study_id}/artifacts` | List artifacts | Members |
| POST | `/studies/{study_id}/artifacts` | Create artifact | Admin, Contributor |
| GET | `/artifacts/{artifact_id}` | Get artifact detail | Members |
| PUT | `/artifacts/{artifact_id}` | Update artifact content | Admin, Contributor |
| DELETE | `/artifacts/{artifact_id}` | Delete DRAFT artifact | Admin, Contributor (own) |

### Artifact Workflow

| Method | Path | Description | Roles |
|--------|------|-------------|-------|
| POST | `/artifacts/{artifact_id}/submit` | Submit for review | Admin, Contributor |
| POST | `/artifacts/{artifact_id}/approve` | Approve artifact | Admin, Reviewer |
| POST | `/artifacts/{artifact_id}/reject` | Reject artifact | Admin, Reviewer |
| POST | `/artifacts/{artifact_id}/lock` | Lock approved artifact | Admin |
| POST | `/artifacts/{artifact_id}/amend` | Begin amendment of locked | Admin |

### Artifact Versions

| Method | Path | Description | Roles |
|--------|------|-------------|-------|
| GET | `/artifacts/{artifact_id}/versions` | List version history | Members |
| GET | `/artifacts/{artifact_id}/versions/{version_id}` | Get specific version | Members |
| GET | `/artifacts/{artifact_id}/versions/compare` | Compare two versions | Members |

```
GET /artifacts/{id}/versions/compare?from=1&to=3
Response: {
  "from_version": {...},
  "to_version": {...},
  "diff": [{op, path, value, old_value}, ...]
}
```

---

## Approvals

| Method | Path | Description | Roles |
|--------|------|-------------|-------|
| GET | `/approvals` | List pending approvals for user | Reviewer, Admin |
| GET | `/artifacts/{artifact_id}/approvals` | Approval history | Members |

---

## Comments

| Method | Path | Description | Roles |
|--------|------|-------------|-------|
| GET | `/artifacts/{artifact_id}/comments` | List comments | Members |
| POST | `/artifacts/{artifact_id}/comments` | Add comment | Members |
| PUT | `/comments/{comment_id}` | Edit own comment | Author |
| DELETE | `/comments/{comment_id}` | Soft-delete own comment | Author, Admin |
| POST | `/comments/{comment_id}/resolve` | Resolve comment | Admin, Reviewer |

---

## Audit

| Method | Path | Description | Roles |
|--------|------|-------------|-------|
| GET | `/audit` | Search org audit log | Admin, Reviewer |
| GET | `/audit/{log_id}` | Get audit entry detail | Admin, Reviewer |
| POST | `/audit/export` | Export audit log (async) | Admin |

### Query Parameters for GET /audit
```
?action=artifact.approved
&resource_type=artifact
&resource_id={uuid}
&actor_user_id={uuid}
&from_date=2024-01-01
&to_date=2024-12-31
&page=1
&page_size=25
```

---

## Validation

| Method | Path | Description | Roles |
|--------|------|-------------|-------|
| POST | `/artifacts/{artifact_id}/validate` | Trigger validation run | All |
| GET | `/artifacts/{artifact_id}/validations` | List validation runs | All |
| GET | `/validation/runs/{run_id}` | Get run detail | All |

---

## AI Generation

| Method | Path | Description | Roles |
|--------|------|-------------|-------|
| POST | `/generation/jobs` | Trigger generation job | Admin, Contributor |
| GET | `/generation/jobs/{job_id}` | Poll job status | Admin, Contributor |
| DELETE | `/generation/jobs/{job_id}` | Cancel pending job | Admin, Contributor |
| GET | `/studies/{study_id}/generation/jobs` | List study jobs | Admin, Contributor |

### POST /generation/jobs
```json
{
  "study_id": "uuid",
  "artifact_type": "PROTOCOL",
  "config": {
    "model_id": "claude-opus-4-7",
    "template_id": "protocol_v1",
    "context_overrides": {}
  }
}
```

---

## Traceability

| Method | Path | Description | Roles |
|--------|------|-------------|-------|
| GET | `/studies/{study_id}/traceability` | Get traceability matrix | All |
| POST | `/studies/{study_id}/traceability/links` | Create link | Admin, Contributor |
| DELETE | `/traceability/links/{link_id}` | Delete link | Admin |

---

## Response Envelope

Paginated list responses:
```json
{
  "items": [...],
  "total": 142,
  "page": 1,
  "page_size": 25,
  "has_next": true,
  "has_prev": false
}
```

Single resource responses: the resource object directly.

---

## HTTP Status Codes Used

| Code | Meaning |
|------|---------|
| 200 | Success (GET, PUT, PATCH) |
| 201 | Created (POST creating a resource) |
| 204 | No Content (DELETE) |
| 400 | Bad Request (business validation error) |
| 401 | Unauthenticated (no or invalid token) |
| 403 | Forbidden (insufficient role) |
| 404 | Not Found (or IDOR protection) |
| 409 | Conflict (workflow error, locked artifact) |
| 422 | Unprocessable Entity (Pydantic validation) |
| 429 | Too Many Requests (rate limit) |
| 500 | Internal Server Error (unexpected) |
