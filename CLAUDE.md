# CLAUDE.md — Celerius Clinical Trial Lifecycle Platform

This file governs how AI agents and human developers interact with this codebase. Read it fully before making any changes.

---

## Project Purpose

Celerius is an AI-native, multi-tenant SaaS platform for managing the complete clinical trial lifecycle. It is designed for eventual FDA, EMA, GxP, and 21 CFR Part 11 compliance. Every design decision must favor auditability, traceability, security, and regulatory readiness over development convenience.

This is not a typical web application. Mistakes in this codebase can affect patient safety, data integrity, and regulatory submissions.

---

## Engineering Principles

1. **Auditability first.** Every significant action — create, update, status change, approval, deletion — must generate an immutable audit record. If you are writing an action that modifies data and you are not also writing an audit log entry, stop and add it.

2. **Explicitness over cleverness.** Prefer verbose, obvious code over compact abstractions. A reviewer must be able to verify correctness without deep framework knowledge.

3. **Security by default.** RBAC checks happen in the service layer, not just route decorators. Tenant isolation is enforced at every database query. Never trust client-supplied tenant context.

4. **Reproducibility.** Every artifact version must be permanently storable and retrievable. Nothing is ever truly deleted — records are soft-deleted and preserved in audit history.

5. **Traceability.** The chain Objective → Endpoint → eCRF → SDTM → ADaM → TLF → CSR must remain intact at all times. Traceability links are first-class records, not derived views.

6. **Fail loudly.** Prefer explicit errors over silent fallbacks. A missing permission should raise a 403, not silently return an empty list.

---

## Celerius Intelligence Platform (CIP) — Core USP

The CIP layer is **the primary differentiator** of this platform. It makes every AI action, data transformation, and mapping decision explainable, auditable, and defensible to regulators. It is not optional infrastructure — it is the product.

The full intelligence chain:

```
ContextGraphService  ←  registers every entity as a graph node
AIDecisionService    ←  logs every AI inference before it executes
HumanOverrideService ←  records every human correction immutably
DataLineageService   ←  traces field-level and artifact-level provenance
ValidationIntelligenceService ← stores per-rule CDISC evidence
```

### Mandatory CIP Compliance Rules

**Every AI agent that generates, derives, or maps clinical data MUST:**

1. **Log the decision before acting.**
   Call `AIDecisionService.begin_decision()` before executing any AI inference.
   Call `complete_decision()` with the output after. Never silently execute AI work.

2. **Register entities in the Context Graph.**
   Any new clinical entity (objective, endpoint, ECR field, SDTM variable, ADaM variable, TLF, CSR section) must be registered via `ContextGraphService.register_domain_record()` before use.

3. **Link entities in the Context Graph.**
   Any relationship established (e.g., mapping an ECR field to a SDTM variable) must be recorded via `ContextGraphService.create_relationship()` or a named shortcut (`link_ecr_to_sdtm()`, etc.) with `is_ai_generated=True` and `ai_decision_id` populated.

4. **Record field-level lineage.**
   Any data transformation (ECR → SDTM, SDTM → ADaM, ADaM → TLF) must produce a `DataLineage` record via `DataLineageService.record_field_lineage()` with the transformation logic stored as code or a formula string.

5. **Expose AI outputs as PENDING_REVIEW.**
   All AI-generated values surface in the frontend at `/intelligence/decisions` with status `PENDING_REVIEW` until a Reviewer or Admin accepts or rejects them. Accepted AI outputs can be used; rejected outputs must not flow downstream.

6. **Capture human corrections as overrides.**
   If a user edits any AI-generated value, the frontend must call `POST /api/v1/intelligence/overrides` with `original_value`, `new_value`, and a mandatory `reason`. This is enforced in the UI and must not be skipped.

### CIP Service Entry Points

| Service | File | Use for |
|---------|------|---------|
| `ContextGraphService` | `services/context_graph_service.py` | Register nodes, create edges, query lineage path |
| `AIDecisionService` | `services/intelligence_service.py` | Log AI decisions, review lifecycle |
| `HumanOverrideService` | `services/intelligence_service.py` | Record human corrections |
| `DataLineageService` | `services/intelligence_service.py` | Field-level and artifact-level lineage |
| `ValidationIntelligenceService` | `services/intelligence_service.py` | CDISC rule evidence, waivers |

### CIP Frontend Screens

All CIP data surfaces at `/intelligence/*`. These screens are the primary interface for human oversight of AI:

