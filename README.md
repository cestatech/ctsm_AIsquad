# Celerius Clinical Trial Lifecycle Platform

> An AI-native, multi-tenant SaaS platform for managing the complete clinical trial lifecycle — from study concept to regulatory-ready submission package.

---

## Platform Vision

Celerius provides end-to-end management of clinical trial artifacts with complete traceability across the full data lineage:

```
Objective → Endpoint → eCRF → SDTM → ADaM → TLF → CSR
```

Every artifact is versioned, auditable, approval-controlled, and reproducible. The platform is designed for eventual FDA, EMA, GxP, and 21 CFR Part 11 compliance.

---

## Current State: MVP Foundation

The current codebase implements the **platform foundation only**. Full AI generation modules are planned for future phases.

**What is implemented (MVP):**
- Multi-tenant architecture with organization isolation
- JWT authentication with refresh tokens
- Role-Based Access Control (RBAC): Admin, Contributor, Reviewer
- Study workspace framework
- Artifact management with lifecycle status tracking
- Artifact versioning system
- Approval workflow engine
- Comprehensive audit logging
- Database models and migrations
- REST API structure (FastAPI)
- Frontend shell (Next.js App Router)
- AI service placeholder interfaces

**What is NOT yet implemented:**
- AI generation modules (Protocol, ICF, SAP, SDTM, ADaM, TLF, CSR)
- Pinnacle 21 integration
- Synthetic data generation
- Regulatory submission packaging

---

## Future Modules

| Module | Description |
|--------|-------------|
| Protocol Generator | AI-assisted protocol drafting from study concepts |
| ICF Generator | Informed consent form generation |
| SAP Generator | Statistical Analysis Plan generation |
| EDC/eCRF Designer | Electronic data capture form design |
| Traceability Matrix | Objective → endpoint → variable mapping |
| Synthetic Data | Test dataset generation |
| SDTM Generator | Study Data Tabulation Model automation |
| ADaM Generator | Analysis Dataset Model automation |
| TLF Generator | Tables, Listings, Figures automation |
| Pinnacle 21 | CDISC validation integration |
| CSR Generator | Clinical Study Report drafting |
| Submission Package | Regulatory submission assembly |

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
│   └── agents/                 # 10 specialized agent definitions
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
| 1 | Authentication + RBAC | Foundation complete |
| 2 | Study Workspace | Foundation complete |
| 3 | Artifact Management | Foundation complete |
| 4 | Approval Workflow | Foundation complete |
| 5 | Audit Logging | Foundation complete |
| 6 | AI Module Placeholders | Foundation complete |
| 7 | Protocol Generator | Planned |
| 8 | SAP Generator | Planned |
| 9 | SDTM Automation | Planned |
| 10 | ADaM Automation | Planned |
| 11 | TLF Automation | Planned |
| 12 | Validation Engine | Planned |
| 13 | CSR Generation | Planned |

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
