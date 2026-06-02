# Architecture Overview — Celerius Clinical Trial Lifecycle Platform

## System Context

Celerius is a multi-tenant SaaS platform serving clinical operations teams at pharmaceutical and biotech companies. Users include Clinical Data Managers, Biostatisticians, Regulatory Affairs Specialists, Principal Investigators, and Site Monitors.

The platform manages the complete lifecycle of clinical trial artifacts, from protocol design through regulatory submission. All artifacts must be permanently auditable, version-controlled, and reproducible for regulatory inspection.

---

## Architectural Principles

1. **Multi-tenancy at every layer.** Organization isolation is enforced at DB, API, auth, and storage layers — not just a soft filter.
2. **Three-layer backend.** Route → Service → Repository. No layer skips.
3. **Audit-first design.** Every state change logs to an immutable audit trail before returning.
4. **Append-only for regulatory records.** `audit_logs` and `artifact_versions` are never updated or deleted.
5. **JWT-scoped tenancy.** `organization_id` always comes from the verified JWT, never from request data.
6. **AI as draft creator only.** All AI-generated content enters as DRAFT. Human approval is mandatory.

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           User's Browser                                  │
│                    Next.js 14 (App Router, TypeScript)                   │
│   Server Components → Data Fetching                                       │
│   Client Components → Interactive UI (forms, modals, real-time)          │
│   TanStack Query → API state management                                   │
│   Zustand → Auth session, UI state                                        │
└─────────────────────────────┬────────────────────────────────────────────┘
                              │ HTTPS / REST
                    ┌─────────▼─────────┐
                    │   Nginx Proxy     │
                    │  (TLS, headers,   │
                    │   static assets)  │
                    └────────┬──────────┘
                             │
                   ┌─────────▼──────────┐
                   │   FastAPI Backend  │
                   │   (Python 3.12)    │
                   │                   │
                   │  ┌─────────────┐  │
                   │  │ JWT Auth    │  │
                   │  │ Middleware  │  │
                   │  └──────┬──────┘  │
                   │         │         │
                   │  ┌──────▼──────┐  │
                   │  │  API v1     │  │  /api/v1/{resource}
                   │  │  Endpoints  │  │
                   │  └──────┬──────┘  │
                   │         │         │
                   │  ┌──────▼──────┐  │
                   │  │  Services   │  │  RBAC + Business Logic
                   │  └──────┬──────┘  │
                   │         │         │
                   │  ┌──────▼──────┐  │
                   │  │ Repositories│  │  SQLAlchemy Async
                   │  └──────┬──────┘  │
                   └─────────┼─────────┘
                             │
              ┌──────────────┼─────────────────┐
              │              │                 │
    ┌─────────▼──────┐  ┌────▼────┐  ┌─────────▼──────┐
    │  PostgreSQL 16 │  │  Redis  │  │ Object Storage │
    │ (Primary DB)   │  │ (Cache, │  │ (S3 / Azure /  │
    │                │  │  Rate   │  │  Filesystem)   │
    │  Per-org data  │  │ Limit)  │  │                │
    └────────────────┘  └─────────┘  └────────────────┘
```

---

## Backend Layer Detail

### Route Layer (`api/v1/endpoints/`)

- Thin handlers: parse HTTP, call one service method, return response
- Declare dependencies (auth, db session) via FastAPI `Depends()`
- No business logic
- No direct database access

### Service Layer (`services/`)

- All business logic lives here
- `check_permission(user, permission)` called FIRST in every mutating method
- Calls `audit_service.log(...)` for every state change
- Calls repository methods for database access
- One service class per domain (ArtifactService, StudyService, etc.)

### Repository Layer (`repositories/`)

- All SQLAlchemy queries here
- Every query filters by `organization_id` (tenant isolation)
- Returns ORM model instances
- No business logic
- Returns HTTP 404 for missing records (protects against IDOR)

---

## Database Architecture

PostgreSQL 16 with:
- UUID primary keys everywhere (no sequential integer IDs exposed to clients)
- `organization_id` on every tenant-scoped table
- Composite indexes on `(organization_id, created_at DESC)` for all paginated queries
- Append-only tables for audit_logs and artifact_versions (DB triggers block UPDATE/DELETE)
- Soft delete via `deleted_at` timestamp (not boolean flags)
- JSONB for flexible metadata and state snapshots

See `docs/architecture/database.md` for full schema detail.

---

## Authentication Architecture

```
Client                    Backend
  │                          │
  │  POST /auth/login         │
  │  { email, password }      │
  ├─────────────────────────→│
  │                          │ verify password
  │                          │ create access_token (15 min)
  │                          │ create refresh_token (7 days)
  │                          │ store refresh_token hash in DB
  │  { access_token }         │
  │  Set-Cookie: refresh=...  │
  │←─────────────────────────┤
  │                          │
  │  GET /studies             │
  │  Authorization: Bearer {at}│
  ├─────────────────────────→│
  │                          │ decode JWT
  │                          │ validate org claim vs DB
  │                          │ check user is_active
  │  [studies list]          │
  │←─────────────────────────┤
  │                          │
  │  (access token expires)  │
  │  POST /auth/refresh       │
  │  Cookie: refresh={rt}    │
  ├─────────────────────────→│
  │                          │ hash RT, lookup in DB
  │                          │ verify not expired/revoked
  │                          │ rotate: revoke old, issue new RT
  │                          │ issue new access_token
  │  { access_token }        │
  │  Set-Cookie: refresh=... │
  │←─────────────────────────┤