- `/intelligence/decisions` — review queue; Reviewers and Admins accept/reject AI work here
- `/intelligence/overrides` — immutable correction log
- `/intelligence/graph` — context graph node/edge browser
- `/intelligence/traceability` — full Objective→CSR chain with gap detection
- `/intelligence/lineage` — upstream/downstream lineage explorer
- `/intelligence/validation` — CDISC conformance findings; waiver workflow
- `/intelligence/synthetic` — synthetic data run log

### CIP Invariants (never violate)

- `AIDecision` records are append-only. No update or delete.
- `HumanOverride` records are append-only. No update or delete.
- `DataLineage` records are append-only. No update or delete.
- `GraphEvent` records are append-only. No update or delete.
- A `HumanOverride` with an empty `reason` must be rejected at the service layer (HTTP 422).
- An AI decision rejection with an empty `notes` must be rejected at the service layer (HTTP 422).
- Synthetic data output is always labeled `SYNTHETIC`. It must never be submitted to regulators as real data.
- Every `SyntheticDataRun` must have a `random_seed` for reproducibility.

---

## Architecture Rules

### Multi-Tenancy
- **Every** database model that contains tenant data MUST have an `organization_id` foreign key.
- **Every** database query MUST filter by `organization_id` from the authenticated user's JWT claim.
- The `organization_id` used in queries must ALWAYS come from the verified JWT token — never from a request body or URL parameter.
- Cross-tenant data access is forbidden. There are no "global" views of tenant data except for System Admin operations, which must be explicitly flagged.

### Service Layer
- All business logic lives in `backend/app/services/`.
- Route handlers (`api/v1/endpoints/`) must only call service methods — no direct database access from routes.
- Services call repositories. Repositories call the database.
- This three-layer architecture (Route → Service → Repository) is mandatory.

### Database Access
- All database access goes through repository classes in `backend/app/repositories/`.
- Raw SQL is allowed only in migration files and complex reporting queries. Use SQLAlchemy ORM for all application code.
- All queries must use async SQLAlchemy sessions.

### API Versioning
- All API endpoints live under `/api/v1/`. Future versions will be `/api/v2/` etc.
- Never modify existing endpoint response schemas in a breaking way. Add fields; never remove or rename.
- Deprecation must be documented in the endpoint's docstring before removal.

### Error Handling
- Use structured error responses: `{"detail": "...", "code": "ERROR_CODE", "field": "optional"}`.
- HTTP status codes must be semantically correct (401 for unauthenticated, 403 for forbidden, 422 for validation).
- Never return stack traces to clients in production. Log them server-side.

---

## RBAC Rules

The three roles are **Admin**, **Contributor**, and **Reviewer**. These are fixed — do not add new roles without explicit architecture review.

### Permission Enforcement
- RBAC is checked in service methods using the `PermissionChecker` utility.
- Permission checks must occur BEFORE any data modification begins.
- Role checks must ALWAYS verify the user's role within the specific `organization_id` from the JWT — not a global role.

### What Each Role Can Do

| Action | Admin | Contributor | Reviewer |
|--------|-------|-------------|----------|
| Create artifact | ✓ | ✓ | ✗ |
| Edit DRAFT artifact | ✓ | ✓ | ✗ |
| Submit for review | ✓ | ✓ | ✗ |
| Approve/Reject | ✓ | ✗ | ✓ |
| Lock artifact | ✓ | ✗ | ✗ |
| Amend LOCKED artifact | ✓ | ✗ | ✗ |
| Delete DRAFT artifact | ✓ | ✓ (own) | ✗ |
| Delete APPROVED/LOCKED | ✗ | ✗ | ✗ |
| Manage users | ✓ | ✗ | ✗ |
| View audit logs | ✓ | ✗ | ✓ |
| Run validations | ✓ | ✓ | ✓ |

### Escalation Rule
Any code that modifies RBAC logic, permission checks, or token validation MUST be reviewed by `rbac-agent` and `architect-agent` before merge.

---

## Artifact Lifecycle Rules

### Status Transitions (enforced in `ArtifactService`)

```
DRAFT         → IN_REVIEW    (Contributor or Admin: submit_for_review)
IN_REVIEW     → APPROVED     (Reviewer or Admin: approve)
IN_REVIEW     → REJECTED     (Reviewer or Admin: reject)
REJECTED      → DRAFT        (Contributor or Admin: revise)
APPROVED      → LOCKED       (Admin only: lock)
LOCKED        → AMENDED      (Admin only: amend — creates new DRAFT version)
APPROVED/LOCKED → SUPERSEDED (system: when newer version is approved)
```

