# Smoke Test Checklist — Phase 0

Use this to verify basic app health after a fresh setup or deploy.

## Backend Health

```bash
cd backend
.venv/bin/python -c "from app.main import app; print('OK')"   # imports clean
curl http://localhost:8000/health                               # {"status":"ok"}
```

## Database

```bash
psql -d celerius_dev -c "SELECT count(*) FROM users;"         # >= 3 after seed
psql -d celerius_dev -c "SELECT count(*) FROM studies;"       # >= 1 after seed
psql -d celerius_dev -c "SELECT count(*) FROM alembic_version;"  # should have latest rev
```

## Auth (requires backend running)

- [ ] POST `/api/v1/auth/register` — create new org + admin → 201
- [ ] POST `/api/v1/auth/login` — correct credentials → 200 + access token
- [ ] POST `/api/v1/auth/login` — wrong password → 401
- [ ] POST `/api/v1/auth/refresh` — valid cookie → 200 + new token
- [ ] GET `/api/v1/auth/me` — valid token → user object

## RBAC Spot-checks

- [ ] Reviewer POST `/api/v1/artifacts` → 403
- [ ] Contributor POST `/api/v1/approvals` → 403
- [ ] Admin POST `/api/v1/users/invite` → 201

## Study + Artifacts

- [ ] GET `/api/v1/studies` — list returns seed study
- [ ] POST `/api/v1/artifacts` as Admin → 201
- [ ] PATCH `/api/v1/artifacts/{id}` as Admin → 200
- [ ] POST `/api/v1/artifacts/{id}/submit` → IN_REVIEW

## Intelligence

- [ ] GET `/api/v1/intelligence/decisions` → 200
- [ ] GET `/api/v1/graph/nodes` → 200
- [ ] GET `/api/v1/intelligence/lineage` → 200

## Audit

- [ ] GET `/api/v1/audit` as Admin → 200 with items
- [ ] GET `/api/v1/audit` as Contributor → 403

## Frontend

- [ ] `pnpm dev` starts without errors
- [ ] Login page loads at `/login`
- [ ] After login, dashboard at `/dashboard` loads
- [ ] Study list loads
- [ ] `/intelligence/decisions` page loads
- [ ] `/intelligence/graph` page loads

## Tests (CI equivalent)

```bash
cd backend && .venv/bin/python -m pytest tests/ -q    # 250 passed
cd frontend && pnpm lint                              # no warnings
cd frontend && pnpm type-check                        # no errors
```
