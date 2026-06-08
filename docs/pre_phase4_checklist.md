# Pre-Phase 4 Checklist — Completed 2026-06-05

Operator checklist executed before starting SDTM/ADaM/TLF/CSR build phases.

## 1. Environment stabilization

- [x] Backend venv at `backend/.venv` with pinned deps from `requirements.txt` (`httpx==0.27.2`)
- [x] Fixed Alembic migration chain (`20260605_0004` → `down_revision = c3d4e5f6a7b8`)
- [x] Local Postgres (`celerius_dev`) migrated to `20260605_0006`
- [x] Docker Postgres (`celerius_dev`) migrated to `20260605_0006`
- [x] `graph_events.idempotency_key` column present on both databases
- [x] Demo seed on local Postgres (pre-existing)
- [x] Demo seed on Docker Postgres (admin@demo.dev / DevPass123!)

## 2. Test results (pinned venv)

```bash
cd backend && .venv/bin/python -m pytest tests/ -q
# 295 passed
```

## 3. Smoke API checks (Docker backend :8000)

| Check | Result |
|-------|--------|
| GET `/health` | 200 |
| POST `/api/v1/auth/login` (admin@demo.dev) | 200 |
| GET `/api/v1/studies` | 200 |
| GET `/api/v1/intelligence/decisions?study_id=…` | 200 |
| GET `/api/v1/graph` | 200 |
| GET `/api/v1/graph/events` | 200 |
| GET `/api/v1/audit` (Admin) | 200 (fixed `ip_address` IPv4 serialization) |
| GET `/api/v1/audit` (Contributor) | 403 |

## 4. Product decisions locked

See [ADR-0008](decisions/0008-phase4-data-pipeline-scope.md):

| Decision | Value |
|----------|-------|
| SDTM IG | 3.3 |
| Validation | Pinnacle 21 |
| Study scope | Full study |
| Upload formats | CSV + Excel |
| Workflow | AI-first with human review |
| Data types | Synthetic + real PHI |
| Pipeline | Raw → SDTM → ADaM → TLF → CSR |

## 5. Still required from operator (non-code)

| Item | Status |
|------|--------|
| `ANTHROPIC_API_KEY` in `backend/.env` | ⚠️ Empty — add before AI phases |
| Pinnacle 21 license + API credentials | ⚠️ Not configured |
| BAA/DPA for real patient data | ⚠️ Legal — required before PHI upload |
| Docker-only dev (Postgres on host port **5433**) | ✅ See [DOCKER_DEV.md](DOCKER_DEV.md) |
| `ANTHROPIC_API_KEY` in root `.env` | ✅ User-provided |
| Pinnacle 21 license + API credentials | ⚠️ Placeholders set; purchase later |

## 6. Login credentials (dev)

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@demo.dev | DevPass123! |
| Contributor | contrib@demo.dev | DevPass123! |
| Reviewer | reviewer@demo.dev | DevPass123! |
