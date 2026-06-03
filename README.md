# Celerius Clinical Trial Lifecycle Platform

> An AI-native, multi-tenant SaaS platform for managing the complete clinical trial lifecycle — from study concept to regulatory-ready submission package.

---

## Platform Vision

Celerius provides end-to-end management of clinical trial artifacts with complete traceability across the full data lineage:

```
Objective → Endpoint → eCRF → SDTM → ADaM → TLF → CSR
```

Every artifact is versioned, auditable, approval-controlled, and reproducible. The platform is designed for eventual FDA, EMA, GxP, and 21 CFR Part 11 compliance.

### The Core USP: Celerius Intelligence Platform (CIP)

The **Celerius Intelligence Platform** is the primary differentiator. Where other clinical data platforms use AI as a black box, Celerius makes every AI action fully explainable and defensible:

| Layer | What it does | Why it matters |
|-------|-------------|----------------|
| **AI Decision Logging** | Every AI inference is recorded *before* it executes — agent, model, prompt hash, reasoning, confidence, input/output | FDA can ask "why did your AI map this field this way?" — answer is in the record |
| **Human Override Framework** | Every human correction to an AI value is immutably logged with mandatory justification | Complete before/after audit trail; no correction is ever lost |
| **Context Graph** | Every clinical entity (objective → endpoint → ECR → SDTM → ADaM → TLF → CSR) is a graph node; every relationship is a graph edge | One API call traces any value to its original source |
| **Data Lineage Engine** | Field-level and artifact-level provenance with transformation logic stored as code | Answers "where does ADTTE.AVAL come from?" with the actual derivation formula |
| **Validation Intelligence** | Per-rule CDISC evidence with structured waiver workflow | Waivers are regulatory-grade records, not emails — flows directly into submission package |
| **Human Review Queue** | All AI outputs surface as PENDING_REVIEW before downstream use | No AI decision reaches a submission without human sign-off |

No AI output can silently enter a regulatory submission. Every step is logged, every correction is recorded, every link is queryable.

---

## Current State

### Frontend (complete)
11 fully functional screens with role-based navigation, TanStack Query data fetching, and mock-data fallback while backend endpoints are being implemented:

| Screen | Path | Notes |
|--------|------|-------|
| Dashboard | `/dashboard` | Stats, recent studies/artifacts, approval banner |
| Studies list | `/studies` | Status filters, protocol number, phase badges |
| Create study | `/studies/new` | Admin-only; regulatory region toggles, phase select |
| Study workspace | `/studies/[id]` | Artifacts, members, status summary |
| Artifact list | `/studies/[id]/artifacts` | New artifact modal |
| Artifact detail | `/studies/[id]/artifacts/[id]` | RBAC-gated workflow actions (submit, approve, lock, amend) |
| Version history | `/studies/[id]/artifacts/[id]/versions` | Append-only, 21 CFR Part 11 notice |
| Approval queue | `/approvals` | Inline review modal with mandatory rejection notes |
| Audit log | `/audit` | Expandable rows showing before/after state |
| User management | `/users` | Admin-only; invite modal, activate/deactivate |

### Backend — Platform Foundation (complete)
- Multi-tenant architecture with organization isolation
- JWT authentication with 15-min access tokens + httpOnly refresh cookies
- Role-Based Access Control: Admin, Contributor, Reviewer
- Study, Artifact, Approval, Comment, Validation, AuditLog models
- Artifact lifecycle enforcement (DRAFT → IN_REVIEW → APPROVED → LOCKED → AMENDED)
- Append-only audit log and artifact versions
- Alembic async migrations

### CIP Intelligence Platform (Phases 1–5 complete)

The **Celerius Intelligence Platform** layer makes every AI action and data transformation explainable and traceable:

**Context Graph** (`/api/v1/graph`)
- `GraphNode` / `GraphEdge` / `GraphEvent` models — 35 node types, 29 edge types
- `ContextGraphService` — single entry point for all graph writes; idempotent upserts
- Named lineage shortcuts: `link_ecr_to_sdtm()`, `link_sdtm_to_adam()`, etc.
- Endpoints: list nodes, get neighbors, walk lineage path (BFS, configurable depth)

