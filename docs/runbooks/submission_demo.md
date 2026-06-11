# Submission Packaging Live Demo Runbook

**Maturity:** Demonstrable on synthetic data — **not for regulatory submission**.

This runbook walks through the end-to-end submission packaging flow after Phase 1 wiring.

---

## Prerequisites

- Docker Compose stack running (Postgres, Redis, backend, frontend)
- Backend virtualenv available for seeds and tests

---

## 1. Seed the database

```bash
# From repo root — base org/users
docker compose exec backend python /database/seeds/dev_seed.py

# Demo program study (intake, documents, synthetic data)
docker compose exec backend python /database/seeds/demo_program_seed.py --all --force

# Opt-in: approved SDTM/ADaM/TLF/CSR for submission readiness
docker compose exec backend python /database/seeds/demo_program_seed.py --all --force --approve-artifacts
```

Log in as `admin@demo.dev` / `DevPass123!`.

---

## 2. Admin walkthrough

1. Open **Studies** → select `DEMO-001` (or `DEMO-002`).
2. Navigate to **Submission** (`/studies/{id}/submission`).
3. Confirm **Backend readiness: ready** (blockers listed if not).
4. Click **Package Submission**.
5. Watch status: `DRAFT` → `PACKAGING` → `READY` (may be fast).
6. Click **View manifest**:
   - SYNTHETIC DEMO banner visible
   - Real outputs: define.xml, SDTM/ADaM CSVs, TLF RTF (rendered)
   - Placeholders: CSR PDF, Reviewer's Guide PDF (amber badges)
7. Click **Download ZIP** and open locally.

---

## 3. Reviewer walkthrough

Log in as `reviewer@demo.dev` / `DevPass123!`.

- Can view manifest and checksums
- Cannot create packages or download ZIP

---

## 4. Contributor walkthrough

Log in as `contrib@demo.dev` / `DevPass123!`.

- Sees package status (read-only)
- Sees message: submission packaging requires Admin role
- No create, manifest, or download controls

---

## 5. Audience disclosure script

> "This ZIP demonstrates our full intake-to-submission workflow on **synthetic demo data**.
> CSV datasets and define.xml are generated from approved artifacts. TLF tables are rendered via our RTF engine.
> The CSR PDF and Reviewer's Guide are **labeled placeholders** — not regulatory-grade outputs.
> This package is **demonstrable**, not submission-ready."

---

## 6. Verification commands

```bash
# Frontend baseline
cd frontend && npx tsc --noEmit && pnpm test

# Backend submission tests
cd backend && .venv/bin/pytest tests/unit/test_submission_service.py tests/integration/test_submission_endpoints.py

# Playwright (mocked API)
cd frontend && pnpm test:e2e e2e/submission-packaging.spec.ts
```

---

## Placeholder inventory

| File | Grade |
|------|-------|
| `m5/datasets/sdtm/*.csv` | Generated |
| `m5/datasets/adam/*.csv` | Generated |
| `m5/define.xml` | Generated |
| `tlf/*.rtf` | Generated (RTF renderer) |
| `manifest.json` | Generated |
| `csr/*.pdf` | Placeholder |
| `m5/reviewers-guide.pdf` | Placeholder |
