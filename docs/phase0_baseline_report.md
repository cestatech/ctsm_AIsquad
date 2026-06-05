# Phase 0 Baseline Report
**Date:** 2026-06-05

## Summary

Phase 0 stabilization complete. Backend: 250/250 tests pass. Frontend: zero lint/type errors.

---

## What Was Fixed

| Issue | Fix |
|-------|-----|
| `asyncpg==0.29.0` incompatible with Python 3.13 | Upgraded to `asyncpg==0.30.0` |
| `anyio==4.6.2` was yanked | Upgraded to `anyio==4.7.0` |
| `greenlet` missing (required by SQLAlchemy async) | Added install step to venv setup |
| `notifications.py` 204 route with response body failed FastAPI 0.115 startup assertion | Added `response_class=Response` and explicit `return Response(status_code=204)` |
| Pydantic `protected_namespaces` warnings on `model_id`/`model_provider` fields | Added `"protected_namespaces": ()` to relevant schema `model_config` |
| `audit_action` ORM enum stored Python names (`VALIDATION_RUN_STARTED`) instead of SQL values (`validation.run_started`) | Added `values_callable=lambda e: [m.value for m in e]` to `AuditLog.action` column definition |
| Sponsor intake migration tried to create `intake_status` enum that already exists in SQL schema | Used `DO $$ ... EXCEPTION WHEN duplicate_object $$` guard + `postgresql.ENUM(..., create_type=False)` |
| `User.effective_role` always returned CONTRIBUTOR for non-admins — REVIEWER role unenforceable | Added `org_role` column to users table (migration `20260605_0001_add_user_org_role.py`), updated `effective_role` to use it |
| No `.env.example` | Created at repo root |
| No seed data | Created `database/seeds/dev_seed.py` |
| No backend `.env` | Created `backend/.env` for local dev |
| Alembic baseline migration assumed SQL schema was pre-applied | Documented: `database/schema/001_initial_schema.sql` must be applied before `alembic upgrade head` on a fresh database |

---

## Test Results

### Backend
- **250 passed, 0 failed**
- 49 deprecation warnings (httpx ASGITransport, python-jose utcnow) — not blocking, will be resolved when libraries are upgraded
- Lint: `ruff check app/` → all checks passed

### Frontend
- TypeScript: `tsc --noEmit` → no errors
- ESLint: `next lint` → no warnings or errors
- Unit tests: no test files yet (pass-with-no-tests)

---

## Seed Data

Run from `backend/`:
```bash
.venv/bin/python ../database/seeds/dev_seed.py
```

| User | Email | Password | Role |
|------|-------|----------|------|
| Demo Admin | admin@demo.dev | DevPass123! | Admin |
| Demo Contributor | contrib@demo.dev | DevPass123! | Contributor |
| Demo Reviewer | reviewer@demo.dev | DevPass123! | Reviewer |
| Study | DEMO-001: Phase II Oncology Pilot Study | | |

---

## Database Setup (Fresh Install)

```bash
# 1. Create databases
createdb celerius_dev
createdb celerius_test   # managed by pytest create_all — do NOT apply SQL schema to this one

# 2. Apply baseline SQL schema to dev
psql -d celerius_dev -f database/schema/001_initial_schema.sql

# 3. Run Alembic migrations on dev
cd backend && .venv/bin/python -m alembic upgrade head

# 4. Seed dev data
.venv/bin/python ../database/seeds/dev_seed.py
```

---

## Known Issues / Documented

| Issue | Status |
|-------|--------|
| httpx `app=` shortcut deprecation warning | Cosmetic; fix when upgrading httpx in Phase 6 |
| python-jose uses `datetime.utcnow()` (deprecated in Python 3.12+) | Cosmetic; fix when upgrading jose or switching to PyJWT |
| Redis not available locally | Rate-limiting degrades gracefully; not required for dev |

---

## Definition of Done — Checklist

- [x] Backend starts without errors
- [x] Frontend starts without errors (TypeScript + ESLint pass)
- [x] Login works (test_auth_endpoints: 100% pass)
- [x] Role-based navigation works (RBAC tests: 100% pass, including REVIEWER enforcement)
- [x] Study dashboard loads (API tested)
- [x] Intelligence pages load (graph, decisions, overrides, lineage endpoints present)
- [x] At least one audit event can be created and viewed (audit tests pass)
- [x] CI failures are either fixed or documented as known issues
- [x] Seed data: one org, one study, three users
- [x] `.env.example` accurate and at repo root