**AI Decision Logging** (`/api/v1/intelligence/decisions`)
- Every AI action creates an `AIDecision` record *before* executing — captures agent, model, prompt hash, reasoning, confidence, input/output JSONB
- Status lifecycle: `PENDING_REVIEW → ACCEPTED / REJECTED / OVERRIDDEN`
- Mandatory rejection notes; `AIDecisionService.begin_decision()` / `complete_decision()` pattern

**Human Override Framework** (`/api/v1/intelligence/overrides`)
- Immutable `HumanOverride` records for every AI-generated value a human corrects
- Mandatory justification field — cannot be empty
- Full before/after value capture with field-level path tracking

**Data Lineage Engine** (`/api/v1/intelligence/lineage`)
- `DataLineage` (field-level): raw ECR → SDTM → ADaM → TLF with transformation logic and code
- `ArtifactLineage` (document-level): Protocol → SAP → ADaM spec → dataset → TLF → CSR
- "Show Your Work" endpoint: given any target entity, returns full upstream + downstream chain

**Validation Intelligence** (`/api/v1/intelligence/validation-evidence`)
- `ValidationEvidence` model: per-rule evidence with `PASS / FAIL / WARNING / WAIVED` status
- Waiver requires mandatory justification stored as both evidence update and `HumanOverride`
- Linked to CDISC rule ID, standard, and the specific data element that was checked

**Synthetic Data** (models complete, service endpoint in progress)
- `SyntheticDataRun` + `SimulationAssumption` — every distributional assumption documented with source citation
- Output always labeled `SYNTHETIC`; random seed required for reproducibility

### CIP Phase 6 — Frontend Intelligence Screens (complete)

8 screens under `/intelligence`:

| Screen | Path |
|--------|------|
| Intelligence Hub | `/intelligence` |
| Context Graph Explorer | `/intelligence/graph` |
| Traceability Matrix | `/intelligence/traceability` |
| AI Decisions | `/intelligence/decisions` |
| Human Overrides | `/intelligence/overrides` |
| Lineage Explorer | `/intelligence/lineage` |
| Validation Evidence | `/intelligence/validation` |
| Synthetic Data Runs | `/intelligence/synthetic` |

### What is NOT yet implemented
- AI generation modules (Protocol, ICF, SAP, SDTM, ADaM, TLF, CSR) — Phase 7+
- Graph visualization (React Flow / Cytoscape) — Phase 7
- Pinnacle 21 integration
- Regulatory submission packaging
- Backend domain endpoints (studies, artifacts, approvals, users) — placeholders only

---

## Tech Stack

### Frontend
- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript
- **Styling:** Tailwind CSS
- **Data Fetching:** TanStack Query v5
- **Forms:** React Hook Form + Zod
- **State:** Zustand

### Backend
- **Framework:** FastAPI
- **Language:** Python 3.12
- **ORM:** SQLAlchemy 2.0
- **Migrations:** Alembic
- **Validation:** Pydantic v2

### Database
- **Primary:** PostgreSQL 16
- **Caching:** Redis (session & rate limiting)

### Authentication
- JWT access tokens (15 min expiry)
- Refresh tokens (7 day expiry, stored in httpOnly cookies)
- Per-tenant token namespacing

### Storage
- Abstract storage layer (filesystem for dev)
- S3-compatible interface (production)
- Azure Blob (future enterprise option)

### Infrastructure
- Docker + Docker Compose
- GitHub Actions CI/CD
- Nginx reverse proxy

### Testing
- **Backend:** Pytest + httpx
- **Frontend E2E:** Playwright
- **Frontend Unit:** Vitest + React Testing Library

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser Client                        │
│                    Next.js (App Router)                      │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTPS
┌─────────────────────────▼───────────────────────────────────┐
│                      Nginx Reverse Proxy                      │
└──────────┬──────────────────────────────────┬───────────────┘
           │                                  │