- Every transition that is not in this list is **forbidden** and must raise a `WorkflowError`.
- Every transition creates an `ArtifactVersion` record and an `AuditLog` record.
- A `LOCKED` artifact's content fields are immutable. The database trigger and service layer both enforce this.
- `SUPERSEDED` artifacts are read-only and preserved for regulatory history.

### Versioning
- Every content change to an artifact creates a new `ArtifactVersion` record.
- `ArtifactVersion` records are append-only. They are never updated or deleted.
- Version numbers are sequential integers within an artifact. They never reset.
- The `artifact.current_version_id` points to the latest version.

---

## Audit Logging Requirements

**Non-negotiable:** Every one of the following actions MUST produce an `AuditLog` record before the operation returns to the caller:

- User login, logout, failed login
- User created, deactivated
- Study created, updated, archived
- Artifact created, updated, status changed
- Artifact version created
- Approval created (approve or reject action)
- Comment created, updated, deleted
- User role changed
- Organization settings changed
- Validation run executed
- Any admin action on another user

### AuditLog Schema (mandatory fields)
- `id` — UUID
- `organization_id` — tenant scope
- `actor_user_id` — who performed the action
- `action` — enum (see `AuditAction`)
- `resource_type` — e.g., "artifact", "study", "user"
- `resource_id` — UUID of the affected record
- `before_state` — JSONB snapshot before change (nullable)
- `after_state` — JSONB snapshot after change (nullable)
- `ip_address` — client IP (from request headers, respecting proxies)
- `user_agent` — browser/client user agent
- `created_at` — timestamp, set by database default (NOT by application code)

### Audit Log Integrity
- Audit logs are append-only. There is no update or delete endpoint for audit records.
- The database role used by the application has `INSERT` only on `audit_logs`. No `UPDATE` or `DELETE`.
- Audit log reads require Admin or Reviewer role and are scoped to the user's organization.

---

## Versioning Rules

- SQLAlchemy models that represent versioned artifacts inherit from `VersionedMixin`.
- On `UPDATE` of any content field, the service must call `create_version_snapshot()` before writing.
- The `diff` between versions is computed and stored in `artifact_versions.content_diff` (JSON Patch format).
- Version comparison UI shows a structured diff. Raw JSON diff is always available.
- Rollback creates a new version (not a revert to old version_id). The history remains linear.

---

## Multi-Tenant Requirements

- Do not create any endpoint that returns data across multiple organizations without an explicit System Admin check.
- The `get_current_user` dependency always returns a user with a validated `organization_id`. This value is the source of truth for all tenant filtering.
- Organization IDs in URLs (`/organizations/{org_id}/`) must be validated against the JWT's `organization_id`.
- Storage paths must be prefixed with `org/{organization_id}/` at all times.

---

## Security Requirements

### Authentication
- JWT access tokens expire in 15 minutes.
- Refresh tokens are stored in httpOnly, Secure, SameSite=Strict cookies.
- Refresh tokens are one-time use (rotation on refresh).
- Failed login attempts are rate-limited (5 attempts per 15 minutes per IP).
- Passwords are hashed with bcrypt, minimum cost factor 12.

### Input Validation
- All inputs are validated with Pydantic v2 models at the API boundary.
- File uploads validate MIME type and size before processing.
- SQL injection is prevented by using ORM parameterized queries exclusively.

### Secrets
- No secrets in source code. Use environment variables exclusively.
- No secrets in git history. Use `.env.example` with placeholder values only.
- The `backend/app/core/config.py` reads from environment variables via Pydantic `BaseSettings`.

### Headers
- CORS is configured explicitly — no wildcard `*` origins in production.
- Security headers (CSP, HSTS, X-Frame-Options) are set by Nginx, not the application.

---

## Agent System Rules

### Governance Model

This repository operates with a team of specialized AI agents. Each agent has a defined domain, allowed directories, and escalation path.

**For any change involving:**
- Authentication or token handling
- Authorization or RBAC checks
- Multi-tenancy isolation
- Audit log schema or ingestion
- Artifact versioning logic
- Approval workflow transitions

The change **must be reviewed** by all three of:
1. `architect-agent`
2. `rbac-agent`
3. `audit-compliance-agent`

before it is accepted.

