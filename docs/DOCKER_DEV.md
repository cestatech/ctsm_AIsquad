# Docker-Only Development

All local development runs through Docker Compose. Do not use a local macOS Postgres instance — Docker Postgres is exposed on **host port 5433** to avoid conflicting with a system Postgres on 5432.

## Quick start

```bash
# From repo root
cp infrastructure/.env.example .env
# Edit .env: set ANTHROPIC_API_KEY (required for AI features)

docker compose -f infrastructure/docker-compose.dev.yml up -d
docker compose -f infrastructure/docker-compose.dev.yml exec backend python -m alembic upgrade head
```

**URLs**

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Mailhog UI | http://localhost:8025 |
| Postgres (host) | `localhost:5433` (user `celerius`, db `celerius_dev`) |

## Seed demo users

```bash
docker compose -f infrastructure/docker-compose.dev.yml exec backend python /database/seeds/dev_seed.py
```

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@demo.dev | DevPass123! |
| Contributor | contrib@demo.dev | DevPass123! |
| Reviewer | reviewer@demo.dev | DevPass123! |

## Seed full demo programs

After `dev_seed.py`, load complete demo studies with compiled intake, Study Brief, Protocol, ICF, SAP, eCRF/EDC mock screens, and synthetic data.

| Protocol | Study |
|----------|-------|
| `DEMO-001` | Phase II Oncology Pilot Study (NSCLC) |
| `DEMO-002` | Phase III Rheumatoid Arthritis Pivotal Study |

```bash
# Oncology demo (default)
docker compose -f infrastructure/docker-compose.dev.yml exec backend python /database/seeds/demo_program_seed.py

# Immunology / RA demo (separate study)
docker compose -f infrastructure/docker-compose.dev.yml exec backend python /database/seeds/demo_program_seed.py --protocol DEMO-002

# Both demos
docker compose -f infrastructure/docker-compose.dev.yml exec backend python /database/seeds/demo_program_seed.py --all
```

Re-run with `--force` to refresh. Open each study under **Studies** → explore Intake, Artifacts, **EDC Screens**, and **Intelligence → Synthetic Data**.

## Running tests (optional, from host venv)

Tests connect to Docker Postgres on port 5433 via `backend/.env`:

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# Copy ANTHROPIC_API_KEY from ../.env into backend/.env for AI tests
.venv/bin/python -m pytest tests/ -q
```

Ensure `celerius_test` exists:

```bash
docker exec celerius_postgres psql -U celerius -d postgres -c \
  "SELECT 1 FROM pg_database WHERE datname='celerius_test'" | grep -q 1 || \
docker exec celerius_postgres psql -U celerius -d postgres -c \
  "CREATE DATABASE celerius_test OWNER celerius;"
```

## Environment variables

Single source of truth: **repo root `.env`**, loaded by `docker-compose.dev.yml` into the backend container.

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | AI generation and mapping (required) |
| `PINNACLE21_ENABLED` | Set `true` after license purchase |
| `PINNACLE21_API_KEY` | Pinnacle 21 API key (placeholder until purchased) |
| `PINNACLE21_PROJECT_ID` | Pinnacle 21 project ID |
| `SDTM_IG_VERSION` | `3.3` (locked per ADR-0008) |

## Restart after .env changes

```bash
docker compose -f infrastructure/docker-compose.dev.yml up -d --force-recreate backend
```