┌──────────▼──────────┐          ┌────────────▼──────────────┐
│   FastAPI Backend   │          │    Static Assets / CDN     │
│   (Python 3.12)     │          └───────────────────────────┘
│                     │
│  ┌───────────────┐  │
│  │  Auth Layer   │  │
│  ├───────────────┤  │
│  │  RBAC Layer   │  │
│  ├───────────────┤  │
│  │ Service Layer │  │
│  ├───────────────┤  │
│  │  Repo Layer   │  │
│  └───────┬───────┘  │
└──────────┼──────────┘
           │
┌──────────▼──────────┐     ┌───────────────────────────────┐
│    PostgreSQL 16     │     │          Redis Cache           │
│   (per-org schema   │     │   (sessions, rate limiting)    │
│    isolation)       │     └───────────────────────────────┘
└─────────────────────┘
           │
┌──────────▼──────────┐
│   Abstract Storage  │
│  (S3 / Azure Blob)  │
└─────────────────────┘
```

### Multi-Tenancy Model

Each **Organization** is an isolated tenant. Tenant isolation is enforced at:
1. **Database level** — all queries filter by `organization_id`
2. **API level** — JWT claims carry `organization_id`, validated on every request
3. **RBAC level** — roles are scoped to organization membership
4. **Storage level** — artifact files stored under `org/{org_id}/` prefix

---

## RBAC Model

Three roles govern all access:

| Role | Create | Edit | Submit | Approve | Lock | Manage Users | View Audit |
|------|--------|------|--------|---------|------|--------------|------------|
| **Admin** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Contributor** | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| **Reviewer** | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ | ✓ |

---

## Artifact Lifecycle

```
DRAFT → IN_REVIEW → APPROVED → LOCKED
          ↓                      ↓
        REJECTED              AMENDED → (new version as DRAFT)
                                         |
                                    SUPERSEDED (previous)
```

All status transitions are:
- Validated against RBAC rules
- Recorded in the audit log with actor, timestamp, and IP
- Immutable once written

---

## Local Development Setup

### Prerequisites

- Docker Desktop 4.x+
- Node.js 20+
- Python 3.12+
- `pnpm` 9+ (frontend package manager)

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/your-org/celerius.git
cd celerius

# 2. Copy environment files
cp infrastructure/.env.example .env
cp frontend/.env.local.example frontend/.env.local

# 3. Start infrastructure services
docker compose -f infrastructure/docker-compose.dev.yml up -d

# 4. Run database migrations
cd backend
pip install -r requirements.txt
alembic upgrade head
python -m app.scripts.seed_dev  # optional dev data

# 5. Start backend
uvicorn app.main:app --reload --port 8000

# 6. Start frontend (new terminal)
cd frontend
pnpm install
pnpm dev
```

Application will be available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Using Docker Compose (full stack)

```bash
docker compose -f infrastructure/docker-compose.dev.yml up --build
```

---

## Environment Variables

### Backend (`backend/.env`)

```env
# Application
APP_ENV=development
APP_SECRET_KEY=your-secret-key-min-32-chars
APP_ALLOWED_ORIGINS=http://localhost:3000

# Database
DATABASE_URL=postgresql+asyncpg://celerius:password@localhost:5432/celerius_dev

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=your-jwt-secret-min-32-chars
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Storage
STORAGE_BACKEND=filesystem
STORAGE_LOCAL_PATH=/tmp/celerius-storage
# For S3:
# STORAGE_BACKEND=s3
# AWS_ACCESS_KEY_ID=...
# AWS_SECRET_ACCESS_KEY=...
# AWS_S3_BUCKET=celerius-artifacts

# Email (for notifications)
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_FROM=noreply@celerius.dev
```