### Agent Boundaries
- `backend-agent` owns `backend/app/`. It does not modify frontend code.
- `frontend-agent` owns `frontend/src/`. It does not modify backend code.
- `database-agent` owns `backend/alembic/`, `database/`. It does not modify application logic.
- `rbac-agent` audits any change to `core/permissions.py`, `core/security.py`, `api/deps.py`, and all service-layer permission checks.
- `audit-compliance-agent` audits any change to `models/audit.py`, `services/audit_service.py`, and all audit log call sites.
- `architect-agent` has authority over all directories and can override decisions from other agents.

### Agent Communication Protocol
- Agents document decisions in `docs/decisions/` as Architecture Decision Records (ADRs).
- When an agent identifies a cross-cutting concern, it must create an ADR before modifying code.
- Agents must not bypass the review requirement for governance-scoped changes.

---

## Coding Standards

### Python (Backend)
- Python 3.12+. Use type hints on all function signatures.
- Async-first: all service and repository methods are `async def`.
- Use `from __future__ import annotations` for forward references.
- PEP 8 compliance enforced by `ruff`.
- No bare `except:` clauses. Catch specific exceptions.
- Imports: stdlib → third-party → local, separated by blank lines.
- Maximum line length: 100 characters.
- All public functions and classes must have docstrings.

### TypeScript (Frontend)
- Strict mode enabled (`"strict": true` in `tsconfig.json`).
- No `any` types. Use `unknown` and narrow with type guards.
- React components are function components only. No class components.
- Server Components by default; use `"use client"` only when necessary.
- All API calls go through the typed client in `lib/api/`.
- No inline styles. Use Tailwind classes exclusively.
- Component props typed with interfaces, not `type`.

### Database (Migrations)
- Every schema change requires an Alembic migration.
- Migrations must be reversible (include `downgrade()` function).
- No destructive migrations (column drops, table drops) without an explicit approval in the PR.
- Migration file names must be descriptive: `alembic revision -m "add_artifact_version_diff_column"`.
- Never modify existing migration files. Create new ones.

### Testing
- New service methods require unit tests in `backend/tests/unit/`.
- New API endpoints require integration tests in `backend/tests/integration/`.
- RBAC rules require explicit tests asserting that unauthorized roles receive 403.
- Audit log generation requires tests asserting that audit records are created.
- Frontend component tests required for all form submissions and approval flows.
- E2E tests required for all role-based navigation and workflow paths.

---

## Documentation Standards

- All new public API endpoints must have docstrings that become OpenAPI descriptions.
- All new database models must have docstrings describing purpose and key relationships.
- Architecture Decision Records (ADRs) go in `docs/decisions/` using the template at `docs/decisions/template.md`.
- The `README.md` is updated whenever new features reach stable state.
- This `CLAUDE.md` is updated whenever governance rules change.

---

## What Agents May Modify

Without special review:
- `backend/app/api/v1/endpoints/` — new endpoints or additions to existing ones
- `backend/app/services/` — new service methods for new functionality
- `backend/app/schemas/` — new request/response schemas
- `frontend/src/components/` — new UI components
- `frontend/src/app/` — new pages and layouts
- `frontend/src/hooks/` — new custom hooks
- `backend/tests/` — test additions
- `docs/` — documentation updates
- `database/seeds/` — development seed data

---

## What Agents Must NOT Modify Without Explicit Approval

These require review by `architect-agent` + `rbac-agent` + `audit-compliance-agent`:

- `backend/app/core/security.py` — token logic
- `backend/app/core/permissions.py` — RBAC definitions
- `backend/app/api/deps.py` — authentication dependencies
- `backend/app/models/audit.py` — audit log schema
- `backend/app/services/audit_service.py` — audit ingestion
- `backend/app/models/` — any existing model (additions to new models are OK)
- `backend/alembic/versions/` — existing migration files (new migrations are OK)
- `database/schema/` — canonical schema definitions
- `infrastructure/docker-compose*.yml` — environment configuration
- `.github/workflows/` — CI/CD pipelines
- `CLAUDE.md` — this file
- Any file that handles JWT creation, validation, or refresh

Never, under any circumstances:
- Bypass RBAC checks (e.g., removing a `check_permission()` call to "simplify" code)
- Remove audit log calls from service methods
- Add cross-tenant database queries that are not behind a System Admin guard
- Hardcode `organization_id`, `user_id`, or role values
- Add secrets or credentials to source files
- Modify or delete existing `AuditLog` records programmatically
- Remove the `organization_id` filter from any repository query