```

---

## Multi-Tenancy Model

Every API request is tenant-scoped by the following chain:

1. Bearer token decoded → `organization_id` extracted
2. User fetched from DB, filtered by `(user_id, organization_id)` — prevents token forgery
3. `current_user.organization_id` passed to all service methods
4. Service passes `organization_id` to all repository methods
5. Repository includes `WHERE organization_id = ?` on every query
6. Storage operations prefix paths with `org/{organization_id}/`

**The client cannot influence the organization context.** URL params like `/organizations/{org_id}/` are validated against the JWT org. If they don't match, the request returns 403.

---

## Artifact Version Architecture

```
Artifact (current pointer)
│
├── current_version_id → ArtifactVersion 3 (is_current=True)
│
├── ArtifactVersion 1  (is_current=False)
│   content: {full snapshot}
│   content_hash: sha256(content)
│   content_diff: null  (first version)
│   status_at_creation: DRAFT
│
├── ArtifactVersion 2  (is_current=False)
│   content: {full snapshot}
│   content_hash: sha256(content)
│   content_diff: [{op: "replace", path: "/section/1", value: "..."}]
│   status_at_creation: REJECTED
│
└── ArtifactVersion 3  (is_current=True)
    content: {full snapshot}
    content_hash: sha256(content)
    content_diff: [{op: "add", path: "/section/4", value: "..."}]
    status_at_creation: DRAFT
```

- Versions are numbered sequentially, never reset
- Full content snapshot always stored (not just diff)
- Diff stored additionally for efficient comparison UI
- `is_current` flag updated on each new version (the only permitted update to this table)
- DB trigger blocks all other UPDATE and DELETE operations

---

## AI Generation Architecture (Future)

```
User triggers generation
      │
      ▼
POST /api/v1/generation/jobs
{artifact_type: "PROTOCOL", study_id: "...", config: {...}}
      │
      ▼
GenerationJob created (status=PENDING)
AuditLog: ai.generation_started
      │
      ▼
Background worker picks up job
Context assembled from study metadata + upstream artifacts
Prompt template loaded by template_id + template_hash
      │
      ▼
LLM API called (Anthropic / configured provider)
      │
      ├── Success
      │    ▼
      │   Artifact created (status=DRAFT)
      │   ArtifactVersion 1 created
      │   GenerationJob.status = COMPLETED
      │   AuditLog: ai.generation_completed
      │
      └── Failure
           ▼
          GenerationJob.status = FAILED
          AuditLog: ai.generation_failed

AI-generated artifacts ALWAYS enter as DRAFT.
They require human review and explicit approval.
They are NEVER automatically approved.
```

---

## Storage Architecture

```python
# Abstract interface — all storage operations go through this
class StorageBackend(ABC):
    async def put(self, key: str, data: bytes, content_type: str) -> str: ...
    async def get(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None: ...
    async def get_presigned_url(self, key: str, expires: int) -> str: ...

# Key format: org/{org_id}/studies/{study_id}/artifacts/{artifact_id}/v{n}/{filename}
```

Backends: `FilesystemStorage` (dev), `S3Storage` (production), `AzureBlobStorage` (enterprise).

---

## Frontend Architecture

```
app/
├── (auth)/              # Unauthenticated routes (no layout wrapper)
│   ├── login/
│   └── register/
│
└── (dashboard)/         # Authenticated routes (shared dashboard layout)
    ├── layout.tsx        # Sidebar nav, topbar, auth check
    ├── page.tsx          # Dashboard home
    │
    ├── studies/
    │   ├── page.tsx      # Study list
    │   └── [studyId]/
    │       ├── page.tsx          # Study overview
    │       ├── artifacts/
    │       │   ├── page.tsx      # Artifact list
    │       │   ├── create/       # New artifact form
    │       │   └── [artifactId]/ # Artifact detail + versioning
    │       ├── approvals/        # Pending review queue
    │       ├── audit/            # Study audit log
    │       └── members/          # Team management
    │
    ├── approvals/        # Organization-wide pending reviews (Reviewer view)
    ├── audit/            # Organization-wide audit log (Admin/Reviewer)
    └── admin/            # Admin-only
        ├── users/
        └── organizations/
```

Server Components fetch data directly; Client Components handle interactivity. Navigation menu items are rendered conditionally based on `usePermissions()`.