### Frontend (`frontend/.env.local`)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_APP_NAME=Celerius
NEXT_PUBLIC_APP_VERSION=0.1.0
```

---

## Project Structure

```
celerius/
├── .claude/                    # AI agent definitions and project rules
│   └── agents/                 # 14 specialized agent definitions
├── .github/
│   └── workflows/              # CI/CD pipelines
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/   # Route handlers
│   │   ├── core/               # Config, security, permissions
│   │   ├── models/             # SQLAlchemy ORM models
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── services/           # Business logic layer
│   │   ├── repositories/       # Database access layer
│   │   └── agents/             # AI agent placeholder services
│   ├── alembic/                # Database migrations
│   └── tests/                  # Backend test suite
├── frontend/
│   ├── src/
│   │   ├── app/                # Next.js App Router pages
│   │   ├── components/         # React components
│   │   ├── hooks/              # Custom React hooks
│   │   ├── lib/                # API client, auth utilities
│   │   ├── store/              # Zustand state stores
│   │   └── types/              # TypeScript type definitions
│   └── public/                 # Static assets
├── database/
│   ├── schema/                 # Canonical SQL schema definitions
│   ├── migrations/             # Tracked migration history
│   └── seeds/                  # Development seed data
├── docs/
│   ├── architecture/           # Architecture decision records
│   └── decisions/              # ADR log
├── infrastructure/
│   ├── docker/                 # Dockerfiles
│   ├── nginx/                  # Nginx configuration
│   └── docker-compose*.yml     # Environment compose files
├── scripts/                    # Development and ops scripts
├── tests/
│   └── e2e/                    # Playwright end-to-end tests
├── README.md
└── CLAUDE.md                   # AI agent governance and engineering rules
```

---

## Deployment

### Development
```bash
docker compose -f infrastructure/docker-compose.dev.yml up
```

### Staging / Production
Deployment via GitHub Actions on push to `main`. See `.github/workflows/deploy.yml`.

Required secrets in GitHub:
- `DATABASE_URL` (production)
- `JWT_SECRET_KEY`
- `APP_SECRET_KEY`
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (if S3)
- `DOCKER_REGISTRY_TOKEN`

---

## Development Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| Foundation | Auth, RBAC, Study/Artifact/Approval/Audit models | ✅ Complete |
| Frontend MVP | 11 screens, role-based nav, mock-data fallback | ✅ Complete |
| CIP Phase 1 | Context Graph (nodes, edges, events, lineage traversal) | ✅ Complete |
| CIP Phase 2 | AI Decision Logging (provenance, review lifecycle) | ✅ Complete |
| CIP Phase 3 | Human Override Framework (immutable corrections + justification) | ✅ Complete |
| CIP Phase 4 | Data Lineage Engine (field-level + artifact-level) | ✅ Complete |
| CIP Phase 5 | Validation Intelligence + Synthetic Data models | ✅ Complete |
| CIP Phase 6 | Frontend Intelligence Screens (Graph Explorer, AI Decisions, Lineage) | ✅ Complete |
| CIP Phase 7 | Graph Visualization (React Flow / Cytoscape) | 🔲 Planned |
| M1–M15 Backend | Implement domain API endpoints (studies, artifacts, approvals, etc.) | 🔲 Planned |
| AI Modules | Protocol, ICF, SAP, SDTM, ADaM, TLF, CSR generators | 🔲 Planned |
| Validation Engine | Pinnacle 21 integration, CDISC conformance checks | 🔲 Planned |
| Submission Package | Regulatory submission assembly (eCTD) | 🔲 Planned |

---

## Contributing

See `CLAUDE.md` for engineering standards, agent governance, and contribution rules.

All changes touching authentication, RBAC, multi-tenancy, audit logs, or versioning require review by `architect-agent`, `rbac-agent`, and `audit-compliance-agent` before acceptance.

---

## Regulatory Context

This platform is designed with regulatory readiness in mind:

- **21 CFR Part 11** — Electronic records and signatures
- **ICH E6(R3)** — Good Clinical Practice
- **CDISC standards** — SDTM, ADaM, define.xml
- **FDA/EMA submission** — Structured submission package support

Full compliance validation is planned for Phase 12.

---

## License

Proprietary. All rights reserved.
